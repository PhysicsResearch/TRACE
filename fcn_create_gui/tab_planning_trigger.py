"""
Beam trigger UI for the Planning tab (core logic: fcn_plan/fcn_trigger.py, Qt-free).

Hooked in by tab_planning.py (buttons, tabs) and fcn_plan/fcn_create.py (Margins checkbox, plot overlay):

* Curve tab: 'Trigger On', 'Trigger Off' and 'Clear Trigger' under the wait buttons.  They use the same
  'Time (s)' box as the waits and answer in a status line under the buttons (no dialog).  They place switch events
  (fcn_trigger.trg_switch_at), so windows can be set in any order, also every On before the Offs: an On before a
  later window runs into it, an On inside a run places a window start there (one green run, a dotted mark where that
  window starts, an orange status line) until a Trigger Off ends the earlier part.  An Off right at such a start
  removes it (the two windows touch: one run, the same cells as in time order; an Off on the row of a mistaken On
  cancels it).
* 'Periodic' tab (after Curve): a repetition (range, period P, first-event offset) and what happens at every
  event: trigger on for D (with Combine), trigger off for D, wait radiation or wait user.
* 'Trigger' tab (after Periodic): position-gated trigger.  Per axis Use / Min / Max (or the same margins for all
  used axes), flip, range and Combine.  The trigger is ON where every used axis lies inside its margins.
* Plot (``trg_draw_overlay``, called from update_plot): every applied trigger-on window gets a light-green cover
  (from the full plan, not the downsampled plot data).  With the 'Margins' checkbox (right under Acceleration) the
  margins are drawn as dashed lines in the axis colour (with Position shown; they do not rescale the plot, and the
  used axis' curve is brought to the front) and the spans where the gate (or, while the 'Periodic' tab is open, the
  periodic pattern) WOULD switch the trigger on are shaded gray: a live preview before Apply.

Every button / Apply is one undo step (push_curve_state); the plan is re-baked (the switches are G1 boundaries)
and stored in the device DataFrame like the existing actions.
"""
import numpy as np
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox, QPushButton, QLabel, QCheckBox, QComboBox,
    QDoubleSpinBox, QRadioButton, QButtonGroup, QScrollArea, QFrame, QSizePolicy
)

from fcn_plan import fcn_trigger as trg

PREVIEW_COLOR = "#757575"
PREVIEW_ALPHA = 0.22
PREVIEW_HATCH = "///"
MARGIN_LINEWIDTH = 1.4
CURVE_FRONT_ZORDER = 2.5          # used axis' position curve above the other curves (Line2D default 2) with Margins on
PREVIEW_DEBOUNCE_MS = 250
INNER_START_COLOR = "#2e7d32"     # dotted mark of a window start inside a green run (manual On before a later window)
WAIT_LINE_STYLES = {'rad': '#e53935', 'usr': '#fbc02d'}   # update_plot's wait colours (radiation / user)
WAIT_LINES_MAX_ARTISTS = 300      # more waits of one kind than this: one LineCollection instead of axvlines
ROTARY_PLAN_AXES = ("Roll", "Pitch", "Yaw")
# same colours as update_plot (used before the first plot has handed its colours over)
FALLBACK_AXIS_COLORS = {
    'X': '#1976d2', 'Y': '#f57c00', 'Z': '#388e3c', 'LAT': '#1976d2', 'SI': '#f57c00', 'AP': '#388e3c',
    'Roll': '#7b1fa2', 'Pitch': '#d32f2f', 'Yaw': '#0097a7',
}

_LABEL_STYLE = "font-weight: bold; font-size: 14px;"
_HINT_STYLE = "font-size: 13px; color: #555555;"


# ----------------------------------------------------------------------------
# Plan access
# ----------------------------------------------------------------------------
def _device(self):
    combo = getattr(self, 'combo_device', None)
    return combo.currentText() if combo is not None else "Lung Phantom"


def _plan(self):
    df = getattr(self, 'dfEdit', None)
    if df is None or 'time' not in df.columns or len(df) == 0:
        return None
    return df


def _commands(df):
    if 'Command' not in df.columns:
        return [""] * len(df)
    return df['Command'].tolist()


def _plan_axes(self):
    """Position axes of the current device's plan (the gate rows)."""
    df = _plan(self)
    if df is None:
        return []
    device = _device(self)
    if device == "Lung Phantom":
        cand = ['X', 'Y', 'Z']
    elif device == "Motion Platform":
        cand = ['LAT', 'SI', 'AP', 'Roll', 'Pitch', 'Yaw']
    else:
        cand = [c for c in df.columns if c not in ('timestamp', 'time', 'Command')
                and not str(c).startswith(('Vel.', 'Acc.'))]
    return [c for c in cand if c in df.columns]


def _plot_frame(self):
    """The plan as plotted (Motion Platform: through compute_motion_platform_actuators, like trigger_plot_update),
    so the gate is evaluated on the values the margins are drawn against."""
    df = _plan(self)
    if df is None:
        return None
    if _device(self) == "Motion Platform":
        from fcn_plan.fcn_create import compute_motion_platform_actuators
        return compute_motion_platform_actuators(self, df)
    return df


def _axis_unit(ax):
    return "deg" if ax in ROTARY_PLAN_AXES else "mm"


def _axis_color(self, ax):
    colors = getattr(self, 'trg_axis_colors', None) or {}
    return colors.get(ax) or FALLBACK_AXIS_COLORS.get(ax) or "#455a64"


# ----------------------------------------------------------------------------
# Status / commit
# ----------------------------------------------------------------------------
def _set_label(lbl, text, kind="ok"):
    if lbl is None:
        return
    color = {"ok": "#1b5e20", "warn": "#e65100", "error": "#c62828", "hint": "#555555"}.get(kind, "#1b5e20")
    lbl.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {color};" if kind != "hint" else _HINT_STYLE)
    lbl.setText(text)
    lbl.setProperty("trg_kind", kind)


