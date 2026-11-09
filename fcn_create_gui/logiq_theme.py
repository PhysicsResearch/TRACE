"""
LogIQ theme: moves the whole app toward the website palette (olive greens, light olive shading, dark olive
instead of black) without editing the existing pages.

How it works (two hooks in Launch_ImGUI.py):
  prepare_logiq_theme()          before the main window is built:
      - QWidget.setStyleSheet / QApplication.setStyleSheet are wrapped: every stylesheet the app sets, now or
        later (pills, toggles, console light / dark ...), has its colours remapped with COLOR_MAP;
      - the modern pages' module constants, default arguments and QColor (painted sliders / icons) are remapped;
      - the application palette (selection, check boxes, tool tips, window) becomes olive.
  apply_logiq_theme(window)      after it is built: sweeps the existing widgets once, restores the original colours
      of axis widgets (see below) and adds the LogIQ word mark next to the logo; product names on screen
      (DYNAMIQ / KINETIQ, see display_names.py).

What keeps its colour (not in COLOR_MAP or excluded):
  - reds (emergency stop, not homed, delete, errors), oranges / ambers (pause, warnings), browns, white / black;
  - axis buttons: pills / check boxes whose text names an axis (X, "Show 'a" ...) and that are drawn in that
    axis' colour: they match the plot lines, so they are never remapped;
  - plots (matplotlib colours are not stylesheets) and the colour constants of plot lines / trigger windows.
"""
import re
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QAbstractButton, QApplication, QHBoxLayout, QLabel, QWidget

APP_NAME = "LogIQ"

# ---------------------------------------------------------------------------------------------------------------
# Palette (from the website: dark olive text, olive / sage greens, very light olive shading)
# ---------------------------------------------------------------------------------------------------------------
OLIVE_TEXT = "#262d23"
OLIVE_DARK = "#354530"
OLIVE = "#4b6143"          # primary (was blue #1565c0)
OLIVE_MID = "#5f7a55"
SAGE = "#7e9470"
SAGE_LIGHT = "#bccbad"
SAGE_PALE = "#d6e0ca"
OLIVE_SHADE = "#e9eee3"    # the regions that were shaded grey
OLIVE_TINT = "#f4f6f0"
CONSOLE_DARK = "#1f271c"   # dark mode: dark olive instead of black

