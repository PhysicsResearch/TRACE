"""
Curve tab controls of the modern Planning tab (request H), built by tab_planning_modern.ModernPlanning.build():

1. Function: a segmented row of buttons, each with a small waveform glyph and its name, for the functions of the
   (hidden) legacy 'Function Type' combo (sin, cos, cos^2, cos^4, cos^6, constant, linear), with the Undo icon at its
   right.  A click sets combo_func_type's index, so the existing handlers run (labels, Amp. offset enabled, linear
   End Time = Start + Duration); the buttons follow the combo also when code sets it.
2. Start Time / End Time: the legacy spin boxes with a two-handle range slider between them (RangeSlider: drag a
   handle, drag the blue range to move both, keyboard arrows), range 0 .. Total duration, 0.01 s resolution as the
   boxes.  Slider and boxes stay in sync both ways (also when code sets a box with blocked signals: the slider
   follows when the box repaints its new text, and after every legacy redraw).  The slider keeps Start <= End (handles cannot cross); a typed Start past End
   (or End before Start) moves the other box when the edit is finished.  An End past the plan end (Add Curve then
   extends the plan, legacy behaviour) is shown as a hatched tail beyond the plan end.
3. Total duration (s): the plan length (last time of the plan; default plans 0 - 60 s).  Longer: rows appended as
   Add Curve extends a plan (every axis holds its last position; a trigger window running to the plan end runs to the
   new end, its explicit S0 moves to the new last row); shorter: the end is cut as the Crop dialog cuts (trigger states kept), after a
   confirmation when motion, pauses / commands or trigger windows would be lost.  One undo step per change.  The
   field follows the plan after every legacy rebuild / redraw (imports, Add Curve, Crop / Trim, Undo, Clear All,
   device switch).  Core functions: fcn_plan/fcn_duration.py.
4. Larger fonts in the Curve tab: the numbers in the boxes 16 px, the function names 15 px, labels 14 px.
5. '.' and ',' both type the decimal point in the Curve tab's number boxes (fcn_create_gui/decimal_keys.py; in a
   decimal-comma locale a typed '.' was a thousands separator).  An extension of the plan to more than twice its
   length and by more than 60 s is confirmed first (slip guard).
"""

import re

import numpy as np
from PySide6.QtCore import Qt, Signal, QRectF, QPointF, QSize, QByteArray, QObject, QEvent, QTimer
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QIcon, QPixmap
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QGridLayout, QToolButton, QLabel, QSizePolicy, QButtonGroup, QDoubleSpinBox,
    QAbstractSpinBox, QLineEdit, QFrame, QMessageBox, QLayout
)

from fcn_create_gui.tab_status_modern import QSvgRenderer, _find_layout_with

VALUE_PX = 16             # numbers in the boxes
FUNC_PX = 15              # function names
LABEL_PX = 14             # field labels
FIELD_HEIGHT = 40         # as the legacy boxes (setMinimumHeight(40))
TOTAL_DEFAULT = 60.0      # default plans 0 - 60 s (fcn_create.initialize_default_curve_data)
EXTEND_ASK_S = 60.0         # Total duration: an extension to more than twice the plan and by more than this asks

LABEL_STYLE = f"font-weight: bold; font-size: {LABEL_PX}px; background: transparent;"
CAPTION_STYLE = "font-size: 13px; color: #607d8b; background: transparent;"

FUNC_LABELS = {'sin': "sin", 'cos': "cos", 'cos^2': "cos²", 'cos^4': "cos⁴", 'cos^6': "cos⁶",
               'constant': "constant", 'linear': "linear"}
FUNC_TIPS = {
    'sin': "sin: Amplitude · sin(2π·t/Period + Phase) + Amp. offset",
    'cos': "cos: Amplitude · cos(2π·t/Period + Phase) + Amp. offset",
    'cos^2': "cos²: Amplitude · cos²(π·t/Period + Phase/2) + Amp. offset (one hump per Period)",
    'cos^4': "cos⁴: Amplitude · cos⁴(π·t/Period + Phase/2) + Amp. offset (narrower humps)",
    'cos^6': "cos⁶: Amplitude · cos⁶(π·t/Period + Phase/2) + Amp. offset (narrowest humps)",
    'constant': "constant: Amplitude + Amp. offset over Start - End",
    'linear': "linear: from Initial pos to Final pos in Duration (End Time = Start Time + Duration)",
}
FUNC_STYLE = """
    QToolButton {{
        background-color: #ffffff; color: #37474f; border: 1px solid #b0bec5;
        font-size: {px}px; font-weight: bold; padding: 2px 4px; {radius}
    }}
    QToolButton:hover {{ background-color: #e3f2fd; color: #1565c0; border: 1px solid #1565c0; }}
    QToolButton:checked {{ background-color: #1565c0; color: #ffffff; border: 1px solid #1565c0; }}
    QToolButton:checked:hover {{ background-color: #0d47a1; border: 1px solid #0d47a1; }}
    QToolButton:disabled {{ color: #b0bec5; }}
"""
_SEG_LEFT = ("border-top-left-radius: 6px; border-bottom-left-radius: 6px; "
             "border-top-right-radius: 0px; border-bottom-right-radius: 0px;")
