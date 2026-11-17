"""
Planning > Curve: a lower Curve Options box, and the Pauses & trigger card on the Trigger tab.

    from fcn_create_gui.planning_curve_layout import apply_planning_curve_layout
    apply_planning_curve_layout(window)     # once, after build_planning_tab + modernise_planning_tab

* Each title in front of its box instead of above it (rows closer together), with short titles and a tooltip that
  explains the box: Function, Amp. (mm), Offset (mm), Period (s), Phase (deg), Start (s), End (s), Total (s).
* Rows: DYNAMIQ | KINETIQ (no 'Device' title, as wide as its names) then Function | Amp. | Offset | Period |
  Phase | Start | slider | End | Total from the left (DYNAMIQ: after the Axis buttons X Y Z) | KINETIQ only:
  Rot. centre with the Axis buttons.  The Axis buttons move with the device.
* Plot curves: the individual axes A B C D 'a 'c 'e 'f start unchecked (the user's later choice is kept).  The titles the legacy code switches for 'linear' (Initial pos / Final pos / Duration) and for
  Roll / Pitch / Yaw (deg) are shortened the same way.
* Number boxes as wide as their numbers (they stretched over the whole column).
* Start | slider | End | Total on one line; the slider caption becomes its tooltip.
* 'Rot. centre (mm)' / 'ref. point for Roll / Pitch / Yaw' with the Axis pills on its right.
* The Pauses & trigger card moves to the Trigger tab, renamed 'Pause and Trigger', left of the Position-Gated
  Trigger panel.  Its Repeat preview follows it (shown while that tab is open; in Repeat mode it is shown there
  instead of the margins preview).
* The sub-tabs (Curve, Pause and Trigger, Tools, Settings, Table) as a column of icon buttons (title as tooltip) on
  the right of the pages instead of a tab bar on top (the QTabWidget, its indexes and currentChanged stay the same).
Layout only: the same widgets, signals and handlers.
"""
from PySide6.QtCore import QByteArray, QSize, Qt, QTimer
from PySide6.QtGui import QFontMetrics, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (QAbstractSpinBox, QBoxLayout, QButtonGroup, QFrame, QGridLayout, QGroupBox,
                               QHBoxLayout, QLabel, QLineEdit, QScrollArea, QSizePolicy, QSplitter, QToolButton,
                               QVBoxLayout, QWidget)

ROW_SPACING = 8                 # px between the Curve Options rows (some separation kept)
TITLE_GAP = 8                   # px between a title and its box
SPIN_SAMPLE = "-0000.00"        # widest number a box shows in full
ROT_FIELD_SAMPLE = "-000.0"
TRIGGER_TAB = "Pause and Trigger"
ROT_TITLE = "Rot. centre (mm)"
ROT_SUBTITLE = "ref. point for Roll / Pitch / Yaw"
SLIDER_TIP = "Start and End of the curve: drag a handle, or drag the blue range to move both."
SUBNAV_BUTTON_HEIGHT = 44       # Planning sub-tab buttons (column on the right)

# legacy title -> (short title, tooltip of the title and its box)
AMP_TIP = ("Amplitude: sin and cos swing ± Amp. around Offset; cos², cos⁴ and cos⁶ go from Offset to "
           "Offset + Amp.; constant: Amp. + Offset.")
