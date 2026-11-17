"""
LogIQ on small or zoomed screens (a 14" laptop at 150 % has a work area of 1280 x 672 logical px; the Control page
alone asked for 1723 x 1186, so Qt squeezed widgets on top of each other or let the window run off the screen).

    from fcn_create_gui.small_screen import apply_small_screen_layout
    apply_small_screen_layout(window)          # after apply_logiq_shell(window)

Layout only; widgets, their names and their logic stay the same objects.  On a large screen nothing moves except
the Control splitter handle and the DYNAMIQ position row (now as high as its fields).

* Pages scroll instead of overlapping: the tab pages sit in a scroll area.  A page that needs more room than the
  window gets a scroll bar; the header (connection, Emergency STOP) and the left column always stay on screen.
  The hidden main tab bar no longer counts for the page height (it added 80 px to every page).
* Control: a splitter between the DYNAMIQ / KINETIQ controls and the command console.  Drag it down and the
  console shrinks to its command line (Step (mm) buttons in a row, log hidden); drag it up and the controls scroll.
* Wide rows go onto a second line when the window is too narrow for them: DYNAMIQ position row (Go to, zero state,
  Set zero), KINETIQ dimensions row (Go to ..., Home ..., Trigger), Status card (speed factor and options, then
  Auto release / pause, the 14 axis speeds in two rows of 7), Planning (Pauses & trigger card under the curve
  fields).
* Status: on its first opening the Reference panel goes to the right, full height, with drag bars
  (fcn_create_gui/status_split.py).  Planning: on its first opening the Curve Options get compact and the sub-tabs
  a column on the right (fcn_create_gui/planning_curve_layout.py); the Pause and Trigger card goes above the
  Position-Gated Trigger panel when they do not fit side by side.
* Header on every screen: less padding, and its logo, IP field and buttons at 70 % of their size (text 13 px).
  Left column at 80 % of its width, icons, text and button height.
* Header: no clipped text (minimum widths as wide as the text); compact when narrow (word mark hidden, smaller IP
  field).  Left column: smaller icons, icons only when low.
* DYNAMIQ position row: its frame was fixed at 60 px while its fields need 72 px (clipped on every screen).
  KINETIQ value fields: wide enough for '-00.000'.
"""
import re

from PySide6.QtCore import QEvent, QObject, QSize, Qt, QTimer
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import (QBoxLayout, QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QScrollArea,
                               QSizePolicy, QSpacerItem, QSplitter, QWidget, QWidgetItem)

STEP_MIN_HEIGHT = 28            # px, Step (mm) buttons (were at least 84)
STEP_ROW_WIDTH = 64             # px, Step (mm) buttons when they sit in a row (console dragged down)
SPLIT_HANDLE = 12               # px, Control splitter handle (touch friendly)
CONSOLE_COMFORT = 150           # px, console height the first split leaves when the controls still fit
LOG_MIN_SHOWN = 40              # px of log needed to show it in the compact console
NAV_SCALE = 0.8                 # left column: width, icons, text and buttons at 80 % of logiq_shell (user request)
NAV_FULL = round(88 * NAV_SCALE)          # left column button height (logiq_shell: 88)
NAV_MIN = round(44 * NAV_SCALE)           # lowest left column button (icons only)
NAV_TEXT_MIN = round(66 * NAV_SCALE)      # below this the left column shows icons only
NAV_NARROW = round(88 * NAV_SCALE)        # left column width in a narrow window (normal: 108 * NAV_SCALE)
NAV_NARROW_SIDE = 5                       # px, left column side margins in a narrow window
NAV_ICON = round(34 * NAV_SCALE)          # left column icons (logiq_shell: 34)
NAV_ICON_LOW = round(28 * NAV_SCALE)      # icons when the window is too low for the full buttons
HEADER_CONTROLS = 0.7           # header logo, IP field and buttons at 70 % of their size (user request, all screens)
HEADER_FONT = 13                # px, text of every header control (buttons 19 px x 0.7; the state pill had 14 / 26)
BRAND_COMPACT = round(52 * HEADER_CONTROLS)   # logo only (word mark hidden) in a narrow window
LOW_HEIGHT = 760                # px of window height below which header and Control sub-tabs get lower
SUBTAB_LOW_CSS = """
    QTabBar::tab { min-height: 26px; padding: 4px 18px; }
    QTabBar::tab:selected { font-size: 17px; }
"""
HEADER_SLACK = 8                # px of hysteresis, compact header
WRAP_SLACK = 6                  # px of hysteresis, wrapped rows and compact console
VALUE_SAMPLE = "-00.000"        # widest value a KINETIQ field shows in full

SPLITTER_CSS = """
    QSplitter::handle:vertical {
        background-color: #cfd8dc;
        border-top: 1px solid #b0bec5;
        border-bottom: 1px solid #b0bec5;
        margin: 2px 0px;
    }
    QSplitter::handle:vertical:hover, QSplitter::handle:vertical:pressed {
        background-color: #1976d2;
    }
"""


def _smart_min(widget):
    """Minimum size a layout gives widget (explicit minimum size, else its minimum size hint)."""
    return QWidgetItem(widget).minimumSize()


# ---------------------------------------------------------------------------------------------------- pages scroll
class _PageHost(QWidget):
    """Holds tabModules in the page scroll area and asks only for the CURRENT page's minimum size (a QTabWidget
    also counts its tab bar, hidden here: 80 px more on every page)."""

    def __init__(self, tw, parent):
        super().__init__(parent)
        self.setObjectName("logiqPageHost")
        self.tw = tw
        tw.setParent(self)
        tw.currentChanged.connect(lambda *_: self.updateGeometry())

    def _page(self):
        return self.tw.currentWidget()

    def minimumSizeHint(self):
        p = self._page()
        if p is None:
            return QSize(0, 0)
        frame = self.tw.minimumSizeHint().width() - p.minimumSizeHint().width()      # pane frame, 4 px
        return _smart_min(p) + QSize(max(0, frame), max(0, frame))

    def sizeHint(self):
        p = self._page()
        return (p.sizeHint() if p is not None else QSize(0, 0)).expandedTo(self.minimumSizeHint())

    def resizeEvent(self, ev):
        self.tw.setGeometry(self.rect())
        super().resizeEvent(ev)

    def event(self, ev):
        if ev.type() == QEvent.LayoutRequest:          # a page's size hints changed
            self.updateGeometry()
        return super().event(ev)