_SEG_RIGHT = ("border-top-right-radius: 6px; border-bottom-right-radius: 6px; "
              "border-top-left-radius: 0px; border-bottom-left-radius: 0px;")
_SEG_MID = "border-radius: 0px;"
GLYPH_W, GLYPH_H = 30, 18

TOTAL_TIP = ("Total duration of the plan (s); the default plans last 60 s.\n"
             "Longer: the plan is extended up to the new end (every axis holds its last position, as Add Curve "
             "extends a plan).\n"
             "Shorter: the end of the plan is cut (as Crop); asks first when motion, pauses or trigger windows "
             "would be lost.\n"
             "One undo step per change.  Follows the plan after imports, Add Curve, Crop / Trim, Undo.")
START_TIP = "Start Time (s) of the curve.  Synced with the left handle of the slider."
END_TIP = "End Time (s) of the curve.  Synced with the right handle of the slider."
CAPTION = "drag a handle or the blue range"


# ---------------------------------------------------------------------------------------------- glyphs
def glyph_points(name, n=49):
    """(x, y) in 0..1 of the waveform glyph of a function (y up)."""
    x = np.linspace(0.0, 1.0, n)
    if name == 'sin':
        y = 0.5 + 0.5 * np.sin(2 * np.pi * 1.25 * x)
    elif name == 'cos':
        y = 0.5 + 0.5 * np.cos(2 * np.pi * 1.25 * x)
    elif name in ('cos^2', 'cos^4', 'cos^6'):
        k = int(name[-1])
        y = np.cos(2 * np.pi * x) ** k
    elif name == 'constant':
        x = np.array([0.0, 1.0])
        y = np.array([0.55, 0.55])
    elif name == 'linear':
        x = np.array([0.0, 1.0])
        y = np.array([0.0, 1.0])
    else:
        y = 0.5 + 0.5 * np.sin(2 * np.pi * x)
    return list(zip(x.tolist(), y.tolist()))


def glyph_svg(name, color):
    pts = " ".join(f"{2 + px * (GLYPH_W - 4):.2f},{GLYPH_H - 2 - py * (GLYPH_H - 4):.2f}"
                   for px, py in glyph_points(name))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {GLYPH_W} {GLYPH_H}" fill="none" '
            f'stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
            f'<polyline points="{pts}"/></svg>')


def glyph_icon(name, off='#1565c0', on='#ffffff', disabled='#b0bec5'):
    icon = QIcon()
    for scale in (1, 2):
        for col, mode, state in ((off, QIcon.Normal, QIcon.Off), (off, QIcon.Active, QIcon.Off),
                                 (on, QIcon.Normal, QIcon.On), (on, QIcon.Active, QIcon.On),
                                 (disabled, QIcon.Disabled, QIcon.Off), (disabled, QIcon.Disabled, QIcon.On)):
            pm = QPixmap(GLYPH_W * scale, GLYPH_H * scale)
            pm.fill(Qt.transparent)
            if QSvgRenderer is not None:
                r = QSvgRenderer(QByteArray(glyph_svg(name, col).encode('utf-8')))
                p = QPainter(pm)
                p.setRenderHint(QPainter.Antialiasing, True)
                r.render(p)
                p.end()
            pm.setDevicePixelRatio(scale)
            icon.addPixmap(pm, mode, state)
    return icon


