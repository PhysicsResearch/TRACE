"""
Right-click edits in the Planning plot (pauses and trigger windows); a new module, hooked by tab_planning_modern.

* Right-click near a dashed pause line (Wait Radiation red / Wait User yellow, drawn by trg_draw_wait_lines; the
  nearest line within PICK_PX screen pixels) or inside / on the edge of a green trigger window (trg_draw_overlay)
  opens one menu with a section per thing under the cursor:
    - pause:   'Wait Radiation at 12,50 s' (header), Delete pause, Adjust time..., Change to Wait User / Radiation
    - window:  'Trigger window 3,00-4,00 s' (header, the run as trg_windows reports it), Delete window,
               Adjust window..., Remove window start mark at x s (one per dotted inner start in the run)
* With Pan or Zoom active the right button keeps matplotlib's meaning (no menu); the left button is never used.
* Pause edits touch only that wait command in its cell (' ; ' cells keep their trigger / other commands; cell helpers
  of fcn_plan.fcn_trigger).  Trigger window edits are state based (fcn_trigger.trg_delete_window / trg_set_window /
  trg_remove_inner_start: off at the start, explicit S0 on the last row, waits in the cells kept; the G-code adds the
  safety M42 P5 S0 at start and end as for every plan with a trigger).
* Every edit is one undo step through tab_planning_trigger._trg_commit (push_curve_state, write, re-bake, store,
  loadTable_create, plot refresh) and reports in the trigger status line under the Curve tab buttons.

``ask_time`` / ``ask_window`` (module functions) open the small dialogs; ``exec_menu`` shows the menu.  Tests patch
them.
"""

import numpy as np
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QMenu, QDialog, QVBoxLayout, QGridLayout, QLabel, QDoubleSpinBox, QDialogButtonBox, QInputDialog
)

from fcn_plan import fcn_trigger as trg

PICK_PX = 6                     # hit distance to a pause line / window edge (logical screen pixels)
WAIT_KINDS = {
    'rad': ("Wait Radiation", 'sensor_wait.g', trg.WAIT_RAD_CMD),
    'usr': ("Wait User", 'M226', trg.WAIT_USER_CMD),
}
OTHER_KIND = {'rad': 'usr', 'usr': 'rad'}


# ----------------------------------------------------------------------------------------- Qt-free cell edits
def cell_wait_piece(cell, kind):
    """The exact command text of the ``kind`` wait in a cell (e.g. 'M98 P"0:macros/sensor_wait.g"'), or None."""
    match = WAIT_KINDS[kind][1]
    for p in trg.split_cell(cell):
        if match in p:
            return p
    return None


def pause_rows(commands, kind):
    match = WAIT_KINDS[kind][1]
    return [i for i, c in enumerate(commands) if isinstance(c, str) and match in c]


def pause_delete(commands, row, kind):
    """Commands with the ``kind`` wait removed from that row only (other commands of the cell kept)."""
    new = list(commands)
    piece = cell_wait_piece(new[row], kind)
    if piece is None:
        return new, False
    new[row] = trg.remove_cell_commands(new[row], lambda p: p == piece)
    return new, True


def pause_move(commands, row, new_row, kind):
    """Moves the ``kind`` wait of ``row`` to ``new_row`` (the same command text; canonical order in the new cell).
    Returns (new_commands, status) with status 'moved' / 'same_row' / 'occupied' / 'missing'."""
    new = list(commands)
    piece = cell_wait_piece(new[row], kind)
    if piece is None:
        return new, 'missing'
    if new_row == row:
        return new, 'same_row'
    if cell_wait_piece(new[new_row], kind) is not None:
        return new, 'occupied'
    new[row] = trg.remove_cell_commands(new[row], lambda p: p == piece)
    new[new_row] = trg.add_cell_command(new[new_row], piece)
    return new, 'moved'


