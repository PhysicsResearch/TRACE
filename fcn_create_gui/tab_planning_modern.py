"""
Modern controls for the Planning tab (added on top of the existing tab, which is left unchanged).

``modernise_planning_tab(self)`` is called once, right after ``build_planning_tab(self)``.  It gives the Planning
tab the look of the modern Status tab (tab_status_modern.py, whose helpers it reuses):

1. Device: a two-segment toggle 'Lung Phantom | Motion Platform' instead of the visible Device Type combo.  Clicking
   the other segment sets the (hidden) combo_device index, so every existing handler runs exactly as before.  The
   toggle follows the combo also when code sets it with blocked signals (imports, Undo, the Settings tab combo).
2. Curve Options 'Axis': toggle pills (lit in the plot colour of the axis) instead of the checkboxes, per device as
   before, Yaw shown as a disabled pill.  The legacy checkboxes (create_curve_axis_checkboxes) stay the source of
   truth: a pill click sets its checkbox, whose own handler applies the linear / rotational rule.
3. Plot curves: a white side card on the RIGHT of the graph with pills grouped as on the Status page ('Lung Phantom'
   X Y Z; 'Motion Platform' with 'Platform position' LAT SI AP Roll Pitch Yaw and 'Individual axes' A B C D 'a 'c 'e
   'f; 'Other axes' for any other column), only for the columns the legacy row has.  Clickable titles with a
   tri-state box select / deselect all.  'Select all' / 'Clear all' sit in the card footer (they click the legacy
   buttons).  Pill colour = colour of the plotted line.
4. Under the graph: 'Position —', 'Velocity --', 'Acceleration ···' and 'Margins' toggle pills (mirroring
   check_show_pos / _vel / _acc and the trigger's check_show_trg_margins), the navigation icons of the Status page
   (driving the hidden matplotlib toolbar) with a pointer readout, and Export GCODE / Upload to Duet (they click the
   legacy buttons).  White card instead of the grey strips.
5. Table: the plan table moves from the right of the option tabs into a last sub-tab 'Table'.  Opening it ticks the
   hidden legacy 'Show Table' checkbox (toggle_planning_table_visibility shows the table), leaving it unticks it; code
   that sets the checkbox switches the tab.
6. Curve Options in two columns: the fields (3 equal columns), Axis and Add Curve / Import File / Clear All on the
   left; on the right a white 'Pauses & trigger' card: Once | Repeat, the exclusive kinds Wait Radiation / Wait User /
   Trigger On / Trigger Off, Time (s) (Once) or the periodic fields (Repeat: Every P, For D, First at, Range, Combine
   - the former 'Periodic' sub-tab, whose own widgets are moved here; the tab is hidden, its page stays alive), Add /
   Clear and the status line.  Repeat-mode Add clicks the legacy 'Apply Periodic'; the gray periodic preview shows
   while Repeat is on in the Curve tab (tab_planning_trigger._active_preview / trg_draw_overlay wrapped once).
7. Motion Platform: the legacy 'Offset Rot. (mm)' fields in a 'Rotation centre (mm)' card (reference point for Roll /
   Pitch / Yaw).  White Curve page and Curve Options card (no grey background).

The legacy row under the graph (create_plot_checkboxes_widget) is rebuilt by rebuild_axis_checkboxes on every device
switch / import / Clear All; it stays in place, hidden, and is the single source of truth.  fcn_plan.fcn_create's
module globals rebuild_axis_checkboxes and update_plot are wrapped once (the originals run unchanged first): after
them the modern controls re-bind to the new legacy widgets and refresh their mirrors.  Every caller looks those
functions up at call time (fcn_create's own calls use the module globals, fcn_import imports them inside the
functions), so all paths are covered.
"""

import functools

import numpy as np
from PySide6.QtCore import Qt, QSize, QObject, QEvent, QByteArray, QTimer
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QToolButton, QLabel, QScrollArea, QFrame, QSizePolicy,
    QButtonGroup, QStyledItemDelegate
)

from fcn_create_gui.tab_status_modern import (
    pill_style, make_icon, make_group_icon, format_number, _find_layout_with, _AXIS_TIPS,
    TITLE_STYLE, SUBTITLE_STYLE, NAV_BUTTON_STYLE, SECTION_STYLE, SEPARATOR_STYLE, CARD_BORDER,
    NAV_ICON_PX, NAV_BUTTON_PX, _is_light, QSvgRenderer,
)

# Same colours as fcn_create.update_plot (AXIS_COLORS there is local); re-synced from the drawn lines after each plot
PLOT_COLORS = {
    'X': '#1976d2', 'Y': '#f57c00', 'Z': '#388e3c',
    'LAT': '#1976d2', 'SI': '#f57c00', 'AP': '#388e3c', 'Roll': '#7b1fa2', 'Pitch': '#d32f2f', 'Yaw': '#0097a7',
    'A': '#5c6bc0', 'B': '#26a69a', 'C': '#ffa726', 'D': '#ab47bc',
    "'a": "#8d6e63", "'c": "#78909c", "'e": "#5c6bc0", "'f": "#26a69a",
}
OTHER_COLOR = '#455a64'
PHANTOM_KEYS = ['X', 'Y', 'Z']
POSITION_KEYS = ['LAT', 'SI', 'AP', 'Roll', 'Pitch', 'Yaw']
INDIVIDUAL_KEYS = ['A', 'B', 'C', 'D', "'a", "'c", "'e", "'f"]
KNOWN_KEYS = set(PHANTOM_KEYS + POSITION_KEYS + INDIVIDUAL_KEYS)
DEVICE_AXES = {'Lung Phantom': set(PHANTOM_KEYS), 'Motion Platform': set(POSITION_KEYS)}   # legacy Curve 'Axis' sets
LINEAR_AXES = {"SI", "LAT", "AP", "X", "Y", "Z"}
ROTATIONAL_AXES = {"Roll", "Pitch", "Yaw"}

# (legacy attribute, pill text, colour of the legacy checkbox text, tooltip)
KINEMATIC_PILLS = [
    ('check_show_pos', "Position —", '#1565c0',
     "Show the positions as continuous solid lines (—).\nAlso shows the position columns of the table."),
    ('check_show_vel', "Velocity --", '#0277bd',
     "Show the velocities as dashed lines (--).\nAlso shows the velocity columns of the table."),
    ('check_show_acc', "Acceleration ···", '#c2185b',
     "Show the accelerations as dotted lines (···).\nAlso shows the acceleration columns of the table."),
    ('check_show_trg_margins', "Margins", '#616161',
     "Show the margins of the 'Trigger' tab (dashed, axis colour; with Position shown) and shade in gray where the "
     "trigger would be on (live preview before Apply).\nIn Repeat mode (Curve tab, Pauses & trigger) the repeated "
     "pattern is previewed in gray anyway."),
]

DEVICE_SEG_STYLE = """
    QToolButton {{
        background-color: #ffffff; color: #546e7a; border: 1px solid #b0bec5;
        font-size: 15px; font-weight: bold; padding: 2px 12px; {radius}
    }}
    QToolButton:hover {{ background-color: #e3f2fd; color: #1565c0; border: 1px solid #1565c0; }}
    QToolButton:checked {{ background-color: #1565c0; color: #ffffff; border: 1px solid #1565c0; }}
    QToolButton:checked:hover {{ background-color: #0d47a1; border: 1px solid #0d47a1; }}
"""
_SEG_LEFT = ("border-top-left-radius: 6px; border-bottom-left-radius: 6px; "
             "border-top-right-radius: 0px; border-bottom-right-radius: 0px;")
_SEG_RIGHT = ("border-top-right-radius: 6px; border-bottom-right-radius: 6px; "
              "border-top-left-radius: 0px; border-bottom-left-radius: 0px;")
_SEG_MID = "border-radius: 0px;"
ACTION_STYLE = """
    QToolButton {{ background-color: {bg}; color: #ffffff; border: none; border-radius: 6px;
                  font-size: 13px; font-weight: bold; padding: 2px 14px; }}
    QToolButton:hover {{ background-color: {hover}; }}
    QToolButton:pressed {{ background-color: {hover}; padding-top: 3px; padding-left: 15px; }}
    QToolButton:disabled {{ background-color: #cfd8dc; color: #90a4ae; }}
"""
OUTLINE_STYLE = """
    QToolButton { background-color: #ffffff; color: #37474f; border: 1px solid #cfd8dc; border-radius: 6px;
                  font-size: 13px; font-weight: bold; padding: 2px 8px; }
    QToolButton:hover { background-color: #e3f2fd; border: 1px solid #1565c0; color: #1565c0; }
    QToolButton:pressed { background-color: #bbdefb; }
"""
DEVICE_HEIGHT = 40          # as the legacy combo (setMinimumHeight(40))
AXIS_PILL_HEIGHT = 32
AXIS_PILL_MIN_WIDTH = 64
PILL_HEIGHT = 28
ROW_HEIGHT = NAV_BUTTON_PX
ACTION_HEIGHT = 32
PANEL_WIDTH = 216           # side card (Status: 236; a little narrower here so the page minimum width does not grow)
EVENT_HEIGHT = 40           # Add Curve / Import File / Clear All (as the boxes)
EVENT_TOGGLE_HEIGHT = 36    # Wait Radiation / Wait User / Trigger On / Trigger Off, Add, Clear (pauses & trigger card)
SEG_HEIGHT = 30             # Once | Repeat, Whole plan | From - To, Combine segments
TIME_BOX_WIDTH = 120        # Time (s) box of the pauses & trigger card
EVENT_CARD_MIN_WIDTH = 470  # pauses & trigger card (right column of Curve Options)
COMPACT_GB_MARGIN = 6       # Curve Options group box: top / bottom margin (legacy 10)
COMPACT_ROW_SPACING = 6     # Curve Options fields: vertical spacing between the rows (legacy 10)
REPEAT_PREVIEW_MS = 250     # live gray preview of the Repeat pattern (debounced, as the legacy preview)
CARD_STYLE = "QFrame#{name} {{ background: #ffffff; border: 1px solid " + CARD_BORDER + "; border-radius: 6px; }}"
WHITE_STYLE = "QWidget#{name} {{ background: #ffffff; }}"
GROUP_CARD_STYLE = ("QGroupBox#pmCurveOptions { background: #ffffff; border: 1px solid " + CARD_BORDER + "; "
                    "border-radius: 6px; margin-top: 24px; font-weight: bold; font-size: 16px; }"
                    "QGroupBox#pmCurveOptions::title { subcontrol-origin: margin; subcontrol-position: top left; "
                    "left: 6px; top: 2px; padding: 0px 4px; color: #263238; }")