# old colour (lower case) -> new colour.  Targets must never be keys (the remap is applied to already remapped
# sheets, e.g. a sheet read back with styleSheet() and set again): checked at import.
COLOR_MAP = {
    # blues -> olive greens (primary buttons, selections, tab underline, links)
    "#1565c0": OLIVE, "#1976d2": "#56704c", "#0d47a1": OLIVE_DARK, "#1e88e5": OLIVE_MID, "#2196f3": "#6b8660",
    "#42a5f5": "#8aa078", "#64b5f6": "#9db08a", "#90caf9": SAGE_LIGHT, "#bbdefb": SAGE_PALE, "#e3f2fd": "#e8eee0",
    "#f1f8fe": "#f3f6ef", "#0288d1": "#4f7a70", "#0277bd": "#456b62", "#01579b": "#3d5036", "#1a73e8": OLIVE,
    "#0a3875": "#2f3d2b", "#264f78": "#3f5338", "#29b6f6": "#8aa078", "blue": OLIVE,
    # cyan / teal -> sage teal
    "#e0f7fa": "#e8efe2", "#80deea": "#b5ccbf", "#00acc1": "#5d8075", "#00bcd4": "#6a8d81", "#0097a7": "#557568",
    "#00838f": "#4a685d", "#006064": "#3a5249", "#009688": "#5b7d6b", "#00897b": "#54735f", "#00796b": "#4a6855",
    "#00695c": "#405c4b", "#004d40": "#31473b", "#26a69a": "#6a8c78",
    # material greens -> olive greens
    "#2e7d32": "#3f5a36", "#1b5e20": "#2e4228", "#388e3c": OLIVE, "#43a047": "#5a7550", "#4caf50": "#6a8660",
    "#66bb6a": "#86a07a", "#81c784": "#a2b894", "#a5d6a7": SAGE_LIGHT, "#c8e6c9": SAGE_PALE, "#e8f5e9": "#edf2e6",
    "#00c853": "#5a7550", "#00e676": "#9fbf84", "#00ff66": "#a9d18e",
    # purple / violet / pink-violet -> khaki bronze (an earthy accent that sits with olive)
    "#8e24aa": "#8a7a4a", "#9c27b0": "#8a7a4a", "#7b1fa2": "#75673d", "#ab47bc": "#a39463", "#673ab7": "#7d7045",
    "#5e35b1": "#73663f", "#512da8": "#6a5e3a", "#4527a0": "#605434", "purple": "#7d7045",
    "darkmagenta": "#605434", "violet": OLIVE_MID,
    # indigo -> slate olive
    "#3f51b5": "#56665d", "#3949ab": "#4d5c54", "#283593": "#3f4c45", "#1a237e": "#333f39", "#5c6bc0": "#6f7f76",
    # blue greys -> olive greys (text, borders, cards)
    "#263238": "#283024", "#37474f": "#3a4535", "#455a64": "#4a5845", "#546e7a": "#5a6954", "#607d8b": "#687862",
    "#78909c": "#7d8b75", "#90a4ae": "#98a68d", "#b0bec5": "#b5c0a9", "#cfd8dc": "#ccd5c2", "#eceff1": OLIVE_SHADE,
    "#212121": "#232a20", "#f5f7f8": "#f3f6ef", "#e3e8ec": "#e2e8da", "#e2e8f0": "#e2e8da", "#e0e6ea": "#dfe5d7",
    "#cbd5e1": "#c9d2bf", "#1f2933": "#232b20",
    # neutral greys -> light olive shading / dark olive
    "#f5f5f5": "#f1f4ed", "#f8f9fa": "#f5f7f2", "#fafafa": "#f8faf5", "#f4f4f4": "#f1f4ed", "#f0f0f0": "#eef2e8",
    "#eeeeee": OLIVE_SHADE, "#ececec": "#e8ede2", "#e8e8e8": "#e4eadd", "#e0e0e0": "#dde4d5", "#dcdcdc": "#d8dfd0",
    "#dddddd": "#d9e0d1", "#d6d6d6": "#d3dbca", "#d4d4d4": "#d1d9c8", "#cccccc": "#c8d0bf", "#bcbcbc": "#b9c2ae",
    "#bbbbbb": "#b6c0ab", "#aaaaaa": "#a7b19c", "#9e9e9e": "#9ca694", "#999999": "#97a18c", "#888888": "#87927d",
    "#777777": "#75806b", "#757575": "#727d69", "#666666": "#636e5c", "#616161": "#5d6857", "#555555": "#535e4d",
    "#444444": "#434d3e", "#424242": "#3f4a3a", "#333333": "#343e30", "#2d2d2d": "#2c3628", "#1e1e1e": CONSOLE_DARK,
    "#1a1a1a": "#1b2219", "#111111": "#161c14", "#fcfcfc": "#fbfcf9",
    "#eee": OLIVE_SHADE, "#ddd": "#d9e0d1", "#ccc": "#c8d0bf", "#bbb": "#b6c0ab", "#aaa": "#a7b19c",
    "#999": "#97a18c", "#888": "#87927d", "#777": "#75806b", "#666": "#636e5c", "#555": "#535e4d",
    "#444": "#434d3e", "#333": "#343e30", "#222": "#232a20",
}
_bad = set(COLOR_MAP) & {v.lower() for v in COLOR_MAP.values()}
assert not _bad, f"theme map targets that are also keys: {_bad}"

_NAMED = [k for k in COLOR_MAP if not k.startswith('#')]
_RX = re.compile(r"#[0-9a-fA-F]{6}(?![0-9a-fA-F])|#[0-9a-fA-F]{3}(?![0-9a-fA-F])"
                 r"|(?<=:)(\s*)(" + "|".join(_NAMED) + r")(?![\w-])", re.IGNORECASE)
_cache = {}


def remap_color(c):
    """One colour string ('#1565c0', 'blue' ...) -> its theme colour (unchanged when not in the map)."""
    if not isinstance(c, str):
        return c
    return COLOR_MAP.get(c.strip().lower(), c)


def remap_css(css):
    """A stylesheet / colour text with every mapped colour replaced (cached; idempotent)."""
    if not isinstance(css, str) or not css:
        return css
    out = _cache.get(css)
    if out is None:
        def sub(m):
            if m.group(2):                                   # named colour after ':'
                return m.group(1) + COLOR_MAP[m.group(2).lower()]
            return COLOR_MAP.get(m.group(0).lower(), m.group(0))
        out = _RX.sub(sub, css)
        if len(_cache) < 20000:
            _cache[css] = out
    return out


# ---------------------------------------------------------------------------------------------------------------
# Axis widgets keep their colours (they match the plot lines)
# ---------------------------------------------------------------------------------------------------------------
AXIS_KEYS = {'X', 'Y', 'Z', 'LAT', 'SI', 'AP', 'Roll', 'Pitch', 'Yaw', 'A', 'B', 'C', 'D', "'a", "'c", "'e", "'f",
             'W', 'V'}
