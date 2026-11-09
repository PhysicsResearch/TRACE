"""
Light / dark switch for the Duet command console on the Control tab (self.duet_log_console).

A small button right of 'Send' shows the console's current mode: a sun in light mode, a moon in dark mode; each press
switches.  Only the console box changes: the original (dark) style sheet is kept and restored exactly, the light one
is white with dark text.  Coloured log lines (errors in red, notes in orange / blue) keep their own colours.  The choice
is remembered per user with QSettings (configuration.json is not touched).
"""
from PySide6.QtCore import Qt, QByteArray, QSettings, QSize
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QToolButton, QLayout

try:
    from PySide6.QtSvg import QSvgRenderer
except Exception:                                   # pragma: no cover
    QSvgRenderer = None

SETTINGS_KEY = "control/console_theme"            # 'dark' (default) or 'light'

LIGHT_STYLE = """
    QTextEdit {
        background-color: #ffffff;
        color: #1f2933;
        font-family: Consolas, monospace;
        font-size: 18px;
        border: 1px solid #cfd8dc;
        border-radius: 4px;
    }
    QScrollBar:vertical {
        width: 36px;
        background: #eceff1;
        margin: 0px;
    }
    QScrollBar::handle:vertical {
        background: #b0bec5;
        min-height: 40px;
        border-radius: 6px;
    }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
        background: none;
        height: 0px;
    }
"""

_SUN = """<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='#f59e0b' stroke-width='2'
stroke-linecap='round'><circle cx='12' cy='12' r='4.5' fill='#fbbf24'/><path d='M12 2v2.5M12 19.5V22M2 12h2.5M19.5 12H22
M4.9 4.9l1.8 1.8M17.3 17.3l1.8 1.8M4.9 19.1l1.8-1.8M17.3 6.7l1.8-1.8'/></svg>"""
_MOON = """<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'><path d='M20.5 14.5A8.5 8.5 0 0 1 9.5 3.5a8.5 8.5 0 1 0
11 11z' fill='#cbd5e1' stroke='#e2e8f0' stroke-width='1.2' stroke-linejoin='round'/></svg>"""


def _icon(svg, px=26):
    pm = QPixmap(px * 2, px * 2)
    pm.fill(Qt.transparent)
    if QSvgRenderer is not None:
        r = QSvgRenderer(QByteArray(svg.encode('utf-8')))
        p = QPainter(pm)
        r.render(p)
        p.end()
    pm.setDevicePixelRatio(2.0)
    return QIcon(pm)


def _find_layout(layout, widget):
    if layout is None:
        return None
    for i in range(layout.count()):
        item = layout.itemAt(i)
        if item.widget() is widget:
            return layout
        sub = item.layout()
        if isinstance(sub, QLayout):
            found = _find_layout(sub, widget)
            if found is not None:
                return found
    return None


class ConsoleTheme:
    def __init__(self, window):
        self.w = window
        self.console = window.duet_log_console
        self.dark_style = self.console.styleSheet()          # the original look, restored exactly
        self.sun = _icon(_SUN)
        self.moon = _icon(_MOON)
        send = window.sendCommandDUET
        self.button = QToolButton(send.parentWidget())
        self.button.setObjectName("consoleThemeButton")
        self.button.setCursor(Qt.PointingHandCursor)
        self.button.setIconSize(QSize(26, 26))
        h = max(send.minimumHeight(), send.sizeHint().height(), 40)
        self.button.setFixedSize(h, h)
        self.button.clicked.connect(self.toggle)
        lay = _find_layout(send.parentWidget().layout(), send)
        if lay is not None:
            lay.insertWidget(lay.indexOf(send) + 1, self.button)
        window.button_console_theme = self.button
        try:
            mode = str(QSettings("TRACE", "TRACE").value(SETTINGS_KEY, "dark"))
        except Exception:
            mode = "dark"
        self.apply("light" if mode == "light" else "dark", save=False)

    def apply(self, mode, save=True):
        self.mode = mode
        light = mode == "light"
        self.console.setStyleSheet(LIGHT_STYLE if light else self.dark_style)
        self.button.setIcon(self.sun if light else self.moon)
        bg, border, hover = ("#fff8e1", "#f59e0b", "#ffecb3") if light else ("#263238", "#455a64", "#37474f")
        self.button.setStyleSheet(
            f"QToolButton#consoleThemeButton {{ background: {bg}; border: 1px solid {border}; border-radius: 6px; }}"
            f"QToolButton#consoleThemeButton:hover {{ background: {hover}; }}")
        self.button.setToolTip("Console: light mode (sun). Click for dark mode." if light
                               else "Console: dark mode (moon). Click for light mode.")
        if save:
            try:
                QSettings("TRACE", "TRACE").setValue(SETTINGS_KEY, mode)
            except Exception:
                pass

    def toggle(self):
        self.apply("dark" if self.mode == "light" else "light")


def add_console_theme_button(window):
    """Adds the sun / moon button right of 'Send' (Control tab, built at start-up).  Safe to call once."""
    if getattr(window, 'console_theme', None) is not None:
        return window.console_theme
    if getattr(window, 'duet_log_console', None) is None or getattr(window, 'sendCommandDUET', None) is None:
        return None
    try:
        window.console_theme = ConsoleTheme(window)
    except Exception as e:                                # never break start-up for a cosmetic switch
        print(f"Console theme button not added: {e}")
        window.console_theme = None
    return window.console_theme