TITLES = {
    "Device Type:": ("Device", "Device the curve is planned for: DYNAMIQ (X, Y, Z) or KINETIQ (LAT, SI, AP, Roll, "
                               "Pitch, Yaw)."),
    "Function Type:": ("Function", "Shape of the curve: sin, cos, cos², cos⁴, cos⁶, constant or linear."),
    "Amplitude (mm):": ("Amp. (mm)", AMP_TIP + " In mm."),
    "Amplitude (deg):": ("Amp. (deg)", AMP_TIP + " In degrees (Roll / Pitch / Yaw)."),
    "Amp. offset (mm):": ("Offset (mm)", "Offset: added to the whole curve (the middle of sin / cos, the bottom of "
                                         "cos², cos⁴, cos⁶). In mm."),
    "Period (s):": ("Period (s)", "Period: time of one full cycle, in seconds."),
    "Initial pos (mm):": ("Initial (mm)", "Linear: position at Start, in mm."),
    "Initial pos (deg):": ("Initial (deg)", "Linear: angle at Start, in degrees."),
    "Final pos (mm):": ("Final (mm)", "Linear: position at the end of the line, in mm."),
    "Final pos (deg):": ("Final (deg)", "Linear: angle at the end of the line, in degrees."),
    "Duration (s):": ("Duration (s)", "Linear: time from Initial to Final, in seconds (End = Start + Duration)."),
    "Starting Phase (deg):": ("Phase (deg)", "Phase: where in the cycle the curve starts, in degrees (0: sin starts "
                                             "at Offset, cos at its top)."),
    "Start Time (s):": ("Start (s)", None),            # the boxes keep their own tooltips (curve controls)
    "End Time (s):": ("End (s)", None),
    "Total duration (s):": ("Total (s)", None),
}
# the titles one column can show (its width is fixed on the widest, so the boxes stay aligned); row 1 is
# Amp. | Offset | Period | Phase, and Start (s) starts the line below it (KINETIQ: under Amp.)
COLUMN_TITLES = [
    ["Amp. (mm)", "Amp. (deg)", "Initial (mm)", "Initial (deg)", "Start (s)"],
    ["Offset (mm)", "Final (mm)", "Final (deg)"],
    ["Period (s)", "Duration (s)"],
    ["Phase (deg)"],
]
DEVICE_NAMES = ("DYNAMIQ", "KINETIQ")
PLATFORM = "Motion Platform"    # legacy device name of KINETIQ (combo_device)

# Planning sub-tab icons (24 x 24 view box, 2 px round strokes), by the start of the tab title
SUBTAB_ICONS = {
    "curve": '<path d="M2 12c2.5-7 5.5-7 8 0s5.5 7 8 0c1-2.8 2-4 4-4"/>',
    "pause": '<line x1="5" y1="5" x2="5" y2="19"/><line x1="10" y1="5" x2="10" y2="19"/>'
             '<path d="M18 3l-3.5 9h5l-3.5 9"/>',
    "tools": '<path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 '
             '6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/>',
    "settings": '<line x1="4" y1="21" x2="4" y2="14"/><line x1="4" y1="10" x2="4" y2="3"/><line x1="12" y1="21" '
                'x2="12" y2="12"/><line x1="12" y1="8" x2="12" y2="3"/><line x1="20" y1="21" x2="20" y2="16"/>'
                '<line x1="20" y1="12" x2="20" y2="3"/><line x1="1" y1="14" x2="7" y2="14"/><line x1="9" y1="8" '
                'x2="15" y2="8"/><line x1="17" y1="16" x2="23" y2="16"/>',
    "table": '<rect x="3" y="4" width="18" height="16" rx="2"/><line x1="3" y1="10" x2="21" y2="10"/>'
             '<line x1="3" y1="15" x2="21" y2="15"/><line x1="9" y1="10" x2="9" y2="20"/>',
}
SUBTAB_ICON_PX = 26
TOOLTIP_TEXTS = [("(Curve tab, Pauses & trigger)", f"({TRIGGER_TAB} tab)"),
                 ("the 'Trigger' tab", f"the '{TRIGGER_TAB}' tab")]


def _number_width(widget, sample, extra):
    widget.ensurePolished()
    return QFontMetrics(widget.font()).horizontalAdvance(sample) + extra


def _short_title(label, boxes=()):
    """label.setText maps the legacy titles to short ones (+ tooltip), also when the legacy code switches them."""
    if getattr(label, "_pcl_short", False):
        return

    def set_text(text, *_):
        raw = str(text).strip()
        short, tip = TITLES.get(raw, (raw.rstrip(":"), None))
        QLabel.setText(label, short)
        if tip:
            label.setToolTip(tip)
            for b in boxes:
                b.setToolTip(tip)

    label.setText = set_text
    label._pcl_short = True
    set_text(label.text())
    label.setSizePolicy(QSizePolicy.Fixed, label.sizePolicy().verticalPolicy())