def _clear_stale(lbl):
    """An error / warning in a summary line is stale once the user changes the inputs."""
    if lbl is not None and lbl.property("trg_kind") in ("error", "warn"):
        _set_label(lbl, "", "hint")


def _trg_status(self, text, kind="ok"):
    self.trg_last_message = text
    _set_label(getattr(self, 'trg_status_label', None), text, kind)


def _trg_commit(self, new_cmds, message, summary_label=None, kind="ok"):
    """One undo step: write the Command column, re-bake (switches are G1 boundaries), store, refresh.
    ``kind`` 'warn' shows the message in orange (applied, but something fell below the row resolution)."""
    from fcn_plan.fcn_create import (push_curve_state, bake_plan_steps, compute_motion_platform_actuators,
                                     loadTable_create, trigger_plot_update)
    from fcn_plan.fcn_edit import getDataframeFromTable
    push_curve_state(self)
    df = self.dfEdit
    df['Command'] = list(new_cmds)
    device = _device(self)
    baked = bake_plan_steps(self, df, device)
    if baked is not df and device == "Motion Platform":
        baked = compute_motion_platform_actuators(self, baked)
    self.dfEdit = baked
    if device == "Lung Phantom":
        self.dfEdit_lung_phantom = self.dfEdit
    elif device == "Motion Platform":
        self.dfEdit_motion_platform = self.dfEdit
    else:
        self.dfEdit_other = self.dfEdit
    loadTable_create(self, self.dfEdit)
    getDataframeFromTable(self)
    trigger_plot_update(self)
    _trg_status(self, message, kind)
    if summary_label is not None:
        _set_label(summary_label, message, kind)


def _ensure_plan(self):
    if getattr(self, 'dfEdit', None) is None:
        from fcn_plan.fcn_create import initialize_default_curve_data
        initialize_default_curve_data(self)
    df = _plan(self)
    if df is None or len(df) < 2:
        return None
    return df


# ----------------------------------------------------------------------------
# Curve tab: Trigger On / Off / Clear
# ----------------------------------------------------------------------------
def trg_manual_switch(self, on):
    """Trigger On / Off at 'Time (s)' (nearest plan row).  Returns the info dict of fcn_trigger.trg_switch_at."""
    df = _ensure_plan(self)
    if df is None:
        _trg_status(self, "The plan is empty.", "error")
        return None
    box = getattr(self, 'input_wait_rad_time', None)
    if box is None:
        _trg_status(self, "Time input field is missing.", "error")
        return None
    t = df['time'].to_numpy(dtype=float)
    new, info = trg.trg_switch_at(t, _commands(df), float(box.value()), on)
    if not info.get('changed'):
        _trg_status(self, info.get('message', 'Nothing changed.'), "warn")
        return info
    # an On that runs into a later window, or a window start placed inside a run (the trigger is already on there):
    # orange, the message says what a Trigger Off does next
    merged = info.get('merged_into') is not None or info.get('inner_start') is not None
    _trg_commit(self, new, info['message'], kind="warn" if merged else "ok")
    return info


def trg_clear_action(self):
    df = _ensure_plan(self)
    if df is None:
        _trg_status(self, "The plan is empty.", "error")
        return 0
    t = df['time'].to_numpy(dtype=float)
    cmds = _commands(df)
    n_win = len(trg.trg_windows(t, cmds))
    new, removed = trg.trg_clear(cmds)
    if not removed:
        _trg_status(self, "No trigger to clear.", "warn")
        return 0
    _trg_commit(self, new, f"Trigger cleared: {n_win} window{'s' if n_win != 1 else ''} removed.")
    return n_win


def _btn(parent, text, bg, fg, hover, border=None, size=15):
    b = QPushButton(text, parent)
    b.setMinimumHeight(40)
    bd = f"border: 1px solid {border};" if border else ""
    b.setStyleSheet(f"""
        QPushButton {{
            background-color: {bg};
            color: {fg};
            font-weight: bold;
            font-size: {size}px;
            border-radius: 6px;
            {bd}
            padding: 0px 12px;
        }}
        QPushButton:hover {{
            background-color: {hover};
        }}
    """)
    return b


def trg_add_buttons(self, parent_vlay, time_vlay=None):
    """Second row under the wait buttons: Trigger On / Trigger Off / Clear Trigger, plus the status line.
    ``time_vlay`` (the 'Time (s)' column) gets a stretch so the box stays level with the wait buttons."""
    parent = self.groupBox_BrCv_createCurve
    if time_vlay is not None:
        time_vlay.addStretch()
    row = QHBoxLayout()
    row.setSpacing(10)
    self.button_trigger_on = _btn(parent, "Trigger On", "#43a047", "white", "#2e7d32")
    self.button_trigger_off = _btn(parent, "Trigger Off", "#a5d6a7", "#1b5e20", "#81c784")
    self.button_clear_trigger = _btn(parent, "Clear Trigger", "#e8f5e9", "#2e7d32", "#c8e6c9", border="#43a047",
                                     size=14)
    for b in (self.button_trigger_on, self.button_trigger_off, self.button_clear_trigger):
        row.addWidget(b)
    row.addStretch()
    parent_vlay.addLayout(row)
    self.trg_status_label = QLabel("", parent)
    self.trg_status_label.setWordWrap(True)
    parent_vlay.addWidget(self.trg_status_label)
    _set_label(self.trg_status_label, f"Trigger On / Off switch the 5 V output (M42 P{trg.TRIGGER_PORT}) at "
                                      f"Time (s); several windows are possible, set in any order.", "hint")
    self.button_trigger_on.clicked.connect(lambda: trg_manual_switch(self, True))
    self.button_trigger_off.clicked.connect(lambda: trg_manual_switch(self, False))
    self.button_clear_trigger.clicked.connect(lambda: trg_clear_action(self))
    _trg_update_hints(self, None)