# ---------------------------------------------------------------------------------------------- range slider
class RangeSlider(QWidget):
    """Two-handle slider for an interval [lo, hi] inside 0 .. maximum.

    The track shows 0 .. limit (the plan end); when a value lies past the limit the scale grows to show it and the
    part past the limit is drawn hatched.  Drag a handle to move it, the range between the handles to move both, or
    click the track to bring the nearer handle there.  Keys: Left / Right move the selected handle 0.1 s (Shift 1 s,
    Ctrl 0.01 s), Page Up / Down 1 s, Home / End to the ends, Up / Down select End / Start.
    ``valuesChanged(lo, hi)`` is emitted for user changes only (``setValues`` is silent)."""

    valuesChanged = Signal(float, float)

    HANDLE_R = 9
    TRACK_H = 6
    TRACK_Y = 15
    MARGIN = 12

    def __init__(self, parent=None, decimals=2):
        super().__init__(parent)
        self._dec = int(decimals)
        self._res = 10.0 ** -self._dec
        self._limit = TOTAL_DEFAULT
        self._lo, self._hi = 0.0, 20.0
        self._lo_min, self._hi_min = 0.0, 0.0
        self._scale = TOTAL_DEFAULT
        self._drag = None
        self._drag_off = 0.0
        self._active = 'hi'
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)
        self.setFixedHeight(FIELD_HEIGHT)
        self.setMinimumWidth(80)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self.setCursor(Qt.PointingHandCursor)
        self._update_tip()

    # ---- state
    def values(self):
        return self._lo, self._hi

    def limit(self):
        return self._limit

    def scale_max(self):
        return self._scale

    def active_handle(self):
        return self._active

    def gap(self):
        return self._res

    def setLimit(self, limit):
        limit = max(float(limit), self._res)
        if abs(limit - self._limit) > 1e-12:
            self._limit = limit
            self._rescale()
            self.update()
            self._update_tip()

    def setMinimums(self, lo_min, hi_min):
        self._lo_min, self._hi_min = float(lo_min), float(hi_min)

    def setValues(self, lo, hi):
        lo, hi = float(lo), float(hi)
        if (lo, hi) != (self._lo, self._hi):
            self._lo, self._hi = lo, hi
            self._rescale()
            self.update()
            self._update_tip()

    def _rescale(self):
        if self._drag is None:
            self._scale = max(self._limit, self._lo, self._hi, self._res)

    def _round(self, v):
        return round(float(v), self._dec)

    # ---- geometry
    def _track_left(self):
        return float(self.MARGIN)

    def _track_width(self):
        return max(1.0, float(self.width() - 2 * self.MARGIN))

    def x_of(self, v):
        return self._track_left() + self._track_width() * (float(v) / self._scale if self._scale > 0 else 0.0)

    def value_at(self, x):
        v = (float(x) - self._track_left()) / self._track_width() * self._scale
        return self._round(min(max(v, 0.0), self._scale))

    def handle_pos(self, which):
        """Centre of a handle ('lo' / 'hi') in widget coordinates (QPoint-like tuple)."""
        v = self._lo if which == 'lo' else self._hi
        return int(round(self.x_of(v))), self.TRACK_Y

    # ---- user changes
    def _set_user(self, lo, hi, which):
        lo, hi = self._round(lo), self._round(hi)
        gap = self._res
        top = self._scale
        if which == 'lo':
            lo = min(max(lo, self._lo_min, 0.0), hi - gap)
        elif which == 'hi':
            hi = max(min(hi, top), lo + gap, self._hi_min)
        else:
            width = hi - lo
            lo = min(max(lo, self._lo_min, 0.0), top - width)
            hi = lo + width
        lo, hi = self._round(lo), self._round(hi)
        if (lo, hi) != (self._lo, self._hi):
            self._lo, self._hi = lo, hi
            self.update()
            self._update_tip()
            self.valuesChanged.emit(lo, hi)

    def _pick(self, x):
        xl, xh = self.x_of(self._lo), self.x_of(self._hi)
        dl, dh = abs(x - xl), abs(x - xh)
        reach = self.HANDLE_R + 4
        if min(dl, dh) <= reach:
            if abs(dl - dh) < 1e-6:            # handles on top of each other: by the side of the click
                return 'hi' if x >= xh else 'lo'
            return 'lo' if dl < dh else 'hi'
        if min(xl, xh) < x < max(xl, xh):
            return 'range'
        return 'lo' if dl < dh else 'hi'

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton or not self.isEnabled():
            return super().mousePressEvent(event)
        x = event.position().x()
        which = self._pick(x)
        self._drag = which
        self.setFocus(Qt.MouseFocusReason)
        if which == 'range':
            self._drag_off = self.value_at(x) - self._lo
        else:
            self._active = which
            v = self.value_at(x)
            if which == 'lo':
                self._set_user(v, self._hi, 'lo')
            else:
                self._set_user(self._lo, v, 'hi')
        self.update()
        event.accept()

    def mouseMoveEvent(self, event):
        x = event.position().x()
        if self._drag is None:
            which = self._pick(x)
            want = Qt.SizeHorCursor if which in ('lo', 'hi') and min(abs(x - self.x_of(self._lo)),
                                                                     abs(x - self.x_of(self._hi))) \
                <= self.HANDLE_R + 4 else (Qt.OpenHandCursor if which == 'range' else Qt.PointingHandCursor)
            if self.cursor().shape() != want:
                self.setCursor(want)
            return super().mouseMoveEvent(event)
        v = self.value_at(x)
        if self._drag == 'lo':
            self._set_user(v, self._hi, 'lo')
        elif self._drag == 'hi':
            self._set_user(self._lo, v, 'hi')
        else:
            width = self._hi - self._lo
            lo = v - self._drag_off
            self._set_user(lo, lo + width, 'range')
        event.accept()

    def mouseReleaseEvent(self, event):
        if self._drag is not None and event.button() == Qt.LeftButton:
            self._drag = None
            self._rescale()
            self.update()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        k = event.key()
        mods = event.modifiers()
        step = 1.0 if mods & Qt.ShiftModifier else (self._res if mods & Qt.ControlModifier else 0.1)
        lo, hi = self._lo, self._hi
        a = self._active
        if k in (Qt.Key_Up, Qt.Key_Down):
            self._active = 'hi' if k == Qt.Key_Up else 'lo'
            self.update()
            self._update_tip()
            return
        if k in (Qt.Key_Left, Qt.Key_Right, Qt.Key_PageUp, Qt.Key_PageDown):
            d = step if k in (Qt.Key_Left, Qt.Key_Right) else 1.0
            d = -d if k in (Qt.Key_Left, Qt.Key_PageDown) else d
            if a == 'lo':
                self._set_user(lo + d, hi, 'lo')
            else:
                self._set_user(lo, hi + d, 'hi')
            return
        if k in (Qt.Key_Home, Qt.Key_End):
            if a == 'lo':
                self._set_user(0.0 if k == Qt.Key_Home else hi, hi, 'lo')
            else:
                self._set_user(lo, lo if k == Qt.Key_Home else self._limit, 'hi')
            return
        super().keyPressEvent(event)

    def focusInEvent(self, event):
        super().focusInEvent(event)
        self.update()

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self.update()

    def changeEvent(self, event):
        super().changeEvent(event)
        self.update()

    # ---- tooltip
    def _update_tip(self):
        lo, hi = self._lo, self._hi
        tip = (f"Curve interval: Start {lo:.2f} s – End {hi:.2f} s (plan 0 – {self._limit:.2f} s).\n"
               "Drag a handle to move Start or End, drag the blue range to move both; the boxes follow.\n"
               "Keys: ← / → move the selected handle 0.1 s (Shift 1 s, Ctrl 0.01 s), ↑ / ↓ select End / Start.")
        if max(lo, hi) > self._limit + 1e-9:
            tip += "\nHatched: past the plan end (Add Curve extends the plan)."
        if self.toolTip() != tip:
            self.setToolTip(tip)

    # ---- painting
    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        en = self.isEnabled()
        left, width = self._track_left(), self._track_width()
        y = self.TRACK_Y
        th = self.TRACK_H
        track = QRectF(left, y - th / 2.0, width, th)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor('#e3e8ec'))
        p.drawRoundedRect(track, th / 2.0, th / 2.0)
        x_lim = self.x_of(self._limit)
        if x_lim < left + width - 0.5:          # past the plan end: hatched
            tail = QRectF(x_lim, y - th / 2.0, left + width - x_lim, th)
            p.setBrush(QColor('#f5f5f5'))
            p.drawRect(tail)
            p.setBrush(QBrush(QColor('#90a4ae'), Qt.BDiagPattern))
            p.drawRect(tail)
            p.setPen(QPen(QColor('#78909c'), 1.5))
            p.drawLine(QPointF(x_lim, y - th), QPointF(x_lim, y + th))
            p.setPen(Qt.NoPen)
        xl, xh = self.x_of(min(self._lo, self._hi)), self.x_of(max(self._lo, self._hi))
        p.setBrush(QColor('#1565c0' if en else '#b0bec5'))
        p.drawRoundedRect(QRectF(xl, y - th / 2.0, max(xh - xl, 1.0), th), th / 2.0, th / 2.0)
        # scale labels
        f = QFont(self.font())
        f.setPixelSize(11)
        f.setBold(False)
        p.setFont(f)
        p.setPen(QColor('#78909c'))
        lab_top = y + self.HANDLE_R + 1
        lab_h = self.height() - lab_top
        p.drawText(QRectF(left - self.MARGIN + 2, lab_top, 60, lab_h), Qt.AlignLeft | Qt.AlignVCenter, "0 s")
        end_txt = f"{self._limit:g} s"
        p.drawText(QRectF(x_lim - 80, lab_top, 80 + (self.MARGIN - 2 if x_lim >= left + width - 0.5 else 0), lab_h),
                   Qt.AlignRight | Qt.AlignVCenter, end_txt)
        # handles
        focused = self.hasFocus()
        for which, v in (('lo', self._lo), ('hi', self._hi)):
            cx = self.x_of(v)
            active = focused and which == self._active
            if active:
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(21, 101, 192, 50))
                p.drawEllipse(QPointF(cx, y), self.HANDLE_R + 4, self.HANDLE_R + 4)
            p.setBrush(QColor('#ffffff'))
            p.setPen(QPen(QColor(('#0d47a1' if active else '#1565c0') if en else '#b0bec5'), 3 if active else 2))
            p.drawEllipse(QPointF(cx, y), self.HANDLE_R - 1, self.HANDLE_R - 1)
        p.end()