FIELD_STYLE = "font-weight: bold; font-size: 14px; background: transparent;"
SMALL_FIELD_STYLE = "font-weight: bold; font-size: 14px; color: #37474f; background: transparent;"
NOTE_STYLE = "font-size: 12px; color: #546e7a; background: transparent;"
MODE_SEG_STYLE = """
    QToolButton {{
        background-color: #ffffff; color: #546e7a; border: 1px solid #b0bec5;
        font-size: 14px; font-weight: bold; padding: 2px 12px; {radius}
    }}
    QToolButton:hover {{ background-color: #e3f2fd; color: #1565c0; border: 1px solid #1565c0; }}
    QToolButton:checked {{ background-color: #1565c0; color: #ffffff; border: 1px solid #1565c0; }}
    QToolButton:checked:hover {{ background-color: #0d47a1; border: 1px solid #0d47a1; }}
"""
OPTION_SEG_STYLE = """
    QToolButton {{
        background-color: #ffffff; color: #546e7a; border: 1px solid #b0bec5;
        font-size: 14px; font-weight: bold; padding: 2px 10px; {radius}
    }}
    QToolButton:hover {{ background-color: #f1f8fe; color: #1565c0; }}
    QToolButton:checked {{ background-color: #e3f2fd; color: #0d47a1; border: 1px solid #1565c0; }}
"""
# Rotation centre (Motion Platform): the legacy 'Offset Rot.' fields input_offset_*_plan in a card
ROT_TITLE = "Rotation centre (mm)"
ROT_SUBTITLE = "reference point for Roll / Pitch / Yaw"
ROT_TOOLTIP = (
    "Rotation centre: the reference point the platform turns about for Roll, Pitch and Yaw.\n"
    "AP: height of that point above the four lift supports A, B, C, D (mm, default 0 mm: the platform turns about\n"
    "the supports).  With AP > 0 the LAT / SI axes follow by AP·sin(angle) during Roll / Pitch, so the platform\n"
    "turns about that point instead of about the supports.\n"
    "LAT / SI: offset of that point (mm), added to the LAT / SI positions.\n"
    "Same values as 'Offset Rot.' in the Control tab (kept in sync). They are not saved: every start begins with\n"
    "AP 0, LAT 0, SI 0. A plan without Roll / Pitch / Yaw does not depend on AP.")

# Pause / trigger row: (key, text, colour, legacy Add button, legacy Clear button, what Clear removes)
EVENT_KINDS = [
    ('rad', "Wait Radiation", '#d84315', 'button_wait_radiation', 'button_clear_rad',
     "every Wait Radiation pause from the plan (as 'Clear Rad Pauses')"),
    ('usr', "Wait User", '#f9a825', 'button_wait_user', 'button_clear_user',
     "every Wait User pause from the plan (as 'Clear Usr Pauses')"),
    ('on', "Trigger On", '#43a047', 'button_trigger_on', 'button_clear_trigger',
     "every trigger switch from the plan, i.e. all trigger windows (as 'Clear Trigger'); pauses are kept"),
    ('off', "Trigger Off", '#607d8b', 'button_trigger_off', 'button_clear_trigger',
     "every trigger switch from the plan, i.e. all trigger windows (as 'Clear Trigger'); pauses are kept"),
]
EVENT_DEFAULT = 'rad'
LEGACY_EVENT_BUTTONS = ['button_undo_curve', 'button_wait_radiation', 'button_wait_user', 'button_clear_rad',
                        'button_clear_user', 'button_trigger_on', 'button_trigger_off', 'button_clear_trigger']
# Repeat mode: the kind -> the action of the legacy Periodic tab (trg_per_action)
REPEAT_ACTIONS = {'rad': 'wait_rad', 'usr': 'wait_user', 'on': 'trigger_on', 'off': 'beam_off'}
EVENT_MODES = [('once', "Once", "Once: Add places one pause / trigger switch at Time (s) (nearest plan row)."),
               ('repeat', "Repeat", "Repeat: Add places the selected kind periodically: first at 'First at', then "
                                    "every P seconds inside the range\n(the former 'Periodic' tab).  The pattern is "
                                    "previewed in gray in the plot before Add.")]
RANGE_SEGS = [('full', "Whole plan", "The pattern covers the whole plan."),
              ('subset', "From – To", "The pattern covers only From (s) to To (s).")]
COMBINE_SEGS = [('add', "Union", "Union (former 'Add'): on where the new or the existing windows are on."),
                ('replace', "Replace", "Replace in range: inside the range only the new windows; outside unchanged."),
                ('intersect', "Only where both", "Only where both: inside the range on only where the new and the "
                                                 "existing windows are on (intersection); outside unchanged.")]
EVENT_HINT = ("Pick a kind, set Time (s), press Add (nearest plan row). Clear removes all of the selected kind. "
              "Right-click a pause line or a green trigger window in the plot to delete or adjust it.")
EVENT_HINT_REPEAT = ("Repeat: Add places the selected kind at 'First at' + k·P inside the range (gray preview in the "
                     "plot). Clear removes all of the selected kind. Right-click a pause line or a green trigger "
                     "window in the plot to delete or adjust it.")
UNDO_TOOLTIP = "Undo (one step)"
UNDO_SVG = '<path d="M3 4 V10 H9"/><path d="M5.1 15.2 A8 8 0 1 0 6.4 6.4 L3 10"/>'
ADD_STYLE = """
    QToolButton { background-color: #1565c0; color: #ffffff; border: none; border-radius: 6px;
                  font-size: 14px; font-weight: bold; padding: 2px 18px; }
    QToolButton:hover { background-color: #0d47a1; }
    QToolButton:pressed { background-color: #0d47a1; padding-top: 3px; padding-left: 19px; }
"""
CLEAR_EVENT_STYLE = """
    QToolButton { background-color: #ffffff; color: #c62828; border: 2px solid #ef9a9a; border-radius: 6px;
                  font-size: 14px; font-weight: bold; padding: 2px 14px; }
    QToolButton:hover { background-color: #ffebee; border: 2px solid #c62828; }
    QToolButton:pressed { background-color: #ffcdd2; }
"""
UNDO_STYLE = """
    QToolButton { background-color: #ffffff; border: 1px solid #b0bec5; border-radius: 6px; padding: 4px; }
    QToolButton:hover { background-color: #fff3e0; border: 1px solid #f57c00; }
    QToolButton:pressed { background-color: #ffe0b2; }
    QToolButton:disabled { background-color: #f5f5f5; border: 1px solid #e0e0e0; }
"""


def _event_style(color):
    """Outline toggle with a coloured contour; filled when selected."""
    c = QColor(color)
    txt_off = c.darker(140).name() if _is_light(color) else c.name()
    txt_on = '#212121' if _is_light(color) else '#ffffff'
    return f"""
        QToolButton {{ background-color: #ffffff; color: {txt_off}; border: 2px solid {c.name()}; border-radius: 6px;
                      font-size: 14px; font-weight: bold; padding: 2px 12px; }}
        QToolButton:hover {{ background-color: rgba({c.red()}, {c.green()}, {c.blue()}, 30); }}
        QToolButton:checked {{ background-color: {c.name()}; color: {txt_on}; }}
    """


def _svg_icon(body, color, disabled='#b0bec5'):
    icon = QIcon()
    for px in (24, 48):
        for col, mode in ((color, QIcon.Normal), (color, QIcon.Active), (disabled, QIcon.Disabled)):
            svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{col}" '
                   f'stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">{body}</svg>')
            pm = QPixmap(px, px)
            pm.fill(Qt.transparent)
            if QSvgRenderer is not None:
                r = QSvgRenderer(QByteArray(svg.encode('utf-8')))
                p = QPainter(pm)
                p.setRenderHint(QPainter.Antialiasing, True)
                r.render(p)
                p.end()
            icon.addPixmap(pm, mode, QIcon.Off)
    return icon


def _segmented(parent, items, style, height, on_click):
    """Segmented exclusive toggle: items = [(key, text, tooltip)] -> (widget, {key: button}).  on_click(key)."""
    box = QWidget(parent)
    h = QHBoxLayout(box)
    h.setContentsMargins(0, 0, 0, 0)
    h.setSpacing(0)
    group = QButtonGroup(box)
    group.setExclusive(True)
    buttons = {}
    n = len(items)
    for i, (key, text, tip) in enumerate(items):
        b = QToolButton(box)
        b.setText(text)
        b.setCheckable(True)
        b.setToolButtonStyle(Qt.ToolButtonTextOnly)
        b.setFixedHeight(height)
        b.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        b.setCursor(Qt.PointingHandCursor)
        b.setToolTip(tip)
        radius = _SEG_LEFT if i == 0 else (_SEG_RIGHT if i == n - 1 else _SEG_MID)
        b.setStyleSheet(style.format(radius=radius))
        b.clicked.connect(lambda _c=False, k=key: on_click(k))
        group.addButton(b)
        h.addWidget(b)
        buttons[key] = b
    box._pm_group = group
    return box, buttons


def _set_checked_quiet(button, on):
    if button.isChecked() != bool(on):
        button.blockSignals(True)
        button.setChecked(bool(on))
        button.blockSignals(False)


def _take_widget(root_layout, widget):
    """Removes widget from the layout under root_layout that holds it (if any)."""
    lay, _idx = _find_layout_with(root_layout, widget)
    if lay is not None:
        lay.removeWidget(widget)


def _card(parent, name):
    f = QFrame(parent)
    f.setObjectName(name)
    f.setStyleSheet(CARD_STYLE.format(name=name))
    return f


class _EnabledWatcher(QObject):
    """Calls ``callback`` when the watched widget's enabled state changes (legacy Undo -> Undo icon)."""

    def __init__(self, target, callback):
        super().__init__(target)
        self._cb = callback
        target.installEventFilter(self)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.EnabledChange:
            try:
                self._cb()
            except RuntimeError:
                pass
        return False


def parse_cell_number(text):
    """Float of a numeric table cell typed with a decimal point or a decimal comma ('3,5', ' -2.25 ', '1e-3'),
    None when it is no number."""
    s = str(text).strip().replace('−', '-')
    if not s:
        return None
    if ',' in s and '.' not in s and s.count(',') == 1:
        s = s.replace(',', '.')
    try:
        v = float(s)
    except ValueError:
        return None
    return v if np.isfinite(v) else None


class _NumericCellDelegate(QStyledItemDelegate):
    """Item delegate of the plan table: numeric columns get '.' decimals (a typed '3,5' is written as '3.5'); text
    that is no number is not written (the cell keeps its value, the status line says so).  'Command' and the derived
    Vel. / Acc. columns are written as typed (legacy behaviour)."""

    def __init__(self, pm, table):
        super().__init__(table)
        self._pm = pm
        self._table = table

    def _header(self, index):
        it = self._table.horizontalHeaderItem(index.column())
        return it.text() if it is not None else ''

    def setModelData(self, editor, model, index):
        header = self._header(index)
        text_of = getattr(editor, 'text', None)
        if header == 'Command' or header.startswith(('Vel.', 'Acc.')) or not callable(text_of):
            super().setModelData(editor, model, index)
            return
        text = text_of()
        v = parse_cell_number(text)
        if v is None:
            try:
                from fcn_create_gui.tab_planning_trigger import _trg_status
                _trg_status(self._pm.win, f"Table: '{text}' is not a number; the {header} cell keeps its value.",
                            "warn")
            except Exception:
                pass
            return
        norm = str(text).strip().replace('−', '-').replace(',', '.')
        model.setData(index, norm, Qt.EditRole)


def _plot_color(key):
    return PLOT_COLORS.get(key, OTHER_COLOR)


def _fc():
    from fcn_plan import fcn_create
    return fcn_create


# ----------------------------------------------------------------------------------------- hooks
def install_hooks():
    """Wraps fcn_plan.fcn_create.rebuild_axis_checkboxes and update_plot once: the original runs unchanged, then the
    modern Planning controls of that window (if any) re-bind / refresh."""
    fc = _fc()
    for name in ('rebuild_axis_checkboxes', 'update_plot'):
        cur = getattr(fc, name)
        if getattr(cur, '_pm_wrapper', False):
            continue
        setattr(fc, name, _make_wrapper(cur))
    # Repeat mode of the pauses & trigger card: the periodic gray preview while it is on in the Curve tab (as while
    # the former 'Periodic' tab was open).  tab_planning_trigger looks both functions up at call time (module global
    # _active_preview inside trg_draw_overlay; update_plot imports trg_draw_overlay when it runs)
    from fcn_create_gui import tab_planning_trigger as tpt
    if not getattr(tpt._active_preview, '_pm_wrapper', False):
        tpt._active_preview = _wrap_active_preview(tpt._active_preview)
    if not getattr(tpt.trg_draw_overlay, '_pm_wrapper', False):
        tpt.trg_draw_overlay = _wrap_draw_overlay(tpt.trg_draw_overlay)