_ORIG = "kq_original_css"


def _widget_text(w):
    try:
        if isinstance(w, (QAbstractButton, QLabel)):
            return str(w.text() or '')
    except RuntimeError:
        pass
    return ''


_axis_colors = {}


def axis_colors():
    """{axis: colours it is drawn in} (Planning plot / pills, Status plot / legacy checkboxes)."""
    if not _axis_colors:
        for mod, attr in (('fcn_create_gui.tab_planning_modern', 'PLOT_COLORS'),
                          ('fcn_create_gui.tab_status_modern', '_FALLBACK_COLORS')):
            try:
                import importlib
                for k, c in getattr(importlib.import_module(mod), attr).items():
                    _axis_colors.setdefault(k, set()).add(c.lower())
            except Exception:
                pass
    return _axis_colors


def is_axis_widget(w, css=None):
    """A button / label that names an axis ('X', "Show 'a", 'Roll 0.00' ...) and is drawn in that axis' colour: it
    matches the plot line, so it is never remapped ('Home X' in green is not an axis colour of X: remapped)."""
    try:
        if w.property("kq_keep_colors"):
            return True
        if css is None:
            css = w.property(_ORIG) or w.styleSheet()
    except RuntimeError:
        return False
    if not isinstance(w, QAbstractButton):                    # pills / 'Show X' boxes; labels follow the theme
        return False
    keys = [tok.rstrip(':') for tok in _widget_text(w).replace('&', '').split()]
    keys = [k for k in keys if k in AXIS_KEYS]
    if not keys:
        return False
    found = {m.group(0).lower() for m in re.finditer(r"#[0-9a-fA-F]{6}(?![0-9a-fA-F])", str(css or ''))}
    cols = axis_colors()
    return any(found & cols.get(k, set()) for k in keys)      # drawn in that axis' own colour


# ---------------------------------------------------------------------------------------------------------------
# Hooks
# ---------------------------------------------------------------------------------------------------------------
_orig_widget_set = QWidget.setStyleSheet
_orig_app_set = QApplication.setStyleSheet
_prepared = False


def _themed_widget_set(self, css):
    try:
        if isinstance(css, str) and css:
            self.setProperty(_ORIG, css)
            if not is_axis_widget(self, css):
                css = remap_css(css)
    except RuntimeError:
        pass
    _orig_widget_set(self, css)


def _themed_app_set(self, css):
    _orig_app_set(self, remap_css(css))


class ThemedQColor(QColor):
    """QColor that maps the old UI colours given as text (painted sliders, drawn icons)."""

    def __init__(self, *args):
        if args and isinstance(args[0], str):
            args = (remap_color(args[0]),) + tuple(args[1:])
        super().__init__(*args)


# Module constants that are plot / axis colours: never remapped
_KEEP_NAMES = ('AXIS', 'PLOT', 'TRIGGER', 'PREVIEW', 'REFERENCE', 'OTHER_COLOR', 'INNER_START', 'FALLBACK')
# painted colours (QColor('#1565c0')) are remapped only where they are UI chrome, never where axis colours are
# computed (the pills derive their text / fill colours from the axis colour with QColor)
_QCOLOR_MODULES = ('fcn_create_gui.tab_planning_curve_controls',)
_THEMED_MODULES = ('fcn_create_gui.tab_status_modern', 'fcn_create_gui.tab_planning_modern',
                   'fcn_create_gui.tab_planning_curve_controls', 'fcn_create_gui.tab_planning_insert',
                   'fcn_create_gui.tab_planning_plot_edit', 'fcn_create_gui.tab_planning_white',
                   'fcn_create_gui.console_theme', 'fcn_create_gui.top_bar_style')


def _theme_module(mod):
    """String constants (styles, icon colours) and string default arguments of a module, and its QColor."""
    for name, val in list(vars(mod).items()):
        if name.startswith('__'):
            continue
        if isinstance(val, str) and '#' in val or isinstance(val, str) and val.lower() in COLOR_MAP:
            if not any(k in name.upper() for k in _KEEP_NAMES):
                setattr(mod, name, remap_css(val))
        elif callable(val) and getattr(val, '__module__', None) == mod.__name__:
            funcs = [val]
            if isinstance(val, type):
                funcs = [f for f in vars(val).values() if callable(f)]
            for f in funcs:
                d = getattr(f, '__defaults__', None)
                if d and any(isinstance(x, str) for x in d):
                    try:
                        f.__defaults__ = tuple(remap_css(x) if isinstance(x, str) else x for x in d)
                    except (AttributeError, TypeError):
                        pass
    if mod.__name__ in _QCOLOR_MODULES and getattr(mod, 'QColor', None) is QColor:
        mod.QColor = ThemedQColor


