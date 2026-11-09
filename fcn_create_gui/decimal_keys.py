"""
Decimal point / decimal comma in the Planning number boxes (fix for the decimal-comma locale, e.g. en_NL).

In a locale whose decimal point is ',' a QDoubleSpinBox reads '.' as a thousands (group) separator, so a typed
'70.25' became 7025 (and '15.5' End Time 155).  ``install_decimal_keys(box)`` makes both keys decimal points for
one box:

- a typed '.' or ',' (also from the keypad) that differs from the box locale's decimal point is replaced by that
  decimal point before the box sees it ('70.25' -> 70,25);
- a pasted number (Ctrl+V / Shift+Insert) gets the same treatment ('70.25' pasted -> 70,25);
- the box locale omits group separators (the displayed value never shows one).

The locale's own decimal point and the displayed text are unchanged (values stay '70,25' in en_NL).
"""

from PySide6.QtCore import QObject, QEvent, Qt, QCoreApplication, QLocale
from PySide6.QtGui import QKeyEvent, QKeySequence, QGuiApplication
from PySide6.QtWidgets import QDoubleSpinBox

_KEY_OF = {'.': Qt.Key_Period, ',': Qt.Key_Comma}


class _DecimalKeyFilter(QObject):
    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress:
            if event.matches(QKeySequence.Paste):
                return self._paste()
            txt = event.text()
            if txt in _KEY_OF:
                box = self.parent()
                try:
                    dp = box.locale().decimalPoint()
                except RuntimeError:
                    return False
                if dp and txt != dp and dp in _KEY_OF:
                    ev = QKeyEvent(QEvent.KeyPress, _KEY_OF[dp], event.modifiers(), dp,
                                   event.isAutoRepeat(), event.count())
                    QCoreApplication.sendEvent(obj, ev)
                    return True
        return False

    def _paste(self):
        box = self.parent()
        try:
            dp = box.locale().decimalPoint()
            txt = (QGuiApplication.clipboard().text() or "").strip()
        except RuntimeError:
            return False
        other = {'.': ',', ',': '.'}.get(dp)
        if not txt or other is None or other not in txt or dp in txt:
            return False                       # nothing to convert: the box pastes as usual
        box.lineEdit().insert(txt.replace(other, dp))
        return True


def install_decimal_keys(box):
    """'.' and ',' both type the decimal point of ``box`` (a QDoubleSpinBox); idempotent.  Returns the filter."""
    if not isinstance(box, QDoubleSpinBox):
        return None
    f = getattr(box, '_pm_decimal_keys', None)
    if f is not None:
        return f
    loc = QLocale(box.locale())
    loc.setNumberOptions(loc.numberOptions() | QLocale.OmitGroupSeparator)
    box.setLocale(loc)
    f = _DecimalKeyFilter(box)
    box.installEventFilter(f)
    box.lineEdit().installEventFilter(f)
    box._pm_decimal_keys = f
    return f


def install_decimal_keys_all(widgets):
    """install_decimal_keys on every QDoubleSpinBox in ``widgets`` (an iterable); returns the boxes handled."""
    done = []
    for b in widgets:
        if install_decimal_keys(b) is not None:
            done.append(b)
    return done
