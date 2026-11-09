"""
Display names: the interface shows the product names, the code keeps its own words.

    Lung Phantom, lung phantom, Phantom, Lung, LungPhan   ->  DYNAMIQ
    Motion Platform, Platform, platform                    ->  KINETIQ
    the 'TRACE' Duet IP preset (the platform's board)      ->  KINETIQ

Only what is drawn changes.  The code compares and stores 'Lung Phantom' / 'Motion Platform' everywhere (device
combo, G-code and log headers, importers), so:
  - labels / buttons / group boxes: the shown text is mapped; text() / title() still return the original text to
    the code (as long as the widget shows the mapped form of it);
  - combo boxes keep their items: only the closed box and the popup list paint the mapped text;
  - tab titles, tool tips, window titles, placeholders and message boxes are mapped (display only);
  - file paths / file names are never mapped (a folder called 'Platform tests' stays as it is).
Hooked by prepare_display_names() (before the window is built) and sweep_display_names(root) (after).
"""
import re

from PySide6.QtCore import QEvent, QObject
from PySide6.QtWidgets import (QAbstractButton, QCheckBox, QComboBox, QGroupBox, QLabel, QLineEdit, QMessageBox,
                               QPushButton, QRadioButton, QStyle, QStyledItemDelegate, QStyleOptionComboBox,
                               QStylePainter, QTabBar, QTabWidget, QWidget)

PHANTOM_NAME = "DYNAMIQ"
PLATFORM_NAME = "KINETIQ"

_RULES = [
    (re.compile(r"\bLung[ -]?Phantoms?\b", re.IGNORECASE), PHANTOM_NAME),
    (re.compile(r"\bLungPhan\b", re.IGNORECASE), PHANTOM_NAME),
    (re.compile(r"\bMotion[ -]?Platforms?\b", re.IGNORECASE), PLATFORM_NAME),
    (re.compile(r"\bPlatforms?\b", re.IGNORECASE), PLATFORM_NAME),
    (re.compile(r"\bPhantoms?\b", re.IGNORECASE), PHANTOM_NAME),
    (re.compile(r"\bLung\b"), PHANTOM_NAME),            # 'Lung' as a device word; 'each lung' (anatomy) stays
    (re.compile(r"\bLUNG\b"), PHANTOM_NAME),
]
_EXACT = {"TRACE": PLATFORM_NAME}                       # the IP preset button of the platform's Duet
_PATHLIKE = re.compile(r"[A-Za-z]:[\\/]|[\\/][^\s\\/]+[\\/]|\w\.(gcode|g|nc|csv|txt|json|vxp|png|pdf|svg)\b",
                       re.IGNORECASE)
_cache = {}
_ORIG = "dn_original_text"


def display_text(text):
    """The text as the interface shows it (cached)."""
    if not isinstance(text, str) or not text:
        return text
    out = _cache.get(text)
    if out is None:
        if text.strip() in _EXACT:
            out = text.replace(text.strip(), _EXACT[text.strip()])
        elif _PATHLIKE.search(text):
            out = text
        else:
            out = text
            for rx, name in _RULES:
                out = rx.sub(name, out)
            out = re.sub(rf"\b({PHANTOM_NAME}|{PLATFORM_NAME})( \1\b)+", r"\1", out)   # 'Lung Phantom phantom'
        if len(_cache) < 20000:
            _cache[text] = out
    return out


# ---------------------------------------------------------------------------------------------------------------
# shims: shown text mapped, original text returned to the code
# ---------------------------------------------------------------------------------------------------------------
_orig = {}


def _wrap_text_holder(cls, setter, getter):
    o_set, o_get = getattr(cls, setter), getattr(cls, getter)
    _orig[(cls, setter)] = o_set
    _orig[(cls, getter)] = o_get

    def set_text(self, text, *a):
        if isinstance(text, str):
            shown = display_text(text)
            try:
                self.setProperty(_ORIG, text if shown != text else None)
            except RuntimeError:
                pass
            text = shown
        return o_set(self, text, *a)

    def get_text(self):
        shown = o_get(self)
        try:
            orig = self.property(_ORIG)
        except RuntimeError:
            return shown
        if isinstance(orig, str) and orig and display_text(orig) == shown:
            return orig
        return shown

    setattr(cls, setter, set_text)
    setattr(cls, getter, get_text)


def _wrap_init(cls, getter_cls, getter, setter):
    o_init = cls.__init__
    _orig[(cls, '__init__')] = o_init

    def init(self, *a, **k):
        o_init(self, *a, **k)
        try:
            t = _orig[(getter_cls, getter)](self)
            if isinstance(t, str) and t and display_text(t) != t:
                getattr(self, setter)(t)
        except (RuntimeError, KeyError):
            pass

    cls.__init__ = init


def _wrap_display_only(cls, name, text_index):
    o = getattr(cls, name)
    _orig[(cls, name)] = o

    def f(self, *a):
        a = list(a)
        for i in ([text_index] if isinstance(text_index, int) else text_index):
            if i < len(a) and isinstance(a[i], str):
                a[i] = display_text(a[i])
        return o(self, *a)

    setattr(cls, name, f)