def pause_change_kind(commands, row, kind):
    """Replaces the ``kind`` wait of the row by the other kind.  Status 'changed' / 'occupied' / 'missing'."""
    new = list(commands)
    piece = cell_wait_piece(new[row], kind)
    if piece is None:
        return new, 'missing'
    other = OTHER_KIND[kind]
    if cell_wait_piece(new[row], other) is not None:
        return new, 'occupied'
    cell = trg.remove_cell_commands(new[row], lambda p: p == piece)
    new[row] = trg.add_cell_command(cell, WAIT_KINDS[other][2])
    return new, 'changed'


# ----------------------------------------------------------------------------------------- dialogs (patchable)
def _spin(parent, value, lo, hi, decimals, locale=None):
    sp = QDoubleSpinBox(parent)
    if locale is not None:
        sp.setLocale(locale)
    sp.setDecimals(decimals)
    sp.setRange(lo, hi)
    sp.setSingleStep(10 ** -decimals if decimals else 1.0)
    sp.setValue(value)
    sp.setMinimumHeight(36)
    sp.setMinimumWidth(130)
    return sp


def ask_time(parent, title, label, value, lo, hi, decimals, locale=None):
    """(value, ok) from a small dialog with one time box (QDoubleSpinBox: the Time (s) box's decimal handling)."""
    dlg = QDialog(parent)
    dlg.setWindowTitle(title)
    lay = QVBoxLayout(dlg)
    lbl = QLabel(label, dlg)
    lbl.setWordWrap(True)
    lay.addWidget(lbl)
    sp = _spin(dlg, value, lo, hi, decimals, locale)
    lay.addWidget(sp)
    bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, dlg)
    bb.accepted.connect(dlg.accept)
    bb.rejected.connect(dlg.reject)
    lay.addWidget(bb)
    ok = dlg.exec() == QDialog.Accepted
    return sp.value(), ok


def ask_window(parent, title, start, end, lo, hi, decimals, locale=None):
    """((start, end), ok) from a dialog with Start and End boxes; OK only while End > Start."""
    dlg = QDialog(parent)
    dlg.setWindowTitle(title)
    lay = QVBoxLayout(dlg)
    grid = QGridLayout()
    s0 = _spin(dlg, start, lo, hi, decimals, locale)
    s1 = _spin(dlg, end, lo, hi, decimals, locale)
    grid.addWidget(QLabel("Start (s):", dlg), 0, 0)
    grid.addWidget(s0, 0, 1)
    grid.addWidget(QLabel("End (s):", dlg), 1, 0)
    grid.addWidget(s1, 1, 1)
    lay.addLayout(grid)
    note = QLabel("Times snap to the nearest plan row. A window it overlaps or touches joins it.", dlg)
    note.setWordWrap(True)
    note.setStyleSheet("color: #555555; font-size: 12px;")
    lay.addWidget(note)
    bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, dlg)
    bb.accepted.connect(dlg.accept)
    bb.rejected.connect(dlg.reject)
    lay.addWidget(bb)
    okb = bb.button(QDialogButtonBox.Ok)

    def check():
        okb.setEnabled(s1.value() > s0.value())
    s0.valueChanged.connect(lambda _v: check())
    s1.valueChanged.connect(lambda _v: check())
    check()
    ok = dlg.exec() == QDialog.Accepted
    return (s0.value(), s1.value()), ok


def exec_menu(menu, global_pos):
    """Shows the menu; returns the chosen QAction or None."""
    return menu.exec(global_pos)


MENU_STYLE = ("QMenu { font-size: 14px; background-color: #ffffff; color: #212121; border: 1px solid #b0bec5; "
              "padding: 4px 0px; } "
              "QMenu::item { padding: 6px 24px 6px 16px; background-color: transparent; } "
              "QMenu::item:selected { background-color: #e3f2fd; color: #0d47a1; } "
              "QMenu::item:disabled { color: #37474f; } "
              "QMenu::separator { height: 1px; background-color: #cfd8dc; margin: 4px 8px; }")


