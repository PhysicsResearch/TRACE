"""
Control tab: work zero UI and actuator rows (the logic is fcn_control/work_zero.py).

    from fcn_create_gui.work_zero_ui import install_work_zero_ui
    install_work_zero_ui(self)          # in build_control_tab, after the sub-tabs, before the start-up scaler

* PLATFORM table: rows "A | B" and "C | D" (free grid rows 4-5, the columns of rows 1-3): Current POS_CURR_PLAT_A..D
  (mirrors of the hidden IND. MOTORS fields POS_CURR_A..D, which the status poll writes), Target POS_DES_A..D
  (goto_targets pairs them with POS_CURR_A..D; Return = Go to ...), jog buttons MIN_A..D / PLUS_A..D ("- A" / "+ A",
  so the start-up scaler skips them; jog_actuator).  The jog buttons and the axis chips have the actuator colours
  marked on the platform: A red, B white, C yellow, D purple (kept by the theme: kq_keep_colors).  To fit five rows
  the table is compacted: every Current / Target field 30 px before scaling (45 after), smaller spacing.
* "Set zero" (set current position as zero) and a zero status label on both pages: LUNG PHANTOM after "Go to" in its
  top panel, PLATFORM in an extra table column (vertical button, label in the header row).  The label shows
  work_zero.zero_summary(...)["text"] ("detail" as tool tip), amber when the zero is not the standard one or not
  read.  The button is enabled when work_zero.zero_ready(...) is ok (else its tool tip says why) and opens the
  Set zero dialog (open_set_zero_dialog).
* PLATFORM "Home LAT", "Home SI", "Home AP" right after "Home ALL" (fcn_control.home 'LAT' / 'SI' / 'AP').  The
  buttons of that row get compact widths and its two title labels two lines, so the row stays about as wide.
* Refresh: every status poll (work_zero.add_listener) and every connection change (windowTitleChanged): Set zero
  buttons, zero labels, A-D jog buttons, an open Set zero dialog; on connection changes also fcn_control's
  update_moving_button_styles / update_home_button_styles (connect / disconnect do not poll).  The A-D jog buttons
  (refresh_actuator_buttons) also run from update_moving_button_styles, after the poll's homed flags.
* Set zero dialog: rows whose axes are not homed cannot be ticked, and their "becomes" field is out of reach of the
  touch keypad (a value written into it while it is unavailable is cleared).
"""
import math
import types

from PySide6.QtCore import QRect, Qt, QTimer
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import (QCheckBox, QDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
                               QPushButton, QSizePolicy, QStyle, QStyleOptionButton, QStylePainter, QVBoxLayout)

from fcn_control import work_zero as WZ
from fcn_control.work_zero_frame import KINETIQ_CENTRE_DOF
from fcn_create_gui.tab_control import RotatedButton

KINETIQ, DYNAMIQ = WZ.KINETIQ, WZ.DYNAMIQ
ACTUATORS = ("A", "B", "C", "D")

# Actuator colours as marked on the platform:
#   (background, text, border, hover; disabled: pale tint of the colour, muted text, border)
ACTUATOR_COLORS = {
    "A": ("#d32f2f", "#ffffff", "none", "#b71c1c", "#f6d6d6", "#cc9393", "none"),
    "B": ("#ffffff", "#212121", "1px solid #9e9e9e", "#eeeeee", "#fcfcfc", "#bdbdbd", "1px solid #e3e3e3"),
    "C": ("#fbc02d", "#212121", "none", "#f9a825", "#fdf0c6", "#bfa55c", "none"),
    "D": ("#7b1fa2", "#ffffff", "none", "#6a1b9a", "#ead9f1", "#ae90bd", "none"),
}

# PLATFORM table compaction (five rows in about the height of three): fields 30 px before the start-up scaler
# (45 px after, as the jog buttons), vertical spacing and top / bottom margin of the grid
FIELD_MIN_HEIGHT = 30
TABLE_VSPACING = 4
TABLE_MARGIN_TB = 6

# PLATFORM button row (Go to ... / Go to zero / Home ALL / LAT / SI / AP, 16 px): compact minimum widths
ROW_BUTTON_WIDTHS = {"btn_go_to": 80, "btn_go_to_center": 92, "HOME_ALL_PLATFORM": 84, "HOME_LAT_PLATFORM": 84,
                     "HOME_SI_PLATFORM": 80, "HOME_AP_PLATFORM": 80}
ROW_TITLE_WRAP = {"Platform Dimensions:": "Platform\nDimensions:", "Offset Rot. (mm):": "Offset Rot.\n(mm):"}

CURR_STYLE = """
    QLineEdit {
        background-color: #f5f5f5;
        font-weight: bold;
        font-size: 15px;
        border: 1px solid #b0bec5;
        border-radius: 5px;
        padding: 4px 8px;
    }
"""
DES_STYLE = CURR_STYLE.replace("#f5f5f5", "#ffffff")