def _wrap_static_box(name):
    o = getattr(QMessageBox, name)
    _orig[(QMessageBox, name)] = o

    def f(*a, **k):
        a = [display_text(x) if isinstance(x, str) else x for x in a]
        k = {kk: (display_text(v) if isinstance(v, str) else v) for kk, v in k.items()}
        return o(*a, **k)

    setattr(QMessageBox, name, staticmethod(f))


# ---------------------------------------------------------------------------------------------------------------
# combo boxes: items unchanged, painted mapped
# ---------------------------------------------------------------------------------------------------------------
class _MappedItemDelegate(QStyledItemDelegate):
    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        option.text = display_text(option.text)


class _ComboPainter(QObject):
    def eventFilter(self, combo, ev):
        if ev.type() == QEvent.Paint and isinstance(combo, QComboBox) and not combo.isEditable():
            opt = QStyleOptionComboBox()
            combo.initStyleOption(opt)
            shown = display_text(opt.currentText)
            if shown == opt.currentText:
                return False
            opt.currentText = shown
            p = QStylePainter(combo)
            p.drawComplexControl(QStyle.CC_ComboBox, opt)
            p.drawControl(QStyle.CE_ComboBoxLabel, opt)
            p.end()
            return True
        return False


_combo_painter = None


def map_combo(combo):
    """Shows a combo's items with the display names (items and currentText() unchanged).  Idempotent."""
    global _combo_painter
    try:
        if combo.property("dn_mapped"):
            return
        if not any(display_text(combo.itemText(i)) != combo.itemText(i) for i in range(combo.count())):
            return
        if _combo_painter is None:
            _combo_painter = _ComboPainter()
        combo.installEventFilter(_combo_painter)
        combo.setItemDelegate(_MappedItemDelegate(combo))
        combo.setProperty("dn_mapped", True)
        combo.update()
    except RuntimeError:
        pass


def _wrap_combo_add(name):
    o = getattr(QComboBox, name)
    _orig[(QComboBox, name)] = o

    def f(self, *a, **k):
        r = o(self, *a, **k)
        map_combo(self)
        return r

    setattr(QComboBox, name, f)


# ---------------------------------------------------------------------------------------------------------------
_prepared = False


def prepare_display_names():
    """Before the main window is built (safe to call more than once)."""
    global _prepared
    if _prepared:
        return
    _prepared = True
    _wrap_text_holder(QLabel, 'setText', 'text')
    _wrap_text_holder(QAbstractButton, 'setText', 'text')
    _wrap_text_holder(QGroupBox, 'setTitle', 'title')
    _wrap_init(QLabel, QLabel, 'text', 'setText')
    for cls in (QPushButton, QCheckBox, QRadioButton):
        _wrap_init(cls, QAbstractButton, 'text', 'setText')
    _wrap_init(QGroupBox, QGroupBox, 'title', 'setTitle')
    _wrap_display_only(QTabWidget, 'setTabText', 1)
    _wrap_display_only(QTabBar, 'setTabText', 1)
    _wrap_display_only(QWidget, 'setToolTip', 0)
    _wrap_display_only(QWidget, 'setWindowTitle', 0)
    _wrap_display_only(QLineEdit, 'setPlaceholderText', 0)
    _wrap_display_only(QMessageBox, 'setText', 0)
    _wrap_display_only(QMessageBox, 'setInformativeText', 0)
    for name in ('information', 'warning', 'critical', 'question', 'about'):
        _wrap_static_box(name)
    for name in ('addItem', 'addItems', 'insertItem', 'insertItems', 'setItemText'):
        _wrap_combo_add(name)


def _map_tabs(bar):
    for i in range(bar.count()):
        t = bar.tabText(i)
        if display_text(t) != t:
            _orig[(QTabBar, 'setTabText')](bar, i, display_text(t))


def sweep_display_names(root):
    """Widgets whose text was set by Qt itself (constructors, .ui, tabs added with addTab): map them once."""
    if root is None:
        return
    for w in [root] + root.findChildren(QWidget):
        try:
            if isinstance(w, (QLabel, QAbstractButton)):
                t = _orig[(QLabel, 'text')](w) if isinstance(w, QLabel) else _orig[(QAbstractButton, 'text')](w)
                if display_text(t) != t:
                    w.setText(t)
            elif isinstance(w, QGroupBox):
                t = _orig[(QGroupBox, 'title')](w)
                if display_text(t) != t:
                    w.setTitle(t)
            elif isinstance(w, QTabBar):
                _map_tabs(w)
            elif isinstance(w, QComboBox):
                map_combo(w)
            tip = w.toolTip()
            if tip and display_text(tip) != tip:
                _orig[(QWidget, 'setToolTip')](w, display_text(tip))
        except (RuntimeError, KeyError):
            continue


def install_display_names(window):
    """Sweeps the window now and each main tab when it is shown (pages that build their widgets late)."""
    prepare_display_names()
    sweep_display_names(window)
    tw = getattr(window, 'tabModules', None)
    if tw is not None and not getattr(window, '_dn_tab_hook', False):
        tw.currentChanged.connect(lambda _i, t=tw: sweep_display_names(t.currentWidget()))
        window._dn_tab_hook = True