def _page_scroll(window):
    tw = getattr(window, "tabModules", None)
    body = tw.parentWidget() if tw is not None else None
    bl = body.layout() if body is not None else None
    if bl is None or bl.indexOf(tw) < 0:
        raise RuntimeError("tabModules is not in the LogIQ body (apply_logiq_shell first)")
    i = bl.indexOf(tw)
    stretch = bl.stretch(i)
    bl.removeWidget(tw)
    sc = QScrollArea(body)
    sc.setObjectName("logiqPageScroll")
    sc.setWidgetResizable(True)
    sc.setFrameShape(QFrame.NoFrame)
    sc.setStyleSheet("QScrollArea#logiqPageScroll { background: transparent; border: none; }")
    host = _PageHost(tw, sc)
    sc.setWidget(host)
    bl.insertWidget(i, sc, stretch or 1)
    tw.show()
    window.page_scroll = sc
    return sc


# ---------------------------------------------------------------------------------------------------- Control
def _step_buttons_shrink(window):
    """Step (mm) buttons share the console's height and may get as low as STEP_MIN_HEIGHT.  set_global_step_size
    re-styles them on every click with 'min-height: 84px'; their own setStyleSheet lowers that value."""
    buttons = getattr(window, "step_buttons", None) or {}
    current = None
    for key, b in buttons.items():
        def themed(css, _b=b):
            QWidget.setStyleSheet(_b, re.sub(r"min-height\s*:\s*\d+px", f"min-height: {STEP_MIN_HEIGHT}px", css))
        b.setStyleSheet = themed
        b.setMinimumHeight(STEP_MIN_HEIGHT)
        b.setSizePolicy(b.sizePolicy().horizontalPolicy(), QSizePolicy.Expanding)
        if b.isChecked():
            current = key
    if buttons:
        from fcn_control.fcn_control import set_global_step_size
        set_global_step_size(window, current if current is not None else "1")


class _Console(QObject):
    """Command console pane of the Control splitter: full (log + Step (mm) column) or, when dragged down, compact
    (Step (mm) buttons in a row; the log hidden when there is no room for it)."""

    def __init__(self, window, pane, box_cmd, box_step):
        super().__init__(pane)
        self.pane, self.box_cmd, self.box_step = pane, box_cmd, box_step
        self.log = window.duet_log_console
        self.step_lay = box_step.layout()
        self.step_buttons = list((getattr(window, "step_buttons", None) or {}).values())
        self.step_width = {b: b.minimumWidth() for b in self.step_buttons}
        self.log_min = self.log.minimumHeight()
        self.compact = False
        cmd_lay = box_cmd.layout()
        m = cmd_lay.contentsMargins()
        row = cmd_lay.itemAt(0)
        self.min_h = row.minimumSize().height() + m.top() + m.bottom() + 4          # the command line alone
        self.full_h = max(_smart_min(box_step).height(), _smart_min(box_cmd).height())
        pane.setMinimumHeight(self.min_h)     # the splitter may drag the pane this low; the modes keep it tidy
        pane.installEventFilter(self)

    def eventFilter(self, obj, ev):
        if ev.type() == QEvent.Resize:
            self.update()
        return False

    def update(self):
        h = self.pane.height()
        if not self.compact and h < self.full_h:
            self.set_compact(True)
        elif self.compact and h >= self.full_h + WRAP_SLACK:
            self.set_compact(False)
        if self.compact:
            self.log.setVisible(h >= self.min_h + LOG_MIN_SHOWN)

    def set_compact(self, on):
        self.compact = on
        self.step_lay.setDirection(QBoxLayout.LeftToRight if on else QBoxLayout.TopToBottom)
        for b in self.step_buttons:
            b.setMinimumWidth(STEP_ROW_WIDTH if on else self.step_width[b])
        self.log.setMinimumHeight(1 if on else self.log_min)     # 0 would mean 'unset': its 128 px hint
        if not on:
            self.log.show()


def _bottom_row(page_layout, widget):
    for i in range(page_layout.count()):
        lay = page_layout.itemAt(i).layout()
        if lay is not None and lay.indexOf(widget) >= 0:
            return i, lay
    return -1, None


def _control_splitter(window):
    """Control: DYNAMIQ / KINETIQ controls (scrollable) above, command console + Step (mm) below, a handle between."""
    page, sub = window.tab_2, window.tabWidget
    lay = page.layout()
    box_cmd = window.duet_log_console.parentWidget()
    box_step = next(iter(window.step_buttons.values())).parentWidget()
    _, bottom = _bottom_row(lay, box_cmd)
    if bottom is None or lay.indexOf(sub) < 0:
        raise RuntimeError("Control page layout not as expected")

    pane = QWidget(page)
    pane.setObjectName("controlConsolePane")
    cl = QHBoxLayout(pane)
    cl.setContentsMargins(0, 0, 0, 0)
    cl.setSpacing(max(0, bottom.spacing()))
    while bottom.count():
        it = bottom.itemAt(0)
        w, st, al = it.widget(), bottom.stretch(0), it.alignment()
        if w is None:
            bottom.takeAt(0)
            continue
        bottom.removeWidget(w)
        cl.addWidget(w, st, al)
    lay.removeItem(bottom)
    bottom.setParent(None)

    i = lay.indexOf(sub)
    lay.removeWidget(sub)
    controls = QScrollArea(page)
    controls.setObjectName("controlScroll")
    controls.setWidgetResizable(True)
    controls.setFrameShape(QFrame.NoFrame)
    controls.setStyleSheet("QScrollArea#controlScroll { background: transparent; border: none; }")
    controls.setWidget(sub)
    sp = QSplitter(Qt.Vertical, page)
    sp.setObjectName("controlSplitter")
    sp.setChildrenCollapsible(False)
    sp.setHandleWidth(SPLIT_HANDLE)
    sp.setStyleSheet(SPLITTER_CSS)
    sp.addWidget(controls)
    sp.addWidget(pane)
    sp.setStretchFactor(0, 0)                   # a taller window gives its extra height to the console
    sp.setStretchFactor(1, 1)
    sp.handle(1).setToolTip("Drag to make the command console smaller or larger")
    lay.insertWidget(i, sp, 1)
    sub.show()
    pane.show()
    window.control_splitter = sp
    window.control_console = _Console(window, pane, box_cmd, box_step)

    # only the shown sub-tab counts for the height of the controls (DYNAMIQ is lower than KINETIQ)
    from fcn_create_gui.window_fit import fit_tabs_to_current_page
    fit_tabs_to_current_page(window, sub)
    controls.setMinimumHeight(min(160, _smart_min(sub).height()))

    state = {"moved": False}
    sp.splitterMoved.connect(lambda *_: state.__setitem__("moved", True))

    def natural_split():
        """Large window: half and half, as before the splitter.  Smaller: controls at their natural height if the
        console keeps CONSOLE_COMFORT px, else at least their minimum (console down to its command line).
        Stops once the user drags the handle."""
        if state["moved"] or not sp.isVisible():
            return
        total = sum(sp.sizes())
        if total <= 0:
            return
        c_min = pane.minimumHeight()
        s_min, s_hint = _smart_min(sub).height(), max(_smart_min(sub).height(), sub.sizeHint().height())
        top = min(s_hint, total - c_min)
        comfy = total - CONSOLE_COMFORT
        if top > comfy >= s_min:
            top = comfy
        if top < total // 2 <= comfy:
            top = total // 2
        top = max(1, min(top, total - c_min))
        if abs(sp.sizes()[0] - top) > 1:
            sp.setSizes([top, max(total - top, 1)])

    class _OnResize(QObject):                   # until the user drags: natural split at every size
        def eventFilter(self, obj, ev):
            if ev.type() in (QEvent.Resize, QEvent.Show):
                QTimer.singleShot(0, natural_split)
            return False

    sp._natural_filter = _OnResize(sp)
    sp.installEventFilter(sp._natural_filter)
    window.control_natural_split = natural_split
    sub.currentChanged.connect(lambda *_: QTimer.singleShot(0, natural_split))
    return sp