def _repeat_preview_on(self):
    pm = getattr(self, 'planning_modern', None)
    if not isinstance(pm, ModernPlanning) or not pm.alive:
        return False
    try:
        return pm.repeat_preview_active()
    except RuntimeError:
        pm.alive = False
        return False


def _wrap_active_preview(original):
    @functools.wraps(original)
    def wrapper(self):
        return "periodic" if _repeat_preview_on(self) else original(self)

    wrapper._pm_wrapper = True
    wrapper._pm_original = original
    return wrapper


def _wrap_draw_overlay(original):
    """Repeat mode: the periodic preview is drawn also with Margins off (it previews what Add does)."""
    @functools.wraps(original)
    def wrapper(self, *args, **kwargs):
        if not _repeat_preview_on(self) or getattr(self, 'trg_show_margins', False):
            return original(self, *args, **kwargs)
        had = hasattr(self, 'trg_show_margins')
        old = getattr(self, 'trg_show_margins', None)
        self.trg_show_margins = True
        try:
            return original(self, *args, **kwargs)
        finally:
            if had:
                self.trg_show_margins = old
            else:
                delattr(self, 'trg_show_margins')

    wrapper._pm_wrapper = True
    wrapper._pm_original = original
    return wrapper


def _make_wrapper(original):
    @functools.wraps(original)
    def wrapper(self, *args, **kwargs):
        result = original(self, *args, **kwargs)
        pm = getattr(self, 'planning_modern', None)
        if isinstance(pm, ModernPlanning) and pm.alive:
            try:
                pm.after_legacy_update()
            except RuntimeError:            # widgets already deleted (window closed)
                pm.alive = False
            except Exception as e:
                print(f"Planning controls: could not refresh after {original.__name__}: {e}")
        return result

    wrapper._pm_wrapper = True
    wrapper._pm_original = original
    return wrapper


