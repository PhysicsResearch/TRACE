"""
Modern controls for the Status tab (added on top of the existing tab, which is left unchanged).

``modernise_status_tab(self)`` is called once, right after ``build_status_tab(self)``.  It:

1. replaces the visible axis checkboxes by toggle "pills" grouped per device (Lung Phantom: X Y Z;
   Motion Platform: "Platform position" LAT SI AP Roll Pitch Yaw and "Individual axes" A B C D 'a 'c 'e 'f)
   plus a "G-code reference" toggle.  A pill lights up in the colour of its curve.  Clicking a group or
   section title selects all of its (shown) axes, or deselects them when all are already on.
2. replaces the matplotlib navigation toolbar by a row of drawn icons (Reset view, Back, Forward, Pan,
   Zoom box, Save image) that drive the hidden matplotlib toolbar, and boxes for the time / position
   limits with an "Auto" toggle per axis.  Manual limits survive the live redraws.
3. drops the grey backgrounds of the old checkbox panel and toolbar strip (both hidden): white cards.
4. shows a "Record - ON" (green) / "Record - OFF" (red) button instead of the 'Record Data Log' checkbox.
5. hides the 'Load Log' and 'Load G-code as Ref' buttons (the Log files tab does that now).
6. gathers the plot controls in the side card: below the axis groups "View limits" (time / position boxes with
   Auto, and in Advanced mode Time interval / Ref. offset / Max Speed Adj) and, in Advanced mode, "Data log"
   (output folder, Set Folder).  Clear Plot Data and Record sit in a fixed footer of the card (both modes), so
   they never scroll out of view.  The old row above the plot is hidden (the plot gets its height).  The
   legacy widgets themselves are moved into the panel, so every reader / handler keeps working on them.
7. (user request, ON by default: ASK_MAX_SPEED_ADJ_IN_POPUP) hides 'Max Speed Adj (%)' and asks for that value
   in a popup when Auto-sync Speed is turned on (OK writes it into the hidden field, Cancel leaves Auto-sync off).
   With the switch False, Auto-sync and Max Speed Adj behave exactly as before (field in the Advanced block).

The legacy widgets (self.status_check_*, self.check_show_reference, self.check_record_log,
self.status_toolbar, ...) stay in place, hidden where needed, and remain the single source of truth:
the new widgets only mirror them, so render_status_plot and the recording logic are untouched.
render_status_plot is wrapped (module global of fcn_monitor.fcn_duet) to re-apply manual axis limits
and to refresh the mirrors after every redraw.
"""

import functools

from PySide6.QtCore import Qt, QByteArray, QSize, QTimer
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QToolButton, QLabel, QLineEdit, QScrollArea, QFrame,
    QSizePolicy, QInputDialog
)

try:
    from PySide6.QtSvg import QSvgRenderer
except Exception:           # pragma: no cover - QtSvg ships with PySide6
    QSvgRenderer = None


# ----------------------------------------------------------------------------------------- axis groups
# (legacy checkbox attribute, plot data key, pill text); colours are read from the legacy checkboxes
# (same colours as render_status_plot draws) and re-synced from the drawn lines after each redraw.
PHANTOM_AXES = [('status_check_X', 'X', 'X'), ('status_check_Y', 'Y', 'Y'), ('status_check_Z', 'Z', 'Z')]
PLATFORM_POSITION_AXES = [('status_check_LAT', 'LAT', 'LAT'), ('status_check_SI', 'SI', 'SI'),
                          ('status_check_AP', 'AP', 'AP'), ('status_check_Roll', 'Roll', 'Roll'),
                          ('status_check_Pitch', 'Pitch', 'Pitch'), ('status_check_Yaw', 'Yaw', 'Yaw')]
INDIVIDUAL_AXES = [('status_check_A', 'A', 'A'), ('status_check_B', 'B', 'B'), ('status_check_C', 'C', 'C'),
                   ('status_check_D', 'D', 'D'), ('status_check_a', "'a", "'a"), ('status_check_c', "'c", "'c"),
                   ('status_check_e', "'e", "'e"), ('status_check_f', "'f", "'f")]
_FALLBACK_COLORS = {
    'X': '#1e88e5', 'Y': '#43a047', 'Z': '#e53935', 'A': '#8e24aa', 'B': '#d81b60', 'C': '#00acc1',
    'D': '#f4511e', "'e": '#795548', "'f": '#607d8b', "'a": '#009688', "'c": '#ffb300', 'Roll': '#3f51b5',
    'Pitch': '#9e9d24', 'Yaw': '#673ab7', 'LAT': '#e65100', 'AP': '#1b5e20', 'SI': '#01579b',
}
_AXIS_TIPS = {
    'X': "Lung phantom X position (mm)", 'Y': "Lung phantom Y position (mm)", 'Z': "Lung phantom Z position (mm)",
    'LAT': "Motion platform lateral (LAT) position (mm)", 'SI': "Motion platform superior-inferior (SI) position (mm)",
    'AP': "Motion platform anterior-posterior (AP) position (mm)", 'Roll': "Motion platform roll (deg)",
    'Pitch': "Motion platform pitch (deg)", 'Yaw': "Motion platform yaw (deg)",
}
REFERENCE_COLOR = '#1565c0'
CARD_BORDER = '#cfd8dc'
ICON_COLOR = '#455a64'
ICON_ACTIVE = '#0d47a1'
ICON_DISABLED = '#b0bec5'

# Drawn icons (24x24 view box, 2 px round strokes)
_ICONS = {
    'home': '<path d="M3 11.5 L12 4 L21 11.5"/><path d="M5.5 9.5 V20 H10 V14.5 H14 V20 H18.5 V9.5"/>',
    'back': '<path d="M19 12 H5"/><path d="M11 6 L5 12 L11 18"/>',
    'forward': '<path d="M5 12 H19"/><path d="M13 6 L19 12 L13 18"/>',
    'pan': '<path d="M12 3 V21 M3 12 H21"/><path d="M9 6 L12 3 L15 6 M9 18 L12 21 L15 18 M6 9 L3 12 L6 15 '
           'M18 9 L21 12 L18 15"/>',
    'zoom': '<circle cx="10.5" cy="10.5" r="6.5"/><path d="M15.5 15.5 L21 21"/>'
            '<path d="M10.5 7.5 V13.5 M7.5 10.5 H13.5"/>',
    'save': '<path d="M12 3.5 V14.5"/><path d="M7.5 10 L12 14.5 L16.5 10"/><path d="M4 16.5 V20.5 H20 V16.5"/>',
    'dashes': '<path d="M2 12 H7 M10 12 H14 M17 12 H22"/>',
    'trash': '<path d="M4 7 H20"/><path d="M9.5 7 V4.5 H14.5 V7"/><path d="M6.5 7 L7.5 20 H16.5 L17.5 7"/>'
             '<path d="M10.5 11 V16.5 M13.5 11 V16.5"/>',
}

# Tri-state "select all" box of the clickable section titles: none / some / all of the shown curves selected
_GROUP_BOX = {
    'none': '<rect x="3.5" y="3.5" width="17" height="17" rx="3.5" fill="#ffffff" stroke="{c}" stroke-width="2"/>',
    'some': '<rect x="3.5" y="3.5" width="17" height="17" rx="3.5" fill="#ffffff" stroke="{c}" stroke-width="2"/>'
            '<path d="M8 12 H16" stroke="{c}" stroke-width="2.6" stroke-linecap="round"/>',
    'all': '<rect x="3.5" y="3.5" width="17" height="17" rx="3.5" fill="{c}" stroke="{c}" stroke-width="2"/>'
           '<path d="M7.5 12.3 L10.7 15.4 L16.6 8.8" fill="none" stroke="#ffffff" stroke-width="2.4" '
           'stroke-linecap="round" stroke-linejoin="round"/>',
}
GROUP_BOX_COLOR = '#1565c0'