# ----------------------------------------------------------------------------
# Shared widgets
# ----------------------------------------------------------------------------
def _scroll_tab(tw):
    w = QWidget(tw)
    outer = QVBoxLayout(w)
    outer.setContentsMargins(0, 0, 0, 0)
    sc = QScrollArea(w)
    sc.setWidgetResizable(True)
    sc.setFrameShape(QFrame.NoFrame)
    content = QWidget()
    lay = QVBoxLayout(content)
    lay.setContentsMargins(10, 8, 10, 8)
    lay.setSpacing(8)
    sc.setWidget(content)
    outer.addWidget(sc)
    return w, content, lay


def _spin(parent, value, vmin, vmax, decimals=2, step=0.1, width=None):
    sp = QDoubleSpinBox(parent)
    sp.setDecimals(decimals)
    sp.setRange(vmin, vmax)
    sp.setSingleStep(step)
    sp.setValue(value)
    sp.setMinimumHeight(36)
    if width:
        sp.setMinimumWidth(width)
    return sp


def _labelled(parent, text, widget):
    lay = QVBoxLayout()
    lay.setSpacing(2)
    lbl = QLabel(text, parent)
    lbl.setStyleSheet(_LABEL_STYLE)
    lay.addWidget(lbl)
    lay.addWidget(widget)
    return lay, lbl


def _combine_combo(parent):
    cb = QComboBox(parent)
    cb.setMinimumHeight(36)
    for mode in trg.COMBINE_MODES:
        cb.addItem(trg.COMBINE_LABELS[mode], mode)
    cb.setToolTip("How the new windows join the trigger windows already in the plan:\n"
                  "Add (union): on where either is on.\n"
                  "Replace in range: inside the range only the new windows; outside unchanged.\n"
                  "Only where both: inside the range on only where both are on (intersection); outside unchanged.")
    return cb


def _range_row(self, parent, on_change):
    """'Range: (o) Full plan ( ) Subset  From (s) [ ]  To (s) [ ]' -> (layout, widgets)."""
    lay = QHBoxLayout()
    lay.setSpacing(10)
    lbl = QLabel("Range:", parent)
    lbl.setStyleSheet(_LABEL_STYLE)
    full = QRadioButton("Full plan", parent)
    sub = QRadioButton("Subset", parent)
    for r in (full, sub):
        r.setStyleSheet("font-size: 14px; font-weight: bold;")
    grp = QButtonGroup(parent)
    grp.addButton(full)
    grp.addButton(sub)
    full.setChecked(True)
    r0 = _spin(parent, 0.0, 0.0, 100000.0, 2, 0.5, 90)
    r1 = _spin(parent, 0.0, 0.0, 100000.0, 2, 0.5, 90)
    l0 = QLabel("From (s):", parent)
    l1 = QLabel("To (s):", parent)
    for x in (l0, l1):
        x.setStyleSheet("font-size: 14px;")
    w = {'full': full, 'subset': sub, 'r0': r0, 'r1': r1, 'group': grp}

    def sync(_=None):
        on = sub.isChecked()
        r0.setEnabled(on)
        r1.setEnabled(on)
        if on and r1.value() <= r0.value():
            df = _plan(self)
            if df is not None:
                r1.setValue(float(df['time'].max()))
        on_change()

    sub.toggled.connect(sync)
    r0.valueChanged.connect(lambda _v: on_change())
    r1.valueChanged.connect(lambda _v: on_change())
    r0.setEnabled(False)
    r1.setEnabled(False)
    for x in (lbl, full, sub, l0, r0, l1, r1):
        lay.addWidget(x)
    return lay, w


def _range_of(w):
    return None if w['full'].isChecked() else (float(w['r0'].value()), float(w['r1'].value()))


# ----------------------------------------------------------------------------
# Periodic tab
# ----------------------------------------------------------------------------
def _build_periodic_tab(self, tw):
    w, content, lay = _scroll_tab(tw)
    gb = QGroupBox("Periodic Pattern", content)
    g = QVBoxLayout(gb)
    g.setContentsMargins(12, 8, 12, 8)
    g.setSpacing(8)
    sched = lambda *_: _trg_input_changed(self)

    row1 = QHBoxLayout()
    row1.setSpacing(12)
    self.trg_per_action = QComboBox(gb)
    self.trg_per_action.setMinimumHeight(36)
    for a in trg.PERIODIC_ACTIONS:
        self.trg_per_action.addItem(trg.PERIODIC_LABELS[a], a)
    self.trg_per_action.setToolTip("Trigger on: on for D at every event.  Trigger off: trigger forced off for D at every "
                                   "event.\nWait radiation / Wait user: the pause at every event (added to the row).")
    self.trg_per_period = _spin(gb, 2.0, 0.001, 100000.0, 3, 0.5, 90)
    self.trg_per_duration = _spin(gb, 0.5, 0.0, 100000.0, 3, 0.1, 90)
    self.trg_per_offset = _spin(gb, 0.0, 0.0, 100000.0, 3, 0.5, 90)
    self.trg_per_combine = _combine_combo(gb)
    for text, wid in (("Action:", self.trg_per_action), ("Period P (s):", self.trg_per_period),
                      ("Duration D (s):", self.trg_per_duration), ("First event offset (s):", self.trg_per_offset),
                      ("Combine:", self.trg_per_combine)):
        sub, _ = _labelled(gb, text, wid)
        row1.addLayout(sub)
    row1.addStretch()
    g.addLayout(row1)

    rr, self.trg_per_range = _range_row(self, gb, sched)
    rr.addStretch()
    g.addLayout(rr)

    row3 = QHBoxLayout()
    row3.setSpacing(12)
    self.button_trg_periodic_apply = _btn(gb, "Apply Periodic", "#43a047", "white", "#2e7d32")
    self.button_trg_periodic_apply.setMinimumWidth(150)
    row3.addWidget(self.button_trg_periodic_apply)
    self.trg_per_summary = QLabel("", gb)
    self.trg_per_summary.setWordWrap(True)
    self.trg_per_summary.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
    row3.addWidget(self.trg_per_summary, 1)
    g.addLayout(row3)

    self.trg_per_hint = QLabel("", gb)
    self.trg_per_hint.setWordWrap(True)
    self.trg_per_hint.setStyleSheet(_HINT_STYLE)
    g.addWidget(self.trg_per_hint)
    lay.addWidget(gb)
    lay.addStretch()

    def on_action(_=None):
        a = self.trg_per_action.currentData()
        self.trg_per_duration.setEnabled(a in ("trigger_on", "beam_off"))
        self.trg_per_combine.setEnabled(a == "trigger_on")
        sched()

    self.trg_per_action.currentIndexChanged.connect(on_action)
    for sp in (self.trg_per_period, self.trg_per_duration, self.trg_per_offset):
        sp.valueChanged.connect(sched)
    self.button_trg_periodic_apply.clicked.connect(lambda: trg_apply_periodic_ui(self))
    on_action()
    return w