# ----------------------------------------------------------------------------------------- the controls
class ModernPlanning:
    """State and widgets of the modern Planning controls of one window (self.planning_modern)."""

    def __init__(self, win):
        self.win = win
        self.alive = True
        # Curve Options 'Axis'
        self.axis_pills = {}            # axis -> pill
        self.axis_cbs = {}              # axis -> legacy checkbox it mirrors
        self._axis_dict = None          # create_curve_axis_checkboxes object bound last
        # plot curves (side card)
        self.pills = {}                 # column -> pill
        self.pill_cb = {}               # column -> legacy checkbox (create_axis_checkboxes)
        self.pill_color = {}
        self.sections = {}              # name -> (title button, [keys], container)
        self._display_dict = None
        self._display_cbs = None
        self._title_state = {}
        self._group_icons = {s: make_group_icon(s) for s in ('none', 'some', 'all')}
        # kinematics row
        self.kin_pills = {}             # legacy attribute -> pill
        self.kin_cbs = {}               # legacy attribute -> checkbox bound
        # table tab
        self._table_cb = None
        self._table_guard = False
        self._last_tab = 0
        # navigation
        self._canvas = None
        self._update_gen = 0            # counts legacy rebuilds / redraws (table cell edit refresh)
        self._axis_resync_pending = False
        self._axis_resync_running = False
        # pauses & trigger card
        self.event_mode = 'once'        # 'once' (at Time (s)) | 'repeat' (periodic, the former Periodic tab)
        self.curve_page = None          # the Curve sub-tab page

    # ---------------------------------------------------------------- build
    def build(self):
        from fcn_create_gui.tab_planning_plot_edit import PlotEditor
        self._build_device_toggle()
        self._build_undo_icon()
        self._balance_grid()
        self._build_axis_pill_row()
        from fcn_create_gui.tab_planning_curve_controls import CurveControls   # request H (new file)
        self.curve_controls = CurveControls(self)
        self.curve_controls.build()
        self._build_event_card()
        self._compact_curve_options()
        from fcn_create_gui.tab_planning_insert import InsertReplace     # requests I + J (new file)
        self.insert_replace = InsertReplace(self)
        self.insert_replace.build()
        self._build_rotation_card()
        self._style_curve_page()
        self._build_plot_frame()
        self._build_table_tab()
        self._hide_periodic_tab()
        from fcn_create_gui.tab_planning_white import whiten_planning_subtabs   # request K (new file)
        whiten_planning_subtabs(self)
        self.plot_editor = PlotEditor(self.win)
        self.after_legacy_update()

    # ............................................................ hidden holder of the legacy controls
    def _legacy_holder(self):
        """A hidden widget the replaced legacy buttons are moved into: hidden by their container, so nothing that
        shows a button again can bring it back on screen."""
        h = getattr(self, 'legacy_holder', None)
        if h is None:
            gb = self.win.groupBox_BrCv_createCurve
            h = QWidget(gb)
            h.setObjectName('pmLegacyHolder')
            QHBoxLayout(h).setContentsMargins(0, 0, 0, 0)
            h.setVisible(False)
            self.legacy_holder = h
        return h

    def _grid_inputs(self):
        gl = self.win.groupBox_BrCv_createCurve.layout()
        for i in range(gl.count()):
            lay = gl.itemAt(i).layout()
            if isinstance(lay, QGridLayout):
                return lay
        return None

    def _balance_grid(self):
        """Curve Options fields in 3 equal columns (Amplitude | Amp. offset | Period, Starting Phase | Start Time |
        End Time, the Offset Rot. AP / LAT / SI row on the same columns).  Stretch / size policy only."""
        w = self.win
        grid = self._grid_inputs()
        if grid is None:
            return
        for c in range(3):
            grid.setColumnStretch(c, 1)
        off = getattr(w, 'offset_rot_widget', None)
        if off is not None and isinstance(off.layout(), QGridLayout):
            for c in range(3):
                off.layout().setColumnStretch(c, 1)
            for le in off.findChildren(QWidget):
                if le.metaObject().className() == 'QLineEdit':
                    le.setMinimumWidth(0)
                    le.setSizePolicy(QSizePolicy.Ignored, le.sizePolicy().verticalPolicy())
        for name in ('combo_func_type', 'input_amplitude', 'input_amp_offset', 'input_period', 'input_phase',
                     'input_start_time', 'input_end_time'):
            wd = getattr(w, name, None)
            if wd is not None:
                wd.setMinimumWidth(0)
                wd.setSizePolicy(QSizePolicy.Ignored, wd.sizePolicy().verticalPolicy())

    # ............................................................ Undo icon next to Function Type
    def _build_undo_icon(self):
        w = self.win
        gb = w.groupBox_BrCv_createCurve
        combo = w.combo_func_type
        lay, idx = _find_layout_with(gb.layout(), combo)
        legacy = getattr(w, 'button_undo_curve', None)
        if lay is None or legacy is None:
            return
        row = QWidget(gb)
        row.setObjectName('pmFuncRow')
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(6)
        lay.removeWidget(combo)
        h.addWidget(combo, 1)
        self.btn_undo = QToolButton(row)
        self.btn_undo.setIcon(_svg_icon(UNDO_SVG, '#e65100'))
        self.btn_undo.setIconSize(QSize(24, 24))
        self.btn_undo.setFixedSize(DEVICE_HEIGHT, DEVICE_HEIGHT)
        self.btn_undo.setCursor(Qt.PointingHandCursor)
        self.btn_undo.setStyleSheet(UNDO_STYLE)
        self.btn_undo.setToolTip(UNDO_TOOLTIP)
        self.btn_undo.clicked.connect(lambda _c=False: self._click_legacy('button_undo_curve'))
        h.addWidget(self.btn_undo)
        lay.insertWidget(idx, row)
        self._undo_watch = _EnabledWatcher(legacy, self.sync_undo)
        self.sync_undo()

    def sync_undo(self):
        legacy = getattr(self.win, 'button_undo_curve', None)
        b = getattr(self, 'btn_undo', None)
        if legacy is not None and b is not None and b.isEnabled() != legacy.isEnabled():
            b.setEnabled(legacy.isEnabled())

    # ............................................................ pauses & trigger card (right column)
    def _build_event_card(self):
        """'Pauses & trigger' card: Once | Repeat, the four exclusive kinds (2 x 2), Time (s) (Once) or the periodic
        fields (Repeat: the legacy Periodic tab's own widgets, moved here), Add / Clear and the status line.  The
        legacy buttons go to the hidden holder; Add / Clear click them (Once) or the legacy Apply Periodic (Repeat)."""
        w = self.win
        gb = w.groupBox_BrCv_createCurve
        gbl = gb.layout()
        card = _card(gb, 'pmEventCard')
        self.event_card = card
        v = QVBoxLayout(card)
        v.setContentsMargins(10, 8, 10, 8)
        v.setSpacing(6)
        # header: title + Once | Repeat
        head = QHBoxLayout()
        head.setSpacing(8)
        title = QLabel("Pauses & trigger", card)
        title.setStyleSheet(SECTION_STYLE)
        title.setToolTip("Pauses (Wait Radiation / Wait User) and the 5 V trigger (Trigger On / Off) of the plan.")
        self.event_title = title
        head.addWidget(title, 0, Qt.AlignVCenter)
        head.addStretch(1)
        self.mode_box, self.mode_buttons = _segmented(card, EVENT_MODES, MODE_SEG_STYLE, SEG_HEIGHT,
                                                      self.set_event_mode)
        head.addWidget(self.mode_box, 0, Qt.AlignVCenter)
        v.addLayout(head)
        # the four kinds, 2 x 2
        self.event_row = QWidget(card)              # (name kept: the kinds' container)
        self.event_row.setObjectName('pmEventKinds')
        kg = QGridLayout(self.event_row)
        kg.setContentsMargins(0, 0, 0, 0)
        kg.setHorizontalSpacing(6)
        kg.setVerticalSpacing(6)
        kg.setColumnStretch(0, 1)
        kg.setColumnStretch(1, 1)
        self.event_group = QButtonGroup(self.event_row)
        self.event_group.setExclusive(True)
        self.event_buttons = {}
        self.event_spec = {}
        for i, (key, text, color, add_attr, clear_attr, clear_what) in enumerate(EVENT_KINDS):
            b = QToolButton(self.event_row)
            b.setText(text)
            b.setCheckable(True)
            b.setToolButtonStyle(Qt.ToolButtonTextOnly)
            b.setFixedHeight(EVENT_TOGGLE_HEIGHT)
            b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet(_event_style(color))
            self.event_group.addButton(b)
            kg.addWidget(b, i // 2, i % 2)
            self.event_buttons[key] = b
            self.event_spec[key] = (text, add_attr, clear_attr, clear_what)
            b.toggled.connect(lambda on, k=key: on and self.on_event_selected(k))
        v.addWidget(self.event_row)
        # Once: Time (s) (the legacy label and box)
        self.once_box = QWidget(card)
        self.once_box.setObjectName('pmOnceBox')
        oh = QHBoxLayout(self.once_box)
        oh.setContentsMargins(0, 0, 0, 0)
        oh.setSpacing(8)
        spin = getattr(w, 'input_wait_rad_time', None)
        self.time_label = None
        if spin is not None:
            tlay, _ = _find_layout_with(gbl, spin)
            if tlay is not None:
                for i in range(tlay.count()):
                    it = tlay.itemAt(i).widget()
                    if isinstance(it, QLabel) and "Time" in it.text():
                        self.time_label = it
                        break
                if self.time_label is not None:
                    tlay.removeWidget(self.time_label)
                tlay.removeWidget(spin)
            if self.time_label is not None:
                oh.addWidget(self.time_label, 0, Qt.AlignVCenter)
            spin.setFixedWidth(max(TIME_BOX_WIDTH, spin.minimumSizeHint().width()))
            oh.addWidget(spin, 0, Qt.AlignVCenter)
        oh.addStretch(1)
        v.addWidget(self.once_box)
        # Repeat: the legacy Periodic widgets
        self._build_repeat_box(card)
        v.addWidget(self.repeat_box)
        # Add / Clear
        act = QHBoxLayout()
        act.setSpacing(8)
        self.btn_event_add = QToolButton(card)
        self.btn_event_add.setText("Add")
        self.btn_event_add.setFixedHeight(EVENT_TOGGLE_HEIGHT)
        self.btn_event_add.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.btn_event_add.setCursor(Qt.PointingHandCursor)
        self.btn_event_add.setStyleSheet(ADD_STYLE)
        self.btn_event_add.clicked.connect(lambda _c=False: self.on_event_add())
        act.addWidget(self.btn_event_add, 2)
        self.btn_event_clear = QToolButton(card)
        self.btn_event_clear.setText("Clear")
        self.btn_event_clear.setFixedHeight(EVENT_TOGGLE_HEIGHT)
        self.btn_event_clear.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.btn_event_clear.setCursor(Qt.PointingHandCursor)
        self.btn_event_clear.setStyleSheet(CLEAR_EVENT_STYLE)
        self.btn_event_clear.clicked.connect(lambda _c=False: self.on_event_clear())
        act.addWidget(self.btn_event_clear, 1)
        v.addLayout(act)
        # constant width (both modes, measured with the Repeat fields shown): no jump when switching
        card_width = max(EVENT_CARD_MIN_WIDTH, card.sizeHint().width())
        # status line (legacy label): word-wrapped, takes the rest of the card's height
        st = getattr(w, 'trg_status_label', None)
        if st is not None:
            _take_widget(gbl, st)
            st.setWordWrap(True)
            st.setAlignment(Qt.AlignLeft | Qt.AlignTop)
            st.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Ignored)
            st.setMinimumHeight(36)
            v.addWidget(st, 1)
            if st.property("trg_kind") in (None, "hint"):
                from fcn_create_gui.tab_planning_trigger import _set_label
                _set_label(st, EVENT_HINT, "hint")
        else:
            v.addStretch(1)
        # the replaced legacy buttons (and Undo): into the hidden holder (they stay the source of truth)
        holder = self._legacy_holder()
        for attr in LEGACY_EVENT_BUTTONS:
            b = getattr(w, attr, None)
            if b is not None:
                holder.layout().addWidget(b)
        card.setFixedWidth(card_width)
        self._rep_timer = QTimer(card)
        self._rep_timer.setSingleShot(True)
        self._rep_timer.setInterval(REPEAT_PREVIEW_MS)
        self._rep_timer.timeout.connect(self._repeat_preview_tick)
        self.event_buttons[EVENT_DEFAULT].setChecked(True)
        self.set_event_mode('once', redraw=False)

    def _build_repeat_box(self, card):
        w = self.win
        rb = QWidget(card)
        rb.setObjectName('pmRepeatBox')
        self.repeat_box = rb
        rv = QVBoxLayout(rb)
        rv.setContentsMargins(0, 0, 0, 0)
        rv.setSpacing(6)
        self.rep_fields = {}
        need = ('trg_per_action', 'trg_per_period', 'trg_per_duration', 'trg_per_offset', 'trg_per_range',
                'trg_per_combine', 'button_trg_periodic_apply')
        if any(getattr(w, n, None) is None for n in need):
            rb.setEnabled(False)
            return
        src = w.trg_per_period.parentWidget()
        src_lay = src.layout() if src is not None else None
        fields = QGridLayout()
        fields.setContentsMargins(0, 0, 0, 0)
        fields.setHorizontalSpacing(8)
        fields.setVerticalSpacing(2)
        specs = [
            ('period', "Every P (s)", w.trg_per_period, "Period P: time between two events (s)."),
            ('duration', "For D (s)", w.trg_per_duration,
             "Duration D (s): Trigger On: the trigger is on for D at every event.\n"
             "Trigger Off: the trigger is forced off for D at every event."),
            ('offset', "First at (s)", w.trg_per_offset,
             "First event offset (s): the first event is at range start + offset, then every P."),
        ]
        for col, (key, text, sp, tip) in enumerate(specs):
            box = QWidget(rb)
            bl = QVBoxLayout(box)
            bl.setContentsMargins(0, 0, 0, 0)
            bl.setSpacing(2)
            lbl = QLabel(text, box)
            lbl.setStyleSheet(SMALL_FIELD_STYLE)
            lbl.setToolTip(tip)
            _take_widget(src_lay, sp)
            sp.setMinimumWidth(0)
            sp.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
            sp.setToolTip(tip)
            bl.addWidget(lbl)
            bl.addWidget(sp)
            fields.addWidget(box, 0, col)
            fields.setColumnStretch(col, 1)
            self.rep_fields[key] = box
        rv.addLayout(fields)
        # Range: Whole plan | From - To  [from] to [to]   (legacy radios stay the source of truth, hidden)
        rng = w.trg_per_range
        rr = QHBoxLayout()
        rr.setSpacing(6)
        lr = QLabel("Range:", rb)
        lr.setStyleSheet(SMALL_FIELD_STYLE)
        rr.addWidget(lr, 0, Qt.AlignVCenter)
        self.range_box, self.range_buttons = _segmented(rb, RANGE_SEGS, OPTION_SEG_STYLE, SEG_HEIGHT,
                                                        self.on_range_clicked)
        rr.addWidget(self.range_box, 0, Qt.AlignVCenter)
        for key in ('r0', 'r1'):
            sp = rng[key]
            _take_widget(src_lay, sp)
            sp.setMinimumWidth(0)
            sp.setFixedWidth(max(84, sp.minimumSizeHint().width()))
            sp.setToolTip("From (s)" if key == 'r0' else "To (s)")
            if key == 'r1':
                dash = QLabel("to", rb)
                dash.setStyleSheet(SMALL_FIELD_STYLE)
                rr.addWidget(dash, 0, Qt.AlignVCenter)
            rr.addWidget(sp, 0, Qt.AlignVCenter)
        rr.addStretch(1)
        rv.addLayout(rr)
        # Combine (Trigger On only): Add | Replace | Only where both  (legacy combo stays the source of truth)
        self.combine_row = QWidget(rb)
        cr = QHBoxLayout(self.combine_row)
        cr.setContentsMargins(0, 0, 0, 0)
        cr.setSpacing(6)
        lc = QLabel("Combine:", self.combine_row)
        lc.setStyleSheet(SMALL_FIELD_STYLE)
        lc.setToolTip(w.trg_per_combine.toolTip())
        cr.addWidget(lc, 0, Qt.AlignVCenter)
        self.combine_box, self.combine_buttons = _segmented(self.combine_row, COMBINE_SEGS, OPTION_SEG_STYLE,
                                                            SEG_HEIGHT, self.on_combine_clicked)
        cr.addWidget(self.combine_box, 0, Qt.AlignVCenter)
        cr.addStretch(1)
        rv.addWidget(self.combine_row)
        # legacy -> segments, and the live preview
        sched = lambda *_a: self._schedule_repeat_preview()
        rng['full'].toggled.connect(lambda _c: (self.sync_repeat_controls(), sched()))
        rng['subset'].toggled.connect(lambda _c: (self.sync_repeat_controls(), sched()))
        w.trg_per_combine.currentIndexChanged.connect(lambda _i: (self.sync_repeat_controls(), sched()))
        w.trg_per_action.currentIndexChanged.connect(lambda _i: sched())
        for sp in (w.trg_per_period, w.trg_per_duration, w.trg_per_offset, rng['r0'], rng['r1']):
            sp.valueChanged.connect(sched)

    def _hide_periodic_tab(self):
        """The Periodic sub-tab is merged into the card (Repeat): hidden, its page and widgets stay alive."""
        w = self.win
        tw = w.create_settings_tab_widget
        page = getattr(w, 'trg_periodic_tab', None)
        idx = tw.indexOf(page) if page is not None else -1
        if idx < 0:
            return
        if tw.currentIndex() == idx:
            tw.setCurrentIndex(tw.indexOf(self.curve_page) if self.curve_page is not None else 0)
        tw.setTabVisible(idx, False)
        tw.currentChanged.connect(lambda _i: self._on_tab_for_preview())

    def selected_event(self):
        for key, b in getattr(self, 'event_buttons', {}).items():
            if b.isChecked():
                return key
        return None

    def on_event_selected(self, key):
        if self.event_mode == 'repeat':
            self._sync_periodic_action()
        self.sync_repeat_controls()
        self.update_event_tooltips()

    # ---- Once | Repeat
    def set_event_mode(self, mode, redraw=True):
        was = getattr(self, 'event_mode', None)
        self.event_mode = mode
        for k, b in self.mode_buttons.items():
            _set_checked_quiet(b, k == mode)
        self.once_box.setVisible(mode == 'once')
        self.repeat_box.setVisible(mode == 'repeat')
        if mode == 'repeat':
            self._sync_periodic_action()
        self.sync_repeat_controls()
        self.update_event_tooltips()
        self._update_event_hint()
        if redraw and was != mode:
            self._redraw_plan()

    def repeat_preview_active(self):
        """Repeat mode on and the Curve sub-tab open: the periodic pattern is previewed in gray."""
        if getattr(self, 'event_mode', 'once') != 'repeat':
            return False
        tw = getattr(self.win, 'create_settings_tab_widget', None)
        return tw is not None and self.curve_page is not None and tw.currentWidget() is self.curve_page

    def _sync_periodic_action(self):
        key = self.selected_event()
        combo = getattr(self.win, 'trg_per_action', None)
        if key is None or combo is None:
            return
        i = combo.findData(REPEAT_ACTIONS[key])
        if i >= 0 and combo.currentIndex() != i:
            combo.setCurrentIndex(i)              # the legacy handler enables Duration / Combine

    def sync_repeat_controls(self):
        w = self.win
        try:
            key = self.selected_event()
            if getattr(self, 'rep_fields', None):
                dur = self.rep_fields.get('duration')
                if dur is not None and dur.isHidden() == (key in ('on', 'off')):
                    dur.setVisible(key in ('on', 'off'))
                if self.combine_row.isHidden() == (key == 'on'):
                    self.combine_row.setVisible(key == 'on')
                rng = w.trg_per_range
                full = rng['full'].isChecked()
                _set_checked_quiet(self.range_buttons['full'], full)
                _set_checked_quiet(self.range_buttons['subset'], not full)
                mode = w.trg_per_combine.currentData()
                for k, b in self.combine_buttons.items():
                    _set_checked_quiet(b, k == mode)
        except RuntimeError:
            self.alive = False

    def on_range_clicked(self, key):
        rng = self.win.trg_per_range
        rng[key].setChecked(True)                 # legacy sync: From / To enabled, To = plan end if needed
        self.sync_repeat_controls()

    def on_combine_clicked(self, key):
        combo = self.win.trg_per_combine
        i = combo.findData(key)
        if i >= 0:
            combo.setCurrentIndex(i)
        self.sync_repeat_controls()

    def _update_event_hint(self):
        st = getattr(self.win, 'trg_status_label', None)
        if st is not None and st.property("trg_kind") in (None, "hint"):
            from fcn_create_gui.tab_planning_trigger import _set_label
            _set_label(st, EVENT_HINT_REPEAT if self.event_mode == 'repeat' else EVENT_HINT, "hint")

    # ---- live preview (Repeat)
    def _schedule_repeat_preview(self):
        if self.alive and self.repeat_preview_active():
            self._rep_timer.start()

    def _repeat_preview_tick(self):
        force, self._rep_force = getattr(self, '_rep_force', False), False
        if self.alive and (force or self.repeat_preview_active()):
            self._redraw_plan()

    def _on_tab_for_preview(self):
        if self.alive and getattr(self, 'event_mode', 'once') == 'repeat':
            self._rep_force = True                # the preview appears / goes with the Curve tab
            self._rep_timer.start()

    def _redraw_plan(self):
        if getattr(self.win, 'dfEdit', None) is None:
            return
        try:
            _fc().trigger_plot_update(self.win)
        except RuntimeError:
            self.alive = False

    def update_event_tooltips(self):
        key = self.selected_event()
        if key is None:
            return
        text, add_attr, _clear_attr, clear_what = self.event_spec[key]
        if self.event_mode == 'repeat':
            hint = getattr(self.win, 'trg_per_hint', None)
            extra = hint.text() if hint is not None and hint.text() else ""
            tip_add = (f"Add: {text} repeated: first at 'First at', then every P seconds inside the range "
                       f"(one undo step).\n{extra}").rstrip()
        else:
            legacy = getattr(self.win, add_attr, None)
            extra = legacy.toolTip() if legacy is not None and legacy.toolTip() else \
                f"Adds a {text} pause at Time (s) (nearest plan row)."
            tip_add = f"Add: {text} at Time (s).\n{extra}"
        tip_clear = f"Clear: removes {clear_what}."
        if self.btn_event_add.toolTip() != tip_add:
            self.btn_event_add.setToolTip(tip_add)
        if self.btn_event_clear.toolTip() != tip_clear:
            self.btn_event_clear.setToolTip(tip_clear)
        for k, b in self.event_buttons.items():
            t = self.event_spec[k][0]
            how = "repeated (Repeat)" if self.event_mode == 'repeat' else "at Time (s)"
            tip = f"Select {t}: Add places it {how}; Clear removes all of this kind."
            if b.toolTip() != tip:
                b.setToolTip(tip)

    def on_event_add(self):
        key = self.selected_event()
        if key is None:
            return
        if self.event_mode == 'repeat':
            self._sync_periodic_action()
            self._click_legacy('button_trg_periodic_apply')     # trg_apply_periodic_ui: same cells, messages, undo
            self._show_periodic_summary()
        else:
            self._click_legacy(self.event_spec[key][1])      # the legacy button's own handler

    def _show_periodic_summary(self):
        """The legacy Apply writes some outcomes (e.g. 'Nothing changed') only to the hidden Periodic summary: the
        card's status line shows them too."""
        w = self.win
        s = getattr(w, 'trg_per_summary', None)
        st = getattr(w, 'trg_status_label', None)
        if s is None or st is None or not s.text() or st.text() == s.text():
            return
        from fcn_create_gui.tab_planning_trigger import _trg_status
        _trg_status(w, s.text(), s.property("trg_kind") or "ok")

    def on_event_clear(self):
        key = self.selected_event()
        if key is not None:
            self._click_legacy(self.event_spec[key][2])

    # ............................................................ compact Curve Options (fits without scrolling)
    def _compact_curve_options(self):
        """Fits the whole Curve tab in the Curve page of the maximised window for both devices, the plot keeping its
        size.  Layout only: the fields (and Add Curve / Import File / Clear All) in a left column, the pauses &
        trigger card in a column on the right; 'Axis:' in front of its pills; Add Curve / Import File / Clear All as
        tall as the boxes."""
        w = self.win
        gb = w.groupBox_BrCv_createCurve
        gbl = gb.layout()
        m = gbl.contentsMargins()
        gbl.setContentsMargins(m.left(), COMPACT_GB_MARGIN, m.right(), COMPACT_GB_MARGIN)
        grid = self._grid_inputs()
        if grid is not None:
            grid.setVerticalSpacing(COMPACT_ROW_SPACING)
        # Offset Rot. (Motion Platform): no extra margins (the rotation centre card follows)
        off = getattr(w, 'offset_rot_widget', None)
        if off is not None and isinstance(off.layout(), QGridLayout):
            off.layout().setContentsMargins(0, 0, 0, 0)
            off.layout().setVerticalSpacing(2)
        # Axis: the title in front of the pills (own row widget: the pills keep their own layout)
        sec = getattr(w, 'axis_selection_widget', None)
        if sec is not None and sec.layout() is not None and getattr(self, 'axis_pill_box', None) is not None:
            sl = sec.layout()
            title = None
            for i in range(sl.count()):
                it = sl.itemAt(i).widget()
                if isinstance(it, QLabel) and it.text().strip().startswith("Axis"):
                    title = it
                    break
            if title is not None:
                self.axis_row = QWidget(sec)
                self.axis_row.setObjectName('pmAxisRow')
                h = QHBoxLayout(self.axis_row)
                h.setContentsMargins(0, 0, 0, 0)
                h.setSpacing(10)
                sl.removeWidget(title)
                sl.removeWidget(self.axis_pill_box)
                h.addWidget(title, 0, Qt.AlignVCenter)
                h.addWidget(self.axis_pill_box, 1)
                sl.addWidget(self.axis_row)
                self.axis_title = title
            sl.setContentsMargins(0, 0, 0, 0)
        # Add Curve / Import File / Clear All: as tall as the boxes (legacy 45 px)
        for name in ('button_create_curve', 'button_import_curve', 'button_clear_all'):
            b = getattr(w, name, None)
            if b is not None and b.minimumHeight() > EVENT_HEIGHT:
                b.setMinimumHeight(EVENT_HEIGHT)
        # the blank label that aligned the old wait buttons with the Time box (legacy pause block): not needed
        st = getattr(w, 'trg_status_label', None)
        for lab in gb.findChildren(QLabel, options=Qt.FindDirectChildrenOnly):
            if lab.text() == "" and lab is not st and not lab.isHidden() \
                    and _find_layout_with(gbl, lab)[0] is not None \
                    and (grid is None or _find_layout_with(grid, lab)[0] is None):
                lab.setVisible(False)
        # two columns: left = the fields grid + the Add Curve row, right = the pauses & trigger card
        card = getattr(self, 'event_card', None)
        create = getattr(w, 'button_create_curve', None)
        blay, _ = _find_layout_with(gbl, create) if create is not None else (None, -1)
        if grid is None or card is None:
            return
        self.curve_body = QWidget(gb)
        self.curve_body.setObjectName('pmCurveBody')
        body = QHBoxLayout(self.curve_body)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(12)
        self.curve_left = QWidget(self.curve_body)
        self.curve_left.setObjectName('pmCurveLeft')
        left = QVBoxLayout(self.curve_left)
        left.setContentsMargins(0, 0, 0, 0)
        left.setSpacing(gbl.spacing() if gbl.spacing() >= 0 else 6)
        moved = []
        for lay in (grid, blay):
            if lay is None:
                continue
            i = gbl.indexOf(lay)
            if i < 0:
                continue
            gbl.takeAt(i)
            lay.setParent(None)
            moved.append(lay)
        for lay in moved:
            left.addLayout(lay)
        left.addStretch(1)
        body.addWidget(self.curve_left, 1)
        body.addWidget(card)
        gbl.insertWidget(0, self.curve_body, 1)
        self._moved_layouts = moved               # keep the Python wrappers referenced

    # ............................................................ rotation centre card (Motion Platform)
    def _build_rotation_card(self):
        """The legacy 'Offset Rot. (mm)' row (offset_rot_widget: input_offset_ap_plan / _lat_ / _si_plan, synced with
        the Control tab) as a card 'Rotation centre (mm) - reference point for Roll / Pitch / Yaw' with AP / LAT / SI
        in one row.  The card sits inside offset_rot_widget, so the legacy device switch still shows / hides it."""
        w = self.win
        off = getattr(w, 'offset_rot_widget', None)
        les = [getattr(w, n, None) for n in ('input_offset_ap_plan', 'input_offset_lat_plan', 'input_offset_si_plan')]
        if off is None or not isinstance(off.layout(), QGridLayout) or any(le is None for le in les):
            return
        og = off.layout()
        for lab in off.findChildren(QLabel, options=Qt.FindDirectChildrenOnly):
            lab.setVisible(False)                 # legacy 'Offset Rot. (mm):', 'AP:', 'LAT:', 'SI:'
        card = _card(off, 'pmRotCard')
        card.setToolTip(ROT_TOOLTIP)
        h = QHBoxLayout(card)
        h.setContentsMargins(10, 5, 10, 5)
        h.setSpacing(8)
        tb = QVBoxLayout()
        tb.setSpacing(0)
        t1 = QLabel(ROT_TITLE, card)
        t1.setStyleSheet(FIELD_STYLE)
        t2 = QLabel(ROT_SUBTITLE, card)
        t2.setStyleSheet(NOTE_STYLE)
        for t in (t1, t2):
            t.setToolTip(ROT_TOOLTIP)
        tb.addWidget(t1)
        tb.addWidget(t2)
        h.addLayout(tb)
        h.addSpacing(6)
        self.rot_labels = {}
        for text, le in zip(("AP", "LAT", "SI"), les):
            og.removeWidget(le)
            lbl = QLabel(text + ":", card)
            lbl.setStyleSheet(FIELD_STYLE)
            lbl.setToolTip(ROT_TOOLTIP)
            le.setToolTip(ROT_TOOLTIP)
            h.addWidget(lbl, 0, Qt.AlignVCenter)
            h.addWidget(le, 1)
            self.rot_labels[text] = lbl
        og.addWidget(card, 1, 0, 1, 3)
        self.rot_card = card
        self.rot_title = t1
        self.rot_subtitle = t2

    # ............................................................ white Curve page (no grey background)
    def _style_curve_page(self):
        w = self.win
        tw = w.create_settings_tab_widget
        gb = w.groupBox_BrCv_createCurve
        page = None
        for i in range(tw.count()):
            if tw.widget(i).isAncestorOf(gb):
                page = tw.widget(i)
                break
        self.curve_page = page
        if page is None:
            return
        whites = [page]
        sc = page.findChild(QScrollArea)
        if sc is not None:
            whites.append(sc.viewport())
            if sc.widget() is not None:
                whites.append(sc.widget())
        for wd, name in zip(whites, ('pmCurvePage', 'pmCurveViewport', 'pmCurveContent')):
            if not wd.objectName():
                wd.setObjectName(name)
            wd.setAttribute(Qt.WA_StyledBackground, True)
            wd.setStyleSheet(WHITE_STYLE.format(name=wd.objectName()))
        if not gb.objectName():
            gb.setObjectName('pmCurveOptions')
        if gb.objectName() == 'pmCurveOptions':
            gb.setStyleSheet(GROUP_CARD_STYLE)
        self.curve_scroll = sc

    # ............................................................ 1. device toggle
    def _build_device_toggle(self):
        w = self.win
        combo = w.combo_device
        gb = w.groupBox_BrCv_createCurve
        lay, idx = _find_layout_with(gb.layout(), combo)
        self.device_box = QWidget(gb)
        self.device_box.setObjectName('pmDeviceToggle')
        h = QHBoxLayout(self.device_box)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)
        self.device_group = QButtonGroup(self.device_box)
        self.device_group.setExclusive(True)
        self.device_buttons = []
        n = combo.count()
        for i in range(n):
            b = QToolButton(self.device_box)
            b.setText(combo.itemText(i))
            b.setCheckable(True)
            b.setToolButtonStyle(Qt.ToolButtonTextOnly)
            b.setFixedHeight(DEVICE_HEIGHT)
            b.setMinimumWidth(0)
            b.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
            b.setCursor(Qt.PointingHandCursor)
            radius = _SEG_LEFT if i == 0 else (_SEG_RIGHT if i == n - 1 else _SEG_MID)
            b.setStyleSheet(DEVICE_SEG_STYLE.format(radius=radius))
            b.clicked.connect(lambda _c=False, i=i: self.on_device_clicked(i))
            self.device_group.addButton(b, i)
            h.addWidget(b)
            self.device_buttons.append(b)
        combo.setVisible(False)                 # stays the source of truth (hidden)
        if lay is not None:
            lay.insertWidget(idx + 1, self.device_box)
        # programmatic changes with signals (connected after the existing handler: runs after it)
        combo.currentIndexChanged.connect(lambda _i: self.sync_device())

    def on_device_clicked(self, index):
        combo = self.win.combo_device
        if combo.currentIndex() != index:
            combo.setCurrentIndex(index)        # every existing currentIndexChanged / currentTextChanged handler runs
        self.sync_device()

    def sync_device(self):
        combo = self.win.combo_device
        cur = combo.currentIndex()
        names = [combo.itemText(i) for i in range(combo.count())]
        for i, b in enumerate(self.device_buttons):
            if b.isChecked() != (i == cur):
                b.blockSignals(True)
                b.setChecked(i == cur)
                b.blockSignals(False)
            if i == cur:
                tip = (f"Device of the plan: {names[i]} (selected).\n"
                       "Each device keeps its own plan; switching shows the other device's plan, axes and table.")
            else:
                tip = (f"Click to switch the plan to the {names[i]}.\n"
                       "Each device keeps its own plan; switching back shows this one again.")
            if b.toolTip() != tip:
                b.setToolTip(tip)

    # ............................................................ 2. Curve Options 'Axis' pills
    def _build_axis_pill_row(self):
        w = self.win
        sec = w.axis_selection_widget
        # The legacy checkboxes go to a hidden holder: update_axis_checkboxes looks up self.axis_checkboxes_layout at
        # call time, so the checkboxes it creates on every device switch land in the hidden holder too
        holder = QWidget(sec)
        holder.setObjectName('pmAxisCheckboxHolder')
        hl = QHBoxLayout(holder)
        hl.setContentsMargins(0, 0, 0, 0)
        old = getattr(w, 'axis_checkboxes_layout', None)
        if old is not None:
            while old.count():
                it = old.takeAt(0)
                if it.widget() is not None:
                    hl.addWidget(it.widget())
            hl.addStretch()
        holder.setVisible(False)
        self.axis_checkbox_holder = holder
        w.axis_checkboxes_layout = hl
        self.axis_pill_box = QWidget(sec)
        self.axis_pill_box.setObjectName('pmAxisPills')
        self.axis_pill_lay = QHBoxLayout(self.axis_pill_box)
        self.axis_pill_lay.setContentsMargins(0, 2, 0, 2)
        self.axis_pill_lay.setSpacing(8)
        self.axis_pill_lay.addStretch(1)
        sec.layout().addWidget(self.axis_pill_box)

    def _rebind_axis_pills(self):
        w = self.win
        d = getattr(w, 'create_curve_axis_checkboxes', None) or {}
        same = (d is self._axis_dict and list(d.keys()) == list(self.axis_cbs.keys())
                and all(self.axis_cbs.get(k) is cb for k, cb in d.items()))
        if not same:
            for b in self.axis_pills.values():
                self.axis_pill_lay.removeWidget(b)
                b.deleteLater()
            self.axis_pills = {}
            self.axis_cbs = {}
            for i, (name, cb) in enumerate(d.items()):
                b = QToolButton(self.axis_pill_box)
                b.setText(name)
                b.setCheckable(True)
                b.setToolButtonStyle(Qt.ToolButtonTextOnly)
                b.setFixedHeight(AXIS_PILL_HEIGHT)
                b.setMinimumWidth(AXIS_PILL_MIN_WIDTH)
                b.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
                b.setCursor(Qt.PointingHandCursor)
                b.setStyleSheet(pill_style(_plot_color(name)).replace("font-size: 13px", "font-size: 14px"))
                b.clicked.connect(lambda checked, a=name: self.on_axis_pill_clicked(a, checked))
                cb.toggled.connect(lambda _c: self.sync_axis_pills())
                self.axis_pill_lay.insertWidget(i, b)
                self.axis_pills[name] = b
                self.axis_cbs[name] = cb
            self._axis_dict = d

    def on_axis_pill_clicked(self, axis, checked):
        cb = self.axis_cbs.get(axis)
        if cb is not None and cb.isEnabled():
            cb.setChecked(bool(checked))             # its handler applies the linear / rotational rule
        self.sync_axis_pills()

    def sync_axis_pills(self):
        try:
            for name, b in self.axis_pills.items():
                cb = self.axis_cbs[name]
                on = bool(cb.isChecked())
                if b.isChecked() != on:
                    b.blockSignals(True)
                    b.setChecked(on)
                    b.blockSignals(False)
                en = bool(cb.isEnabled())
                if b.isEnabled() != en:
                    b.setEnabled(en)
                kind = "rotational" if name in ROTATIONAL_AXES else "linear"
                what = _AXIS_TIPS.get(name, f"Axis {name}")
                if not en:
                    tip = f"{what}\n{cb.toolTip() or 'This axis is disabled.'}"
                else:
                    tip = (f"{what}\nAdd Curve writes the curve to the selected (lit) axes.\n"
                           f"{name} is a {kind} axis: linear (mm) and rotational (deg) axes cannot be selected "
                           f"together.")
                if b.toolTip() != tip:
                    b.setToolTip(tip)
        except RuntimeError:
            self.alive = False

    # ............................................................ 3./4. plot frame, side card, bottom row
    def _build_plot_frame(self):
        w = self.win
        pv = w.create_plot_view
        pvl = pv.layout()
        cc = w.create_plot_canvas_container
        self.plot_frame = QFrame(pv)
        self.plot_frame.setObjectName('pmPlotFrame')
        self.plot_frame.setStyleSheet(
            f"QFrame#pmPlotFrame {{ background: #ffffff; border: 1px solid {CARD_BORDER}; border-radius: 6px; }}")
        fl = QHBoxLayout(self.plot_frame)
        fl.setContentsMargins(4, 4, 4, 4)
        fl.setSpacing(6)
        self.plot_left = QWidget(self.plot_frame)
        self.plot_left.setObjectName('pmPlotLeft')
        self.plot_left.setStyleSheet("QWidget#pmPlotLeft { background: #ffffff; }")
        lv = QVBoxLayout(self.plot_left)
        lv.setContentsMargins(0, 0, 0, 0)
        lv.setSpacing(2)
        pvl.removeWidget(cc)
        lv.addWidget(cc, 1)
        self._build_bottom_row()
        lv.addWidget(self.bottom_row)
        fl.addWidget(self.plot_left, 1)
        self._build_side_card()
        fl.addWidget(self.side_card)
        pvl.insertWidget(0, self.plot_frame, 1)
        w.create_plot_checkboxes_widget.setVisible(False)   # the legacy row: hidden source of truth

    def _build_side_card(self):
        self.side_card = QFrame(self.plot_frame)
        self.side_card.setObjectName('pmSideCard')
        self.side_card.setFixedWidth(PANEL_WIDTH)
        self.side_card.setStyleSheet(
            f"QFrame#pmSideCard {{ background: #ffffff; border: 1px solid {CARD_BORDER}; border-radius: 6px; }}")
        card_lay = QVBoxLayout(self.side_card)
        card_lay.setContentsMargins(2, 2, 2, 2)
        card_lay.setSpacing(0)
        self.panel_scroll = QScrollArea(self.side_card)
        self.panel_scroll.setObjectName('pmPanelScroll')
        self.panel_scroll.setWidgetResizable(True)
        self.panel_scroll.setFrameShape(QFrame.NoFrame)
        self.panel_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.panel_scroll.setStyleSheet("QScrollArea#pmPanelScroll { background: #ffffff; border: none; }")
        self.panel_scroll.viewport().setStyleSheet("background: #ffffff;")
        self.panel_scroll.setMinimumHeight(20)     # scrolls: no extra minimum height for the Planning page
        self.panel = QWidget()
        self.panel.setObjectName('pmPanel')
        self.panel.setStyleSheet("QWidget#pmPanel { background: #ffffff; }")
        lay = QVBoxLayout(self.panel)
        lay.setContentsMargins(8, 6, 6, 6)
        lay.setSpacing(5)

        head = QLabel("Plot curves", self.panel)
        head.setStyleSheet(SECTION_STYLE)
        head.setToolTip("Curves shown in the plot (lit = shown, in the colour of the curve).\n"
                        "Only the columns of the current device's plan are listed.")
        lay.addWidget(head)
        self.card_head = head

        # Lung Phantom
        box = QWidget(self.panel)
        bl = QVBoxLayout(box)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(4)
        t = self._title("Lung Phantom", TITLE_STYLE, "Click to select / deselect all Lung Phantom curves (X, Y, Z).\n"
                        "Selects all when at least one is off; deselects all when all are on.", box)
        bl.addWidget(t)
        g = self._grid(box, 'phantom', 3)
        bl.addWidget(g)
        lay.addWidget(box)
        self.sections['phantom'] = (t, [], box)

        # Motion Platform (title acts on both subsections)
        mp = QWidget(self.panel)
        ml = QVBoxLayout(mp)
        ml.setContentsMargins(0, 0, 0, 0)
        ml.setSpacing(4)
        tp = self._title("Motion Platform", TITLE_STYLE,
                         "Click to select / deselect all shown Motion Platform curves (platform position and "
                         "individual axes).\nSelects all when at least one is off; deselects all when all are on.", mp)
        ml.addWidget(tp)
        pos_box = QWidget(mp)
        pl = QVBoxLayout(pos_box)
        pl.setContentsMargins(6, 0, 0, 0)
        pl.setSpacing(4)
        ts = self._title("Platform position", SUBTITLE_STYLE,
                         "Click to select / deselect all platform position curves "
                         "(LAT, SI, AP and the rotations Roll, Pitch, Yaw).\n"
                         "Selects all when at least one is off; deselects all when all are on.", pos_box)
        pl.addWidget(ts)
        pl.addWidget(self._grid(pos_box, 'position', 3))
        ml.addWidget(pos_box)
        ind_box = QWidget(mp)
        il = QVBoxLayout(ind_box)
        il.setContentsMargins(6, 4, 0, 0)
        il.setSpacing(4)
        ti = self._title("Individual axes", SUBTITLE_STYLE,
                         "Click to select / deselect all individual motor axes (A, B, C, D, 'a, 'c, 'e, 'f).\n"
                         "Selects all when at least one is off; deselects all when all are on.", ind_box)
        il.addWidget(ti)
        il.addWidget(self._grid(ind_box, 'individual', 4))
        ml.addWidget(ind_box)
        lay.addWidget(mp)
        self.sections['platform'] = (tp, [], mp)
        self.sections['position'] = (ts, [], pos_box)
        self.sections['individual'] = (ti, [], ind_box)

        # Other columns (a plan of another device)
        ob = QWidget(self.panel)
        ol = QVBoxLayout(ob)
        ol.setContentsMargins(0, 0, 0, 0)
        ol.setSpacing(4)
        to = self._title("Other axes", TITLE_STYLE, "Click to select / deselect all curves of this plan.\n"
                         "Selects all when at least one is off; deselects all when all are on.", ob)
        ol.addWidget(to)
        ol.addWidget(self._grid(ob, 'other', 3))
        lay.addWidget(ob)
        self.sections['other'] = (to, [], ob)
        lay.addStretch(1)
        self.panel_scroll.setWidget(self.panel)

        # Fixed footer: Select all / Clear all (they click the legacy buttons of the hidden row)
        self.footer = QWidget(self.side_card)
        self.footer.setObjectName('pmFooter')
        self.footer.setStyleSheet("QWidget#pmFooter { background: #ffffff; }")
        fl = QVBoxLayout(self.footer)
        fl.setContentsMargins(8, 4, 6, 6)
        fl.setSpacing(6)
        sep = QFrame(self.footer)
        sep.setFrameShape(QFrame.NoFrame)
        sep.setFixedHeight(1)
        sep.setStyleSheet(SEPARATOR_STYLE)
        fl.addWidget(sep)
        row = QHBoxLayout()
        row.setSpacing(6)
        self.btn_select_all = self._outline_button(self.footer, "Select all", "Show all curves of the plan.",
                                                   lambda: self._click_legacy('btn_select_all_axes'))
        self.btn_clear_all = self._outline_button(self.footer, "Clear all", "Hide all curves of the plan.",
                                                  lambda: self._click_legacy('btn_clear_all_axes'))
        row.addWidget(self.btn_select_all)
        row.addWidget(self.btn_clear_all)
        fl.addLayout(row)
        card_lay.addWidget(self.panel_scroll, 1)
        card_lay.addWidget(self.footer)

    def _outline_button(self, parent, text, tip, slot):
        b = QToolButton(parent)
        b.setText(text)
        b.setToolButtonStyle(Qt.ToolButtonTextOnly)
        b.setFixedHeight(ACTION_HEIGHT)
        b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        b.setCursor(Qt.PointingHandCursor)
        b.setStyleSheet(OUTLINE_STYLE)
        b.setToolTip(tip)
        b.clicked.connect(lambda _c=False: slot())
        return b

    def _title(self, text, style, tip, parent):
        b = QToolButton(parent)
        b.setText(text)
        b.setStyleSheet(style)
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

    def _grid(self, parent, name, cols):
        box = QWidget(parent)
        grid = QGridLayout(box)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(5)
        grid.setVerticalSpacing(5)
        for c in range(cols):
            grid.setColumnStretch(c, 1)
        if not hasattr(self, 'grids'):
            self.grids = {}
        self.grids[name] = (grid, cols)
        return box

    def _build_bottom_row(self):
        self.bottom_row = QWidget(self.plot_left)
        self.bottom_row.setObjectName('pmBottomRow')
        self.bottom_row.setStyleSheet("QWidget#pmBottomRow { background: #ffffff; }")
        self.bottom_row.setFixedHeight(ROW_HEIGHT)
        row = QHBoxLayout(self.bottom_row)
        row.setContentsMargins(4, 0, 0, 0)
        row.setSpacing(4)
        for attr, text, color, tip in KINEMATIC_PILLS:
            b = QToolButton(self.bottom_row)
            b.setText(text)
            b.setCheckable(True)
            b.setToolButtonStyle(Qt.ToolButtonTextOnly)
            b.setFixedHeight(PILL_HEIGHT)
            b.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet(pill_style(color))
            b.setToolTip(tip + "\nClick to switch on / off (lit = on).")
            b.clicked.connect(lambda checked, a=attr: self.on_kin_clicked(a, checked))
            row.addWidget(b)
            self.kin_pills[attr] = b
        # pointer readout, then the navigation icons (driving the hidden matplotlib toolbar)
        self.coord_label = QLabel("", self.bottom_row)
        self.coord_label.setStyleSheet("color: #546e7a; font-size: 13px; background: transparent;")
        self.coord_label.setMinimumWidth(0)
        self.coord_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.coord_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.coord_label.setToolTip("Time and value under the mouse pointer.")
        row.addSpacing(4)
        row.addWidget(self.coord_label, 1)
        self.btn_reset = self._nav_button('home', "Reset view: back to the first view of the plot (matplotlib "
                                          "Home).", self.on_reset)
        self.btn_back = self._nav_button('back', "Back to the previous view.", self.on_back)
        self.btn_forward = self._nav_button('forward', "Forward to the next view.", self.on_forward)
        self.btn_pan = self._nav_button('pan', "Pan: drag the plot with the left mouse button (right button "
                                        "zooms).\nClick again to leave pan mode.", self.on_pan, checkable=True)
        self.btn_zoom = self._nav_button('zoom', "Zoom box: drag a rectangle to zoom in (right button zooms "
                                         "out).\nClick again to leave zoom mode.", self.on_zoom, checkable=True)
        self.btn_save = self._nav_button('save', "Save the plot as an image (PNG, SVG, PDF ...).", self.on_save)
        for b in (self.btn_reset, self.btn_back, self.btn_forward):
            row.addWidget(b)
        row.addWidget(self._vsep())
        row.addWidget(self.btn_pan)
        row.addWidget(self.btn_zoom)
        row.addWidget(self._vsep())
        row.addWidget(self.btn_save)
        row.addSpacing(6)
        self.btn_export = self._action_button("Export GCODE", '#0288d1', '#01579b',
                                              "Write the plan as a G-code file (choose where to save it).",
                                              lambda: self._click_legacy('btn_export_gcode'))
        self.btn_upload = self._action_button("Upload to Duet", '#2e7d32', '#1b5e20',
                                              "Write the plan as G-code and upload it to the Duet (0:/gcodes/).",
                                              lambda: self._click_legacy('btn_upload_duet'))
        row.addWidget(self.btn_export)
        row.addWidget(self.btn_upload)

    def _action_button(self, text, bg, hover, tip, slot):
        b = QToolButton(self.bottom_row)
        b.setText(text)
        b.setToolButtonStyle(Qt.ToolButtonTextOnly)
        b.setFixedHeight(ACTION_HEIGHT)
        b.setCursor(Qt.PointingHandCursor)
        b.setStyleSheet(ACTION_STYLE.format(bg=bg, hover=hover))
        b.setToolTip(tip)
        b.clicked.connect(lambda _c=False: slot())
        return b

    def _nav_button(self, name, tip, slot, checkable=False):
        b = QToolButton(self.bottom_row)
        b.setIcon(make_icon(name))
        b.setIconSize(QSize(NAV_ICON_PX, NAV_ICON_PX))
        b.setFixedSize(NAV_BUTTON_PX, NAV_BUTTON_PX)
        b.setCheckable(checkable)
        b.setAutoRaise(True)
        b.setCursor(Qt.PointingHandCursor)
        b.setToolTip(tip)
        b.setStyleSheet(NAV_BUTTON_STYLE)
        b.clicked.connect(lambda _c=False: slot())
        return b

    def _vsep(self):
        s = QFrame(self.bottom_row)
        s.setFrameShape(QFrame.VLine)
        s.setFixedSize(9, 22)
        s.setStyleSheet("QFrame { color: #cfd8dc; background: transparent; }")
        return s

    def _click_legacy(self, attr):
        b = getattr(self.win, attr, None)
        if b is not None:
            b.click()                            # the legacy button's own handler (hidden row)

    # ............................................................ 5. Table tab
    def _build_table_tab(self):
        w = self.win
        tw = w.create_settings_tab_widget
        table = w.create_table_view
        self.table_tab = QWidget(tw)
        self.table_tab.setObjectName('pmTableTab')
        v = QVBoxLayout(self.table_tab)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        v.addWidget(table)                       # moved out of bottom_splitter (same object: readers unchanged)
        tw.addTab(self.table_tab, "Table")
        tw.setTabToolTip(tw.indexOf(self.table_tab), "The plan as a table (time, positions, commands); cells can "
                                                     "be edited.")
        self._last_tab = tw.currentIndex() if tw.currentWidget() is not self.table_tab else 0
        tw.currentChanged.connect(self.on_subtab_changed)
        # A cell edit: on_table_item_changed (connected first) writes the plan but redraws only when the bake changed
        # it; the plot is refreshed afterwards when no redraw followed the edit
        table.itemChanged.connect(self._on_table_item_changed)
        # Numeric cells: a decimal comma (the locale of the boxes, '3,5') is written as '3.5'; text that is no number
        # keeps the old value (the legacy handler would otherwise raise on the float column)
        self.table_delegate = _NumericCellDelegate(self, table)
        table.setItemDelegate(self.table_delegate)

    def _on_table_item_changed(self, _item):
        from PySide6.QtCore import QTimer
        gen = self._update_gen
        QTimer.singleShot(0, lambda g=gen: self._refresh_after_cell_edit(g))

    def _refresh_after_cell_edit(self, gen):
        if not self.alive or self._update_gen != gen:
            return                                # the legacy code already redrew (bake changed the plan)
        try:
            _fc().trigger_plot_update(self.win)
        except RuntimeError:
            self.alive = False

    def on_subtab_changed(self, index):
        if self._table_guard or not self.alive:
            return
        w = self.win
        tw = w.create_settings_tab_widget
        on_table = tw.widget(index) is self.table_tab
        if not on_table:
            self._last_tab = index
        cb = getattr(w, 'check_show_table', None)
        if cb is not None and cb.isChecked() != on_table:
            self._table_guard = True
            try:
                cb.setChecked(on_table)          # toggle_planning_table_visibility shows / hides the table
            finally:
                self._table_guard = False

    def _on_show_table_toggled(self, checked):
        if self._table_guard or not self.alive:
            return
        self._sync_table_tab()

    def _sync_table_tab(self):
        """Code set the legacy 'Show Table' checkbox: the selected sub-tab follows it."""
        w = self.win
        cb = getattr(w, 'check_show_table', None)
        tw = getattr(w, 'create_settings_tab_widget', None)
        if cb is None or tw is None:
            return
        on_table = tw.currentWidget() is self.table_tab
        if cb.isChecked() == on_table:
            return
        self._table_guard = True
        try:
            if cb.isChecked():
                tw.setCurrentWidget(self.table_tab)
            else:
                idx = self._last_tab if 0 <= self._last_tab < tw.count() else 0
                if tw.widget(idx) is self.table_tab:
                    idx = 0
                tw.setCurrentIndex(idx)
        finally:
            self._table_guard = False

    # ---------------------------------------------------------------- re-binding after legacy rebuilds
    def after_legacy_update(self):
        self._update_gen += 1
        self._rebind_axis_pills()
        self._rebind_display()
        self._rebind_kinematics()
        self._rebind_table()
        self._rebind_canvas()
        self.sync_all()
        cc = getattr(self, 'curve_controls', None)
        if cc is not None:
            cc.after_legacy_update()          # function selector, Total duration, Start / End slider
        self._check_axis_device()

    # ............................................................ Curve 'Axis' set must match the device
    def _axis_device_mismatch(self):
        w = self.win
        dev = w.combo_device.currentText()
        want = DEVICE_AXES.get(dev)
        have = set((getattr(w, 'create_curve_axis_checkboxes', None) or {}).keys())
        return want is not None and have != want

    def _check_axis_device(self):
        """Code that sets combo_device with blocked signals (a G-code / file import onto the other device) leaves the
        Curve 'Axis' checkboxes of the previous device (Add Curve then writes nothing).  The legacy re-sync of the
        Settings tab device combo (update_settings_device_sync -> update_axis_checkboxes, plan kept) runs once,
        deferred, when the axis set does not match the device."""
        if self._axis_resync_pending or self._axis_resync_running or not self._axis_device_mismatch():
            return
        from PySide6.QtCore import QTimer
        self._axis_resync_pending = True
        QTimer.singleShot(0, self._resync_axis_device)

    def _resync_axis_device(self):
        self._axis_resync_pending = False
        if not self.alive:
            return
        try:
            w = self.win
            sd = getattr(w, 'combo_settings_device', None)
            if sd is None or not self._axis_device_mismatch():
                return
            self._axis_resync_running = True
            try:
                sd.currentTextChanged.emit(w.combo_device.currentText())
            finally:
                self._axis_resync_running = False
            self.after_legacy_update()
        except RuntimeError:
            self.alive = False

    def _rebind_display(self):
        w = self.win
        d = getattr(w, 'create_axis_checkboxes', None) or {}
        cbs = list(d.values())
        if d is self._display_dict and self._display_cbs is not None and len(cbs) == len(self._display_cbs) \
                and all(a is b for a, b in zip(cbs, self._display_cbs)):
            return
        for b in self.pills.values():
            b.setParent(None)
            b.deleteLater()
        self.pills, self.pill_cb = {}, {}
        groups = {'phantom': [], 'position': [], 'individual': [], 'other': []}
        for key in d.keys():
            if key in PHANTOM_KEYS:
                groups['phantom'].append(key)
            elif key in POSITION_KEYS:
                groups['position'].append(key)
            elif key in INDIVIDUAL_KEYS:
                groups['individual'].append(key)
            else:
                groups['other'].append(key)
        for name, keys in groups.items():
            grid, cols = self.grids[name]
            parent = grid.parentWidget()
            for i, key in enumerate(keys):
                cb = d[key]
                color = self.pill_color.get(key) or _plot_color(key)
                b = QToolButton(parent)
                b.setText(key)
                b.setCheckable(True)
                b.setToolButtonStyle(Qt.ToolButtonTextOnly)
                b.setFixedHeight(PILL_HEIGHT)
                b.setMinimumWidth(40)
                b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                b.setCursor(Qt.PointingHandCursor)
                b.setStyleSheet(pill_style(color))
                what = _AXIS_TIPS.get(key) or (f"Motion platform motor axis {key} (mm)" if key in INDIVIDUAL_KEYS
                                               else f"Axis {key}")
                b.setToolTip(f"{what}\nClick to show / hide this curve in the plot (lit = shown, in the curve's "
                             f"colour).")
                b.clicked.connect(lambda checked, k=key: self.on_pill_clicked(k, checked))
                cb.toggled.connect(lambda _c: self.sync_display_pills())
                grid.addWidget(b, i // cols, i % cols)
                self.pills[key] = b
                self.pill_cb[key] = cb
                self.pill_color[key] = color
        sec = self.sections
        sec['phantom'] = (sec['phantom'][0], groups['phantom'], sec['phantom'][2])
        sec['position'] = (sec['position'][0], groups['position'], sec['position'][2])
        sec['individual'] = (sec['individual'][0], groups['individual'], sec['individual'][2])
        sec['platform'] = (sec['platform'][0], groups['position'] + groups['individual'], sec['platform'][2])
        sec['other'] = (sec['other'][0], groups['other'], sec['other'][2])
        for name, (_t, keys, box) in sec.items():
            if box.isHidden() == bool(keys):
                box.setVisible(bool(keys))
        self._display_dict = d
        self._display_cbs = cbs
        self._title_state = {}

    def _rebind_kinematics(self):
        w = self.win
        for attr, b in self.kin_pills.items():
            cb = getattr(w, attr, None)
            if cb is self.kin_cbs.get(attr):
                continue
            self.kin_cbs[attr] = cb
            if cb is not None:
                cb.toggled.connect(lambda _c: self.sync_kinematics())
            if b.isHidden() == (cb is not None):
                b.setVisible(cb is not None)

    def _rebind_table(self):
        cb = getattr(self.win, 'check_show_table', None)
        if cb is self._table_cb:
            return
        self._table_cb = cb
        if cb is not None:
            cb.toggled.connect(self._on_show_table_toggled)     # after its own handler (toggle_planning_table_...)
            self._sync_table_tab()

    def _rebind_canvas(self):
        w = self.win
        canvas = getattr(w, 'create_plot_canvas', None)
        tb = getattr(w, 'create_plot_toolbar', None)
        if tb is not None and not tb.isHidden():
            tb.setVisible(False)                  # driven by the navigation icons
        if canvas is None or canvas is self._canvas:
            return
        self._canvas = canvas
        canvas.mpl_connect('motion_notify_event', self._on_motion)
        canvas.mpl_connect('axes_leave_event', lambda _e: self._clear_coord())
        canvas.mpl_connect('button_release_event', lambda _e: self.update_nav_buttons())
        pe = getattr(self, 'plot_editor', None)
        if pe is not None:
            pe.connect(canvas)                    # right-click menu on pauses / trigger windows

    # ---------------------------------------------------------------- mirrors
    def sync_all(self):
        self.sync_device()
        self.sync_axis_pills()
        self.sync_display_pills()
        self.sync_colors_from_lines()
        self.sync_kinematics()
        self.update_nav_buttons()
        self.sync_undo()
        if getattr(self, 'event_buttons', None):
            self.update_event_tooltips()          # Add's tooltip shows the legacy hint (row spacing) of the plan

    def sync_display_pills(self):
        try:
            for key, b in self.pills.items():
                on = bool(self.pill_cb[key].isChecked())
                if b.isChecked() != on:
                    b.blockSignals(True)
                    b.setChecked(on)
                    b.blockSignals(False)
            self.update_title_states()
        except RuntimeError:
            self.alive = False

    def section_state(self, name):
        _t, keys, _box = self.sections[name]
        n_on = sum(1 for k in keys if self.pill_cb[k].isChecked())
        if not keys or n_on == 0:
            return 'none'
        return 'all' if n_on == len(keys) else 'some'

    def update_title_states(self):
        for name, (title, _keys, _box) in self.sections.items():
            state = self.section_state(name)
            if self._title_state.get(title) != state:
                self._title_state[title] = state
                title.setIcon(self._group_icons[state])

    def sync_colors_from_lines(self):
        ax = getattr(self.win, 'create_plot_ax', None)
        if ax is None:
            return
        from matplotlib.colors import to_hex
        seen = set()
        for line in ax.get_lines():
            lbl = str(line.get_label() or '')
            key = lbl[:-6] if lbl.endswith((' (Pos)', ' (Vel)', ' (Acc)')) else lbl
            b = self.pills.get(key)
            if b is None or key in seen:
                continue
            seen.add(key)
            try:
                col = to_hex(line.get_color()).lower()
            except Exception:
                continue
            if col != self.pill_color.get(key):
                self.pill_color[key] = col
                b.setStyleSheet(pill_style(col))

    def sync_kinematics(self):
        try:
            for attr, b in self.kin_pills.items():
                cb = self.kin_cbs.get(attr)
                if cb is None:
                    continue
                on = bool(cb.isChecked())
                if b.isChecked() != on:
                    b.blockSignals(True)
                    b.setChecked(on)
                    b.blockSignals(False)
        except RuntimeError:
            self.alive = False

    # ---------------------------------------------------------------- user actions
    def on_pill_clicked(self, key, checked):
        cb = self.pill_cb.get(key)
        if cb is not None:
            cb.setChecked(bool(checked))          # its stateChanged handler redraws the plot
        self.sync_display_pills()

    def section_keys(self, title_btn):
        for name, (title, keys, _box) in self.sections.items():
            if title is title_btn:
                return name, list(keys)
        return None, []

    def on_title_clicked(self, title_btn):
        _name, keys = self.section_keys(title_btn)
        if not keys:
            return
        target = not all(self.pill_cb[k].isChecked() for k in keys)
        for k in keys:                            # as select_all_axes / clear_all_axes: one redraw at the end
            cb = self.pill_cb[k]
            cb.blockSignals(True)
            cb.setChecked(target)
            cb.blockSignals(False)
        _fc().trigger_plot_update(self.win)
        self.sync_display_pills()

    def on_kin_clicked(self, attr, checked):
        cb = getattr(self.win, attr, None)
        if cb is not None:
            cb.setChecked(bool(checked))          # its own handler (table columns, redraw / margins preview)
        self.sync_kinematics()

    # ---------------------------------------------------------------- navigation
    def _toolbar(self):
        return getattr(self.win, 'create_plot_toolbar', None)

    def _nav_mode(self):
        tb = self._toolbar()
        try:
            return str(getattr(tb.mode, 'value', tb.mode) or '')
        except Exception:
            return ''

    def update_nav_buttons(self):
        tb = self._toolbar()
        if tb is None:
            return
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

    def _call_toolbar(self, name):
        tb = self._toolbar()
        if tb is not None:
            getattr(tb, name)()
        self.update_nav_buttons()

    def on_reset(self):
        self._call_toolbar('home')

    def on_back(self):
        self._call_toolbar('back')

    def on_forward(self):
        self._call_toolbar('forward')

    def on_pan(self):
        self._call_toolbar('pan')

    def on_zoom(self):
        self._call_toolbar('zoom')

    def on_save(self):
        self._call_toolbar('save_figure')

    def _clear_coord(self):
        try:
            self.coord_label.setText("")
        except RuntimeError:
            pass

    def _on_motion(self, event):
        try:
            ax = getattr(self.win, 'create_plot_ax', None)
            if event.inaxes is ax and ax is not None and event.xdata is not None and event.ydata is not None:
                self.coord_label.setText(f"t = {format_number(event.xdata, 10)} s    "
                                         f"value = {format_number(event.ydata, 10)}")
            elif self.coord_label.text():
                self.coord_label.setText("")
        except RuntimeError:
            pass


def modernise_planning_tab(self):
    """Adds the modern Planning controls to the Planning tab built by build_planning_tab(self)."""
    pm = getattr(self, 'planning_modern', None)
    if isinstance(pm, ModernPlanning):
        return pm
    for name in ('combo_device', 'create_plot_view', 'create_plot_canvas_container', 'create_settings_tab_widget',
                 'create_table_view', 'axis_selection_widget', 'groupBox_BrCv_createCurve'):
        if getattr(self, name, None) is None:
            return None
    # Never raises: on an error the legacy controls stay as they are
    try:
        install_hooks()
        pm = ModernPlanning(self)
        self.planning_modern = pm
        pm.build()
        return pm
    except Exception:
        import traceback
        print("Planning tab: the modern controls could not be built:\n" + traceback.format_exc())
        pm = getattr(self, 'planning_modern', None)
        if isinstance(pm, ModernPlanning):
            pm.alive = False
        return None