def _svg_pixmap(name, color, px):
    body = _ICONS[name]
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" '
           f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">{body}</svg>')
    pm = QPixmap(px, px)
    pm.fill(Qt.transparent)
    if QSvgRenderer is not None:
        r = QSvgRenderer(QByteArray(svg.encode('utf-8')))
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing, True)
        r.render(p)
        p.end()
    return pm


def make_icon(name, color=ICON_COLOR, active=ICON_ACTIVE, disabled=ICON_DISABLED, on_color=None):
    """QIcon from a drawn SVG: normal / checked (on) / disabled colours, crisp at 100-200 % scaling."""
    icon = QIcon()
    for px in (24, 48):
        icon.addPixmap(_svg_pixmap(name, color, px), QIcon.Normal, QIcon.Off)
        icon.addPixmap(_svg_pixmap(name, active, px), QIcon.Active, QIcon.Off)
        icon.addPixmap(_svg_pixmap(name, on_color or active, px), QIcon.Normal, QIcon.On)
        icon.addPixmap(_svg_pixmap(name, on_color or active, px), QIcon.Active, QIcon.On)
        icon.addPixmap(_svg_pixmap(name, disabled, px), QIcon.Disabled, QIcon.Off)
        icon.addPixmap(_svg_pixmap(name, disabled, px), QIcon.Disabled, QIcon.On)
    return icon


def make_group_icon(state, color=GROUP_BOX_COLOR):
    """Tri-state box of a clickable section title ('none' / 'some' / 'all' of its shown curves on)."""
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
           + _GROUP_BOX[state].replace('{c}', color) + '</svg>')
    icon = QIcon()
    for px in (24, 48):
        pm = QPixmap(px, px)
        pm.fill(Qt.transparent)
        if QSvgRenderer is not None:
            r = QSvgRenderer(QByteArray(svg.encode('utf-8')))
            p = QPainter(pm)
            p.setRenderHint(QPainter.Antialiasing, True)
            r.render(p)
            p.end()
        icon.addPixmap(pm, QIcon.Normal, QIcon.Off)
        icon.addPixmap(pm, QIcon.Active, QIcon.Off)
    return icon


# ----------------------------------------------------------------------------------------- helpers
def _legacy_color(cb, key):
    """Colour of the legacy checkbox text (the same colour the curve is drawn in)."""
    import re
    try:
        m = re.search(r'color\s*:\s*(#[0-9a-fA-F]{6})', cb.styleSheet() or '')
        if m:
            return m.group(1).lower()
    except Exception:
        pass
    return _FALLBACK_COLORS.get(key, '#455a64')


def _is_light(color):
    c = QColor(color)
    lum = 0.2126 * c.redF() ** 2.2 + 0.7152 * c.greenF() ** 2.2 + 0.0722 * c.blueF() ** 2.2
    return lum > 0.30


def pill_style(color):
    """Off: white with the curve colour as text; on: filled with the curve colour."""
    c = QColor(color)
    txt_off = c.darker(150).name() if _is_light(color) else c.name()
    txt_on = '#212121' if _is_light(color) else '#ffffff'
    hover_bg = f"rgba({c.red()}, {c.green()}, {c.blue()}, 28)"
    on_hover = c.darker(115).name()
    return f"""
        QToolButton {{
            background-color: #ffffff; color: {txt_off};
            border: 1px solid {CARD_BORDER}; border-radius: 14px;
            font-size: 13px; font-weight: bold; padding: 2px 8px;
        }}
        QToolButton:hover {{ border: 1px solid {c.name()}; background-color: {hover_bg}; }}
        QToolButton:checked {{ background-color: {c.name()}; color: {txt_on}; border: 1px solid {c.name()}; }}
        QToolButton:checked:hover {{ background-color: {on_hover}; border: 1px solid {on_hover}; }}
        QToolButton:disabled {{ color: #b0bec5; border: 1px solid #eceff1; }}
    """


TITLE_STYLE = """
    QToolButton {
        border: none; background: transparent; color: #263238;
        font-size: 14px; font-weight: bold; padding: 2px 0px; margin: 0px; text-align: left;
    }
    QToolButton:hover { color: #1565c0; text-decoration: underline; }
"""
SUBTITLE_STYLE = """
    QToolButton {
        border: none; background: transparent; color: #546e7a;
        font-size: 12px; font-weight: bold; padding: 1px 0px; margin: 0px; text-align: left;
    }
    QToolButton:hover { color: #1565c0; text-decoration: underline; }
"""
NAV_BUTTON_STYLE = """
    QToolButton {
        background: #ffffff; border: 1px solid transparent; border-radius: 6px; padding: 2px;
    }
    QToolButton:hover { background: #e3f2fd; border: 1px solid #bbdefb; }
    QToolButton:checked { background: #bbdefb; border: 1px solid #1565c0; }
    QToolButton:pressed { background: #90caf9; }
"""
AUTO_STYLE = """
    QToolButton {
        background: #ffffff; color: #455a64; border: 1px solid #b0bec5; border-radius: 4px;
        font-size: 12px; font-weight: bold; padding: 1px 8px;
    }
    QToolButton:hover { border: 1px solid #1565c0; color: #1565c0; }
    QToolButton:checked { background: #1565c0; color: #ffffff; border: 1px solid #1565c0; }
"""
LIMIT_STYLE_AUTO = """
    QLineEdit { background: #ffffff; color: #37474f; border: 1px solid #cfd8dc; border-radius: 4px;
                font-size: 13px; padding: 1px 6px; }
    QLineEdit:focus { border: 1px solid #1565c0; color: #0d47a1; }
"""
# Time interval / Ref. offset / Max Speed Adj (legacy fields, restyled only): same look as the limit boxes
FIELD_STYLE = """
    QLineEdit { background: #ffffff; color: #263238; border: 1px solid #cfd8dc; border-radius: 4px;
                font-size: 13px; font-weight: bold; padding: 1px 6px; }
    QLineEdit:focus { border: 1px solid #1565c0; color: #0d47a1; }
    QLineEdit:disabled { color: #90a4ae; background: #ffffff; }
"""
FIELD_WIDTH = 72
CLEAR_STYLE = """
    QPushButton { background-color: #ffffff; color: #c62828; border: 1px solid #cfd8dc; border-radius: 6px;
                  font-size: 13px; font-weight: bold; padding: 2px 10px; }
    QPushButton:hover { background-color: #ffebee; border: 1px solid #ef9a9a; }
    QPushButton:pressed { background-color: #ffcdd2; border: 1px solid #e57373; }
"""
LIMIT_STYLE_MANUAL = """
    QLineEdit { background: #ffffff; color: #0d47a1; border: 1px solid #1565c0; border-radius: 4px;
                font-size: 13px; font-weight: bold; padding: 1px 6px; }
    QLineEdit:focus { border: 1px solid #0d47a1; }
"""
RECORD_ON_STYLE = """
    QToolButton { background-color: #2e7d32; color: #ffffff; border: none; border-radius: 6px;
                  font-size: 13px; font-weight: bold; padding: 2px 14px; }
    QToolButton:hover { background-color: #1b5e20; }
"""
RECORD_OFF_STYLE = """
    QToolButton { background-color: #c62828; color: #ffffff; border: none; border-radius: 6px;
                  font-size: 13px; font-weight: bold; padding: 2px 14px; }
    QToolButton:hover { background-color: #b71c1c; }
"""
SECTION_STYLE = "color: #263238; font-size: 14px; font-weight: bold; background: transparent;"
FIELD_LABEL_STYLE = "color: #455a64; font-size: 13px; font-weight: bold; background: transparent;"
SEPARATOR_STYLE = f"QFrame {{ background: {CARD_BORDER}; border: none; }}"
PANEL_WIDTH = 236
NAV_ICON_PX = 22
NAV_BUTTON_PX = 34
MAX_ADJ_RANGE = (1.0, 200.0, 1)         # what input_max_speed_adj's validator accepts (min, max, decimals)
# Item 7 (popup for the max speed adjustment when Auto-sync is turned on): requested by the user, ON by default;
# with False the Auto-sync checkbox and the Max Speed Adj field work exactly as before.
ASK_MAX_SPEED_ADJ_IN_POPUP = True
RECORD_ON_TEXT = "●  Record – ON"
RECORD_OFF_TEXT = "●  Record – OFF"