def _periodic_params(self):
    return (self.trg_per_action.currentData(), float(self.trg_per_period.value()),
            float(self.trg_per_duration.value()), float(self.trg_per_offset.value()),
            _range_of(self.trg_per_range), self.trg_per_combine.currentData())


def _open_run_note(t, cmds, rng):
    """A window that is on up to the plan end (closed only by the S0 on the last row, e.g. a Trigger On whose Trigger
    Off is still to come) and overlaps the Apply range: the pattern merges with that run, and a Trigger Off entered
    afterwards changes the pattern too (the switch events store no pending Off).  Returns a warning text, or ''."""
    try:
        wins = trg.trg_windows(t, cmds)
        if not wins:
            return ""
        a, b = wins[-1]
        t_end = float(t[-1])
        r0, r1 = trg.trg_resolve_range(t, rng)
    except Exception:
        return ""
    if abs(b - t_end) > 1e-6 or not a < r1 - 1e-9:
        return ""
    return (f" Note: the window from {a:.3f} s is on up to the plan end and overlaps this range. If its Trigger Off "
            f"is still to come, Undo, enter that Off first and Apply again: otherwise the pattern merges with it and "
            f"the later Off changes the pattern too.")


def trg_apply_periodic_ui(self):
    """Apply of the Periodic tab (one undo step).  Returns the summary dict, or None on an error / no change."""
    df = _ensure_plan(self)
    if df is None:
        _set_label(self.trg_per_summary, "The plan is empty.", "error")
        return None
    action, period, duration, offset, rng, combine = _periodic_params(self)
    t = df['time'].to_numpy(dtype=float)
    try:
        new, summ = trg.trg_apply_periodic(t, _commands(df), action, period, duration, offset, rng, combine)
    except ValueError as e:
        _set_label(self.trg_per_summary, str(e), "error")
        _trg_status(self, str(e), "error")
        return None
    if action in ("wait_rad", "wait_user") and not summ.get('n_added'):
        _set_label(self.trg_per_summary, summ['text'] + " Nothing changed.", "warn")
        return summ
    note = _open_run_note(t, _commands(df), rng) if action in ("trigger_on", "beam_off") else ""
    if note:
        summ = dict(summ, text=summ['text'] + note, open_run=True)
    _trg_commit(self, new, summ['text'], self.trg_per_summary, "warn" if summ.get('warning') or note else "ok")
    return summ


# ----------------------------------------------------------------------------
# Trigger tab (position-gated)
# ----------------------------------------------------------------------------
def _build_gate_tab(self, tw):
    w, content, lay = _scroll_tab(tw)
    gb = QGroupBox("Position-Gated Trigger", content)
    g = QVBoxLayout(gb)
    g.setContentsMargins(12, 8, 12, 8)
    g.setSpacing(8)
    sched = lambda *_: _trg_input_changed(self)

    self.trg_gate_hint = QLabel("", gb)
    self.trg_gate_hint.setWordWrap(True)
    self.trg_gate_hint.setStyleSheet(_HINT_STYLE)
    g.addWidget(self.trg_gate_hint)

    self.trg_gate_axes_widget = QWidget(gb)
    self.trg_gate_grid = QGridLayout(self.trg_gate_axes_widget)
    self.trg_gate_grid.setContentsMargins(0, 0, 0, 0)
    self.trg_gate_grid.setHorizontalSpacing(10)
    self.trg_gate_grid.setVerticalSpacing(4)
    axes_row = QHBoxLayout()
    axes_row.addWidget(self.trg_gate_axes_widget)
    axes_row.addStretch()
    g.addLayout(axes_row)
    self.trg_gate_rows = {}
    self.trg_gate_values = {}
    self._trg_gate_axes = None

    opt = QHBoxLayout()
    opt.setSpacing(10)
    self.trg_same_cb = QCheckBox("Same margins for all axes", gb)
    self.trg_same_cb.setStyleSheet(_LABEL_STYLE)
    self.trg_same_min = _spin(gb, 0.0, -100000.0, 100000.0, 2, 0.5, 90)
    self.trg_same_max = _spin(gb, 10.0, -100000.0, 100000.0, 2, 0.5, 90)
    l0 = QLabel("Min:", gb)
    l1 = QLabel("Max:", gb)
    for x in (l0, l1):
        x.setStyleSheet("font-size: 14px;")
    self.trg_flip_cb = QCheckBox("Flip (on outside the margins)", gb)
    self.trg_flip_cb.setStyleSheet(_LABEL_STYLE)
    for x in (self.trg_same_cb, l0, self.trg_same_min, l1, self.trg_same_max):
        opt.addWidget(x)
    opt.addSpacing(20)
    opt.addWidget(self.trg_flip_cb)
    opt.addStretch()
    g.addLayout(opt)

    rr, self.trg_gate_range = _range_row(self, gb, sched)
    rr.addSpacing(20)
    lc = QLabel("Combine:", gb)
    lc.setStyleSheet(_LABEL_STYLE)
    self.trg_gate_combine = _combine_combo(gb)
    rr.addWidget(lc)
    rr.addWidget(self.trg_gate_combine)
    rr.addStretch()
    g.addLayout(rr)

    row3 = QHBoxLayout()
    row3.setSpacing(12)
    self.button_trg_gate_apply = _btn(gb, "Apply Margins", "#43a047", "white", "#2e7d32")
    self.button_trg_gate_apply.setMinimumWidth(150)
    row3.addWidget(self.button_trg_gate_apply)
    self.trg_gate_summary = QLabel("", gb)
    self.trg_gate_summary.setWordWrap(True)
    self.trg_gate_summary.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
    row3.addWidget(self.trg_gate_summary, 1)
    g.addLayout(row3)
    lay.addWidget(gb)
    lay.addStretch()

    self.trg_same_cb.toggled.connect(lambda _c: (_trg_update_gate_enabled(self), sched()))
    self.trg_same_min.valueChanged.connect(sched)
    self.trg_same_max.valueChanged.connect(sched)
    self.trg_flip_cb.toggled.connect(sched)
    self.button_trg_gate_apply.clicked.connect(lambda: trg_apply_gate_ui(self))
    _trg_update_gate_enabled(self)
    return w