def _position_row_height(window):
    """DYNAMIQ position row: frame as high as its fields need (it was fixed at 60 px, the fields need 72)."""
    frame = window.btn_goto_lung.parentWidget()
    need = frame.minimumSizeHint().height()
    if need > frame.maximumHeight():
        frame.setFixedHeight(need)
    return frame


def _kinetiq_fields(window):
    """KINETIQ table: current / target fields wide enough for VALUE_SAMPLE (A-D showed ').000' on a laptop)."""
    grid_frame = window.POS_CURR_LATAXIS.parentWidget()
    for le in grid_frame.findChildren(QLineEdit):
        le.ensurePolished()
        need = QFontMetrics(le.font()).horizontalAdvance(VALUE_SAMPLE) + 18
        if le.minimumWidth() < need <= le.maximumWidth():
            le.setMinimumWidth(need)


# ---------------------------------------------------------------------------------------------------- wrapped rows
def _clone_spacer(item):
    s = item.spacerItem()
    hint, pol = s.sizeHint(), s.sizePolicy()
    return QSpacerItem(hint.width(), hint.height(), pol.horizontalPolicy(), pol.verticalPolicy())


def _move_tail(src, start, dst):
    """Items src[start:] to the end of dst, in order (widgets keep their stretch, alignment and hidden state)."""
    while src.count() > start:
        it = src.itemAt(start)
        st, al = src.stretch(start), it.alignment()
        w, lay = it.widget(), it.layout()
        if w is not None:
            hidden = w.isHidden()
            src.removeWidget(w)
            dst.addWidget(w, st, al)
            w.setVisible(not hidden)
        elif lay is not None:
            src.takeAt(start)
            dst.addLayout(lay, st)
        elif it.spacerItem() is not None:
            sp = _clone_spacer(it)
            src.takeAt(start)
            dst.addItem(sp)
            dst.setStretch(dst.count() - 1, st)
        else:
            src.takeAt(start)


def _natural_width(item):
    """Width a layout item needs for all its contents, also those with an Ignored width policy (they shrink, so
    the layout's own minimum does not count them)."""
    if isinstance(item, QWidget):
        if item.isHidden():
            return 0
        lay = item.layout()
        if lay is None:
            return max(item.minimumSizeHint().width(), item.minimumWidth())
        m = item.contentsMargins()
        return max(item.minimumWidth(), _natural_width(lay) + m.left() + m.right())
    if isinstance(item, QGridLayout):
        sp = max(0, item.horizontalSpacing())
        cols = [0] * item.columnCount()
        spans = []
        for i in range(item.count()):
            r, c, rs, cs = item.getItemPosition(i)
            v = _natural_item(item.itemAt(i))
            if cs <= 1:
                cols[c] = max(cols[c], v)
            else:
                spans.append((c, min(cs, item.columnCount() - c), v))
        for c, cs, v in spans:                    # an item over several columns widens the last one if needed
            have = sum(cols[c:c + cs]) + sp * (cs - 1)
            if v > have:
                cols[c + cs - 1] += v - have
        m = item.contentsMargins()
        used = [v for v in cols if v > 0]
        return sum(used) + sp * max(0, len(used) - 1) + m.left() + m.right()
    if isinstance(item, QBoxLayout):
        widths = [_natural_item(item.itemAt(i)) for i in range(item.count())]
        m = item.contentsMargins()
        if item.direction() in (QBoxLayout.LeftToRight, QBoxLayout.RightToLeft):
            used = [v for v in widths if v > 0]
            return sum(used) + max(0, item.spacing()) * max(0, len(used) - 1) + m.left() + m.right()
        return max(widths or [0]) + m.left() + m.right()
    return 0


def _natural_item(it):
    if it is None:
        return 0
    if it.widget() is not None:
        return _natural_width(it.widget())
    if it.layout() is not None:
        return _natural_width(it.layout())
    s = it.spacerItem()
    if s is not None and s.sizePolicy().horizontalPolicy() == QSizePolicy.Fixed:
        return s.sizeHint().width()
    return 0