# zero status label (font-size before the start-up scaler: 10 px -> 14 px); its width fits the longest text it can
# show (ZERO_TEXTS), so the PLATFORM table and the LUNG PHANTOM panel do not shift when the zero changes
ZERO_LABEL_PAD = 8
ZERO_LABEL_STYLE = (
    "QLabel#{name} {{ font-size: 10px; font-weight: bold; color: #4b6143; background-color: #e9eee3; "
    "border: 1px solid #ccd5c2; border-radius: 8px; padding: 1px " + str(ZERO_LABEL_PAD) + "px; }}\n"
    "QLabel#{name}[zeroState=\"warn\"] {{ color: #8a4b00; background-color: #fff3e0; border: 1px solid #ffb74d; }}\n"
    "QLabel#{name}[zeroState=\"off\"] {{ color: #7d8b75; background-color: #ffffff; border: 1px solid #e9eee3; }}")

ZERO_TEXTS = {   # work_zero.zero_summary texts per page
    KINETIQ: ("Zero: platform centre", "Zero: home, not centre", "Zero: custom", "Zero: not read", "Not connected",
              "DYNAMIQ connected"),
    DYNAMIQ: ("Zero: home (0)", "Zero: custom", "Zero: not read", "Not connected", "KINETIQ connected"),
}
SET_ZERO_TIP = ("Set current position as zero: the positions you pick read a new value (G10 L20). Nothing moves, "
                "only the numbers change.")
NOTE = {KINETIQ: "Nothing moves: only the numbers change. Homing puts the zero back at the platform centre.",
        DYNAMIQ: "Nothing moves: only the numbers change. Homing puts the zero back at home (0)."}
STANDARD_BUTTON = {KINETIQ: "Back to centre", DYNAMIQ: "Back to home zero"}


# ---------------------------------------------------------------------------------------------------------- styles
def actuator_button_style(m):
    """Jog button of actuator m in its colour; disabled: a pale tint of the same colour (stays recognisable)."""
    bg, fg, border, hover, dbg, dfg, dborder = ACTUATOR_COLORS[m]
    return (f"QPushButton {{ background-color: {bg}; color: {fg}; font-weight: bold; font-size: 20px; "
            f"min-height: 45px; border-radius: 6px; border: {border}; }}\n"
            f"QPushButton:hover {{ background-color: {hover}; }}\n"
            f"QPushButton:pressed {{ background-color: {hover}; padding-top: 3px; padding-left: 3px; }}\n"
            f"QPushButton:disabled, QPushButton:disabled:hover {{ background-color: {dbg}; color: {dfg}; "
            f"border: {dborder}; }}")


def actuator_chip_style(m, font_px=17):
    """Axis name of actuator m as a small chip in its colour (font before the start-up scaler: 17 -> 23 px)."""
    bg, fg, border = ACTUATOR_COLORS[m][:3]
    return (f"QLabel {{ background-color: {bg}; color: {fg}; border: {border}; border-radius: 6px; "
            f"font-weight: bold; font-size: {font_px}px; padding: 0px 9px; }}")


def _motion_style(*a, **k):
    from fcn_control.fcn_control import motion_button_style
    return motion_button_style(*a, **k)


def _set_button(btn, style, enabled):
    from fcn_control.fcn_control import set_motion_button
    set_motion_button(btn, style, enabled)