def _store_gate_values(self):
    for ax, w in getattr(self, 'trg_gate_rows', {}).items():
        self.trg_gate_values[ax] = {'use': w['use'].isChecked(), 'min': w['min'].value(), 'max': w['max'].value()}


def _default_margins(self, ax):
    df = _plan(self)
    try:
        v = np.asarray(df[ax], dtype=float)
        v = v[np.isfinite(v)]
        lo, hi = float(v.min()), float(v.max())
        return np.floor(lo * 100.0) / 100.0, np.ceil(hi * 100.0) / 100.0
    except Exception:
        return 0.0, 10.0


def trg_refresh_gate_rows(self, force=False):
    """(Re)builds one row per position axis of the current plan; values are kept per axis name."""
    grid = getattr(self, 'trg_gate_grid', None)
    if grid is None:
        return
    axes = _plan_axes(self)
    if not force and axes == self._trg_gate_axes:
        _trg_update_gate_enabled(self)
        return
    _store_gate_values(self)
    while grid.count():
        item = grid.takeAt(0)
        if item.widget():
            item.widget().deleteLater()
    self.trg_gate_rows = {}
    parent = self.trg_gate_axes_widget
    sched = lambda *_: _trg_input_changed(self)
    halves = 2 if len(axes) > 3 else 1
    per_col = int(np.ceil(len(axes) / halves)) if axes else 0
    for h in range(halves):
        c0 = h * 5
        for k, text in enumerate(("Axis", "Use", "Min", "Max")):
            lbl = QLabel(text, parent)
            lbl.setStyleSheet("font-weight: bold; font-size: 13px; color: #546e7a;")
            grid.addWidget(lbl, 0, c0 + k)
        if h < halves - 1:
            grid.setColumnMinimumWidth(c0 + 4, 24)
    for i, ax in enumerate(axes):
        h, r = divmod(i, per_col) if per_col else (0, i)
        c0 = h * 5
        vals = self.trg_gate_values.get(ax)
        if vals is None:
            lo, hi = _default_margins(self, ax)
            vals = {'use': False, 'min': lo, 'max': hi}
            self.trg_gate_values[ax] = vals
        name = QLabel(f"{ax} ({_axis_unit(ax)})", parent)
        name.setStyleSheet(f"font-weight: bold; font-size: 14px; color: {_axis_color(self, ax)};")
        use = QCheckBox(parent)
        use.setChecked(bool(vals['use']))
        use.setToolTip(f"Use {ax} in the condition (unchecked: {ax} is ignored)")
        lo = _spin(parent, float(vals['min']), -100000.0, 100000.0, 2, 0.5, 90)
        hi = _spin(parent, float(vals['max']), -100000.0, 100000.0, 2, 0.5, 90)
        grid.addWidget(name, r + 1, c0)
        grid.addWidget(use, r + 1, c0 + 1)
        grid.addWidget(lo, r + 1, c0 + 2)
        grid.addWidget(hi, r + 1, c0 + 3)
        use.toggled.connect(lambda c, a=ax: (_trg_use_toggled(self, a, c), sched()))
        lo.valueChanged.connect(sched)
        hi.valueChanged.connect(sched)
        self.trg_gate_rows[ax] = {'use': use, 'min': lo, 'max': hi, 'label': name}
    self._trg_gate_axes = axes
    _trg_update_gate_enabled(self)


def _trg_use_toggled(self, ax, checked):
    """Ticking 'Use' on an axis whose margins were never set (Min == Max) starts from the axis' data range."""
    w = self.trg_gate_rows.get(ax)
    if checked and w is not None and w['min'].value() == w['max'].value():
        frame = _plot_frame(self)
        if frame is not None and ax in frame.columns:
            v = np.asarray(frame[ax], dtype=float)
            v = v[np.isfinite(v)]
            if len(v) and v.max() > v.min():
                w['min'].setValue(float(np.floor(v.min() * 100.0) / 100.0))
                w['max'].setValue(float(np.ceil(v.max() * 100.0) / 100.0))
    _trg_update_gate_enabled(self)


def _trg_update_gate_enabled(self):
    same = self.trg_same_cb.isChecked() if hasattr(self, 'trg_same_cb') else False
    for w in getattr(self, 'trg_gate_rows', {}).values():
        use = w['use'].isChecked()
        w['min'].setEnabled(use and not same)
        w['max'].setEnabled(use and not same)
    if hasattr(self, 'trg_same_min'):
        self.trg_same_min.setEnabled(same)
        self.trg_same_max.setEnabled(same)