def _svg_icon(body, color, disabled="#b5c0a9", sizes=(24, 48, 64)):
    """Line icon from an SVG body (24 x 24 view box), as the left column of the window draws its icons."""
    try:
        from PySide6.QtSvg import QSvgRenderer
    except Exception:                                             # pragma: no cover
        QSvgRenderer = None
    icon = QIcon()
    for px in sizes:
        for col, mode in ((color, QIcon.Normal), (color, QIcon.Active), (disabled, QIcon.Disabled)):
            svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{col}" '
                   f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">{body}</svg>')
            pm = QPixmap(px, px)
            pm.fill(Qt.transparent)
            if QSvgRenderer is not None:
                p = QPainter(pm)
                p.setRenderHint(QPainter.Antialiasing, True)
                QSvgRenderer(QByteArray(svg.encode("utf-8"))).render(p)
                p.end()
            icon.addPixmap(pm, mode, QIcon.Off)
    return icon


def _contains(layout, widget):
    if layout is None:
        return False
    if layout.indexOf(widget) >= 0:
        return True
    for i in range(layout.count()):
        it = layout.itemAt(i)
        if _contains(it.layout(), widget) or (it.widget() is not None and _contains(it.widget().layout(), widget)):
            return True
    return False


def _grid_holding(layout, widget):
    """The QGridLayout (anywhere under layout) one of whose cells holds widget."""
    if layout is None:
        return None
    if isinstance(layout, QGridLayout) and _contains(layout, widget):
        return layout
    for i in range(layout.count()):
        it = layout.itemAt(i)
        for sub in (it.layout(), it.widget().layout() if it.widget() is not None else None):
            found = _grid_holding(sub, widget)
            if found is not None:
                return found
    return None


def _keep_visibility(widgets):
    return [(w, w.isHidden()) for w in widgets]


def _restore_visibility(states):
    for w, hidden in states:
        w.setVisible(not hidden)