def theme_palette(app):
    pal = app.palette()
    roles = {
        QPalette.Window: OLIVE_TINT, QPalette.WindowText: OLIVE_TEXT, QPalette.Base: "#ffffff",
        QPalette.AlternateBase: OLIVE_TINT, QPalette.Text: OLIVE_TEXT, QPalette.Button: "#eef2e8",
        QPalette.ButtonText: OLIVE_TEXT, QPalette.Highlight: OLIVE_MID, QPalette.HighlightedText: "#ffffff",
        QPalette.Link: OLIVE, QPalette.LinkVisited: OLIVE_DARK, QPalette.ToolTipBase: "#fbfcf9",
        QPalette.ToolTipText: OLIVE_TEXT, QPalette.Light: "#ffffff", QPalette.Midlight: OLIVE_SHADE,
        QPalette.Mid: "#b5c0a9", QPalette.Dark: "#7d8b75", QPalette.Shadow: "#3a4535",
        QPalette.PlaceholderText: "#87927d",
    }
    for role, c in roles.items():
        pal.setColor(QPalette.All, role, QColor(c))
    pal.setColor(QPalette.Disabled, QPalette.Text, QColor("#9ca694"))
    pal.setColor(QPalette.Disabled, QPalette.ButtonText, QColor("#9ca694"))
    pal.setColor(QPalette.Disabled, QPalette.WindowText, QColor("#9ca694"))
    app.setPalette(pal)


def prepare_logiq_theme():
    """Before the main window is built (safe to call more than once)."""
    global _prepared
    if _prepared:
        return
    _prepared = True
    from fcn_create_gui.display_names import prepare_display_names
    prepare_display_names()                          # DYNAMIQ / KINETIQ on screen, the code keeps its words
    QWidget.setStyleSheet = _themed_widget_set
    QApplication.setStyleSheet = _themed_app_set
    import importlib
    for name in _THEMED_MODULES:
        try:
            _theme_module(sys.modules.get(name) or importlib.import_module(name))
        except Exception as e:                       # a missing module never stops the app
            print(f"[theme] {name}: {e}", flush=True)
    app = QApplication.instance()
    if app is not None:
        theme_palette(app)


def _sweep(root):
    """Existing widgets: remap sheets set before the hook; axis widgets get their original sheet back."""
    for w in [root] + root.findChildren(QWidget):
        try:
            css = w.styleSheet()
            orig = w.property(_ORIG)
            if is_axis_widget(w, orig if isinstance(orig, str) and orig else css):
                if isinstance(orig, str) and orig and orig != css:
                    _orig_widget_set(w, orig)
            elif css:
                new = remap_css(css)
                if new != css:
                    _orig_widget_set(w, new)
        except RuntimeError:
            continue


def add_word_mark(window):
    """'LogIQ' next to the logo in the top-left corner of the main tab bar."""
    if getattr(window, 'logiq_word_mark', None) is not None:
        return
    tw = getattr(window, 'tabModules', None)
    corner = tw.cornerWidget(Qt.TopLeftCorner) if tw is not None else None
    lay = corner.layout() if isinstance(corner, QWidget) else None
    if not isinstance(lay, QHBoxLayout):
        return
    lbl = QLabel(APP_NAME, corner)
    lbl.setObjectName("logiqWordMark")
    lbl.setStyleSheet(f"QLabel#logiqWordMark {{ color: {OLIVE_TEXT}; background: transparent; border: none; "
                      f"font-size: 21px; font-weight: 600; letter-spacing: 2px; padding-left: 10px; }}")
    lbl.setToolTip(APP_NAME)
    lay.addWidget(lbl)
    corner.adjustSize()
    window.logiq_word_mark = lbl


def apply_logiq_theme(window):
    """After the main window is built."""
    prepare_logiq_theme()
    app = QApplication.instance()
    if app is not None:
        theme_palette(app)
        if app.styleSheet():
            _orig_app_set(app, remap_css(app.styleSheet()))
    _sweep(window)
    add_word_mark(window)
    from fcn_create_gui.display_names import install_display_names
    install_display_names(window)                    # widgets Qt named itself, and pages built later
    try:
        t = window.windowTitle()
        for old in ("TRACE", "KINETIQ"):
            if t.startswith(old):
                window.setWindowTitle(APP_NAME + t[len(old):])
                break
    except RuntimeError:
        pass
    window.logiq_theme = True
    return window