def parse_number(text):
    """Float from a box: decimal comma or point, optional spaces / unicode minus. None if not a number."""
    if text is None:
        return None
    t = str(text).strip().replace(' ', '').replace('−', '-').replace(',', '.')
    if not t:
        return None
    try:
        v = float(t)
    except ValueError:
        return None
    return v if v == v and abs(v) != float('inf') else None


def format_number(v, span=None):
    """Short number for a limit box / the pointer readout, always with a decimal POINT (as the plot ticks and
    the Time interval / Ref. offset fields show it); the boxes accept a comma or a point when typing."""
    s = abs(span) if span else abs(v)
    dec = 3 if s < 10 else (2 if s < 1000 else 1)
    txt = f"{v:.{dec}f}"
    if '.' in txt:
        txt = txt.rstrip('0').rstrip('.')
    if txt in ('-0', ''):
        txt = '0'
    return txt


def _find_layout_with(layout, widget):
    """(layout, index) of the layout under `layout` that directly holds `widget`."""
    if layout is None:
        return None, -1
    idx = layout.indexOf(widget)
    if idx >= 0:
        return layout, idx
    for i in range(layout.count()):
        sub = layout.itemAt(i).layout()
        if sub is not None:
            found, j = _find_layout_with(sub, widget)
            if found is not None:
                return found, j
    return None, -1


def _render(self):
    """The same redraw the legacy checkboxes trigger (module global: the wrapper below)."""
    from fcn_monitor import fcn_duet
    fcn_duet.render_status_plot(self)


# ----------------------------------------------------------------------------------------- render wrap
def install_render_wrapper():
    """Wraps fcn_monitor.fcn_duet.render_status_plot once: the original runs unchanged, then the modern
    Status controls (if this window has them) re-apply manual limits and refresh their mirrors.  Every
    caller in the app looks the function up at call time (fcn_duet's own calls use the module global,
    tab_status imports it inside the handlers), so all of them get the wrapper."""
    from fcn_monitor import fcn_duet
    cur = fcn_duet.render_status_plot
    if getattr(cur, '_stm_wrapper', False):
        return cur
    original = cur

    @functools.wraps(original)
    def render_status_plot(self):
        st = getattr(self, 'status_modern', None)
        if not isinstance(st, ModernStatus) or not st.alive:
            return original(self)
        before = st.before_render()
        result = original(self)
        try:
            st.after_render(before)
        except RuntimeError:            # widgets already deleted (window closed)
            st.alive = False
        except Exception as e:
            print(f"Status controls: could not refresh after the redraw: {e}")
        return result

    render_status_plot._stm_wrapper = True
    render_status_plot._stm_original = original
    fcn_duet.render_status_plot = render_status_plot
    return render_status_plot