def _paint_rotated(btn, _event):
    """RotatedButton painting with the text colour of the button's stylesheet (palette ButtonText, also for
    :disabled) instead of a fixed white, so the light 'homed' tint and the disabled look keep a readable text."""
    painter = QStylePainter(btn)
    option = QStyleOptionButton()
    btn.initStyleOption(option)
    text = option.text
    option.text = ""
    painter.drawControl(QStyle.CE_PushButton, option)
    painter.save()
    painter.setPen(option.palette.color(QPalette.ButtonText))
    font = btn.font()
    font.setBold(True)
    font.setPointSize(15)
    painter.setFont(font)
    rect = btn.rect()
    painter.translate(rect.center())
    painter.rotate(getattr(btn, 'rotation', -90))
    painter.drawText(QRect(-rect.height() // 2, -rect.width() // 2, rect.height(), rect.width()), Qt.AlignCenter,
                     text)
    painter.restore()


class VerticalButton(RotatedButton):
    """RotatedButton (vertical text) whose text takes the stylesheet colour (_paint_rotated)."""

    def paintEvent(self, event):
        _paint_rotated(self, event)


# ---------------------------------------------------------------------------------------------------------- install
def install_work_zero_ui(self):
    """Builds the work zero UI into the Control tab (see the module docstring).  Each part is independent: a part that
    fails is reported on stdout and the others are still built."""
    for part in (_add_actuator_rows, _add_set_zero_platform, _add_set_zero_lung, _add_home_group_buttons,
                 _compact_button_row, _readable_home_all, _platform_table_takes_height, _add_si_b_field):
        try:
            part(self)
        except Exception as e:                       # never stops the window from being built
            print(f"Work zero UI: {part.__name__} failed: {e}")
    WZ.add_listener(self, refresh_work_zero_ui)
    try:
        self.windowTitleChanged.connect(lambda _t: on_connection_change(self))   # connect / disconnect
    except Exception as e:
        print(f"Work zero UI: connection hook failed: {e}")
    on_connection_change(self)
    QTimer.singleShot(0, lambda: refresh_work_zero_ui(self))     # after the start-up scaler: label widths


def _platform_grid(self):
    grid = self.POS_CURR_LATAXIS.parentWidget().layout()
    if not isinstance(grid, QGridLayout):
        raise RuntimeError("PLATFORM table grid not found")
    return grid


def _add_actuator_rows(self):
    """Rows 4 ('A | B') and 5 ('C | D') of the PLATFORM table, and the table compaction."""
    from fcn_create_gui.touch_keyboard import register_touch_line_edit
    grid = _platform_grid(self)
    frame = grid.parentWidget()

    for key in ('LATAXIS', 'SIAXIS', 'APAXIS', 'ROLL', 'PITCH', 'YAW'):          # existing fields: 30 px (45 scaled)
        for prefix in ('POS_CURR_', 'POS_DES_'):
            field = getattr(self, prefix + key, None)
            if field is not None:
                field.setMinimumHeight(FIELD_MIN_HEIGHT)
    grid.setVerticalSpacing(TABLE_VSPACING)
    m = grid.contentsMargins()
    grid.setContentsMargins(m.left(), TABLE_MARGIN_TB, m.right(), TABLE_MARGIN_TB)

    for row, pair in ((4, ("A", "B")), (5, ("C", "D"))):
        for block, act in enumerate(pair):
            c0 = 5 * block
            chip = QLabel(act, frame)
            chip.setProperty('kq_keep_colors', True)                          # actuator colours: never remapped
            chip.setStyleSheet(actuator_chip_style(act))
            chip.setAlignment(Qt.AlignCenter)
            chip.setToolTip(f"Actuator {act} (colour as marked on the platform)")
            setattr(self, f"LBL_PLAT_{act}", chip)
            grid.addWidget(chip, row, c0, Qt.AlignCenter)

            curr = QLineEdit("0.000", frame)
            curr.setReadOnly(True)
            curr.setMinimumHeight(FIELD_MIN_HEIGHT)
            curr.setMaximumWidth(100)
            curr.setStyleSheet(CURR_STYLE)
            setattr(self, f"POS_CURR_PLAT_{act}", curr)
            src = getattr(self, f"POS_CURR_{act}", None)                    # hidden IND. MOTORS field (poll)
            if src is not None:
                curr.setText(src.text())
                src.textChanged.connect(curr.setText)
            grid.addWidget(curr, row, c0 + 1)

            des = QLineEdit(curr.text(), frame)
            des.setMinimumHeight(FIELD_MIN_HEIGHT)
            des.setMaximumWidth(100)
            des.setStyleSheet(DES_STYLE)
            setattr(self, f"POS_DES_{act}", des)
            register_touch_line_edit(self, des, label_name=f"Target Pos {act}")
            des.returnPressed.connect(lambda: _go_platform(self))
            grid.addWidget(des, row, c0 + 2)

            for col, plus in ((3, False), (4, True)):
                btn = QPushButton(f"{'+' if plus else '-'} {act}", frame)
                btn.setProperty('kq_keep_colors', True)
                btn.setStyleSheet(actuator_button_style(act))
                btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
                btn.clicked.connect(lambda _c=False, a=act, p=plus: jog_actuator(self, a, p))
                setattr(self, f"{'PLUS' if plus else 'MIN'}_{act}", btn)
                grid.addWidget(btn, row, c0 + col)
        grid.setRowStretch(row, 1)


def _zero_label(name, parent):
    lbl = QLabel("", parent)
    lbl.setObjectName(name)
    lbl.setStyleSheet(ZERO_LABEL_STYLE.format(name=name))
    lbl.setAlignment(Qt.AlignCenter)
    lbl.setProperty('zeroState', "off")
    return lbl


def _add_set_zero_platform(self):
    """Extra PLATFORM table column: zero label in the header row, vertical Set zero button over rows 1-5."""
    grid = _platform_grid(self)
    frame = grid.parentWidget()
    col = 10
    self.lbl_zero_platform = _zero_label("zeroStatusPlatform", frame)
    grid.addWidget(self.lbl_zero_platform, 0, col, Qt.AlignCenter)
    btn = VerticalButton("Set zero", frame, rotation=-90)
    btn.setFixedWidth(80)
    btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
    btn.setProperty('wzStyle', _motion_style(20, None))
    btn.setStyleSheet(btn.property('wzStyle'))
    btn.setToolTip(SET_ZERO_TIP)
    btn.clicked.connect(lambda _c=False: open_set_zero_dialog(self, KINETIQ))
    self.btn_set_zero_platform = btn
    grid.addWidget(btn, 1, col, 5, 1, Qt.AlignHCenter)
    grid.setColumnStretch(col, 0)


def _add_set_zero_lung(self):
    """LUNG PHANTOM top panel, after Go to: separator, zero label, Set zero (fixed height 36 like Go to)."""
    panel = self.btn_goto_lung.parentWidget()
    lay = panel.layout()
    sep = QFrame(panel)
    sep.setFixedHeight(28)
    sep.setFrameShape(QFrame.VLine)
    sep.setFrameShadow(QFrame.Sunken)
    sep.setStyleSheet("border: none; background-color: #cfd8dc; width: 1px; margin: 0px 8px;")
    lay.addWidget(sep, 0, Qt.AlignVCenter)
    self.lbl_zero_lung = _zero_label("zeroStatusLung", panel)
    lay.addWidget(self.lbl_zero_lung, 0, Qt.AlignVCenter)
    btn = QPushButton("Set zero", panel)
    btn.setFixedHeight(36)
    btn.setMinimumWidth(100)
    btn.setProperty('wzStyle', _motion_style(16, None, extra="padding: 0px 16px;"))
    btn.setStyleSheet(btn.property('wzStyle'))
    btn.setToolTip(SET_ZERO_TIP)
    btn.clicked.connect(lambda _c=False: open_set_zero_dialog(self, DYNAMIQ))
    self.btn_set_zero_lung = btn
    lay.addWidget(btn, 0, Qt.AlignVCenter)


def _home(self, group):
    from fcn_control import fcn_control as FC
    FC.home(self, group)


def _add_home_group_buttons(self):
    """Home LAT / Home SI / Home AP right after Home ALL in the PLATFORM button row (the trigger toggle stays last)."""
    home_all = self.HOME_ALL_PLATFORM
    row = home_all.parentWidget().layout()
    i = row.indexOf(home_all)
    if i < 0:
        raise RuntimeError("Home ALL not found in the PLATFORM button row")
    tips = {"LAT": "Home LAT ('e 'f). Its zero goes back to the platform centre.",
            "SI": "Home SI ('a and 'c or 'b). Its zero goes back to the platform centre.",
            "AP": "Home AP (actuators A B C D). Their zero goes back to the platform centre."}
    from fcn_control.fcn_control import ROW_BUTTON_EXTRA
    for k, group in enumerate(("LAT", "SI", "AP"), start=1):
        btn = QPushButton(f"Home {group}", home_all.parentWidget())
        btn.setMinimumHeight(45)
        btn.setStyleSheet(_motion_style(16, 45, extra=ROW_BUTTON_EXTRA))
        btn.setToolTip(tips[group])
        btn.clicked.connect(lambda _c=False, g=group: _home(self, g))
        setattr(self, f"HOME_{group}_PLATFORM", btn)
        row.insertWidget(i + k, btn)


def _compact_button_row(self):
    """PLATFORM button row: compact minimum widths for its buttons; its two title labels on two lines."""
    for name, width in ROW_BUTTON_WIDTHS.items():
        btn = getattr(self, name, None)
        if btn is not None:
            btn.setMinimumWidth(width)
    for lbl in self.HOME_ALL_PLATFORM.parentWidget().findChildren(QLabel):
        wrapped = ROW_TITLE_WRAP.get(lbl.text())
        if wrapped:
            lbl.setText(wrapped)


def _readable_home_all(self):
    """LUNG PHANTOM Home ALL (vertical text, painted white by RotatedButton): text in its stylesheet colour, so the
    light 'homed' tint and the disabled look stay readable."""
    btn = getattr(self, 'HOME_ALL', None)
    if isinstance(btn, RotatedButton):
        btn.paintEvent = types.MethodType(_paint_rotated, btn)


def _platform_table_takes_height(self):
    """PLATFORM page (a QVBoxLayout: table, button row, trailing stretch): the table gets the spare height of a large
    window (stretch 1, the trailing stretch 0), so its rows, the A-D rows and the vertical Set zero button grow and the
    button row stays right under the table; before, the trailing stretch took the height and left an empty band
    between the button row and the console.  Only stretch factors change (no item is moved), so the minimum sizes
    stay the same.  (The LUNG PHANTOM page has no trailing stretch: its table frame already takes the height.)"""
    page = self.tab_platform.layout()
    table = _platform_grid(self).parentWidget()
    row = self.HOME_ALL_PLATFORM.parentWidget()
    i_table, i_row = page.indexOf(table), page.indexOf(row)
    if i_table < 0 or i_row < 0:
        raise RuntimeError("PLATFORM table / button row not found in the page layout")
    page.setStretch(i_table, 1)
    for k in range(i_row + 1, page.count()):         # the trailing stretch (addStretch)
        page.setStretch(k, 0)


def _add_si_b_field(self):
    """Hidden IND. MOTORS field POS_CURR_'b next to POS_CURR_'a / 'c: on the boards that use 'b for SI's second motor
    the status poll writes its position there, and SI = mean of 'a and 'b (fcn_control.update_duet_status_ui)."""
    if getattr(self, "POS_CURR_'b", None) is not None:
        return
    ref = getattr(self, "POS_CURR_'c")
    field = QLineEdit("0.000", ref.parentWidget())
    field.setReadOnly(True)
    field.hide()                                     # like the page it belongs to: never shown
    setattr(self, "POS_CURR_'b", field)
    fields = getattr(self, 'ext_curr_pos_fields', None)
    if isinstance(fields, dict):
        fields["'b"] = field


# ---------------------------------------------------------------------------------------------------------- refresh
def on_connection_change(self):
    """Connect / disconnect (window title): no status poll follows a disconnect, so every Control motion button is
    re-evaluated here (fcn_control styles and enabled states, then the work zero UI)."""
    from fcn_control import fcn_control as FC
    for fn in (FC.update_moving_button_styles, FC.update_home_button_styles, refresh_work_zero_ui):
        try:
            fn(self)
        except Exception as e:
            print(f"Work zero UI: {getattr(fn, '__name__', fn)} failed: {e}")


def actuator_homed(self, m):
    """Actuator m homed: work_zero's record of the board (per board; refreshed first on every poll, so it is never a
    poll behind) when it has the axis, else LogIQ's homed flag of that letter (upper-case A-D only, never SI's
    'a / 'b / 'c)."""
    ax = WZ.state(self).axes.get(m)
    if ax is not None and 'homed' in ax:
        return bool(ax['homed'])
    return bool((getattr(self, 'ext_axes_homed', None) or {}).get(m))


def refresh_actuator_buttons(self):
    """A-D jog buttons: available when KINETIQ is connected and that actuator is homed.  Runs from the work zero
    listener (inside the poll's sync) and from fcn_control.update_moving_button_styles (after the poll's homed
    flags), so a change shows on the same poll."""
    ok = _actuators_ok(self)
    for m in ACTUATORS:
        enabled = ok and actuator_homed(self, m)
        for prefix in ('MIN_', 'PLUS_'):
            _set_button(getattr(self, f"{prefix}{m}", None), actuator_button_style(m), enabled)


def _actuators_ok(self):
    return bool(getattr(self, 'duet_connected', False)) and WZ.device_of(self) == KINETIQ


def _fit_zero_label(lbl, device, current):
    """Minimum width of a zero label = its longest possible text (as shown) with the label's font after the start-up
    scaler, so the label does not resize the table / panel when the zero changes."""
    from fcn_create_gui.display_names import display_text
    lbl.ensurePolished()
    fm = lbl.fontMetrics()
    need = max(fm.horizontalAdvance(display_text(t)) for t in ZERO_TEXTS.get(device, ()) + (current,))
    need += 2 * ZERO_LABEL_PAD + 2 + 4                      # padding, border, a little air
    if lbl.minimumWidth() != need:
        lbl.setMinimumWidth(need)


def _show_zero(lbl, zs, device=None):
    state = "warn" if zs.get("kind") in ("custom", "unknown") else ("std" if zs.get("standard") else "off")
    if device is not None:
        _fit_zero_label(lbl, device, zs.get("text", ""))
    if lbl.text() != zs.get("text", ""):
        lbl.setText(zs.get("text", ""))
    if lbl.property('wzTip') != zs.get("detail", ""):
        lbl.setProperty('wzTip', zs.get("detail", ""))
        lbl.setToolTip(zs.get("detail", ""))
    if lbl.property('zeroState') != state:
        lbl.setProperty('zeroState', state)
        lbl.style().unpolish(lbl)
        lbl.style().polish(lbl)


def refresh_work_zero_ui(self):
    """Zero labels, Set zero buttons, A-D jog buttons and an open Set zero dialog (work_zero listener: every status
    poll and every fresh read of the Duet; also on connection changes)."""
    for device, lbl_name, btn_name in ((DYNAMIQ, 'lbl_zero_lung', 'btn_set_zero_lung'),
                                       (KINETIQ, 'lbl_zero_platform', 'btn_set_zero_platform')):
        lbl, btn = getattr(self, lbl_name, None), getattr(self, btn_name, None)
        if lbl is not None:
            _show_zero(lbl, WZ.zero_summary(self, device), device)
        if btn is not None:
            ok, reason = WZ.zero_ready(self, device)
            _set_button(btn, btn.property('wzStyle'), ok)
            tip = SET_ZERO_TIP if ok else f"Set zero is not available: {reason}"
            if btn.property('wzTip') != tip:
                btn.setProperty('wzTip', tip)
                btn.setToolTip(tip)
    refresh_actuator_buttons(self)
    dlg = getattr(self, '_set_zero_dialog', None)
    if dlg is not None:
        try:
            dlg.refresh()
        except RuntimeError:
            self._set_zero_dialog = None
    try:
        refresh_si_letter_labels(self)
    except Exception as e:
        print(f"Work zero UI: SI motor labels not refreshed: {e}")


def refresh_si_letter_labels(self):
    """Status tab: the curve of SI's second motor (data key "'c") is named after the board's letter, 'c or 'b
    (work_zero.kinetiq_si_motors: the connected KINETIQ board, else the last one seen): its pill, its legacy check box
    ('Show 'b') and its position label.  The widgets keep their axis colour (kq_keep_colors)."""
    from fcn_control.work_zero_frame import SI_SECOND
    letter = WZ.kinetiq_si_motors(self)[1]
    ms = getattr(self, 'status_modern', None)
    pill = (getattr(ms, 'pills', None) or {}).get("'c") if ms is not None else None
    for wdg in (pill, getattr(self, 'status_check_c', None)):
        old = wdg.text() if wdg is not None else ""
        other = next((o for o in SI_SECOND if o != letter and o in old), None)
        if other is None:
            continue
        wdg.setProperty('kq_keep_colors', True)
        wdg.setText(old.replace(other, letter))                   # "'c" -> "'b", "Show 'c" -> "Show 'b"
        wdg.setToolTip(wdg.toolTip().replace(f"axis {other} ", f"axis {letter} "))
    lbl = getattr(self, 'statusPos_c', None)
    if lbl is not None:
        t = lbl.text()
        for other in SI_SECOND:
            if other != letter and t.startswith(other + " "):
                lbl.setText(letter + t[len(other):])


# ---------------------------------------------------------------------------------------------------------- actions
def _go_platform(self):
    from fcn_control.goto_targets import go_platform_changed
    go_platform_changed(self)


def jog_actuator(self, m, plus=True):
    """'- A' / '+ A' ... (PLATFORM rows A-D): one actuator by the step size.  Refused when not connected, when the
    connected board is not KINETIQ or when the actuator is not homed; else fcn_control.step (G91 + G1 A<step> F600,
    checked against LogIQ's actuator range 0.2-70 mm machine and the M208 limits).  True when the step was sent on."""
    from fcn_control import fcn_control as FC
    if not getattr(self, 'duet_connected', False):
        FC.log_to_duet_console(self, f"Error: Cannot move actuator {m}. Not connected to Duet.", color="#ff3333")
        QMessageBox.warning(self, "Not Connected", "Please connect to Duet before moving axes.")
        return False
    dev = WZ.device_of(self)
    if dev != KINETIQ:
        why = f"The actuators A-D are KINETIQ motors; the connected board is {dev or 'not recognised'}."
        FC.log_to_duet_console(self, f"Error: Cannot move actuator {m}. {why}", color="#ff3333")
        QMessageBox.warning(self, "Wrong Device", f"Cannot move actuator {m}.\n{why}")
        return False
    if not actuator_homed(self, m):
        FC.log_to_duet_console(self, f"Error: Cannot move actuator {m}. Please home the axis first!", color="#ff3333")
        QMessageBox.warning(self, "Axis Not Homed", f"Cannot move actuator {m}.\nPlease home the axis first!")
        return False
    FC.step(self, m, plus=plus)
    return True


def open_set_zero_dialog(self, device):
    """Set zero button: the modal Set zero dialog of ``device`` (built now, so the start-up scaler never sizes it).
    Returns the dialog result (QDialog.Accepted when a zero was set), None when not available."""
    ok, reason = WZ.zero_ready(self, device)
    if not ok:
        QMessageBox.warning(self, "Set zero", reason)
        return None
    dlg = SetZeroDialog(self, device)
    self._set_zero_dialog = dlg
    try:
        return dlg.exec()
    finally:
        self._set_zero_dialog = None
        dlg.deleteLater()


# ---------------------------------------------------------------------------------------------------------- dialog
DIALOG_STYLE = """
    QDialog#wzDialog { background-color: #ffffff; }
    QLabel { font-size: 16px; color: #283024; background: transparent; }
    QLabel#wzSummary { font-size: 18px; font-weight: bold; color: #4b6143; background-color: #e9eee3;
                       border: 1px solid #ccd5c2; border-radius: 8px; padding: 6px 12px; }
    QLabel#wzSummary[zeroState="warn"] { color: #8a4b00; background-color: #fff3e0; border: 1px solid #ffb74d; }
    QLabel#wzSummary[zeroState="off"] { color: #5a6954; background-color: #f4f6f0; border: 1px solid #ccd5c2; }
    QLabel#wzDetail { font-size: 16px; color: #3a4535; }
    QLabel#wzHeader { font-size: 16px; font-weight: bold; color: #5a6954; }
    QLabel#wzCurrent { font-size: 18px; font-weight: bold; color: #283024; }
    QLabel#wzRowNote { font-size: 16px; font-weight: bold; color: #8a4b00; }
    QLabel#wzNote { font-size: 16px; color: #5a6954; }
    QLabel#wzMessage { font-size: 16px; font-weight: bold; color: #c62828; }
    QCheckBox { font-size: 18px; font-weight: bold; color: #283024; spacing: 12px; min-height: 44px; }
    QCheckBox::indicator { width: 28px; height: 28px; }
    QCheckBox:disabled { color: #a2aa99; }
    QLineEdit { font-size: 18px; font-weight: bold; color: #283024; background-color: #ffffff; min-height: 44px;
                border: 1px solid #b5c0a9; border-radius: 5px; padding: 0px 10px; }
    QLineEdit:focus { border: 2px solid #4b6143; }
    QLineEdit:disabled { background-color: #f1f4ed; color: #a2aa99; border: 1px solid #dde4d5; }
    QPushButton#wzStandard, QPushButton#wzCancel { background-color: #ffffff; color: #4b6143; font-size: 18px;
        font-weight: bold; min-height: 48px; border: 2px solid #4b6143; border-radius: 6px; padding: 0px 18px; }
    QPushButton#wzCancel { color: #3a4535; border: 2px solid #b5c0a9; }
    QPushButton#wzStandard:hover, QPushButton#wzCancel:hover { background-color: #e9eee3; }
    QPushButton#wzStandard:pressed, QPushButton#wzCancel:pressed { padding-top: 3px; padding-left: 21px; }
    QPushButton#wzStandard:disabled { color: #a2aa99; border: 2px solid #dde4d5; background-color: #ffffff; }
"""


BECOMES_DEFAULT = "0.000"


def _keypad_reachable(edit, on):
    """The touch keypad filter (register_touch_line_edit) on a "becomes" field only while its row is available: Qt
    still hands a press on a disabled field to its event filters, which opened the keypad on an unhomed row."""
    filt = getattr(edit, '_touch_filter', None)
    if filt is None or bool(edit.property('wzKeypad')) == bool(on):
        return
    if on:
        edit.installEventFilter(filt)
    else:
        edit.removeEventFilter(filt)
    edit.setProperty('wzKeypad', bool(on))


def _number(text):
    """A typed number (decimal comma and the minus sign '−' accepted), None when it is not a finite number."""
    try:
        x = float(str(text).strip().replace(",", ".").replace("−", "-"))
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


class SetZeroDialog(QDialog):
    """Set current position as zero (KINETIQ: LAT, SI, AP, A, B, C, D; DYNAMIQ: X, Y, Z).

    One row per work_zero.ROWS[device]: tick box with the axis name, current value, "becomes" field (default 0.000,
    negatives allowed).  Set zero -> work_zero.set_zero (closes on success, stays open otherwise); Back to centre /
    Back to home zero -> a Yes / No question, then work_zero.set_standard_zero; Cancel.  Rows whose axes are not
    homed are shown but cannot be ticked.  Built at click time: explicit sizes, fonts >= 16 px, controls >= 44 px."""

    def __init__(self, win, device):
        from fcn_create_gui.touch_keyboard import register_touch_line_edit
        super().__init__(win)
        self.win, self.device = win, device
        self.setObjectName("wzDialog")
        self.setWindowTitle(f"Set current position as zero - {device}")
        self.setModal(True)
        self.setMinimumWidth(700)
        self.setStyleSheet(DIALOG_STYLE)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 18, 22, 18)
        lay.setSpacing(10)

        self.lbl_summary = QLabel("", self)
        self.lbl_summary.setObjectName("wzSummary")
        lay.addWidget(self.lbl_summary)
        det = QGridLayout()
        det.setHorizontalSpacing(28)
        det.setVerticalSpacing(2)
        self.lbl_detail = [QLabel("", self), QLabel("", self)]          # two columns of 'LAT: 0 at machine ...'
        for i, lbl in enumerate(self.lbl_detail):
            lbl.setObjectName("wzDetail")
            lbl.setAlignment(Qt.AlignLeft | Qt.AlignTop)
            det.addWidget(lbl, 0, i)
        self.lbl_detail_more = QLabel("", self)                       # other text (e.g. 'home, not centre'), wrapped
        self.lbl_detail_more.setObjectName("wzDetail")
        self.lbl_detail_more.setWordWrap(True)
        det.addWidget(self.lbl_detail_more, 1, 0, 1, 2)
        det.setColumnStretch(1, 1)
        lay.addLayout(det)

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(4)
        for col, text in ((1, "Axis"), (2, "Current (mm)"), (3, "Becomes (mm)")):
            h = QLabel(text, self)
            h.setObjectName("wzHeader")
            grid.addWidget(h, 0, col)
        self.rows = {}
        for r, (row, _motors) in enumerate(WZ.ROWS[device], start=1):
            if row in ACTUATORS:
                sw = QLabel("", self)
                sw.setProperty('kq_keep_colors', True)
                bg, _fg, border = ACTUATOR_COLORS[row][:3]
                edge = border if border != "none" else f"1px solid {bg}"
                sw.setStyleSheet(f"QLabel {{ background-color: {bg}; border: {edge}; border-radius: 4px; }}")
                sw.setFixedSize(16, 28)
                grid.addWidget(sw, r, 0, Qt.AlignVCenter)
            cb = QCheckBox(row, self)
            cb.setMinimumWidth(110)
            cur = QLabel("-", self)
            cur.setObjectName("wzCurrent")
            cur.setMinimumWidth(130)
            edit = QLineEdit(BECOMES_DEFAULT, self)
            edit.setFixedWidth(150)
            edit.setMinimumHeight(44)
            register_touch_line_edit(win, edit, label_name=f"{row} becomes (mm)")
            edit.setProperty('wzKeypad', True)                   # the keypad filter is installed (refresh toggles it)
            edit.textChanged.connect(lambda _t, c=cb, e=edit: self._edited(c, e))
            cb.toggled.connect(lambda _on: self._message(""))
            note = QLabel("", self)
            note.setObjectName("wzRowNote")
            grid.addWidget(cb, r, 1)
            grid.addWidget(cur, r, 2)
            grid.addWidget(edit, r, 3)
            grid.addWidget(note, r, 4)
            grid.setRowMinimumHeight(r, 46)
            self.rows[row] = {'cb': cb, 'cur': cur, 'edit': edit, 'note': note}
        grid.setColumnStretch(4, 1)
        lay.addLayout(grid)

        self.lbl_message = QLabel("", self)
        self.lbl_message.setObjectName("wzMessage")
        self.lbl_message.setWordWrap(True)
        self.lbl_message.hide()
        lay.addWidget(self.lbl_message)
        note = QLabel(NOTE[device], self)
        note.setObjectName("wzNote")
        note.setWordWrap(True)
        lay.addWidget(note)

        buttons = QHBoxLayout()
        buttons.setSpacing(12)
        self.btn_standard = QPushButton(STANDARD_BUTTON[device], self)
        self.btn_standard.setObjectName("wzStandard")
        self.btn_cancel = QPushButton("Cancel", self)
        self.btn_cancel.setObjectName("wzCancel")
        self.btn_set = QPushButton("Set zero", self)
        self.btn_set.setObjectName("wzSet")
        self.btn_set.setStyleSheet(_motion_style(18, 48, extra="padding: 0px 22px;"))
        for b in (self.btn_standard, self.btn_cancel):
            b.setAutoDefault(False)
        self.btn_set.setDefault(True)
        buttons.addWidget(self.btn_standard)
        buttons.addStretch(1)
        buttons.addWidget(self.btn_cancel)
        buttons.addWidget(self.btn_set)
        lay.addLayout(buttons)
        self.btn_set.clicked.connect(self._on_set)
        self.btn_standard.clicked.connect(self._on_standard)
        self.btn_cancel.clicked.connect(self.reject)
        self.refresh()

    # -------------------------------------------------------------------------------------- state
    def _edited(self, cb, edit):
        """Typing in a "becomes" field ticks its row; a value written into an unavailable field (e.g. by a keypad
        opened before its row became unavailable) is cleared."""
        if not edit.isEnabled():
            if edit.text() != BECOMES_DEFAULT:
                edit.blockSignals(True)
                edit.setText(BECOMES_DEFAULT)
                edit.blockSignals(False)
            return
        if cb.isEnabled():
            cb.setChecked(True)

    def _message(self, text):
        self.lbl_message.setText(text)
        self.lbl_message.setVisible(bool(text))

    def refresh(self):
        """Summary, detail, current values and homed state of the rows, buttons (also while open: every poll)."""
        win, device = self.win, self.device
        zs = WZ.zero_summary(win, device)
        self.lbl_summary.setText(zs.get("text", ""))
        state = "warn" if zs.get("kind") in ("custom", "unknown") else ("std" if zs.get("standard") else "off")
        if self.lbl_summary.property('zeroState') != state:
            self.lbl_summary.setProperty('zeroState', state)
            self.lbl_summary.style().unpolish(self.lbl_summary)
            self.lbl_summary.style().polish(self.lbl_summary)
        lines = [l for l in str(zs.get("detail", "")).split("\n") if l.strip()]
        rows_txt = [l for l in lines if ": 0 at machine" in l]
        other = [l for l in lines if ": 0 at machine" not in l]
        half = (len(rows_txt) + 1) // 2 if len(rows_txt) > 4 else len(rows_txt)
        self.lbl_detail[0].setText("\n".join(rows_txt[:half]))
        self.lbl_detail[1].setText("\n".join(rows_txt[half:]))
        self.lbl_detail_more.setText("\n".join(other))
        self.lbl_detail_more.setVisible(bool(other))

        st = WZ.state(win)
        for row, r in self.rows.items():
            motors = WZ.row_motors(win, device, row)
            v = WZ.row_value(win, device, row)
            r['cur'].setText("-" if v is None else f"{v:.3f}")
            homed = bool(motors) and all(st.axes.get(m, {}).get('homed') for m in motors)
            usable = homed and v is not None
            if not usable and r['cb'].isChecked():
                r['cb'].setChecked(False)
            r['cb'].setEnabled(usable)
            r['edit'].setEnabled(usable)
            _keypad_reachable(r['edit'], usable)
            r['note'].setText("" if usable else ("not homed" if v is not None else "no position"))
        ok, reason = WZ.zero_ready(win, device)
        self.btn_set.setEnabled(ok)
        self.btn_standard.setEnabled(ok and not zs.get("standard"))
        if not ok:
            tip = reason
        elif zs.get("standard"):
            tip = f"The zero is already {'the platform centre' if device == KINETIQ else 'at home (0)'}."
        else:
            tip = self._standard_text()
        self.btn_standard.setToolTip(tip)
        if not ok:
            self._message(f"Set zero is not available now: {reason}")
        elif self.lbl_message.text().startswith("Set zero is not available now"):
            self._message("")

    def _standard_text(self):
        if self.device == KINETIQ:
            c = KINETIQ_CENTRE_DOF
            return (f"Set the zero of KINETIQ back to the platform centre (LAT {c['LAT']:g}, SI {c['SI']:g}, "
                    f"A-D {c['AP']:g} mm machine).")
        return "Set the zero of DYNAMIQ back to home (0)."

    def values(self):
        """({row: value} of the ticked rows, '') or (None, why not): nothing ticked, AP with A-D, not a number."""
        ticked = [row for row, r in self.rows.items() if r['cb'].isChecked()]
        if not ticked:
            return None, "Tick at least one axis."
        if "AP" in ticked and any(m in ticked for m in ACTUATORS):
            return None, "AP sets the zero of all four actuators: tick either AP or single actuators A, B, C, D."
        out = {}
        for row in ticked:
            text = self.rows[row]['edit'].text().strip()
            x = _number(text)
            if x is None:
                return None, f"{row}: '{text}' is not a number."
            out[row] = x
        return out, ""

    # -------------------------------------------------------------------------------------- actions
    def _on_set(self):
        vals, why = self.values()
        if vals is None:
            self._message(why)
            return
        self._message("")
        if WZ.set_zero(self.win, self.device, vals):
            self.accept()
        else:
            self.refresh()                       # stays open; work_zero told the user why

    def _on_standard(self):
        if QMessageBox.question(self, "Set zero", self._standard_text() + "\n\nNothing moves: only the numbers "
                                "change.", QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            return
        if WZ.set_standard_zero(self.win, self.device):
            self.accept()
        else:
            self.refresh()

    def done(self, result):
        for r in self.rows.values():             # the touch keypad filters are children of the main window
            filt = getattr(r['edit'], '_touch_filter', None)
            if filt is not None:
                r['edit'].removeEventFilter(filt)
                filt.deleteLater()
                r['edit']._touch_filter = None
        super().done(result)
