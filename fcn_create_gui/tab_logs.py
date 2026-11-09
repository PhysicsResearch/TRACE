"""
Log files tab for TRACE GUI
Analysis of TRACE position logs (log_*.csv) against each other and against a reference G-code:
multi-log overlay with per-curve time / value offsets, axis selection, region of interest,
automatic alignment (cross-correlation), the logged sensor waits (Probe -1000 rows and the wait
notes of the log, never estimated) shown in real time or removed from the time axis,
comparison statistics (mean / STD / RMS / max / p95 / correlation), ensemble error bands,
peaks and periods, movement detection (start, stop, time until it stops), reference points
and CSV / PNG export (CSV in the v2 style of the logs: ';' columns, decimal comma).

All numerical work is done by fcn_logs.log_analysis (no Qt).  This module only builds the
widgets inside the existing empty QWidget self.tab_logs and drives the analysis.

State lives in one object, self.logs_state (LogsState); every widget attribute starts with
'logs_'.  Every user action is a plain module-level function taking (self, ...) with explicit
arguments (no dialogs), so it can be scripted / tested; errors are shown with
QMessageBox.warning instead of being raised:

    logs_add_files(self, paths)                 logs_add_reference(self, path_or_text, name=None)
    logs_reference_from_duet(self, index=None)  logs_remove_curves(self, indices=None)
    logs_clear_all(self)                        logs_select_curve(self, index)
    logs_set_visible(self, index, on)           logs_set_curve_color(self, index, color)
    logs_set_time_offset(self, index, value)    logs_set_value_offset(self, index, value, axis=None)
    logs_set_axis_enabled(self, axis, on)       logs_set_analysis_axis(self, axis)
    logs_set_display(self, show_probe=..., show_gaps=..., show_pauses=..., show_diff=...,
                     show_band=..., band_k=..., show_envelope=...)
    logs_set_roi(self, t0, t1)                  logs_clear_roi(self)
    logs_zoom_to_roi(self)                      logs_zoom_all(self)
    logs_set_pick_mode(self, mode)              (None | 'roi' | 'points')
    logs_set_reference(self, index)             logs_auto_align(self, all_curves=False, index=None, max_lag=None)
    logs_reset_offsets(self)                    logs_compare(self)
    logs_set_pause_mode(self, mode)             ('show' | 'remove')
    logs_set_pause_source(self, index_or_None)  (curves-table index of a log with logged waits; None = first one)
    logs_find_peaks(self, prominence=None, min_distance=None, kind=None)        logs_clear_peaks(self)
    logs_detect_movements(self, threshold=None, settle_time=None, min_duration=None, merge_gap=None)
    logs_clear_movements(self)                  logs_movement_list(self)
    logs_set_movement(self, index, t_start=None, t_stop=None)   logs_delete_movements(self, indices)
    logs_add_movement_from_roi(self, curve_index=None)
    logs_add_point(self, curve_index, t, axis=None)   logs_pick_point(self, t, value)
    logs_set_point_time(self, index, t)         logs_set_point_value(self, index, value)
    logs_delete_points(self, indices)           logs_clear_points(self)
    logs_align_points(self, i, j, match_value=False)
    logs_show_results(self, name)               logs_export_results(self, path, name=None)
    logs_export_aligned(self, path, dt=0.01)    logs_save_figure(self, path, dpi=150)
    logs_redraw(self, rescale=False)

Logged sensor waits (section 4 'Pauses:'): nothing is ever estimated, a log without -1000 rows /
wait notes is shown exactly as recorded.  'Show (real time)' (default) draws the logs as recorded
with each wait (amber band [received, end], hatched window [sent_from, received] in which the Duet
sent its message, so the real start lies in it); the G-code's sensor_wait pauses take the lengths
of the waits of one log ('Pause lengths from:', la.pair_pause_waits: in order, only when the counts
match), so the pause period is drawn (a purple strip along the top between two dashed lines: it
keeps its colour over the amber band).  'Remove logged waits' cuts every visible log's waits out of
its time axis (la.remove_waits; the G-code pauses get length 0): logs and G-code then share G-code
time; each pause's label / note says what was removed THERE (from the pairing of each visible cut
log with the G-code: 'wait removed', 'wait not marked: not removed', 'not paired: no wait removed
here').  The pause table's 'G-code t (s)' is the planner time (as in the G-code); the plot position
is in its tooltip and in the 'Pauses' view.  All overlays (points, movements, peaks) stay stored in
RECORDED time (a log's own t, a point / edited edge on the exact row; a G-code reference's own time
base, remapped exactly when its pause lengths change): displayed = cut(t) + time offset, so Show ->
Remove -> Show leaves them where they were.  In Remove mode a point inside a removed wait is not
drawn (the points table says so, editing it is refused), a movement edge inside one is drawn at
the cut point and keeps its recorded time when only the other edge is typed / dragged.  A second
compact legend (the colour key) lists the event classes drawn; both legends keep clear of the
vertical pause / cut labels.  Numbers copied from a log's v2 notes are shown with a decimal point
like every other number of the tab; the CSV files the tab writes use a decimal comma throughout
(also in their note columns and '#' lines) and plain ASCII.
Results views: 'Pauses', 'Waits', 'Movements', 'Points' and 'Peak list' are rebuilt from the state
and always match the plot; the others (Compare, Alignment, Peaks & periods) keep the numbers of the
analysis that made them.  The caption next to the results combo shows the view's time base
(whether logged waits were removed, and from which logs: for Compare / Alignment / Peaks & periods
the curves they analysed, for the views rebuilt from the state every log, a hidden one marked), in
orange with 'run ... again' when the view was made in another time base than the plot's now for a
curve loaded then and now (logged waits shown / removed, other G-code pause lengths; a Show / Remove
switch with no marked wait anywhere, or a log added / removed, changes no time and marks nothing).
A results table the user sorted keeps its order when its cells are rewritten in place (_resort_rows).

The public functions update the state, the widgets and the plot synchronously.  Spin box slots
(ROI, offsets, band k) change the state at once but debounce the redraw
(_REDRAW_DELAY_MS, longer than the spin arrows' auto-repeat; while an arrow is held the redraw waits
for the release, and Enter / leaving the box redraws at once).  A mouse wheel over a spin box /
combo box without keyboard focus scrolls the panel instead of changing the value (_WheelGuard).
Band, envelope and difference are drawn on a grid of at most _DRAW_MAX_POINTS points (statistics
keep dt 0.01 s); the fills are min/max-decimated to the visible range and redrawn on zoom / pan,
which also refits the difference panel's y-range (again after a pan of the toolbar, which sets the
y-limits after the x-limits, and after every Home / Back / Forward, in any toolbar mode: _LogsToolbar).
Labels with variable text (_ElidedLabel) wrap / elide to the width they get, so a long message never
widens the window; long curve / axis names are elided in the legend (kept out of constrained_layout),
the axis checkboxes and combo boxes (full names in the curves table and the tooltips).
Editing: the t / Value cells of the points table and the Start / Stop cells of the movements table
take a typed number (snapped to a sample of the curve; an invalid one is refused in the status line
and the cell restored; one that snaps back onto the sample it is on changes nothing).  On the plot
(pick mode None or 'points', no toolbar mode) a point marker, a movement lane edge or a whole lane
segment (it keeps its width: on sparse rows it may stay) is dragged with the left button: only the
dragged artist is redrawn while the mouse moves (blitting), the release commits with one full redraw
at the same zoom, Escape cancels, a press-release that did not move changes nothing (in pick mode
'points' it is a click: it adds a point, unless it is on that point's own sample).  A redraw from
elsewhere during a drag drops the drag (nothing changed).  The movements table and the 'Movements'
results view follow st.movements on every redraw (offsets, pauses, Clear ...); only the rows that
changed are rewritten (_sync_movements), so thousands of movements cost nothing when they did not.
"""

import functools
import math
import os
import re
import traceback
from itertools import repeat
from urllib.parse import quote

import numpy as np
import shiboken6
import matplotlib
from matplotlib import colors as mcolors
from matplotlib import path as mpath
from matplotlib.backend_bases import MouseButton
from matplotlib.backend_tools import Cursors
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.collections import PolyCollection
from matplotlib.figure import Figure
from matplotlib.legend import Legend
from matplotlib.legend_handler import HandlerBase
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, Rectangle
from matplotlib.transforms import Bbox
from matplotlib.widgets import SpanSelector
from PySide6.QtCore import Qt, QTimer, QLocale, QItemSelectionModel, QObject, QEvent, QSize
from PySide6.QtGui import QColor, QIcon, QPixmap, QFont, QBrush, QFontMetrics, QTextLayout, QTextOption
from PySide6.QtWidgets import (
    QAbstractItemView, QAbstractSpinBox, QApplication, QButtonGroup, QCheckBox, QColorDialog, QComboBox,
    QDoubleSpinBox, QFileDialog, QFrame, QGridLayout, QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QMessageBox, QPushButton, QRadioButton, QScrollArea, QSizePolicy, QSplitter, QStyle, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from fcn_logs import log_analysis as la

# ----------------------------------------------------------------------------
# Constants / styles
# ----------------------------------------------------------------------------
_TAB10 = [mcolors.to_hex(c) for c in matplotlib.colormaps['tab10'].colors]
_LINESTYLES = ['-', '--', ':', '-.']
_ROI_COLOR = '#fff176'
_LANE_Y0 = 0.01                   # movement lanes: bottom of the first lane (axes fraction)
_LANE_STEP = 0.032
_PROBE_DET_COLOR = '#ff0000'
_PROBE_REL_COLOR = '#0288d1'
_PAUSE_COLOR = '#8e24aa'          # G-code pause (purple: the detector is red)
_GAP_COLOR = '#78909c'
_WAIT_COLOR = '#ffb300'           # waiting for sensor (Probe -1000), as the Status plot
_READFAIL_COLOR = '#757575'
# event classes drawn on the plot: (face colour, alpha, hatch, edge colour) of the spans; the colour key
# (_key_handle) uses the same look
_DET_ALPHA = 0.12
_REL_ALPHA = 0.18
_WAIT_ALPHA = 0.20
_SENT_FACE = (1.0, 0.878, 0.51, 0.40)      # '#ffe082', light amber: the window the Duet sent the message in
_SENT_HATCH = '\\\\\\\\'
_GAP_FACE = (0.47, 0.56, 0.61, 0.18)
_GAP_HATCH = '///'
# a G-code pause with a length (Show mode: the logged wait's length) is drawn as a purple strip along the
# top of the axes from its start to its end (both ends a dashed purple line): on top of the amber wait
# band it keeps its own colour; its label starts below the strip, inside the period
_PAUSE_STRIP = (0.955, 1.0)       # y range (axes fraction) of the pause-period strip
_PAUSE_STRIP_ALPHA = 0.55
_PAUSE_LABEL_Y = 0.985            # top of the vertical pause / cut labels (axes fraction) ...
_PAUSE_LABEL_Y_STRIP = 0.945      # ... below the strip when the pause has a length
# light box behind those labels: readable over the hatched sent window / amber band / grid
_LABEL_BOX = dict(boxstyle='square,pad=0.12', facecolor='white', edgecolor='none', alpha=0.72)
_ROI_ALPHA = 0.45
_KEY_LABELS = {
    'det': 'Detector (Probe 1-1499)',
    'rel': 'Release button (Probe 2000)',
    'wait': 'Waiting for sensor (Probe -1000)',
    'sent': 'Wait message sent (start uncertainty)',
    'not_marked': 'Wait not marked',
    'read_failed': 'Duet message read failed',
    'cut': 'Wait removed',
    'pause': 'G-code pause',
    'gap': 'Connection gap',
    'roi': 'Region of interest',
}
_KEY_ORDER = tuple(_KEY_LABELS)
_CUT_LABEL_TOL = 2.0              # s: cut lines of several logs closer than this share one label

_LOG_FILTER = "LogIQ logs (log_*.csv log_*.txt *.csv *.txt);;All files (*)"
_GCODE_FILTER = "G-code (*.gcode *.g *.nc);;All files (*)"

_RESULT_VIEWS = ['Alignment', 'Pauses', 'Waits', 'Compare', 'Peaks & periods', 'Peak list', 'Movements', 'Points']
# pause table (section 4): 'G-code t (s)' is the planner time of the pause (as in the G-code / Planning
# tab); where it is on the plot (+ earlier pause lengths and the reference's time offset) is in the
# tooltip and in the 'Pauses' view
_PAUSE_HEADERS = ['#', 'Pause', 'G-code t (s)', 'Length (s)', 'Ended by', 'Note']
_PAUSE_COL_WIDTHS = ((0, 26), (1, 84), (2, 86), (3, 76), (4, 116))   # Note stretches over the rest
_PAUSES_VIEW_HEADERS = ['Pause #', 'Label', 'G-code t (s)', 'Start on plot (s)', 'Length (s)', 'Ended by', 'Note',
                        'From']
# 'Waits' view: the window in which the Duet sent the wait message as two numbers (from is empty when
# the note says 'before T s (no earlier read)')
_WAITS_HEADERS = ['Curve', '#', 'Received (s)', 'Duet sent from (s)', 'Duet sent to (s)', 'Ended (s)', 'Length (s)',
                  'Ended by', 'Timing note', '-1000 rows']
_PEAK_LIST_BASE = ['Curve', 'Axis', '#', 'Kind', 't (s)']     # + 'Value (<unit>)', 'dt to previous (s)', 'Note'
_REMOVED_NOTE = 'inside a removed wait'
_REF_VIEWS = ('Alignment', 'Pauses', 'Compare')     # views computed against the reference curve
# results views whose rows are rebuilt from the state whenever the time base changes (pause mode,
# offsets ...): they always follow the plot.  The other views keep the numbers of the analysis that made
# them; one made in another time base (logged waits shown / removed, other G-code pause lengths, for a
# curve loaded then and now: not a mode switch without any marked wait, _base_change) is marked on
# screen ('logs_results_note') until the analysis is run again.
_LIVE_VIEWS = ('Pauses', 'Waits', 'Movements', 'Points', 'Peak list')
# analyses of the visible curves (and the reference): their notes name the cut logs among those
_ANALYSIS_VIEWS = ('Compare', 'Alignment', 'Peaks & periods')
_NOTE_COLUMNS = ('Note', 'Timing note')             # text columns whose numbers follow the CSV decimal mark
# curves table: Show, colour, Name, Type, t offset, v offset fit a ~500 px wide panel; Info scrolls
_CURVES_COL_WIDTHS = ((0, 40), (1, 28), (2, 128), (3, 96), (4, 100), (5, 110), (6, 320))

# debounce of redraws triggered by spin boxes: longer than the auto-repeat of a held spin arrow
# (150 ms in Fusion, SH_SpinBox_ClickAutoRepeatRate), so every step of a held arrow restarts it
_REDRAW_DELAY_MS = 250
_DRAW_MAX_POINTS = 20000          # band / envelope / difference: drawing grid of at most this many points
_DRAW_MIN_DT = 0.02               # s, finest drawing grid of band / envelope / difference
_STATUS_MAX_LINES = 3             # status line below the results: wrapped over at most 3 lines, then '…'
# aligned export: time column and '<axis>: <curve> [<unit>]' columns that the Planning importer
# (fcn_plan.fcn_import.is_trace_log_file) never takes for a TRACE log (see _export_columns)
_EXPORT_TIME_COL = 'time [s]'
# long names: legend entries are elided to about this many characters (middle '…', so the start and
# a ' (2)' suffix stay); axis checkboxes to this many pixels; the axis combo box sizes for this many
# characters (Qt elides the shown item, the popup lists full names)
_LEGEND_MAX_CHARS = 40
_LEGEND_AXIS_MAX_CHARS = 16
_AXIS_CHECK_TEXT_PX = 104        # 'Cmd Pitch (deg)' (100 px) whole; 3 columns fit the 440 px panel minimum
_AXIS_COMBO_MIN_CHARS = 12
_UNIT_MAX_CHARS = 8
# legends at loc='best' test the data up to this many plotted points: matplotlib tests every line
# vertex at each draw (+~45 ms per 100k points), so on a heavier plot they only avoid the pause / cut
# labels and each other (curve legend upper right first, the key upper left first; _best_legend_xy)
_LEGEND_BEST_MAX_POINTS = 40000
_AXIS_COMBO_TIP = "Axis used by alignment, compare, peaks, movements and points"
# editing on the plot: a left press within _DRAG_POINT_PX (logical) pixels of a reference point
# marker, or within _DRAG_EDGE_PX of a movement lane edge (inside the lane), drags it; a
# press-release that moved less than _DRAG_MIN_PX changes nothing
_DRAG_POINT_PX = 8.0
_DRAG_EDGE_PX = 6.0
_DRAG_MIN_PX = 3.0
_DRAG_LANE_SLACK_PX = 2.0         # y tolerance of a press on a (thin) movement lane
# a whole lane segment dragged keeps its width: a position where its snapped width differs from the
# original by more than this fraction of the curve's median sample interval is skipped (sparse G-code rows)
_DRAG_MOVE_WIDTH_TOL = 0.75
_LANE_HEIGHT = 0.75               # drawn height of a lane (fraction of _LANE_STEP)
# editable tables: double-click, F2 or typing over an editable cell starts the editor
_EDIT_TRIGGERS = (QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed
                  | QAbstractItemView.AnyKeyPressed)
_POINT_HEADERS = ["#", "Curve", "Axis", "t (s)", "Value", "dt prev (s)", "dv prev", "Note"]
_POINT_EDIT_COLS = (3, 4)         # t (s), Value
_MOVEMENT_EDIT_COLS = (2, 3)      # Start (s), Stop (s)
# movements table: #, Curve, Start, Stop, Duration, Delta (430 px) fit the ~520 px viewport (also with
# its vertical scroll bar); Note stretches over the rest (full note in its tooltip)
_MOVEMENTS_COL_WIDTHS = ((0, 30), (1, 104), (2, 66), (3, 66), (4, 84), (5, 80), (6, 60))
_EDITED_NOTE = 'edited by hand'
_HIDDEN_FG = '#90a4ae'
_FLAGS_RO = Qt.ItemIsEnabled | Qt.ItemIsSelectable          # (Qt enum '|' is slow in a loop of thousands)
_FLAGS_EDIT = _FLAGS_RO | Qt.ItemIsEditable
_ALIGN_NUM = Qt.AlignRight | Qt.AlignVCenter
_MOVEMENT_ROW_FIELD = (1, 2, 3, 4, 5, 6, 7)   # field of a _movement_table_row shown in table column c
# per-movement lists of a st.movements entry (parallel to its segments)
_MV_LIST_KEYS = ('segments', 'in_gap', 'complete', 'start_in_gap', 'stop_in_gap', 'edited', 'ids', 'stats')
_MV_DEFAULTS = {'in_gap': False, 'complete': True, 'start_in_gap': False, 'stop_in_gap': False,
                'edited': False, 'stats': None}

_ROOT_STYLE = """
    QWidget#logs_root { background-color: #f5f7f8; }
    QGroupBox {
        font-weight: bold; font-size: 14px; color: #1565c0;
        border: 1px solid #cfd8dc; border-radius: 6px;
        margin-top: 14px; padding-top: 8px; background-color: #ffffff;
    }
    QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; left: 10px; padding: 0 4px; }
    QLabel { font-weight: bold; font-size: 13px; color: #37474f; }
    QCheckBox { font-weight: bold; font-size: 13px; color: #37474f; }
    QRadioButton { font-weight: bold; font-size: 13px; color: #37474f; }
    QCheckBox::indicator { width: 18px; height: 18px; }
    QComboBox { font-weight: bold; font-size: 13px; min-height: 28px; padding: 1px 6px; }
    QDoubleSpinBox { font-weight: bold; font-size: 13px; min-height: 26px; }
    QTableWidget { font-size: 12px; background-color: #ffffff; gridline-color: #eceff1; }
    QHeaderView::section {
        font-weight: bold; font-size: 12px; color: #37474f; background-color: #eceff1;
        padding: 3px 4px; border: none; border-right: 1px solid #cfd8dc;
    }
"""


def _btn_style(bg):
    c = QColor(bg)
    hover = c.darker(112).name()
    pressed = c.darker(135).name()
    return f"""
        QPushButton {{
            background-color: {bg}; color: white; font-weight: bold; font-size: 13px;
            padding: 4px 10px; border-radius: 4px; border: none; min-height: 30px;
        }}
        QPushButton:hover {{ background-color: {hover}; }}
        QPushButton:pressed {{ background-color: {pressed}; }}
        QPushButton:checked {{ background-color: #f9a825; color: #212121; }}
        QPushButton:disabled {{ background-color: #b0bec5; color: #eceff1; }}
    """


# ----------------------------------------------------------------------------
# State
# ----------------------------------------------------------------------------
class LogsEntry:
    """One loaded curve of the tab (log or reference) with its display settings."""

    def __init__(self, uid, curve, color, visible=True):
        self.uid = uid
        self.curve = curve
        self.color = color
        self.visible = bool(visible)
        self.cut = None                 # (recorded curve, its curve without the logged waits) cache (_vc)

    def __repr__(self):
        return f"LogsEntry({self.uid}, {self.curve.name!r}, {self.curve.kind})"


class LogsState:
    """All state of the Log files tab (stored as self.logs_state)."""

    def __init__(self):
        self.entries = []               # LogsEntry, in table order
        self.uid_counter = 0
        self.known_axes = []            # axes present in any curve (canonical order)
        self.enabled_axes = set()       # axes drawn on the plot
        self.analysis_axis = None
        self.roi = None                 # (t0, t1) in the displayed time base, or None
        self.selected = -1              # selected row of the curves table
        self.ref_uid = None             # uid of the reference curve
        self.show_probe = True
        self.show_gaps = True
        self.show_pauses = True
        self.show_diff = False
        self.show_band = False
        self.band_k = 2.0
        self.show_envelope = False
        self.peaks = {}                 # uid -> dict(axis, t_raw, v_raw, kind)
        self.movements = {}             # uid -> dict(axis, segments [(t0_raw, t1_raw)], in_gap [bool], complete [bool],
                                        #              start_in_gap [bool], stop_in_gap [bool], edited [bool],
                                        #              ids [int], stats [dict]); per movement, sorted by start
                                        # (stats: its numbers, displayed time base at _toff / _voff)
        self.movement_counter = 0       # last movement id (table rows, lane segments and the selection use it)
        self.mv_cache = None            # what the movements table / 'Movements' view were last built from
                                        # (_sync_movements: signature, view, table, rows shown)
        self.points = []                # dict(id, uid, axis, t_raw)
        self.point_counter = 0          # last point id (the points table keeps its selection by id)
        self.point_artists = {}         # point id -> dict(marker, ann, xy) drawn by the last redraw
        self.lane_artists = {}          # uid -> dict(col, y0, y1, ranges, ids) movement lane of the last redraw
        self.drag = None                # point / lane edge being dragged on the plot (_drag_press ... _drag_end)
        self.hover_cursor = None        # None | 'h' | 'move': cursor shown over a draggable item
        self.results = {}               # view name -> (headers, rows)
        self.results_ref = {}           # view name -> uid of the reference it was computed against
        self.current_results = None
        self.pick_mode = None           # None | 'roi' | 'points'
        self.artists = []               # artists of the main axes (removed on every redraw)
        self.diff_artists = []
        self.diff_series = []           # [(t, diff)] drawn on the difference axes (y-limits follow the zoom)
        self.band_fills = []            # [(t, lower, upper, style)] envelope / band on the drawing grid
        self.band_artists = []          # their fills, decimated to the visible range (redrawn on zoom)
        self.band_view = None           # (x0, x1, bins) the fills were drawn for
        self.view_set = False
        self.last_folder = None
        self.summary = ''
        self.defer_redraw = 0           # > 0: redraws are debounced (spin box slots)
        self.pending_redraw = None      # dict(rescale, refit_y) of a debounced redraw
        self.held_spin = None           # spin box whose arrow the left button holds (redraw waits)
        self.busy_depth = 0             # > 0 inside a busy action (override cursor): warnings wait
        self.pending_warnings = []      # (title, message) shown once the cursor is restored
        self.in_xlim_cb = False
        self.pause_mode = 'show'        # 'show': logged waits in real time | 'remove': cut out of the logs
        self.pause_source_uid = None    # log whose waits give the G-code pause lengths (None = first with waits)
        self.pause_info = []            # la.pair_pause_waits of the reference (pause table, 'Pauses' view)
        self.key_artist = None          # colour key (second legend) of the last redraw
        self.key_loc = None             # its position after the user dragged it (axes fraction), else None
        self.key_classes = []           # event classes it lists (= drawn), in key order
        self.results_notes = {}         # view name -> time-base note of its CSV export
        self.results_base = {}          # view name -> _time_base_key when it was made (stale views marked)
        self.results_uids = {}          # analysis view name -> uids of the curves it used (its note)

    @property
    def curves(self):
        return [e.curve for e in self.entries]


def _state(self):
    st = getattr(self, 'logs_state', None)
    if not isinstance(st, LogsState):
        st = LogsState()
        self.logs_state = st
    return st


# ----------------------------------------------------------------------------
# Error handling
# ----------------------------------------------------------------------------
def _warn(self, title, message):
    """Warning box; inside a busy action (wait cursor) it is queued and shown once the cursor is back."""
    st = getattr(self, 'logs_state', None)
    if isinstance(st, LogsState) and st.busy_depth > 0:
        st.pending_warnings.append((title, str(message)))
        return
    try:
        QMessageBox.warning(self, title, str(message))
    except Exception:
        print(f"[Log files] {title}: {message}")


def _flush_warnings(self):
    st = _state(self)
    while st.busy_depth == 0 and st.pending_warnings:
        title, message = st.pending_warnings.pop(0)
        _warn(self, title, message)


def _action(title, busy=False):
    """Decorator for user actions: errors are shown in a warning box and the function returns None.
    busy=True shows the wait cursor; warnings raised meanwhile are shown after it is restored."""
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(self, *args, **kwargs):
            err = None
            cursor = False
            st = _state(self)
            if busy:
                st.busy_depth += 1
                try:
                    QApplication.setOverrideCursor(Qt.WaitCursor)
                    cursor = True
                except Exception:
                    cursor = False
            try:
                return fn(self, *args, **kwargs)
            except Exception as e:      # every action reports its error instead of raising
                if not isinstance(e, (ValueError, KeyError)):
                    traceback.print_exc()
                err = e
            finally:
                if cursor:
                    try:
                        QApplication.restoreOverrideCursor()
                    except Exception:
                        pass
                if busy:
                    st.busy_depth = max(0, st.busy_depth - 1)
                    _flush_warnings(self)
            if err is not None:
                _warn(self, title, err if str(err) else repr(err))
            return None
        return wrapper
    return deco


# ----------------------------------------------------------------------------
# Small helpers
# ----------------------------------------------------------------------------
def _short_device(device):
    if not device:
        return ''
    from fcn_logs.product_names import canonical_device, device_label
    return device_label(canonical_device(str(device)))       # KINETIQ / DYNAMIQ (old and new logs)


def _unit(axis):
    return la.axis_unit(axis) if axis else ''


def _meta_unit(curve, axis):
    """Per-curve unit of `axis` from the reader (meta['units'] = {axis: unit}, e.g. an aligned export
    read back), or None when the reader gave none."""
    try:
        units = (getattr(curve, 'meta', None) or {}).get('units')
        u = units.get(axis) if isinstance(units, dict) else None
    except Exception:
        return None
    u = '' if u is None else str(u).strip()
    return _elide_mid(u, _UNIT_MAX_CHARS) if u else None


def _curve_unit(curve, axis):
    """Unit of `axis` of one curve: its per-curve unit when the reader gave one, else la.axis_unit."""
    if not axis:
        return ''
    return _meta_unit(curve, axis) or la.axis_unit(axis)


def _axis_unit(st, axis):
    """Unit of `axis` over the loaded curves: the first per-curve unit of a curve with this axis
    (meta['units'], optional), else la.axis_unit(axis)."""
    if not axis:
        return ''
    for e in st.entries:
        if e.curve.has(axis):
            u = _meta_unit(e.curve, axis)
            if u:
                return u
    return la.axis_unit(axis)


def _elide_mid(text, n):
    """text shortened to at most n characters with '…' in the middle (start and end stay)."""
    text = '' if text is None else str(text)
    n = max(1, int(n))
    if len(text) <= n:
        return text
    keep = n - 1
    head = (keep + 1) // 2
    tail = keep - head
    return text[:head] + '…' + (text[len(text) - tail:] if tail else '')


class _LegendText(str):
    """A shown (elided) legend text that remembers its full text (for _distinct_texts)."""
    full = ''


def _legend_label(name, axis=None):
    """Legend text '<name> · <axis>' of about _LEGEND_MAX_CHARS characters at most: a long name (and
    a long axis name) is elided in the middle.  The axis part gets the room the name leaves (at
    least _LEGEND_AXIS_MAX_CHARS).  The plotted line keeps the full label; the full curve name is
    in the curves table and its tooltip.  Texts that still collide are separated by
    _distinct_texts when the legend is drawn."""
    name = '' if name is None else str(name)
    if axis is None:
        out = _LegendText(_elide_mid(name, _LEGEND_MAX_CHARS))
        out.full = name
        return out
    axis = str(axis)
    ax_txt = _elide_mid(axis, max(_LEGEND_AXIS_MAX_CHARS, _LEGEND_MAX_CHARS - len(name) - 3))
    out = _LegendText(f"{_elide_mid(name, max(12, _LEGEND_MAX_CHARS - len(ax_txt) - 3))} · {ax_txt}")
    out.full = f"{name} · {axis}"
    return out


def _elide_core(text, prefix, suffix, n):
    """text (whose first `prefix` and last `suffix` characters are shared with similar texts) in at
    most n characters, keeping the differing middle visible: '<head>…<middle>…<tail>'."""
    core = text[prefix:len(text) - suffix]
    if len(core) + 2 >= n:
        return '…' + _elide_mid(core, max(1, n - 2)) + '…'
    room = n - len(core) - 2
    head = text[:min(prefix, (room + 1) // 2)]
    tail_n = min(suffix, room - len(head))
    tail = text[len(text) - tail_n:] if tail_n > 0 else ''
    return (head + ('…' if prefix > len(head) else '') + core +
            ('…' if suffix > len(tail) else '') + tail)


def _distinct_texts(shown, fulls, n):
    """shown texts (elided to about n characters) made distinct: texts whose full texts differ but
    that were elided to the same text are elided again around the part where their full texts
    differ (common prefix / suffix removed); texts that are still equal get ' #k'."""
    shown = [str(s) for s in shown]
    fulls = [str(f) for f in fulls]
    groups = {}
    for i, s in enumerate(shown):
        groups.setdefault(s, []).append(i)
    for idx in groups.values():
        members = sorted({fulls[i] for i in idx})
        if len(idx) < 2 or len(members) < 2:
            continue
        p = len(os.path.commonprefix(members))
        rev = [m[::-1] for m in members]
        s = min(len(os.path.commonprefix(rev)), min(len(m) for m in members) - p)
        for i in idx:
            if fulls[i] in members:
                shown[i] = _elide_core(fulls[i], p, max(0, s), max(n, 8))
    seen = {}
    for i, s in enumerate(shown):
        k = seen.get(s, 0) + 1
        seen[s] = k
        if k > 1:
            shown[i] = f"{s} #{k}"
    return shown


def _fmt_t(x):
    return '–' if x is None or not np.isfinite(x) else f"{x:.3f}"


def _roi_txt(st):
    if st.roi is None:
        return ''
    return f" (ROI {st.roi[0]:.3f}–{st.roi[1]:.3f} s)"


def _entry_by_uid(st, uid):
    for e in st.entries:
        if e.uid == uid:
            return e
    return None


def _index_of(st, entry):
    for i, e in enumerate(st.entries):
        if e is entry:
            return i
    return -1


def _entry_at(st, index):
    if index is None:
        index = st.selected
    try:
        index = int(index)
    except (TypeError, ValueError):
        raise ValueError("No curve selected") from None
    if not st.entries:
        raise ValueError("No curves loaded: add log files or a reference G-code first")
    if not 0 <= index < len(st.entries):
        raise ValueError("Select a curve in the Files table first")
    return st.entries[index]


def _ref_entry(st):
    e = _entry_by_uid(st, st.ref_uid) if st.ref_uid is not None else None
    return e


def _default_ref_uid(st):
    for e in st.entries:
        if e.curve.kind == 'reference':
            return e.uid
    for e in st.entries:
        if e.curve.kind == 'log':
            return e.uid
    return st.entries[0].uid if st.entries else None


def _visible(st, axis=None, kind=None):
    out = []
    for e in st.entries:
        if not e.visible:
            continue
        if axis is not None and not e.curve.has(axis):
            continue
        if kind is not None and e.curve.kind != kind:
            continue
        out.append(e)
    return out


def _require_axis(st):
    axis = st.analysis_axis
    if not axis:
        raise ValueError("No analysis axis: load a curve first")
    return axis


def _vof(curve, axis):
    try:
        return float(curve.value_offsets.get(axis, 0.0) or 0.0)
    except (TypeError, ValueError):
        return 0.0


# ---------------- logged waits: the curve shown / analysed and its time maps ----------------
def _has_waits(curve):
    """A log with logged sensor waits (marked or not marked)."""
    m = getattr(curve, 'meta', None) or {}
    return curve.kind == 'log' and bool(m.get('waits') or m.get('waits_not_marked'))


def _cut_active(st, e):
    """Entry e is shown without its logged waits: Remove mode and a log with marked waits."""
    c = e.curve
    return st.pause_mode == 'remove' and c.kind == 'log' and bool(c.meta.get('waits'))


def _vc(st, e):
    """The curve drawn and analysed for entry e: e.curve, or in Remove mode the log without its
    logged waits (la.remove_waits, cached on the entry; its time offset and value offsets are those of
    e.curve, so display = cut(t) + offset)."""
    c = e.curve
    if not _cut_active(st, e):
        return c
    cache = getattr(e, 'cut', None)
    if cache is None or cache[0] is not c:
        cache = e.cut = (c, la.remove_waits(c))
    cut = cache[1]
    cut.time_offset = c.time_offset
    cut.value_offsets = c.value_offsets             # shared: a value offset set on e.curve applies at once
    return cut


def _view_key(st, e):
    """What the displayed time base of entry e depends on besides its time offset (movement numbers
    are recomputed when it changes): a reference's pause lengths, a log shown cut."""
    c = e.curve
    if c.kind == 'reference':
        return ('ref', tuple(float(x) for x in (c.meta.get('pause_durations') or [])))
    return ('cut',) if _cut_active(st, e) else None


def _r2d(st, e, t):
    """Recorded time(s) of entry e (its own t) -> displayed time(s): cut(t) + time offset."""
    vc = _vc(st, e)
    off = e.curve.time_offset
    if vc is e.curve:
        return np.asarray(t, dtype=float) + off if np.ndim(t) else float(t) + off
    return vc.meta['cut_map'].forward(t) + off


def _d2r(st, e, x):
    """Displayed time(s) of entry e -> recorded time(s) (outside a removed wait: exact)."""
    vc = _vc(st, e)
    off = e.curve.time_offset
    if vc is e.curve:
        return np.asarray(x, dtype=float) - off if np.ndim(x) else float(x) - off
    return vc.meta['cut_map'].inverse(np.asarray(x, dtype=float) - off if np.ndim(x) else float(x) - off)


def _raw_of(st, e, vc, i):
    """Recorded time of sample i of the shown curve vc of entry e (exact: the recorded row's time)."""
    if vc is e.curve:
        return float(vc.t[int(i)])
    return float(e.curve.t[int(vc.meta['cut_index'][int(i)])])


def _raw_of_disp_samples(st, e, vc, ts):
    """Recorded times of the shown samples nearest to displayed times ts (times an analysis returned on
    the cut curve vc, e.g. movement starts): exact recorded row times (vectorised)."""
    ts = np.asarray(ts, dtype=float)
    tt = vc.times()
    if ts.size == 0 or tt.size == 0:
        return np.empty(0)
    i = np.clip(np.searchsorted(tt, ts), 0, tt.size - 1)
    im = np.maximum(i - 1, 0)
    i = np.where((i > 0) & (np.abs(ts - tt[im]) <= np.abs(tt[i] - ts)), im, i)     # a tie: the earlier one
    return e.curve.t[np.asarray(vc.meta['cut_index'])[i]]


_INSIDE_TOL = 1e-9                # s: a recorded time within this of a removed wait's end is its kept end row


def _inside_cut(cm, t_raw):
    """CutMap.inside with a float tolerance at the end of each removed interval: a time a few ulp
    below the row that ended the wait (t - offset + offset rounding) is that kept row, not inside."""
    t = np.asarray(t_raw, dtype=float)
    return cm.inside(t + _INSIDE_TOL)


def _in_removed(st, e, t_raw):
    """A recorded time of entry e that lies inside one of its removed waits (Remove mode)."""
    if not _cut_active(st, e):
        return False
    vc = _vc(st, e)
    return bool(_inside_cut(vc.meta['cut_map'], float(t_raw)))


def _next_color(st):
    used = {e.color for e in st.entries}
    for c in _TAB10:
        if c not in used:
            return c
    return _TAB10[len(st.entries) % len(_TAB10)]


def _unique_name(st, name):
    names = {e.curve.name for e in st.entries}
    if name not in names:
        return name
    k = 2
    while f"{name} ({k})" in names:
        k += 1
    return f"{name} ({k})"


def _platform_dims(self):
    out = []
    for attr in ('input_plat_lat', 'input_plat_si'):
        v = 100.0
        w = getattr(self, attr, None)
        try:
            if w is not None and w.text().strip():
                v = float(w.text().strip().replace(',', '.'))
        except Exception:
            v = 100.0
        out.append(v if v > 0.0 else 100.0)
    return out[0], out[1]


def _default_folder(self):
    """Folder of the file dialogs: the last folder used in this tab, else the Status tab's log
    folder (PhOperFolder), else the Desktop."""
    st = _state(self)
    if st.last_folder and os.path.isdir(st.last_folder):
        return st.last_folder
    w = getattr(self, 'PhOperFolder', None)
    try:
        text = w.text().strip() if w is not None else ''
        if text and os.path.isdir(text):
            return text
    except Exception:
        pass
    desk = os.path.join(os.path.expanduser("~"), "Desktop")
    return desk if os.path.isdir(desk) else os.path.expanduser("~")


def _remember_folder(st, path):
    try:
        folder = os.path.dirname(os.path.abspath(os.fspath(path)))
    except Exception:
        return
    if folder and os.path.isdir(folder):
        st.last_folder = folder


def _draw_dt(span):
    """Grid step (s) used to DRAW the band / envelope / difference over `span` seconds: at most
    _DRAW_MAX_POINTS points (the statistics keep their own finer grid)."""
    try:
        span = float(span)
    except (TypeError, ValueError):
        return _DRAW_MIN_DT
    if not np.isfinite(span) or span <= 0.0:
        return _DRAW_MIN_DT
    return max(_DRAW_MIN_DT, span / _DRAW_MAX_POINTS)


def _safe_remove(artist):
    try:
        artist.remove()
    except Exception:
        pass


def _runs(mask):
    """[(start, end_exclusive)] of the True runs of a boolean array."""
    m = np.asarray(mask, dtype=bool)
    if m.size == 0 or not m.any():
        return []
    d = np.diff(np.concatenate(([0], m.astype(np.int8), [0])))
    return list(zip(np.flatnonzero(d == 1), np.flatnonzero(d == -1)))


def _run_ranges(t, mask):
    """Time ranges covered by the True runs (each run lasts until the next sample)."""
    n = t.size
    out = []
    if n == 0:
        return out
    dt = float(np.median(np.diff(t))) if n > 1 else 0.05
    for s, e in _runs(mask):
        a = float(t[s])
        b = float(t[e]) if e < n else float(t[-1]) + dt
        if b <= a:
            b = a + dt
        out.append((a, b))
    return out


def _span_collection(ax, ranges, y0, y1, **kw):
    """One PolyCollection of vertical bands (x in data, y in axes coordinates).  The vertices go in as
    one (n, 4, 2) array: matplotlib's fast path (thousands of movement segments per lane)."""
    r = np.asarray(ranges, dtype=float).reshape(-1, 2)
    verts = np.empty((r.shape[0], 4, 2), dtype=float)
    verts[:, 0, 0] = verts[:, 1, 0] = r[:, 0]
    verts[:, 2, 0] = verts[:, 3, 0] = r[:, 1]
    verts[:, 0, 1] = verts[:, 3, 1] = y0
    verts[:, 1, 1] = verts[:, 2, 1] = y1
    col = PolyCollection(verts, transform=ax.get_xaxis_transform(), **kw)
    ax.add_collection(col, autolim=False)
    return col


def _plot_xy(curve, axis):
    """Times / values of a curve axis (offsets applied) with NaN breaks at connection gaps."""
    x = curve.times()
    y = curve.values(axis)
    gaps = curve.meta.get('gaps') or []
    if gaps and x.size > 1:
        off = curve.time_offset
        pos = []
        for g in gaps:
            if not g or g[0] is None:
                continue
            i = int(np.searchsorted(x, float(g[0]) + off, side='right')) - 1
            if 0 <= i < x.size - 1:
                pos.append(i + 1)
        if pos:
            pos = sorted(set(pos))
            xm = [(x[p - 1] + x[p]) / 2.0 for p in pos]
            x = np.insert(x, pos, xm)
            y = np.insert(y.astype(float), pos, np.nan)
    return x, y


def _info(curve):
    """(info text, warning flag, tooltip) for the curves table."""
    m = curve.meta
    t = curve.t
    dur = float(t[-1] - t[0]) if t.size > 1 else 0.0
    parts = [f"n={m.get('n') or t.size}", f"{dur:.1f} s"]
    if m.get('median_dt'):
        parts.append(f"dt {float(m['median_dt']) * 1000.0:.0f} ms")
    if curve.kind == 'reference':
        pauses = m.get('pauses') or []
        if pauses:
            parts.append(f"{len(pauses)} pause(s)")
    if m.get('gcode'):
        parts.append(f"G-code: {os.path.basename(str(m['gcode']).replace(':', '/'))}")
    end = m.get('end')
    if end:
        parts.append(f"End: {end[0]}" if isinstance(end, (tuple, list)) else f"End: {end}")
    gaps = m.get('gaps') or []
    if gaps:
        parts.append(f"{len(gaps)} gap(s)")
    waits = m.get('waits') or []
    nm = m.get('waits_not_marked') or []
    if waits or nm:
        parts.append(_waits_text(curve))
    pos_axes = [a for a in curve.data if not a.startswith(la.CMD_PREFIX)]
    zero = set(m.get('all_zero_axes') or [])
    warn = bool(pos_axes) and all(a in zero for a in pos_axes)
    text = " · ".join(parts)
    if warn:
        text = f"WARNING: all positions are 0 ({', '.join(pos_axes)}) · " + text
    tip = [f"{curve.name} ({curve.kind})"]
    if curve.path:
        tip.append(curve.path)
    for k in ('computer_time', 'gcode', 'device', 'format'):
        if m.get(k):
            tip.append(f"{k}: {m[k]}")
    if m.get('recording_from') is not None:
        tip.append(f"recording from: {m['recording_from']} s")
    if m.get('release_times'):
        tip.append("Release button at: " + ", ".join(f"{x:.3f}" for x in m['release_times']) + " s")
    if gaps:
        tip.append("Gaps: " + ", ".join(f"{g[0]:.3f}–{'?' if g[1] is None else f'{g[1]:.3f}'} s" for g in gaps))
    for k, w in enumerate(waits):
        tip.append(f"Wait {k + 1}: {_wait_timing_text(w)}")
    for w in nm:
        tip.append(f"Wait not marked: received at {w['received']:.3f} s"
                   + (f" ({_dots(w['reason'])})" if w.get('reason') else ""))
    for f in m.get('message_read_failures') or []:
        tip.append(f"Duet message read failed at {f['t']:.3f} s ({_sent_text(f.get('sent_from'), f.get('sent_to'))})")
    for w in m.get('warnings') or []:
        tip.append(f"WARNING: {w}")
    return text, warn, "\n".join(tip)


def _sent_text(a, b):
    """'sent between A and B s' / 'sent before B s' of a Duet message window."""
    if a is None and b is None:
        return "send time unknown"
    if a is None:
        return f"sent before {b:.3f} s"
    return f"sent between {a:.3f} and {b:.3f} s"


_COMMA_NUM_RE = re.compile(r'(?<![\w.,])(\d+),(\d+)(?![\w,])')
_POINT_NUM_RE = re.compile(r'(?<![\w.,])(\d+)\.(\d+)(?![\w.])')


def _dots(text):
    """Text copied from a v2 log note ('detector 1000 at 9,632 s') with its numbers in the tab's
    on-screen style: a decimal point, as every other number of the tab ('9.632')."""
    return _COMMA_NUM_RE.sub(r'\1.\2', str(text)) if text else ('' if text is None else str(text))


def _csv_text(text):
    """Text written into a CSV file of the tab (v2 style, for Excel with ';' lists and a decimal
    comma): the numbers in it with a decimal comma (as the logs' own notes: '9,640 s'), dashes /
    dots plain ASCII (a file without BOM is read as cp1252 by Excel)."""
    s = '' if text is None else str(text)
    s = s.replace('–', '-').replace('—', '-').replace('…', '...').replace('·', '-').replace('±', '+/-')
    return _POINT_NUM_RE.sub(r'\1,\2', s)


def _csv_rows(headers, rows):
    """Rows of a results view as written to its CSV: the text of the note columns (_NOTE_COLUMNS)
    through _csv_text (numbers stay numbers: write_rows_csv gives them the decimal comma); curve
    names and other text unchanged."""
    cols = [i for i, h in enumerate(headers) if str(h) in _NOTE_COLUMNS]
    if not cols:
        return rows
    out = []
    for r in rows:
        r = list(r)
        for i in cols:
            if i < len(r) and isinstance(r[i], str):
                r[i] = _csv_text(r[i])
        out.append(r)
    return out


def _wait_timing_text(w):
    """The full logged timing of one wait (recorded run time): Duet send window, received, end."""
    src = " (from the -1000 rows only: no notes)" if w.get('source') == 'rows' else ""
    sent = ("the Duet sent the message between "
            f"{w['sent_from']:.3f} and {w['received']:.3f} s" if w.get('sent_from') is not None
            else "the Duet's send time is unknown (no earlier read)")
    how = f" ({_dots(w['end_note'])})" if w.get('end_note') else ""
    return (f"received at {w['received']:.3f} s ({sent}), ended at {float(w['end']):.3f} s by "
            f"{w.get('end_by') or 'unknown'}{how}, {float(w.get('length', 0.0)):.3f} s, "
            f"{int(w.get('rows', 0))} rows with -1000{src}")


def _waits_text(curve):
    """'1 logged sensor wait (1.74 s)' / '2 logged sensor waits (1.62, 3.10 s)' (+ not marked)."""
    m = curve.meta
    waits = m.get('waits') or []
    nm = m.get('waits_not_marked') or []
    parts = []
    if waits:
        lens = ", ".join(f"{float(w.get('length', 0.0)):.2f}" for w in waits[:6]) + (", …" if len(waits) > 6 else "")
        parts.append(f"{len(waits)} logged sensor wait{'s' if len(waits) != 1 else ''} ({lens} s)")
    if nm:
        parts.append(f"{len(nm)} wait{'s' if len(nm) != 1 else ''} not marked")
    return ", ".join(parts)


_ICON_CACHE = {}


def _color_icon(color, size=16):
    """Square colour icon (cached: a table of thousands of rows shares one icon per colour)."""
    key = (str(color), int(size))
    ic = _ICON_CACHE.get(key)
    if ic is None:
        if len(_ICON_CACHE) > 256:
            _ICON_CACHE.clear()
        pm = QPixmap(size, size)
        pm.fill(QColor(color))
        ic = _ICON_CACHE[key] = QIcon(pm)
    return ic


def _set_icon_color(item, color, size=12):
    """Colour icon of a table item, set only when its colour changed (tables refreshed in place)."""
    if item.data(Qt.UserRole + 1) != color:
        item.setIcon(_color_icon(color, size))
        item.setData(Qt.UserRole + 1, color)


class _NumItem(QTableWidgetItem):
    """Table item that sorts numerically when both items carry a number."""

    def __init__(self, text, key=None):
        super().__init__(text)
        self._key = key

    def __lt__(self, other):
        a = self._key
        b = getattr(other, '_key', None)
        if a is not None and b is not None:
            a = -math.inf if not math.isfinite(a) else a
            b = -math.inf if not math.isfinite(b) else b
            return a < b
        return self.text() < other.text()


def _fmt_value(x, header):
    if x is None:
        return ''
    if isinstance(x, (bool, np.bool_)):
        return 'yes' if x else 'no'
    if isinstance(x, (int, np.integer)):
        return str(int(x))
    if isinstance(x, (float, np.floating)):
        x = float(x)
        if not math.isfinite(x):
            return '–'
        h = str(header).lower()
        if 'corr' in h or 'strength' in h:
            return f"{x:.5f}"
        if '(s)' in h:
            return f"{x:.3f}"
        return f"{x:.4f}"
    return str(x)


def _num_key(x):
    if isinstance(x, (bool, np.bool_)):
        return None
    if isinstance(x, (int, np.integer, float, np.floating)):
        return float(x)
    return None


# ----------------------------------------------------------------------------
# Widget factories
# ----------------------------------------------------------------------------
class _WheelGuard(QObject):
    """Event filter shared by every spin box / combo box of the tab.
    - A mouse wheel over a widget without keyboard focus is ignored, so Qt passes it on to the
      parent (the left panel's scroll area scrolls) instead of silently changing the ROI, an offset,
      a pause duration or a combo.  Click (or Tab) into the widget first to change it with the wheel.
    - While the left button holds a spin box (its arrow auto-repeats) the debounced redraw waits;
      the release redraws at once (_hold_spin / _release_spin)."""

    def __init__(self, win, parent=None):
        super().__init__(parent)
        self._win = win

    def eventFilter(self, obj, event):
        try:
            t = event.type()
            if t == QEvent.Wheel and isinstance(obj, QWidget) and not obj.hasFocus():
                event.ignore()
                return True
            if isinstance(obj, QAbstractSpinBox):
                if t == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
                    _hold_spin(self._win, obj)
                elif t == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton:
                    _release_spin(self._win, obj)
        except Exception:
            traceback.print_exc()
        return False


def _wheel_guard(self):
    g = getattr(self, 'logs_wheel_guard', None)
    if g is None:
        g = _WheelGuard(self, getattr(self, 'tab_logs', None))
        self.logs_wheel_guard = g
    return g


def _guard_wheel(self, widget):
    """Spin box / combo box: focus by click or Tab only, and no wheel change while unfocused."""
    try:
        widget.setFocusPolicy(Qt.StrongFocus)
        widget.installEventFilter(_wheel_guard(self))      # installing twice keeps one filter
    except Exception:
        pass
    return widget


def _mk_combo(self, parent):
    return _guard_wheel(self, QComboBox(parent))


def _mk_btn(text, color, parent, checkable=False, tip=None):
    b = QPushButton(text, parent)
    b.setStyleSheet(_btn_style(color))
    b.setCheckable(checkable)
    b.setMinimumHeight(36)
    if tip:
        b.setToolTip(tip)
    return b


def _mk_spin(self, parent, value, lo, hi, decimals, step, suffix='', label=None, width=None):
    s = QDoubleSpinBox(parent)
    s.setLocale(QLocale(QLocale.C))
    s.setRange(lo, hi)
    s.setDecimals(decimals)
    s.setSingleStep(step)
    s.setValue(value)
    s.setKeyboardTracking(False)
    s.setAccelerated(True)
    if suffix:
        s.setSuffix(suffix)
    if width:
        s.setMinimumWidth(width)
    _guard_wheel(self, s)
    # Enter / leaving the box: a value typed in (keyboardTracking off) is drawn at once, not after
    # the debounce
    s.editingFinished.connect(lambda: _flush_redraw_now(self))
    if label:
        _touch_spin(self, s, label)
    return s


def _touch_spin(self, spin, label):
    """On-screen keyboard for a spin box in touchscreen mode (same keyboard as the other tabs)."""
    try:
        from fcn_create_gui.touch_keyboard import register_touch_line_edit
        le = spin.findChild(QLineEdit)
        if le is None:
            return
        register_touch_line_edit(self, le, label_name=label)
        filt = getattr(le, '_touch_filter', None)
        if filt is not None:
            filt.setParent(spin)            # deleted with the spin box (table rows are rebuilt)

        def on_text(_text, s=spin):
            cb = getattr(self, 'check_touchscreen', None)
            try:
                if cb is not None and cb.isChecked():
                    s.interpretText()
            except Exception:
                pass
        le.textChanged.connect(on_text)
    except Exception:
        pass


def _mk_table(parent, headers, min_h=110, multi=False):
    t = QTableWidget(0, len(headers), parent)
    t.setHorizontalHeaderLabels(headers)
    t.verticalHeader().setVisible(False)
    t.verticalHeader().setDefaultSectionSize(30)
    t.setEditTriggers(QAbstractItemView.NoEditTriggers)
    t.setSelectionBehavior(QAbstractItemView.SelectRows)
    t.setSelectionMode(QAbstractItemView.ExtendedSelection if multi else QAbstractItemView.SingleSelection)
    t.setAlternatingRowColors(True)
    t.setMinimumHeight(min_h)
    t.horizontalHeader().setHighlightSections(False)
    return t


def _hint(text, parent):
    lb = QLabel(text, parent)
    lb.setWordWrap(True)
    lb.setStyleSheet("font-weight: normal; font-size: 12px; color: #607d8b;")
    return lb


def _wrap_elide(text, font, width, max_lines):
    """(shown, elided): `text` wrapped to `width` px in `font` (at word boundaries, else anywhere)
    over at most max_lines lines joined by '\\n'; when text remains, the last line ends in '…'."""
    text = '' if text is None else str(text)
    if not text or width < 8:
        return text, False
    fm = QFontMetrics(font)
    opt = QTextOption()
    opt.setWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
    paras = text.split('\n')
    lines = []
    for pi, para in enumerate(paras):
        u16 = para.encode('utf-16-le')                 # QTextLine positions count UTF-16 units
        layout = QTextLayout(para, font)
        layout.setTextOption(opt)
        layout.beginLayout()
        try:
            while True:
                ln = layout.createLine()
                if not ln.isValid():
                    break
                ln.setLineWidth(float(width))
                s, n = ln.textStart(), ln.textLength()
                if len(lines) == max_lines - 1:        # last line: everything left, elided
                    rest = ' '.join([u16[2 * s:].decode('utf-16-le', 'ignore')] + paras[pi + 1:]).strip()
                    elided = fm.horizontalAdvance(rest) > width
                    if elided:
                        rest = fm.elidedText(rest, Qt.ElideRight, int(width))
                    lines.append(rest)
                    return '\n'.join(lines), elided
                lines.append(u16[2 * s:2 * (s + n)].decode('utf-16-le', 'ignore').rstrip())
        finally:
            layout.endLayout()
    return '\n'.join(lines), False


class _ElidedLabel(QLabel):
    """QLabel for variable text (status line, selected curve, pause summary, ROI) that never makes
    its panel or the window wider: the horizontal size policy is Ignored and the text is wrapped to
    the width the layout gives, over at most `max_lines` lines; a longer text ends in '…'.  The
    height follows the number of lines shown (at least one line / min_height px; no explicit
    minimum height, which would override the layout minimum of a multi-line text).  text() and the
    tooltip hold the full text, shownText() the text on screen."""

    _SAFETY_PX = 10        # QLabel's own text margins (text-selectable labels draw via a QTextDocument)

    def __init__(self, text='', parent=None, max_lines=1, min_height=0):
        super().__init__(parent)
        self._full = ''
        self._elided = False
        self._max_lines = max(1, int(max_lines))
        self._min_height = max(0, int(min_height))
        self.setTextFormat(Qt.PlainText)
        self.setWordWrap(False)              # wrapped here: no height-for-width in the layouts
        self.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self.setText(text)

    def text(self):
        return self._full

    def shownText(self):
        return QLabel.text(self)

    def isElided(self):
        return self._elided

    def maxLines(self):
        return self._max_lines

    def setText(self, text):
        self._full = '' if text is None else str(text)
        self.setToolTip(self._full)
        self._update_shown()

    def availableWidth(self):
        return self.contentsRect().width() - 2 * max(0, self.margin()) - self._SAFETY_PX

    def _with_min_height(self, size):
        cm = self.contentsMargins()
        one_line = self.fontMetrics().lineSpacing() + cm.top() + cm.bottom() + 2 * max(0, self.margin())
        return QSize(size.width(), max(size.height(), one_line, self._min_height))

    def sizeHint(self):
        return self._with_min_height(QLabel.sizeHint(self))

    def minimumSizeHint(self):
        # any width works (the text is elided to it): just room for '…'
        cm = self.contentsMargins()
        w = self.fontMetrics().horizontalAdvance('…') + cm.left() + cm.right() + self._SAFETY_PX
        return self._with_min_height(QSize(w, QLabel.minimumSizeHint(self).height()))

    def _update_shown(self):
        try:
            self.ensurePolished()               # the style sheet font
            shown, self._elided = _wrap_elide(self._full, self.font(), self.availableWidth(), self._max_lines)
        except Exception:
            shown, self._elided = self._full, False
        if shown != QLabel.text(self):
            QLabel.setText(self, shown)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if event.size().width() != event.oldSize().width():
            self._update_shown()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() in (QEvent.FontChange, QEvent.StyleChange):
            self._update_shown()


class _LogsToolbar(NavigationToolbar):
    """matplotlib's Qt toolbar.  Home / Back / Forward restore a stored view: the x- and y-limits of
    both axes, so also a difference y-range stored before a data change (time offset, pauses ...) or
    one set by a zoom rectangle on that panel.  After each of them (toolbar button or a call; the
    embedded canvas has no figure manager, so matplotlib's h / c / v keys are not connected)
    on_view_restored() refits it, in every toolbar mode (Zoom checked too)."""

    def __init__(self, canvas, parent=None, on_view_restored=None):
        super().__init__(canvas, parent)
        self._on_view_restored = on_view_restored

    def _view_restored(self):
        cb = getattr(self, '_on_view_restored', None)
        if cb is None:
            return
        try:
            cb()
        except Exception:
            traceback.print_exc()

    def home(self, *args):
        super().home(*args)
        self._view_restored()

    def back(self, *args):
        super().back(*args)
        self._view_restored()

    def forward(self, *args):
        super().forward(*args)
        self._view_restored()


# ----------------------------------------------------------------------------
# Tab construction
# ----------------------------------------------------------------------------
def build_logs_tab(self):
    """Populate self.tab_logs with the Log files tab (left: controls, right: plot + results)."""
    if getattr(self, 'logs_built', False):
        return
    st = _state(self)
    _wheel_guard(self)

    outer = QVBoxLayout(self.tab_logs)
    outer.setContentsMargins(0, 0, 0, 0)
    self.logs_root = QWidget(self.tab_logs)
    self.logs_root.setObjectName('logs_root')
    self.logs_root.setStyleSheet(_ROOT_STYLE)
    outer.addWidget(self.logs_root)
    root_layout = QHBoxLayout(self.logs_root)
    root_layout.setContentsMargins(8, 4, 8, 4)

    self.logs_splitter = QSplitter(Qt.Horizontal, self.logs_root)
    self.logs_splitter.setChildrenCollapsible(False)
    root_layout.addWidget(self.logs_splitter)

    # ---------------- left: controls ----------------
    self.logs_left_scroll = QScrollArea(self.logs_splitter)
    self.logs_left_scroll.setWidgetResizable(True)
    self.logs_left_scroll.setFrameShape(QFrame.NoFrame)
    self.logs_left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    self.logs_left_scroll.setMinimumWidth(440)
    left = QWidget()
    left.setObjectName('logs_left')
    lv = QVBoxLayout(left)
    lv.setContentsMargins(4, 0, 10, 8)
    lv.setSpacing(6)
    self.logs_left_scroll.setWidget(left)

    _build_files_group(self, left, lv)
    _build_axes_group(self, left, lv)
    _build_roi_group(self, left, lv)
    _build_align_group(self, left, lv)
    _build_compare_group(self, left, lv)
    _build_peaks_group(self, left, lv)
    _build_movement_group(self, left, lv)
    _build_points_group(self, left, lv)
    _build_export_group(self, left, lv)
    lv.addStretch()

    # ---------------- right: plot + results ----------------
    self.logs_right_split = QSplitter(Qt.Vertical, self.logs_splitter)
    self.logs_right_split.setChildrenCollapsible(False)

    plot_box = QGroupBox("", self.logs_right_split)
    plot_box.setStyleSheet("QGroupBox { margin-top: 2px; padding-top: 2px; }")
    pv = QVBoxLayout(plot_box)
    pv.setContentsMargins(6, 6, 6, 6)
    pv.setSpacing(4)

    self.logs_fig = Figure(figsize=(8, 5), dpi=90, layout='constrained')
    self.logs_gs = self.logs_fig.add_gridspec(2, 1, height_ratios=[3, 1])
    self.logs_ax = self.logs_fig.add_subplot(self.logs_gs[0])
    self.logs_ax_diff = self.logs_fig.add_subplot(self.logs_gs[1], sharex=self.logs_ax)
    self.logs_diff_caption = None
    for a in (self.logs_ax, self.logs_ax_diff):
        a.grid(True, linestyle=':', alpha=0.6)
        a.tick_params(axis='both', which='major', labelsize=10)
    self.logs_canvas = FigureCanvas(self.logs_fig)
    self.logs_canvas.setMinimumHeight(260)
    self.logs_canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    self.logs_toolbar = _LogsToolbar(self.logs_canvas, plot_box, on_view_restored=lambda: _on_view_restored(self))
    self.logs_toolbar.setStyleSheet("background-color: #f5f5f5; border: none; font-weight: bold;")
    pv.addWidget(self.logs_toolbar)
    pv.addWidget(self.logs_canvas, stretch=1)

    self.logs_span = SpanSelector(self.logs_ax, lambda a, b: _on_span_selected(self, a, b), 'horizontal',
                                  useblit=True, props=dict(facecolor='#fdd835', alpha=0.30),
                                  interactive=False, button=1, minspan=0.0)
    self.logs_span.set_active(False)
    self.logs_canvas.mpl_connect('button_press_event', lambda ev: _on_canvas_press(self, ev))
    # dragging points / lane edges (the press is handled by _on_canvas_press: one handler decides
    # between adding a point and dragging, so a click never does both)
    self.logs_canvas.mpl_connect('motion_notify_event', lambda ev: _on_canvas_motion(self, ev))
    self.logs_canvas.mpl_connect('button_release_event', lambda ev: _on_canvas_release(self, ev))
    self.logs_canvas.mpl_connect('key_press_event', lambda ev: _on_canvas_key(self, ev))
    self.logs_canvas.mpl_connect('draw_event', lambda ev: _on_canvas_draw(self, ev))
    self.logs_drag_filter = _DragKeyFilter(self, self.tab_logs)
    # difference panel: y-limits follow the zoom / pan of the shared time axis (toolbar included);
    # a zoom on the difference axes only emits on that axes, so both are connected
    for a in (self.logs_ax, self.logs_ax_diff):
        a.callbacks.connect('xlim_changed', lambda _a: _on_xlim_changed(self))

    res_box = QGroupBox("", self.logs_right_split)
    res_box.setStyleSheet("QGroupBox { margin-top: 2px; padding-top: 2px; }")
    rv = QVBoxLayout(res_box)
    rv.setContentsMargins(6, 6, 6, 6)
    rv.setSpacing(4)
    hdr = QHBoxLayout()
    lbl = QLabel("Results:", res_box)
    lbl.setStyleSheet("font-weight: bold; font-size: 14px; color: #1565c0;")
    self.logs_results_combo = _mk_combo(self, res_box)
    self.logs_results_combo.setMinimumWidth(180)
    self.logs_results_combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
    self.logs_results_combo.setMinimumContentsLength(16)
    self.logs_results_combo.currentTextChanged.connect(lambda name: _on_results_view(self, name))
    # caption: the time base of the view shown (whether logged waits were removed); orange when the
    # view was computed in another time base than the plot's now (_refresh_results_note)
    self.logs_results_note = _ElidedLabel("", res_box, max_lines=1)
    self.logs_results_note.setStyleSheet("font-weight: normal; font-size: 12px; color: #607d8b;")
    hdr.addWidget(lbl)
    hdr.addWidget(self.logs_results_combo)
    hdr.addWidget(self.logs_results_note, stretch=1)
    rv.addLayout(hdr)
    self.logs_results_table = _mk_table(res_box, ['Results'], min_h=120, multi=True)
    rv.addWidget(self.logs_results_table, stretch=1)
    # status line: wraps over at most _STATUS_MAX_LINES lines of the panel width, never wider (a
    # long message used to force the window wider than the screen); full text in the tooltip
    self.logs_summary = _ElidedLabel("Add log files or a reference G-code to start.", res_box,
                                     max_lines=_STATUS_MAX_LINES, min_height=24)
    self.logs_summary.setStyleSheet("font-weight: bold; font-size: 13px; color: #1b5e20; padding: 2px 4px;")
    self.logs_summary.setTextInteractionFlags(Qt.TextSelectableByMouse)
    rv.addWidget(self.logs_summary)

    self.logs_right_split.setStretchFactor(0, 3)
    self.logs_right_split.setStretchFactor(1, 1)
    self.logs_right_split.setSizes([620, 230])
    self.logs_splitter.setStretchFactor(0, 0)
    self.logs_splitter.setStretchFactor(1, 1)
    # the controls keep ~580 px (stretch 0; the plot gets the rest: ~1000 px at 1600x900, ~770 px at
    # 1366x768), enough for the main columns of the curves table without horizontal scrolling
    self.logs_splitter.setSizes([580, 1000])

    # every spin box / combo box of the tab ignores the wheel unless it has focus (table spin
    # boxes created later get the same filter in _mk_spin)
    for wdg in self.logs_root.findChildren(QAbstractSpinBox) + self.logs_root.findChildren(QComboBox):
        _guard_wheel(self, wdg)

    # Duet button follows the connection state
    self.logs_duet_timer = QTimer(self.tab_logs)
    self.logs_duet_timer.setInterval(2000)
    self.logs_duet_timer.timeout.connect(lambda: _update_duet_button(self))
    self.logs_duet_timer.start()

    # debounced redraw of the spin box slots (the public logs_* functions redraw at once)
    self.logs_redraw_timer = QTimer(self.tab_logs)
    self.logs_redraw_timer.setSingleShot(True)
    self.logs_redraw_timer.setInterval(_REDRAW_DELAY_MS)
    self.logs_redraw_timer.timeout.connect(lambda: _flush_redraw(self))

    # second refit of the difference panel once control is back in the event loop (_schedule_diff_refit)
    self.logs_diff_refit_timer = QTimer(self.tab_logs)
    self.logs_diff_refit_timer.setSingleShot(True)
    self.logs_diff_refit_timer.setInterval(0)
    self.logs_diff_refit_timer.timeout.connect(lambda: _flush_diff_refit(self))

    self.logs_built = True
    _apply_diff_layout(self)
    _refresh_everything(self, rescale=True)


def _group(title, parent, layout):
    g = QGroupBox(title, parent)
    v = QVBoxLayout(g)
    v.setContentsMargins(8, 10, 8, 8)
    v.setSpacing(6)
    layout.addWidget(g)
    return g, v


def _build_files_group(self, parent, lv):
    g, v = _group("1. Files", parent, lv)
    row = QHBoxLayout()
    self.logs_btn_add = _mk_btn("Add logs...", '#1565c0', g, tip="Add one or more LogIQ log files")
    self.logs_btn_add_ref = _mk_btn("Add reference G-code...", '#00897b', g,
                                    tip="Add a G-code file as reference curve (planned motion)")
    row.addWidget(self.logs_btn_add)
    row.addWidget(self.logs_btn_add_ref)
    v.addLayout(row)
    self.logs_btn_duet_ref = _mk_btn("Reference from log's G-code (Duet)", '#00695c', g,
                                     tip="Download the G-code named in the selected log from the Duet "
                                         "(needs a Duet connection)")
    self.logs_btn_duet_ref.setEnabled(False)
    v.addWidget(self.logs_btn_duet_ref)
    row = QHBoxLayout()
    self.logs_btn_remove = _mk_btn("Remove selected", '#d32f2f', g)
    self.logs_btn_clear = _mk_btn("Clear all", '#757575', g)
    row.addWidget(self.logs_btn_remove)
    row.addWidget(self.logs_btn_clear)
    v.addLayout(row)

    self.logs_curves_table = _mk_table(g, ["Show", "", "Name", "Type", "t offset (s)", "v offset", "Info"],
                                       min_h=170)
    hh = self.logs_curves_table.horizontalHeader()
    hh.setSectionResizeMode(QHeaderView.Interactive)
    for col, w in _CURVES_COL_WIDTHS:
        self.logs_curves_table.setColumnWidth(col, w)
    hh.setStretchLastSection(True)
    self.logs_curves_table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
    self.logs_curves_table.verticalHeader().setDefaultSectionSize(34)
    v.addWidget(self.logs_curves_table)
    self.logs_selected_label = _ElidedLabel("Selected: –", g, max_lines=1)
    self.logs_selected_label.setStyleSheet("font-weight: bold; font-size: 13px; color: #0d47a1;")
    v.addWidget(self.logs_selected_label)
    v.addWidget(_hint("Click a row to select a curve. Double-click the colour to change it. "
                      "Offsets: t is added to the time, v to the analysis axis value.", g))

    self.logs_btn_add.clicked.connect(lambda: _on_add_logs_clicked(self))
    self.logs_btn_add_ref.clicked.connect(lambda: _on_add_ref_clicked(self))
    self.logs_btn_duet_ref.clicked.connect(lambda: logs_reference_from_duet(self))
    self.logs_btn_remove.clicked.connect(lambda: logs_remove_curves(self))
    self.logs_btn_clear.clicked.connect(lambda: logs_clear_all(self))
    self.logs_curves_table.itemChanged.connect(lambda item: _on_curve_item_changed(self, item))
    self.logs_curves_table.itemSelectionChanged.connect(lambda: _on_curve_selection(self))
    self.logs_curves_table.cellDoubleClicked.connect(lambda r, c: _on_curve_double_clicked(self, r, c))


def _build_axes_group(self, parent, lv):
    g, v = _group("2. Axes", parent, lv)
    row = QHBoxLayout()
    row.addWidget(QLabel("Analysis axis:", g))
    self.logs_axis_combo = _mk_combo(self, g)
    self.logs_axis_combo.setMinimumWidth(140)
    # items are axis names, also long column names of a file read back: they must not set the
    # panel's minimum width (Qt elides the shown item; popup and tooltip: full name)
    self.logs_axis_combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
    self.logs_axis_combo.setMinimumContentsLength(_AXIS_COMBO_MIN_CHARS)
    self.logs_axis_combo.setToolTip(_AXIS_COMBO_TIP)
    row.addWidget(self.logs_axis_combo, stretch=1)
    v.addLayout(row)
    v.addWidget(QLabel("Show on plot:", g))
    self.logs_axes_box = QWidget(g)
    self.logs_axes_grid = QGridLayout(self.logs_axes_box)
    self.logs_axes_grid.setContentsMargins(0, 0, 0, 0)
    self.logs_axes_grid.setHorizontalSpacing(10)
    self.logs_axes_grid.setVerticalSpacing(2)
    self.logs_axis_checks = {}
    v.addWidget(self.logs_axes_box)
    self.logs_axes_empty = _hint("(load a curve to list its axes)", g)
    v.addWidget(self.logs_axes_empty)
    grid = QGridLayout()
    self.logs_chk_probe = QCheckBox("Show probe events", g)
    self.logs_chk_probe.setToolTip(
        "Shading over the plot (the colour key on the plot lists what is drawn):\n"
        "red: detector (Probe 1-1499)\nblue: Release button (Probe 2000)\n"
        "amber: waiting for sensor (Probe -1000, logged wait from 'received' to its end)\n"
        "hatched light amber: window in which the Duet sent the wait message (the real start lies in it)\n"
        "amber dashed line: wait not marked · grey dotted line: Duet message read failed\n"
        "amber dotted line: wait removed (Pauses: Remove logged waits)")
    self.logs_chk_gaps = QCheckBox("Show connection gaps", g)
    self.logs_chk_gaps.setToolTip("Grey hatched: connection gap (no data between the last sample before and the "
                                  "first after it)")
    self.logs_chk_pauses = QCheckBox("Show G-code pauses", g)
    self.logs_chk_pauses.setToolTip("Purple dashed line: G-code pause (sensor_wait, M226 ...) of the reference; when a "
                                    "logged wait gives it a length (Pauses: Show, section 4) a purple strip along the "
                                    "top runs from its start to its end, a dashed line at both ends")
    self.logs_chk_probe.setChecked(_st_flag(self, 'show_probe'))
    self.logs_chk_gaps.setChecked(_st_flag(self, 'show_gaps'))
    self.logs_chk_pauses.setChecked(_st_flag(self, 'show_pauses'))
    grid.addWidget(self.logs_chk_probe, 0, 0)
    grid.addWidget(self.logs_chk_gaps, 0, 1)
    grid.addWidget(self.logs_chk_pauses, 1, 0)
    v.addLayout(grid)

    self.logs_axis_combo.currentIndexChanged.connect(lambda _i: _on_axis_combo(self))
    self.logs_chk_probe.toggled.connect(lambda on: logs_set_display(self, show_probe=on))
    self.logs_chk_gaps.toggled.connect(lambda on: logs_set_display(self, show_gaps=on))
    self.logs_chk_pauses.toggled.connect(lambda on: logs_set_display(self, show_pauses=on))


def _st_flag(self, name):
    return bool(getattr(_state(self), name))


def _build_roi_group(self, parent, lv):
    g, v = _group("3. Region of interest", parent, lv)
    row = QHBoxLayout()
    self.logs_btn_roi_select = _mk_btn("Select ROI on plot", '#5d4037', g, checkable=True,
                                       tip="Drag on the plot to select the region used by all analyses")
    self.logs_btn_roi_clear = _mk_btn("Clear ROI", '#757575', g)
    row.addWidget(self.logs_btn_roi_select, stretch=2)
    row.addWidget(self.logs_btn_roi_clear, stretch=1)
    v.addLayout(row)
    row = QHBoxLayout()
    row.addWidget(QLabel("Start", g))
    self.logs_spin_roi0 = _mk_spin(self, g, 0.0, -1e6, 1e6, 3, 0.1, " s", label="ROI start (s)")
    row.addWidget(self.logs_spin_roi0, stretch=1)
    row.addWidget(QLabel("End", g))
    self.logs_spin_roi1 = _mk_spin(self, g, 0.0, -1e6, 1e6, 3, 0.1, " s", label="ROI end (s)")
    row.addWidget(self.logs_spin_roi1, stretch=1)
    v.addLayout(row)
    row = QHBoxLayout()
    self.logs_btn_roi_zoom = _mk_btn("Zoom to ROI", '#1565c0', g)
    self.logs_btn_zoom_all = _mk_btn("Show all", '#546e7a', g)
    row.addWidget(self.logs_btn_roi_zoom)
    row.addWidget(self.logs_btn_zoom_all)
    v.addLayout(row)
    self.logs_roi_label = _ElidedLabel("ROI: all data", g, max_lines=1)
    self.logs_roi_label.setStyleSheet("font-weight: bold; font-size: 13px; color: #f57f17;")
    v.addWidget(self.logs_roi_label)

    self.logs_btn_roi_select.toggled.connect(lambda on: logs_set_pick_mode(self, 'roi' if on else None))
    self.logs_btn_roi_clear.clicked.connect(lambda: logs_clear_roi(self))
    self.logs_btn_roi_zoom.clicked.connect(lambda: logs_zoom_to_roi(self))
    self.logs_btn_zoom_all.clicked.connect(lambda: logs_zoom_all(self))
    self.logs_spin_roi0.valueChanged.connect(lambda _v: _on_roi_spins(self))
    self.logs_spin_roi1.valueChanged.connect(lambda _v: _on_roi_spins(self))


def _build_align_group(self, parent, lv):
    g, v = _group("4. Align", parent, lv)
    row = QHBoxLayout()
    row.addWidget(QLabel("Reference curve:", g))
    self.logs_ref_combo = _mk_combo(self, g)
    self.logs_ref_combo.setMinimumWidth(160)
    # items are curve names: a long name must not set the panel's minimum width (tooltip: full name)
    self.logs_ref_combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
    self.logs_ref_combo.setMinimumContentsLength(16)
    row.addWidget(self.logs_ref_combo, stretch=1)
    v.addLayout(row)
    row = QHBoxLayout()
    row.addWidget(QLabel("Max lag", g))
    self.logs_spin_maxlag = _mk_spin(self, g, 5.0, 0.01, 1e4, 2, 0.5, " s", label="Max lag (s)")
    row.addWidget(self.logs_spin_maxlag)
    row.addStretch()
    v.addLayout(row)
    row = QHBoxLayout()
    self.logs_btn_align_sel = _mk_btn("Auto-align selected", '#1565c0', g,
                                      tip="Cross-correlation on the analysis axis inside the ROI")
    self.logs_btn_align_all = _mk_btn("Auto-align all", '#0d47a1', g)
    row.addWidget(self.logs_btn_align_sel)
    row.addWidget(self.logs_btn_align_all)
    v.addLayout(row)
    self.logs_btn_reset_offsets = _mk_btn("Reset offsets", '#757575', g, tip="Time and value offsets of all curves to 0")
    v.addWidget(self.logs_btn_reset_offsets)

    row = QHBoxLayout()
    row.addWidget(QLabel("Pauses:", g))
    self.logs_radio_pause_show = QRadioButton("Show (real time)", g)
    self.logs_radio_pause_show.setToolTip(
        "Logs as recorded, each logged sensor wait drawn (amber) with the window in which the Duet sent its "
        "message (hatched). The G-code's sensor_wait pauses take the lengths of the waits of the log chosen "
        "below, so the pause period is drawn")
    self.logs_radio_pause_remove = QRadioButton("Remove logged waits", g)
    self.logs_radio_pause_remove.setToolTip(
        "Every visible log is shown without its logged waits (the rows from 'received' to the wait's end are cut "
        "out, later times move earlier), the G-code pauses get length 0: logs and G-code share G-code time. "
        "Logs without logged waits are unchanged. Points, movements and peaks stay stored in recorded time")
    self.logs_pause_group = QButtonGroup(g)
    self.logs_pause_group.addButton(self.logs_radio_pause_show)
    self.logs_pause_group.addButton(self.logs_radio_pause_remove)
    self.logs_radio_pause_show.setChecked(_state(self).pause_mode != 'remove')
    self.logs_radio_pause_remove.setChecked(_state(self).pause_mode == 'remove')
    row.addWidget(self.logs_radio_pause_show)
    row.addWidget(self.logs_radio_pause_remove)
    row.addStretch()
    v.addLayout(row)
    row = QHBoxLayout()
    row.addWidget(QLabel("Pause lengths from:", g))
    self.logs_pause_source_combo = _mk_combo(self, g)
    self.logs_pause_source_combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
    self.logs_pause_source_combo.setMinimumContentsLength(14)
    self.logs_pause_source_combo.setToolTip("Log whose logged waits give the lengths of the G-code's sensor_wait "
                                            "pauses (Show mode; logs with logged waits only)")
    row.addWidget(self.logs_pause_source_combo, stretch=1)
    v.addLayout(row)
    self.logs_pause_table = _mk_table(g, list(_PAUSE_HEADERS), min_h=96)
    self.logs_pause_table.setMaximumHeight(150)
    hh = self.logs_pause_table.horizontalHeader()
    hh.setMinimumSectionSize(24)
    for col, w in _PAUSE_COL_WIDTHS:
        self.logs_pause_table.setColumnWidth(col, w)
    hh.setStretchLastSection(True)
    self.logs_pause_table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
    self.logs_pause_table.verticalHeader().setDefaultSectionSize(30)
    v.addWidget(self.logs_pause_table)
    # summary line under the table: the source log, or 'no logged waits: pauses shown with length 0'
    self.logs_pause_label = _ElidedLabel("G-code pauses: –", g, max_lines=2)
    v.addWidget(self.logs_pause_label)
    v.addWidget(_hint("Pause lengths come only from logged waits (Probe -1000 and the wait notes at the end of the "
                      "log); a log without them is shown as recorded. A wait really started inside its hatched window, "
                      "so up to that much standstill stays before each removed wait; auto-align removes a remaining "
                      "delay.", g))

    self.logs_ref_combo.currentIndexChanged.connect(lambda _i: _on_ref_combo(self))
    self.logs_btn_align_sel.clicked.connect(lambda: logs_auto_align(self, all_curves=False))
    self.logs_btn_align_all.clicked.connect(lambda: logs_auto_align(self, all_curves=True))
    self.logs_btn_reset_offsets.clicked.connect(lambda: logs_reset_offsets(self))
    self.logs_radio_pause_show.toggled.connect(lambda on: on and logs_set_pause_mode(self, 'show'))
    self.logs_radio_pause_remove.toggled.connect(lambda on: on and logs_set_pause_mode(self, 'remove'))
    self.logs_pause_source_combo.currentIndexChanged.connect(lambda _i: _on_pause_source_combo(self))


def _build_compare_group(self, parent, lv):
    g, v = _group("5. Compare", parent, lv)
    self.logs_btn_compare = _mk_btn("Compare to reference", '#2e7d32', g,
                                    tip="Difference statistics of every visible curve vs the reference")
    v.addWidget(self.logs_btn_compare)
    self.logs_chk_diff = QCheckBox("Show difference plot", g)
    v.addWidget(self.logs_chk_diff)
    row = QHBoxLayout()
    self.logs_chk_band = QCheckBox("Show mean ± k·STD band", g)
    row.addWidget(self.logs_chk_band)
    row.addWidget(QLabel("k", g))
    self.logs_spin_band_k = _mk_spin(self, g, 2.0, 0.1, 10.0, 2, 0.5, label="Band k")
    row.addWidget(self.logs_spin_band_k)
    row.addStretch()
    v.addLayout(row)
    self.logs_chk_envelope = QCheckBox("Show min-max envelope", g)
    v.addWidget(self.logs_chk_envelope)
    v.addWidget(_hint("Band and envelope use the visible log curves on the analysis axis.", g))

    self.logs_btn_compare.clicked.connect(lambda: logs_compare(self))
    self.logs_chk_diff.toggled.connect(lambda on: logs_set_display(self, show_diff=on))
    self.logs_chk_band.toggled.connect(lambda on: logs_set_display(self, show_band=on))
    self.logs_chk_envelope.toggled.connect(lambda on: logs_set_display(self, show_envelope=on))
    self.logs_spin_band_k.valueChanged.connect(lambda val: _deferred(self, logs_set_display, band_k=val))


def _build_peaks_group(self, parent, lv):
    g, v = _group("6. Peaks && periods", parent, lv)       # '&&' = literal '&' in a Qt title
    grid = QGridLayout()
    grid.addWidget(QLabel("Prominence", g), 0, 0)
    self.logs_spin_prom = _mk_spin(self, g, 0.0, 0.0, 1e5, 4, 0.01, " mm", label="Prominence")
    self.logs_spin_prom.setToolTip("0 = automatic (10 % of the value range in the ROI)")
    grid.addWidget(self.logs_spin_prom, 0, 1)
    grid.addWidget(_hint("0 = auto", g), 0, 2)
    grid.addWidget(QLabel("Min distance", g), 1, 0)
    self.logs_spin_peakdist = _mk_spin(self, g, 0.5, 0.0, 1e4, 2, 0.1, " s", label="Min peak distance (s)")
    grid.addWidget(self.logs_spin_peakdist, 1, 1)
    grid.addWidget(QLabel("Kind", g), 2, 0)
    self.logs_combo_peakkind = _mk_combo(self, g)
    for text, key in (("Maxima", 'max'), ("Minima", 'min'), ("Both", 'both')):
        self.logs_combo_peakkind.addItem(text, key)
    grid.addWidget(self.logs_combo_peakkind, 2, 1)
    v.addLayout(grid)
    row = QHBoxLayout()
    self.logs_btn_peaks = _mk_btn("Find peaks", '#ef6c00', g)
    self.logs_btn_peaks_clear = _mk_btn("Clear peaks", '#757575', g)
    row.addWidget(self.logs_btn_peaks, stretch=2)
    row.addWidget(self.logs_btn_peaks_clear, stretch=1)
    v.addLayout(row)
    self.logs_btn_peaks.clicked.connect(lambda: logs_find_peaks(self))
    self.logs_btn_peaks_clear.clicked.connect(lambda: logs_clear_peaks(self))


def _build_movement_group(self, parent, lv):
    g, v = _group("7. Movement", parent, lv)
    grid = QGridLayout()
    grid.addWidget(QLabel("Threshold", g), 0, 0)
    self.logs_spin_mv_thr = _mk_spin(self, g, 0.02, 0.0, 1e4, 4, 0.005, " mm", label="Movement threshold")
    self.logs_spin_mv_thr.setToolTip("A movement starts when the value leaves the rest value by more than this")
    grid.addWidget(self.logs_spin_mv_thr, 0, 1)
    grid.addWidget(QLabel("Settle time", g), 1, 0)
    self.logs_spin_mv_settle = _mk_spin(self, g, 0.5, 0.0, 1e4, 3, 0.1, " s", label="Settle time (s)")
    self.logs_spin_mv_settle.setToolTip("The movement stops when the value stays within the threshold this long")
    grid.addWidget(self.logs_spin_mv_settle, 1, 1)
    grid.addWidget(QLabel("Min duration", g), 2, 0)
    self.logs_spin_mv_mindur = _mk_spin(self, g, 0.0, 0.0, 1e4, 3, 0.1, " s", label="Min duration (s)")
    grid.addWidget(self.logs_spin_mv_mindur, 2, 1)
    grid.addWidget(QLabel("Merge gap", g), 3, 0)
    self.logs_spin_mv_merge = _mk_spin(self, g, 0.0, 0.0, 1e4, 3, 0.1, " s", label="Merge gap (s)")
    self.logs_spin_mv_merge.setToolTip("Movements separated by less than this are merged")
    grid.addWidget(self.logs_spin_mv_merge, 3, 1)
    v.addLayout(grid)
    row = QHBoxLayout()
    self.logs_btn_movements = _mk_btn("Detect movements", '#00838f', g,
                                      tip="Movements of every visible curve on the analysis axis inside the ROI. "
                                          "Replaces all movements, also those edited by hand.")
    self.logs_btn_movements_clear = _mk_btn("Clear", '#757575', g)
    row.addWidget(self.logs_btn_movements, stretch=2)
    row.addWidget(self.logs_btn_movements_clear, stretch=1)
    v.addLayout(row)
    tbl = _mk_table(g, _movement_table_headers(''), min_h=110, multi=True)
    tbl.setEditTriggers(_EDIT_TRIGGERS)
    tbl.horizontalHeader().setMinimumSectionSize(24)
    for col, w in _MOVEMENTS_COL_WIDTHS:
        tbl.setColumnWidth(col, w)
    tbl.horizontalHeader().setStretchLastSection(True)
    tbl.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
    tbl.setMaximumHeight(240)
    self.logs_movements_table = tbl
    v.addWidget(tbl)
    row = QHBoxLayout()
    self.logs_btn_movements_del = _mk_btn("Delete selected movement(s)", '#d32f2f', g)
    self.logs_btn_movements_add = _mk_btn("Add movement from ROI", '#00838f', g,
                                          tip="A movement spanning the ROI on the curve selected in the Files table "
                                              "(on every visible curve with the analysis axis when none is selected)")
    row.addWidget(self.logs_btn_movements_del)
    row.addWidget(self.logs_btn_movements_add)
    v.addLayout(row)
    v.addWidget(_hint("Double-click Start or Stop to type a time (snapped to a sample of the curve). On the plot, "
                      "drag a lane edge, or a whole lane segment, with the left button (Esc cancels).", g))
    self.logs_btn_movements.clicked.connect(lambda: logs_detect_movements(self))
    self.logs_btn_movements_clear.clicked.connect(lambda: logs_clear_movements(self))
    self.logs_btn_movements_del.clicked.connect(lambda: _on_delete_movements_clicked(self))
    self.logs_btn_movements_add.clicked.connect(lambda: logs_add_movement_from_roi(self))
    tbl.itemChanged.connect(lambda item: _on_movement_item_changed(self, item))


def _build_points_group(self, parent, lv):
    g, v = _group("8. Reference points", parent, lv)
    self.logs_btn_points_mode = _mk_btn("Add points by clicking", '#ad1457', g, checkable=True,
                                        tip="Click on the plot: the point snaps to the nearest sample of the "
                                            "nearest visible curve (analysis axis); a press on an existing point "
                                            "drags it instead")
    v.addWidget(self.logs_btn_points_mode)
    self.logs_points_table = _mk_table(g, list(_POINT_HEADERS), min_h=110, multi=True)
    self.logs_points_table.setEditTriggers(_EDIT_TRIGGERS)
    for col, w in ((0, 30), (1, 112), (2, 46), (3, 76), (4, 76), (5, 76), (6, 72)):
        self.logs_points_table.setColumnWidth(col, w)
    self.logs_points_table.horizontalHeader().setStretchLastSection(True)       # Note (Remove mode)
    self.logs_points_table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
    v.addWidget(self.logs_points_table)
    v.addWidget(_hint("Double-click t or Value to type a new one (the point snaps to a sample of its curve). On the "
                      "plot, drag a point with the left button (Esc cancels).", g))
    self.logs_points_table.itemChanged.connect(lambda item: _on_point_item_changed(self, item))
    row = QHBoxLayout()
    self.logs_btn_points_del = _mk_btn("Delete selected point(s)", '#d32f2f', g)
    self.logs_btn_points_clear = _mk_btn("Clear points", '#757575', g)
    row.addWidget(self.logs_btn_points_del, stretch=2)
    row.addWidget(self.logs_btn_points_clear, stretch=1)
    v.addLayout(row)
    self.logs_btn_points_align = _mk_btn("Align curves at 2 selected points", '#4527a0', g,
                                         tip="Shift the curve of the second point in time so both points coincide")
    v.addWidget(self.logs_btn_points_align)
    self.logs_chk_points_value = QCheckBox("Also match the value (value offset)", g)
    v.addWidget(self.logs_chk_points_value)

    self.logs_btn_points_mode.toggled.connect(lambda on: logs_set_pick_mode(self, 'points' if on else None))
    self.logs_btn_points_del.clicked.connect(lambda: _on_delete_points_clicked(self))
    self.logs_btn_points_clear.clicked.connect(lambda: logs_clear_points(self))
    self.logs_btn_points_align.clicked.connect(lambda: _on_align_points_clicked(self))


def _build_export_group(self, parent, lv):
    g, v = _group("9. Export", parent, lv)
    self.logs_btn_export_results = _mk_btn("Export results CSV...", '#37474f', g,
                                           tip="Results view shown below the plot")
    self.logs_btn_export_aligned = _mk_btn("Export aligned data CSV...", '#37474f', g,
                                           tip="Visible curves on the analysis axis, offsets applied, common time grid (ROI)")
    self.logs_btn_save_fig = _mk_btn("Save figure PNG...", '#37474f', g)
    for b in (self.logs_btn_export_results, self.logs_btn_export_aligned, self.logs_btn_save_fig):
        v.addWidget(b)
    self.logs_btn_export_results.clicked.connect(lambda: _on_export_results_clicked(self))
    self.logs_btn_export_aligned.clicked.connect(lambda: _on_export_aligned_clicked(self))
    self.logs_btn_save_fig.clicked.connect(lambda: _on_save_fig_clicked(self))


# ----------------------------------------------------------------------------
# Refresh of the widgets from the state
# ----------------------------------------------------------------------------
def _built(self):
    return bool(getattr(self, 'logs_built', False))


def _refresh_everything(self, rescale=False):
    st = _state(self)
    _update_axes_from_curves(st)
    if st.ref_uid is None or _entry_by_uid(st, st.ref_uid) is None:
        st.ref_uid = _default_ref_uid(st)
    uids = {e.uid for e in st.entries}
    st.peaks = {u: p for u, p in st.peaks.items() if u in uids}
    st.movements = {u: m for u, m in st.movements.items() if u in uids}
    st.points = [p for p in st.points if p['uid'] in uids]
    if st.selected >= len(st.entries):
        st.selected = len(st.entries) - 1
    _apply_pause_lengths(self)
    _refresh_peak_list(self)            # a log with waits loaded can change the G-code pause lengths
    _refresh_live_notes(self)           # curves added / removed: which logs are cut, the reference
    if not _built(self):
        return
    _refresh_curves_table(self)
    _refresh_axes_panel(self)
    _refresh_ref_combo(self)
    _refresh_pause_controls(self)
    _refresh_pause_table(self, rebuild=True)
    _refresh_waits_view(self)
    _refresh_points_table(self)
    _sync_roi_widgets(self)
    _update_unit_suffixes(self)
    _update_duet_button(self)
    _redraw(self, rescale=rescale)


def _update_axes_from_curves(st):
    present = set()
    for e in st.entries:
        present |= set(e.curve.data)
    order = [a for a in la.AXIS_ORDER if a in present]
    order += [la.CMD_PREFIX + a for a in la.AXIS_ORDER if la.CMD_PREFIX + a in present]
    order += sorted(a for a in present if a not in order)
    st.known_axes = order
    st.enabled_axes = {a for a in st.enabled_axes if a in present}
    if st.analysis_axis not in present:
        st.analysis_axis = _default_axis(st)
    if not st.enabled_axes and st.analysis_axis:
        st.enabled_axes = {st.analysis_axis}


def _default_axis(st):
    """Axis with the largest range in the first log (platform DOF preferred), else the first axis."""
    entries = [e for e in st.entries if e.curve.kind == 'log'] + [e for e in st.entries if e.curve.kind != 'log']
    for e in entries:
        c = e.curve
        cands = [a for a in c.axes() if not a.startswith(la.CMD_PREFIX)]
        if not cands:
            continue
        rng = {}
        for a in cands:
            v = c.data[a]
            rng[a] = float(np.nanmax(v) - np.nanmin(v)) if v.size else 0.0
        dof = [a for a in la.PLATFORM_DOF if a in rng and rng[a] > 0.0]
        pool = dof or [a for a in cands if rng[a] > 0.0]
        if pool:
            return max(pool, key=lambda a: rng[a])
    return st.known_axes[0] if st.known_axes else None


def _refresh_curves_table(self):
    st = _state(self)
    tbl = self.logs_curves_table
    axis = st.analysis_axis
    tbl.blockSignals(True)
    try:
        tbl.clearContents()
        tbl.setRowCount(len(st.entries))
        self.logs_toff_spins = []
        self.logs_voff_spins = []
        for r, e in enumerate(st.entries):
            c = e.curve
            it = QTableWidgetItem("")
            it.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Checked if e.visible else Qt.Unchecked)
            it.setToolTip("Show / hide this curve")
            tbl.setItem(r, 0, it)
            it = QTableWidgetItem("")
            it.setIcon(_color_icon(e.color))
            it.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            it.setToolTip("Double-click to change the colour")
            tbl.setItem(r, 1, it)
            info, warn, tip = _info(c)
            it = QTableWidgetItem(c.name)
            it.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            it.setToolTip(tip)
            if e.uid == st.ref_uid:
                f = it.font()
                f.setBold(True)
                it.setFont(f)
            tbl.setItem(r, 2, it)
            kind = 'G-code' if c.kind == 'reference' else 'log'
            dev = _short_device(c.meta.get('device'))
            it = QTableWidgetItem(f"{kind} · {dev}" if dev else kind)
            it.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            it.setToolTip(("G-code reference" if c.kind == 'reference' else "LogIQ log")
                          + (f" · {c.meta.get('device')}" if c.meta.get('device') else ""))
            tbl.setItem(r, 3, it)

            sp = _mk_spin(self, tbl, float(c.time_offset), -1e5, 1e5, 3, 0.001, label="Time offset (s)")
            sp.setToolTip("Time offset (s) added to this curve's time")
            sp.valueChanged.connect(lambda val, uid=e.uid: _on_toff_spin(self, uid, val))
            tbl.setCellWidget(r, 4, sp)
            self.logs_toff_spins.append(sp)

            sv = _mk_spin(self, tbl, _vof(c, axis) if axis else 0.0, -1e5, 1e5, 4, 0.001, label="Value offset")
            sv.setEnabled(bool(axis) and c.has(axis))
            sv.setToolTip(f"Value offset added to {axis}" if axis else "Value offset")
            sv.valueChanged.connect(lambda val, uid=e.uid: _on_voff_spin(self, uid, val))
            tbl.setCellWidget(r, 5, sv)
            self.logs_voff_spins.append(sv)

            it = QTableWidgetItem(info)
            it.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            it.setToolTip(tip)
            if warn:
                it.setForeground(QBrush(QColor('#c62828')))
                f = it.font()
                f.setBold(True)
                it.setFont(f)
                for col in (2, 3):
                    tbl.item(r, col).setBackground(QBrush(QColor('#ffebee')))
            tbl.setItem(r, 6, it)
        tbl.setHorizontalHeaderItem(5, _voff_header_item(st, axis))
        if 0 <= st.selected < len(st.entries):
            tbl.selectRow(st.selected)
        else:
            tbl.clearSelection()
    finally:
        tbl.blockSignals(False)
    _update_selected_label(self)


def _sync_offset_spins(self):
    st = _state(self)
    axis = st.analysis_axis
    for i, e in enumerate(st.entries):
        for spins, val, enabled in ((getattr(self, 'logs_toff_spins', []), e.curve.time_offset, True),
                                    (getattr(self, 'logs_voff_spins', []),
                                     _vof(e.curve, axis) if axis else 0.0,
                                     bool(axis) and e.curve.has(axis))):
            if i < len(spins):
                s = spins[i]
                s.blockSignals(True)
                s.setValue(float(val))
                s.setEnabled(enabled)
                s.blockSignals(False)
    if _built(self):
        self.logs_curves_table.setHorizontalHeaderItem(5, _voff_header_item(st, axis))


def _voff_header_item(st, axis):
    """Header of the curves table's value-offset column: 'v offset (<axis> <unit>)', a long axis
    name elided (full text in the tooltip)."""
    if not axis:
        return QTableWidgetItem("v offset")
    u = _axis_unit(st, axis)
    it = QTableWidgetItem(f"v offset ({_elide_mid(axis, _LEGEND_AXIS_MAX_CHARS)} {u})")
    it.setToolTip(f"Value offset added to {axis} ({u})")
    return it


def _update_selected_label(self):
    st = _state(self)
    lbl = getattr(self, 'logs_selected_label', None)
    if lbl is None:
        return
    if 0 <= st.selected < len(st.entries):
        e = st.entries[st.selected]
        lbl.setText(f"Selected: {e.curve.name} ({'G-code ref' if e.curve.kind == 'reference' else 'log'})")
    else:
        lbl.setText("Selected: –")


def _std_axis(axis):
    """A platform / phantom axis of the TRACE logs ('SI', 'Cmd Pitch' ...): short, never elided."""
    a = str(axis)
    if a.startswith(la.CMD_PREFIX):
        a = a[len(la.CMD_PREFIX):]
    return a in la.AXIS_ORDER


def _set_axis_check_text(cb, axis, unit):
    """Axis checkbox text '<axis>' (mm) or '<axis> (<unit>)'; any other than a standard axis name is
    elided in the middle to _AXIS_CHECK_TEXT_PX (style sheet font) so that a long name (a column of
    a file read back) never widens the left panel; the tooltip holds the full text."""
    suffix = '' if unit == 'mm' else f" ({unit})"
    full = f"{axis}{suffix}"
    if getattr(cb, '_logs_full_text', None) == full:
        return
    try:
        cb.ensurePolished()                 # the style sheet font
        fm = cb.fontMetrics()
        room = max(4 * fm.horizontalAdvance('…'), _AXIS_CHECK_TEXT_PX - fm.horizontalAdvance(suffix))
        shown = full if _std_axis(axis) else fm.elidedText(axis, Qt.ElideMiddle, room) + suffix
    except Exception:
        shown = full if _std_axis(axis) else _elide_mid(axis, 14) + suffix
    cb.setText(shown)
    tip = full
    if axis.startswith(la.CMD_PREFIX):
        tip = (f"{full}\n" if shown != full else '') + \
            f"Requested position {axis[len(la.CMD_PREFIX):]} (Cmd_* column)"
    cb.setToolTip(tip)
    cb._logs_full_text = full


def _distinct_axis_checks(self, units):
    """Axis checkbox texts that were elided to the same text (e.g. 'SI log_…case_02' for several
    runs read back from an aligned export) are elided again around the part where the axis names
    differ, within the same pixel room; the tooltips keep the full names."""
    groups = {}
    for a, cb in self.logs_axis_checks.items():
        groups.setdefault(cb.text(), []).append(a)
    for txt, axes in groups.items():
        if len(axes) < 2:
            continue
        cbs = [self.logs_axis_checks[a] for a in axes]
        sufs = ['' if units[a] == 'mm' else f" ({units[a]})" for a in axes]
        try:
            fm = cbs[0].fontMetrics()
            fits = lambda s, suf: fm.horizontalAdvance(s + suf) <= max(  # noqa: E731
                4 * fm.horizontalAdvance('…'), _AXIS_CHECK_TEXT_PX)
        except Exception:
            fits = lambda s, suf: True  # noqa: E731
        n = max(8, len(txt) - len(sufs[0]))
        while True:
            shown = _distinct_texts([txt] * len(axes), axes, n)
            if n <= 8 or all(fits(s, suf) for s, suf in zip(shown, sufs)):
                break
            n -= 1
        for cb, s, suf in zip(cbs, shown, sufs):
            cb.setText(s + suf)


def _axis_combo_tip(self):
    combo = getattr(self, 'logs_axis_combo', None)
    if combo is not None:
        cur = combo.currentText()
        combo.setToolTip(f"{cur}\n{_AXIS_COMBO_TIP}" if cur else _AXIS_COMBO_TIP)


def _refresh_axes_panel(self, rebuild_combo=True):
    st = _state(self)
    grid = self.logs_axes_grid
    units = {a: _axis_unit(st, a) for a in st.known_axes}
    if list(self.logs_axis_checks) != st.known_axes:
        for cb in self.logs_axis_checks.values():
            grid.removeWidget(cb)
            cb.deleteLater()
        self.logs_axis_checks = {}
        for k, a in enumerate(st.known_axes):
            cb = QCheckBox(self.logs_axes_box)
            if a.startswith(la.CMD_PREFIX):
                cb.setStyleSheet("QCheckBox { color: #6d4c41; }")
            cb.toggled.connect(lambda on, ax_=a: logs_set_axis_enabled(self, ax_, on))
            grid.addWidget(cb, k // 3, k % 3)
            self.logs_axis_checks[a] = cb
    for a, cb in self.logs_axis_checks.items():
        _set_axis_check_text(cb, a, units[a])
        cb.blockSignals(True)
        cb.setChecked(a in st.enabled_axes)
        cb.blockSignals(False)
    _distinct_axis_checks(self, units)
    self.logs_axes_empty.setVisible(not st.known_axes)
    combo = self.logs_axis_combo
    combo.blockSignals(True)
    if rebuild_combo or combo.count() != len(st.known_axes):
        combo.clear()
        for a in st.known_axes:
            txt = f"{a} ({units[a]})"
            combo.addItem(txt, a)
            combo.setItemData(combo.count() - 1, txt, Qt.ToolTipRole)
    if st.analysis_axis in st.known_axes:
        combo.setCurrentIndex(st.known_axes.index(st.analysis_axis))
    combo.blockSignals(False)
    _axis_combo_tip(self)


def _refresh_ref_combo(self):
    st = _state(self)
    combo = self.logs_ref_combo
    combo.blockSignals(True)
    combo.clear()
    sel = -1
    for i, e in enumerate(st.entries):
        kind = 'G-code' if e.curve.kind == 'reference' else 'log'
        combo.addItem(f"{e.curve.name} ({kind})", e.uid)
        if e.uid == st.ref_uid:
            sel = i
    if sel >= 0:
        combo.setCurrentIndex(sel)
    combo.blockSignals(False)
    _ref_combo_tip(self)


def _ref_combo_tip(self):
    combo = getattr(self, 'logs_ref_combo', None)
    if combo is not None:
        combo.setToolTip(combo.currentText() or "Reference curve of alignment, pauses and compare")


def _gcode_entries(st):
    """Entries of G-code references (rebuilt with la.with_pause_durations when their pause lengths change)."""
    return [e for e in st.entries if e.curve.kind == 'reference' and isinstance(e.curve.meta.get('_source'), dict)]


def _wait_logs(st):
    """Log entries with logged sensor waits (marked or not marked), curves table order."""
    return [e for e in st.entries if _has_waits(e.curve)]


def _pause_source(st):
    """The log whose logged waits give the G-code pause lengths: the chosen one while it is loaded and
    has waits, else the first log with waits (None when no log has any)."""
    logs = _wait_logs(st)
    for e in logs:
        if e.uid == st.pause_source_uid:
            return e
    return logs[0] if logs else None


def _target_pause_lengths(st, ref_entry):
    """(lengths, pairing) of a G-code reference in the current pause mode: Show = the lengths of the
    source log's waits (la.pair_pause_waits), Remove = 0 (the waits are cut out of the logs)."""
    src = _pause_source(st)
    info = la.pair_pause_waits(ref_entry.curve, src.curve if src is not None else None)
    if st.pause_mode == 'remove':
        return [0.0] * len(info), info
    return [float(p['length']) for p in info], info


def _apply_pause_lengths(self):
    """Every G-code reference rebuilt with the pause lengths of the current mode when they changed
    (overlays on it remapped exactly, see _remap_reference_overlays); st.pause_info = the pairing of
    the reference curve; the 'Pauses' results view follows.  Returns True when a curve changed."""
    st = _state(self)
    changed = False
    for e in _gcode_entries(st):
        target, info = _target_pause_lengths(st, e)
        cur = [float(x) for x in (e.curve.meta.get('pause_durations') or [])]
        cur = cur[:len(target)] + [0.0] * (len(target) - len(cur))
        if target and cur != target:
            old = e.curve
            e.curve = la.with_pause_durations(old, target)
            _remap_reference_overlays(st, e, old.meta, e.curve.meta)
            changed = True
    ref = _ref_entry(st)
    st.pause_info = _target_pause_lengths(st, ref)[1] if ref is not None and ref in _gcode_entries(st) else []
    _refresh_pauses_view(self)
    if changed:
        _rebuild_movements_view(self)
    return changed


def _refresh_pauses_view(self):
    """The 'Pauses' results view (= its CSV export) from the reference's G-code pauses as they are now
    (pause mode, source log, the reference's time offset, which logs are shown cut); dropped when the
    reference is not a G-code.  Only rewritten when a row or its time-base note changed."""
    st = _state(self)
    ref = _ref_entry(st)
    if st.pause_info and ref is not None and ref in _gcode_entries(st):
        rows = _pause_rows(st, ref, view=True)
        old = st.results.get('Pauses')
        if (old is None or list(old[0]) != _PAUSES_VIEW_HEADERS or len(old[1]) != len(rows)
                or not all(_same_row(a, b) for a, b in zip(old[1], rows))
                or st.results_ref.get('Pauses') != ref.uid
                or st.results_notes.get('Pauses') != _time_base_note(st, 'Pauses')):
            _set_results(self, 'Pauses', list(_PAUSES_VIEW_HEADERS), rows, show=False, ref_uid=ref.uid)
    elif 'Pauses' in st.results:
        _drop_results(self, 'Pauses')


def _cut_logs(st):
    """Log entries shown without their logged waits now (Remove mode, visible, with marked waits)."""
    return [e for e in st.entries if e.visible and _cut_active(st, e)]


def _remove_status(st, ref_curve):
    """Remove mode: per G-code pause of a reference, what was cut out of the visible logs THERE, from
    the pairing of each visible cut log's waits with the G-code's sensor_wait pauses
    (la.pair_pause_waits: in order, only when the counts match; nothing guessed).  One dict per pause:
    removed [(log name, length)], not_marked [log names], unpaired [log names: other number of waits],
    n_logs (visible cut logs), label."""
    logs = _cut_logs(st)
    pauses = ref_curve.meta.get('pauses') or []
    out = [{'removed': [], 'not_marked': [], 'unpaired': [], 'n_logs': len(logs), 'label': str(lab)}
           for lab, _ in pauses]
    for e in logs:
        for i, p in enumerate(la.pair_pause_waits(ref_curve, e.curve)[:len(out)]):
            if p['label'] != la.SENSOR_WAIT_LABEL:
                continue
            if p['kind'] == 'marked':
                out[i]['removed'].append((e.curve.name, float(p['length'])))
            elif p['kind'] == 'not_marked':
                out[i]['not_marked'].append(e.curve.name)
            else:
                out[i]['unpaired'].append(e.curve.name)
    return out


def _len_range(lengths):
    """'1.739 s' (one length) or '2.15-4.50 s' (several logs): short enough for the pause table's Note column."""
    lo, hi = min(lengths), max(lengths)
    return f"{lo:.3f} s" if hi - lo < 0.0005 else f"{lo:.2f}-{hi:.2f} s"


def _remove_label(s):
    """Plot label (after the pause name) of a G-code pause in Remove mode, from its _remove_status:
    it says 'removed' only where a visible log's wait paired with this pause was cut out."""
    if s['label'] != la.SENSOR_WAIT_LABEL:
        return "(no logged wait)"               # M226 / M25 / M0 ...: TRACE logs no wait for them
    n, N = len(s['removed']), s['n_logs']
    if n:
        if n == N:
            return "(wait removed)" if N == 1 else "(waits removed)"
        return f"(waits removed from {n} of {N} logs)"
    if s['unpaired']:
        return "(not paired: no wait removed here)"
    if s['not_marked']:
        return "(wait not marked: not removed)"
    return "(no logged wait)"


def _pause_note(st, p, rs=None):
    """Note of a G-code pause in the current mode (pause table, 'Pauses' view); rs = its _remove_status
    (Remove mode).  Numbers of the log's notes shown with a decimal point (_dots)."""
    note = _dots(p.get('note') or '')
    if st.pause_mode != 'remove':
        return note
    if rs is None or p['label'] != la.SENSOR_WAIT_LABEL:
        return note
    n, N = len(rs['removed']), rs['n_logs']
    if n:
        rng = _len_range([L for _, L in rs['removed']])
        return f"removed ({rng})" if n == N else f"removed from {n} of {N} logs ({rng})"
    if not N:
        # no log is shown cut: the source log (it has this wait) is hidden
        return "not removed: the log with this wait is hidden" if p['kind'] == 'marked' else note
    why = []
    if rs['unpaired']:
        why.append(f"not paired ({', '.join(rs['unpaired'])}: other number of logged waits than G-code pauses)")
    if rs['not_marked']:
        why.append("wait not marked" + (f" ({note.split(':', 1)[1].strip()})" if p['kind'] == 'not_marked'
                                        and ':' in note else ""))
    return "no wait removed here: " + ("; ".join(why) if why else note)


def _pause_rows(st, ref, view=False):
    """Rows of the pause table ('#', 'Pause', 'G-code t (s)', 'Length (s)', 'Ended by', 'Note') or of the
    'Pauses' view ('Pause #', 'Label', 'G-code t (s)', 'Start on plot (s)', 'Length (s)', 'Ended by', 'Note',
    'From'): one per G-code pause of the reference.  'G-code t' is the planner time of the pause (as in
    the G-code and the Planning tab); 'Start on plot' adds the earlier pause lengths and the reference's
    time offset; the length is the pause's length now, how its logged wait ended."""
    pauses = list(ref.curve.meta.get('pauses') or [])
    planner = list(ref.curve.meta.get('pauses_gcode') or [])
    durs = [float(x) for x in (ref.curve.meta.get('pause_durations') or [])]
    durs = durs[:len(pauses)] + [0.0] * (len(pauses) - len(durs))
    src = _pause_source(st)
    rstat = _remove_status(st, ref.curve) if st.pause_mode == 'remove' else None
    rows = []
    for i, (label, tp) in enumerate(pauses):
        p = st.pause_info[i] if i < len(st.pause_info) else {'kind': 'none', 'note': '', 'ended_by': '',
                                                             'length': 0.0, 'label': label}
        tg = float(p['t_gcode']) if 't_gcode' in p else (float(planner[i][1]) if i < len(planner) else float(tp))
        rs = rstat[i] if rstat is not None and i < len(rstat) else None
        ended = p.get('ended_by', '') if p['kind'] == 'marked' else ''
        note = _pause_note(st, p, rs)
        if view:
            if rs is not None:
                frm = ', '.join(n for n, _ in rs['removed'])
            else:
                frm = src.curve.name if (src is not None and p['kind'] != 'none') else ''
            rows.append([i + 1, str(label), tg, float(tp) + ref.curve.time_offset, durs[i], ended, note, frm])
        else:
            rows.append([i + 1, str(label), tg, durs[i], ended, note])
    return rows


def _pause_tip(st, ref, i, rs=None):
    p = st.pause_info[i] if i < len(st.pause_info) else None
    pauses = ref.curve.meta.get('pauses') or []
    lines = []
    if i < len(pauses):
        tg = float(p['t_gcode']) if p else float(pauses[i][1])
        lines.append(f"{pauses[i][0]} at G-code time {tg:.3f} s (planner); on the plot at "
                     f"{float(pauses[i][1]) + ref.curve.time_offset:.3f} s")
    src = _pause_source(st)
    if p is None or p['kind'] == 'none':
        lines.append(_dots(p['note']) if p else '')
    elif p['kind'] == 'marked':
        lines.append(f"Logged wait of {src.curve.name if src else '?'}: {_wait_timing_text(p['wait'])}")
    else:
        w = p['wait']
        lines.append(f"{src.curve.name if src else '?'}: wait not marked, received at {w['received']:.3f} s "
                     f"({_sent_text(w.get('sent_from'), w['received'])}): {_dots(w.get('reason') or '')}")
    if st.pause_mode == 'remove':
        lines.append("Pauses: Remove logged waits - the pause has length 0, the waits are cut out of the logs")
        if rs is not None:
            for name, L in rs['removed']:
                lines.append(f"  {name}: its wait for this pause removed ({L:.3f} s)")
            for name in rs['not_marked']:
                lines.append(f"  {name}: wait not marked - nothing removed here")
            for name in rs['unpaired']:
                lines.append(f"  {name}: its waits are not paired with the G-code pauses (other number) - "
                             f"they are removed where the amber dotted cut lines are")
    return "\n".join(x for x in lines if x)


def _refresh_pause_table(self, rebuild=False):
    """Pause table (read-only): one row per G-code pause of the reference, the summary line under it."""
    st = _state(self)
    tbl = getattr(self, 'logs_pause_table', None)
    if tbl is None:
        return
    ref = _ref_entry(st)
    is_gcode = ref is not None and isinstance(ref.curve.meta.get('_source'), dict)
    rows = _pause_rows(st, ref) if is_gcode else []
    rstat = _remove_status(st, ref.curve) if is_gcode and st.pause_mode == 'remove' else None
    src = _pause_source(st)
    if ref is None:
        txt = "G-code pauses: no reference curve"
    elif not is_gcode:
        txt = f"G-code pauses: reference '{ref.curve.name}' is a log (no pauses)"
    else:
        txt = f"G-code pauses of '{ref.curve.name}': {len(rows)}"
        if rows:
            if st.pause_mode == 'remove':
                n_cut = len(_cut_logs(st))
                txt += (f" · logged waits removed from {n_cut} log(s): pauses shown with length 0 (G-code time)"
                        if n_cut else " · no logged waits to remove: pauses shown with length 0")
            elif src is None:
                txt += " · no logged waits: pauses shown with length 0"
            else:
                n = sum(1 for p in st.pause_info if p['kind'] == 'marked')
                txt += (f" · lengths from the logged waits of '{src.curve.name}'" if n else
                        f" · '{src.curve.name}': {_dots(st.pause_info[0]['note']) if st.pause_info else ''}")
    self.logs_pause_label.setText(txt)
    self.logs_pause_label.setToolTip(txt)
    tbl.blockSignals(True)
    try:
        if rebuild or tbl.rowCount() != len(rows):
            tbl.clearContents()
            tbl.setRowCount(len(rows))
        for r, row in enumerate(rows):
            tip = _pause_tip(st, ref, r, rstat[r] if rstat is not None and r < len(rstat) else None)
            for c, val in enumerate(row):
                it = _set_cell(tbl, r, c, val, _PAUSE_HEADERS[c], editable=False, reuse=not rebuild)
                if it.toolTip() != tip:
                    it.setToolTip(tip)
    finally:
        tbl.blockSignals(False)


def _refresh_pause_controls(self):
    """'Pauses:' radio buttons and the 'Pause lengths from:' combo from the state."""
    st = _state(self)
    for wname, on in (('logs_radio_pause_show', st.pause_mode != 'remove'),
                      ('logs_radio_pause_remove', st.pause_mode == 'remove')):
        w = getattr(self, wname, None)
        if w is not None and w.isChecked() != on:
            w.blockSignals(True)
            w.setChecked(on)
            w.blockSignals(False)
    combo = getattr(self, 'logs_pause_source_combo', None)
    if combo is None:
        return
    logs = _wait_logs(st)
    src = _pause_source(st)
    combo.blockSignals(True)
    try:
        items = [(e.curve.name, e.uid) for e in logs]
        if [(combo.itemText(i), combo.itemData(i)) for i in range(combo.count())] != items:
            combo.clear()
            for name, uid in items:
                combo.addItem(name, uid)
                combo.setItemData(combo.count() - 1, name, Qt.ToolTipRole)
        if not items:
            combo.clear()
            combo.addItem("(no log with logged waits)", None)
        i = combo.findData(src.uid) if src is not None else 0
        combo.setCurrentIndex(max(0, i))
        combo.setEnabled(bool(items) and st.pause_mode != 'remove')
        tip = ("Log whose logged waits give the lengths of the G-code's sensor_wait pauses (Show mode)"
               + (f"\nNow: {src.curve.name}" if src is not None else "\nNo loaded log has logged waits"))
        combo.setToolTip(tip)
    finally:
        combo.blockSignals(False)


def _waits_rows(st):
    """'Waits' view: per log, its logged sensor waits (marked and not marked) and failed Duet message
    reads in time order (recorded run time).  '#' numbers the sensor waits of the log in time order
    (marked and not marked: the same number as the G-code pause they pair with); a failed read is
    'read failed'.  'Duet sent from / to (s)': the window in which the Duet sent the message (the real
    start lies in it; from is empty when unknown: 'before T s')."""
    nan = float('nan')
    rows = []
    for e in st.entries:
        c = e.curve
        if c.kind != 'log':
            continue
        m = c.meta
        items = [(float(it['received']), 0, it) for it in la.logged_wait_items(c)]
        items += [(float(f['t']), 1, {'kind': 'read_failed', 'wait': f}) for f in m.get('message_read_failures') or []]
        items.sort(key=lambda x: (x[0], x[1]))
        n = 0
        for _, _, it in items:
            w = it['wait']
            if it['kind'] == 'read_failed':
                a, b = w.get('sent_from'), w.get('sent_to')
                rows.append([c.name, 'read failed', float(w['t']), nan if a is None else float(a),
                             nan if b is None else float(b), nan, nan, '',
                             f"Duet message read failed at {w['t']:.3f} s: messages sent then may be lost (a wait "
                             f"start or end may be missing)", 0])
                continue
            n += 1
            rec = float(w['received'])
            sf = nan if w.get('sent_from') is None else float(w['sent_from'])
            if it['kind'] == 'marked':
                parts = [_dots(w.get('end_note') or '')]
                if w.get('source') == 'rows':
                    parts.append("no notes: start / end from the -1000 rows")
                elif w.get('sent_from') is None:
                    parts.append(f"the Duet sent the message before {rec:.3f} s (no earlier read)")
                rows.append([c.name, n, rec, sf, rec, float(w['end']), float(w.get('length', 0.0)),
                             w.get('end_by') or '', "; ".join(x for x in parts if x), int(w.get('rows', 0))])
            else:
                rows.append([c.name, n, rec, sf, rec, nan, nan, '',
                             "wait not marked (no row has -1000): " + _dots(w.get('reason') or 'it may have ended '
                                                                             'before LogIQ knew of it'), 0])
    return rows


def _refresh_waits_view(self):
    """'Waits' results view (exportable) from the loaded logs; dropped when no log has any."""
    st = _state(self)
    rows = _waits_rows(st)
    if rows:
        old = st.results.get('Waits')
        if old is None or list(old[0]) != _WAITS_HEADERS or len(old[1]) != len(rows) \
                or not all(_same_row(a, b) for a, b in zip(old[1], rows)):
            _set_results(self, 'Waits', list(_WAITS_HEADERS), rows, show=False)
    elif 'Waits' in st.results:
        _drop_results(self, 'Waits')


def _point_tv(st, p):
    """Current (t, value) of a reference point (displayed time base, offsets applied, snapped to the
    curve sample); (NaN, NaN) when its sample lies inside a removed wait (Remove mode)."""
    e = _entry_by_uid(st, p['uid'])
    if e is None or not e.curve.has(p['axis']):
        return float('nan'), float('nan')
    vc = _vc(st, e)
    if vc is e.curve:
        return la.nearest_point(e.curve, p['axis'], p['t_raw'] + e.curve.time_offset)
    if _in_removed(st, e, p['t_raw']):
        return float('nan'), float('nan')
    return la.nearest_point(vc, p['axis'], _r2d(st, e, p['t_raw']))


def _point_note(st, p):
    """Note of a point in the points table: why it is not drawn."""
    e = _entry_by_uid(st, p['uid'])
    if e is not None and _in_removed(st, e, p['t_raw']):
        return f"{_REMOVED_NOTE} (recorded at {float(p['t_raw']) + e.curve.time_offset:.3f} s)"
    return ''


def _points_rows(st):
    rows = []
    prev = None
    for i, p in enumerate(st.points):
        e = _entry_by_uid(st, p['uid'])
        t, v = _point_tv(st, p)
        dt = t - prev[0] if prev is not None else float('nan')
        dv = v - prev[1] if prev is not None else float('nan')
        rows.append([i + 1, e.curve.name if e else '?', p['axis'], t, v, dt, dv, _point_note(st, p)])
        if math.isfinite(t):
            prev = (t, v)
    return rows


def _new_point(st, uid, axis, t_raw):
    st.point_counter += 1
    p = {'id': st.point_counter, 'uid': uid, 'axis': axis, 't_raw': float(t_raw)}
    st.points.append(p)
    return p


def _point_id(st, p):
    if p.get('id') is None:
        st.point_counter += 1
        p['id'] = st.point_counter
    return p['id']


def _selected_point_ids(self):
    """Ids of the points selected in the points table (the selection follows the points, not the
    row numbers, so a delete or a removed curve never moves it onto another point)."""
    tbl = getattr(self, 'logs_points_table', None)
    if tbl is None:
        return set()
    ids = set()
    for r in {ix.row() for ix in tbl.selectedIndexes()}:
        it = tbl.item(r, 0)
        pid = it.data(Qt.UserRole) if it is not None else None
        if pid is not None:
            ids.add(int(pid))
    return ids


def _row_ids(tbl):
    """Ids stored in column 0 (Qt.UserRole) of every row of a points / movements table."""
    out = []
    for r in range(tbl.rowCount()):
        it = tbl.item(r, 0)
        v = it.data(Qt.UserRole) if it is not None else None
        out.append(int(v) if v is not None else None)
    return out


def _set_cell(tbl, r, c, val, header, editable=False, reuse=False):
    """Cell (r, c) of a points / movements table showing val (formatted for its header).  reuse:
    the item already there is updated in place (no new item: an edited cell keeps its item while
    its own itemChanged runs).  Only editable cells carry Qt.ItemIsEditable."""
    text, key = _fmt_value(val, header), _num_key(val)
    it = tbl.item(r, c) if reuse else None
    if isinstance(it, _NumItem):
        if it.text() != text:
            it.setText(text)
        it._key = key
    else:
        it = _NumItem(text, key)
        tbl.setItem(r, c, it)
    flags = _FLAGS_EDIT if editable else _FLAGS_RO
    if it.flags() != flags:
        it.setFlags(flags)
    if key is not None and it.data(Qt.TextAlignmentRole) is None:     # (every setter emits dataChanged)
        it.setTextAlignment(_ALIGN_NUM)
    return it


def _refresh_points_table(self):
    st = _state(self)
    rows = _points_rows(st)
    tbl = getattr(self, 'logs_points_table', None)
    if tbl is not None:
        ids = [_point_id(st, p) for p in st.points]
        # same points in the same order (a point moved): the cells are updated in place
        same = tbl.rowCount() == len(rows) and _row_ids(tbl) == ids
        sel_ids = _selected_point_ids(self)
        tbl.blockSignals(True)
        try:
            if not same:
                tbl.clearSelection()
                tbl.clearContents()
                tbl.setRowCount(len(rows))
            hdrs = _POINT_HEADERS
            keep = []
            for r, row in enumerate(rows):
                pid = ids[r]
                if pid in sel_ids:
                    keep.append(r)
                e = _entry_by_uid(st, st.points[r]['uid'])
                for c, val in enumerate(row):
                    it = _set_cell(tbl, r, c, val, hdrs[c], editable=c in _POINT_EDIT_COLS, reuse=same)
                    if c == 0:
                        it.setData(Qt.UserRole, pid)
                    if c == 1 and e is not None:
                        _set_icon_color(it, e.color)
                    if c in _POINT_EDIT_COLS:
                        tip = ("Double-click (or F2) to type a new value: the point snaps to the nearest sample of "
                               "its curve") if not row[7] else (
                            f"{row[7]}: switch Pauses to 'Show (real time)' (section 4) to see or edit it")
                        if it.toolTip() != tip:
                            it.setToolTip(tip)
                    if c == 7 and it.toolTip() != row[7]:
                        it.setToolTip(row[7])
            if not same:
                sm = tbl.selectionModel()
                for r in keep:
                    sm.select(tbl.model().index(r, 0), QItemSelectionModel.Select | QItemSelectionModel.Rows)
        finally:
            tbl.blockSignals(False)
    if rows:
        _set_results(self, 'Points', ['#', 'Curve', 'Axis', 't (s)', 'Value', 'dt to previous (s)',
                                      'dvalue to previous', 'Note'], rows, show=False)
    elif 'Points' in st.results:
        _drop_results(self, 'Points')


# ---------------- movements: model helpers and the movements table ----------------
def _new_movement_id(st):
    st.movement_counter += 1
    return st.movement_counter


def _mv_norm(st, mv):
    """Pad the per-movement lists of a st.movements entry to its segments (an entry built by older
    code or by hand may lack some), give every movement an id and keep them sorted by start.
    Returns the number of movements."""
    segs = [tuple(s) for s in (mv.get('segments') or [])]
    n = len(segs)
    for key, default in _MV_DEFAULTS.items():
        lst = list(mv.get(key) or [])
        mv[key] = lst[:n] + [default] * (n - len(lst))
    ids = [i for i in list(mv.get('ids') or [])[:n]]
    while len(ids) < n:
        ids.append(_new_movement_id(st))
    mv['ids'] = ids
    mv['segments'] = segs
    if any(segs[k][0] > segs[k + 1][0] for k in range(n - 1)):
        order = sorted(range(n), key=lambda k: segs[k][0])
        for key in _MV_LIST_KEYS:
            mv[key] = [mv[key][k] for k in order]
    return n


def _movement_items(st):
    """[(entry, movement dict, k)] of every movement in table order: curves table order, then start."""
    out = []
    for e in st.entries:
        mv = st.movements.get(e.uid)
        if not mv:
            continue
        out.extend((e, mv, k) for k in range(_mv_norm(st, mv)))
    return out


def _movement_by_id(st, mid):
    """(entry, movement dict, k) of the movement with id mid, or None."""
    if mid is None:
        return None
    for e in st.entries:
        mv = st.movements.get(e.uid)
        if mv and _mv_norm(st, mv) and mid in mv['ids']:
            return e, mv, mv['ids'].index(mid)
    return None


def _mv_stats(curve, axis, t0, t1, view=None):
    """la.movement_stats of [t0, t1] (displayed time base) plus the offsets and the view key
    (_view_key) it was computed at."""
    s = la.movement_stats(curve, axis, t0, t1)
    s['_toff'] = float(curve.time_offset)
    s['_voff'] = _vof(curve, axis)
    s['_view'] = view
    return s


def _detected_stats(m, flags, curve, axis, view=None):
    """Stats of a movement from detect_movements (keys read with .get; flags = _gap_flags(m))."""
    def num(key, default=float('nan')):
        try:
            return float(m.get(key, default))
        except (TypeError, ValueError):
            return default
    t0, t1 = num('t_start'), num('t_stop')
    return {'t_start': t0, 't_stop': t1, 'duration': num('duration', t1 - t0), 'v_start': num('v_start'),
            'v_stop': num('v_stop'), 'delta': num('delta'), 'peak_speed': num('peak_speed'),
            'complete': bool(m.get('complete', True)), 'in_gap': flags[0], 'start_in_gap': flags[1],
            'stop_in_gap': flags[2], '_toff': float(curve.time_offset), '_voff': _vof(curve, axis),
            '_view': view}


def _stats_for_view(st, e, mv, k):
    """mv['stats'][k] for the current view of entry e (_view_key).  Numbers stored for another view
    (pause mode switched, reference pause lengths changed) are kept aside (s['_alt'] by view key), so
    switching back gives them again, exactly.  For the new view: a movement no removed wait / pause
    hold falls into (its duration is the same in both time bases) keeps its numbers, only its times
    move; one that a cut or a pause changes is computed again from its segment (la.movement_stats on
    the shown curve)."""
    key = _view_key(st, e)
    s = mv['stats'][k]
    if isinstance(s, dict) and s.get('_view') == key:
        return s
    alt = dict(s.get('_alt') or {}) if isinstance(s, dict) else {}
    if isinstance(s, dict):
        old = {kk: vv for kk, vv in s.items() if kk != '_alt'}
        alt[old.get('_view')] = old
    found = alt.pop(key, None)
    a, b = mv['segments'][k]
    ta, tb = _r2d(st, e, float(a)), _r2d(st, e, float(b))
    if found is not None:
        s_new = dict(found)
    elif isinstance(s, dict) and all(np.isfinite(float(s.get(x, np.nan))) for x in ('t_start', 't_stop', 'duration')) \
            and abs((tb - ta) - float(s['duration'])) <= 1e-9 * max(1.0, abs(tb)):
        s_new = {kk: vv for kk, vv in s.items() if kk != '_alt'}
        s_new.update(t_start=float(ta), t_stop=float(tb), _toff=float(e.curve.time_offset), _view=key)
    else:
        try:
            s_new = _mv_stats(_vc(st, e), mv.get('axis'), ta, tb, view=key)
        except Exception:
            s_new = {kk: float('nan') for kk in ('t_start', 't_stop', 'duration', 'v_start', 'v_stop', 'delta',
                                                 'peak_speed')}
            s_new.update(_toff=float(e.curve.time_offset), _voff=0.0, _view=key)
    s_new['_alt'] = alt
    mv['stats'][k] = s_new
    return s_new


def _movement_values(st, e, mv, k):
    """Movement k of entry e in the displayed time base (current offsets): dict(id, number, axis,
    t_start, t_stop, duration, v_start, v_stop, delta, peak_speed, complete, in_gap, start_in_gap,
    stop_in_gap, edited, note).  Its numbers are those stored when it was detected / edited (shifted
    by the offset changes since; recomputed for another view: _stats_for_view); the flags are those
    of the entry's lists."""
    c = e.curve
    axis = mv.get('axis')
    s = _stats_for_view(st, e, mv, k)
    dt = float(c.time_offset) - float(s.get('_toff', c.time_offset))
    dv = (_vof(c, axis) - float(s.get('_voff', 0.0))) if axis and c.has(axis) else 0.0
    complete, in_gap = bool(mv['complete'][k]), bool(mv['in_gap'][k])
    s_gap, e_gap = bool(mv['start_in_gap'][k]), bool(mv['stop_in_gap'][k])
    note = _movement_note(complete, in_gap, start_in_gap=s_gap, stop_in_gap=e_gap)
    edited = bool(mv['edited'][k])
    if edited:
        note = _EDITED_NOTE + (f"; {note}" if note else "")
    return {'id': mv['ids'][k], 'number': k + 1, 'axis': axis,
            't_start': s['t_start'] + dt, 't_stop': s['t_stop'] + dt, 'duration': s['duration'],
            'v_start': s['v_start'] + dv, 'v_stop': s['v_stop'] + dv, 'delta': s['delta'],
            'peak_speed': s['peak_speed'], 'complete': complete, 'in_gap': in_gap, 'start_in_gap': s_gap,
            'stop_in_gap': e_gap, 'edited': edited, 'note': note}


def _movement_unit(st):
    """Unit of the movements' axes (the analysis axis' unit when there are none)."""
    axes = {mv.get('axis') for mv in st.movements.values() if mv and mv.get('segments') and mv.get('axis')}
    if not axes and st.analysis_axis:
        axes = {st.analysis_axis}
    units = sorted({_axis_unit(st, a) for a in axes})
    return ' / '.join(units)


def _movement_headers(u):
    """Headers of the 'Movements' results view."""
    return ['Curve', 'Axis', '#', 'Start (s)', 'Stop (s)', 'Duration (s)', f'Start value ({u})', f'End value ({u})',
            f'Delta ({u})', f'Peak speed ({u}/s)', 'Complete', 'In gap', 'Note']


def _movement_table_headers(u):
    return ['#', 'Curve', 'Start (s)', 'Stop (s)', 'Duration (s)', f'Delta ({u})' if u else 'Delta', 'Note']


def _movement_view_row(e, d):
    """Row of the 'Movements' results view of movement values d (_movement_values) of entry e."""
    return [e.curve.name, d['axis'], d['number'], d['t_start'], d['t_stop'], d['duration'], d['v_start'],
            d['v_stop'], d['delta'], d['peak_speed'], d['complete'], d['in_gap'], d['note']]


def _movement_table_row(e, d):
    """What a movements-table row shows: (id, #, curve name, start, stop, duration, delta, note, hidden,
    colour, axis)."""
    return (d['id'], d['number'], e.curve.name, d['t_start'], d['t_stop'], d['duration'], d['delta'], d['note'],
            not e.visible, e.color, d['axis'])


def _movement_result_rows(st):
    return [_movement_view_row(e, _movement_values(st, e, mv, k)) for e, mv, k in _movement_items(st)]


def _is_nan(x):
    return isinstance(x, (float, np.floating)) and x != x


def _same_row(a, b):
    """Rows / cells equal (NaN equals NaN: a row with an undefined number is not 'changed')."""
    if a == b:
        return True
    if len(a) != len(b):
        return False
    return all(x == y or (_is_nan(x) and _is_nan(y)) for x, y in zip(a, b))


def _movements_sig(st):
    """Everything the movements table and the 'Movements' view show, as one comparable value, without
    computing any number: per curve with movements its uid, curve object, name, visibility, colour,
    time / value offset and the movement lists (ids, segments, edited and gap flags); plus the unit.
    Equal signatures = the same rows."""
    parts = []
    for e in st.entries:
        mv = st.movements.get(e.uid)
        if not mv or not _mv_norm(st, mv):
            continue
        c = e.curve
        axis = mv.get('axis')
        voff = _vof(c, axis) if axis and c.has(axis) else 0.0
        parts.append((e.uid, id(c), c.name, e.visible, e.color, float(c.time_offset), voff, axis,
                      tuple(mv['ids']), tuple(mv['segments']), tuple(mv['edited']), tuple(mv['complete']),
                      tuple(mv['in_gap']), tuple(mv['start_in_gap']), tuple(mv['stop_in_gap']),
                      _view_key(st, e)))
    return _movement_unit(st), tuple(parts)


def _sync_movements(self, force=None):
    """The movements table and the 'Movements' results view (= its CSV export) from st.movements, in
    the displayed time base (current offsets).  Nothing is done when nothing they show changed since
    the last call (signature, _movements_sig): every redraw calls it.  Otherwise only what changed is
    rewritten: the view's changed rows (in place in the results table when it is shown), the table's
    changed rows (in place when the same movements are listed, else the table is refilled and the
    selection follows the ids).  The view is dropped when no movement is left.  force: ids (or True =
    every row) of table rows rewritten anyway (a refused cell entry is restored).  True when anything
    was looked at again."""
    st = _state(self)
    tbl = getattr(self, 'logs_movements_table', None)
    sig = _movements_sig(st)
    view = st.results.get('Movements')
    cache = st.mv_cache
    valid = cache is not None and cache['tbl'] is tbl and (tbl is None or tbl.rowCount() == len(cache['rows']))
    if not force and valid and cache['sig'] == sig and cache['view'] is view:
        return False
    items = _movement_items(st)
    vals = [_movement_values(st, e, mv, k) for e, mv, k in items]
    u = sig[0]
    vrows = [_movement_view_row(e, d) for (e, _, _), d in zip(items, vals)]
    if vrows:
        hdrs = _movement_headers(u)
        if view is None or list(view[0]) != hdrs or len(view[1]) != len(vrows) \
                or not all(_same_row(a, b) for a, b in zip(view[1], vrows)):
            _update_results_view(self, 'Movements', hdrs, vrows)
    elif view is not None:
        _drop_results(self, 'Movements')
    trows = [_movement_table_row(e, d) for (e, _, _), d in zip(items, vals)]
    if tbl is not None:
        _fill_movements_table(self, tbl, trows, u, cache['rows'] if valid else None, force)
    st.mv_cache = {'sig': sig, 'view': st.results.get('Movements'), 'tbl': tbl, 'rows': trows}
    return True


def _rebuild_movements_view(self):
    """'Movements' results view (and the movements table) from st.movements after a movement is
    edited, added or deleted: one row per movement in table order, with its current numbers; dropped
    when none is left (see _sync_movements: only the changed rows are rewritten)."""
    _sync_movements(self)


def _update_results_view(self, name, headers, rows):
    """Store results view `name` (as _set_results(show=False)).  When it is the view shown with the
    same headers and number of rows, only its changed rows are rewritten in the results table, in
    place (sort order, scroll position and column widths stay; a column only grows when a new text
    does not fit), instead of refilling the table.  A table the user sorted is kept sorted: with many
    rows changed here (_sort_held, _resort_rows: ~0.1 s for 16k rows, where Qt's re-sort took 0.7-1.7 s),
    with few by Qt, cell by cell."""
    st = _state(self)
    old = st.results.get(name)
    tbl = getattr(self, 'logs_results_table', None)
    if old is None or tbl is None or st.current_results != name or list(old[0]) != list(headers) \
            or len(old[1]) != len(rows) or tbl.rowCount() != len(rows) or tbl.columnCount() != len(headers):
        _set_results(self, name, headers, rows, show=False)
        return
    st.results[name] = (list(headers), [list(r) for r in rows])
    note = _time_base_note(st, name)
    if st.results_notes.get(name) != note:
        st.results_notes[name] = note
        _refresh_results_note(self)             # the caption shows the view's note
    st.results_ref.pop(name, None)
    # the changed cells (stored row, column), as _same_row / _same_cell (NaN equals NaN), in flat int
    # lists: an offset or pause-mode change rewrites a cell of each of ~16k 'Peak list' rows, and an
    # object per cell / row would cost as much again in garbage collections
    n = len(headers)
    cr, cc, changed = [], [], []
    for r, (a, b) in enumerate(zip(old[1], rows)):
        if a == b:
            continue
        k = len(cc)
        for c, x, y in zip(range(n), a, b):
            if not (x == y or (_is_nan(x) and _is_nan(y))):
                cr.append(r)
                cc.append(c)
        for c in range(len(a), n):
            cr.append(r)
            cc.append(c)
        if len(cc) > k:
            changed.append(r)
    if not changed:
        return
    item, role = tbl.item, Qt.UserRole          # (a PySide6 enum lookup costs ~2 us: once)
    hh = tbl.horizontalHeader()
    sec, order = hh.sortIndicatorSection(), hh.sortIndicatorOrder()
    # stored row -> table row: where it was filled while no column sorts the table (only a sort moves
    # rows and it sets the indicator, which is cleared by a refill only); else from the stored rows
    pos = cur = None
    if not 0 <= sec < tbl.columnCount():
        if all(it is not None and it.data(role) == r for r in (changed[0], changed[-1]) for it in (item(r, 0),)):
            pos = range(len(rows))
    if pos is None:
        # cur: table row -> stored row, as remembered since Qt last moved the rows (_table_moved), checked
        # at three rows; else read (~25 ms for 16k rows)
        nr = tbl.rowCount()
        cur = getattr(tbl, '_order', None)
        if cur is None or len(cur) != nr or not all(
                it is not None and it.data(role) == cur[tr] for tr in {0, nr // 2, nr - 1} for it in (item(tr, 0),)):
            cur = [it.data(role) if it is not None else None for it in map(item, range(nr), repeat(0, nr))]
        tbl._order = cur
        pos = {int(v): tr for tr, v in enumerate(cur) if v is not None}
        if any(r not in pos for r in changed):
            _fill_results_table(self, headers, rows)
            return
    # the changed cells' items (held, not rows: with a sort column a changed cell may move its row)
    items = [item(pos[r], c) for r, c in zip(cr, cc)]
    if any(it is None for it in items):
        _fill_results_table(self, headers, rows)
        return
    # a table the user sorted: with many rows changed it is kept sorted here (_sort_held, _resort_rows:
    # Qt's own re-sort compares the items in Python), with few Qt re-sorts each cell written
    sort_col = sec if tbl.isSortingEnabled() and 0 <= sec < n else -1
    keep_sorted = sort_col >= 0 and len(changed) >= _BULK_ROWS
    new = None                                  # new table row -> old table row, when the sort column changed
    if keep_sorted and sec in set(cc):
        if (len(pos) == len(rows) == len(cur) and None not in cur and all(len(a) > sec for a in old[1])
                and all(len(b) > sec for b in rows)):
            new = _sort_order([rows[int(r)][sec] for r in cur], headers[sec], order)
        keep_sorted = new is not None           # (numbers mixed with texts: Qt re-sorts, as before)
        if keep_sorted and new == list(range(len(new))):
            new = None                          # no row moves
    nudge = sort_col if not keep_sorted and len(changed) < _BULK_ROWS else -1
    m = tbl.model()
    longest = {}                                # column -> its longest new text (_grow_columns)

    def write():
        for it, r, c in zip(items, cr, cc):
            val = rows[r][c]
            text = _fmt_value(val, headers[c])
            if isinstance(it, _NumItem):
                key = _num_key(val)
                if c == nudge and not _same_cell(key, it._key) and it.text() == text:
                    it._key = key               # a new sort key, the same text: no signal, so Qt is told
                    ix = m.index(tbl.row(it), c)
                    m.dataChanged.emit(ix, ix)
                    continue
                it._key = key
            it.setText(text)                    # (Qt ignores an unchanged text: no signal)
            if len(text) > len(longest.get(c, '')):
                longest[c] = text

    tbl.blockSignals(True)
    try:
        if not keep_sorted:
            with _bulk_cells(tbl, [pos[r] for r in changed]):
                write()
        else:
            with _sort_held(tbl), _bulk_cells(tbl, range(tbl.rowCount())):
                trs = [pos[r] for r in cr]          # the changed cells' table rows
                if new is not None:                 # rows first in their new order (the sort column's
                    rank = _resort_rows(tbl, sec, new)      # items then know their position: written fast)
                    tbl._order = [cur[tr] for tr in new]
                    trs = [rank[tr] for tr in trs]
                _fresh_positions(tbl, trs, cc)
                write()
    finally:
        tbl.blockSignals(False)
    _grow_columns(tbl, longest)


def _sort_order(vals, header, order):
    """The order a column sorted by the user (order: its Qt.SortOrder) puts cells showing these values
    in (vals[tr]: the value of table row tr): new table row -> old table row, stably as Qt's own sort
    (equal keys keep their order) and by the keys of _NumItem.__lt__: numbers (NaN / inf as -inf) when
    every value is one, texts when none is; None for a mix (no total order: Qt sorts it)."""
    desc = order == Qt.DescendingOrder
    if all(type(v) is float or type(v) is int for v in vals):       # (the common case: in numpy)
        k = np.asarray(vals, dtype=float)
        k[~np.isfinite(k)] = -np.inf
        return np.argsort(-k if desc else k, kind='stable').tolist()
    ks = [_num_key(v) for v in vals]
    nums = sum(k is not None for k in ks)
    if nums == len(ks):
        ks = [k if math.isfinite(k) else -math.inf for k in ks]
    elif nums == 0:
        ks = [_fmt_value(v, header) for v in vals]
    else:
        return None
    return sorted(range(len(ks)), key=ks.__getitem__, reverse=desc)


class _sort_held:
    """While a sorted table is rewritten in place: its sort indicator hidden (the header's signals held:
    no sort is made), so neither a cell put back (Qt's sorted insertion) nor the dataChanged at the end
    (Qt's ensureSorted: ~0.7-1.7 s for a 16k-row 'Peak list', through _NumItem.__lt__) re-sorts the
    rows; restored on exit."""

    def __init__(self, tbl):
        self.hh = tbl.horizontalHeader()
        self.sec, self.order = -1, Qt.AscendingOrder

    def __enter__(self):
        hh = self.hh
        self.sec, self.order = hh.sortIndicatorSection(), hh.sortIndicatorOrder()
        b = hh.blockSignals(True)
        hh.setSortIndicator(-1, self.order)
        hh.blockSignals(b)
        return self

    def __exit__(self, *exc):
        hh = self.hh
        b = hh.blockSignals(True)
        hh.setSortIndicator(self.sec, self.order)
        hh.blockSignals(b)
        return False


def _fresh_positions(tbl, trs, cols):
    """Before cells (table rows trs, columns cols) of a sorted table are rewritten in place: renew the
    position Qt keeps in their items.  A sort moves items without renewing it, and setText then finds
    the item by a linear search of the table (~20 µs a cell at 16k rows, at every write); taking an item
    out and putting it back renews it (~3.5 µs).  A column with many such cells is renewed whole and
    remembered (tbl._pos_fresh: the columns whose items all know their position; emptied by any sort,
    full after _fill_results_table).  Call it inside _sort_held and _bulk_cells."""
    fresh = getattr(tbl, '_pos_fresh', None) or set()
    todo = {}
    for tr, c in zip(trs, cols):
        if c not in fresh:
            todo.setdefault(c, []).append(tr)
    n = tbl.rowCount()
    take, put = tbl.takeItem, tbl.setItem
    for c, rs in todo.items():
        if 4 * len(rs) >= n:
            rs = range(n)
            fresh.add(c)
        taken = list(map(take, rs, repeat(c, len(rs))))
        list(map(put, rs, repeat(c, len(rs)), taken))
    tbl._pos_fresh = fresh


def _table_moved(tbl):
    """Qt moved the rows of the results table (a sort, model layoutChanged): the positions its items
    keep (_fresh_positions) and the row order _update_results_view remembers (tbl._order) are stale."""
    tbl._pos_fresh = set()
    tbl._order = None


def _resort_rows(tbl, sec, new):
    """Rows of a table sorted by column sec put in the order new (new table row -> old table row,
    _sort_order), without Qt comparing items through Python (_NumItem.__lt__, ~1 µs a call: its re-sort
    of a 16k-row 'Peak list' after one dataChanged took 0.7-1.7 s, and could leave an inversion).
    Column sec's items are swapped for C++ items holding each row's new rank (made by the model for an
    empty cell: no Python method), the model sorts by those, moving every other item with its row (the
    selection follows), and the column's own items are put back: ~80 ms for 16k rows.  Call it inside
    _sort_held and _bulk_cells (the model's signals held; let through for the sort itself).  Returns
    the rank of each old table row (its new table row)."""
    nr = len(new)
    m = tbl.model()
    rows = range(nr)
    own = list(map(tbl.takeItem, rows, repeat(sec, nr)))
    rank = [0] * nr
    for i, tr in enumerate(new):
        rank[tr] = i
    list(map(m.setData, map(m.index, rows, repeat(sec, nr)), rank))
    blocked = m.blockSignals(False)
    try:
        m.sort(sec, Qt.AscendingOrder)
    finally:
        m.blockSignals(blocked)
    list(map(tbl.setItem, rows, repeat(sec, nr), [own[tr] for tr in new]))     # (deletes the rank items)
    tbl._pos_fresh = {sec}                      # every other item moved (_fresh_positions)
    return rank


def _grow_columns(tbl, texts):
    """After an in-place update (column widths kept, also the user's): widen a column whose longest new
    text (texts: column -> text) does not fit, e.g. a 'Peak list' note after Show -> Remove; never
    narrowed.  Width as the view's own size hint: text + 2 x (focus-frame margin + 1) + the grid line."""
    if not texts:
        return
    fm = tbl.fontMetrics()
    pad = 2 * (tbl.style().pixelMetric(QStyle.PM_FocusFrameHMargin, None, tbl) + 1) + int(tbl.showGrid())
    for c, text in texts.items():
        need = fm.horizontalAdvance(text) + pad
        if need > tbl.columnWidth(c):
            tbl.setColumnWidth(c, need)


def _selected_movement_ids(self):
    tbl = getattr(self, 'logs_movements_table', None)
    if tbl is None:
        return set()
    ids = set()
    for r in {ix.row() for ix in tbl.selectedIndexes()}:
        it = tbl.item(r, 0)
        mid = it.data(Qt.UserRole) if it is not None else None
        if mid is not None:
            ids.add(int(mid))
    return ids


_MOVEMENT_EDIT_TIP = ("Double-click (or F2) to type a new time: snapped to the nearest sample of the curve, at "
                      "least one sample between start and stop, no overlap with the curve's other movements")


def _same_cell(a, b):
    return a == b or (_is_nan(a) and _is_nan(b))


def _movement_cells(tbl, r, row, hdrs, new, old=None):
    """Write movements-table row r from a _movement_table_row tuple.  new: the row is empty (items
    made complete before they enter the table); else the items are updated in place and every property
    is set only when it differs (each setter emits dataChanged).  old: the row tuple shown now: only
    the cells whose value (or look: hidden, colour) changed are touched (None = every cell)."""
    mid, number, name, t0, t1, dur, delta, note, hidden, color, axis = row
    vals = (number, name, t0, t1, dur, delta, note)
    curve_tip = f"{name} · {axis}" + ("\nThe curve is hidden: its lane is not drawn" if hidden else "")
    fg = QBrush(QColor(_HIDDEN_FG)) if hidden else None
    diff = old is not None and not new
    same_look = diff and old[8] == hidden
    same_curve = same_look and old[9] == color and old[10] == axis and old[2] == name
    for c, val in enumerate(vals):
        same_val = diff and (c != 0 or old[0] == mid) and _same_cell(old[_MOVEMENT_ROW_FIELD[c]], val)
        if same_val and same_look and (c != 1 or same_curve):
            continue
        editable = c in _MOVEMENT_EDIT_COLS
        tip = curve_tip if c == 1 else (_MOVEMENT_EDIT_TIP if editable else (note if c == 6 else None))
        if new:
            key = _num_key(val)
            it = _NumItem(_fmt_value(val, hdrs[c]), key)
            it.setFlags(_FLAGS_EDIT if editable else _FLAGS_RO)
            if key is not None:
                it.setTextAlignment(_ALIGN_NUM)
            if c == 0:
                it.setData(Qt.UserRole, mid)
            elif c == 1:
                _set_icon_color(it, color)
            if tip:
                it.setToolTip(tip)
            if fg is not None:
                it.setForeground(fg)
            tbl.setItem(r, c, it)
            continue
        prev = tbl.item(r, c)
        if same_val and isinstance(prev, _NumItem):
            it, fresh = prev, False                         # only its look changed (hidden / colour)
        else:
            it = _set_cell(tbl, r, c, val, hdrs[c], editable=editable, reuse=True)
            fresh = it is not prev
        full = fresh or not diff                            # every property checked
        if c == 0:
            if (full or not same_val) and it.data(Qt.UserRole) != mid:
                it.setData(Qt.UserRole, mid)
        elif c == 1:
            if full or not same_curve:
                _set_icon_color(it, color)
                if it.toolTip() != tip:
                    it.setToolTip(tip)
        elif tip is not None and (full or not same_val) and it.toolTip() != tip:
            it.setToolTip(tip)
        if full or not same_look:
            if fg is not None:
                if it.data(Qt.ForegroundRole) is None:
                    it.setForeground(fg)
            elif it.data(Qt.ForegroundRole) is not None:
                it.setData(Qt.ForegroundRole, None)


_BULK_ROWS = 50         # from this many rows rewritten in place, one dataChanged for the range (_bulk_cells)


class _bulk_cells:
    """Context of an in-place update of many rows of a QTableWidget (call it while the table's own
    signals are blocked): the model's per-item dataChanged signals are held (each one costs the view a
    repaint request, ~10 µs, for every cell of thousands of rows) and one dataChanged for the touched
    rows (all columns) is emitted at the end: the view repaints once and a sorted table keeps its
    order.  Fewer than _BULK_ROWS rows: nothing is held."""

    def __init__(self, tbl, rows):
        self.tbl = tbl
        self.rows = [int(r) for r in rows]
        self.model = None

    def __enter__(self):
        if len(self.rows) >= _BULK_ROWS:
            self.model = self.tbl.model()
            self.model.blockSignals(True)
        return self

    def __exit__(self, *exc):
        m = self.model
        if m is not None:
            m.blockSignals(False)
            n_r, n_c = m.rowCount(), m.columnCount()
            if n_r and n_c:
                r0 = max(0, min(min(self.rows), n_r - 1))
                r1 = max(r0, min(max(self.rows), n_r - 1))
                m.dataChanged.emit(m.index(r0, 0), m.index(r1, n_c - 1))
        return False


def _fill_movements_table(self, tbl, rows, u, old_rows=None, force=None):
    """Movements table showing rows (_movement_table_row, table order).  old_rows: what it shows now
    (None = unknown).  The same movements in the same order: only the changed rows (and the forced
    ones: ids, or True = all) are rewritten in place, the selection stays; else the table is refilled
    and the selection follows the movement ids (Qt.UserRole of column 0)."""
    hdrs = _movement_table_headers(u)
    ids = [r[0] for r in rows]
    tbl.blockSignals(True)
    upd = tbl.updatesEnabled()
    tbl.setUpdatesEnabled(False)
    try:
        hi = tbl.horizontalHeaderItem(5)
        if hi is None or hi.text() != hdrs[5]:
            it = QTableWidgetItem(hdrs[5])
            it.setToolTip("Value change from the start to the stop (axis of the movement)")
            tbl.setHorizontalHeaderItem(5, it)
        if old_rows is not None and len(old_rows) == len(rows) == tbl.rowCount() \
                and [r[0] for r in old_rows] == ids:
            todo = [(r, a, b) for r, (a, b) in enumerate(zip(old_rows, rows))
                    if force is True or (force and b[0] in force) or not _same_row(a, b)]
            with _bulk_cells(tbl, [r for r, _, _ in todo]):
                for r, a, b in todo:
                    full = force is True or (force and b[0] in force)
                    _movement_cells(tbl, r, b, hdrs, new=False, old=None if full else a)
            return
        sel_ids = _selected_movement_ids(self)
        tbl.clearSelection()
        tbl.clearContents()
        tbl.setRowCount(len(rows))
        keep = []
        for r, row in enumerate(rows):
            _movement_cells(tbl, r, row, hdrs, new=True)
            if row[0] in sel_ids:
                keep.append(r)
        sm = tbl.selectionModel()
        for r in keep:
            sm.select(tbl.model().index(r, 0), QItemSelectionModel.Select | QItemSelectionModel.Rows)
    finally:
        tbl.setUpdatesEnabled(upd)
        tbl.blockSignals(False)


def _refresh_movements_table(self, force=None):
    """Movements table (and the 'Movements' view) from st.movements: one row per movement (curves
    table order, then start), times in the displayed time base, each row keeping its movement id.
    Called by every redraw, so a row and its lane segment always show the same movement; it costs
    nothing when nothing shown changed (_sync_movements).  force: ids (or True) of rows rewritten
    anyway (a refused cell entry is restored)."""
    _sync_movements(self, force=force)


def _sync_roi_widgets(self):
    st = _state(self)
    s0 = getattr(self, 'logs_spin_roi0', None)
    s1 = getattr(self, 'logs_spin_roi1', None)
    if s0 is None or s1 is None:
        return
    if st.roi is not None:
        a, b = st.roi
        self.logs_roi_label.setText(f"ROI: {a:.3f} – {b:.3f} s ({b - a:.3f} s)")
    else:
        a, b = _data_span(st)
        self.logs_roi_label.setText("ROI: all data")
    for s, val in ((s0, a), (s1, b)):
        s.blockSignals(True)
        s.setValue(float(val) if np.isfinite(val) else 0.0)
        s.blockSignals(False)


def _data_span(st, visible_only=False):
    lo, hi = np.inf, -np.inf
    for e in st.entries:
        if visible_only and not e.visible:
            continue
        tt = _vc(st, e).times()
        if tt.size:
            lo = min(lo, float(tt[0]))
            hi = max(hi, float(tt[-1]))
    if not np.isfinite(lo):
        return 0.0, 0.0
    return lo, hi


def _update_unit_suffixes(self):
    st = _state(self)
    u = _axis_unit(st, st.analysis_axis) or 'mm'
    for name in ('logs_spin_prom', 'logs_spin_mv_thr'):
        s = getattr(self, name, None)
        if s is not None:
            s.setSuffix(f" {u}")


def _update_duet_button(self):
    btn = getattr(self, 'logs_btn_duet_ref', None)
    if btn is None:
        return
    try:
        st = _state(self)
        e = st.entries[st.selected] if 0 <= st.selected < len(st.entries) else None
        ok = bool(getattr(self, 'duet_connected', False)) and e is not None and e.curve.kind == 'log' \
            and bool(e.curve.meta.get('gcode'))
        btn.setEnabled(ok)
    except Exception:
        btn.setEnabled(False)


# ----------------------------------------------------------------------------
# Results
# ----------------------------------------------------------------------------
def _result_names(st):
    return [n for n in _RESULT_VIEWS if n in st.results] + [n for n in st.results if n not in _RESULT_VIEWS]


def _refresh_results_combo(self, current=None):
    st = _state(self)
    combo = getattr(self, 'logs_results_combo', None)
    if combo is None:
        return
    names = _result_names(st)
    cur = current if current is not None else st.current_results
    combo.blockSignals(True)
    combo.clear()
    combo.addItems(names)
    if cur in names:
        combo.setCurrentIndex(names.index(cur))
    combo.blockSignals(False)


def _set_results(self, name, headers, rows, show=True, ref_uid=None, uids=None):
    """Store a results view; ref_uid = uid of the reference curve it was computed against (the view
    is dropped when that curve is removed); uids = the curves an analysis used (Compare, Alignment,
    Peaks & periods: its note names the cut logs among them).  Its time-base note and key are stored
    with it (the note goes into its CSV export and the caption above the table; a view of an analysis
    made in another time base is marked there, _results_stale)."""
    st = _state(self)
    st.results[name] = (list(headers), [list(r) for r in rows])
    if uids is not None:
        st.results_uids[name] = frozenset(uids)
    else:
        st.results_uids.pop(name, None)
    st.results_notes[name] = _time_base_note(st, name, st.results_uids.get(name))
    st.results_base[name] = _time_base_key(st)
    if ref_uid is not None:
        st.results_ref[name] = ref_uid
    else:
        st.results_ref.pop(name, None)
    _refresh_results_combo(self, current=name if show else st.current_results)
    if show or st.current_results is None or st.current_results == name:
        _show_results(self, name)
    else:
        _refresh_results_note(self)


def _time_base_key(st):
    """What the times of an analysis depend on besides the time offsets, per curve: (uids of the logs
    shown without their logged waits (Remove mode and marked waits, _cut_active), uids of every curve
    loaded, (uid, pause lengths) of every G-code reference (Show: the source log's waits; Remove: all
    0)).  Two keys are compared per curve, _base_change."""
    return (frozenset(e.uid for e in st.entries if _cut_active(st, e)), frozenset(e.uid for e in st.entries),
            tuple((e.uid, _ref_durs(e.curve.meta)) for e in _gcode_entries(st)))


def _base_change(base, now, used=None):
    """What changed between two _time_base_key for the curves loaded in both (and, with `used`, that
    the view analysed): (logs shown cut then, logs shown cut now, a G-code with other pause lengths),
    or None when no time of such a curve changed.  So a curve added or removed marks nothing (a log
    with waits loaded or removed in Remove mode changes no time of the others), nor does a Show /
    Remove switch without any marked wait (v1 logs, waits 'not marked': the same times), nor a change
    of a curve the view did not use."""
    both = base[1] & now[1]
    if used is not None:
        both = both & used
    cut0, cut1 = base[0] & both, now[0] & both
    g0, g1 = dict(base[2]), dict(now[2])
    durs = any(g0[u] != g1[u] for u in g0.keys() & g1.keys() & both)
    return (cut0, cut1, durs) if cut0 != cut1 or durs else None


_RERUN = {'Compare': "Compare", 'Alignment': "Auto-align", 'Peaks & periods': "Find peaks"}


def _results_stale(st, name):
    """A results view made by an analysis in another time base than the plot's now (logged waits
    shown / removed, other G-code pause lengths, for a curve loaded then and now): its times / numbers
    do not match the plot until it is run again.  Views rebuilt from the state (_LIVE_VIEWS) are never
    stale."""
    if name in _LIVE_VIEWS or name not in st.results:
        return False
    base = st.results_base.get(name)
    return base is not None and _base_change(base, _time_base_key(st), st.results_uids.get(name)) is not None


def _results_note_text(st, name):
    """(caption text, stale) of results view `name` (above the results table)."""
    if not name or name not in st.results:
        return '', False
    note = st.results_notes.get(name) or _time_base_note(st, name)
    if not _results_stale(st, name):
        return note, False
    cut0, cut1, _ = _base_change(st.results_base[name], _time_base_key(st), st.results_uids.get(name))
    then = "with the logged waits removed" if cut0 else "in real time (logged waits shown)"
    now = "the logged waits removed" if cut1 else "real time"
    if cut0 and cut1 and cut0 != cut1:
        then, now = "with the logged waits of other logs removed", "other logs without their waits"
    elif cut0 == cut1:
        then, now = "with other G-code pause lengths", "other pause lengths"
    act = _RERUN.get(name, "the analysis")
    return (f"Computed {then} - the plot now shows {now}: these numbers do not match it, run {act} again. "
            f"({note})"), True


def _refresh_results_note(self):
    """Caption above the results table: the time base of the view shown (whether logged waits were
    removed), in orange when the view was computed in another time base than the plot's now."""
    st = _state(self)
    lbl = getattr(self, 'logs_results_note', None)
    if lbl is None:
        return
    text, stale = _results_note_text(st, st.current_results)
    style = ("font-weight: bold; font-size: 12px; color: #e65100;" if stale else
             "font-weight: normal; font-size: 12px; color: #607d8b;")
    if lbl.styleSheet() != style:
        lbl.setStyleSheet(style)
    if lbl.text() != text:
        lbl.setText(text)
    combo = getattr(self, 'logs_results_combo', None)
    if combo is not None:
        for i in range(combo.count()):
            tip, _ = _results_note_text(st, combo.itemText(i))
            if combo.itemData(i, Qt.ToolTipRole) != tip:
                combo.setItemData(i, tip, Qt.ToolTipRole)
        if combo.toolTip() != text:
            combo.setToolTip(text)


def _refresh_live_notes(self):
    """The time-base notes of the views rebuilt from the state (_LIVE_VIEWS) as the state is now, then
    the caption above the results table: after a change that can alter a note without changing a row
    (a curve shown / hidden, the reference, the pause mode / source, curves added or removed).  An
    analysis view (_ANALYSIS_VIEWS) one of whose curves was removed forgets it; when that log was shown
    cut (its note names it) and the view is not stale, its note is made again for the curves left."""
    st = _state(self)
    for name in _LIVE_VIEWS:
        if name in st.results:
            st.results_notes[name] = _time_base_note(st, name)
    present = {e.uid for e in st.entries}
    for name in _ANALYSIS_VIEWS:
        used, base = st.results_uids.get(name), st.results_base.get(name)
        # (only once the view is not stale: a stale view keeps the removed curve until a later change
        # clears the stale mark, and its note is made again then)
        if name in st.results and used is not None and not used <= present and not _results_stale(st, name):
            st.results_uids[name] = used & present
            if base is not None and (used - present) & base[0]:
                st.results_notes[name] = _time_base_note(st, name, st.results_uids[name])
    _refresh_results_note(self)


def _peak_list_rows(st):
    """(headers, rows) of the 'Peak list' view from st.peaks (stored in recorded time): times in the
    displayed time base now (offsets, pause mode), so the list always matches the peaks drawn; in
    Remove mode a peak inside a removed wait is not drawn: its t is empty and the note says so."""
    rows = []
    axis = None
    for e in st.entries:
        pk = st.peaks.get(e.uid)
        if pk is None:
            continue
        axis = axis or pk['axis']
        t_raw = np.asarray(pk['t_raw'], dtype=float).ravel()
        if t_raw.size == 0:
            continue
        t = np.asarray(_r2d(st, e, t_raw), dtype=float).reshape(-1)
        hidden = (_inside_cut(_vc(st, e).meta['cut_map'], t_raw) if _cut_active(st, e)
                  else np.zeros(t_raw.shape, dtype=bool))
        v = np.asarray(pk['v_raw'], dtype=float).ravel() + (_vof(e.curve, pk['axis']) if e.curve.has(pk['axis'])
                                                          else 0.0)
        last = {}
        for i, (ti, vi, k, hid) in enumerate(zip(t, v, pk['kind'], hidden)):
            if hid:
                rows.append([e.curve.name, pk['axis'], i + 1, k, float('nan'), float(vi), float('nan'),
                             f"{_REMOVED_NOTE} (recorded at {float(t_raw[i]) + e.curve.time_offset:.3f} s)"])
                continue
            dt = float(ti) - last[k] if k in last else float('nan')
            last[k] = float(ti)
            rows.append([e.curve.name, pk['axis'], i + 1, k, float(ti), float(vi), dt, ''])
    u = _axis_unit(st, axis) if axis else ''
    return list(_PEAK_LIST_BASE) + [f'Value ({u})' if u else 'Value', 'dt to previous (s)', 'Note'], rows


def _refresh_peak_list(self):
    """The 'Peak list' view follows the peaks drawn (offsets, pause mode); dropped without peaks.
    Only rewritten when a row changed; when it is the view shown and lists as many peaks, only its
    changed cells are rewritten in place (_update_results_view: a refill of ~16k rows takes ~0.9 s)."""
    st = _state(self)
    if not any(st.peaks.get(e.uid) is not None for e in st.entries):
        if 'Peak list' in st.results:
            _drop_results(self, 'Peak list')
        return
    hdrs, rows = _peak_list_rows(st)
    old = st.results.get('Peak list')
    same_shape = old is not None and list(old[0]) == hdrs and len(old[1]) == len(rows)
    if (same_shape and all(_same_row(a, b) for a, b in zip(old[1], rows))
            and st.results_notes.get('Peak list') == _time_base_note(st, 'Peak list')):
        return
    if same_shape and st.current_results == 'Peak list':
        _update_results_view(self, 'Peak list', hdrs, rows)
    else:
        _set_results(self, 'Peak list', hdrs, rows, show=False)


def _time_base_note(st, view=None, uids=None):
    """What the times of a results view / an export refer to (written as a '#' line of its CSV).  The
    logs it names as shown without their waits: for the aligned export (view None: visible curves only)
    and 'Pauses' (its 'From' column, _remove_status) the visible ones; for an analysis of the visible
    curves (_ANALYSIS_VIEWS) those it used (uids; by default the visible ones and, but for Peaks &
    periods, the reference), a hidden one (the reference) marked so; for every other results view each
    log shown cut, hidden or not ('Movements', 'Points', 'Peak list' keep a hidden log's rows, in its
    cut time), a hidden one marked so."""
    if view == 'Waits':
        return ("Time base: the logs' own recorded run time (s), as written in their notes; lengths = end - "
                "received of the rows each wait covers")
    vis_only = view in (None, 'Pauses')
    if uids is None and view in _ANALYSIS_VIEWS:
        uids = {e.uid for e in st.entries if e.visible}
        if view != 'Peaks & periods' and st.ref_uid is not None:
            uids.add(st.ref_uid)
    cut = [e.curve.name + ('' if e.visible else ' (hidden)') for e in st.entries
           if _cut_active(st, e) and (e.uid in uids if uids is not None else e.visible or not vis_only)]
    if st.pause_mode == 'remove':
        if cut:
            return (f"Time base: logged sensor waits removed (Pauses: Remove logged waits) from {', '.join(cut)}, "
                    f"G-code pauses with length 0, plus each curve's time offset")
        which = 'visible ' if vis_only else 'analysed ' if uids is not None else ''
        return f"Time base: Pauses set to Remove logged waits, but no {which}log has logged waits: as recorded"
    src = _pause_source(st)
    marked = any(p.get('kind') == 'marked' for p in st.pause_info)
    txt = "Time base: as recorded (logged sensor waits in real time), plus each curve's time offset"
    if st.pause_info:
        txt += (f", G-code pause lengths from the logged waits of {src.curve.name}" if src is not None and marked
                else ", G-code pauses with length 0 (no logged wait paired)")
    return txt


def _prune_results(self, removed_uids, removed_names):
    """After curves are removed: drop their rows from every results view ('Curve' column), drop the
    views computed against a removed reference (Alignment, Compare, Pauses) and 'Pauses' when the
    reference is no longer a G-code; then refresh the combo and the table."""
    st = _state(self)
    removed_uids, removed_names = set(removed_uids), set(removed_names)
    ref = _ref_entry(st)
    ref_is_gcode = ref is not None and isinstance(ref.curve.meta.get('_source'), dict)
    for name in list(st.results):
        if name == 'Points':                    # rebuilt from st.points by _refresh_points_table
            continue
        headers, rows = st.results[name]
        drop = st.results_ref.get(name) in removed_uids
        if name == 'Pauses' and not ref_is_gcode:
            drop = True
        if not drop and 'Curve' in headers:
            ci = headers.index('Curve')
            rows = [r for r in rows if not (ci < len(r) and r[ci] in removed_names)]
            st.results[name] = (headers, rows)
            drop = not rows
        if drop:
            st.results.pop(name, None)
            st.results_ref.pop(name, None)
            st.results_base.pop(name, None)
            st.results_uids.pop(name, None)
    if st.current_results not in st.results:
        names = _result_names(st)
        st.current_results = names[0] if names else None
    _refresh_results_combo(self)
    if st.current_results is not None:
        _show_results(self, st.current_results)
    else:
        _fill_results_table(self, ['Results'], [])
        _refresh_results_note(self)


def _drop_results(self, name):
    st = _state(self)
    st.results.pop(name, None)
    st.results_ref.pop(name, None)
    st.results_base.pop(name, None)
    st.results_uids.pop(name, None)
    combo = getattr(self, 'logs_results_combo', None)
    if combo is not None:
        i = combo.findText(name)
        if i >= 0:
            combo.blockSignals(True)
            combo.removeItem(i)
            combo.blockSignals(False)
    if st.current_results == name:
        nxt = combo.currentText() if combo is not None and combo.count() else None
        if nxt:
            _show_results(self, nxt)
        else:
            st.current_results = None
            _fill_results_table(self, ['Results'], [])
    _refresh_results_note(self)


def _show_results(self, name):
    st = _state(self)
    if name not in st.results:
        return
    st.current_results = name
    headers, rows = st.results[name]
    _fill_results_table(self, headers, rows)
    combo = getattr(self, 'logs_results_combo', None)
    if combo is not None and combo.currentText() != name:
        i = combo.findText(name)
        if i >= 0:
            combo.blockSignals(True)
            combo.setCurrentIndex(i)
            combo.blockSignals(False)
    _refresh_results_note(self)


def _fill_results_table(self, headers, rows):
    tbl = getattr(self, 'logs_results_table', None)
    if tbl is None:
        return
    if not getattr(tbl, '_pos_hooked', False):  # a sort moves items: the positions they keep go stale
        tbl._pos_hooked = True
        tbl.model().layoutChanged.connect(lambda *_a: _table_moved(tbl))
    tbl.setSortingEnabled(False)
    tbl.clear()
    tbl.setColumnCount(len(headers))
    tbl.setHorizontalHeaderLabels([str(h) for h in headers])
    tbl.setRowCount(len(rows))
    for r, row in enumerate(rows):
        for c, val in enumerate(row):
            key = _num_key(val)
            it = _NumItem(_fmt_value(val, headers[c] if c < len(headers) else ''), key)
            if key is not None:
                it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            if c == 0:
                it.setData(Qt.UserRole, r)          # its stored row (_update_results_view, after a sort)
            tbl.setItem(r, c, it)
    tbl.resizeColumnsToContents()
    # no sort column: filling keeps the stored row order (= the exported CSV); clicking a header
    # still sorts the table
    tbl.horizontalHeader().setSortIndicator(-1, Qt.AscendingOrder)
    tbl.setSortingEnabled(True)
    tbl._pos_fresh = set(range(len(headers)))   # every item put in its place (_fresh_positions)
    tbl._order = None


def _set_summary(self, text):
    """Status line: logs_summary shows it wrapped / elided to its width, text() and the tooltip
    hold the full message."""
    st = _state(self)
    st.summary = text
    lbl = getattr(self, 'logs_summary', None)
    if lbl is not None:
        lbl.setText(text)
        lbl.setToolTip(text)


def _ensemble_summary(st, with_roi=True):
    axis = st.analysis_axis
    if not axis:
        return ''
    logs = [_vc(st, e) for e in _visible(st, axis, kind='log')]
    if len(logs) < 2:
        return f"ensemble: needs >= 2 visible logs with {axis} ({len(logs)} visible)"
    ens = la.ensemble(logs, axis, roi=st.roi, dt=0.01, k=st.band_k)
    u = _axis_unit(st, axis)
    return (f"ensemble of N={len(logs)} logs on {axis}{_roi_txt(st) if with_roi else ''}: mean STD {ens['std_mean']:.4f} {u}, "
            f"max STD {ens['std_max']:.4f} {u}")


# ----------------------------------------------------------------------------
# Plot
# ----------------------------------------------------------------------------
def _apply_diff_layout(self):
    st = _state(self)
    ax, axd, gs = self.logs_ax, self.logs_ax_diff, self.logs_gs
    if st.show_diff:
        ax.set_subplotspec(gs[0])
        axd.set_visible(True)
        axd.set_in_layout(True)
        ax.tick_params(labelbottom=False)
        ax.set_xlabel('')
        axd.set_xlabel("Time (s)", fontsize=12, fontweight='bold')
    else:
        ax.set_subplotspec(gs[:])
        axd.set_visible(False)
        axd.set_in_layout(False)
        ax.tick_params(labelbottom=True)
        ax.set_xlabel("Time (s)", fontsize=12, fontweight='bold')


@_action("Plot")
def logs_redraw(self, rescale=False):
    """Redraw the plot from the state (rescale=True fits the view to the visible data)."""
    _redraw(self, rescale=rescale)


def _deferred(self, fn, *args, **kwargs):
    """Run an action from a spin box slot: its state change is immediate, its redraw is debounced
    (one redraw _REDRAW_DELAY_MS after the last step of the spin box; while a spin arrow is held,
    at its release; after Enter / leaving the box, at once)."""
    st = _state(self)
    st.defer_redraw += 1
    try:
        return fn(self, *args, **kwargs)
    finally:
        st.defer_redraw = max(0, st.defer_redraw - 1)


def _hold_spin(self, spin):
    """Left button pressed on a spin box (its arrows auto-repeat while held): the debounced redraw
    waits for the release."""
    if spin.isEnabled():
        _state(self).held_spin = spin


def _release_spin(self, spin):
    st = _state(self)
    if st.held_spin is spin or st.held_spin is None:
        st.held_spin = None
        _flush_redraw_now(self)


def _redraw_held(self):
    """True while the left button holds a spin box of the tab.  A hold whose release never came
    (the box was deleted or hidden, the button is up) is dropped."""
    st = _state(self)
    sp = st.held_spin
    if sp is None:
        return False
    try:
        alive = shiboken6.isValid(sp) and sp.isVisible() and sp.isEnabled()
        down = bool(QApplication.mouseButtons() & Qt.LeftButton)
    except Exception:
        alive = down = False
    if alive and down:
        return True
    st.held_spin = None
    return False


def _flush_redraw_now(self):
    """Do a pending debounced redraw now (spin arrow released, Enter / focus out of a spin box)."""
    st = _state(self)
    if st.pending_redraw is None or _redraw_held(self):
        return
    timer = getattr(self, 'logs_redraw_timer', None)
    if timer is not None:
        timer.stop()
    _flush_redraw(self)


def _flush_redraw(self):
    st = _state(self)
    p = st.pending_redraw
    if p is None or not _built(self):
        return
    if _redraw_held(self):                      # arrow still held: look again later, draw at release
        timer = getattr(self, 'logs_redraw_timer', None)
        if timer is not None:
            timer.start()
        return
    st.pending_redraw = None
    try:
        _do_redraw(self, rescale=p['rescale'], refit_y=p['refit_y'])
    except Exception as e:
        traceback.print_exc()
        _warn(self, "Plot", e)


def _redraw(self, rescale=False, refit_y=False):
    """Redraw now, or (inside a spin box slot, see _deferred) once the spin box stops changing."""
    if not _built(self):
        return
    st = _state(self)
    timer = getattr(self, 'logs_redraw_timer', None)
    p = st.pending_redraw
    if st.defer_redraw > 0 and timer is not None:
        if p is None:
            p = st.pending_redraw = {'rescale': False, 'refit_y': False}
        p['rescale'] = p['rescale'] or bool(rescale)
        p['refit_y'] = p['refit_y'] or bool(refit_y)
        timer.start()                           # (re)start: the redraw waits for the last change
        return
    if p is not None:                           # a synchronous redraw also does the pending one
        st.pending_redraw = None
        rescale = rescale or p['rescale']
        refit_y = refit_y or p['refit_y']
        if timer is not None:
            timer.stop()
    _do_redraw(self, rescale=rescale, refit_y=refit_y)


def _do_redraw(self, rescale=False, refit_y=False):
    st = _state(self)
    ax, axd = self.logs_ax, self.logs_ax_diff
    if st.drag is not None:
        _drag_abort(self)       # the artists it moves are rebuilt from the (unchanged) state: drag dropped
    st.point_artists, st.lane_artists = {}, {}
    for a in st.artists:
        _safe_remove(a)
    for a in st.diff_artists + st.band_artists:
        _safe_remove(a)
    st.artists, st.diff_artists, st.band_artists = [], [], []
    st.diff_series, st.band_fills, st.band_view = [], [], None
    leg = ax.get_legend()
    if leg is not None:
        _safe_remove(leg)
    _remove_key(self)
    A = st.artists.append
    axis = st.analysis_axis
    ref = _ref_entry(st)
    order = [a for a in st.known_axes if a in st.enabled_axes]
    style_of = {a: _LINESTYLES[k % len(_LINESTYLES)] for k, a in enumerate(order)}
    series = []                     # (x, y) of everything that sets the view limits
    n_lines = 0
    n_pts = 0                       # points of the plotted curves (legend placement cost)
    units = set()
    handles = []                    # legend entries; their texts (leg_labels) are elided, the artists
    leg_labels = []                 # keep the full '<curve> · <axis>' label
    drawn = set()                   # event classes drawn (the colour key lists them)
    pause_span = False              # a G-code pause drawn with its length (strip)
    labels = []                     # vertical pause / cut labels: the two legends keep clear of them

    # ROI
    if st.roi is not None:
        A(ax.axvspan(st.roi[0], st.roi[1], color=_ROI_COLOR, alpha=_ROI_ALPHA, zorder=0, lw=0))
        drawn.add('roi')

    # probe events / gaps / pauses
    cut_marks = []                  # (x, length, entry) of the removed waits drawn (labelled per position)
    for e in st.entries:
        if not e.visible:
            continue
        c = _vc(st, e)
        tt = c.times()
        if st.show_probe and c.probe is not None and c.probe.size == tt.size:
            det = (c.probe > 0) & (c.probe < la.PROBE_RELEASE_MIN)
            rel = c.probe >= la.PROBE_RELEASE_MIN
            for mask, color, alpha, cls in ((det, _PROBE_DET_COLOR, _DET_ALPHA, 'det'),
                                            (rel, _PROBE_REL_COLOR, _REL_ALPHA, 'rel')):
                rng = _run_ranges(tt, mask)
                if rng:
                    A(_span_collection(ax, rng, 0.0, 1.0, facecolor=color, alpha=alpha, edgecolor='none',
                                       zorder=0))
                    drawn.add(cls)
        if c is not e.curve:                # Remove mode: where the waits were cut out (always drawn)
            cut_marks.extend((float(t_cut) + c.time_offset, float(length), e)
                             for t_cut, length, _ in c.meta.get('cuts') or [])
        if st.show_probe and c.kind == 'log':
            _draw_wait_events(self, st, e, c, drawn)
        if st.show_gaps and c.meta.get('gaps'):
            rng = []
            for g in c.meta['gaps']:
                if not g or g[0] is None:
                    continue
                a0 = float(g[0]) + c.time_offset
                b0 = (float(g[1]) + c.time_offset) if len(g) > 1 and g[1] is not None else float(tt[-1])
                if b0 <= a0:
                    b0 = a0 + 0.05
                rng.append((a0, b0))
            if rng:
                A(_span_collection(ax, rng, 0.0, 1.0, facecolor=_GAP_FACE, edgecolor=_GAP_COLOR, hatch=_GAP_HATCH,
                                   linewidth=0.0, zorder=0))
                drawn.add('gap')
        if st.show_pauses and c.kind == 'reference':
            pauses = c.meta.get('pauses') or []
            durs = list(c.meta.get('pause_durations') or [])
            durs = durs[:len(pauses)] + [0.0] * (len(pauses) - len(durs))
            # Remove mode: per pause what was cut out of the visible logs there (never one flag per plot)
            rstat = _remove_status(st, c) if st.pause_mode == 'remove' else None
            for k, ((label, tp), d) in enumerate(zip(pauses, durs)):
                x0 = float(tp) + c.time_offset
                A(ax.axvline(x0, color=_PAUSE_COLOR, ls='--', lw=1.3, alpha=0.9, zorder=1))
                drawn.add('pause')
                y_lab, ha = _PAUSE_LABEL_Y, 'right'
                if d > 0:
                    # the pause period (its logged length): a purple strip along the top from its start
                    # to its end, a dashed line at both ends; on top of the amber wait band it keeps its
                    # colour (the key shows the same: _PausePeriodHandler).  The label starts below the
                    # strip, inside the period (not over the hatched sent window before it).
                    A(ax.axvspan(x0, x0 + d, ymin=_PAUSE_STRIP[0], ymax=_PAUSE_STRIP[1], facecolor=_PAUSE_COLOR,
                                 alpha=_PAUSE_STRIP_ALPHA, lw=0, zorder=1))
                    A(ax.axvline(x0 + d, color=_PAUSE_COLOR, ls='--', lw=1.3, alpha=0.9, zorder=1))
                    pause_span = True
                    txt = f" {label} {d:.2f} s (logged)"
                    y_lab, ha = _PAUSE_LABEL_Y_STRIP, 'left'
                elif rstat is not None and k < len(rstat):
                    txt = f" {label} {_remove_label(rstat[k])}"
                else:
                    txt = f" {label} (no logged wait)"
                # clipped to the axes and kept out of constrained_layout: a label outside the
                # zoomed range otherwise counts as a decoration and collapses the axes
                lab = ax.text(x0, y_lab, txt, color=_PAUSE_COLOR, fontsize=9, fontstyle='italic', rotation=90,
                              va='top', ha=ha, transform=ax.get_xaxis_transform(), zorder=2, clip_on=True,
                              bbox=_LABEL_BOX)
                lab.set_in_layout(False)
                A(lab)
                labels.append(lab)
    labels.extend(_draw_cut_labels(self, st, cut_marks))
    if cut_marks:
        drawn.add('cut')

    # ensemble band / envelope (drawing grid capped to _DRAW_MAX_POINTS; the statistics use dt 0.01)
    if (st.show_band or st.show_envelope) and axis and axis in st.enabled_axes:
        logs = [_vc(st, e) for e in _visible(st, axis, kind='log')]
        if logs:
            spans = [(float(tt[0]), float(tt[-1])) for tt in (c.times() for c in logs) if tt.size]
            span = (max(b for _, b in spans) - min(a for a, _ in spans)) if spans else 0.0
            ens = la.ensemble(logs, axis, roi=None, dt=_draw_dt(span), k=st.band_k)
            t = ens['t']
            if t.size:
                # the fills are drawn after the limits (_draw_band_fills, min/max-decimated to the
                # visible range); the legend gets a patch with the same look
                if st.show_envelope:
                    style = dict(color='#ffb74d', alpha=0.30, lw=0, zorder=1, label=f"min-max envelope · {axis}")
                    st.band_fills.append((t, ens['vmin'], ens['vmax'], style))
                    handles.append(Patch(facecolor=style['color'], alpha=style['alpha'], lw=0, label=style['label']))
                    leg_labels.append(_legend_label("min-max envelope", axis))
                    series += [(t, ens['vmin']), (t, ens['vmax'])]
                if st.show_band and len(logs) >= 2:
                    style = dict(color='#546e7a', alpha=0.22, lw=0, zorder=1, label=f"mean ± {st.band_k:g}·STD · {axis}")
                    st.band_fills.append((t, ens['lo'], ens['hi'], style))
                    handles.append(Patch(facecolor=style['color'], alpha=style['alpha'], lw=0, label=style['label']))
                    leg_labels.append(_legend_label(f"mean ± {st.band_k:g}·STD", axis))
                    ln, = ax.plot(t, ens['mean'], color='#263238', lw=1.0, ls=(0, (5, 2)), zorder=2,
                                  label=f"mean · {axis}")
                    A(ln)
                    handles.append(ln)
                    leg_labels.append(_legend_label("mean", axis))
                    series += [(t, ens['lo']), (t, ens['hi'])]

    # curves
    for e in st.entries:
        if not e.visible:
            continue
        c = _vc(st, e)
        is_ref = c.kind == 'reference'
        for a in order:
            if not c.has(a):
                continue
            x, y = _plot_xy(c, a)
            n_pts += int(np.size(x))
            ln, = ax.plot(x, y, color=e.color, ls=style_of[a], lw=2.4 if is_ref else 1.4,
                          alpha=0.85 if is_ref else 1.0, zorder=2 if is_ref else 3, label=f"{c.name} · {a}")
            A(ln)
            handles.append(ln)
            leg_labels.append(_legend_label(c.name, a))
            series.append((x, y))
            n_lines += 1
            units.add(_curve_unit(c, a))

    # peaks (only on the axes shown on the plot; in Remove mode a peak inside a removed wait is not drawn)
    for e in st.entries:
        pk = st.peaks.get(e.uid)
        if pk is None or not e.visible or pk['axis'] not in st.enabled_axes or not e.curve.has(pk['axis']):
            continue
        t_raw = np.asarray(pk['t_raw'], dtype=float)
        t = _r2d(st, e, t_raw)
        shown = ~_inside_cut(_vc(st, e).meta['cut_map'], t_raw) if _cut_active(st, e) else np.ones(t_raw.shape, bool)
        v = pk['v_raw'] + _vof(e.curve, pk['axis'])
        kinds = np.asarray(pk['kind'])
        for kname, marker in (('max', '^'), ('min', 'v')):
            sel = (kinds == kname) & shown if kinds.size else kinds == kname
            if sel.any():
                A(ax.plot(t[sel], v[sel], ls='none', marker=marker, ms=9, mfc=e.color, mec='black', mew=0.8,
                          zorder=6, label='_nolegend_')[0])

    # movements: one thin lane per curve at the bottom; a movement that spans a connection gap
    # (in_gap, its stop is not confirmed) is drawn faint with a dashed outline, one edited by hand
    # with a thicker outline.  st.lane_artists keeps each lane (its segments by movement id) for
    # dragging the edges.  Segments are stored in recorded time: displayed = cut(t) + offset (an edge
    # inside a removed wait is drawn at its cut point).
    lane = 0
    for e in st.entries:
        mv = st.movements.get(e.uid)
        if mv is None or not e.visible:
            continue
        _mv_norm(st, mv)
        segs = mv['segments']
        rng, faces, styles, widths = [], [], [], []
        if segs:
            sa = _r2d(st, e, np.array([float(s[0]) for s in segs], dtype=float))
            sb = _r2d(st, e, np.array([float(s[1]) if s[1] > s[0] else float(s[0]) + 0.02 for s in segs],
                                      dtype=float))
        for j, (gap, edited) in enumerate(zip(mv['in_gap'], mv['edited'])):
            a0, b0 = float(sa[j]), float(sb[j])
            rng.append((a0, b0 if b0 > a0 else a0 + 0.02))
            faces.append(mcolors.to_rgba(e.color, 0.30 if gap else 0.85))
            styles.append('--' if gap else '-')
            widths.append(0.9 if gap else (1.6 if edited else 0.4))
        if rng:
            y0 = _LANE_Y0 + lane * _LANE_STEP
            y1 = y0 + _LANE_STEP * _LANE_HEIGHT
            col = _span_collection(ax, rng, y0, y1, facecolors=faces, edgecolor='black', linewidths=widths,
                                   linestyles=styles, zorder=4)
            A(col)
            st.lane_artists[e.uid] = {'col': col, 'y0': y0, 'y1': y1, 'ranges': rng, 'ids': list(mv['ids'])}
            lane += 1                   # a curve without movements (all deleted / none found) takes no lane
    _refresh_movements_table(self)      # (nothing to do when no row changed)

    # reference points (only on the axes shown on the plot)
    for i, p in enumerate(st.points):
        e = _entry_by_uid(st, p['uid'])
        if e is None or not e.visible or p['axis'] not in st.enabled_axes:
            continue
        t, v = _point_tv(st, p)
        if not (np.isfinite(t) and np.isfinite(v)):
            continue
        mk = ax.plot([t], [v], ls='none', marker='o', ms=10, mfc='white', mec=e.color, mew=2.2, zorder=7,
                     label='_nolegend_')[0]
        A(mk)
        ann = ax.annotate(str(i + 1), (t, v), xytext=(7, 7), textcoords='offset points', fontsize=11,
                          fontweight='bold', color=e.color, zorder=8,
                          bbox=dict(boxstyle='round,pad=0.15', fc='white', ec=e.color, lw=0.8, alpha=0.9))
        ann.set_in_layout(False)            # a number near the edge must not resize the axes
        A(ann)
        st.point_artists[_point_id(st, p)] = {'marker': mk, 'ann': ann, 'xy': (float(t), float(v))}

    # labels / legend
    if not st.entries:
        A(ax.text(0.5, 0.5, "Add log files or a reference G-code (section 1. Files)", transform=ax.transAxes,
                  ha='center', va='center', fontsize=13, color='#90a4ae'))
    elif not n_lines:
        A(ax.text(0.5, 0.5, "Nothing to show: enable an axis (section 2) and show a curve (section 1)",
                  transform=ax.transAxes, ha='center', va='center', fontsize=12, color='#90a4ae'))
    if units == {'deg'}:
        ylab = "Angle (deg)"
    elif units == {'mm', 'deg'}:
        ylab = "Position (mm) / angle (deg)"
    elif units <= {'mm'}:
        ylab = "Position (mm)"
    else:                           # per-curve units of the reader (meta['units']) other than mm / deg
        ylab = f"Value ({' / '.join(sorted(units)[:3])}{' …' if len(units) > 3 else ''})"
    ax.set_ylabel(ylab, fontsize=12, fontweight='bold')
    # heavy plot: the legends' 'best' does not test the data (slow), only the labels and each other
    heavy = n_pts > _LEGEND_BEST_MAX_POINTS
    key = _draw_key(self, st, drawn, pause_span, heavy, labels)
    if handles:
        n = len(handles)
        # elided texts (full names: curves table / tooltips), inside the axes and out of
        # constrained_layout: a legend wider than the canvas used to collapse the plot
        leg_labels = _distinct_texts(leg_labels, [getattr(x, 'full', '') or str(x) for x in leg_labels],
                                     _LEGEND_MAX_CHARS)
        leg = _curve_legend(ax, handles, leg_labels, key, texts=labels, heavy=heavy, loc='best',
                            fontsize=9 if n <= 12 else 8, ncol=1 if n <= 10 else 2, framealpha=0.85)
        leg.set_in_layout(False)
        try:
            leg.set_draggable(True)
        except Exception:
            pass

    # difference plot
    if st.show_diff:
        _draw_diff(self, st, ref, axis)

    # limits
    if rescale or not st.view_set:
        _fit_view(self, series, lanes=lane)
        st.view_set = n_lines > 0
        try:
            self.logs_toolbar.update()
        except Exception:
            pass
    elif refit_y:
        _fit_view(self, series, xlim=ax.get_xlim(), lanes=lane)
    _draw_band_fills(self)
    _fit_diff_ylim(self)
    self.logs_canvas.draw_idle()


def _draw_wait_events(self, st, e, c, drawn):
    """The logged waits of log entry e (shown curve c) under 'Show probe events': Show mode an amber
    band [received, end] per wait and the hatched light-amber window [sent_from, received] in which
    the Duet sent the message (the real start lies in it); Remove mode the window before each cut
    (the cut itself: _draw_cut_labels); both modes an amber dashed line at each wait not marked and
    a grey dotted line at each failed message read."""
    ax = self.logs_ax
    A = st.artists.append
    rec = e.curve.meta
    cutting = c is not e.curve
    bands, sent = [], []
    for w in rec.get('waits') or []:
        a, b = w.get('cut', (w['received'], w['end']))
        if not cutting:
            bands.append((float(a) + c.time_offset, float(b) + c.time_offset))
        if w.get('sent_from') is not None and float(w['sent_from']) < float(w['received']):
            sa = _r2d(st, e, float(w['sent_from']))
            sb = _r2d(st, e, float(a))
            if sb > sa:
                sent.append((sa, sb))
    if bands:
        A(_span_collection(ax, bands, 0.0, 1.0, facecolor=_WAIT_COLOR, alpha=_WAIT_ALPHA, edgecolor='none',
                           zorder=0))
        drawn.add('wait')
    if sent:
        A(_span_collection(ax, sent, 0.0, 1.0, facecolor=_SENT_FACE, edgecolor=_WAIT_COLOR, hatch=_SENT_HATCH,
                           linewidth=0.0, zorder=0))
        drawn.add('sent')
    for w in rec.get('waits_not_marked') or []:
        A(ax.axvline(_r2d(st, e, float(w['received'])), color=_WAIT_COLOR, ls='--', lw=1.4, alpha=0.95, zorder=1))
        drawn.add('not_marked')
    for f in rec.get('message_read_failures') or []:
        A(ax.axvline(_r2d(st, e, float(f['t'])), color=_READFAIL_COLOR, ls=':', lw=1.4, alpha=0.95, zorder=1))
        drawn.add('read_failed')


def _draw_cut_labels(self, st, cut_marks):
    """Remove mode: a thin amber dotted line at each cut of each log, and ONE label per cut position
    (cuts of several logs closer than _CUT_LABEL_TOL share it): 'wait removed (1.74 s)', or with
    several logs 'waits removed (1.62-1.80 s)'.  Returns the label Texts."""
    out = []
    if not cut_marks:
        return out
    ax = self.logs_ax
    A = st.artists.append
    for x, _, _ in cut_marks:
        A(ax.axvline(x, color=_WAIT_COLOR, ls=':', lw=1.3, alpha=1.0, zorder=1))
    groups = []
    for x, L, e in sorted(cut_marks, key=lambda m: m[0]):
        g = groups[-1] if groups else None
        if g is not None and x - g['x'][-1] < _CUT_LABEL_TOL and e.uid not in g['uids']:
            g['x'].append(x)
            g['L'].append(L)
            g['uids'].add(e.uid)
        else:
            groups.append({'x': [x], 'L': [L], 'uids': {e.uid}})
    for g in groups:
        lo, hi = min(g['L']), max(g['L'])
        txt = (f" wait removed ({lo:.2f} s)" if len(g['L']) == 1 else
               (f" waits removed ({lo:.2f} s)" if hi - lo < 0.005 else f" waits removed ({lo:.2f}-{hi:.2f} s)"))
        lab = ax.text(min(g['x']), _PAUSE_LABEL_Y, txt, color='#e65100', fontsize=9, fontstyle='italic', rotation=90,
                      va='top', ha='left', transform=ax.get_xaxis_transform(), zorder=2, clip_on=True,
                      bbox=_LABEL_BOX)
        lab.set_in_layout(False)
        A(lab)
        out.append(lab)
    return out


class _PausePeriodKey:
    """Colour-key handle of a G-code pause drawn with its length (Show mode): drawn by
    _PausePeriodHandler as the plot draws it (strip along the top between two dashed lines)."""

    def get_label(self):
        return _KEY_LABELS['pause']


class _PausePeriodHandler(HandlerBase):
    """The pause period in the colour key, with the look of the plot: a purple strip (the same face
    colour and alpha as _PAUSE_STRIP) across the top of the handle box between two dashed purple lines
    (the pause's start and end, as drawn)."""

    def create_artists(self, legend, orig_handle, xdescent, ydescent, width, height, fontsize, trans):
        x0, y0 = -xdescent, -ydescent
        x1, y1 = x0 + width, y0 + height
        frac = _PAUSE_STRIP[1] - _PAUSE_STRIP[0]
        sh = max(height * 0.35, min(height, height * frac * 8.0))
        strip = Rectangle((x0, y1 - sh), width, sh, facecolor=_PAUSE_COLOR, alpha=_PAUSE_STRIP_ALPHA,
                          edgecolor='none', linewidth=0.0, transform=trans)
        a = Line2D([x0, x0], [y0, y1], color=_PAUSE_COLOR, ls='--', lw=1.3, alpha=0.9, transform=trans)
        b = Line2D([x1, x1], [y0, y1], color=_PAUSE_COLOR, ls='--', lw=1.3, alpha=0.9, transform=trans)
        return [strip, a, b]


def _key_handle(cls, pause_span=False):
    """Colour-key handle of an event class, with the look of the drawn artists."""
    if cls == 'det':
        return Patch(facecolor=_PROBE_DET_COLOR, alpha=_DET_ALPHA, edgecolor='none')
    if cls == 'rel':
        return Patch(facecolor=_PROBE_REL_COLOR, alpha=_REL_ALPHA, edgecolor='none')
    if cls == 'wait':
        return Patch(facecolor=_WAIT_COLOR, alpha=_WAIT_ALPHA, edgecolor='none')
    if cls == 'sent':
        return Patch(facecolor=_SENT_FACE, edgecolor=_WAIT_COLOR, hatch=_SENT_HATCH, linewidth=0.0)
    if cls == 'not_marked':
        return Line2D([], [], color=_WAIT_COLOR, ls='--', lw=1.4)
    if cls == 'read_failed':
        return Line2D([], [], color=_READFAIL_COLOR, ls=':', lw=1.4)
    if cls == 'cut':
        return Line2D([], [], color=_WAIT_COLOR, ls=':', lw=1.3)
    if cls == 'pause':
        if pause_span:
            return _PausePeriodKey()
        return Line2D([], [], color=_PAUSE_COLOR, ls='--', lw=1.3)
    if cls == 'gap':
        return Patch(facecolor=_GAP_FACE, edgecolor=_GAP_COLOR, hatch=_GAP_HATCH, linewidth=0.0)
    if cls == 'roi':
        return Patch(facecolor=_ROI_COLOR, alpha=_ROI_ALPHA, edgecolor='none')
    raise KeyError(cls)


def _remove_key(self):
    st = _state(self)
    k = st.key_artist
    st.key_artist = None
    if k is None:
        return
    try:
        loc = getattr(k, '_loc', None)
        if isinstance(loc, tuple) and len(loc) == 2:          # dragged by the user: kept for the next redraw
            st.key_loc = (float(loc[0]), float(loc[1]))
    except Exception:
        pass
    try:
        k.set_draggable(False)
    except Exception:
        pass
    _safe_remove(k)


# legend placement ('best'): a legend covering a vertical pause / cut label costs this much (more than
# any amount of data it would cover), covering the other legend (the colour key) far more
_LEGEND_LABEL_COST = 10 ** 6
_LEGEND_AVOID_COST = 10 ** 9
# preferred positions (Legend codes) when the plot is heavy (data not tested, see _LEGEND_BEST_MAX_POINTS):
# the curve legend upper right first, the key upper left first
_HEAVY_ORDER_LEGEND = (1, 2, 4, 3, 7, 6, 9, 8, 5, 10)
_HEAVY_ORDER_KEY = (2, 3, 6, 1, 4, 7, 9, 8, 5, 10)


def _label_boxes(labels, axes, renderer):
    """Window extents of the vertical pause / cut labels, clipped to the axes (they are drawn clipped)."""
    out = []
    try:
        ab = axes.bbox
    except Exception:
        return out
    for t in labels or ():
        try:
            if not t.get_visible() or t.axes is None or not t.get_text().strip():
                continue
            bb = Bbox.intersection(t.get_window_extent(renderer), ab)
        except Exception:
            continue
        if bb is not None and bb.width > 0 and bb.height > 0:
            out.append(bb)
    return out


def _best_legend_xy(leg, width, height, renderer, labels, avoid=None, data=True, order=None):
    """Position (display px) of a legend at loc 'best': among the 9 anchored positions the one with the
    lowest cost = matplotlib's data cost (vertices / lines / patches covered; skipped when data is False,
    a heavy plot) + _LEGEND_LABEL_COST per pause / cut label covered + _LEGEND_AVOID_COST when it would
    cover `avoid` (the colour key's box).  Ties: the first in `order` (default: matplotlib's)."""
    bbox = Bbox.from_bounds(0, 0, width, height)
    if data:
        bboxes, lines, offsets = leg._auto_legend_data(renderer)
    lab = _label_boxes(labels, leg.parent, renderer)
    cands = []
    for rank, idx in enumerate(order or range(1, len(leg.codes))):
        l, b = leg._get_anchored_bbox(idx, bbox, leg.get_bbox_to_anchor(), renderer)
        lb = Bbox.from_bounds(l, b, width, height)
        bad = _LEGEND_LABEL_COST * sum(1 for x in lab if lb.overlaps(x))
        if avoid is not None and lb.overlaps(avoid):
            bad += _LEGEND_AVOID_COST
        if data:
            bad += (sum(lb.count_contains(line.vertices) for line in lines) + lb.count_contains(offsets)
                    + lb.count_overlaps(bboxes) + sum(line.intersects_bbox(lb, filled=False) for line in lines))
        cands.append((bad, rank, (l, b)))
        if bad == 0:
            break
    return min(cands)[2]


class _KeyLegend(Legend):
    """The colour key: at 'best' it keeps clear of the pause / cut labels (_logs_labels) and, unless the
    plot is heavy (_logs_heavy: then the data is not tested, upper left first), of the data."""
    _logs_labels = ()
    _logs_heavy = False

    def _find_best_position(self, width, height, renderer):
        try:
            return _best_legend_xy(self, width, height, renderer, self._logs_labels, data=not self._logs_heavy,
                                   order=_HEAVY_ORDER_KEY if self._logs_heavy else None)
        except Exception:
            traceback.print_exc()
            return super()._find_best_position(width, height, renderer)


def _draw_key(self, st, drawn, pause_span=False, heavy=False, labels=()):
    """The colour key: a second compact legend listing ONLY the event classes drawn (its own artist
    on the axes, kept out of constrained_layout, draggable, in saved figures).  Placed at 'best'
    (_KeyLegend: clear of the pause / cut labels and of the data; on a heavy plot the data is not
    tested and upper left comes first; the curve legend then avoids it, _curve_legend), or where the
    user dragged it."""
    classes = [c for c in _KEY_ORDER if c in drawn]
    st.key_classes = classes
    if not classes:
        return None
    ax = self.logs_ax
    loc = st.key_loc if st.key_loc is not None else 'best'
    try:
        key = _KeyLegend(ax, [_key_handle(c, pause_span) for c in classes], [_KEY_LABELS[c] for c in classes],
                         loc=loc, fontsize=8, framealpha=0.85, handlelength=1.6, handleheight=0.9, borderpad=0.35,
                         labelspacing=0.25, title=None, handler_map={_PausePeriodKey: _PausePeriodHandler()})
        key._logs_labels = tuple(labels)
        key._logs_heavy = bool(heavy)
        key.set_in_layout(False)
        ax.add_artist(key)
        try:
            key.set_draggable(True)
        except Exception:
            pass
    except Exception:
        traceback.print_exc()
        return None
    key._logs_key = True
    st.key_artist = key
    return key


class _CurveLegend(Legend):
    """The curve legend: at 'best' it also keeps clear of the colour key (_logs_avoid) and of the pause /
    cut labels (_logs_labels), so neither legend covers the other or a label at the default positions.
    On a heavy plot (_logs_heavy) the data is not tested (matplotlib tests every vertex: slow) and
    upper right comes first."""
    _logs_avoid = None
    _logs_labels = ()
    _logs_heavy = False

    def _find_best_position(self, width, height, renderer):
        key = self._logs_avoid
        try:
            box = key.get_window_extent(renderer) if key is not None and key.get_visible() else None
        except Exception:
            box = None
        try:
            return _best_legend_xy(self, width, height, renderer, self._logs_labels, avoid=box,
                                   data=not self._logs_heavy,
                                   order=_HEAVY_ORDER_LEGEND if self._logs_heavy else None)
        except Exception:
            traceback.print_exc()
            return super()._find_best_position(width, height, renderer)


def _curve_legend(ax, handles, labels, key, texts=(), heavy=False, **kw):
    """The axes' legend (ax.get_legend()) as a _CurveLegend that avoids the colour key and the pause /
    cut label texts; ax.legend() when that cannot be made."""
    try:
        leg = _CurveLegend(ax, handles, labels, **kw)
        leg._logs_avoid = key
        leg._logs_labels = tuple(texts)
        leg._logs_heavy = bool(heavy)
        leg._remove_method = ax._remove_legend
        ax.legend_ = leg
        return leg
    except Exception:
        traceback.print_exc()
        return ax.legend(handles=handles, labels=labels, **kw)


def _decimate_band(t, lower, upper, x0, x1, max_bins):
    """The band [lower, upper] over t restricted to [x0, x1] (plus one sample beyond each edge).
    With more than 2 * max_bins samples it is min/max-decimated: each bin keeps min(lower) and
    max(upper) at its first and last time, so the filled area covers exactly the same pixels at
    this zoom with a polygon of ~4 * max_bins vertices."""
    t = np.asarray(t, dtype=float)
    n = t.size
    if n == 0:
        return t, np.asarray(lower, dtype=float), np.asarray(upper, dtype=float)
    i0 = max(0, int(np.searchsorted(t, x0, side='left')) - 1)
    i1 = min(n, int(np.searchsorted(t, x1, side='right')) + 1)
    t = t[i0:i1]
    lo = np.asarray(lower, dtype=float)[i0:i1]
    hi = np.asarray(upper, dtype=float)[i0:i1]
    m = t.size
    max_bins = max(1, int(max_bins))
    if m <= 2 * max_bins:
        return t, lo, hi
    starts = np.unique(np.linspace(0, m, max_bins + 1).astype(int)[:-1])
    ends = np.append(starts[1:], m) - 1
    with np.errstate(invalid='ignore'):
        blo = np.fmin.reduceat(lo, starts)
        bhi = np.fmax.reduceat(hi, starts)
    tt = np.column_stack([t[starts], t[ends]]).ravel()
    return tt, np.repeat(blo, 2), np.repeat(bhi, 2)


def _draw_band_fills(self):
    """(Re)draw the envelope / band fills for the current x-range of the plot (called after every
    redraw and on every zoom / pan through the xlim_changed callback)."""
    st = _state(self)
    if not _built(self) or not st.band_fills:
        return
    ax = self.logs_ax
    x0, x1 = sorted(float(x) for x in ax.get_xlim())
    try:
        width_px = float(ax.bbox.width)
    except Exception:
        width_px = 1000.0
    bins = int(min(4000.0, max(400.0, width_px if np.isfinite(width_px) else 1000.0)))
    view = (x0, x1, bins)
    if st.band_view == view and st.band_artists:
        return
    for a in st.band_artists:
        _safe_remove(a)
    st.band_artists = []
    for t, lower, upper, style in st.band_fills:
        tt, lo, hi = _decimate_band(t, lower, upper, x0, x1, bins)
        if tt.size:
            st.band_artists.append(ax.fill_between(tt, lo, hi, **style))
    st.band_view = view


def _n_lanes(st):
    """Movement lanes drawn: one per visible curve with at least one movement (as _do_redraw)."""
    return sum(1 for e in st.entries if e.visible and (st.movements.get(e.uid) or {}).get('segments'))


def _draw_diff(self, st, ref, axis):
    axd = self.logs_ax_diff
    D = st.diff_artists.append
    D(axd.axhline(0.0, color='#90a4ae', lw=0.9, zorder=1))
    if st.roi is not None:
        D(axd.axvspan(st.roi[0], st.roi[1], color=_ROI_COLOR, alpha=0.45, zorder=0, lw=0))
    msg = None
    if ref is None or not axis:
        msg = "Choose a reference curve (section 4)"
    elif not ref.curve.has(axis):
        msg = f"The reference has no {axis}"
    else:
        rc = _vc(st, ref)
        r_span = rc.times()
        for e in _visible(st, axis):
            if e is ref:
                continue
            ec = _vc(st, e)
            tt = ec.times()
            span = 0.0
            if tt.size and r_span.size:
                span = min(float(tt[-1]), float(r_span[-1])) - max(float(tt[0]), float(r_span[0]))
            r = la.compare(rc, ec, axis, roi=None, dt=_draw_dt(span))   # drawing grid only
            if r['t'].size:
                D(axd.plot(r['t'], r['diff'], color=e.color, lw=1.2, zorder=3)[0])
                st.diff_series.append((np.asarray(r['t'], dtype=float), np.asarray(r['diff'], dtype=float)))
        if not st.diff_series:
            msg = "No other visible curve with this axis overlaps the reference"
    if msg:
        D(axd.text(0.5, 0.5, msg, transform=axd.transAxes, ha='center', va='center', fontsize=10,
                   color='#90a4ae'))
    u = _axis_unit(st, axis)
    # a long axis name (e.g. an aligned export read back) would make the label taller than the panel
    # The y-label is only 'Δ (unit)': a vertical '<axis> vs ref' label is taller than the panel at
    # 1366x768.  The axis goes in a horizontal caption inside the panel (long names elided; full
    # name in the axis combo).
    axd.set_ylabel(f"Δ ({u})" if axis else "Δ", fontsize=11, fontweight='bold')
    self.logs_diff_caption = None
    if axis:
        ax_txt = axis if _std_axis(axis) else _elide_mid(axis, _LEGEND_MAX_CHARS)
        cap = axd.text(0.006, 0.95, f"{ax_txt}: curve − reference", transform=axd.transAxes, ha='left',
                       va='top', fontsize=9, color='#455a64', zorder=6, clip_on=True,
                       bbox=dict(boxstyle='round,pad=0.2', fc='white', ec='none', alpha=0.75))
        cap.set_in_layout(False)
        D(cap)
        self.logs_diff_caption = cap


def _diff_ylim(st, xlim):
    """y-limits of the difference axes for the diff samples inside xlim (plus the sample just
    outside each edge, so a narrow zoom between two samples still fits); 0 is always included.
    None when there is nothing to fit."""
    x0, x1 = sorted(float(x) for x in xlim)
    lo, hi = np.inf, -np.inf
    for t, d in st.diff_series:
        if t.size == 0:
            continue
        i0 = max(0, int(np.searchsorted(t, x0, side='left')) - 1)
        i1 = min(t.size, int(np.searchsorted(t, x1, side='right')) + 1)
        seg = d[i0:i1]
        seg = seg[np.isfinite(seg)]
        if seg.size:
            lo, hi = min(lo, float(seg.min())), max(hi, float(seg.max()))
    if not np.isfinite(lo):
        return None
    lo, hi = min(lo, 0.0), max(hi, 0.0)
    pad = (hi - lo) * 0.08 if hi > lo else max(abs(hi) * 0.1, 0.01)
    return lo - pad, hi + pad


def _fit_diff_ylim(self):
    """Fit the difference axes' y-limits to the diff inside the current time range of the plot."""
    st = _state(self)
    if not st.show_diff or not st.diff_series or not _built(self):
        return
    lim = _diff_ylim(st, self.logs_ax.get_xlim())
    if lim is not None:
        self.logs_ax_diff.set_ylim(*lim)


def _on_xlim_changed(self):
    """xlim_changed of the main or the difference axes (zoom / pan / toolbar / code): refit the
    difference y-range now and once more from the event loop (_schedule_diff_refit).  Guarded:
    setting the limits from here must not re-enter."""
    st = _state(self)
    if st.in_xlim_cb:
        return
    st.in_xlim_cb = True
    try:
        _draw_band_fills(self)
        _fit_diff_ylim(self)
        _schedule_diff_refit(self)
    except Exception:
        traceback.print_exc()
    finally:
        st.in_xlim_cb = False


def _toolbar_mode(self):
    tb = getattr(self, 'logs_toolbar', None)
    mode = getattr(tb, 'mode', '') if tb is not None else ''
    return str(getattr(mode, 'value', mode) or '')


def _schedule_diff_refit(self):
    """matplotlib sets the y-limits right after the x-limits when it pans an axes (Axes.drag_pan)
    and when the toolbar's Home / Back / Forward restore a view (Axes._set_view), which undoes the
    refit the xlim_changed callback just did on the difference panel.  So the refit is repeated
    once control is back in the event loop (before the canvas' idle draw, scheduled after it).
    Not in zoom-rectangle mode: a rectangle drawn on the difference panel sets its y-range on
    purpose (a rectangle on the main axes still refits it: the callback above).  Home / Back /
    Forward refit in every mode (_on_view_restored)."""
    st = _state(self)
    timer = getattr(self, 'logs_diff_refit_timer', None)
    if timer is None or not st.show_diff or not st.diff_series:
        return
    if _toolbar_mode(self) == 'zoom rect':
        return
    if not timer.isActive():
        timer.start()


def _on_view_restored(self):
    """Toolbar Home / Back / Forward (_LogsToolbar), in any mode: the restored view's difference
    y-range may be stale (stored before a data change, or drawn by a zoom rectangle), so it is
    refitted to the restored time range at once and again from the event loop."""
    st = _state(self)
    if not _built(self) or not st.show_diff or not st.diff_series:
        return
    _fit_diff_ylim(self)
    self.logs_canvas.draw_idle()
    timer = getattr(self, 'logs_diff_refit_timer', None)
    if timer is not None and not timer.isActive():
        timer.start()


def _flush_diff_refit(self):
    st = _state(self)
    try:
        if not _built(self) or not st.show_diff or not st.diff_series:
            return
        lim = _diff_ylim(st, self.logs_ax.get_xlim())
        if lim is None:
            return
        cur = self.logs_ax_diff.get_ylim()
        tol = 1e-9 * max(1.0, abs(lim[1] - lim[0]))
        if abs(cur[0] - lim[0]) > tol or abs(cur[1] - lim[1]) > tol:
            self.logs_ax_diff.set_ylim(*lim)
            self.logs_canvas.draw_idle()
    except Exception:
        traceback.print_exc()


def _fit_view(self, series, xlim=None, lanes=0):
    """Set the main axes limits to the data of series [(x, y)] (y limited to xlim when given),
    leaving room at the bottom for `lanes` movement lanes."""
    ax = self.logs_ax
    if xlim is None:
        x0, x1 = np.inf, -np.inf
        for x, _ in series:
            x = np.asarray(x, dtype=float)
            x = x[np.isfinite(x)]
            if x.size:
                x0, x1 = min(x0, float(x.min())), max(x1, float(x.max()))
        if not np.isfinite(x0):
            x0, x1 = 0.0, 1.0
        w = x1 - x0
        pad = w * 0.01 if w > 0 else 0.5
        x0, x1 = x0 - pad, x1 + pad
    else:
        x0, x1 = xlim
    ax.set_xlim(x0, x1)
    lo, hi = np.inf, -np.inf
    for x, y in series:
        x = np.asarray(x, dtype=float)
        y = np.asarray(y, dtype=float)
        if xlim is not None and x.shape == y.shape:
            y = y[(x >= x0) & (x <= x1)]
        y = y[np.isfinite(y)]
        if y.size:
            lo, hi = min(lo, float(y.min())), max(hi, float(y.max()))
    if not np.isfinite(lo):
        lo, hi = 0.0, 1.0
    if hi - lo < 1e-9:
        pad = max(abs(hi) * 0.05, 0.5)
    else:
        pad = (hi - lo) * 0.08
    y0, y1 = lo - pad, hi + pad
    if lanes > 0:
        f = min(0.6, _LANE_Y0 + lanes * _LANE_STEP + 0.015)     # axes fraction used by the lanes
        y0 = min(y0, (lo - f * y1) / (1.0 - f))
    ax.set_ylim(y0, y1)


# ----------------------------------------------------------------------------
# Actions: files
# ----------------------------------------------------------------------------
def _add_entry(st, curve):
    curve.name = _unique_name(st, curve.name)
    st.uid_counter += 1
    e = LogsEntry(st.uid_counter, curve, _next_color(st))
    st.entries.append(e)
    return e


@_action("Log files", busy=True)
def logs_add_files(self, paths):
    """Load TRACE log files (list of paths). Unusable files are reported in one warning; returns the
    list of Curves added."""
    st = _state(self)
    if isinstance(paths, (str, os.PathLike)):
        paths = [paths]
    added, errors = [], []
    for p in paths or []:
        try:
            c = la.read_trace_log(p)
        except Exception as e:
            errors.append(f"{os.path.basename(str(p))}: {e}")
            continue
        added.append(_add_entry(st, c))
    if added:
        _remember_folder(st, str(added[-1].curve.path))
        st.selected = _index_of(st, added[-1])
        _refresh_everything(self, rescale=True)
        n_log = sum(1 for e in st.entries if e.curve.kind == 'log')
        n_ref = len(st.entries) - n_log
        warn = [e.curve.name for e in added if _info(e.curve)[1]]
        waits = [f"{e.curve.name}: {_waits_text(e.curve)}" for e in added if _has_waits(e.curve)]
        _set_summary(self, f"Added {len(added)} log(s) · loaded: {n_log} log(s), {n_ref} reference(s)"
                     + (f" · {' · '.join(waits)}" if waits else "")
                     + (f" · all positions 0 in: {', '.join(warn)}" if warn else ""))
    if errors:      # queued by _warn while the wait cursor is shown, then displayed with the normal cursor
        _warn(self, "Log files", "These files could not be loaded:\n\n" + "\n".join(errors))
    return [e.curve for e in added]


@_action("Reference G-code", busy=True)
def logs_add_reference(self, path_or_text, name=None):
    """Load a reference G-code (file path or G-code text); it becomes the reference curve."""
    st = _state(self)
    lat, si = _platform_dims(self)
    c = la.read_reference_gcode(path_or_text, name=name, lat_dim=lat, si_dim=si)
    e = _add_entry(st, c)
    st.ref_uid = e.uid
    if c.path:
        _remember_folder(st, c.path)
    if st.selected < 0:
        st.selected = _index_of(st, e)
    _refresh_everything(self, rescale=True)
    c = e.curve                         # (rebuilt with the logged pause lengths, _apply_pause_lengths)
    pauses = c.meta.get('pauses') or []
    _set_summary(self, f"Reference '{c.name}' loaded: {c.meta.get('n_rows')} G-code rows, "
                       f"{float(c.meta.get('total_time') or c.t[-1]):.2f} s, {len(pauses)} pause(s)"
                       + (f" · {_pause_summary(st)}" if pauses else ""))
    return c


def _rrf_gcode_path(gcode):
    g = str(gcode).strip().replace('\\', '/')
    p = g.split(':', 1)[1] if re.match(r'^\d+:', g) else g
    if p.startswith('/gcodes/'):
        return p
    return '/gcodes/' + os.path.basename(p)


@_action("Reference from Duet", busy=True)
def logs_reference_from_duet(self, index=None):
    """Download the G-code named in a log's header (meta['gcode']) from the Duet and add it as the
    reference curve (index None = selected curve)."""
    st = _state(self)
    e = _entry_at(st, index)
    if e.curve.kind != 'log':
        raise ValueError("Select a log curve (not a reference)")
    gcode = e.curve.meta.get('gcode')
    if not gcode:
        raise ValueError(f"{e.curve.name}: the log header has no G-code file name")
    if not getattr(self, 'duet_connected', False):
        raise ValueError("Not connected to the Duet")
    from fcn_monitor.fcn_duet import duet_request, get_clean_duet_ip
    ip = get_clean_duet_ip(self)
    rrf = _rrf_gcode_path(gcode)
    url = f"http://{ip}/rr_download?name={quote(rrf, safe='/')}"
    r = duet_request(url, timeout=10)
    if r.status_code != 200:
        raise ValueError(f"The Duet returned HTTP {r.status_code} for {rrf}")
    text = r.text
    if not text or not text.strip():
        raise ValueError(f"{rrf} is empty on the Duet")
    base = os.path.basename(rrf)
    lat, si = _platform_dims(self)
    c = la.read_reference_gcode(text if '\n' in text else text + '\n',
                                name=os.path.splitext(base)[0], lat_dim=lat, si_dim=si)
    c.meta['gcode'] = base
    ne = _add_entry(st, c)
    st.ref_uid = ne.uid
    _refresh_everything(self, rescale=True)
    c = ne.curve
    _set_summary(self, f"Reference '{c.name}' downloaded from the Duet ({rrf}), "
                       f"{len(c.meta.get('pauses') or [])} pause(s)"
                       + (f" · {_pause_summary(st)}" if c.meta.get('pauses') else ""))
    return c


@_action("Remove curves")
def logs_remove_curves(self, indices=None):
    """Remove curves by table index (None = selected curve).  Their rows leave every results view;
    the selection stays on the previously selected curve if it is kept, else it is cleared (so a
    second 'Remove selected' never removes a curve the user did not pick)."""
    st = _state(self)
    if indices is None:
        indices = [st.selected]
    if isinstance(indices, int):
        indices = [indices]
    idx = sorted({int(i) for i in indices if i is not None and 0 <= int(i) < len(st.entries)}, reverse=True)
    if not idx:
        raise ValueError("Select a curve in the Files table first")
    sel_entry = st.entries[st.selected] if 0 <= st.selected < len(st.entries) else None
    names, uids = [], []
    for i in idx:
        names.append(st.entries[i].curve.name)
        uids.append(st.entries[i].uid)
        del st.entries[i]
    st.selected = _index_of(st, sel_entry) if sel_entry is not None else -1
    if st.ref_uid in uids:
        st.ref_uid = _default_ref_uid(st)
    _prune_results(self, uids, names)
    _refresh_everything(self, rescale=True)
    _set_summary(self, f"Removed {', '.join(reversed(names))}")
    return len(idx)


@_action("Clear all")
def logs_clear_all(self):
    """Remove every curve and every analysis result."""
    st = _state(self)
    st.entries = []
    st.selected = -1
    st.ref_uid = None
    st.peaks, st.movements, st.points = {}, {}, []
    st.roi = None
    st.results = {}
    st.results_ref = {}
    st.results_notes = {}
    st.results_base = {}
    st.results_uids = {}
    st.current_results = None
    st.pause_source_uid = None
    st.pause_info = []
    st.key_loc = None
    if _built(self):
        self.logs_results_combo.blockSignals(True)
        self.logs_results_combo.clear()
        self.logs_results_combo.blockSignals(False)
        _fill_results_table(self, ['Results'], [])
    _refresh_everything(self, rescale=True)
    _set_summary(self, "All curves removed.")


@_action("Select curve")
def logs_select_curve(self, index):
    st = _state(self)
    _entry_at(st, index)
    st.selected = int(index)
    if _built(self):
        tbl = self.logs_curves_table
        tbl.blockSignals(True)
        tbl.selectRow(st.selected)
        tbl.blockSignals(False)
    _update_selected_label(self)
    _update_duet_button(self)
    return st.selected


@_action("Show curve")
def logs_set_visible(self, index, on):
    st = _state(self)
    e = _entry_at(st, index)
    e.visible = bool(on)
    if _built(self):
        it = self.logs_curves_table.item(int(index), 0)
        if it is not None:
            self.logs_curves_table.blockSignals(True)
            it.setCheckState(Qt.Checked if on else Qt.Unchecked)
            self.logs_curves_table.blockSignals(False)
        # Remove mode: which logs are shown cut decides the pause notes / summary (as the plot labels)
        _refresh_pause_table(self)
    _refresh_pauses_view(self)
    _refresh_live_notes(self)           # Remove mode: the notes mark a hidden cut log
    _redraw(self)


@_action("Curve colour")
def logs_set_curve_color(self, index, color):
    st = _state(self)
    e = _entry_at(st, index)
    e.color = mcolors.to_hex(color)
    if _built(self):
        it = self.logs_curves_table.item(int(index), 1)
        if it is not None:
            it.setIcon(_color_icon(e.color))
        _refresh_points_table(self)
    _redraw(self)


@_action("Time offset")
def logs_set_time_offset(self, index, value):
    st = _state(self)
    e = _entry_at(st, index)
    e.curve.time_offset = float(value)
    _sync_offset_spins(self)
    _after_offsets_changed(self)


@_action("Value offset")
def logs_set_value_offset(self, index, value, axis=None):
    st = _state(self)
    e = _entry_at(st, index)
    axis = axis or _require_axis(st)
    if not e.curve.has(axis):
        raise ValueError(f"{e.curve.name} has no axis {axis}")
    e.curve.value_offsets[axis] = float(value)
    _sync_offset_spins(self)
    _after_offsets_changed(self)


def _after_offsets_changed(self):
    """Tables and the views that follow the plot (pause table, points, 'Pauses', 'Peak list') after a
    time / value offset changed; then the plot."""
    if _built(self):
        _refresh_pause_table(self)
        _refresh_points_table(self)
    _refresh_pauses_view(self)
    _refresh_peak_list(self)
    _redraw(self)


# ----------------------------------------------------------------------------
# Actions: axes / display
# ----------------------------------------------------------------------------
@_action("Axes")
def logs_set_axis_enabled(self, axis, on):
    """Show / hide an axis on the plot."""
    st = _state(self)
    if axis not in st.known_axes:
        raise ValueError(f"No loaded curve has the axis {axis!r}")
    if on:
        st.enabled_axes.add(axis)
    else:
        st.enabled_axes.discard(axis)
    cb = getattr(self, 'logs_axis_checks', {}).get(axis)
    if cb is not None and cb.isChecked() != bool(on):
        cb.blockSignals(True)
        cb.setChecked(bool(on))
        cb.blockSignals(False)
    _redraw(self, rescale=True)
    return sorted(st.enabled_axes, key=st.known_axes.index)


@_action("Analysis axis")
def logs_set_analysis_axis(self, axis):
    """Axis used by all analyses (also enabled on the plot)."""
    st = _state(self)
    if axis not in st.known_axes:
        raise ValueError(f"No loaded curve has the axis {axis!r}")
    changed = axis != st.analysis_axis
    st.analysis_axis = axis
    st.enabled_axes.add(axis)
    if _built(self):
        _refresh_axes_panel(self, rebuild_combo=False)     # may run inside the combo's own signal
        _sync_offset_spins(self)
        _update_unit_suffixes(self)
    _redraw(self, rescale=changed)
    return axis


@_action("Display")
def logs_set_display(self, show_probe=None, show_gaps=None, show_pauses=None, show_diff=None,
                     show_band=None, band_k=None, show_envelope=None):
    """Display options (None = unchanged)."""
    st = _state(self)
    pairs = (('show_probe', show_probe, 'logs_chk_probe'), ('show_gaps', show_gaps, 'logs_chk_gaps'),
             ('show_pauses', show_pauses, 'logs_chk_pauses'), ('show_diff', show_diff, 'logs_chk_diff'),
             ('show_band', show_band, 'logs_chk_band'), ('show_envelope', show_envelope, 'logs_chk_envelope'))
    diff_changed = False
    for attr, val, wname in pairs:
        if val is None:
            continue
        if attr == 'show_diff' and bool(val) != st.show_diff:
            diff_changed = True
        setattr(st, attr, bool(val))
        w = getattr(self, wname, None)
        if w is not None and w.isChecked() != bool(val):
            w.blockSignals(True)
            w.setChecked(bool(val))
            w.blockSignals(False)
    if band_k is not None:
        k = float(band_k)
        if not k > 0:
            raise ValueError("k must be > 0")
        st.band_k = k
        w = getattr(self, 'logs_spin_band_k', None)
        if w is not None and abs(w.value() - k) > 1e-12:
            w.blockSignals(True)
            w.setValue(k)
            w.blockSignals(False)
    if diff_changed and _built(self):
        _apply_diff_layout(self)
    _redraw(self)
    if (show_band is not None or show_envelope is not None or band_k is not None) and \
            (st.show_band or st.show_envelope):
        txt = _ensemble_summary(st)
        _set_summary(self, txt[:1].upper() + txt[1:])


# ----------------------------------------------------------------------------
# Actions: ROI / view / pick mode
# ----------------------------------------------------------------------------
@_action("Region of interest")
def logs_set_roi(self, t0, t1):
    """Region of interest (s, displayed time base) used by every analysis."""
    st = _state(self)
    a, b = float(t0), float(t1)
    if not (np.isfinite(a) and np.isfinite(b)):
        raise ValueError("ROI limits must be numbers")
    if a > b:
        a, b = b, a
    if b - a <= 1e-6:
        raise ValueError("The ROI must have a length > 0")
    st.roi = (a, b)
    _sync_roi_widgets(self)
    _redraw(self)
    return st.roi


@_action("Region of interest")
def logs_clear_roi(self):
    st = _state(self)
    st.roi = None
    _sync_roi_widgets(self)
    _redraw(self)


@_action("Zoom")
def logs_zoom_to_roi(self):
    st = _state(self)
    if st.roi is None:
        _redraw(self, rescale=True)
        return
    a, b = st.roi
    pad = (b - a) * 0.03
    series = []
    order = [x for x in st.known_axes if x in st.enabled_axes]
    for e in st.entries:
        if not e.visible:
            continue
        c = _vc(st, e)
        for ax_ in order:
            if c.has(ax_):
                series.append(_plot_xy(c, ax_))
    _fit_view(self, series, xlim=(a - pad, b + pad), lanes=_n_lanes(st))
    _fit_diff_ylim(self)            # (also done by the xlim_changed callback)
    self.logs_canvas.draw_idle()


@_action("Zoom")
def logs_zoom_all(self):
    _redraw(self, rescale=True)


@_action("Plot mode")
def logs_set_pick_mode(self, mode):
    """Mouse mode of the plot: None, 'roi' (drag selects the ROI) or 'points' (click adds a point)."""
    st = _state(self)
    if mode not in (None, 'roi', 'points'):
        raise ValueError("mode must be None, 'roi' or 'points'")
    st.pick_mode = mode
    for wname, m in (('logs_btn_roi_select', 'roi'), ('logs_btn_points_mode', 'points')):
        w = getattr(self, wname, None)
        if w is not None and w.isChecked() != (mode == m):
            w.blockSignals(True)
            w.setChecked(mode == m)
            w.blockSignals(False)
    span = getattr(self, 'logs_span', None)
    if span is not None:
        span.set_active(mode == 'roi')
    if mode == 'points':
        if st.analysis_axis and st.analysis_axis not in st.enabled_axes:
            _set_summary(self, _hidden_axis_msg(st.analysis_axis))
        else:
            _set_summary(self, f"Click on the plot to add points on {st.analysis_axis or 'the analysis axis'} "
                               "(the pan / zoom tools of the toolbar must be off); drag a point to move it.")
    elif mode == 'roi':
        _set_summary(self, "Drag on the plot to select the region of interest.")
    return mode


def _on_span_selected(self, xmin, xmax):
    try:
        if abs(float(xmax) - float(xmin)) < 1e-6:
            return
    except Exception:
        return
    logs_set_roi(self, xmin, xmax)


def _on_roi_spins(self):
    st = _state(self)
    a, b = self.logs_spin_roi0.value(), self.logs_spin_roi1.value()
    if st.roi is not None and abs(a - st.roi[0]) < 1e-9 and abs(b - st.roi[1]) < 1e-9:
        return
    if abs(b - a) <= 1e-6:
        return
    _deferred(self, logs_set_roi, a, b)


def _toolbar_busy(self):
    return bool(_toolbar_mode(self))


def _on_canvas_press(self, event):
    try:
        st = _state(self)
        if _drag_press(self, event):
            return                                  # on a point / lane edge: armed to drag (adds nothing)
        if st.pick_mode != 'points' or _toolbar_busy(self):
            return
        if event.inaxes is not self.logs_ax or event.button != 1 or getattr(event, 'dblclick', False):
            return
        if event.xdata is None or event.ydata is None:
            return
        if _on_a_legend(self, event):
            return                                  # click / drag on the legend or the key: no point
        _points_click(self, float(event.xdata), float(event.ydata))
    except Exception as e:
        traceback.print_exc()
        _warn(self, "Reference points", e)


def _on_a_legend(self, event):
    """The mouse event is on the curve legend or the colour key (both are dragged themselves)."""
    for leg in (self.logs_ax.get_legend(), _state(self).key_artist):
        if leg is None or not leg.get_visible():
            continue
        try:
            if leg.contains(event)[0]:
                return True
        except Exception:
            return True
    return False


def _points_click(self, xdata, ydata):
    """Pick mode 'points': a click at (xdata, ydata) (data coordinates) adds a point on the nearest
    visible sample (logs_pick_point); with the analysis axis hidden the status line says why not."""
    st = _state(self)
    if st.analysis_axis and st.analysis_axis not in st.enabled_axes:
        _set_summary(self, _hidden_axis_msg(st.analysis_axis))      # status only, no box per click
        return
    logs_pick_point(self, float(xdata), float(ydata))


# ----------------------------------------------------------------------------
# Dragging reference points and movement lane edges on the plot
# ----------------------------------------------------------------------------
# A left press on a point marker (pick mode None or 'points') or on a lane edge / inside a lane
# segment arms a drag (st.drag); nothing changes until the mouse has moved _DRAG_MIN_PX.  While the
# mouse moves only the dragged artist is redrawn: the background without it is captured once (one
# full draw), then restore_region + draw_artist + blit.  The release commits to the state with one
# full redraw (same zoom); Escape cancels; a redraw from elsewhere drops the drag (state unchanged).
class _DragKeyFilter(QObject):
    """Application event filter, installed only while a drag is armed: Escape cancels the drag
    wherever the keyboard focus is (the embedded canvas takes no focus of its own)."""

    def __init__(self, win, parent=None):
        super().__init__(parent)
        self._win = win

    def eventFilter(self, obj, event):
        try:
            if event.type() in (QEvent.KeyPress, QEvent.ShortcutOverride) and event.key() == Qt.Key_Escape:
                st = getattr(self._win, 'logs_state', None)
                if isinstance(st, LogsState) and st.drag is not None:
                    _drag_cancel(self._win)
                    event.accept()
                    return True
        except Exception:
            traceback.print_exc()
        return False


def _drag_filter(self, on):
    f = getattr(self, 'logs_drag_filter', None)
    app = QApplication.instance()
    if f is None or app is None:
        return
    try:
        if on:
            app.installEventFilter(f)       # installing twice keeps one filter
        else:
            app.removeEventFilter(f)
    except Exception:
        pass


def _dpr(self):
    """Device pixel ratio of the canvas (matplotlib event coordinates are device pixels)."""
    try:
        r = float(getattr(self.logs_canvas, 'device_pixel_ratio', 1.0) or 1.0)
    except Exception:
        r = 1.0
    return r if r > 0 else 1.0


def _drag_allowed(self, event):
    """A press / hover there may drag a point or a lane: pick mode None or 'points' (not the ROI
    selector), no toolbar mode, no other widget holding the canvas, inside the main axes and not on
    the legend (which is dragged itself)."""
    st = _state(self)
    if not _built(self) or st.pick_mode not in (None, 'points') or _toolbar_busy(self):
        return False
    if event is None or event.inaxes is not self.logs_ax or event.x is None or event.y is None:
        return False
    if not (st.point_artists or st.lane_artists):
        return False
    try:
        if self.logs_canvas.widgetlock.locked():
            return False
    except Exception:
        pass
    return not _on_a_legend(self, event)


def _drag_target(self, event):
    """The draggable item at the mouse (pixel hit test against the artists of the last redraw):
    dict(kind='point', pid) for a marker within _DRAG_POINT_PX, dict(kind='start' | 'stop', uid, mid)
    for a lane edge within _DRAG_EDGE_PX inside that lane's band, dict(kind='move', uid, mid) inside a
    lane segment; the nearest marker / edge wins (an edge shared by two segments goes to the one the
    mouse is in), a segment body only when no marker or edge is near.  None elsewhere."""
    st = _state(self)
    ax = self.logs_ax
    x, y = float(event.x), float(event.y)
    dpr = _dpr(self)
    cands = []                  # (class, distance, tie, target): class 0 marker / edge, 1 segment body
    if st.point_artists:
        pids = list(st.point_artists)
        px = ax.transData.transform(np.array([st.point_artists[p]['xy'] for p in pids], dtype=float))
        d = np.hypot(px[:, 0] - x, px[:, 1] - y)
        d = np.where(np.isfinite(d), d, np.inf)
        j = int(d.size - 1 - np.argmin(d[::-1]))     # of coinciding markers the one drawn last (on top)
        if d[j] <= _DRAG_POINT_PX * dpr:
            cands.append((0, float(d[j]), 0, {'kind': 'point', 'pid': pids[j]}))
    if st.lane_artists:
        slack = _DRAG_LANE_SLACK_PX * dpr
        r_edge = _DRAG_EDGE_PX * dpr
        y_any = float(ax.get_ylim()[0])
        for uid, lane in st.lane_artists.items():
            yb = ax.transAxes.transform([(0.0, lane['y0']), (0.0, lane['y1'])])[:, 1]
            if not (float(yb.min()) - slack <= y <= float(yb.max()) + slack):
                continue
            rng = np.asarray(lane['ranges'], dtype=float).reshape(-1, 2)
            if rng.size == 0:
                continue
            xs = ax.transData.transform(np.column_stack([rng.ravel(), np.full(rng.size, y_any)]))[:, 0]
            xs = xs.reshape(-1, 2)
            # only the segments near the mouse are looked at (a lane can hold thousands)
            near = (np.abs(xs[:, 0] - x) <= r_edge) | (np.abs(xs[:, 1] - x) <= r_edge) \
                | ((np.minimum(xs[:, 0], xs[:, 1]) <= x) & (x <= np.maximum(xs[:, 0], xs[:, 1])))
            for k in np.flatnonzero(near).tolist():
                x0, x1 = float(min(xs[k])), float(max(xs[k]))
                inside = x0 <= x <= x1
                mid = lane['ids'][k]
                for xe, which in ((float(xs[k, 0]), 'start'), (float(xs[k, 1]), 'stop')):
                    de = abs(xe - x)
                    if de <= r_edge:
                        cands.append((0, de, 0 if inside else 1, {'kind': which, 'uid': uid, 'mid': mid}))
                if inside:
                    cands.append((1, 0.0, 0, {'kind': 'move', 'uid': uid, 'mid': mid}))
    if not cands:
        return None
    return min(cands, key=lambda c: c[:3])[3]


def _lane_put_path(lane, j, path):
    """Segment j of a lane's PolyCollection drawn as `path`: only that path is replaced, so the cost
    of a drag step does not grow with the number of movements in the lane."""
    col = lane['col']
    paths = col.get_paths()
    paths[j] = path
    if col.get_paths()[j] is not path:         # (a matplotlib that hands out a copy: all vertices)
        verts = [p.vertices[:4] for p in paths]
        col.set_verts(verts)
    col.stale = True


def _lane_path(lane, a, b):
    """Closed path of a lane segment spanning a..b (data x, axes-fraction y)."""
    y0, y1 = lane['y0'], lane['y1']
    return mpath.Path(np.array([[a, y0], [a, y1], [b, y1], [b, y0], [a, y0]], dtype=float), closed=True)


def _drag_setup(self, tgt):
    """Drag state of a target of _drag_target: the curve's sample times (and values) cached, the
    allowed sample range, the artists it moves; None when it cannot be dragged."""
    st = _state(self)
    if tgt['kind'] == 'point':
        art = st.point_artists.get(tgt['pid'])
        p = next((q for q in st.points if q.get('id') == tgt['pid']), None)
        e = _entry_by_uid(st, p['uid']) if p is not None else None
        if art is None or e is None or not e.curve.has(p['axis']):
            return None
        vc = _vc(st, e)
        tt = vc.times()
        if tt.size == 0:
            return None
        i0 = _nearest_idx(tt, art['xy'][0])
        return dict(tgt, uid=e.uid, tt=tt, vv=vc.values(p['axis']), i0=i0, i=i0, lo=0, hi=int(tt.size) - 1,
                    artists=[art['marker'], art['ann']], orig=art['xy'])
    lane = st.lane_artists.get(tgt['uid'])
    found = _movement_by_id(st, tgt['mid'])
    if lane is None or found is None or tgt['mid'] not in lane['ids']:
        return None
    e, mv, k = found
    tt = _vc(st, e).times()
    n = int(tt.size)
    if n < 2:
        return None
    segs = mv['segments']
    ia, ib = _nearest_idx(tt, _r2d(st, e, float(segs[k][0]))), _nearest_idx(tt, _r2d(st, e, float(segs[k][1])))
    lo = _nearest_idx(tt, _r2d(st, e, float(segs[k - 1][1]))) if k > 0 else 0          # previous stop
    hi = _nearest_idx(tt, _r2d(st, e, float(segs[k + 1][0]))) if k + 1 < len(segs) else n - 1   # next start
    kind = tgt['kind']
    if kind == 'start':
        lo, hi = lo, ib - 1
    elif kind == 'stop':
        lo, hi = ia + 1, hi
    if hi < lo or (kind == 'move' and ib - ia > hi - lo) or ib <= ia:
        return None
    j = lane['ids'].index(tgt['mid'])
    tol = _DRAG_MOVE_WIDTH_TOL * float(np.median(np.diff(tt))) if kind == 'move' else 0.0
    return dict(tgt, uid=e.uid, tt=tt, ia0=ia, ib0=ib, ia=ia, ib=ib, lo=lo, hi=hi, lane=lane, j=j,
                path0=lane['col'].get_paths()[j], tol=tol, stuck=False, artists=[lane['col']])


def _drag_press(self, event):
    """Left press: arm a drag when it is on a point marker / lane edge / lane segment (see
    _drag_target).  True when armed (the press then adds no point)."""
    st = _state(self)
    try:
        if st.drag is not None:
            if getattr(event, 'button', None) != 1:
                return True                         # another button while dragging: ignored
            _drag_cancel(self)                      # the release of an earlier press never came
        if getattr(event, 'button', None) != 1 or getattr(event, 'dblclick', False) \
                or not _drag_allowed(self, event):
            return False
        if st.pending_redraw is not None and not _redraw_held(self):
            # a debounced redraw (spin box) would drop the drag when it fires: draw now, then hit-test
            _flush_redraw_now(self)
            if not _drag_allowed(self, event):
                return False
        tgt = _drag_target(self, event)
        d = _drag_setup(self, tgt) if tgt is not None else None
        if d is None:
            return False
        x0 = float(self.logs_ax.transData.inverted().transform((float(event.x), float(event.y)))[0])
        d.update(press=(float(event.x), float(event.y)), x0=x0, started=False, bg=None, bg_size=None,
                 capturing=False, press_data=(event.xdata, event.ydata))
        st.drag = d
        _drag_filter(self, True)
        return True
    except Exception:
        traceback.print_exc()
        _drag_end(self)
        return False


def _drag_move(self, d, event):
    """Move the dragged artist to the mouse x, snapped to a sample of its curve within the allowed
    range.  True when it moved."""
    try:
        x = float(self.logs_ax.transData.inverted().transform((float(event.x), float(event.y)))[0])
    except Exception:
        return False
    if not math.isfinite(x):
        return False
    tt = d['tt']
    kind = d['kind']
    if kind == 'point':
        i = min(max(_nearest_idx(tt, x), d['lo']), d['hi'])
        if i == d['i']:
            return False
        d['i'] = i
        t, v = float(tt[i]), float(d['vv'][i])
        d['artists'][0].set_data([t], [v])
        d['artists'][1].xy = (t, v)
        return True
    if kind in ('start', 'stop'):
        i = min(max(_nearest_idx(tt, x), d['lo']), d['hi'])
        key = 'ia' if kind == 'start' else 'ib'
        if i == d[key]:
            return False
        d[key] = i
    else:
        dx = x - d['x0']
        best = _move_target(d, dx)
        # it lags behind the mouse (more than ~2 sample intervals): the toolbar says why (_drag_message)
        if best is None:
            d['stuck'] = True
            return False
        ia, ib, lag = best
        d['stuck'] = lag > 2.0 * d['tol'] / _DRAG_MOVE_WIDTH_TOL
        if (ia, ib) == (d['ia'], d['ib']):
            return False
        d['ia'], d['ib'] = ia, ib
    _lane_put_path(d['lane'], d['j'], _lane_path(d['lane'], float(tt[d['ia']]), float(tt[d['ib']])))
    return True


def _move_target(d, dx):
    """Sample indices (start, stop) of a whole lane segment dragged by dx (s) since the press: both
    ends shifted by the same time and each on a sample of the curve, inside the allowed range, with
    the width of the movement kept (within d['tol']: on sparse rows, e.g. a G-code reference, most
    shifts would change it; those positions are skipped).  Candidates: the start or the stop at the
    sample nearest to the mouse (the other end follows), or the range limit when the mouse is past
    it; the one nearest to the mouse wins.  (start, stop, |its shift - dx|), or None when there is none
    (the segment stays put)."""
    tt = d['tt']
    lo, hi = d['lo'], d['hi']
    t_a, t_b = float(tt[d['ia0']]), float(tt[d['ib0']])
    w0 = t_b - t_a
    i = _nearest_idx(tt, t_a + dx)
    j = _nearest_idx(tt, t_b + dx)
    cands = [(i, _nearest_idx(tt, t_b + float(tt[i]) - t_a)), (_nearest_idx(tt, t_a + float(tt[j]) - t_b), j)]
    if t_a + dx < float(tt[lo]):
        cands.append((lo, _nearest_idx(tt, t_b + float(tt[lo]) - t_a)))
    if t_b + dx > float(tt[hi]):
        cands.append((_nearest_idx(tt, t_a + float(tt[hi]) - t_b), hi))
    best = None
    for ia, ib in cands:
        if not lo <= ia < ib <= hi:
            continue
        werr = abs(float(tt[ib]) - float(tt[ia]) - w0)
        if werr > d['tol'] + 1e-12:
            continue
        shift = 0.5 * ((float(tt[ia]) - t_a) + (float(tt[ib]) - t_b))
        key = (abs(shift - dx), werr)
        if best is None or key < best[0]:
            best = (key, (ia, ib))
    return (best[1][0], best[1][1], best[0][0]) if best is not None else None


def _fig_size(self):
    bb = self.logs_fig.bbox
    return int(round(bb.width)), int(round(bb.height))


def _drag_blit(self, d):
    """Show the dragged artist at its new place: restore the background captured without it, draw
    the artist, blit.  The background is (re)captured with one full draw when there is none yet, or
    after another full draw / a resize."""
    cv, fig = self.logs_canvas, self.logs_fig
    arts = d['artists']
    if d.get('bg') is None or d.get('bg_size') != _fig_size(self):
        vis = [a.get_visible() for a in arts]
        d['capturing'] = True
        try:
            for a in arts:
                a.set_visible(False)
            cv.draw()
            d['bg'] = cv.copy_from_bbox(fig.bbox)
            d['bg_size'] = _fig_size(self)
        finally:
            for a, on in zip(arts, vis):
                a.set_visible(on)
            d['capturing'] = False
    else:
        cv.restore_region(d['bg'])
    for a in arts:
        if a.get_visible():
            self.logs_ax.draw_artist(a)
    cv.blit(fig.bbox)


def _drag_end(self):
    """Forget the drag (nothing restored) and remove the Escape filter."""
    st = _state(self)
    st.drag = None
    _drag_filter(self, False)


def _drag_restore_artists(self, d):
    """Put the dragged artist back where it was drawn (Escape / a lost release)."""
    if d['kind'] == 'point':
        t, v = d['orig']
        d['artists'][0].set_data([t], [v])
        d['artists'][1].xy = (t, v)
    else:
        _lane_put_path(d['lane'], d['j'], d['path0'])


def _drag_cancel(self):
    """Cancel the drag (Escape): the artist goes back to where it was, the state is unchanged."""
    st = _state(self)
    d = st.drag
    if d is None:
        return
    _drag_end(self)
    if not d.get('started'):
        return
    try:
        _drag_restore_artists(self, d)
        if d.get('bg') is not None and d.get('bg_size') == _fig_size(self):
            self.logs_canvas.restore_region(d['bg'])
            for a in d['artists']:
                if a.get_visible():
                    self.logs_ax.draw_artist(a)
            self.logs_canvas.blit(self.logs_fig.bbox)
        else:
            self.logs_canvas.draw_idle()
    except Exception:
        traceback.print_exc()
        self.logs_canvas.draw_idle()
    what = 'point' if d['kind'] == 'point' else 'movement'
    _set_summary(self, f"Drag cancelled: the {what} is unchanged.")


def _drag_abort(self):
    """A redraw from elsewhere during a drag (debounced spin box, an action): the drag is dropped
    (the state was not changed; the redraw rebuilds the artists)."""
    st = _state(self)
    d = st.drag
    _drag_end(self)
    if d is not None and d.get('started'):
        _set_summary(self, "Drag cancelled: the plot was redrawn.")


def _drag_commit(self, d):
    """Release after a drag: store the dragged point / movement (one full redraw at the same zoom,
    tables and status line)."""
    st = _state(self)
    if d['kind'] == 'point':
        p = next((q for q in st.points if q.get('id') == d['pid']), None)
        e = _entry_by_uid(st, d['uid'])
        if p is None or e is None:
            _redraw(self)
            return
        if d['i'] == d['i0']:
            _set_summary(self, f"Point {st.points.index(p) + 1}: not moved (back on its sample).")
            return
        _point_to_sample(self, st.points.index(p), p, e, d['i'], " (dragged on the plot)")
        return
    found = _movement_by_id(st, d['mid'])
    if found is None:
        _redraw(self)
        return
    e, mv, k = found
    if (d['ia'], d['ib']) == (d['ia0'], d['ib0']):
        _set_summary(self, f"Movement {k + 1} of {e.curve.name}: not moved (back where it was).")
        return
    tt = d['tt']
    try:
        ia, ib = _movement_span_idx(st, e, mv, k, float(tt[d['ia']]), float(tt[d['ib']]))
    except ValueError as err:
        _redraw(self)
        _set_summary(self, f"Movement {k + 1} of {e.curve.name}: {err} – not changed.")
        return
    what = {'start': 'start dragged', 'stop': 'stop dragged'}.get(d['kind'], 'moved on the plot')
    # a dragged edge: the other one keeps its recorded time; a whole segment moved: both snap
    _commit_movement(self, e, mv, k, ia, ib, what, d['kind'] if d['kind'] in ('start', 'stop') else None)


def _drag_message(self, d):
    """Where the dragged item is now, in the toolbar's coordinate label (instead of the mouse
    position: the item snaps to samples)."""
    tb = getattr(self, 'logs_toolbar', None)
    if tb is None:
        return
    tt = d['tt']
    if d['kind'] == 'point':
        msg = f"point: t = {float(tt[d['i']]):.3f} s, value = {float(d['vv'][d['i']]):.4f}"
    else:
        a, b = float(tt[d['ia']]), float(tt[d['ib']])
        msg = f"movement: {a:.3f} – {b:.3f} s ({b - a:.3f} s)"
        if d.get('stuck'):
            msg += (" · it stays: no position with the same width on the curve's samples there, or a neighbouring "
                    "movement")
    try:
        tb.set_message(msg)
    except Exception:
        pass


def _drag_hover(self, event):
    """Cursor over a draggable item: horizontal-move over a marker / lane edge, move over a lane
    segment, the normal cursor elsewhere (pixel hit test only, no redraw)."""
    st = _state(self)
    kind = None
    try:
        if _drag_allowed(self, event):
            tgt = _drag_target(self, event)
            if tgt is not None:
                kind = 'move' if tgt['kind'] == 'move' else 'h'
    except Exception:
        kind = None
    if kind == st.hover_cursor:
        return
    st.hover_cursor = kind
    try:
        if kind == 'h':
            self.logs_canvas.set_cursor(Cursors.RESIZE_HORIZONTAL)
        elif kind == 'move':
            self.logs_canvas.set_cursor(Cursors.MOVE)
        elif not _toolbar_busy(self):
            self.logs_canvas.set_cursor(Cursors.POINTER)
    except Exception:
        pass


def _on_canvas_motion(self, event):
    st = _state(self)
    d = st.drag
    try:
        if d is None:
            _drag_hover(self, event)
            return
        if getattr(event, 'guiEvent', None) is not None and MouseButton.LEFT not in (event.buttons or ()):
            _drag_cancel(self)          # the left button is up but the release never came: nothing changes
            return
        if event.x is None or event.y is None:
            return
        if not d['started']:
            if math.hypot(event.x - d['press'][0], event.y - d['press'][1]) < _DRAG_MIN_PX * _dpr(self):
                return
            d['started'] = True
        if _drag_move(self, d, event) or d.get('bg') is None:
            _drag_blit(self, d)
        _drag_message(self, d)
    except Exception:
        traceback.print_exc()
        _drag_end(self)
        try:
            _redraw(self)
        except Exception:
            pass


def _on_canvas_release(self, event):
    st = _state(self)
    d = st.drag
    if d is None or getattr(event, 'button', None) != 1:
        return
    try:
        if d['started'] and event.x is not None and event.y is not None:
            _drag_move(self, d, event)
    except Exception:
        traceback.print_exc()
    _drag_end(self)
    if not d['started']:
        _drag_click(self, d)            # a click (moved < _DRAG_MIN_PX): nothing is dragged
        return
    try:
        _drag_commit(self, d)
    except Exception as e:
        traceback.print_exc()
        _warn(self, "Reference points" if d['kind'] == 'point' else "Movements", e)
        try:
            _redraw(self)
        except Exception:
            pass


def _drag_click(self, d):
    """A press on a draggable item released without moving: nothing is dragged.  In pick mode
    'points' it is a click like any other and adds a point on the nearest visible sample (another
    curve's marker or a lane may lie under the mouse, e.g. curves aligned within a few pixels), unless
    that sample is the pressed point's own (a duplicate): then the status line says how to add one
    next to it."""
    try:
        st = _state(self)
        if st.pick_mode != 'points' or _toolbar_busy(self):
            return
        xd, yd = d.get('press_data') or (None, None)
        if xd is None or yd is None:
            return
        if d['kind'] == 'point' and not (st.analysis_axis and st.analysis_axis not in st.enabled_axes):
            p = next((q for q in st.points if q.get('id') == d['pid']), None)
            best = _snap(self, *d['press'])
            if p is not None and best is not None:
                e = st.entries[best[1]]
                if e.uid == p['uid'] and p['axis'] == st.analysis_axis \
                        and _nearest_idx(_vc(st, e).times(), best[2]) == d['i0']:
                    _set_summary(self, f"Point {st.points.index(p) + 1} is here: drag it to move it; zoom in to "
                                       f"add another point next to it.")
                    return
        _points_click(self, xd, yd)
    except Exception as e:
        traceback.print_exc()
        _warn(self, "Reference points", e)


def _on_canvas_key(self, event):
    if getattr(event, 'key', None) == 'escape' and _state(self).drag is not None:
        _drag_cancel(self)


def _on_canvas_draw(self, event):
    """A full draw while dragging (not the background capture itself): the captured background may
    be stale (resize, an idle draw); it is captured again at the next mouse move."""
    d = _state(self).drag
    if d is not None and d.get('started') and not d.get('capturing'):
        d['bg'] = None


# ----------------------------------------------------------------------------
# Actions: alignment / pauses
# ----------------------------------------------------------------------------
@_action("Reference curve")
def logs_set_reference(self, index):
    st = _state(self)
    e = _entry_at(st, index)
    st.ref_uid = e.uid
    if _built(self):
        combo = self.logs_ref_combo                # may run inside the combo's own signal: no rebuild
        i = combo.findData(e.uid)
        if i < 0 or combo.count() != len(st.entries):
            _refresh_ref_combo(self)
        elif combo.currentIndex() != i:
            combo.blockSignals(True)
            combo.setCurrentIndex(i)
            combo.blockSignals(False)
        _ref_combo_tip(self)
    _apply_pause_lengths(self)
    if _built(self):
        _refresh_curves_table(self)
        _refresh_pause_controls(self)
        _refresh_pause_table(self, rebuild=True)
        _refresh_points_table(self)
    _refresh_live_notes(self)           # Show mode: the notes name the G-code pause lengths of the reference
    _redraw(self)
    return e.curve.name


def _max_lag(self, max_lag):
    if max_lag is not None:
        return float(max_lag)
    w = getattr(self, 'logs_spin_maxlag', None)
    return float(w.value()) if w is not None else 5.0


@_action("Auto-align", busy=True)
def logs_auto_align(self, all_curves=False, index=None, max_lag=None):
    """Align curves in time to the reference curve on the analysis axis inside the ROI
    (estimate_shift): all visible curves, or one curve (index None = selected).  Returns the
    list of result dicts (curve, shift, corr ...)."""
    st = _state(self)
    axis = _require_axis(st)
    ref = _ref_entry(st)
    if ref is None:
        raise ValueError("Choose a reference curve (section 4)")
    if not ref.curve.has(axis):
        raise ValueError(f"The reference '{ref.curve.name}' has no {axis}")
    lag = _max_lag(self, max_lag)
    if all_curves:
        targets = [e for e in _visible(st, axis) if e is not ref]
        if not targets:
            raise ValueError(f"No other visible curve with {axis} to align")
    else:
        e = _entry_at(st, index)
        if e is ref:
            raise ValueError("The selected curve is the reference: select another curve")
        if not e.curve.has(axis):
            raise ValueError(f"{e.curve.name} has no {axis}")
        targets = [e]
    rows, out = [], []
    n_ok = 0
    rc = _vc(st, ref)
    for e in targets:
        res = la.estimate_shift(rc, _vc(st, e), axis, roi=st.roi, max_lag=lag)
        s = res['shift']
        note = ''
        if np.isfinite(s):
            e.curve.time_offset += float(s)
            n_ok += 1
            if res.get('at_limit'):
                note = 'at max lag: increase max lag'
        else:
            note = 'no shift found (flat signal or no overlap)'
        rows.append([e.curve.name, axis, s, e.curve.time_offset, res['corr'], int(res['n']), note])
        out.append({'curve': e.curve.name, 'shift': float(s), 'corr': float(res['corr']),
                    'time_offset': float(e.curve.time_offset), 'at_limit': bool(res.get('at_limit'))})
    _sync_offset_spins(self)
    _set_results(self, 'Alignment', ['Curve', 'Axis', 'Shift (s)', 'New time offset (s)', 'Corr', 'N', 'Note'],
                 rows, ref_uid=ref.uid, uids=[ref.uid] + [e.uid for e in targets])
    _after_offsets_changed(self)
    _set_summary(self, f"Auto-aligned {n_ok} of {len(targets)} curve(s) to '{ref.curve.name}' on {axis}"
                       f"{_roi_txt(st)}, max lag {lag:g} s")
    return out


@_action("Offsets")
def logs_reset_offsets(self):
    st = _state(self)
    for e in st.entries:
        e.curve.time_offset = 0.0
        e.curve.value_offsets = {}
    _sync_offset_spins(self)
    _after_offsets_changed(self)
    _set_summary(self, "All time and value offsets reset to 0.")


def _ref_durs(meta):
    """Pause lengths of a reference's meta, padded to its pauses (a hashable tuple)."""
    n = len(meta.get('pauses_gcode') or meta.get('pauses') or [])
    d = [float(x) for x in (meta.get('pause_durations') or [])][:n]
    return tuple(d + [0.0] * (n - len(d)))


def _ref_canon(t, meta):
    """A time of a G-code reference (its own time base, pause lengths meta['pause_durations']) in a
    form that does not depend on the pause lengths: ('pause', i, phase) for a time in the hold of
    pause i (its start included, phase = time into the hold), else ('free', n, g) with n = pauses
    before it and g its time with those pauses at length 0."""
    pg = [float(tp) for _, tp in (meta.get('pauses_gcode') or [])]
    d = _ref_durs(meta)
    t = float(t)
    acc = 0.0
    for i, tp in enumerate(pg):
        s = tp + acc
        if t < s - 1e-9:
            return ('free', i, t - acc)
        if t <= s + d[i] + 1e-9:
            return ('pause', i, min(max(t - s, 0.0), d[i]))
        acc += d[i]
    return ('free', len(pg), t - acc)


def _ref_from_canon(cn, meta):
    """_ref_canon back to a time of the reference with the pause lengths of meta (a phase longer
    than the new pause ends at the pause's end)."""
    pg = [float(tp) for _, tp in (meta.get('pauses_gcode') or [])]
    d = _ref_durs(meta)
    kind, i, x = cn
    if kind == 'pause' and 0 <= i < len(pg):
        return pg[i] + sum(d[:i]) + min(x, d[i])
    return x + sum(d[:min(int(i), len(d))])


def _ref_remap_times(store, key, times, meta_old, meta_new):
    """Times of one overlay on a reference (tuple) mapped from pause lengths meta_old to meta_new,
    exactly reversible: store (the overlay's '_rc' dict) keeps its pause-independent form ('canon')
    and the times it had under each set of pause lengths ('at'), so a change back gives the very
    same numbers.  A stale store (the overlay was edited since) is rebuilt from the current times."""
    d_old, d_new = _ref_durs(meta_old), _ref_durs(meta_new)
    rc = store.get(key)
    if not isinstance(rc, dict) or rc.get('at', {}).get(d_old) != tuple(times):
        rc = {'canon': tuple(_ref_canon(t, meta_old) for t in times), 'at': {d_old: tuple(times)}}
    new = rc['at'].get(d_new)
    if new is None:
        new = tuple(float(_ref_from_canon(cn, meta_new)) for cn in rc['canon'])
        rc['at'][d_new] = new
    store[key] = rc
    return new


def _remap_ref_time(t, meta_old, meta_new):
    """Times on a reference rebuilt with new pause lengths (own time base, no offset): the same G-code
    motion (_ref_canon; a time inside a pause keeps its time into the hold, up to the new length)."""
    t = np.asarray(t, dtype=float)
    return np.array([_ref_from_canon(_ref_canon(x, meta_old), meta_new) for x in t.ravel()],
                    dtype=float).reshape(t.shape)


def _remap_reference_overlays(st, ref, meta_old, meta_new):
    """Keep the points, peaks and movements of a reference on the same G-code motion when its pause
    lengths change (pause mode, pause source): their times are remapped through the pause-independent
    form (_ref_remap_times), so changing back restores them exactly; the movements keep their ids,
    edited / gap flags and (per view, _stats_for_view) their numbers."""
    for p in st.points:
        if p['uid'] == ref.uid:
            p.setdefault('_rc', {})
            p['t_raw'] = _ref_remap_times(p['_rc'], 't', (float(p['t_raw']),), meta_old, meta_new)[0]
    pk = st.peaks.get(ref.uid)
    if pk is not None:
        pk.setdefault('_rc', {})
        t = tuple(float(x) for x in np.asarray(pk['t_raw'], dtype=float).ravel())
        pk['t_raw'] = np.asarray(_ref_remap_times(pk['_rc'], 't', t, meta_old, meta_new), dtype=float)
    mv = st.movements.get(ref.uid)
    if mv:
        _mv_norm(st, mv)
        store = mv.setdefault('_rc', {})
        segs = []
        for mid, (a, b) in zip(mv['ids'], mv['segments']):
            na, nb = _ref_remap_times(store, mid, (float(a), float(b)), meta_old, meta_new)
            segs.append((na, nb))
        mv['segments'] = segs


def _mv_params(self, threshold=None, settle_time=None, min_duration=None, merge_gap=None):
    def val(x, wname, default):
        if x is not None:
            return float(x)
        w = getattr(self, wname, None)
        return float(w.value()) if w is not None else default
    return (val(threshold, 'logs_spin_mv_thr', 0.02), val(settle_time, 'logs_spin_mv_settle', 0.5),
            val(min_duration, 'logs_spin_mv_mindur', 0.0), val(merge_gap, 'logs_spin_mv_merge', 0.0))


def _pause_summary(st):
    """Short status text of the G-code pause lengths in the current mode."""
    if st.pause_mode == 'remove':
        cut = [e.curve.name for e in st.entries if e.visible and _cut_active(st, e)]
        return (f"logged waits removed from {len(cut)} log(s), G-code pauses with length 0" if cut else
                "no logged waits to remove: logs and G-code as recorded")
    src = _pause_source(st)
    if src is None:
        return "no logged waits: G-code pauses shown with length 0"
    marked = [p for p in st.pause_info if p['kind'] == 'marked']
    if marked:
        return (f"pause lengths from the logged waits of '{src.curve.name}': "
                + ", ".join(f"{p['label']} {p['length']:.2f} s" for p in marked))
    note = next((p['note'] for p in st.pause_info if p['label'] == la.SENSOR_WAIT_LABEL), '')
    return f"'{src.curve.name}': {note or 'no pause paired'}"


def _after_pause_change(self, msg=None):
    """Widgets, results and plot after the pause mode / source changed (overlays stay in recorded time;
    the ROI keeps its numbers in plot time)."""
    _apply_pause_lengths(self)
    if _built(self):
        _refresh_pause_controls(self)
        _refresh_pause_table(self, rebuild=True)
        _refresh_curves_table(self)
        _refresh_points_table(self)
        _sync_roi_widgets(self)
    _rebuild_movements_view(self)
    _refresh_peak_list(self)            # the peaks drawn, in the new time base
    _refresh_live_notes(self)           # (rows unchanged without waits); Compare / ... of another time base: marked
    _redraw(self, rescale=True)
    if msg:
        _set_summary(self, msg)


@_action("Pauses")
def logs_set_pause_mode(self, mode):
    """'show': logs as recorded, each logged sensor wait drawn and the G-code's sensor_wait pauses as
    long as the source log's waits; 'remove': every log shown without its logged waits (la.remove_waits)
    and the G-code pauses with length 0, so logs and G-code share G-code time.  Points, movements and
    peaks stay stored in recorded time.  Returns the mode."""
    st = _state(self)
    m = str(mode).strip().lower() if mode is not None else ''
    m = {'real time': 'show', 'show (real time)': 'show', 'remove logged waits': 'remove'}.get(m, m)
    if m not in ('show', 'remove'):
        raise ValueError("mode must be 'show' or 'remove'")
    changed = m != st.pause_mode
    st.pause_mode = m
    if not changed:
        _refresh_pause_controls(self)
        return m
    roi = f" The ROI keeps its numbers ({st.roi[0]:.3f}–{st.roi[1]:.3f} s, plot time)." if st.roi else ""
    _after_pause_change(self, None)
    if m == 'show':
        msg = f"Pauses: shown in real time · {_pause_summary(st)}.{roi}"
    else:
        msg = f"Pauses: logged waits removed · {_pause_summary(st)}.{roi}"
    _set_summary(self, msg)
    return m


@_action("Pauses")
def logs_set_pause_source(self, index_or_None):
    """The log (curves-table index) whose logged waits give the lengths of the G-code's sensor_wait
    pauses in Show mode; None = the first log with logged waits.  Refused for a curve without logged
    waits.  Returns the name of the source log (None when no log has waits)."""
    st = _state(self)
    if index_or_None is None:
        st.pause_source_uid = None
    else:
        e = _entry_at(st, index_or_None)
        if not _has_waits(e.curve):
            raise ValueError(f"{e.curve.name} has no logged sensor waits (no -1000 rows / wait notes): "
                             f"choose a log with logged waits")
        st.pause_source_uid = e.uid
    _after_pause_change(self, None)
    src = _pause_source(st)
    _set_summary(self, f"Pause lengths: {_pause_summary(st)}")
    return src.curve.name if src is not None else None


# ----------------------------------------------------------------------------
# Actions: compare / peaks / movements
# ----------------------------------------------------------------------------
@_action("Compare", busy=True)
def logs_compare(self):
    """Statistics of (curve - reference) for every visible curve on the analysis axis in the ROI.
    Returns the list of row dicts."""
    st = _state(self)
    axis = _require_axis(st)
    ref = _ref_entry(st)
    if ref is None:
        raise ValueError("Choose a reference curve (section 4)")
    if not ref.curve.has(axis):
        raise ValueError(f"The reference '{ref.curve.name}' has no {axis}")
    targets = [e for e in _visible(st, axis) if e is not ref]
    if not targets:
        raise ValueError(f"No other visible curve with {axis} to compare")
    lag = _max_lag(self, None)
    u = _axis_unit(st, axis)
    headers = ['Curve', 'Axis', 'Shift to align (s)', f'Mean diff ({u})', f'STD ({u})', f'RMS ({u})',
               f'Max |diff| ({u})', f'P95 |diff| ({u})', 'Corr', 'N']
    rows, out = [], []
    rc = _vc(st, ref)
    for e in targets:
        ec = _vc(st, e)
        s = la.estimate_shift(rc, ec, axis, roi=st.roi, max_lag=lag)
        r = la.compare(rc, ec, axis, roi=st.roi)
        rows.append([e.curve.name, axis, s['shift'], r['mean'], r['std'], r['rms'], r['max_abs'], r['p95_abs'],
                     r['corr'], int(r['n'])])
        out.append({'curve': e.curve.name, 'shift': s['shift'], 'mean': r['mean'], 'std': r['std'],
                    'rms': r['rms'], 'max_abs': r['max_abs'], 'p95_abs': r['p95_abs'], 'corr': r['corr'],
                    'n': int(r['n'])})
    _set_results(self, 'Compare', headers, rows, ref_uid=ref.uid, uids=[ref.uid] + [e.uid for e in targets])
    _redraw(self)
    _set_summary(self, f"Compare to '{ref.curve.name}' on {axis}{_roi_txt(st)}: {len(rows)} curve(s) · "
                       + _ensemble_summary(st, with_roi=False))
    return out


@_action("Peaks", busy=True)
def logs_find_peaks(self, prominence=None, min_distance=None, kind=None):
    """Peaks of every visible curve on the analysis axis in the ROI (prominence 0/None = auto,
    kind 'max' | 'min' | 'both').  Returns {curve name: dict(t, v, kind)}."""
    st = _state(self)
    axis = _require_axis(st)
    if prominence is None:
        w = getattr(self, 'logs_spin_prom', None)
        prominence = w.value() if w is not None else 0.0
    prom = float(prominence) if prominence and float(prominence) > 0 else None
    if min_distance is None:
        w = getattr(self, 'logs_spin_peakdist', None)
        min_distance = w.value() if w is not None else 0.5
    if kind is None:
        w = getattr(self, 'logs_combo_peakkind', None)
        kind = w.currentData() if w is not None else 'max'
    kind = {'maxima': 'max', 'minima': 'min'}.get(str(kind).lower(), str(kind).lower())
    targets = _visible(st, axis)
    if not targets:
        raise ValueError(f"No visible curve with {axis}")
    u = _axis_unit(st, axis)
    rows, out = [], {}
    total = 0
    st.peaks = {}
    for e in targets:
        c = _vc(st, e)
        pk = la.find_peaks_curve(c, axis, roi=st.roi, prominence=prom, min_distance_s=float(min_distance),
                                 kind=kind)
        kinds = list(pk['kind'])
        # stored in recorded time (_d2r: as before t - offset when nothing is cut)
        st.peaks[e.uid] = {'axis': axis, 't_raw': np.asarray(_d2r(st, e, np.asarray(pk['t'], dtype=float))),
                           'v_raw': pk['v'] - _vof(c, axis), 'kind': kinds}
        out[c.name] = pk
        total += len(kinds)
        karr = np.asarray(kinds)
        main = 'min' if kind == 'min' or (kind == 'both' and not np.any(karr == 'max')) else 'max'
        ps = la.period_stats(pk['t'][karr == main] if karr.size else [])
        dp = la.dominant_period(c, axis, roi=st.roi)
        rows.append([c.name, axis, len(kinds), int(ps['n']), ps['mean'], ps['std'], ps['min'], ps['max'],
                     ps['freq'], dp['period'], dp['freq'], dp['strength']])
    # the list is built from st.peaks (as after a pause-mode / offset change): it lists the peaks drawn
    hdrs, plist = _peak_list_rows(st)
    _set_results(self, 'Peak list', hdrs, plist, show=False)
    _set_results(self, 'Peaks & periods', ['Curve', 'Axis', 'Peaks', 'Periods', 'Period mean (s)', 'Period STD (s)',
                                           'Period min (s)', 'Period max (s)', 'Freq (Hz)', 'Dominant period (s)',
                                           'Dominant freq (Hz)', 'ACF strength'], rows,
                 uids=[e.uid for e in targets])
    _redraw(self)
    _set_summary(self, f"Peaks on {axis}{_roi_txt(st)}: {total} in {len(targets)} curve(s) "
                       f"(prominence {'auto' if prom is None else f'{prom:g} {u}'}, min distance {float(min_distance):g} s)")
    return out


@_action("Peaks")
def logs_clear_peaks(self):
    _state(self).peaks = {}
    _refresh_peak_list(self)            # the list of the peaks drawn: dropped
    _redraw(self)


@_action("Movements", busy=True)
def logs_detect_movements(self, threshold=None, settle_time=None, min_duration=None, merge_gap=None):
    """Movements (start, stop, duration ...) of every visible curve on the analysis axis in the ROI.
    Returns {curve name: list of movement dicts}."""
    st = _state(self)
    axis = _require_axis(st)
    thr, settle, mind, merge = _mv_params(self, threshold, settle_time, min_duration, merge_gap)
    targets = _visible(st, axis)
    if not targets:
        raise ValueError(f"No visible curve with {axis}")
    u = _axis_unit(st, axis)
    rows, out, counts = [], {}, []
    # every movement is replaced, also those edited by hand (said in the summary)
    n_edited = sum(1 for m_ in st.movements.values() if m_ for x in (m_.get('edited') or []) if x)
    st.movements = {}
    for e in targets:
        c = _vc(st, e)
        mv = la.detect_movements(c, axis, roi=st.roi, threshold=thr, settle_time=settle, min_duration=mind,
                                 merge_gap=merge)
        off = c.time_offset
        view = _view_key(st, e)
        # gap flags of the core: 'in_gap' (overlaps / touches a connection gap), 'start_in_gap' /
        # 'stop_in_gap' (newer cores: that time lies in a gap); every key is optional
        flags = [_gap_flags(m) for m in mv]
        # segments in recorded time: t - offset (nothing cut), else the recorded time of the sample
        if c is e.curve:
            segs = [(m['t_start'] - off, m['t_stop'] - off) for m in mv]
        else:
            ra = _raw_of_disp_samples(st, e, c, [m['t_start'] for m in mv])
            rb = _raw_of_disp_samples(st, e, c, [m['t_stop'] for m in mv])
            segs = [(float(a), float(b)) for a, b in zip(ra, rb)]
        st.movements[e.uid] = {'axis': axis, 'segments': segs,
                               'in_gap': [f[0] for f in flags],
                               'complete': [bool(m.get('complete', True)) for m in mv],
                               'start_in_gap': [f[1] for f in flags], 'stop_in_gap': [f[2] for f in flags],
                               'edited': [False] * len(mv), 'ids': [_new_movement_id(st) for _ in mv],
                               'stats': [_detected_stats(m, f, c, axis, view) for m, f in zip(mv, flags)]}
        out[c.name] = mv
        counts.append(f"{c.name} {len(mv)}")
        for i, (m, (in_gap, s_gap, e_gap)) in enumerate(zip(mv, flags)):
            complete = bool(m.get('complete', True))
            rows.append([c.name, axis, i + 1, m['t_start'], m['t_stop'], m['duration'], m['v_start'], m['v_stop'],
                         m['delta'], m['peak_speed'], complete, in_gap,
                         _movement_note(complete, in_gap, start_in_gap=s_gap, stop_in_gap=e_gap)])
    _set_results(self, 'Movements', _movement_headers(u), rows)
    _redraw(self, refit_y=True)
    full = [r[5] for r in rows if r[10] and not r[11]]
    n_gap = sum(1 for r in rows if r[11])
    n_inc = sum(1 for r in rows if not r[10] and not r[11])
    extra = []
    if n_gap:
        extra.append(f"{n_gap} span a connection gap")
    if n_inc:
        extra.append(f"{n_inc} incomplete")
    _set_summary(self, f"Movements on {axis}{_roi_txt(st)} (threshold {thr:g} {u}, settle {settle:g} s): "
                       + ", ".join(counts)
                       + (f" · mean duration {np.mean(full):.3f} s" + (" (complete ones)" if extra else "")
                          if full else "")
                       + (f" · {', '.join(extra)}" if extra else "")
                       + (f" · {n_edited} movement(s) edited by hand were replaced" if n_edited else ""))
    return out


def _gap_flags(m):
    """(in_gap, start_in_gap, stop_in_gap) of a movement dict; missing keys are False, and a start /
    stop in a gap also counts as in_gap."""
    s_gap = bool(m.get('start_in_gap', False))
    e_gap = bool(m.get('stop_in_gap', False))
    return bool(m.get('in_gap', False)) or s_gap or e_gap, s_gap, e_gap


def _movement_note(complete, in_gap, start_in_gap=False, stop_in_gap=False):
    if start_in_gap and stop_in_gap:
        return "starts and stops in connection gaps: start and stop uncertain"
    if start_in_gap:
        return "starts in a connection gap: start uncertain" + ("" if complete else ", incomplete")
    if stop_in_gap:
        return "stops in a connection gap: stop uncertain" + ("" if complete else ", incomplete")
    if in_gap:
        return "spans connection gap: incomplete" if not complete else "spans connection gap"
    if not complete:
        return "incomplete: data or ROI ends before the stop"
    return ""


@_action("Movements")
def logs_clear_movements(self):
    _state(self).movements = {}
    _rebuild_movements_view(self)           # the 'Movements' view (and its export) goes with them
    _redraw(self, refit_y=True)


def _nearest_idx(tt, t):
    """Index of the sample of the increasing times tt nearest to t (a tie goes to the earlier one,
    as la.nearest_point)."""
    n = int(tt.size)
    i = int(np.searchsorted(tt, float(t)))
    if i >= n:
        return n - 1
    if i > 0 and abs(float(t) - tt[i - 1]) <= abs(tt[i] - float(t)):
        return i - 1
    return i


def _parse_float(text):
    """A number typed in a table cell, locale-independent as the rest of the tab (C locale spin
    boxes; '.' or ',' as the decimal point, as the platform dimension fields).  ValueError when it is
    not a finite number."""
    if isinstance(text, (int, float, np.integer, np.floating)) and not isinstance(text, (bool, np.bool_)):
        x = float(text)
    else:
        s = str('' if text is None else text).strip().replace('−', '-').replace(',', '.')
        try:
            x = float(s)
        except ValueError:
            raise ValueError(f"'{text}' is not a number") from None
    if not math.isfinite(x):
        raise ValueError(f"'{text}' is not a finite number")
    return x


def _movement_at(st, index):
    """(entry, movement dict, k) of movement `index` (0-based, movements table order)."""
    items = _movement_items(st)
    if not items:
        raise ValueError("No movements: detect them first (section 7)")
    try:
        i = int(index)
    except (TypeError, ValueError):
        raise ValueError("Select a movement in the movements table first") from None
    if not 0 <= i < len(items):
        raise ValueError(f"No movement {i + 1} (there are {len(items)})")
    return items[i]


def _movement_span_idx(st, e, mv, k, t_start=None, t_stop=None):
    """Sample indices (start, stop) of movement k of entry e with a new start and / or stop (s,
    displayed time base; None = unchanged), each snapped to the nearest sample of the shown curve
    (_vc: in Remove mode the curve without its waits).
    ValueError (nothing changed) when a time is outside the curve's data (by more than one sample
    interval), the stop is not at least one sample after the start, or the movement would overlap
    the curve's previous / next movement (touching is allowed, as detected movements do)."""
    c = _vc(st, e)
    tt = c.times()
    if tt.size < 2:
        raise ValueError(f"{c.name} has fewer than 2 samples")
    segs = mv['segments']
    a = _r2d(st, e, float(segs[k][0])) if t_start is None else _parse_float(t_start)
    b = _r2d(st, e, float(segs[k][1])) if t_stop is None else _parse_float(t_stop)
    tol = max(float(np.median(np.diff(tt))), 1e-6)
    for x, what in ((a, 'start'), (b, 'stop')):
        if x < tt[0] - tol or x > tt[-1] + tol:
            raise ValueError(f"the {what} {x:.3f} s is outside the data of {c.name} ({tt[0]:.3f}–{tt[-1]:.3f} s)")
    ia, ib = _nearest_idx(tt, a), _nearest_idx(tt, b)
    if ib <= ia:
        raise ValueError(f"the start ({tt[ia]:.3f} s) must be at least one sample before the stop ({tt[ib]:.3f} s)")
    if k > 0:
        prev = _r2d(st, e, float(segs[k - 1][1]))
        if tt[ia] < prev - 1e-9:
            raise ValueError(f"it would overlap movement {k} of {c.name} (which stops at {prev:.3f} s)")
    if k + 1 < len(segs):
        nxt = _r2d(st, e, float(segs[k + 1][0]))
        if tt[ib] > nxt + 1e-9:
            raise ValueError(f"it would overlap movement {k + 2} of {c.name} (which starts at {nxt:.3f} s)")
    return ia, ib


def _movement_cur_idx(st, e, mv, k):
    """Sample indices (start, stop) movement k of entry e is on now (nearest samples of the shown
    curve, as a drag sees it)."""
    tt = _vc(st, e).times()
    a, b = mv['segments'][k]
    return _nearest_idx(tt, _r2d(st, e, float(a))), _nearest_idx(tt, _r2d(st, e, float(b)))


def _unchanged_msg(st, e, k, ia, ib, what=None):
    """Status line of an edit that snaps back to the samples the movement is on (what: 'start' /
    'stop' typed, None = both)."""
    tt = _vc(st, e).times()
    if what in ('start', 'stop'):
        where = f"the {what} snaps to the sample it is on ({float(tt[ia if what == 'start' else ib]):.3f} s)"
    else:
        where = f"it is on these samples already ({float(tt[ia]):.3f}–{float(tt[ib]):.3f} s)"
    return f"Movement {k + 1} of {e.curve.name}: unchanged – {where}"


def _edited_edge(t_start, t_stop):
    """Which edge of a movement an edit sets: 'start' / 'stop' when only that one is given, None for
    both (the other one keeps its recorded time, see _store_movement)."""
    if (t_start is None) == (t_stop is None):
        return None
    return 'stop' if t_start is None else 'start'


def _store_movement(st, e, mv, k, ia, ib, edge=None):
    """Movement k of entry e set to the samples ia..ib of the shown curve: segment in recorded time,
    edited, numbers (la.movement_stats on the shown curve) and flags.  edge 'start' / 'stop': only that
    edge was typed / dragged, the other one keeps its stored recorded time exactly (in Remove mode an
    edge inside a removed wait is shown at the cut point: snapping it to a shown sample would move it
    in recorded time); its numbers use where it is shown."""
    c = _vc(st, e)
    segs = list(mv['segments'])
    old0, old1 = float(segs[k][0]), float(segs[k][1])
    t0 = old0 if edge == 'stop' else _raw_of(st, e, c, ia)
    t1 = old1 if edge == 'start' else _raw_of(st, e, c, ib)
    x0 = _r2d(st, e, t0) if edge == 'stop' else float(c.t[ia]) + c.time_offset
    x1 = _r2d(st, e, t1) if edge == 'start' else float(c.t[ib]) + c.time_offset
    s = _mv_stats(c, mv['axis'], x0, x1, view=_view_key(st, e))
    segs[k] = (t0, t1)
    mv['segments'] = segs
    mv['stats'][k] = s
    mv['edited'][k] = True
    for key in ('complete', 'in_gap', 'start_in_gap', 'stop_in_gap'):
        mv[key][k] = bool(s[key])
    return s


def _movement_msg(st, e, mv, k, what):
    d = _movement_values(st, e, mv, k)
    u = _curve_unit(e.curve, mv['axis'])
    return (f"Movement {k + 1} of {e.curve.name} ({mv['axis']}) {what}: {d['t_start']:.3f}–{d['t_stop']:.3f} s "
            f"({d['duration']:.3f} s), delta {d['delta']:+.4f} {u}, peak speed {d['peak_speed']:.4f} {u}/s · "
            f"{d['note']}")


def _commit_movement(self, e, mv, k, ia, ib, what, edge=None):
    """Store an edited movement (edge: see _store_movement), then the 'Movements' view, the lanes and
    the movements table (one redraw at the current zoom) and the status line.  Returns its values."""
    st = _state(self)
    _store_movement(st, e, mv, k, ia, ib, edge)
    _rebuild_movements_view(self)
    _redraw(self)
    _set_summary(self, _movement_msg(st, e, mv, k, what))
    return _movement_values(st, e, mv, k)


def logs_movement_list(self):
    """The movements in table order (curves table order, then start), times in the displayed time
    base: [dict(id, curve, uid, axis, number, t_start, t_stop, duration, v_start, v_stop, delta,
    peak_speed, complete, in_gap, start_in_gap, stop_in_gap, edited, note)]."""
    st = _state(self)
    out = []
    for e, mv, k in _movement_items(st):
        d = _movement_values(st, e, mv, k)
        d.update(curve=e.curve.name, uid=e.uid)
        out.append(d)
    return out


@_action("Movements")
def logs_set_movement(self, index, t_start=None, t_stop=None):
    """New start and / or stop (s, displayed time base; None = unchanged) of movement `index`
    (0-based, movements table order), snapped to the nearest samples of its curve.  Refused (warning,
    nothing changed) when the start is not at least one sample before the stop, a time is outside
    the curve's data or the movement would overlap the curve's other movements.  The movement is
    marked edited and its numbers come from la.movement_stats.  Returns its values (dict)."""
    st = _state(self)
    e, mv, k = _movement_at(st, index)
    ia, ib = _movement_span_idx(st, e, mv, k, t_start, t_stop)
    edge = _edited_edge(t_start, t_stop)
    if (ia, ib) == _movement_cur_idx(st, e, mv, k):
        # the same samples: nothing is stored (not marked edited, its flags / numbers stay)
        _set_summary(self, _unchanged_msg(st, e, k, ia, ib, edge))
        return _movement_values(st, e, mv, k)
    return _commit_movement(self, e, mv, k, ia, ib, 'set', edge)


@_action("Movements")
def logs_delete_movements(self, indices):
    """Delete movements by 0-based index (movements table order).  Returns the number deleted."""
    st = _state(self)
    if isinstance(indices, (int, np.integer)):
        indices = [indices]
    items = _movement_items(st)
    idx = sorted({int(i) for i in indices if 0 <= int(i) < len(items)})
    if not idx:
        raise ValueError("Select movement(s) in the movements table first")
    groups = {}
    for i in idx:
        e, mv, k = items[i]
        groups.setdefault(e.uid, (mv, []))[1].append(k)
    for mv, ks in groups.values():
        for key in _MV_LIST_KEYS:
            mv[key] = [x for j, x in enumerate(mv[key]) if j not in ks]
    _rebuild_movements_view(self)
    _redraw(self)
    names = [_entry_by_uid(st, uid).curve.name for uid in groups]
    _set_summary(self, f"Deleted {len(idx)} movement(s) of {', '.join(names)}")
    return len(idx)


def _add_roi_movement(st, e, axis):
    """Add a movement spanning the ROI (its samples inside it) to entry e on `axis`; returns its
    index k.  ValueError with the reason when it cannot be added."""
    c = _vc(st, e)
    tt = c.times()
    a, b = st.roi
    if tt.size < 2 or b < tt[0] or a > tt[-1]:
        raise ValueError("the ROI is outside its data")
    ia = int(np.searchsorted(tt, a - 1e-9, side='left'))
    ib = int(np.searchsorted(tt, b + 1e-9, side='right')) - 1
    if ib <= ia:
        raise ValueError("the ROI holds fewer than 2 of its samples")
    mv = st.movements.get(e.uid)
    if mv:
        n = _mv_norm(st, mv)
        if n and mv.get('axis') != axis:
            raise ValueError(f"its movements are on {mv.get('axis')}, not on {axis} (detect them again, or choose "
                             f"{mv.get('axis')} as analysis axis)")
    else:
        mv = {'segments': []}
        n = _mv_norm(st, mv)
        st.movements[e.uid] = mv
    mv['axis'] = axis
    t0, t1 = float(tt[ia]), float(tt[ib])
    for j, (sa, sb) in enumerate(mv['segments']):
        sa, sb = _r2d(st, e, float(sa)), _r2d(st, e, float(sb))
        if t0 < sb - 1e-9 and t1 > sa + 1e-9:
            raise ValueError(f"the ROI overlaps its movement {j + 1} ({sa:.3f}–{sb:.3f} s)")
    k = sum(1 for sa, _ in mv['segments'] if _r2d(st, e, float(sa)) < t0)
    for key in _MV_LIST_KEYS:
        mv[key] = list(mv[key])
    mv['segments'].insert(k, (_raw_of(st, e, c, ia), _raw_of(st, e, c, ib)))
    for key, default in _MV_DEFAULTS.items():
        mv[key].insert(k, default)
    mv['ids'].insert(k, _new_movement_id(st))
    _store_movement(st, e, mv, k, ia, ib)
    return k


@_action("Movements")
def logs_add_movement_from_roi(self, curve_index=None):
    """Add a movement spanning the ROI (from its first to its last sample inside the ROI) on the
    analysis axis: on curve `curve_index`, or None = the curve selected in the curves table, or on
    every visible curve with the analysis axis when none is selected.  Refused (warning) without a
    ROI, or when it would overlap a movement of that curve; with several curves the refused ones are
    listed in the status line.  Returns the number of movements added."""
    st = _state(self)
    if st.roi is None:
        raise ValueError("Set a region of interest first (section 3): the new movement spans the ROI")
    axis = _require_axis(st)
    if curve_index is None and 0 <= st.selected < len(st.entries):
        curve_index = st.selected
    if curve_index is not None:
        e = _entry_at(st, curve_index)
        if not e.curve.has(axis):
            raise ValueError(f"{e.curve.name} has no {axis}")
        targets = [e]
    else:
        targets = _visible(st, axis)
        if not targets:
            raise ValueError(f"No visible curve with {axis}")
    lanes0 = _n_lanes(st)
    added, refused = [], []
    for e in targets:
        try:
            added.append((e, _add_roi_movement(st, e, axis)))
        except ValueError as err:
            refused.append(f"{e.curve.name}: {err}")
    if not added:
        raise ValueError("No movement added: " + "; ".join(refused))
    _rebuild_movements_view(self)
    _redraw(self, refit_y=_n_lanes(st) > lanes0)
    if len(added) == 1:
        e, k = added[0]
        msg = _movement_msg(st, e, st.movements[e.uid], k, f"added from the ROI{_roi_txt(st)}")
    else:
        msg = f"Added {len(added)} movement(s) on {axis} from the ROI{_roi_txt(st)}"
    _set_summary(self, msg + (f" · not added: {'; '.join(refused)}" if refused else ""))
    return len(added)


# ----------------------------------------------------------------------------
# Actions: reference points
# ----------------------------------------------------------------------------
@_action("Reference points")
def logs_add_point(self, curve_index, t, axis=None):
    """Add a reference point on a curve at the sample nearest to t (displayed time base).
    Returns the point number (1-based)."""
    st = _state(self)
    e = _entry_at(st, curve_index)
    axis = axis or _require_axis(st)
    if not e.curve.has(axis):
        raise ValueError(f"{e.curve.name} has no {axis}")
    vc = _vc(st, e)
    ti, vi = la.nearest_point(vc, axis, float(t))
    _new_point(st, e.uid, axis, _point_raw(st, e, vc, ti))
    _refresh_points_table(self)
    _redraw(self)
    n = len(st.points)
    _set_summary(self, f"Point {n}: {e.curve.name} · {axis} at t = {ti:.3f} s, {vi:.4f} {_curve_unit(e.curve, axis)}"
                 + ("" if axis in st.enabled_axes else f" ({axis} is hidden on the plot)"))
    return n


def _point_raw(st, e, vc, t_disp):
    """Recorded time of a point put on the shown sample at displayed time t_disp: the recorded time
    of that row, exactly (not t - offset, which can land an ulp below the row: on the row that ended
    a wait that would read as inside the removed wait)."""
    return _raw_of(st, e, vc, _nearest_idx(vc.times(), float(t_disp)))


def _hidden_axis_msg(axis):
    return (f"Points are put on the analysis axis {axis}, which is hidden: tick {axis} under 'Show on plot' "
            f"(section 2) or choose a shown axis as analysis axis, then click again.")


def _snap(self, x_px, y_px):
    """(screen distance, entry index, sample time) of the visible curve sample nearest to a pixel."""
    st = _state(self)
    ax = self.logs_ax
    axis = st.analysis_axis
    inv = ax.transData.inverted()
    t_lo = inv.transform((x_px - 60.0, y_px))[0]
    t_hi = inv.transform((x_px + 60.0, y_px))[0]
    best = None
    for idx, e in enumerate(st.entries):
        if not e.visible or not axis or not e.curve.has(axis):
            continue
        vc = _vc(st, e)
        tt = vc.times()
        vv = vc.values(axis)
        n = tt.size
        if n == 0:
            continue
        i0 = max(0, int(np.searchsorted(tt, t_lo)) - 1)
        i1 = min(n, int(np.searchsorted(tt, t_hi)) + 1)
        if i1 <= i0:
            i0, i1 = max(0, n - 1), n
        pts = ax.transData.transform(np.column_stack([tt[i0:i1], vv[i0:i1]]))
        d = np.hypot(pts[:, 0] - x_px, pts[:, 1] - y_px)
        d = np.where(np.isfinite(d), d, np.inf)
        k = int(np.argmin(d))
        if np.isfinite(d[k]) and (best is None or d[k] < best[0]):
            best = (float(d[k]), idx, float(tt[i0 + k]))
    return best


@_action("Reference points")
def logs_pick_point(self, t, value):
    """Add a point as a click at (t, value) in data coordinates would: snapped to the nearest sample
    (screen distance) of the visible curves on the analysis axis.  Refused (warning, None) when the
    analysis axis is hidden on the plot.  Returns the point number."""
    st = _state(self)
    axis = _require_axis(st)
    if axis not in st.enabled_axes:
        msg = _hidden_axis_msg(axis)
        _set_summary(self, msg)
        raise ValueError(msg)
    x_px, y_px = self.logs_ax.transData.transform((float(t), float(value)))
    best = _snap(self, x_px, y_px)
    if best is None:
        raise ValueError(f"No visible curve with {axis} to put a point on")
    _, idx, ts = best
    e = st.entries[idx]
    vc = _vc(st, e)
    ti, vi = la.nearest_point(vc, axis, ts)
    _new_point(st, e.uid, axis, _point_raw(st, e, vc, ti))
    _refresh_points_table(self)
    _redraw(self)
    n = len(st.points)
    _set_summary(self, f"Point {n}: {e.curve.name} · {axis} at t = {ti:.3f} s, {vi:.4f} {_curve_unit(e.curve, axis)}")
    return n


@_action("Reference points")
def logs_delete_points(self, indices):
    """Delete points by 0-based index."""
    st = _state(self)
    if isinstance(indices, int):
        indices = [indices]
    idx = sorted({int(i) for i in indices if 0 <= int(i) < len(st.points)}, reverse=True)
    if not idx:
        raise ValueError("Select point(s) in the points table first")
    for i in idx:
        del st.points[i]
    _refresh_points_table(self)
    _redraw(self)
    return len(idx)


@_action("Reference points")
def logs_clear_points(self):
    _state(self).points = []
    tbl = getattr(self, 'logs_points_table', None)
    if tbl is not None:
        tbl.clearSelection()
    _refresh_points_table(self)
    _redraw(self)


def _point_at(st, index):
    """(index, point, entry) of reference point `index` (0-based)."""
    n = len(st.points)
    try:
        i = int(index)
    except (TypeError, ValueError):
        raise ValueError("Select a point in the points table first") from None
    if not 0 <= i < n:
        raise ValueError(f"No point {i + 1} (there are {n})")
    p = st.points[i]
    e = _entry_by_uid(st, p['uid'])
    if e is None or not e.curve.has(p['axis']) or e.curve.t.size == 0:
        raise ValueError(f"Point {i + 1} is no longer on a curve")
    return i, p, e


def _refuse_removed_point(st, i, p, e):
    """ValueError for a point whose sample lies inside a removed wait (Remove mode): it is not shown
    on the cut curve, so it cannot be edited or dragged there."""
    if _in_removed(st, e, p['t_raw']):
        raise ValueError(f"Point {i + 1} ({e.curve.name}) lies {_REMOVED_NOTE} (recorded at "
                         f"{float(p['t_raw']) + e.curve.time_offset:.3f} s): switch Pauses to 'Show (real time)' "
                         f"(section 4) to edit it")


def _point_to_sample(self, i, p, e, idx, how=''):
    """Move point i (on entry e) to sample idx of its shown curve (_vc); then the points table (in
    place, the selection stays), the 'Points' view, the plot and the status line.  Returns (t, value)."""
    st = _state(self)
    c = _vc(st, e)
    p['t_raw'] = _raw_of(st, e, c, int(idx))
    p.pop('_rc', None)
    t, v = _point_tv(st, p)
    _refresh_points_table(self)
    _redraw(self)
    _set_summary(self, f"Point {i + 1}: {c.name} · {p['axis']} moved to t = {t:.3f} s, "
                       f"{v:.4f} {_curve_unit(c, p['axis'])}{how}")
    return t, v


def _point_set_time(self, index, t):
    st = _state(self)
    i, p, e = _point_at(st, index)
    _refuse_removed_point(st, i, p, e)
    x = _parse_float(t)
    tt = _vc(st, e).times()
    how = '' if tt[0] <= x <= tt[-1] else f" (nearest sample: {x:.3f} s is outside its data)"
    return _point_to_sample(self, i, p, e, _nearest_idx(tt, x), how)


def _point_set_value(self, index, value):
    st = _state(self)
    i, p, e = _point_at(st, index)
    _refuse_removed_point(st, i, p, e)
    x = _parse_float(value)
    c, axis = _vc(st, e), p['axis']
    u = _curve_unit(c, axis)
    t_cur, _ = _point_tv(st, p)
    tc = la.nearest_crossing(c, axis, x, t_cur)
    if tc is None:
        vv = c.values(axis)
        vv = vv[np.isfinite(vv)]
        rng = f" (its values: {float(vv.min()):.4f} … {float(vv.max()):.4f} {u})" if vv.size else ""
        raise ValueError(f"{c.name} · {axis} never reaches {x:g} {u}{rng}")
    return _point_to_sample(self, i, p, e, _nearest_idx(c.times(), tc),
                            f" (it reaches {x:g} {u} at {tc:.3f} s: nearest sample)")


@_action("Reference points")
def logs_set_point_time(self, index, t):
    """Move reference point `index` (0-based) to the sample of its own curve and axis nearest to t
    (s, displayed time base).  Returns (t, value) of that sample."""
    return _point_set_time(self, index, t)


@_action("Reference points")
def logs_set_point_value(self, index, value):
    """Move reference point `index` (0-based) to where its curve reaches `value` (displayed, offsets
    applied) nearest to the point's current time: linear crossing between samples, then the nearest
    sample.  Refused (warning, nothing changed) when the curve never reaches the value.  Returns
    (t, value) of that sample."""
    return _point_set_value(self, index, value)


@_action("Align at points")
def logs_align_points(self, i, j, match_value=False):
    """Shift the curve of point j (0-based) in time so it meets point i; with match_value also its
    value offset.  Returns dict(curve, dt, dv)."""
    st = _state(self)
    n = len(st.points)
    i, j = int(i), int(j)
    if not (0 <= i < n and 0 <= j < n) or i == j:
        raise ValueError("Select 2 different points")
    pi, pj = st.points[i], st.points[j]
    if pi['uid'] == pj['uid']:
        raise ValueError("Both points are on the same curve: pick points on two different curves")
    ej = _entry_by_uid(st, pj['uid'])
    for k_, p_ in ((i, pi), (j, pj)):
        e_ = _entry_by_uid(st, p_['uid'])
        if e_ is not None:
            _refuse_removed_point(st, k_, p_, e_)
    ti, vi = _point_tv(st, pi)
    tj, vj = _point_tv(st, pj)
    if not all(np.isfinite(x) for x in (ti, vi, tj, vj)):
        raise ValueError("A point is no longer on its curve")
    dt = ti - tj
    dv = 0.0
    if match_value:
        ei = _entry_by_uid(st, pi['uid'])
        if _curve_unit(ei.curve if ei else None, pi['axis']) != _curve_unit(ej.curve, pj['axis']):
            raise ValueError(f"Cannot match values of {pi['axis']} and {pj['axis']} (different units)")
        dv = vi - vj
        ej.curve.value_offsets[pj['axis']] = _vof(ej.curve, pj['axis']) + dv
    ej.curve.time_offset += dt
    _sync_offset_spins(self)
    _after_offsets_changed(self)
    _set_summary(self, f"Shifted '{ej.curve.name}' by {dt:+.3f} s" + (f" and {dv:+.4f} {_curve_unit(ej.curve, pj['axis'])}"
                                                                       if match_value else "")
                 + f" so point {j + 1} meets point {i + 1}")
    return {'curve': ej.curve.name, 'dt': dt, 'dv': dv}


# ----------------------------------------------------------------------------
# Actions: results / export
# ----------------------------------------------------------------------------
@_action("Results")
def logs_show_results(self, name):
    st = _state(self)
    if name not in st.results:
        raise ValueError(f"No results '{name}' (available: {', '.join(st.results) or 'none'})")
    _show_results(self, name)
    return name


@_action("Export results")
def logs_export_results(self, path, name=None):
    """Write a results view (default: the one shown) to a CSV file (la.write_rows_csv: ';' columns,
    decimal comma; '#' notes first: the view and its time base, i.e. whether waits were removed)."""
    st = _state(self)
    name = name or st.current_results
    if not name or name not in st.results:
        raise ValueError("No results to export: run an analysis first")
    headers, rows = st.results[name]
    note = st.results_notes.get(name) or _time_base_note(st, name)
    notes = [f"LogIQ Log files results: {name}", note]
    if _results_stale(st, name):
        notes.append(_results_note_text(st, name)[0].split(" (Time base:")[0])
    notes.append("Format: columns separated by semicolons, decimal comma")
    # numbers in the note columns and the '#' notes with a decimal comma too, plain ASCII dashes
    la.write_rows_csv(path, headers, _csv_rows(headers, rows), notes=[_csv_text(n) for n in notes])
    _remember_folder(st, path)
    _set_summary(self, f"Results '{name}' exported to {path}")
    return path


def _export_col_stem(axis, name):
    """'<axis>: <curve name>' made safe for the Planning importer's header test
    (fcn_plan.fcn_import.is_trace_log_file): it splits the header at , ; and tab (also inside
    quotes) and takes the file for a TRACE log when two of: a token 'time' / 't' / containing
    'time_s'; a token starting with 'pos_' or ending in '_mm' / '_deg'; a token containing 'probe' /
    'sensor' (or a 'log_*' file name with one of the first two).  The axis prefix and the unit
    suffix added by _export_columns rule out the position test; separators / quotes become spaces
    and 'time_s' becomes 'time-s', so neither of the first two can match whatever the name."""
    txt = f"{axis}: {name}"
    txt = re.sub(r'[,;\t\r\n"]+', ' ', txt)
    txt = re.sub(r'(?i)(time)_(s)', r'\1-\2', txt)
    txt = re.sub(r'\s+', ' ', txt).strip()
    if txt[:4].lower() == 'pos_':
        txt = txt[:3] + ' ' + txt[4:]
    return txt


def _export_columns(axis, names, unit=None):
    """Header of the aligned export: _EXPORT_TIME_COL, then a unique '<stem> [<unit>]' per curve
    name (in order); unit: of the axis (default la.axis_unit)."""
    u = unit or _unit(axis)
    out = [_EXPORT_TIME_COL]
    for name in names:
        stem = _export_col_stem(axis, name)
        col, k = f"{stem} [{u}]", 2
        while col in out:
            col = f"{stem} ({k}) [{u}]"
            k += 1
        out.append(col)
    return out


@_action("Export aligned data", busy=True)
def logs_export_aligned(self, path, dt=0.01):
    """Visible curves on the analysis axis (offsets applied; in Remove mode without their logged waits)
    on a common time grid (ROI) to CSV, in the v2 style of the logs: '#' notes first (what was exported,
    the time base: whether waits were removed), ';' columns, decimal comma.
    Columns: 'time [s]' and '<axis>: <curve> [<unit>]' per curve (_export_columns), which the Planning
    importer never takes for a TRACE log; the Log files tab reads the file back as one curve with
    one axis per column."""
    st = _state(self)
    axis = _require_axis(st)
    curves = [_vc(st, e) for e in _visible(st, axis)]
    if not curves:
        raise ValueError(f"No visible curve with {axis}")
    df = la.aligned_table(curves, axis, roi=st.roi, dt=float(dt))
    # aligned_table: the time column, then one column per curve in order (named after the curve,
    # ' (2)' ... added on a clash, also with its own 'Time_s'): renamed from the curve names
    cols = list(df.columns)
    t_col = 'Time_s' if 'Time_s' in cols else cols[0]
    data_cols = [c for c in cols if c != t_col]
    df = df[[t_col] + data_cols]
    names = [c.name for c in curves] if len(data_cols) == len(curves) else data_cols
    df.columns = _export_columns(axis, names, unit=_axis_unit(st, axis))
    folder = os.path.dirname(os.fspath(path))
    if folder:
        os.makedirs(folder, exist_ok=True)
    # v2 style (as the logs): '#' notes (no ';' in them), ';' columns, decimal comma
    notes = [f"LogIQ Log files aligned export: {axis} of {len(curves)} curve(s), common time grid {float(dt):g} s"
             + (_roi_txt(st) if st.roi else ""), _time_base_note(st),
             "Format: columns separated by semicolons, decimal comma"]
    with open(path, 'w', newline='', encoding='utf-8') as f:
        for n in notes:
            f.write(la.comment_line(_csv_text(n)) + '\r\n')
        df.to_csv(f, index=False, float_format='%.6f', na_rep='', sep=la.CSV_SEP, decimal=la.CSV_DECIMAL,
                  lineterminator='\r\n')
    _remember_folder(st, path)
    _set_summary(self, f"Aligned {axis} data of {len(curves)} curve(s) ({len(df)} rows) exported to {path}")
    return path


@_action("Save figure")
def logs_save_figure(self, path, dpi=150):
    folder = os.path.dirname(os.fspath(path))
    if folder:
        os.makedirs(folder, exist_ok=True)
    self.logs_fig.savefig(path, dpi=dpi, facecolor='white')
    _remember_folder(_state(self), path)
    _set_summary(self, f"Figure saved to {path}")
    return path


# ----------------------------------------------------------------------------
# Slots (dialogs and widget signals only collect values and call the actions)
# ----------------------------------------------------------------------------
def _on_add_logs_clicked(self):
    try:
        paths, _ = QFileDialog.getOpenFileNames(self, "Add LogIQ log files", _default_folder(self), _LOG_FILTER)
    except Exception as e:
        _warn(self, "Log files", e)
        return
    if paths:
        logs_add_files(self, paths)


def _on_add_ref_clicked(self):
    try:
        path, _ = QFileDialog.getOpenFileName(self, "Add reference G-code", _default_folder(self), _GCODE_FILTER)
    except Exception as e:
        _warn(self, "Reference G-code", e)
        return
    if path:
        logs_add_reference(self, path)


def _save_dialog(self, title, default_name, filt):
    path, _ = QFileDialog.getSaveFileName(self, title, os.path.join(_default_folder(self), default_name), filt)
    return path


def _safe_file_part(text):
    return re.sub(r'[^A-Za-z0-9_.-]+', '_', str(text)).strip('_') or 'x'


# Suggested export names never start with 'log_': that prefix marks a TRACE log for the Planning
# importer (fcn_plan.fcn_import.is_trace_log_file) and for this tab's own file filter.
def _results_file_name(view):
    return f"results_{_safe_file_part(view)}.csv"


def _aligned_file_name(axis):
    return f"aligned_{_safe_file_part(axis or 'data')}.csv"


def _figure_file_name(axis):
    return f"plot_{_safe_file_part(axis or 'logs')}.png"


def _on_export_results_clicked(self):
    try:
        st = _state(self)
        if not st.current_results:
            raise ValueError("No results to export: run an analysis first")
        path = _save_dialog(self, "Export results CSV", _results_file_name(st.current_results),
                            "CSV (*.csv);;All files (*)")
    except Exception as e:
        _warn(self, "Export results", e)
        return
    if path:
        logs_export_results(self, path)


def _on_export_aligned_clicked(self):
    try:
        st = _state(self)
        path = _save_dialog(self, "Export aligned data CSV", _aligned_file_name(st.analysis_axis),
                            "CSV (*.csv);;All files (*)")
    except Exception as e:
        _warn(self, "Export aligned data", e)
        return
    if path:
        logs_export_aligned(self, path)


def _on_save_fig_clicked(self):
    try:
        path = _save_dialog(self, "Save figure", _figure_file_name(_state(self).analysis_axis),
                            "PNG image (*.png);;PDF (*.pdf);;SVG (*.svg)")
    except Exception as e:
        _warn(self, "Save figure", e)
        return
    if path:
        logs_save_figure(self, path)


def _on_curve_item_changed(self, item):
    try:
        if item.column() != 0:
            return
        logs_set_visible(self, item.row(), item.checkState() == Qt.Checked)
    except Exception as e:
        _warn(self, "Show curve", e)


def _on_curve_selection(self):
    try:
        st = _state(self)
        rows = sorted({ix.row() for ix in self.logs_curves_table.selectedIndexes()})
        st.selected = rows[0] if rows else -1
        _update_selected_label(self)
        _update_duet_button(self)
    except Exception as e:
        _warn(self, "Select curve", e)


def _on_curve_double_clicked(self, row, col):
    if col != 1:
        return
    try:
        st = _state(self)
        e = _entry_at(st, row)
        c = QColorDialog.getColor(QColor(e.color), self, f"Colour of {e.curve.name}")
        if c.isValid():
            logs_set_curve_color(self, row, c.name())
    except Exception as e:
        _warn(self, "Curve colour", e)


def _on_toff_spin(self, uid, value):
    st = _state(self)
    e = _entry_by_uid(st, uid)
    if e is not None:
        _deferred(self, logs_set_time_offset, _index_of(st, e), value)


def _on_voff_spin(self, uid, value):
    st = _state(self)
    e = _entry_by_uid(st, uid)
    if e is not None and st.analysis_axis and e.curve.has(st.analysis_axis):
        _deferred(self, logs_set_value_offset, _index_of(st, e), value)


def _on_axis_combo(self):
    axis = self.logs_axis_combo.currentData()
    if axis:
        logs_set_analysis_axis(self, axis)


def _on_ref_combo(self):
    st = _state(self)
    uid = self.logs_ref_combo.currentData()
    e = _entry_by_uid(st, uid)
    if e is not None:
        logs_set_reference(self, _index_of(st, e))


def _on_pause_source_combo(self):
    st = _state(self)
    uid = self.logs_pause_source_combo.currentData()
    e = _entry_by_uid(st, uid) if uid is not None else None
    if e is not None and uid != getattr(_pause_source(st), 'uid', None):
        logs_set_pause_source(self, _index_of(st, e))


def _on_results_view(self, name):
    if name:
        logs_show_results(self, name)


def _selected_point_rows(self):
    """0-based indices (in st.points) of the points selected in the points table, by point id."""
    st = _state(self)
    ids = _selected_point_ids(self)
    return [i for i, p in enumerate(st.points) if p.get('id') in ids]


def _on_delete_points_clicked(self):
    try:
        rows = _selected_point_rows(self)
        if not rows:
            raise ValueError("Select point(s) in the points table first")
    except Exception as e:
        _warn(self, "Reference points", e)
        return
    logs_delete_points(self, rows)


def _on_align_points_clicked(self):
    try:
        rows = _selected_point_rows(self)
        if len(rows) != 2:
            raise ValueError("Select exactly 2 points in the points table (Ctrl+click)")
    except Exception as e:
        _warn(self, "Align at points", e)
        return
    logs_align_points(self, rows[0], rows[1], match_value=self.logs_chk_points_value.isChecked())


def _on_point_item_changed(self, item):
    """A t / Value cell of the points table edited by the user (double-click / F2 / typing): the
    point moves (table updated in place, plot, status line); an invalid entry is refused in the
    status line and the cell restored (no box per typo)."""
    try:
        if item is None or item.column() not in _POINT_EDIT_COLS:
            return
        st = _state(self)
        it0 = self.logs_points_table.item(item.row(), 0)
        pid = it0.data(Qt.UserRole) if it0 is not None else None
        idx = next((i for i, p in enumerate(st.points) if pid is not None and p.get('id') == int(pid)), None)
        col, text = item.column(), item.text()
    except Exception:
        traceback.print_exc()
        return
    if idx is None:
        _refresh_points_table(self)
        return
    try:
        if col == _POINT_EDIT_COLS[0]:
            _point_set_time(self, idx, text)
        else:
            _point_set_value(self, idx, text)
    except ValueError as e:
        _refresh_points_table(self)             # restores the cell (in place)
        _set_summary(self, f"Point {idx + 1}: {e} – the cell is restored.")
    except Exception as e:
        traceback.print_exc()
        _refresh_points_table(self)
        _warn(self, "Reference points", e)


def _on_movement_item_changed(self, item):
    """A Start / Stop cell of the movements table edited by the user: the movement changes (marked
    edited, numbers from la.movement_stats, 'Movements' view, lanes, status line); an invalid entry is
    refused in the status line and the cell restored."""
    try:
        if item is None or item.column() not in _MOVEMENT_EDIT_COLS:
            return
        st = _state(self)
        it0 = self.logs_movements_table.item(item.row(), 0)
        mid = it0.data(Qt.UserRole) if it0 is not None else None
        found = _movement_by_id(st, int(mid)) if mid is not None else None
        col, text = item.column(), item.text()
    except Exception:
        traceback.print_exc()
        return
    if found is None:
        _refresh_movements_table(self, force=True)
        return
    e, mv, k = found
    is_start = col == _MOVEMENT_EDIT_COLS[0]
    restore = {int(mid)}                        # the edited row is rewritten from the state
    try:
        x = _parse_float(text)
        ia, ib = _movement_span_idx(st, e, mv, k, x if is_start else None, None if is_start else x)
        if (ia, ib) == _movement_cur_idx(st, e, mv, k):
            # the same sample: nothing stored (not marked edited; flags such as 'incomplete' stay)
            _refresh_movements_table(self, force=restore)
            _set_summary(self, _unchanged_msg(st, e, k, ia, ib, 'start' if is_start else 'stop')
                         + " – the cell is restored.")
            return
        _commit_movement(self, e, mv, k, ia, ib, 'start set' if is_start else 'stop set',
                         'start' if is_start else 'stop')
    except ValueError as err:
        _refresh_movements_table(self, force=restore)      # restores the cell (in place)
        _set_summary(self, f"Movement {k + 1} of {e.curve.name}: {err} – the cell is restored.")
    except Exception as err:
        traceback.print_exc()
        _refresh_movements_table(self, force=restore)
        _warn(self, "Movements", err)


def _selected_movement_rows(self):
    """0-based indices (movements table order) of the movements selected in the movements table, by id."""
    st = _state(self)
    ids = _selected_movement_ids(self)
    return [i for i, (e, mv, k) in enumerate(_movement_items(st)) if mv['ids'][k] in ids]


def _on_delete_movements_clicked(self):
    try:
        rows = _selected_movement_rows(self)
        if not rows:
            raise ValueError("Select movement(s) in the movements table first")
    except Exception as e:
        _warn(self, "Movements", e)
        return
    logs_delete_movements(self, rows)