# ----------------------------------------------------------------------------------------- the panel
class ModernStatus:
    """State and widgets of the modern Status controls of one window (self.status_modern)."""

    def __init__(self, win):
        self.win = win
        self.alive = True
        self.pills = {}                 # data key -> QToolButton
        self.pill_cb = {}               # data key -> legacy checkbox
        self.pill_color = {}            # data key -> colour of the pill
        self.sections = {}              # name -> (title button, [keys], container widget or None)
        self.manual_x = None            # (lo, hi) or None (Auto)
        self.manual_y = None
        self.data_ref = None            # status_plot_data object seen last: a new one = new data set
        self.data_seen = False
        self.cb_registry = None         # ax.callbacks the limit callbacks are connected to
        self.dragging = False
        self.press_lims = None
        self._updating_boxes = False
        self._editing = set()           # limit boxes the user is typing in (not overwritten by redraws)
        self._auto_sync_ok = False      # Auto-sync turned on by the popup's OK (no second popup)
        self._asking_max_adj = False
        self._title_state = {}          # title button -> 'none' / 'some' / 'all' (icon shown)
        self._group_icons = {s: make_group_icon(s) for s in ('none', 'some', 'all')}
        self.ask_max_adj = bool(ASK_MAX_SPEED_ADJ_IN_POPUP)

    # ---------------------------------------------------------------- build
    def build(self):
        w = self.win
        self.plot_box = w.statusCanvas.parentWidget()
        self._build_axis_panel()
        self._build_nav_row()
        self.on_mode_changed()
        self._connect_canvas()
        self.update_limit_boxes()
        self.update_nav_buttons()
        # Basic <-> Advanced: connected after the existing handler (it lays out the legacy checkboxes first)
        w.check_advanced_mode.toggled.connect(lambda _c: self.on_mode_changed())
        # Item 7 (optional, off by default): Auto-sync Speed on asks for the max speed adjustment in a popup
        if (self.ask_max_adj and getattr(w, 'check_auto_sync', None) is not None
                and getattr(w, 'input_max_speed_adj', None) is not None):
            w.check_auto_sync.toggled.connect(self._on_auto_sync_toggled)
            w.check_auto_sync.setToolTip("Adjusts the speed factor automatically so the live curve keeps up with the "
                                         "G-code reference.\nTurning it on asks for the maximum speed adjustment (%).")

    def _build_axis_panel(self):
        w = self.win
        # Side card (white, 1 px border, radius 6): the scrolling panel + a fixed footer that never scrolls
        # away (Clear Plot Data, Record - the latter is the safety-relevant one)
        self.side_card = QFrame(self.plot_box)
        self.side_card.setObjectName('stmSideCard')
        self.side_card.setFixedWidth(PANEL_WIDTH)
        self.side_card.setStyleSheet(
            f"QFrame#stmSideCard {{ background: #ffffff; border: 1px solid {CARD_BORDER}; border-radius: 6px; }}")
        card_lay = QVBoxLayout(self.side_card)
        card_lay.setContentsMargins(2, 2, 2, 2)
        card_lay.setSpacing(0)
        self.panel_scroll = QScrollArea(self.side_card)
        self.panel_scroll.setObjectName('stmPanelScroll')
        self.panel_scroll.setWidgetResizable(True)
        self.panel_scroll.setFrameShape(QFrame.NoFrame)
        self.panel_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.panel_scroll.setStyleSheet("QScrollArea#stmPanelScroll { background: #ffffff; border: none; }")
        self.panel_scroll.viewport().setStyleSheet("background: #ffffff;")
        self.panel = QWidget()
        self.panel.setObjectName('stmPanel')
        self.panel.setStyleSheet("QWidget#stmPanel { background: #ffffff; }")
        lay = QVBoxLayout(self.panel)
        lay.setContentsMargins(8, 6, 6, 6)
        lay.setSpacing(5)

        # Reference toggle
        self.ref_title = QLabel("Reference", self.panel)
        self.ref_title.setStyleSheet(SECTION_STYLE)
        lay.addWidget(self.ref_title)
        self.ref_pill = QToolButton(self.panel)
        self.ref_pill.setText("G-code reference")
        self.ref_pill.setCheckable(True)
        self.ref_pill.setIcon(make_icon('dashes', color=REFERENCE_COLOR, active=REFERENCE_COLOR, on_color='#ffffff'))
        self.ref_pill.setIconSize(QSize(18, 18))
        self.ref_pill.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.ref_pill.setStyleSheet(pill_style(REFERENCE_COLOR))
        self.ref_pill.setFixedHeight(30)
        self.ref_pill.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.ref_pill.setCursor(Qt.PointingHandCursor)
        self.ref_pill.setToolTip(
            "Show the planned trajectory of the current job's G-code as dashed lines, in the colour of each "
            "selected curve.\nTurning it on loads the current job's G-code from the Duet when no reference "
            "is loaded yet.")
        self.ref_pill.clicked.connect(self.on_reference_clicked)
        lay.addWidget(self.ref_pill)
        lay.addSpacing(6)

        # Lung Phantom
        t = self._title("Lung Phantom", TITLE_STYLE,
                        "Click to select / deselect all Lung Phantom axes (X, Y, Z).\n"
                        "Selects all when at least one is off; deselects all when all are on.")
        lay.addWidget(t)
        g, keys = self._pill_grid(PHANTOM_AXES, cols=3)
        lay.addWidget(g)
        self.sections['phantom'] = (t, keys, None)
        lay.addSpacing(6)

        # Motion Platform (title acts on both subsections)
        tp = self._title("Motion Platform", TITLE_STYLE,
                         "Click to select / deselect all shown Motion Platform curves (platform position and "
                         "individual axes).\nSelects all when at least one is off; deselects all when all are on.")
        lay.addWidget(tp)
        pos_box = QWidget(self.panel)
        pos_lay = QVBoxLayout(pos_box)
        pos_lay.setContentsMargins(6, 0, 0, 0)
        pos_lay.setSpacing(4)
        ts = self._title("Platform position", SUBTITLE_STYLE,
                         "Click to select / deselect all shown platform position curves "
                         "(LAT, SI, AP and the rotations Roll, Pitch, Yaw).\n"
                         "Selects all when at least one is off; deselects all when all are on.")
        pos_lay.addWidget(ts)
        g, keys_pos = self._pill_grid(PLATFORM_POSITION_AXES, cols=3)
        pos_lay.addWidget(g)
        lay.addWidget(pos_box)
        self.sections['position'] = (ts, keys_pos, pos_box)

        ind_box = QWidget(self.panel)
        ind_lay = QVBoxLayout(ind_box)
        ind_lay.setContentsMargins(6, 4, 0, 0)
        ind_lay.setSpacing(4)
        ti = self._title("Individual axes", SUBTITLE_STYLE,
                         "Click to select / deselect all individual motor axes (A, B, C, D, 'a, 'c, 'e, 'f).\n"
                         "Selects all when at least one is off; deselects all when all are on.\n"
                         "Shown in Advanced mode only.")
        ind_lay.addWidget(ti)
        g, keys_ind = self._pill_grid(INDIVIDUAL_AXES, cols=4)
        ind_lay.addWidget(g)
        lay.addWidget(ind_box)
        self.sections['individual'] = (ti, keys_ind, ind_box)
        self.sections['platform'] = (tp, keys_pos + keys_ind, None)

        lay.addSpacing(4)
        lay.addWidget(self._separator())

        # View limits
        lim_title = QLabel("View limits", self.panel)
        lim_title.setStyleSheet(SECTION_STYLE)
        lim_title.setToolTip("Axis limits of the plot. Auto (lit) follows the data; typing a limit, panning or "
                             "zooming fixes the axis until Auto or Reset view is clicked.")
        lay.addWidget(lim_title)
        self.x_from, self.x_to, self.x_auto = self._limit_rows(lay, "Time (s)", 'x')
        self.y_from, self.y_to, self.y_auto = self._limit_rows(lay, "Position (mm / deg)", 'y')
        # Time interval / Ref. offset / Max Speed Adj (legacy fields, Advanced mode as before; restyled only)
        self.plot_settings_box = QWidget(self.panel)
        ps = QGridLayout(self.plot_settings_box)
        ps.setContentsMargins(0, 2, 0, 0)
        ps.setHorizontalSpacing(6)
        ps.setVerticalSpacing(5)
        fields = [
            ('input_time_interval', "Time interval (s)",
             "Width of the live time window (s). When the live data reaches its end, the window moves on by "
             "half its width.\nLoading a log sets it to the log's duration."),
            ('input_ref_offset', "Ref. offset (s)",
             "Shifts the G-code reference curves in time (s); positive = later. Auto-sync uses it too.")]
        if not self.ask_max_adj:
            fields.append(('input_max_speed_adj', "Max speed adj. (%)",
                           "Auto-sync Speed changes the speed factor by at most this much (from 100 %); a larger "
                           "correction turns Auto-sync off."))
        self.field_labels = {}
        for r, (attr, text, tip) in enumerate(fields):
            le = getattr(w, attr, None)
            if le is None:
                continue
            lbl = QLabel(text, self.plot_settings_box)
            lbl.setStyleSheet(FIELD_LABEL_STYLE)
            lbl.setToolTip(tip)
            le.setToolTip(tip)
            le.setStyleSheet(FIELD_STYLE)                # the look of the limit boxes (style only)
            le.setFixedHeight(28)
            le.setFixedWidth(FIELD_WIDTH)
            le.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            ps.addWidget(lbl, r, 0)
            ps.addWidget(le, r, 1, Qt.AlignRight)
            self.field_labels[attr] = lbl
        lay.addWidget(self.plot_settings_box)

        # Data log (Advanced mode, as the old log row)
        self.datalog_box = QWidget(self.panel)
        dl = QVBoxLayout(self.datalog_box)
        dl.setContentsMargins(0, 4, 0, 0)
        dl.setSpacing(5)
        dl.addWidget(self._separator(self.datalog_box))
        dl_title = QLabel("Data log", self.datalog_box)
        dl_title.setStyleSheet(SECTION_STYLE)
        dl_title.setToolTip("Recording of the live positions and probe of every G-code run to a CSV file.")
        dl.addWidget(dl_title)
        folder_lbl = QLabel("Output folder", self.datalog_box)
        folder_lbl.setStyleSheet(FIELD_LABEL_STYLE)
        dl.addWidget(folder_lbl)
        folder = getattr(w, 'PhOperFolder', None)
        if folder is not None:
            folder.setMinimumWidth(0)
            folder.setMaximumWidth(16777215)
            folder.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            folder.setToolTip(f"Folder of the data log files (log_DDMMYYYY_HH_MM_SS.csv):\n{folder.text()}")
            folder.textChanged.connect(lambda t, e=folder: e.setToolTip(
                f"Folder of the data log files (log_DDMMYYYY_HH_MM_SS.csv):\n{t}"))
            dl.addWidget(folder)
        set_folder = getattr(w, 'setPhOperFolder', None)
        if set_folder is not None:
            set_folder.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            set_folder.setCursor(Qt.PointingHandCursor)
            set_folder.setToolTip("Choose the folder of the data log files.")
            dl.addWidget(set_folder)
        lay.addWidget(self.datalog_box)
        lay.addStretch(1)
        self.panel_scroll.setWidget(self.panel)

        # Fixed footer (both modes): Clear Plot Data and Record
        self.footer = QWidget(self.side_card)
        self.footer.setObjectName('stmFooter')
        self.footer.setStyleSheet("QWidget#stmFooter { background: #ffffff; }")
        fl = QVBoxLayout(self.footer)
        fl.setContentsMargins(8, 4, 6, 6)
        fl.setSpacing(6)
        fl.addWidget(self._separator(self.footer))
        clear = getattr(w, 'button_clear_plot', None)
        if clear is not None:            # the legacy button itself: its handler from init_buttons stays connected
            clear.setMinimumWidth(0)
            clear.setMaximumWidth(16777215)
            clear.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            clear.setCursor(Qt.PointingHandCursor)
            clear.setStyleSheet(CLEAR_STYLE)             # outline button instead of the grey block (style only)
            clear.setIcon(make_icon('trash', color='#c62828', active='#b71c1c'))
            clear.setIconSize(QSize(16, 16))
            clear.setFixedHeight(32)
            clear.setToolTip("Clear all curves, the reference and the probe shading from the plot.\n"
                             "Log files already written are not affected.")
            fl.addWidget(clear)
        self._build_record_button(self.footer)
        fl.addWidget(self.btn_record)

        card_lay.addWidget(self.panel_scroll, 1)
        card_lay.addWidget(self.footer)
        lay_row, idx = _find_layout_with(self.plot_box.layout(), w.status_checks_scroll)
        if lay_row is not None:
            lay_row.insertWidget(idx + 1, self.side_card)
        else:
            self.plot_box.layout().addWidget(self.side_card)

    def _title(self, text, style, tip):
        b = QToolButton(self.panel)
        b.setText(text)
        b.setStyleSheet(style)
        # A tri-state box in front of the title (none / some / all of its shown curves on): the visible cue
        # that the title is clickable (select / deselect all), also on a touch screen (no hover there)
        b.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        px = 16 if style is TITLE_STYLE else 14
        b.setIconSize(QSize(px, px))
        b.setIcon(self._group_icons['none'])
        b.setCursor(Qt.PointingHandCursor)
        b.setToolTip(tip + "\nThe box in front of the title shows the state: empty = none, dash = some, "
                           "tick = all selected.")
        b.setAutoRaise(True)
        b.clicked.connect(lambda _c=False, btn=b: self.on_title_clicked(btn))
        return b

    def _separator(self, parent=None):
        s = QFrame(parent if parent is not None else self.panel)
        s.setFrameShape(QFrame.NoFrame)
        s.setFixedHeight(1)
        s.setStyleSheet(SEPARATOR_STYLE)
        return s

    def _pill_grid(self, specs, cols):
        w = self.win
        box = QWidget(self.panel)
        grid = QGridLayout(box)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(5)
        grid.setVerticalSpacing(5)
        keys = []
        for i, (attr, key, text) in enumerate(specs):
            cb = getattr(w, attr, None)
            if cb is None:
                continue
            color = _legacy_color(cb, key)
            b = QToolButton(box)
            b.setText(text)
            b.setCheckable(True)
            b.setToolButtonStyle(Qt.ToolButtonTextOnly)
            b.setFixedHeight(28)
            b.setMinimumWidth(40)
            b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet(pill_style(color))
            what = _AXIS_TIPS.get(key, f"Motion platform motor axis {key} (mm)")
            b.setToolTip(f"{what}\nClick to show / hide this curve (lit = shown, in the curve's colour).")
            b.clicked.connect(lambda checked, k=key: self.on_pill_clicked(k, checked))
            cb.toggled.connect(lambda checked, k=key: self._on_legacy_toggled(k, checked))
            grid.addWidget(b, i // cols, i % cols)
            self.pills[key] = b
            self.pill_cb[key] = cb
            self.pill_color[key] = color
            keys.append(key)
        return box, keys

    def _nav_button(self, name, tip, slot, checkable=False):
        b = QToolButton(self.nav_row)
        b.setIcon(make_icon(name))
        b.setIconSize(QSize(NAV_ICON_PX, NAV_ICON_PX))
        b.setFixedSize(NAV_BUTTON_PX, NAV_BUTTON_PX)
        b.setCheckable(checkable)
        b.setAutoRaise(True)
        b.setCursor(Qt.PointingHandCursor)
        b.setToolTip(tip)
        b.setStyleSheet(NAV_BUTTON_STYLE)
        b.clicked.connect(slot)
        return b

    def _build_nav_row(self):
        w = self.win
        self.nav_row = QWidget(self.plot_box)
        self.nav_row.setObjectName('stmNavRow')
        self.nav_row.setStyleSheet("QWidget#stmNavRow { background: #ffffff; }")
        self.nav_row.setFixedHeight(NAV_BUTTON_PX)
        row = QHBoxLayout(self.nav_row)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        self.btn_reset = self._nav_button('home', "Reset view: automatic limits on both axes (live window / whole "
                                          "log), and clears the Back / Forward history.", self.on_reset)
        self.btn_back = self._nav_button('back', "Back to the previous view.", self.on_back)
        self.btn_forward = self._nav_button('forward', "Forward to the next view.", self.on_forward)
        self.btn_pan = self._nav_button('pan', "Pan: drag the plot with the left mouse button (right button "
                                        "zooms).\nClick again to leave pan mode.", self.on_pan, checkable=True)
        self.btn_zoom = self._nav_button('zoom', "Zoom box: drag a rectangle to zoom in (right button zooms "
                                         "out).\nClick again to leave zoom mode.", self.on_zoom, checkable=True)
        self.btn_save = self._nav_button('save', "Save the plot as an image (PNG, SVG, PDF ...).", self.on_save)
        # Pointer readout on the left, the icons on the right (next to the side card with the view limits)
        self.coord_label = QLabel("", self.nav_row)
        self.coord_label.setStyleSheet("color: #546e7a; font-size: 13px; background: transparent;")
        self.coord_label.setMinimumWidth(0)
        self.coord_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.coord_label.setToolTip("Time and value under the mouse pointer.")
        row.addWidget(self.coord_label, 1)
        row.addSpacing(10)
        for b in (self.btn_reset, self.btn_back, self.btn_forward):
            row.addWidget(b)
        row.addWidget(self._vsep())
        row.addWidget(self.btn_pan)
        row.addWidget(self.btn_zoom)
        row.addWidget(self._vsep())
        row.addWidget(self.btn_save)

        lay, idx = _find_layout_with(self.plot_box.layout(), w.status_toolbar)
        if lay is not None:
            lay.insertWidget(idx + 1, self.nav_row)
        else:
            self.plot_box.layout().addWidget(self.nav_row)

    def _vsep(self):
        s = QFrame(self.nav_row)
        s.setFrameShape(QFrame.VLine)
        s.setFixedSize(9, 22)
        s.setStyleSheet("QFrame { color: #cfd8dc; background: transparent; }")
        return s

    def _limit_rows(self, lay, title, axis):
        """'Title ........ [Auto]' then '[from] - [to]' (fits the panel width)."""
        head = QHBoxLayout()
        head.setContentsMargins(0, 2, 0, 0)
        lbl = QLabel(title, self.panel)
        lbl.setStyleSheet(FIELD_LABEL_STYLE)
        head.addWidget(lbl)
        head.addStretch(1)
        what = title.split(' ')[0].lower()
        auto = QToolButton(self.panel)
        auto.setText("Auto")
        auto.setCheckable(True)
        auto.setChecked(True)
        auto.setFixedHeight(26)
        auto.setCursor(Qt.PointingHandCursor)
        auto.setStyleSheet(AUTO_STYLE)
        auto.setToolTip(f"Auto (lit): the {what} axis follows the data (live window / whole log).\nTyping a limit, "
                        f"panning or zooming switches it off; click to return to automatic limits.")
        auto.clicked.connect(lambda checked, a=axis: self.on_auto_clicked(a, checked))
        head.addWidget(auto)
        lay.addLayout(head)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        unit = "seconds" if axis == 'x' else "mm / deg"
        boxes = []
        for which in ("from", "to"):
            e = QLineEdit(self.panel)
            e.setFixedHeight(28)
            e.setMinimumWidth(56)
            e.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            e.setPlaceholderText(which)
            e.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            e.setStyleSheet(LIMIT_STYLE_AUTO)
            e.setToolTip(f"{'Lower' if which == 'from' else 'Upper'} limit of the {what} axis ({unit}).\n"
                         f"Type a value and press Enter (decimal comma or point). This fixes the axis (Auto off); "
                         f"the limits stay during live updates.")
            e.textEdited.connect(lambda _t, box=e: self._editing.add(box))
            e.editingFinished.connect(lambda a=axis: self.on_limits_edited(a))
            e.textChanged.connect(lambda _t, a=axis, box=e: self._on_box_text_changed(a, box))
            try:
                from fcn_create_gui.touch_keyboard import register_touch_line_edit
                register_touch_line_edit(self.win, e, label_name=f"{title} {which}")
            except Exception:
                pass
            boxes.append(e)
            row.addWidget(e, 1)
            if which == "from":
                dash = QLabel("\u2013", self.panel)
                dash.setStyleSheet("color: #78909c; font-size: 13px; background: transparent;")
                row.addWidget(dash)
        lay.addLayout(row)
        return boxes[0], boxes[1], auto

    def _build_record_button(self, parent):
        w = self.win
        self.btn_record = QToolButton(parent)
        self.btn_record.setCheckable(True)
        self.btn_record.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.btn_record.setFixedHeight(32)
        self.btn_record.setCursor(Qt.PointingHandCursor)
        f = self.btn_record.font()
        f.setPixelSize(13)
        f.setBold(True)
        from PySide6.QtGui import QFontMetrics
        fm = QFontMetrics(f)
        self.btn_record.setMinimumWidth(max(fm.horizontalAdvance(RECORD_ON_TEXT),
                                            fm.horizontalAdvance(RECORD_OFF_TEXT)) + 34)
        self.btn_record.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.btn_record.clicked.connect(self.on_record_clicked)
        w.check_record_log.toggled.connect(lambda _c: self.sync_record())
        if getattr(w, 'PhOperFolder', None) is not None:
            w.PhOperFolder.textChanged.connect(lambda _t: self.sync_record())

    # ---------------------------------------------------------------- legacy widgets
    def hide_legacy(self):
        w = self.win
        # log_folder_container: the old row above the plot (apply_status_advanced_mode shows it in Advanced
        # mode; what is left in it - labels, Max Speed Adj - stays hidden)
        for name in ('status_checks_scroll', 'status_toolbar', 'check_record_log', 'button_load_log',
                     'button_load_gcode_ref', 'log_folder_container'):
            wid = getattr(w, name, None)
            if wid is not None and not wid.isHidden():
                wid.setVisible(False)

    def is_advanced(self):
        cb = getattr(self.win, 'check_advanced_mode', None)
        return bool(cb is not None and cb.isChecked())

    def on_mode_changed(self):
        self.hide_legacy()
        adv = self.is_advanced()
        for box in (self.plot_settings_box, self.datalog_box):
            if box.isHidden() == adv:
                box.setVisible(adv)
        self.sync_all()

    # ---------------------------------------------------------------- mirrors
    def _set_pill(self, key, checked):
        b = self.pills.get(key)
        if b is not None and b.isChecked() != bool(checked):
            b.blockSignals(True)
            b.setChecked(bool(checked))
            b.blockSignals(False)

    def _on_legacy_toggled(self, key, checked):
        self._set_pill(key, checked)
        self.update_title_states()

    def section_state(self, name):
        """'none' / 'some' / 'all' of the section's SHOWN curves selected (what a title click acts on)."""
        _title, keys, _box = self.sections[name]
        shown = [k for k in keys if not self.pill_cb[k].isHidden()]
        n_on = sum(1 for k in shown if self.pill_cb[k].isChecked())
        if not shown or n_on == 0:
            return 'none'
        return 'all' if n_on == len(shown) else 'some'

    def update_title_states(self):
        try:
            for name, (title, _keys, _box) in self.sections.items():
                state = self.section_state(name)
                if self._title_state.get(title) != state:
                    self._title_state[title] = state
                    title.setIcon(self._group_icons[state])
        except RuntimeError:
            self.alive = False

    def sync_all(self):
        w = self.win
        for key, cb in self.pill_cb.items():
            self._set_pill(key, cb.isChecked())
            b = self.pills[key]
            shown = not cb.isHidden()          # update_status_axes_layout decides the Basic / Advanced set
            if b.isHidden() == shown:
                b.setVisible(shown)
        for name, (title, keys, box) in self.sections.items():
            any_shown = any(not self.pill_cb[k].isHidden() for k in keys)
            target = box if box is not None else None
            if target is not None and target.isHidden() == any_shown:
                target.setVisible(any_shown)
            if box is None and title.isHidden() == any_shown:
                title.setVisible(any_shown)
        ref = getattr(w, 'check_show_reference', None)
        if ref is not None and self.ref_pill.isChecked() != ref.isChecked():
            self.ref_pill.blockSignals(True)
            self.ref_pill.setChecked(ref.isChecked())
            self.ref_pill.blockSignals(False)
        self.update_title_states()
        self.sync_record()

    def sync_colors_from_lines(self):
        lines = getattr(self.win, 'status_plot_lines', None) or {}
        if not lines:
            return
        from matplotlib.colors import to_hex
        for key, line in list(lines.items()):
            b = self.pills.get(key)
            if b is None:
                continue
            try:
                col = to_hex(line.get_color()).lower()
            except Exception:
                continue
            if col != self.pill_color.get(key):
                self.pill_color[key] = col
                b.setStyleSheet(pill_style(col))

    def sync_record(self):
        w = self.win
        cb = getattr(w, 'check_record_log', None)
        if cb is None:
            return
        on = bool(cb.isChecked())
        if self.btn_record.isChecked() != on:
            self.btn_record.blockSignals(True)
            self.btn_record.setChecked(on)
            self.btn_record.blockSignals(False)
        text = RECORD_ON_TEXT if on else RECORD_OFF_TEXT
        if self.btn_record.text() != text:
            self.btn_record.setText(text)
            self.btn_record.setStyleSheet(RECORD_ON_STYLE if on else RECORD_OFF_STYLE)
        folder = ''
        try:
            folder = w.PhOperFolder.text().strip()
        except Exception:
            pass
        if not folder:
            import os
            folder = os.path.join(os.path.expanduser("~"), "Desktop")
        state = ("Recording is ON: every G-code run is written to a data log file."
                 if on else "Recording is OFF: G-code runs are not written to a log file.")
        tip = (f"{state}\nFile name: log_DDMMYYYY_HH_MM_SS.csv (date and time of the run start)\n"
               f"Folder: {folder}  (set in the Data log section, Advanced mode)\n"
               f"Click to turn recording {'off' if on else 'on'}."
               + ("\nTurning it off during a run closes the current log file." if on else ""))
        if self.btn_record.toolTip() != tip:
            self.btn_record.setToolTip(tip)

    # ---------------------------------------------------------------- user actions: curves
    def on_pill_clicked(self, key, checked):
        cb = self.pill_cb.get(key)
        if cb is None:
            return
        cb.setChecked(bool(checked))
        _render(self.win)

    def on_reference_clicked(self, checked):
        ref = getattr(self.win, 'check_show_reference', None)
        if ref is None:
            return
        ref.setChecked(bool(checked))         # its toggled handler loads the job's G-code and redraws
        self.sync_all()

    def section_keys(self, title_btn):
        for name, (title, keys, _box) in self.sections.items():
            if title is title_btn:
                return name, [k for k in keys if not self.pill_cb[k].isHidden()]
        return None, []

    def on_title_clicked(self, title_btn):
        _name, keys = self.section_keys(title_btn)
        if not keys:
            return
        target = not all(self.pill_cb[k].isChecked() for k in keys)
        for k in keys:
            self.pill_cb[k].setChecked(target)
        _render(self.win)

    def on_record_clicked(self, checked):
        cb = getattr(self.win, 'check_record_log', None)
        if cb is not None:
            cb.setChecked(bool(checked))      # its toggled handler closes the log when turned off
        self.sync_record()

    # ---------------------------------------------------------------- Auto-sync: max speed adjustment
    def _on_auto_sync_toggled(self, checked):
        """Auto-sync turned on: it is switched off again at once (process_auto_sync_speed reads
        input_max_speed_adj on every dashboard tick while it is on, so it never runs with a value not yet
        confirmed) and the popup asks for the max speed adjustment; OK turns it on with that value."""
        if not checked or self._auto_sync_ok:
            return
        self.win.check_auto_sync.setChecked(False)   # the existing handler re-enables the manual speed controls
        QTimer.singleShot(0, self.ask_max_speed_adj)

    def ask_max_speed_adj(self):
        w = self.win
        if self._asking_max_adj or not self.alive:
            return False
        self._asking_max_adj = True
        try:
            lo, hi, dec = MAX_ADJ_RANGE
            cur = parse_number(w.input_max_speed_adj.text())
            cur = 20.0 if cur is None else min(hi, max(lo, cur))
            val, ok = QInputDialog.getDouble(
                w, "Auto-sync Speed",
                "Auto-sync changes the speed factor by at most this much (from 100 %); a larger correction turns "
                "Auto-sync off.\n\nMax speed adjustment (%):",
                cur, lo, hi, dec)
            if not ok:
                return False                # Auto-sync stays off
            val = min(hi, max(lo, round(float(val), dec)))
            w.input_max_speed_adj.setText(f"{val:g}")      # read by process_auto_sync_speed (float())
            self._auto_sync_ok = True
            try:
                w.check_auto_sync.setChecked(True)
            finally:
                self._auto_sync_ok = False
            return True
        except RuntimeError:
            self.alive = False
            return False
        finally:
            self._asking_max_adj = False

    # ---------------------------------------------------------------- axis limits
    def _ax(self):
        return getattr(self.win, 'ax_status', None)

    def _connect_canvas(self):
        c = self.win.statusCanvas
        c.mpl_connect('button_press_event', self._on_press)
        c.mpl_connect('button_release_event', self._on_release)
        c.mpl_connect('motion_notify_event', self._on_motion)
        c.mpl_connect('axes_leave_event', lambda _e: self.coord_label.setText(""))
        # Clear Plot Data (clear_status_plot_data: ax.clear() + draw_idle, no render_status_plot) is seen on
        # the draw it triggers, so the boxes / Auto / history are right even with no later redraw (Duet
        # disconnected, job over).  No click hook: init_buttons re-connects button_clear_plot.clicked.
        c.mpl_connect('draw_event', self._on_draw_event)
        self._ensure_lim_callbacks()

    def _ensure_lim_callbacks(self):
        """Connects the limit callbacks to the current ax.callbacks; True when the registry was new
        (ax.clear() - Clear plot, Start - makes a new one, and drops the old connections)."""
        ax = self._ax()
        if ax is None:
            return False
        if self.cb_registry is not ax.callbacks:
            first = self.cb_registry is None
            ax.callbacks.connect('xlim_changed', lambda _a: self.update_limit_boxes())
            ax.callbacks.connect('ylim_changed', lambda _a: self.update_limit_boxes())
            self.cb_registry = ax.callbacks
            return not first
        return False

    def _on_axes_cleared(self):
        """The axes were cleared (a new, empty data set): automatic limits on both axes, boxes showing the
        cleared axes' limits, and no Back / Forward history of the old data."""
        self.manual_x = None
        self.manual_y = None
        self.data_ref = getattr(self.win, 'status_plot_data', None)
        self.data_seen = True
        try:
            self.win.status_toolbar.update()          # clears matplotlib's view history
        except Exception:
            pass
        self.update_limit_boxes(force=True)
        self.update_nav_buttons()

    def _on_draw_event(self, _event):
        if not self.alive:
            return
        try:
            if self._ensure_lim_callbacks():
                self._on_axes_cleared()
        except RuntimeError:
            self.alive = False

    def _nav_mode(self):
        tb = getattr(self.win, 'status_toolbar', None)
        try:
            return str(getattr(tb.mode, 'value', tb.mode) or '')
        except Exception:
            return ''

    def _on_press(self, event):
        ax = self._ax()
        if ax is None or not self._nav_mode():
            return
        self.dragging = True
        self.press_lims = (tuple(ax.get_xlim()), tuple(ax.get_ylim()))

    def _on_release(self, event):
        if not self.dragging:
            return
        QTimer.singleShot(0, self._capture_after_nav)

    def _on_motion(self, event):
        try:
            if event.inaxes is self._ax() and event.xdata is not None and event.ydata is not None:
                self.coord_label.setText(f"t = {format_number(event.xdata, 10)} s    "
                                         f"value = {format_number(event.ydata, 10)}")
            elif self.coord_label.text():
                self.coord_label.setText("")
        except RuntimeError:
            pass

    def _capture_after_nav(self):
        """After a pan / zoom drag: the axes whose limits changed become manual (Auto off)."""
        ax = self._ax()
        before = self.press_lims
        self.dragging = False
        self.press_lims = None
        if ax is None or before is None:
            return
        self._take_view(before)

    def _take_view(self, before):
        ax = self._ax()
        x, y = tuple(ax.get_xlim()), tuple(ax.get_ylim())
        changed = False
        if before is None or any(abs(a - b) > 1e-12 for a, b in zip(x, before[0])):
            self.manual_x = x
            changed = True
        if before is None or any(abs(a - b) > 1e-12 for a, b in zip(y, before[1])):
            self.manual_y = y
            changed = True
        if changed:
            self.update_limit_boxes()
        self.update_nav_buttons()

    def update_nav_buttons(self):
        tb = getattr(self.win, 'status_toolbar', None)
        mode = self._nav_mode()
        for b, m in ((self.btn_pan, 'pan/zoom'), (self.btn_zoom, 'zoom rect')):
            if b.isChecked() != (mode == m):
                b.setChecked(mode == m)
        try:
            stack = tb._nav_stack
            pos, n = stack._pos, len(stack)
            self.btn_back.setEnabled(n > 0 and pos > 0)
            self.btn_forward.setEnabled(n > 0 and pos < n - 1)
        except Exception:
            self.btn_back.setEnabled(True)
            self.btn_forward.setEnabled(True)

    def on_pan(self):
        self.win.status_toolbar.pan()
        self.update_nav_buttons()

    def on_zoom(self):
        self.win.status_toolbar.zoom()
        self.update_nav_buttons()

    def _history(self, step):
        ax = self._ax()
        if ax is None:
            return
        before = (tuple(ax.get_xlim()), tuple(ax.get_ylim()))
        (self.win.status_toolbar.back if step < 0 else self.win.status_toolbar.forward)()
        self._take_view(before)
        self.apply_limits(draw=True)

    def on_back(self):
        self._history(-1)

    def on_forward(self):
        self._history(+1)

    def on_save(self):
        self.win.status_toolbar.save_figure()

    def on_reset(self):
        self.manual_x = None
        self.manual_y = None
        self._refit()
        try:
            self.win.status_toolbar.update()          # clears the Back / Forward history
        except Exception:
            pass
        self.update_limit_boxes()
        self.update_nav_buttons()

    def _refit(self):
        """Automatic limits again: (0, 1) is the 'uninitialised' x range render_status_plot refits from."""
        ax = self._ax()
        if ax is None:
            return
        if self.manual_x is None:
            ax.set_xlim(0.0, 1.0)
        _render(self.win)
        self.apply_limits(draw=True)

    def on_auto_clicked(self, axis, checked):
        if checked:
            if axis == 'x':
                self.manual_x = None
            else:
                self.manual_y = None
            self._refit()
        else:
            ax = self._ax()
            if ax is not None:                         # Auto off: keep the current view fixed
                if axis == 'x':
                    self.manual_x = tuple(ax.get_xlim())
                else:
                    self.manual_y = tuple(ax.get_ylim())
        self.update_limit_boxes()

    def _on_box_text_changed(self, axis, box):
        # Typed text waits for Enter / leaving the box; text set from outside (the touch keyboard) is
        # applied at once
        if self._updating_boxes or box in self._editing:
            return
        self.on_limits_edited(axis)

    def on_limits_edited(self, axis):
        if self._updating_boxes:
            return
        ax = self._ax()
        if ax is None:
            return
        lo_box, hi_box = (self.x_from, self.x_to) if axis == 'x' else (self.y_from, self.y_to)
        self._editing.discard(lo_box)
        self._editing.discard(hi_box)
        cur = ax.get_xlim() if axis == 'x' else ax.get_ylim()
        lo, hi = parse_number(lo_box.text()), parse_number(hi_box.text())
        lo = cur[0] if lo is None and lo_box.text().strip() == '' else lo
        hi = cur[1] if hi is None and hi_box.text().strip() == '' else hi
        if lo is None or hi is None or lo == hi:
            self.update_limit_boxes(force=True)      # not a number: show the current limits again
            return
        if lo > hi:
            lo, hi = hi, lo
        new = (float(lo), float(hi))
        old = self.manual_x if axis == 'x' else self.manual_y
        if old is not None and all(abs(a - b) < 1e-12 for a, b in zip(old, new)):
            self.update_limit_boxes(force=True)
            return
        if axis == 'x':
            self.manual_x = new
        else:
            self.manual_y = new
        self.apply_limits(draw=True)
        self.update_limit_boxes(force=True)

    def update_limit_boxes(self, force=False):
        ax = self._ax()
        if ax is None or not self.alive:
            return
        self._updating_boxes = True
        try:
            for (lo_box, hi_box, auto, lims, manual) in (
                    (self.x_from, self.x_to, self.x_auto, ax.get_xlim(), self.manual_x),
                    (self.y_from, self.y_to, self.y_auto, ax.get_ylim(), self.manual_y)):
                span = lims[1] - lims[0]
                for box, v in ((lo_box, lims[0]), (hi_box, lims[1])):
                    if (box in self._editing or box.hasFocus()) and not force:
                        continue
                    txt = format_number(v, span)
                    if box.text() != txt:
                        box.setText(txt)
                    style = LIMIT_STYLE_AUTO if manual is None else LIMIT_STYLE_MANUAL
                    if box.styleSheet() != style:
                        box.setStyleSheet(style)
                if auto.isChecked() != (manual is None):
                    auto.setChecked(manual is None)
        except RuntimeError:
            self.alive = False
        finally:
            self._updating_boxes = False

    def _auto_y_for_x(self, x_lo, x_hi):
        """y range of the shown curves inside a manual time range (Auto y with a fixed x range)."""
        import numpy as np
        w = self.win
        lo, hi = None, None
        for d in (getattr(w, 'status_plot_lines', None) or {}, getattr(w, 'status_ref_lines', None) or {}):
            for line in d.values():
                try:
                    if not line.get_visible():
                        continue
                    xs = np.asarray(line.get_xdata(), dtype=float)
                    ys = np.asarray(line.get_ydata(), dtype=float)
                    if xs.size == 0 or xs.size != ys.size:
                        continue
                    m = (xs >= x_lo) & (xs <= x_hi) & np.isfinite(ys)
                    if not m.any():
                        continue
                    a, b = float(ys[m].min()), float(ys[m].max())
                    lo = a if lo is None else min(lo, a)
                    hi = b if hi is None else max(hi, b)
                except Exception:
                    continue
        if lo is None:
            return None
        pad = (hi - lo) * 0.1 if hi != lo else 1.0
        return lo - pad, hi + pad

    def apply_limits(self, draw=False):
        """Re-applies the manual limits (render_status_plot sets its own on every update)."""
        ax = self._ax()
        if ax is None:
            return False
        x_before = tuple(ax.get_xlim())
        changed = False
        if self.manual_x is not None:
            if any(abs(a - b) > 1e-12 for a, b in zip(ax.get_xlim(), self.manual_x)):
                ax.set_xlim(*self.manual_x)
                changed = True
        if self.manual_y is not None:
            if any(abs(a - b) > 1e-12 for a, b in zip(ax.get_ylim(), self.manual_y)):
                ax.set_ylim(*self.manual_y)
                changed = True
        elif self.manual_x is not None:
            fit = self._auto_y_for_x(*self.manual_x)
            if fit is not None and any(abs(a - b) > 1e-9 for a, b in zip(ax.get_ylim(), fit)):
                ax.set_ylim(*fit)
                changed = True
        if tuple(ax.get_xlim()) != x_before:
            try:
                from fcn_monitor import fcn_duet
                if fcn_duet._refresh_probe_key(self.win):     # probe colour key for the shown range
                    self.win.fig_status.tight_layout()
            except Exception:
                pass
        if (changed or draw) and getattr(self.win, 'statusCanvas', None) is not None:
            self.win.statusCanvas.draw_idle()
        return changed

    # ---------------------------------------------------------------- redraw hooks
    def before_render(self):
        ax = self._ax()
        if ax is None:
            return None
        return (tuple(ax.get_xlim()), tuple(ax.get_ylim()))

    def after_render(self, before):
        w = self.win
        ax = self._ax()
        if ax is None:
            return
        if self._ensure_lim_callbacks():
            self._on_axes_cleared()                    # Start / Clear plot before this redraw
        data = getattr(w, 'status_plot_data', None)
        if not self.data_seen:
            self.data_seen = True
            self.data_ref = data
        elif data is not self.data_ref:
            # A new data set (Clear plot, new run, loaded log): automatic limits again
            self.data_ref = data
            if self.manual_x is not None or self.manual_y is not None:
                self.manual_x = None
                self.manual_y = None
        if self.dragging and before is not None:
            # A pan / zoom drag in progress: keep the view the mouse is moving (the redraw would snap it)
            if tuple(ax.get_xlim()) != before[0]:
                ax.set_xlim(*before[0])
            if tuple(ax.get_ylim()) != before[1]:
                ax.set_ylim(*before[1])
        else:
            self.apply_limits()
        self.sync_all()
        self.sync_colors_from_lines()
        self.update_limit_boxes()


def modernise_status_tab(self):
    """Adds the modern Status controls to the Status tab built by build_status_tab(self)."""
    st = getattr(self, 'status_modern', None)
    if isinstance(st, ModernStatus):
        return st
    if getattr(self, 'statusCanvas', None) is None or getattr(self, 'check_advanced_mode', None) is None:
        return None
    # Never raises: the caller (on_main_tab_changed) must still mark the Status tab as built, or the next
    # visit would build it again (duplicate pollers).  On an error the legacy controls stay as they are.
    try:
        install_render_wrapper()
        st = ModernStatus(self)
        self.status_modern = st
        st.build()
        return st
    except Exception:
        import traceback
        print("Status tab: the modern controls could not be built:\n" + traceback.format_exc())
        st = getattr(self, 'status_modern', None)
        if isinstance(st, ModernStatus):
            st.alive = False                   # the render wrapper then runs the original only
        return None