def _gate_params(self):
    """(limits {axis: (min, max)} of the used axes, flip, range, combine)."""
    same = self.trg_same_cb.isChecked()
    limits = {}
    for ax, w in self.trg_gate_rows.items():
        if w['use'].isChecked():
            limits[ax] = ((float(self.trg_same_min.value()), float(self.trg_same_max.value())) if same
                          else (float(w['min'].value()), float(w['max'].value())))
    return limits, self.trg_flip_cb.isChecked(), _range_of(self.trg_gate_range), self.trg_gate_combine.currentData()


def trg_apply_gate_ui(self):
    """Apply of the Trigger tab (one undo step).  Returns the summary dict, or None on an error."""
    df = _ensure_plan(self)
    if df is None:
        _set_label(self.trg_gate_summary, "The plan is empty.", "error")
        return None
    trg_refresh_gate_rows(self)
    limits, flip, rng, combine = _gate_params(self)
    frame = _plot_frame(self)
    t = df['time'].to_numpy(dtype=float)
    try:
        values = {ax: frame[ax].to_numpy(dtype=float) for ax in limits}
        new, summ = trg.trg_apply_gate(t, _commands(df), values, limits, flip, rng, combine)
    except (ValueError, KeyError) as e:
        msg = str(e).strip("'\"")
        _set_label(self.trg_gate_summary, msg, "error")
        _trg_status(self, msg, "error")
        return None
    note = _open_run_note(t, _commands(df), rng)
    if note:
        summ = dict(summ, text=summ['text'] + note, open_run=True)
    _trg_commit(self, new, summ['text'], self.trg_gate_summary, "warn" if note else "ok")
    return summ


# ----------------------------------------------------------------------------
# Tabs, Margins checkbox, preview scheduling
# ----------------------------------------------------------------------------
def trg_build_tabs(self):
    """Adds 'Periodic' and 'Trigger' right after 'Curve' (called after the Curve tab was added)."""
    tw = self.create_settings_tab_widget
    self.trg_periodic_tab = _build_periodic_tab(self, tw)
    tw.addTab(self.trg_periodic_tab, "Periodic")
    self.trg_gate_tab = _build_gate_tab(self, tw)
    tw.addTab(self.trg_gate_tab, "Trigger")
    self._trg_preview_timer = QTimer(tw)
    self._trg_preview_timer.setSingleShot(True)
    self._trg_preview_timer.setInterval(PREVIEW_DEBOUNCE_MS)
    self._trg_preview_timer.timeout.connect(lambda: _trg_preview_now(self))
    tw.currentChanged.connect(lambda _i: _trg_on_subtab_changed(self))
    _trg_update_hints(self, None)


def _trg_on_subtab_changed(self):
    tw = getattr(self, 'create_settings_tab_widget', None)
    if tw is not None and tw.currentWidget() is getattr(self, 'trg_gate_tab', None):
        trg_refresh_gate_rows(self)
    _trg_schedule_preview(self)


def trg_add_margins_checkbox(self, layout_cb):
    """'Margins' checkbox next to Acceleration (called from rebuild_axis_checkboxes; keeps its state in
    self.trg_show_margins).  It sits right UNDER Acceleration, in one column with it: the Motion Platform row (14 axes)
    already needs ~1840 px, and one more checkbox column in the row pushed the window's minimum width past a 1920 px
    screen.  The column is a widget, so the row rebuild deletes it together with both checkboxes."""
    from PySide6.QtWidgets import QCheckBox as _QCheckBox
    row = self.create_plot_checkboxes_widget
    cb = _QCheckBox("Margins", row)
    cb.setChecked(bool(getattr(self, 'trg_show_margins', False)))
    cb.setStyleSheet("font-weight: bold; font-size: 14px; color: #616161; margin-right: 12px;")
    cb.setToolTip("Show the margins of the 'Trigger' tab (dashed, axis colour; with Position shown) and shade in gray "
                  "where the trigger would be on (live preview before Apply).\nWhile the 'Periodic' tab is open: its "
                  "windows.")
    cb.toggled.connect(lambda c: _trg_margins_toggled(self, c))
    acc = getattr(self, 'check_show_acc', None)
    idx = layout_cb.indexOf(acc) if acc is not None else -1
    if idx >= 0:
        layout_cb.removeWidget(acc)
        col = QWidget(row)
        v = QVBoxLayout(col)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        v.addWidget(acc)
        v.addWidget(cb)
        layout_cb.insertWidget(idx, col)
        self.trg_margins_column = col
    else:
        layout_cb.addWidget(cb)
    self.check_show_trg_margins = cb
    trg_refresh_gate_rows(self)


def _trg_margins_toggled(self, checked):
    self.trg_show_margins = bool(checked)
    from fcn_plan.fcn_create import trigger_plot_update
    trigger_plot_update(self)


def _trg_input_changed(self):
    """Any Periodic / Trigger tab input changed: drop a stale error line, refresh the preview (debounced)."""
    _clear_stale(getattr(self, 'trg_per_summary', None))
    _clear_stale(getattr(self, 'trg_gate_summary', None))
    _trg_schedule_preview(self)


def _trg_schedule_preview(self):
    if not getattr(self, 'trg_show_margins', False):
        return
    timer = getattr(self, '_trg_preview_timer', None)
    if timer is not None:
        timer.start()


def _trg_preview_now(self):
    if getattr(self, 'trg_show_margins', False) and getattr(self, 'dfEdit', None) is not None:
        from fcn_plan.fcn_create import trigger_plot_update
        trigger_plot_update(self)