class RowWrap:
    """One line of a QHBoxLayout (row) that puts its tail (from item first on) on a second line while there is not
    enough width for the whole line.  host: the widget whose width bounds the row (its frame, or the card holding
    it); line2 / line2_row: the second line (a widget under the row) and its layout; lead: items line2_row holds
    before the moved ones (e.g. a stretch).  need_fn / avail_fn (optional): width the host needs for one line and
    the width it can get; by default the row's own minimum and the width of the nearest scroll area around it.
    fill_row1: while wrapped, a stretch ends the first line (its buttons keep their width)."""

    def __init__(self, host, row, first, line2, line2_row, lead=0, hide_when_wrapped=(), need_fn=None,
                 avail_fn=None, fill_row1=False, visible_with=None):
        self.host, self.row, self.first = host, row, first
        self.line2, self.line2_row, self.lead = line2, line2_row, lead
        self.hide_when_wrapped = hide_when_wrapped
        self.need_fn, self.avail_fn = need_fn, avail_fn
        self.fill_row1 = fill_row1
        self.visible_with = visible_with      # the moved items' former container: line 2 is hidden with it
        self.wrapped = False
        line2.hide()
        if visible_with is not None:
            self._follow = _FollowVisible(self, visible_with)

    def sync_visible(self):
        if self.wrapped and self.visible_with is not None:
            self.line2.setVisible(not self.visible_with.isHidden())

    def need(self):
        if self.need_fn is not None:
            return self.need_fn()
        need = self.row.minimumSize().width()
        if self.wrapped:
            m = self.line2_row.contentsMargins()
            need += self.line2_row.minimumSize().width() - m.left() - m.right() + max(0, self.row.spacing())
            for w in self.hide_when_wrapped:
                need += w.sizeHint().width() + max(0, self.row.spacing())
        return need + (self.host.width() - self.row.geometry().width())

    def scroll_area(self):
        """Nearest scroll area around the host (its width is what the row can get)."""
        p = self.host.parentWidget()
        while p is not None:
            if isinstance(p, QScrollArea) and p.widget() is not None and p.widget().isAncestorOf(self.host):
                return p
            p = p.parentWidget()
        return None

    def avail(self):
        if self.avail_fn is not None:
            return self.avail_fn()
        sa = self.scroll_area()
        if sa is None:
            return self.host.width()
        return sa.viewport().width() - (sa.widget().width() - self.host.width())

    def update(self):
        if not self.host.isVisible() or self.row.geometry().width() <= 0:
            return
        avail = self.avail()
        need = self.need()
        if not self.wrapped and avail < need:
            self.wrap(True)
        elif self.wrapped and avail >= need + WRAP_SLACK:
            self.wrap(False)

    def wrap(self, on):
        if on == self.wrapped:
            return
        if on:
            self.line2.show()                     # shown first: moved widgets come up shown
            _move_tail(self.row, self.first, self.line2_row)
            if self.fill_row1:
                self.row.addStretch(1)
            for w in self.hide_when_wrapped:
                w.setProperty("_wrap_hidden", w.isHidden())
                w.hide()
            self.wrapped = True
            self.sync_visible()
        else:
            last = self.row.count() - 1
            if self.fill_row1 and last >= 0 and self.row.itemAt(last).spacerItem() is not None:
                self.row.takeAt(last)
            _move_tail(self.line2_row, self.lead, self.row)
            for w in self.hide_when_wrapped:
                w.setVisible(not w.property("_wrap_hidden"))
            self.line2.hide()
        self.wrapped = on


class _FollowVisible(QObject):
    """Line 2 of a RowWrap follows a widget's shown / hidden state (Status Basic mode hides the speed controls)."""

    def __init__(self, rw, widget):
        super().__init__(widget)
        self.rw = rw
        widget.installEventFilter(self)

    def eventFilter(self, obj, ev):
        if ev.type() in (QEvent.Show, QEvent.Hide, QEvent.ShowToParent, QEvent.HideToParent):
            self.rw.sync_visible()
        return False


def _wrap_frame_row(first_widget, align_right=False, from_separator=False, above=False):
    """RowWrap for the framed row holding first_widget: first_widget and what follows go to a second framed line,
    under the row (or above it: above=True)."""
    frame = first_widget.parentWidget()
    row = frame.layout()
    first = row.indexOf(first_widget)
    hide = ()
    if from_separator and first > 0:           # separator line just before first_widget: hidden while wrapped
        prev = row.itemAt(first - 1).widget()
        if isinstance(prev, QFrame) and prev.frameShape() in (QFrame.VLine, QFrame.HLine):
            hide = (prev,)
    parent_box = frame.parentWidget().layout()
    twin = QFrame(frame.parentWidget())
    twin.setStyleSheet(frame.styleSheet())
    twin.setFrameShape(frame.frameShape())
    lay = QHBoxLayout(twin)
    m = row.contentsMargins()
    lay.setContentsMargins(m.left(), m.top(), m.right(), m.bottom())
    lay.setSpacing(row.spacing())
    lead = 0
    if align_right:
        lay.addStretch(1)
        lead = 1
    if frame.maximumHeight() == frame.minimumHeight():          # fixed height frame (DYNAMIQ position row)
        twin.setFixedHeight(frame.maximumHeight())
    parent_box.insertWidget(parent_box.indexOf(frame) + (0 if above else 1), twin)
    return RowWrap(frame, row, first, twin, lay, lead, hide)


def _index_of_layout(box, lay):
    for i in range(box.count()):
        if box.itemAt(i).layout() is lay:
            return i
    return -1


class GridRowWrap(RowWrap):
    """Row grid_row of a QGridLayout: its items from column split on go to a new row under it (columns 0 ..)
    while there is not enough width (Status: the 14 axis speeds in two rows of 7).  The width needed is measured
    with sample values (VALUE_SAMPLE-like), so live numbers changing length never make the rows jump."""

    def __init__(self, host, grid, grid_row, split):
        self.host, self.row, self.grid = host, grid, grid
        self.need_fn = self.avail_fn = None
        self.wrapped = False
        self.grid_row, self.split = grid_row, split
        self.new_row = grid.rowCount()
        self.moved = []
        for c in range(split, grid.columnCount()):
            it = grid.itemAtPosition(grid_row, c)
            if it is not None and it.widget() is not None:
                self.moved.append((it.widget(), c))
        self.cols = {}                                     # column -> widgets, as on one row
        for i in range(grid.count()):
            r, c, rs, cs = grid.getItemPosition(i)
            w = grid.itemAt(i).widget()
            if w is not None and cs == 1:
                self.cols.setdefault(c, []).append(w)

    @staticmethod
    def _width(w):
        hint = w.minimumSizeHint().width()
        if isinstance(w, QLabel) and w.text():
            w.ensurePolished()
            name = w.text().split(" ")[0]
            if not name.endswith(":"):                     # 'X 0.00', 'Pitch 0.00': room for '-000.00'
                hint = max(hint, QFontMetrics(w.font()).horizontalAdvance(f"{name} -000.00") + 4)
        return hint

    def need(self):
        box = self.grid.parentWidget()
        if box is None or not box.isVisible():
            return 0                                       # Basic mode: the speeds are hidden
        widths = [max([self._width(w) for w in ws if not w.isHidden()] or [0]) for _, ws in sorted(self.cols.items())]
        used = [v for v in widths if v > 0]
        m = self.grid.contentsMargins()
        one_row = sum(used) + max(0, self.grid.horizontalSpacing()) * max(0, len(used) - 1) + m.left() + m.right()
        return one_row + (self.host.width() - box.width())

    def wrap(self, on):
        if on == self.wrapped:
            return
        for w, c in self.moved:
            self.grid.removeWidget(w)
            if on:
                self.grid.addWidget(w, self.new_row, c - self.split)
            else:
                self.grid.addWidget(w, self.grid_row, c)
        self.wrapped = on