# ---------------------------------------------------------------------------------------------- controller
class _BoxWatcher(QObject):
    """Start / End box set by code with blocked signals: the box repaints its new text, the slider follows."""

    def __init__(self, box, ctl):
        super().__init__(box)
        self._ctl = ctl
        box.installEventFilter(self)
        box.lineEdit().installEventFilter(self)

    def eventFilter(self, obj, event):
        if event.type() in (QEvent.Paint, QEvent.Show) and self._ctl.slider_out_of_sync():
            QTimer.singleShot(0, self._ctl.sync_slider)
        return False


def _grid_take(grid, row, col):
    """Takes the item at (row, col) out of a QGridLayout: (layout or widget, (rowspan, colspan)) or (None, None)."""
    for i in range(grid.count()):
        r, c, rs, cs = grid.getItemPosition(i)
        if (r, c) == (row, col):
            item = grid.itemAt(i)
            lay, wd = item.layout(), item.widget()
            grid.takeAt(i)
            return (lay if lay is not None else wd), (rs, cs)
    return None, None


def _bigger_font(widget, px, weight=QFont.DemiBold):
    f = QFont(widget.font())
    f.setPixelSize(px)
    f.setWeight(weight)
    widget.setFont(f)


class CurveControls:
    """Function selector, Start / End range slider, Total duration and fonts of the Curve tab (one per window)."""

    def __init__(self, pm):
        self.pm = pm
        self.win = pm.win
        self._guard = False
        self._keep = []                     # Python wrappers of re-parented layouts
        self.func_buttons = []
        self.slider = None
        self.total_spin = None

    # ------------------------------------------------------------------ build
    def build(self):
        self._build_function_selector()
        self._build_time_range()
        self.apply_fonts()
        self._install_decimal_keys()
        self.after_legacy_update()

    def _install_decimal_keys(self):
        """'.' and ',' both type the decimal point in the Curve tab's number boxes (decimal-comma locales read a
        typed '.' as a thousands separator: '70.25' was 7025 s)."""
        from fcn_create_gui.decimal_keys import install_decimal_keys_all
        w = self.win
        boxes = [w.input_start_time, w.input_end_time, self.total_spin] + list(getattr(self, 'value_boxes', []))
        self.decimal_boxes = install_decimal_keys_all(dict.fromkeys(b for b in boxes if b is not None))

    def _grid(self):
        return self.pm._grid_inputs()

    # ---- 1. function selector
    def _build_function_selector(self):
        w = self.win
        combo = w.combo_func_type
        row = combo.parentWidget()
        h = row.layout() if row is not None and row.objectName() == 'pmFuncRow' else None
        if h is None:
            lay, idx = _find_layout_with(w.groupBox_BrCv_createCurve.layout(), combo)
            if lay is None:
                return
            h, row = lay, combo.parentWidget()
        self.func_box = QWidget(row)
        self.func_box.setObjectName('pmFuncSelector')
        fl = QHBoxLayout(self.func_box)
        fl.setContentsMargins(0, 0, 0, 0)
        fl.setSpacing(0)
        self.func_group = QButtonGroup(self.func_box)
        self.func_group.setExclusive(True)
        n = combo.count()
        for i in range(n):
            key = combo.itemText(i)
            b = QToolButton(self.func_box)
            b.setText(FUNC_LABELS.get(key, key))
            b.setIcon(glyph_icon(key))
            b.setIconSize(QSize(GLYPH_W, GLYPH_H))
            b.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            b.setCheckable(True)
            b.setFixedHeight(FIELD_HEIGHT)
            b.setMinimumWidth(0)
            b.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
            b.setCursor(Qt.PointingHandCursor)
            radius = _SEG_LEFT if i == 0 else (_SEG_RIGHT if i == n - 1 else _SEG_MID)
            b.setStyleSheet(FUNC_STYLE.format(px=FUNC_PX, radius=radius))
            b.setToolTip(FUNC_TIPS.get(key, key) + "\nClick to select this function for Add Curve.")
            b.setProperty('func_key', key)
            b.clicked.connect(lambda _c=False, i=i: self.on_function_clicked(i))
            self.func_group.addButton(b, i)
            fl.addWidget(b, 1)
            self.func_buttons.append(b)
        h.insertWidget(0, self.func_box, 1)
        combo.setVisible(False)               # stays the source of truth (hidden)
        combo.currentIndexChanged.connect(lambda _i: (self.sync_function(), self.sync_slider()))  # linear: End
        # the Function field spans the columns 1 - 2 of row 0 (column 2 was empty)
        grid = self._grid()
        if grid is not None:
            item, span = _grid_take(grid, 0, 1)
            if item is not None:
                if isinstance(item, QLayout):
                    grid.addLayout(item, 0, 1, 1, 2)
                else:
                    grid.addWidget(item, 0, 1, 1, 2)
                self._keep.append(item)
        for lab in w.groupBox_BrCv_createCurve.findChildren(QLabel):
            if lab.text().strip() == "Function Type:":
                self.func_label = lab
                lab.setToolTip("Function of the curve that Add Curve writes (hover a button for its formula).")
                break

    def on_function_clicked(self, index):
        combo = self.win.combo_func_type
        if combo.currentIndex() != index:
            combo.setCurrentIndex(index)      # the existing currentTextChanged handlers run
        self.sync_function()

    def sync_function(self):
        try:
            cur = self.win.combo_func_type.currentIndex()
            for i, b in enumerate(self.func_buttons):
                if b.isChecked() != (i == cur):
                    b.blockSignals(True)
                    b.setChecked(i == cur)
                    b.blockSignals(False)
            en = self.win.combo_func_type.isEnabled()
            if self.func_box.isEnabled() != en:
                self.func_box.setEnabled(en)
        except RuntimeError:
            pass

    # ---- 2./3. Start | slider | End | Total duration
    def _build_time_range(self):
        w = self.win
        grid = self._grid()
        start, end = w.input_start_time, w.input_end_time
        if grid is None:
            return
        s_lay, _ = _grid_take(grid, 2, 1)
        e_lay, _ = _grid_take(grid, 2, 2)
        labels = {}
        for key, lay, sp in (('start', s_lay, start), ('end', e_lay, end)):
            if lay is None or isinstance(lay, QWidget):
                continue
            for i in range(lay.count()):
                wd = lay.itemAt(i).widget()
                if isinstance(wd, QLabel):
                    labels[key] = wd
            if key in labels:
                lay.removeWidget(labels[key])
            lay.removeWidget(sp)
            self._keep.append(lay)
        gb = w.groupBox_BrCv_createCurve
        self.time_box = QWidget(gb)
        self.time_box.setObjectName('pmTimeRange')
        tg = QGridLayout(self.time_box)
        tg.setContentsMargins(0, 0, 0, 0)
        tg.setHorizontalSpacing(10)
        tg.setVerticalSpacing(2)
        self.start_label = labels.get('start') or QLabel("Start Time (s):", self.time_box)
        self.end_label = labels.get('end') or QLabel("End Time (s):", self.time_box)
        self.caption = QLabel(CAPTION, self.time_box)
        self.caption.setStyleSheet(CAPTION_STYLE)
        self.caption.setAlignment(Qt.AlignHCenter | Qt.AlignBottom)
        self.caption.setMinimumWidth(0)
        self.caption.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)   # never widens the column
        self.total_label = QLabel("Total duration (s):", self.time_box)
        self.total_label.setStyleSheet(LABEL_STYLE)
        self.total_label.setToolTip(TOTAL_TIP)
        self.slider = RangeSlider(self.time_box, decimals=max(start.decimals(), end.decimals()))
        self.slider.setObjectName('pmTimeSlider')
        self.total_spin = QDoubleSpinBox(self.time_box)
        self.total_spin.setObjectName('pmTotalDuration')
        self.total_spin.setDecimals(2)
        self.total_spin.setRange(0.1, max(end.maximum(), 10000.0))
        self.total_spin.setSingleStep(1.0)
        self.total_spin.setKeyboardTracking(False)      # applied on Enter / focus out / arrow steps
        self.total_spin.setValue(TOTAL_DEFAULT)
        self.total_spin.setMinimumHeight(FIELD_HEIGHT)
        self.total_spin.setToolTip(TOTAL_TIP)
        sep = QFrame(self.time_box)
        sep.setFrameShape(QFrame.VLine)
        sep.setFixedWidth(9)
        sep.setStyleSheet("QFrame { color: #cfd8dc; background: transparent; }")
        start.setToolTip(START_TIP)
        end.setToolTip(END_TIP)
        for lab in (self.start_label, self.end_label, self.total_label):
            lab.setMinimumWidth(0)                # the labels never widen the field columns (3 equal columns)
            lab.setSizePolicy(QSizePolicy.Ignored, lab.sizePolicy().verticalPolicy())
        for sp in (start, end, self.total_spin):
            sp.setMinimumWidth(0)
            sp.setSizePolicy(QSizePolicy.Ignored, sp.sizePolicy().verticalPolicy())
        tg.addWidget(self.start_label, 0, 0)
        tg.addWidget(self.caption, 0, 1)
        tg.addWidget(self.end_label, 0, 2)
        tg.addWidget(self.total_label, 0, 4)
        tg.addWidget(start, 1, 0)
        tg.addWidget(self.slider, 1, 1)
        tg.addWidget(end, 1, 2)
        tg.addWidget(sep, 0, 3, 2, 1)
        tg.addWidget(self.total_spin, 1, 4)
        for c, s in ((0, 2), (1, 5), (2, 2), (4, 2)):
            tg.setColumnStretch(c, s)
        grid.addWidget(self.time_box, 2, 1, 1, 2)
        # boxes -> slider: valueChanged (typed / set with signals); a value set with blocked signals (linear End =
        # Start + Duration, Add Curve's transit shift) emits nothing - not even the line edit's textChanged - but the
        # box repaints its new text: _BoxWatcher syncs the slider then (and every legacy redraw does, after_legacy_update)
        self._box_watch = []
        for sp in (start, end):
            sp.valueChanged.connect(lambda _v: self.sync_slider())
            self._box_watch.append(_BoxWatcher(sp, self))
        start.editingFinished.connect(lambda: self._enforce_order('start'))
        end.editingFinished.connect(lambda: self._enforce_order('end'))
        # slider -> boxes
        self.slider.valuesChanged.connect(self.on_slider_changed)
        # Total duration -> plan
        self.total_spin.valueChanged.connect(self.on_total_changed)

    # ---- sync
    def slider_out_of_sync(self):
        try:
            return self.slider is not None and self.slider.values() != (self.win.input_start_time.value(),
                                                                         self.win.input_end_time.value())
        except RuntimeError:
            return False

    def sync_slider(self):
        if self.slider is None:
            return
        try:
            w = self.win
            self.slider.setMinimums(w.input_start_time.minimum(), w.input_end_time.minimum())
            self.slider.setValues(w.input_start_time.value(), w.input_end_time.value())
        except RuntimeError:
            pass

    def on_slider_changed(self, lo, hi):
        w = self.win
        start, end = w.input_start_time, w.input_end_time
        self._guard = True
        try:
            if abs(start.value() - lo) > 1e-9:
                start.setValue(lo)            # the legacy handlers run (linear: End = Start + Duration)
            if abs(end.value() - hi) > 1e-9:
                end.setValue(hi)              # (linear: Duration = End - Start)
        finally:
            self._guard = False
        self.sync_slider()

    def _enforce_order(self, which):
        """A typed Start past End (or End before Start): the other box moves when the edit is finished."""
        if self._guard or self.slider is None:
            return
        w = self.win
        start, end = w.input_start_time, w.input_end_time
        gap = self.slider.gap()
        lo, hi = start.value(), end.value()
        if hi - lo >= gap - 1e-9:
            return
        self._guard = True
        try:
            if which == 'start':
                end.setValue(min(end.maximum(), round(lo + gap, end.decimals())))
            else:
                start.setValue(max(start.minimum(), round(hi - gap, start.decimals())))
        finally:
            self._guard = False
        self.sync_slider()

    def plan_total(self):
        from fcn_plan.fcn_duration import plan_end
        df = getattr(self.win, 'dfEdit', None)
        return plan_end(df) if df is not None and len(df) else None

    def sync_total(self):
        if self.total_spin is None:
            return
        try:
            t = self.plan_total()
            if t is None:
                return
            v = round(t, self.total_spin.decimals())
            if abs(self.total_spin.value() - v) > 1e-9:
                self.total_spin.blockSignals(True)
                self.total_spin.setValue(v)
                self.total_spin.blockSignals(False)
            self.slider.setLimit(round(t, self.total_spin.decimals()))
        except RuntimeError:
            pass

    def after_legacy_update(self):
        self.sync_function()
        self.sync_total()
        self.sync_slider()

    # ---- Total duration -> plan
    def on_total_changed(self, value):
        if self._guard:
            return
        try:
            self.apply_total(value)
        except RuntimeError:
            pass

    def apply_total(self, value):
        from fcn_plan import fcn_create as fc
        from fcn_plan.fcn_duration import plan_end, extend_plan, crop_plan_end, cut_report, cut_report_text
        from fcn_create_gui.tab_planning_trigger import _trg_status
        w = self.win
        df = getattr(w, 'dfEdit', None)
        if df is None or len(df) == 0:
            fc.initialize_default_curve_data(w)
            df = w.dfEdit
        cur = plan_end(df)
        new = round(float(value), 2)
        if abs(new - cur) < 0.005:
            self.sync_total()
            return False
        device = w.combo_device.currentText()
        if new > cur:
            if new > 2.0 * cur and new - cur > EXTEND_ASK_S:
                # a slip guard (e.g. a mistyped extra digit): a large extension is confirmed first
                ans = QMessageBox.question(
                    w, "Extend the plan",
                    f"Total duration {cur:.2f} s → {new:.2f} s extends the plan by {new - cur:.2f} s "
                    f"(every axis holds its last position).\n\nExtend it?  (Undo restores it.)",
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                if ans != QMessageBox.Yes:
                    self.sync_total()
                    _trg_status(w, f"Total duration: kept {cur:.2f} s (not extended).", "warn")
                    return False
            df2 = extend_plan(df, new)
            verb = "extended"
        else:
            what = cut_report_text(cut_report(df, new))
            if what:
                ans = QMessageBox.question(
                    w, "Shorten the plan",
                    f"Total duration {cur:.2f} s → {new:.2f} s cuts the end of the plan after {new:.2f} s:\n"
                    f"{what}.\n\nCut it?  (Undo restores it.)",
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                if ans != QMessageBox.Yes:
                    self.sync_total()
                    _trg_status(w, f"Total duration: kept {cur:.2f} s (nothing cut).", "warn")
                    return False
            df2 = crop_plan_end(df, new)
            if df2 is None:
                self.sync_total()
                return False
            verb = "shortened"
        fc.push_curve_state(w)                # one undo step
        w.dfEdit = fc.bake_plan_steps(w, df2, device)
        if device == "Lung Phantom":
            w.dfEdit_lung_phantom = w.dfEdit
        elif device == "Motion Platform":
            w.dfEdit = fc.compute_motion_platform_actuators(w, w.dfEdit)
            w.dfEdit_motion_platform = w.dfEdit
        else:
            w.dfEdit_other = w.dfEdit
        fc.loadTable_create(w, w.dfEdit)
        fc.trigger_plot_update(w)
        total = plan_end(w.dfEdit)
        self.sync_total()
        self._clamp_interval(total)
        _trg_status(w, f"Total duration: plan {verb} to {total:.2f} s (Undo restores {cur:.2f} s).", "ok")
        return True

    def _clamp_interval(self, total):
        """Start / End inside 0 .. total after the user changed Total duration."""
        w = self.win
        start, end = w.input_start_time, w.input_end_time
        gap = self.slider.gap() if self.slider is not None else 0.01
        self._guard = True
        try:
            if start.value() > total - gap:
                start.setValue(max(start.minimum(), round(total - gap, start.decimals())))
            if end.value() > total:
                end.setValue(max(end.minimum(), round(total, end.decimals())))
        finally:
            self._guard = False
        self.sync_slider()

    # ---- 4. fonts
    def apply_fonts(self):
        w = self.win
        gb = w.groupBox_BrCv_createCurve
        boxes = list(gb.findChildren(QAbstractSpinBox))
        for name in ('trg_per_period', 'trg_per_duration', 'trg_per_offset', 'input_wait_rad_time'):
            sp = getattr(w, name, None)
            if sp is not None and sp not in boxes:
                boxes.append(sp)
        rng = getattr(w, 'trg_per_range', None)
        if isinstance(rng, dict):
            for key in ('r0', 'r1'):
                sp = rng.get(key)
                if sp is not None and sp not in boxes:
                    boxes.append(sp)
        for sp in boxes:
            _bigger_font(sp, VALUE_PX)
        for le in gb.findChildren(QLineEdit):
            if isinstance(le.parentWidget(), QAbstractSpinBox):
                continue
            ss = le.styleSheet()
            if 'font-size' in ss:
                ss = re.sub(r'font-size\s*:\s*\d+px', f'font-size: {VALUE_PX}px', ss)
                ss = ss.replace('font-weight: bold', 'font-weight: 600')
                le.setStyleSheet(ss)
            else:
                _bigger_font(le, VALUE_PX)
        self.value_boxes = boxes