def _trg_update_hints(self, dt):
    if dt is not None and dt == getattr(self, '_trg_hint_dt', None):
        return
    self._trg_hint_dt = dt
    res = f"every {dt:.3f} s" if dt else "the plan row spacing"
    snap = f"Times snap to the nearest plan row ({res})."
    if getattr(self, 'trg_per_hint', None) is not None:
        self.trg_per_hint.setText(
            "Events at range start + offset + k*P, before the range end. Trigger on: on for D at every event "
            "(Combine joins it with the windows already in the plan). Trigger off: the trigger is forced off for D at "
            "every event. Wait radiation / Wait user: the pause at every event, added to that row. " + snap)
    if getattr(self, 'trg_gate_hint', None) is not None:
        self.trg_gate_hint.setText(
            "The trigger is ON where every used axis lies inside [Min, Max] (all conditions together); axes "
            "without 'Use' are ignored, so one axis is enough. Flip: on outside the margins instead. The condition "
            "is evaluated on the plan rows: " + snap[0].lower() + snap[1:] +
            " Tick 'Margins' under the plot to preview it in gray.")
    tip_on = (f"Switch the 5 V trigger on (M42 P{trg.TRIGGER_PORT} S1) at Time (s). " + snap +
              "\nInside a window this changes nothing; at a window's end it extends that window.\nBefore a later "
              "window it stays on until that window starts (dotted mark): press Trigger Off to end it earlier.")
    tip_off = (f"Switch the 5 V trigger off (M42 P{trg.TRIGGER_PORT} S0) at Time (s). " + snap +
               "\nOutside a window this changes nothing. Inside one the trigger is off from there up to the next "
               "window start,\nso the windows you set later in time keep their start and end.")
    if getattr(self, 'button_trigger_on', None) is not None:
        self.button_trigger_on.setToolTip(tip_on)
        self.button_trigger_off.setToolTip(tip_off)
        self.button_clear_trigger.setToolTip(f"Remove every trigger switch (M42 P{trg.TRIGGER_PORT}) from the plan; "
                                             f"waits are kept.")


# ----------------------------------------------------------------------------
# Plot overlay
# ----------------------------------------------------------------------------
def _span_collection(ax, windows, gid, label, facecolor, alpha, zorder, hatch=None, edgecolor="none"):
    from matplotlib.collections import PolyCollection
    verts = [[(a, 0.0), (a, 1.0), (b, 1.0), (b, 0.0)] for a, b in windows]
    coll = PolyCollection(verts, transform=ax.get_xaxis_transform(), facecolors=facecolor, alpha=alpha,
                          edgecolors=edgecolor, linewidths=0.0, zorder=zorder, label=label)
    if hatch:
        coll.set_hatch(hatch)
    coll.set_gid(gid)
    ax.add_collection(coll, autolim=False)
    return coll


def trg_draw_wait_lines(self, ax, dataframe):
    """Vertical dashed lines of the pauses (called from update_plot, replaces its per-row loop): red for wait
    radiation, yellow for wait user, a row holding both gets both.  Taken from the full plan (self._trg_df_full while
    trigger_plot_update runs), not the downsampled plot frame, so no wait goes missing on a long plan.  Up to
    WAIT_LINES_MAX_ARTISTS lines per kind are axvlines as before; above that one LineCollection per kind (same look,
    a fraction of the drawing time when the Periodic tab placed thousands of pauses)."""
    full = getattr(self, '_trg_df_full', None)
    df = dataframe if full is None or 'Command' not in getattr(full, 'columns', ()) else full
    if df is None or 'Command' not in df.columns or 'time' not in df.columns:
        return
    times = {kind: [] for kind in WAIT_LINE_STYLES}
    for cmd, t_val in zip(df['Command'].values, df['time'].values):
        if isinstance(cmd, str) and cmd.strip():
            if 'sensor_wait.g' in cmd:
                times['rad'].append(float(t_val))
            if 'M226' in cmd:
                times['usr'].append(float(t_val))
    for kind, ts in times.items():
        color = WAIT_LINE_STYLES[kind]
        if len(ts) <= WAIT_LINES_MAX_ARTISTS:
            for t_val in ts:
                ax.axvline(x=t_val, color=color, linestyle='--', linewidth=1.5, alpha=0.85)
        else:
            from matplotlib.collections import LineCollection
            lc = LineCollection([[(x, 0.0), (x, 1.0)] for x in ts], transform=ax.get_xaxis_transform(), colors=color,
                                linestyles='--', linewidths=1.5, alpha=0.85)
            lc.set_gid(f"wait_lines_{kind}")
            ax.add_collection(lc, autolim=False)


def _plotted_color(ax, axis):
    for ln in ax.get_lines():
        lb = str(ln.get_label())
        if lb == axis or lb.startswith(axis + " ("):
            return ln.get_color()
    return None


def _active_preview(self):
    tw = getattr(self, 'create_settings_tab_widget', None)
    if tw is not None and tw.currentWidget() is getattr(self, 'trg_periodic_tab', None):
        return "periodic"
    return "margins"


def trg_draw_overlay(self, ax, dataframe, axis_colors=None):
    """Called from update_plot before the legend.  Green cover of the applied windows (full plan) and, with
    'Margins' on, the margin lines and the gray preview.  self.trg_overlay describes what was drawn."""
    if axis_colors:
        self.trg_axis_colors = dict(axis_colors)
    info = {'windows': [], 'inner_starts': [], 'preview': [], 'preview_kind': None, 'events': [], 'margin_lines': [],
            'artists': [], 'error': None}
    self.trg_overlay = info
    full = getattr(self, '_trg_df_full', None)
    df = full if full is not None else dataframe
    if df is None or 'time' not in getattr(df, 'columns', ()) or len(df) < 2:
        return info
    t = df['time'].to_numpy(dtype=float)
    _trg_update_hints(self, trg.row_spacing(t))
    if 'Command' in df.columns:
        cmds = df['Command'].tolist()
        wins = trg.trg_windows(t, cmds)
        info['windows'] = wins
        if wins:
            info['artists'].append(_span_collection(ax, wins, "trg_windows", trg.TRIGGER_LABEL, trg.TRIGGER_COLOR,
                                                    trg.TRIGGER_ALPHA, 0.8))
        _draw_inner_starts(ax, trg.trg_inner_starts(t, cmds), info)
    if not getattr(self, 'trg_show_margins', False):
        return info
    if _active_preview(self) == "periodic" and hasattr(self, 'trg_per_action'):
        _draw_periodic_preview(self, ax, t, info)
    elif getattr(self, 'trg_gate_rows', None):
        _draw_gate_preview(self, ax, df, t, info)
    return info