# ----------------------------------------------------------------------------------------- the editor
class PlotEditor:
    """Right-click menu on the Planning canvas of one window (self.planning_modern.plot_editor)."""

    def __init__(self, win):
        self.win = win
        self.canvas = None
        self.cid = None
        self.last_menu = None           # (QMenu, [section dicts]) of the last menu shown (tests / screenshots)

    def connect(self, canvas):
        if canvas is None or canvas is self.canvas:
            return
        self.canvas = canvas
        self.cid = canvas.mpl_connect('button_press_event', self.on_press)

    # ---------------------------------------------------------------- helpers
    def _locale(self):
        box = getattr(self.win, 'input_wait_rad_time', None)
        return box.locale() if box is not None else None

    def _decimals(self):
        box = getattr(self.win, 'input_wait_rad_time', None)
        return box.decimals() if box is not None else 2

    def fmt(self, x):
        loc = self._locale()
        if loc is None:
            return f"{float(x):.2f}"
        return loc.toString(float(x), 'f', max(2, self._decimals()))

    def _nav_mode(self):
        tb = getattr(self.win, 'create_plot_toolbar', None)
        try:
            return str(getattr(tb.mode, 'value', tb.mode) or '')
        except Exception:
            return ''

    def _plan(self):
        df = getattr(self.win, 'dfEdit', None)
        if df is None or 'time' not in df.columns or 'Command' not in df.columns or len(df) < 2:
            return None
        return df

    def _px_tol(self):
        try:
            dpr = float(self.canvas.device_pixel_ratio)
        except Exception:
            dpr = 1.0
        return PICK_PX * dpr

    # ---------------------------------------------------------------- hit test
    def hits_at(self, x_px, xdata):
        """Sections for the menu at display x (pixels, as matplotlib events give them) / data time xdata."""
        df = self._plan()
        ax = getattr(self.win, 'create_plot_ax', None)
        if df is None or ax is None or xdata is None:
            return []
        t = df['time'].to_numpy(dtype=float)
        cmds = df['Command'].tolist()
        tol = self._px_tol()
        sections = []
        for kind in ('rad', 'usr'):
            rows = pause_rows(cmds, kind)
            if not rows:
                continue
            xs = ax.transData.transform(np.column_stack([t[rows], np.zeros(len(rows))]))[:, 0]
            d = np.abs(xs - float(x_px))
            k = int(np.argmin(d))
            if d[k] <= tol:
                sections.append({'type': 'pause', 'kind': kind, 'row': rows[k], 'time': float(t[rows[k]])})
        # trigger window: inside, or within tol pixels of an edge
        try:
            x0 = ax.transData.transform([[float(xdata), 0.0]])[0, 0]
            x1 = ax.transData.transform([[float(xdata) + 1.0, 0.0]])[0, 0]
            px_per_s = abs(x1 - x0) or 1.0
        except Exception:
            px_per_s = 1.0
        run = trg.trg_run_at(t, cmds, float(xdata), tol=tol / px_per_s)
        if run is not None:
            a, b = run
            inner = [x for x in trg.trg_inner_starts(t, cmds) if t[a] < x < t[b]]
            sections.append({'type': 'window', 'rows': (a, b), 'window': (float(t[a]), float(t[b])),
                             'inner': inner})
        return sections

    # ---------------------------------------------------------------- menu
    def _header(self, menu, text):
        act = menu.addAction(text)
        act.setEnabled(False)
        f = QFont(act.font())
        f.setBold(True)
        act.setFont(f)
        return act

    def build_menu(self, sections):
        menu = QMenu(self.canvas)
        # explicit colours: the menu is a child of the plot canvas, whose style sheet makes backgrounds transparent
        # (a popup with a transparent background is drawn black on Windows)
        menu.setStyleSheet(MENU_STYLE)
        handlers = {}
        for k, s in enumerate(sections):
            if k:
                menu.addSeparator()
            if s['type'] == 'pause':
                name = WAIT_KINDS[s['kind']][0]
                self._header(menu, f"{name} at {self.fmt(s['time'])} s")
                handlers[menu.addAction("Delete pause")] = lambda s=s: self.delete_pause(s)
                handlers[menu.addAction("Adjust time…")] = lambda s=s: self.adjust_pause(s)
                other = WAIT_KINDS[OTHER_KIND[s['kind']]][0]
                handlers[menu.addAction(f"Change to {other}")] = lambda s=s: self.change_pause(s)
            else:
                a, b = s['window']
                self._header(menu, f"Trigger window {self.fmt(a)}–{self.fmt(b)} s")
                handlers[menu.addAction("Delete window")] = lambda s=s: self.delete_window(s)
                handlers[menu.addAction("Adjust window…")] = lambda s=s: self.adjust_window(s)
                for x in s['inner']:
                    handlers[menu.addAction(f"Remove window start mark at {self.fmt(x)} s")] = \
                        lambda s=s, x=x: self.remove_inner_start(s, x)
        return menu, handlers

    def _global_pos(self, event):
        ge = getattr(event, 'guiEvent', None)
        try:
            if ge is not None:
                return ge.globalPosition().toPoint()
        except Exception:
            pass
        try:
            dpr = float(self.canvas.device_pixel_ratio) or 1.0
        except Exception:
            dpr = 1.0
        return self.canvas.mapToGlobal(QPoint(int(event.x / dpr), int(self.canvas.height() - event.y / dpr)))

    def on_press(self, event):
        try:
            if getattr(event, 'button', None) != 3 or getattr(event, 'dblclick', False):
                return
            if self._nav_mode():
                return                          # Pan / Zoom: right button keeps matplotlib's meaning
            ax = getattr(self.win, 'create_plot_ax', None)
            if ax is None or event.inaxes is not ax:
                return
            sections = self.hits_at(event.x, event.xdata)
            if not sections:
                return
            menu, handlers = self.build_menu(sections)
            self.last_menu = (menu, sections)
            chosen = exec_menu_ref()(menu, self._global_pos(event))
            fn = handlers.get(chosen)
            if fn is not None:
                fn()
        except RuntimeError:
            pass                                # window closed

    # ---------------------------------------------------------------- edits
    def _status(self, text, kind="ok"):
        from fcn_create_gui.tab_planning_trigger import _trg_status
        _trg_status(self.win, text, kind)

    def _commit(self, new, message, kind="ok"):
        from fcn_create_gui.tab_planning_trigger import _trg_commit
        _trg_commit(self.win, new, message, kind=kind)

    def _cmds(self):
        df = self._plan()
        return (None, None) if df is None else (df['time'].to_numpy(dtype=float), df['Command'].tolist())

    def delete_pause(self, s):
        t, cmds = self._cmds()
        if t is None:
            return
        new, ok = pause_delete(cmds, s['row'], s['kind'])
        name = WAIT_KINDS[s['kind']][0]
        if not ok:
            self._status(f"No {name} at {self.fmt(s['time'])} s: nothing changed.", "warn")
            return
        self._commit(new, f"{name} at {self.fmt(s['time'])} s deleted.")

    def adjust_pause(self, s):
        t, cmds = self._cmds()
        if t is None:
            return
        name = WAIT_KINDS[s['kind']][0]
        val, ok = ask_time_ref()(self.win, f"Adjust {name}",
                                 f"New time of the {name} pause (s); it moves to the nearest plan row.",
                                 s['time'], float(t[0]), float(t[-1]), self._decimals(), self._locale())
        if not ok:
            return
        new_row = trg.nearest_row(t, float(val))
        new, status = pause_move(cmds, s['row'], new_row, s['kind'])
        tn = float(t[new_row])
        if status == 'same_row':
            self._status(f"{name} stays at {self.fmt(tn)} s (nearest plan row): nothing changed.", "warn")
        elif status == 'occupied':
            self._status(f"The row at {self.fmt(tn)} s already has a {name}: nothing changed.", "warn")
        elif status == 'missing':
            self._status(f"No {name} at {self.fmt(s['time'])} s: nothing changed.", "warn")
        else:
            self._commit(new, f"{name} moved from {self.fmt(s['time'])} s to {self.fmt(tn)} s.")

    def change_pause(self, s):
        t, cmds = self._cmds()
        if t is None:
            return
        name, other = WAIT_KINDS[s['kind']][0], WAIT_KINDS[OTHER_KIND[s['kind']]][0]
        new, status = pause_change_kind(cmds, s['row'], s['kind'])
        if status == 'occupied':
            self._status(f"The row at {self.fmt(s['time'])} s already has a {other}: nothing changed.", "warn")
        elif status == 'missing':
            self._status(f"No {name} at {self.fmt(s['time'])} s: nothing changed.", "warn")
        else:
            self._commit(new, f"{name} at {self.fmt(s['time'])} s changed to {other}.")

    # status texts in the decimal sign of the Time box (as the menu headers and the pause edits)
    def fmt_span(self, a, b):
        return f"{self.fmt(a)}–{self.fmt(b)} s"

    def describe(self, windows):
        if not windows:
            return "no trigger window"
        n = len(windows)
        return f"{n} window{'s' if n != 1 else ''}, {self.fmt(trg.trg_on_time(windows))} s on in total"

    def delete_window(self, s):
        t, cmds = self._cmds()
        if t is None:
            return
        try:
            new, info = trg.trg_delete_window(t, cmds, *s['rows'])
        except ValueError as e:
            self._status(f"Delete window: {e}.", "error")
            return
        self._commit(new, f"Trigger window {self.fmt_span(*info['removed'])} deleted "
                          f"({self.describe(info['windows'])}).")

    def _window_error(self, t, start, end):
        """The reason trg_set_window would refuse start..end (in the Time box's decimal sign), or None."""
        eps = 1e-9
        if start < t[0] - eps or end > t[-1] + eps:
            return f"the window must lie inside the plan ({self.fmt_span(t[0], t[-1])})"
        if not end > start:
            return "the end must be after the start"
        if trg.nearest_row(t, end) <= trg.nearest_row(t, start):
            return (f"{self.fmt_span(start, end)} is shorter than one plan row "
                    f"({self.fmt(trg.row_spacing(t))} s)")
        return None

    def adjust_window(self, s):
        t, cmds = self._cmds()
        if t is None:
            return
        a, b = s['window']
        (start, end), ok = ask_window_ref()(self.win, "Adjust trigger window", a, b, float(t[0]), float(t[-1]),
                                            self._decimals(), self._locale())
        if not ok:
            return
        start, end = float(start), float(end)
        err = self._window_error(t, start, end)
        if err is not None:
            self._status(f"Adjust window: {err}; nothing changed.", "error")
            return
        try:
            new, info = trg.trg_set_window(t, cmds, s['rows'][0], s['rows'][1], start, end)
        except ValueError as e:
            self._status(f"Adjust window: {e}; nothing changed.", "error")
            return
        msg = f"Trigger window {self.fmt_span(a, b)} moved to {self.fmt_span(*info['window'])}"
        if info['joined']:
            msg += " and joined with " + ", ".join(self.fmt_span(p, q) for p, q in info['joined'])
            if info.get('run'):
                msg += f": one window {self.fmt_span(*info['run'])}"
        msg += f" ({self.describe(info['windows'])})."
        self._commit(new, msg, kind="warn" if info['joined'] else "ok")

    def remove_inner_start(self, s, x):
        t, cmds = self._cmds()
        if t is None:
            return
        new, info = trg.trg_remove_inner_start(t, cmds, x)
        tx = self.fmt(float(t[trg.nearest_row(t, x)]))
        if not info['changed']:
            self._status(f"No window start mark at {tx} s: nothing changed.", "warn")
            return
        self._commit(new, f"Window start mark at {tx} s removed; the run is unchanged.")


# Late-bound references (tests patch the module functions ask_time / ask_window / exec_menu)
def exec_menu_ref():
    import sys
    return sys.modules[__name__].exec_menu


def ask_time_ref():
    import sys
    return sys.modules[__name__].ask_time


def ask_window_ref():
    import sys
    return sys.modules[__name__].ask_window