class PlanningCurveLayout:
    def __init__(self, window):
        self.window = w = window
        self.pm = w.planning_modern
        self.cc = getattr(self.pm, "curve_controls", None)
        self.gb = w.groupBox_BrCv_createCurve
        self.grid = _grid_holding(self.gb.layout(), w.input_amplitude)     # moved into the left column by now
        if self.grid is None:
            raise RuntimeError("Curve Options grid not found")
        self.spin_w = _number_width(w.input_amplitude, SPIN_SAMPLE, 44)

    # ------------------------------------------------------------------ 1. titles in front
    def titles_in_front(self):
        grid = self.grid
        for i in range(grid.count()):
            cell = grid.itemAt(i).layout()
            r, c, rs, cs = grid.getItemPosition(i)
            if not isinstance(cell, QBoxLayout) or cell.direction() != QBoxLayout.TopToBottom:
                continue
            title, boxes = None, []
            for k in range(cell.count()):
                wd = cell.itemAt(k).widget()
                if isinstance(wd, QLabel) and title is None:
                    title = wd
                elif wd is not None:
                    boxes.append(wd)
            if title is None:
                continue
            cell.setDirection(QBoxLayout.LeftToRight)
            cell.setSpacing(TITLE_GAP)
            cell.setAlignment(title, Qt.AlignVCenter)
            _short_title(title, boxes)
            self._column_width(title, c)
            spins = [b for b in boxes if isinstance(b, QAbstractSpinBox)]
            for sp in spins:
                self._number_box(sp)
            if spins:
                cell.addStretch(1)                         # boxes packed on the left of their column
        grid.setVerticalSpacing(ROW_SPACING)

    def _column_width(self, label, col):
        texts = (COLUMN_TITLES[col] if col < len(COLUMN_TITLES) else []) + [label.text()]
        label.ensurePolished()
        fm = QFontMetrics(label.font())
        label.setMinimumWidth(max(fm.horizontalAdvance(t) for t in texts) + 4)

    def _number_box(self, sp):
        sp.setMinimumWidth(0)
        sp.setSizePolicy(QSizePolicy.Fixed, sp.sizePolicy().verticalPolicy())
        sp.setFixedWidth(self.spin_w)

    # ------------------------------------------------------------------ 2. Start | slider | End | Total
    def time_row(self):
        cc = self.cc
        box = getattr(cc, "time_box", None)
        tg = box.layout() if box is not None else None
        if tg is None:
            return
        w = self.window
        start, end = w.input_start_time, w.input_end_time
        sep = next((f for f in box.findChildren(QFrame, options=Qt.FindDirectChildrenOnly)
                    if f.frameShape() == QFrame.VLine), None)
        order = [cc.start_label, start, cc.slider, cc.end_label, end, sep, cc.total_label, cc.total_spin]
        states = _keep_visibility([x for x in order + [cc.caption] if x is not None])
        for x in order + [cc.caption]:
            if x is not None:
                tg.removeWidget(x)
        for c in range(tg.columnCount()):
            tg.setColumnStretch(c, 0)
        col = 0
        for x in order:
            if x is None:
                continue
            if isinstance(x, QLabel):
                tg.addWidget(x, 0, col, Qt.AlignVCenter)
            else:
                tg.addWidget(x, 0, col)
            col += 1
        tg.setColumnStretch(2, 1)                          # the slider takes the free width
        tg.setHorizontalSpacing(TITLE_GAP)
        _restore_visibility(states)
        cc.caption.hide()
        tip = cc.slider.toolTip()
        cc.slider.setToolTip(f"{tip}\n{SLIDER_TIP}" if tip else SLIDER_TIP)
        for lab, boxes in ((cc.start_label, [start]), (cc.end_label, [end]), (cc.total_label, [cc.total_spin])):
            _short_title(lab, ())
            lab.setMinimumWidth(0)
        self._column_width(cc.start_label, 1)
        for sp in (start, end, cc.total_spin):
            self._number_box(sp)

    # ------------------------------------------------------------------ 3. Rot. centre + Axis on one row
    def rotation_and_axis(self):
        w, grid = self.window, self.grid
        off = getattr(w, "offset_rot_widget", None)
        axis = getattr(w, "axis_selection_widget", None)
        if off is None or axis is None or grid.indexOf(off) < 0 or grid.indexOf(axis) < 0:
            return
        r, c, rs, cs = grid.getItemPosition(grid.indexOf(off))
        states = _keep_visibility([off, axis])
        grid.removeWidget(off)
        grid.removeWidget(axis)
        row = QWidget(self.gb)
        row.setObjectName("pmRotAxisRow")
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(16)
        h.addWidget(off, 0, Qt.AlignVCenter)
        h.addWidget(axis, 1, Qt.AlignVCenter)
        grid.addWidget(row, r, 0, 1, 3)
        _restore_visibility(states)
        self.rot_axis_row = row
        # shorter card: short title, number boxes as wide as their numbers
        pm = self.pm
        if getattr(pm, "rot_title", None) is not None:
            pm.rot_title.setText(ROT_TITLE)
            pm.rot_subtitle.setText(ROT_SUBTITLE)
        card = getattr(pm, "rot_card", None)
        if card is not None and card.layout() is not None:
            cl = card.layout()
            for le in card.findChildren(QLineEdit):
                le.setSizePolicy(QSizePolicy.Fixed, le.sizePolicy().verticalPolicy())
                le.setFixedWidth(_number_width(le, ROT_FIELD_SAMPLE, 26))
                i = cl.indexOf(le)
                if i >= 0:
                    cl.setStretch(i, 0)
            card.setSizePolicy(QSizePolicy.Fixed, card.sizePolicy().verticalPolicy())

    # ------------------------------------------------------------------ 3b. rows: device toggle, Phase, Axis
    def _cell(self, widget):
        """(index, layout) of the grid item whose cell layout holds widget."""
        for i in range(self.grid.count()):
            lay = self.grid.itemAt(i).layout()
            if lay is not None and lay.indexOf(widget) >= 0:
                return i, lay
        return -1, None

    def rows_by_device(self):
        """Row 0: DYNAMIQ | KINETIQ (no 'Device' title, as wide as its names) then Function, which gets the rest.
        Row 1: Amp. | Offset | Period | Phase.  Row 2: Start | slider | End | Total from the left (DYNAMIQ: after
        the Axis buttons X Y Z).  Row 3 (KINETIQ): Rot. centre with the Axis buttons."""
        w, pm, grid, cc = self.window, self.pm, self.grid, self.cc
        toggle = getattr(pm, "device_box", None)
        func_row = w.findChild(QWidget, "pmFuncRow")
        if toggle is None or func_row is None or cc is None:
            raise RuntimeError("Curve Options rows not as expected")
        parent = grid.parentWidget()
        i_dev, dev = self._cell(toggle)
        i_fun, fun = self._cell(func_row)
        _, phase = self._cell(w.input_phase)
        if dev is None or fun is None or phase is None:
            raise RuntimeError("Curve Options cells not found")
        cells = [dev, fun, phase]
        widgets = [lay.itemAt(k).widget() for lay in cells for k in range(lay.count())
                   if lay.itemAt(k).widget() is not None]
        states = _keep_visibility(widgets + [cc.time_box, self.rot_axis_row])
        self._kept = []
        for lay in cells:                                   # out of the grid (kept referenced)
            for i in range(grid.count()):
                if grid.itemAt(i).layout() is lay:
                    grid.takeAt(i)
                    break
            self._kept.append(lay)
        grid.removeWidget(cc.time_box)
        grid.removeWidget(self.rot_axis_row)

        # row 0
        row0 = QWidget(parent)
        row0.setObjectName("pmDeviceFunctionRow")
        h0 = QHBoxLayout(row0)
        h0.setContentsMargins(0, 0, 0, 0)
        h0.setSpacing(20)
        h0.addLayout(dev, 0)
        h0.addLayout(fun, 1)
        grid.addWidget(row0, 0, 0, 1, 4)
        # row 1: Phase right of Period
        grid.addLayout(phase, 1, 3)
        # row 2: (Axis) Start | slider | End | Total
        row2 = QWidget(parent)
        row2.setObjectName("pmAxisTimeRow")
        h2 = QHBoxLayout(row2)
        h2.setContentsMargins(0, 0, 0, 0)
        h2.setSpacing(20)
        h2.addWidget(cc.time_box, 1)
        grid.addWidget(row2, 2, 0, 1, 4)
        # row 3: Rot. centre (KINETIQ)
        grid.addWidget(self.rot_axis_row, 3, 0, 1, 4)
        for c in range(4):
            grid.setColumnStretch(c, 1)
        _restore_visibility(states)
        self.row0, self.row2, self.row2_layout = row0, row2, h2

        # no 'Device' title: its tooltip on the toggle; the toggle as wide as its two names
        for k in range(dev.count()):
            wd = dev.itemAt(k).widget()
            if isinstance(wd, QLabel):
                tip = wd.toolTip()
                wd.hide()
                toggle.setToolTip(tip)
        btns = list(getattr(pm, "device_buttons", []) or [])
        if btns:
            btns[0].ensurePolished()
            fm = QFontMetrics(btns[0].font())
            toggle.setFixedWidth((max(fm.horizontalAdvance(t) for t in DEVICE_NAMES) + 44) * len(btns))
        # title widths for the new columns
        for k in range(fun.count()):
            wd = fun.itemAt(k).widget()
            if isinstance(wd, QLabel):
                wd.setMinimumWidth(0)
        for k in range(phase.count()):
            wd = phase.itemAt(k).widget()
            if isinstance(wd, QLabel):
                self._column_width(wd, 3)
        self._column_width(cc.start_label, 0)

        w.combo_device.currentTextChanged.connect(lambda _t: QTimer.singleShot(0, self.place_axis))
        self.place_axis()

    def place_axis(self):
        """Axis buttons: KINETIQ next to Rot. centre, DYNAMIQ in front of Start (its Rot. centre row is hidden)."""
        try:
            w = self.window
            axis = w.axis_selection_widget
            rot_lay = self.rot_axis_row.layout()
            kinetiq = w.combo_device.currentText() == PLATFORM
            target = rot_lay if kinetiq else self.row2_layout
            if target.indexOf(axis) < 0:
                hidden = axis.isHidden()
                for lay in (rot_lay, self.row2_layout):
                    if lay.indexOf(axis) >= 0:
                        lay.removeWidget(axis)
                if kinetiq:
                    rot_lay.addWidget(axis, 1, Qt.AlignVCenter)
                else:
                    self.row2_layout.insertWidget(0, axis, 0, Qt.AlignVCenter)
                axis.setVisible(not hidden)
            shown = any(rot_lay.itemAt(i).widget() is not None and not rot_lay.itemAt(i).widget().isHidden()
                        for i in range(rot_lay.count()))
            self.rot_axis_row.setVisible(shown)
        except RuntimeError:
            pass

    # ------------------------------------------------------------------ 3c. individual axes start unchecked
    def individual_axes_off(self):
        """Plot curves: A B C D 'a 'c 'e 'f start unchecked whenever the legacy code builds the plot checkboxes
        (Planning opened, device switched, file imported: it builds them all checked); one the user turns on stays
        as the user set it."""
        from fcn_create_gui.tab_planning_modern import INDIVIDUAL_KEYS
        from fcn_plan import fcn_create as fc
        w, pm = self.window, self.pm
        user = {}
        seen = {"boxes": None}

        def apply():
            boxes = getattr(w, "create_axis_checkboxes", None) or {}
            if boxes is seen["boxes"]:
                return False
            seen["boxes"] = boxes
            changed = False
            for key in INDIVIDUAL_KEYS:
                cb = boxes.get(key)
                if cb is None:
                    continue
                want = user.get(key, False)
                if cb.isChecked() != want:
                    cb.blockSignals(True)
                    cb.setChecked(want)
                    cb.blockSignals(False)
                    changed = True
                cb.toggled.connect(lambda on, k=key: user.__setitem__(k, on))
            return changed

        original = pm.after_legacy_update

        def after_legacy_update():
            if apply():
                QTimer.singleShot(0, lambda: fc.trigger_plot_update(w))    # one redraw, outside this update
            original()

        pm.after_legacy_update = after_legacy_update
        if apply():
            fc.trigger_plot_update(w)

    # ------------------------------------------------------------------ 4. Pauses & trigger -> Trigger tab
    def move_event_card(self):
        w, pm = self.window, self.pm
        card = getattr(pm, "event_card", None)
        gate_tab = getattr(w, "trg_gate_tab", None)
        gate = w.trg_gate_axes_widget.parentWidget() if hasattr(w, "trg_gate_axes_widget") else None
        sc = gate_tab.findChild(QScrollArea) if gate_tab is not None else None
        content = sc.widget() if sc is not None else None
        clay = content.layout() if content is not None else None
        body = pm.curve_body.layout() if getattr(pm, "curve_body", None) is not None else None
        if None in (card, gate, clay, body) or not isinstance(gate, QGroupBox) or clay.indexOf(gate) < 0:
            raise RuntimeError("Pauses & trigger card or Trigger tab not as expected")
        states = _keep_visibility([card, gate])
        body.removeWidget(card)
        i = clay.indexOf(gate)
        clay.removeWidget(gate)
        row = QHBoxLayout()
        row.setSpacing(12)
        row.addWidget(card)
        row.addWidget(gate, 1)
        clay.insertLayout(i, row)
        _restore_visibility(states)
        tw = w.create_settings_tab_widget
        tw.setTabText(tw.indexOf(gate_tab), TRIGGER_TAB)
        self.trigger_content, self.trigger_row, self.gate_box = content, row, gate

        # Repeat preview: while the tab holding the card is open (it was: while the Curve tab was open)
        def repeat_preview_active():
            if getattr(pm, "event_mode", "once") != "repeat":
                return False
            cur = tw.currentWidget()
            return cur is not None and cur.isAncestorOf(card)

        pm.repeat_preview_active = repeat_preview_active

    # ------------------------------------------------------------------ 5. sub-tabs as a column on the right
    def vertical_tabs(self):
        """Curve / Pause and Trigger / Tools / Settings / Table as a button column on the right of the pages (the
        tab bar on top is hidden; the QTabWidget, its indexes and currentChanged stay as they are)."""
        from fcn_create_gui.logiq_shell import LINE, NAV_BG, NAV_HOVER, NAV_SELECTED, OLIVE_DARK, TEXT, TEXT_MUTED
        tw = self.window.create_settings_tab_widget
        sp = tw.parentWidget()
        if not isinstance(sp, QSplitter) or sp.indexOf(tw) < 0:
            raise RuntimeError("Planning sub-tabs are not in the bottom splitter")
        nav = QFrame()
        nav.setObjectName("pmSubNav")
        nav.setAttribute(Qt.WA_StyledBackground, True)
        nav.setStyleSheet(f"""
            QFrame#pmSubNav {{ background: {NAV_BG}; border: none; border-left: 1px solid {LINE}; }}
            QToolButton#pmSubNavButton {{ background: transparent; border: none; border-radius: 10px;
                                         color: {TEXT_MUTED}; font-size: 15px; font-weight: 600; padding: 6px 4px; }}
            QToolButton#pmSubNavButton:hover {{ background: {NAV_HOVER}; }}
            QToolButton#pmSubNavButton:checked {{ background: {NAV_SELECTED}; color: {TEXT}; }}
        """)
        v = QVBoxLayout(nav)
        v.setContentsMargins(6, 8, 6, 8)
        v.setSpacing(4)
        group = QButtonGroup(nav)
        group.setExclusive(True)
        buttons = {}
        for k in range(tw.count()):
            if not tw.isTabVisible(k):
                continue
            b = QToolButton(nav)
            b.setObjectName("pmSubNavButton")
            title = tw.tabText(k)
            key = next((n for n in SUBTAB_ICONS if title.lower().startswith(n)), None)
            if key is not None:                                   # icon, the title as tooltip
                b.setIcon(_svg_icon(SUBTAB_ICONS[key], OLIVE_DARK))
                b.setIconSize(QSize(SUBTAB_ICON_PX, SUBTAB_ICON_PX))
                b.setToolButtonStyle(Qt.ToolButtonIconOnly)
            else:                                                 # unknown tab: its title
                b.setText(title)
                b.setToolButtonStyle(Qt.ToolButtonTextOnly)
            b.setToolTip(title)
            b.setAccessibleName(title)
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            b.setMinimumHeight(SUBNAV_BUTTON_HEIGHT)
            b.clicked.connect(lambda _c=False, i=k: tw.setCurrentIndex(i))
            group.addButton(b)
            v.addWidget(b)
            buttons[k] = b
        v.addStretch(1)
        widest = max((b.sizeHint().width() for b in buttons.values()), default=44)
        nav.setFixedWidth(max(widest + 12, 56))

        def sync(i):
            b = buttons.get(i)
            if b is not None and not b.isChecked():
                b.setChecked(True)

        tw.currentChanged.connect(sync)
        sync(tw.currentIndex())

        holder = QWidget()
        holder.setObjectName("pmSubTabsHolder")
        self.subtabs_holder = holder      # kept: QSplitter.replaceWidget does not take it over from Python (else the
                                          # holder, and the tab widget in it, are deleted when this method returns)
        h = QHBoxLayout(holder)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)
        sp.replaceWidget(sp.indexOf(tw), holder)          # same splitter slot (its sizes stay the same)
        h.addWidget(tw, 1)
        h.addWidget(nav)                                   # on the right of the pages (user request)
        tw.tabBar().hide()
        tw.show()
        self.subnav, self.subnav_buttons = nav, buttons

    def tooltips(self):
        for wd in self.window.tab_planning.findChildren(QWidget):
            tip = wd.toolTip()
            if tip and any(old in tip for old, _ in TOOLTIP_TEXTS):
                for old, new in TOOLTIP_TEXTS:
                    tip = tip.replace(old, new)
                wd.setToolTip(tip)


def apply_planning_curve_layout(window):
    """Each part is independent: a part that fails is reported on stdout and the others are still applied."""
    done = getattr(window, "planning_curve_layout", None)
    if done is not None:
        return done
    pcl = PlanningCurveLayout(window)
    window.planning_curve_layout = pcl
    for name in ("titles_in_front", "time_row", "rotation_and_axis", "rows_by_device", "move_event_card",
                 "vertical_tabs", "tooltips", "individual_axes_off"):
        try:
            getattr(pcl, name)()
        except Exception as e:                     # never stops the tab from being built
            print(f"Planning curve layout: {name} failed: {e}")
    return pcl