def _draw_inner_starts(ax, starts, info):
    """Dotted dark-green line at every window start inside a green run (an On before a later window runs into it, or
    an On while the trigger is already on): the user still sees where that window starts, the S1 the G-code repeats
    there."""
    info['inner_starts'] = list(starts)
    if not starts:
        return
    from matplotlib.collections import LineCollection
    lc = LineCollection([[(x, 0.0), (x, 1.0)] for x in starts], transform=ax.get_xaxis_transform(),
                        colors=INNER_START_COLOR, linestyles=":", linewidths=1.6, alpha=0.95, zorder=0.85,
                        label="Later window start (trigger already on)")
    lc.set_gid("trg_inner_starts")
    ax.add_collection(lc, autolim=False)
    info['artists'].append(lc)


def _draw_periodic_preview(self, ax, t, info):
    action, period, duration, offset, rng, _combine = _periodic_params(self)
    info['preview_kind'] = "periodic"
    try:
        pv = trg.trg_periodic_preview(t, period, duration, offset, rng, action)
    except ValueError as e:
        info['error'] = str(e)
        return
    if 'windows' in pv:
        info['preview'] = pv['windows']
        if pv['windows']:
            lbl = "Trigger-off preview (periodic)" if action == "beam_off" else "Trigger preview (periodic)"
            info['artists'].append(_span_collection(ax, pv['windows'], "trg_preview", lbl, PREVIEW_COLOR,
                                                    PREVIEW_ALPHA, 0.9, PREVIEW_HATCH, "#616161"))
    else:
        from matplotlib.collections import LineCollection
        ev = pv['events']
        info['events'] = ev
        if ev:
            segs = [[(x, 0.0), (x, 1.0)] for x in ev]
            lc = LineCollection(segs, transform=ax.get_xaxis_transform(), colors=PREVIEW_COLOR, linestyles=":",
                                linewidths=1.4, zorder=1.9, label=f"{trg.PERIODIC_LABELS[action]} preview (periodic)")
            lc.set_gid("trg_preview_events")
            ax.add_collection(lc, autolim=False)
            info['artists'].append(lc)


def _position_lines(ax, axis):
    """The plotted position curve(s) of an axis (label 'LAT' or 'LAT (Pos)')."""
    return [ln for ln in ax.get_lines() if str(ln.get_label()) in (axis, f"{axis} (Pos)")]


def _draw_margin_lines(self, ax, limits, info):
    """Dashed horizontal lines at Min / Max of every used axis, in the axis' plot colour.  The axis' own position
    curve is brought to the front (on the platform the actuator curves A..'f have identical values in other colours
    and would hide it).  The lines are added without touching the data limits, so a wide margin (e.g. Max 200 mm to
    say 'LAT >= 10') does not rescale the plot."""
    from matplotlib.lines import Line2D
    lines = []                     # (y, axis, colour)
    for axis, (lo, hi) in limits.items():
        color = _plotted_color(ax, axis) or _axis_color(self, axis)
        for ln in _position_lines(ax, axis):
            ln.set_zorder(CURVE_FRONT_ZORDER)
        for y in sorted({float(lo), float(hi)}):
            lines.append((y, axis, color))
    groups = {}
    for y, axis, color in lines:   # lines at the same height (e.g. same margins): interleave their dashes
        groups.setdefault(round(y, 9), []).append((axis, color))
    for yk, members in groups.items():
        m = len(members)
        for k, (axis, color) in enumerate(members):
            # one dash of each colour in turn, with a gap after each (still reads as dashed)
            ls = (0, (6, 4)) if m == 1 else (k * 9, (6, 9 * m - 6))
            ln = Line2D([0.0, 1.0], [yk, yk], transform=ax.get_yaxis_transform(), color=color, linestyle=ls,
                        linewidth=MARGIN_LINEWIDTH, alpha=0.95, zorder=1.8, label="_trg_margin")
            ln.set_gid(f"trg_margin_{axis}")
            ax.add_artist(ln)      # not ax.add_line / axhline: those extend the data limits (autoscale)
            info['margin_lines'].append((axis, float(yk), color))
            info['artists'].append(ln)


def _draw_gate_preview(self, ax, df, t, info):
    trg_refresh_gate_rows(self)
    limits, flip, rng, _combine = _gate_params(self)
    info['preview_kind'] = "margins"
    if not limits:
        info['error'] = "no axis used"
        return
    pos_cb = getattr(self, 'check_show_pos', None)
    if pos_cb is None or pos_cb.isChecked():
        _draw_margin_lines(self, ax, limits, info)
    else:                          # margins are positions: no lines on a Velocity / Acceleration-only axis
        info['margin_lines_hidden'] = "Position not shown"
    try:
        values = {a: np.asarray(df[a], dtype=float) for a in limits}
        pv = trg.trg_gate_preview(t, values, limits, flip, rng)
    except (ValueError, KeyError) as e:
        info['error'] = str(e)
        return
    info['preview'] = pv
    if pv:
        info['artists'].append(_span_collection(ax, pv, "trg_preview", "Trigger preview (margins)", PREVIEW_COLOR,
                                                PREVIEW_ALPHA, 0.9, PREVIEW_HATCH, "#616161"))