def _items_width(lay, skip=()):
    """Minimum width of a box layout's shown items on one line (spacers count with their minimum)."""
    if lay is None:
        return 0, 0
    ws = []
    for i in range(lay.count()):
        it = lay.itemAt(i)
        if it.widget() is not None and (it.widget() in skip or it.widget().isHidden()):
            continue
        if it.spacerItem() is None and it.isEmpty():
            continue
        ws.append(it.minimumSize().width())
    n = len([v for v in ws if v > 0])
    return sum(ws), n


def _wrap_status_row(window):
    """Status card, when narrow:
       line 1  Status: Idle  Start Pause Resume Stop Release
       line 2  Speed Factor - +  Auto-sync Speed          Advanced mode
       line 3  Auto release  Auto pause  Include pause    (only if line 2 is still too wide)
       speeds  the 14 axis speeds in two rows of 7       (only if one row is too wide)"""
    card = window.card_status
    card_box = card.layout()
    hdr, first, right = None, -1, None
    for i in range(card_box.count()):
        lay = card_box.itemAt(i).layout()
        if lay is None:
            continue
        for k in range(lay.count()):
            sub = lay.itemAt(k).layout()
            if sub is not None and sub.indexOf(window.speed_controls_container) >= 0:
                hdr, first, right = lay, k, sub
    if hdr is None:
        raise RuntimeError("Status header row not found")
    left = hdr.itemAt(0).layout()
    line2 = QWidget(card)
    lay2 = QHBoxLayout(line2)
    lay2.setContentsMargins(0, 0, 0, 0)
    card_box.insertWidget(_index_of_layout(card_box, hdr) + 1, line2)
    wraps = [RowWrap(card, hdr, first, line2, lay2)]
    hdr_wrap = wraps[0]

    spd = window.speed_controls_container.layout()
    rel = getattr(window, "check_auto_release", None)
    if spd is not None and rel is not None and spd.indexOf(rel) > 0:
        line3 = QWidget(card)
        lay3 = QHBoxLayout(line3)
        lay3.setContentsMargins(0, 0, 0, 0)
        lay3.setSpacing(spd.spacing())
        lay3.setAlignment(Qt.AlignLeft)                    # together on the left, as on line 2
        card_box.insertWidget(card_box.indexOf(line2) + 1, line3)
        cm, bm = card.contentsMargins(), card_box.contentsMargins()

        def spd_need():
            """Card width for line 2 with Auto release ... Include pause on it (and line 1 too if not wrapped)."""
            w1, n1 = _items_width(spd)
            w3, n3 = _items_width(lay3)
            sm = spd.contentsMargins()
            box_w = w1 + w3 + max(0, spd.spacing()) * max(0, n1 + n3 - 1) + sm.left() + sm.right()
            wr, nr = _items_width(right, skip=(window.speed_controls_container,))
            rm = right.contentsMargins()
            line = box_w + wr + max(0, right.spacing()) * nr + rm.left() + rm.right()
            if not hdr_wrap.wrapped and left is not None:
                line += left.minimumSize().width() + max(0, hdr.spacing())
            return line + cm.left() + cm.right() + bm.left() + bm.right()

        wraps.append(RowWrap(card, spd, spd.indexOf(rel), line3, lay3, need_fn=spd_need,
                             visible_with=window.speed_controls_container))   # Basic mode hides them all

    metrics = getattr(window, "metrics_container", None)
    grid = metrics.layout() if metrics is not None else None
    if isinstance(grid, QGridLayout) and grid.columnCount() > 8:
        wraps.append(GridRowWrap(card, grid, 1, (grid.columnCount() + 1) // 2))
    return wraps


def _status_card_spacing(window):
    """Low window: the Status card's rows 8 px apart instead of 18 (about 50 px more for the graph)."""
    compact = getattr(window, "small_screen_compact", None)
    lay = window.card_status.layout()
    if compact is None or lay is None:
        return
    full = lay.spacing()
    compact.add_low_hook(lambda low: lay.setSpacing(min(8, full) if low else full))


def _wrap_planning_card(window):
    """Planning, Curve page: the Pauses & trigger card under the curve fields when they would be squeezed (their
    widths are Ignored so they shrink; on a laptop they shrank until labels and fields overlapped)."""
    pm = window.planning_modern
    body_w, left, card = pm.curve_body, pm.curve_left, pm.event_card
    body = body_w.layout()
    gbl = body_w.parentWidget().layout()
    line2 = QWidget(body_w.parentWidget())
    lay2 = QHBoxLayout(line2)
    lay2.setContentsMargins(0, 0, 0, 0)
    gbl.insertWidget(gbl.indexOf(body_w) + 1, line2)

    def need():
        return _natural_width(left) + max(0, body.spacing()) + card.width()

    return RowWrap(body_w, body, body.indexOf(card), line2, lay2, need_fn=need, avail_fn=body_w.width)


class _Wraps(QObject):
    """Re-checks every wrapped row when the page area is resized, a tab changes or a row's contents change."""

    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.rows = []
        self.pending = False
        window.page_scroll.viewport().installEventFilter(self)
        window.tabModules.currentChanged.connect(lambda *_: self.schedule())
        sub = getattr(window, "tabWidget", None)
        if sub is not None:
            sub.currentChanged.connect(lambda *_: self.schedule())

    def add(self, rw):
        self.rows.append(rw)
        rw.host.installEventFilter(self)
        sa = rw.scroll_area()
        if sa is not None:
            sa.viewport().installEventFilter(self)
        self.schedule()
        return rw

    def eventFilter(self, obj, ev):
        if ev.type() in (QEvent.Resize, QEvent.LayoutRequest, QEvent.Show):
            self.schedule()
        return False

    def schedule(self):
        if not self.pending:
            self.pending = True
            QTimer.singleShot(0, self.run)

    def run(self):
        self.pending = False
        try:
            for rw in self.rows:
                rw.update()
        except RuntimeError:
            pass                                 # window closing


# ---------------------------------------------------------------------------------------------------- header / nav
class _Compact(QObject):
    """Header: minimum widths as wide as the text (no clipped labels), compact when the window is narrow.
    Left column: buttons as high as the window allows (smaller icons, then icons only)."""

    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.header = window.findChild(QFrame, "logiqHeader")
        self.bar = getattr(window, "top_bar_frame", None)
        self.brand = window.findChild(QWidget, "logiqBrand")
        self.word = window.findChild(QLabel, "logiqHeaderWordMark")
        self.nav = window.findChild(QFrame, "logiqNav")
        self.nav_buttons = list(getattr(window, "nav_buttons", []))
        self.ip = getattr(window, "DuetIPAddress", None)
        self.sub = getattr(window, "tabWidget", None)            # Control: DYNAMIQ / KINETIQ sub-tabs
        self.compact = False
        self.low = False
        self.low_hooks = []                    # fn(low): parts built later (Status card) follow the low mode
        self.delta = 0
        self.nav_h = None
        self.brand_w = self.brand.maximumWidth() if self.brand is not None else 0
        self.ip_w = self.ip.minimumWidth() if self.ip is not None else 0
        self.nav_w = self.nav.maximumWidth() if self.nav is not None else 0
        self.nav_margins = self.nav.layout().contentsMargins() if self.nav is not None else None
        self.nav_narrow = max(NAV_NARROW, _nav_label_width(self.nav_buttons) + 2 * NAV_NARROW_SIDE + 1)
        bar_lay = self.bar.layout() if self.bar is not None else None
        self.bar_margins = bar_lay.contentsMargins() if bar_lay is not None else None
        self.sub_css = self.sub.styleSheet() if self.sub is not None else ""
        self.gap, self.gap_w = self._state_gap()
        self.orig_min = {}
        if self.bar is not None and self.bar.layout() is not None:
            lay = self.bar.layout()
            for i in range(lay.count()):
                w = lay.itemAt(i).widget()
                if w is not None and w is not self.ip and w.minimumWidth() != w.maximumWidth():
                    self.orig_min[w] = w.minimumWidth()
            self.bar.installEventFilter(self)
        self.header_wrap = None
        try:
            self.header_wrap = self._header_line2()
        except Exception as e:
            print(f"Small screen layout: header second line failed: {e}")
        window.installEventFilter(self)
        if self.nav is not None:
            self.nav.installEventFilter(self)
        self.pending = False
        self.schedule()

    def _header_line2(self):
        """Very narrow window (1920 x 1080 at 175 %, 1366 x 768 at 125 %): connection state, Touch Screen and
        Emergency STOP on a second header line instead of clipped."""
        state = getattr(self.window, "connect_status", None)
        lay = self.bar.layout() if self.bar is not None else None
        central = self.header.parentWidget() if self.header is not None else None
        box = central.layout() if central is not None else None
        if lay is None or state is None or box is None or box.indexOf(self.header) < 0:
            return None
        first = lay.indexOf(state)
        if first > 0 and lay.itemAt(first - 1).spacerItem() is not None:
            first -= 1                                     # the gap before the state goes along
        line2 = QFrame(central)
        line2.setObjectName("logiqHeaderLine2")
        line2.setAttribute(Qt.WA_StyledBackground, True)
        css = self.header.styleSheet()
        line2.setStyleSheet(css.replace("logiqHeader", "logiqHeaderLine2"))
        row2 = QHBoxLayout(line2)
        hm = self.header.layout().contentsMargins()
        row2.setContentsMargins(hm.left(), 0, hm.right(), hm.bottom())
        row2.setSpacing(lay.spacing())
        box.insertWidget(box.indexOf(self.header) + 1, line2)
        line2.installEventFilter(self)                     # state text changes: re-check the widths
        self.header_css = css
        return RowWrap(self.header, lay, first, line2, row2, avail_fn=self.window.width, fill_row1=True)

    def _wrap_header(self, on):
        hw = self.header_wrap
        hw.wrap(on)
        css = self.header_css
        QFrame.setStyleSheet(self.header, re.sub(r"border-bottom\s*:[^;]*;", "border-bottom: none;", css) if on else css)

    def _state_gap(self):
        state = getattr(self.window, "connect_status", None)
        lay = self.bar.layout() if self.bar is not None else None
        if lay is None or state is None:
            return None, 0
        i = lay.indexOf(state)
        if i > 0 and lay.itemAt(i - 1).spacerItem() is not None:
            s = lay.itemAt(i - 1).spacerItem()
            return s, s.sizeHint().width()
        return None, 0

    def eventFilter(self, obj, ev):
        if ev.type() in (QEvent.Resize, QEvent.Show, QEvent.LayoutRequest):
            self.schedule()
        return False

    def schedule(self):
        if not self.pending:
            self.pending = True
            QTimer.singleShot(0, self.update)

    def update(self):
        self.pending = False
        try:
            self._text_widths()
            self._header()
            self._low()
            self._nav()
        except RuntimeError:
            return
        # maximized before the header / left column got compact: the window may still run past the screen
        from fcn_create_gui.window_fit import keep_on_screen
        QTimer.singleShot(0, lambda: keep_on_screen(self.window))

    def _client_height(self):
        """Height the window has, never more than its screen offers (a window grown past the screen bottom by a
        large minimum height would otherwise keep that height)."""
        h = self.window.height()
        scr = self.window.screen()
        if scr is not None and self.window.isVisible():
            extra = max(0, self.window.frameGeometry().height() - self.window.height())
            h = min(h, scr.availableGeometry().height() - extra)
        return h

    def _low(self):
        """Low window: thinner header and lower Control sub-tab bar (about 40 px more for the pages)."""
        low = self._client_height() < LOW_HEIGHT
        if low == self.low:
            return
        self.low = low
        if self.bar_margins is not None:
            m = self.bar_margins
            self.bar.layout().setContentsMargins(m.left(), min(2, m.top()) if low else m.top(), m.right(),
                                                 min(2, m.bottom()) if low else m.bottom())
        if self.sub is not None:
            self.sub.setStyleSheet(self.sub_css + (SUBTAB_LOW_CSS if low else ""))
        for fn in self.low_hooks:
            fn(low)

    def add_low_hook(self, fn):
        self.low_hooks.append(fn)
        fn(self.low)

    def _text_widths(self):
        """Explicit minimum widths (160, 110, 90 ...) were narrower than the texts at the scaled fonts."""
        for w, orig in self.orig_min.items():
            need = max(orig, w.minimumSizeHint().width()) if not w.isHidden() else orig
            if w.minimumWidth() != need:
                w.setMinimumWidth(need)

    def _header(self):
        if self.header is None or self.header.layout() is None:
            return
        lay = self.header.layout()
        hw = self.header_wrap
        avail = self.window.width()
        cur = lay.minimumSize().width()
        # narrower: compact first, then the second line
        if not self.compact and avail < cur:
            self._set_compact(True)
            self.delta = max(0, cur - lay.minimumSize().width())
        if self.compact and hw is not None and not hw.wrapped and avail < lay.minimumSize().width():
            self._wrap_header(True)
        # wider: one line again, then full
        if hw is not None and hw.wrapped and avail >= hw.need() + HEADER_SLACK:
            self._wrap_header(False)
        if self.compact and not (hw is not None and hw.wrapped) \
                and avail >= lay.minimumSize().width() + self.delta + HEADER_SLACK:
            self._set_compact(False)

    def _set_compact(self, on):
        self.compact = on
        if self.word is not None:
            self.word.setVisible(not on)
        if self.brand is not None and self.brand_w:
            self.brand.setFixedWidth(BRAND_COMPACT if on else self.brand_w)
        if self.ip is not None and self.ip_w:
            self.ip.setMinimumWidth(min(self.ip_w, self.ip.minimumSizeHint().width() + 16) if on else self.ip_w)
        gap, _ = self._state_gap()                 # looked up again: a moved spacer is a new object
        if gap is not None and self.gap_w:
            gap.changeSize(12 if on else self.gap_w, 0, QSizePolicy.Fixed, QSizePolicy.Minimum)
            self.bar.layout().invalidate()
        if self.nav is not None and self.nav_w and self.nav_margins is not None:
            m = self.nav_margins
            self.nav.setFixedWidth(self.nav_narrow if on else self.nav_w)
            side = NAV_NARROW_SIDE if on else m.left()
            self.nav.layout().setContentsMargins(side, m.top(), NAV_NARROW_SIDE if on else m.right(), m.bottom())
        self.header.layout().activate()

    def _nav(self):
        if self.nav is None or not self.nav_buttons:
            return
        lay = self.nav.layout()
        m = lay.contentsMargins()
        n = len(self.nav_buttons)
        avail = self.nav.height()
        if self.header is not None and self.window.isVisible():
            avail = min(avail, self._client_height() - self.header.height())
        h = (avail - m.top() - m.bottom() - max(0, lay.spacing()) * (n - 1)) // n
        h = max(NAV_MIN, min(NAV_FULL, h))
        if h == self.nav_h:
            return
        self.nav_h = h
        icon = NAV_ICON if h >= NAV_FULL - 4 else NAV_ICON_LOW
        style = Qt.ToolButtonTextUnderIcon if h >= NAV_TEXT_MIN else Qt.ToolButtonIconOnly
        for b in self.nav_buttons:
            b.setMinimumHeight(h)
            b.setIconSize(QSize(icon, icon))
            b.setToolButtonStyle(style)


HEADER_FACTOR = 0.7             # header height: 70 % of the logiq_shell one (user request, all screens)
HEADER_PAD = 5                  # px above and below the header's buttons


def _slim_header(window):
    """Header at HEADER_FACTOR of its height: first the padding (header 8 + 8 -> 5 + 5, connection bar 10 + 10 ->
    0 + 0), then, only if still higher, the fixed-height buttons of the bar."""
    header = window.findChild(QFrame, "logiqHeader")
    bar = getattr(window, "top_bar_frame", None)
    if header is None or header.layout() is None or bar is None or bar.layout() is None:
        raise RuntimeError("header not found")
    target = round(header.sizeHint().height() * HEADER_FACTOR)
    hm, bm = header.layout().contentsMargins(), bar.layout().contentsMargins()
    header.layout().setContentsMargins(hm.left(), HEADER_PAD, hm.right(), HEADER_PAD)
    bar.layout().setContentsMargins(bm.left(), 0, bm.right(), 0)
    header.layout().activate()
    room = target - 2 * HEADER_PAD
    if header.sizeHint().height() > target and room > 30:
        for w in bar.findChildren(QWidget, options=Qt.FindDirectChildrenOnly):
            if w.minimumHeight() == w.maximumHeight() and w.maximumHeight() > room:
                w.setFixedHeight(room)
    window.header_target_height = target


_SCALED_PROPS = re.compile(r"(?<![\w-])(border-radius|border-top-right-radius|border-bottom-right-radius|padding|width)"
                           r"(\s*:\s*)([^;}]*)")
_ORIG_CSS = "kq_original_css"               # logiq_theme keeps the sheet as set (before its colour remap) here


def _scaled_css(css, factor, font_px=None):
    """css at factor: font sizes (or all font_px), corner radii, paddings and widths (not borders or min-*)."""
    if not isinstance(css, str) or not css:
        return css

    def px(m):
        return f"{max(0, round(int(m.group(1)) * factor))}px"

    css = re.sub(r"font-size\s*:\s*(\d+)px",
                 lambda m: f"font-size: {font_px or max(1, round(int(m.group(1)) * factor))}px", css)
    return _SCALED_PROPS.sub(lambda m: m.group(1) + m.group(2) + re.sub(r"(\d+)px", px, m.group(3)), css)


def _sheet(w):
    css = w.property(_ORIG_CSS)
    return css if isinstance(css, str) and css else w.styleSheet()


def _keep_scaled_sheet(w, factor, font_px=None):
    """Scale w's stylesheet now and every one set later (the connection state is restyled on every connection
    change, Touch Screen on every toggle), for this widget only."""
    QWidget.setStyleSheet(w, _scaled_css(_sheet(w), factor, font_px))
    w.setStyleSheet = lambda css, w=w: QWidget.setStyleSheet(w, _scaled_css(css, factor, font_px))


def _header_controls(window):
    """Header logo, LogIQ, IP field, Connect, DYNAMIQ / KINETIQ, connection state, Touch Screen and Emergency STOP at
    HEADER_CONTROLS of their size: height, width, text, icon, corners and the gaps between them."""
    f = HEADER_CONTROLS
    header = window.findChild(QFrame, "logiqHeader")
    bar = getattr(window, "top_bar_frame", None)
    if header is None or header.layout() is None or bar is None or bar.layout() is None:
        raise RuntimeError("header not found")
    hl = header.layout()
    m = hl.contentsMargins()
    hl.setContentsMargins(round(m.left() * f), m.top(), round(m.right() * f), m.bottom())
    hl.setSpacing(round(hl.spacing() * f))

    brand = window.findChild(QWidget, "logiqBrand")
    if brand is not None and brand.layout() is not None:
        from PySide6.QtGui import QPixmap
        from fcn_create_gui.logiq_shell import _logo_path
        for lbl in brand.findChildren(QLabel):
            if lbl.objectName() == "logiqHeaderWordMark":
                QWidget.setStyleSheet(lbl, _scaled_css(_sheet(lbl), f))
                continue
            pix = lbl.pixmap()
            src = QPixmap(_logo_path())
            if pix is None or pix.isNull() or src.isNull():
                continue
            side = round(max(pix.width(), pix.height()) / max(pix.devicePixelRatio(), 1.0) * f)
            dpr = window.screen().devicePixelRatio() if window.screen() is not None else 1.0
            logo = src.scaled(round(side * dpr), round(side * dpr), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            logo.setDevicePixelRatio(dpr)            # sharp on a scaled screen
            lbl.setPixmap(logo)
        brand.layout().setSpacing(round(brand.layout().spacing() * f))
        brand.layout().activate()
        brand.setFixedWidth(brand.layout().sizeHint().width())    # logo and LogIQ, no gap between them

    lay = bar.layout()
    lay.setSpacing(round(lay.spacing() * f))
    controls = [lay.itemAt(i).widget() for i in range(lay.count()) if lay.itemAt(i).widget() is not None]
    controls = [w for w in controls if not w.isHidden()]
    height = round(max(w.minimumHeight() for w in controls) * f)
    connect = getattr(window, "setDuetIP", None)
    for w in controls:
        if w is connect:                           # icon only, its own fixed style (logiq_shell._connect_icon)
            QWidget.setStyleSheet(w, _scaled_css(_sheet(w), f))
            w.setFixedWidth(round(w.maximumWidth() * f))
            w.setIconSize(w.iconSize() * f)
        else:
            _keep_scaled_sheet(w, f, HEADER_FONT)
            if w.minimumWidth() > 0:
                w.setMinimumWidth(round(w.minimumWidth() * f))
        w.setFixedHeight(height)
        le = w.lineEdit() if isinstance(w, QComboBox) else None
        if le is not None:                         # IP field: the launcher gave its line edit 55 px and 18 px text
            QWidget.setStyleSheet(le, _scaled_css(_sheet(le), f, HEADER_FONT))
            le.setMinimumHeight(0)
    state = getattr(window, "connect_status", None)  # the gap before the connection state
    i = lay.indexOf(state) if state is not None else -1
    gap = lay.itemAt(i - 1).spacerItem() if i > 0 else None
    if gap is not None:
        gap.changeSize(round(gap.sizeHint().width() * f), 0, QSizePolicy.Fixed, QSizePolicy.Minimum)
    lay.invalidate()
    hl.activate()


def _nav_label_width(buttons):
    """Widest left column label in bold (the selected button) plus the button's side padding."""
    from PySide6.QtGui import QFont
    need = 0
    for b in buttons:
        b.ensurePolished()                         # the column's stylesheet font
        font = QFont(b.font())
        font.setWeight(QFont.DemiBold)
        need = max(need, QFontMetrics(font).horizontalAdvance(b.text()) + 6)
    return need


def _nav_size(window):
    """Left column at NAV_SCALE: width, margins, icons, text, button height and corners."""
    s = NAV_SCALE
    nav = window.findChild(QFrame, "logiqNav")
    buttons = list(getattr(window, "nav_buttons", []))
    if nav is None or nav.layout() is None or not buttons:
        raise RuntimeError("left column not found")
    nav.ensurePolished()            # else Qt keeps the sheet it parsed for the buttons (they stayed at 15 px)
    QFrame.setStyleSheet(nav, _scaled_css(_sheet(nav), s))
    lay = nav.layout()
    m = lay.contentsMargins()
    lay.setContentsMargins(round(m.left() * s), round(m.top() * s), round(m.right() * s), round(m.bottom() * s))
    lay.setSpacing(round(lay.spacing() * s))
    m = lay.contentsMargins()
    nav.setFixedWidth(max(round(nav.maximumWidth() * s), _nav_label_width(buttons) + m.left() + m.right() + 1))
    for b in buttons:
        b.setIconSize(QSize(NAV_ICON, NAV_ICON))
        b.setMinimumHeight(NAV_FULL)


def _wrap_trigger_row(window):
    """Planning, Pause and Trigger tab: the card above the Position-Gated Trigger panel when they do not fit side
    by side."""
    pcl = window.planning_curve_layout
    content, row, gate = pcl.trigger_content, pcl.trigger_row, pcl.gate_box
    clay = content.layout()
    line2 = QWidget(content)
    lay2 = QHBoxLayout(line2)
    lay2.setContentsMargins(0, 0, 0, 0)
    clay.insertWidget(_index_of_layout(clay, row) + 1, line2)
    return RowWrap(content, row, row.indexOf(gate), line2, lay2, fill_row1=True)    # card stays on the left


# ---------------------------------------------------------------------------------------------------- entry
def apply_small_screen_layout(window):
    """Each part is independent: a part that fails is reported on stdout and the others are still applied."""
    if getattr(window, "small_screen_layout", False):
        return window
    window.small_screen_layout = True

    def part(name, fn):
        try:
            return fn()
        except Exception as e:                   # never stops the window from being built
            print(f"Small screen layout: {name} failed: {e}")
            return None

    wraps = None
    if part("page scroll", lambda: _page_scroll(window)) is not None:
        wraps = _Wraps(window)
        window.small_screen_wraps = wraps
    part("step buttons", lambda: _step_buttons_shrink(window))
    part("control splitter", lambda: _control_splitter(window))
    part("position row height", lambda: _position_row_height(window))
    part("KINETIQ fields", lambda: _kinetiq_fields(window))
    if wraps is not None:
        part("DYNAMIQ row", lambda: wraps.add(_wrap_frame_row(window.btn_goto_lung, align_right=True)))
        # KINETIQ: Go to / Home / Trigger (used all the time) right under the table, the dimensions line last
        part("KINETIQ row", lambda: wraps.add(_wrap_frame_row(window.btn_go_to, from_separator=True, above=True)))
        done = set()

        def lazy_tab(index):                     # Status and Planning are built on their first opening
            if index == 1 and "status" not in done and getattr(window, "card_status", None) is not None:
                done.add("status")
                from fcn_create_gui.status_split import apply_status_split
                part("Status split", lambda: apply_status_split(window))   # first: the card moves
                part("Status rows", lambda: [wraps.add(rw) for rw in _wrap_status_row(window)])
                part("Status card spacing", lambda: _status_card_spacing(window))
            if index == 3 and "planning" not in done and getattr(window, "planning_modern", None) is not None \
                    and getattr(window.planning_modern, "curve_body", None) is not None:
                done.add("planning")
                from fcn_create_gui.planning_curve_layout import apply_planning_curve_layout
                part("Planning curve layout", lambda: apply_planning_curve_layout(window))
                pm = window.planning_modern
                if pm.curve_body.layout().indexOf(pm.event_card) >= 0:          # card still next to the fields
                    part("Planning card", lambda: wraps.add(_wrap_planning_card(window)))
                else:
                    part("Pause and Trigger row", lambda: wraps.add(_wrap_trigger_row(window)))

        # direct call: on_main_tab_changed (connected earlier) has built the tab; no frame of the old layout
        window.tabModules.currentChanged.connect(lazy_tab)
    part("header height", lambda: _slim_header(window))     # before _Compact: it keeps these margins as 'full'
    part("header controls", lambda: _header_controls(window))      # before _Compact: widths it keeps as 'full'
    part("left column size", lambda: _nav_size(window))
    window.small_screen_compact = part("header / left column", lambda: _Compact(window))
    return window
