"""
Status tab layout: the Reference panel (curve toggles, view limits, Clear Plot Data, Record) on its own on the
right, as high as the status card and the graph together, and two drag bars:

* vertical bar between the left column and the Reference panel: drag left / right for a wider / narrower panel;
* horizontal bar between the status card and the graph: drag up for a taller graph (the card then scrolls).
  The bar never goes below the card's natural height (no empty space under the card).

    from fcn_create_gui.status_split import apply_status_split
    apply_status_split(window)        # once, after build_status_tab + modernise_status_tab

Layout only: the same widgets move into the splitters; their logic, names and signals stay as they are.  The plot
navigation row (Reset view, Back, Forward, Pan, Zoom, Save) stays under the graph.
"""
from PySide6.QtCore import QEvent, QObject, Qt, QTimer
from PySide6.QtWidgets import QFrame, QScrollArea, QSizePolicy, QSplitter, QWidgetItem

HANDLE = 12                     # px, both bars (touch friendly)
PANEL_MIN = 150                 # px, the Reference panel never gets narrower than this
QT_MAX = 16777215

SPLITTER_CSS = """
    QSplitter::handle:vertical {
        background-color: #cfd8dc;
        border-top: 1px solid #b0bec5;
        border-bottom: 1px solid #b0bec5;
        margin: 2px 0px;
    }
    QSplitter::handle:horizontal {
        background-color: #cfd8dc;
        border-left: 1px solid #b0bec5;
        border-right: 1px solid #b0bec5;
        margin: 0px 2px;
    }
    QSplitter::handle:vertical:hover, QSplitter::handle:vertical:pressed,
    QSplitter::handle:horizontal:hover, QSplitter::handle:horizontal:pressed {
        background-color: #1976d2;
    }
"""


def _layout_holding(layout, widget):
    """The (sub-)layout of layout that holds widget, or None."""
    if layout is None:
        return None
    if layout.indexOf(widget) >= 0:
        return layout
    for i in range(layout.count()):
        sub = layout.itemAt(i).layout()
        found = _layout_holding(sub, widget)
        if found is not None:
            return found
    return None


def _splitter(orientation, parent, name):
    sp = QSplitter(orientation, parent)
    sp.setObjectName(name)
    sp.setChildrenCollapsible(False)
    sp.setHandleWidth(HANDLE)
    sp.setStyleSheet(SPLITTER_CSS)
    return sp


class StatusSplit(QObject):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        page = window.tab_status
        lay = page.layout()
        self.card = window.card_status
        st = getattr(window, "status_modern", None)
        self.panel = getattr(st, "side_card", None)
        self.panel_scroll = getattr(st, "panel_scroll", None)
        self.plot_box = window.statusCanvas.parentWidget()
        if lay is None or self.panel is None or lay.indexOf(self.card) < 0 or lay.indexOf(self.plot_box) < 0:
            raise RuntimeError("Status page layout not as expected")

        # the Reference panel out of the graph row
        row = _layout_holding(self.plot_box.layout(), self.panel)
        if row is not None:
            row.removeWidget(self.panel)

        i = lay.indexOf(self.card)
        lay.removeWidget(self.card)
        lay.removeWidget(self.plot_box)

        # status card in a scroll area: dragging the bar up keeps its top row (Start ... Release) in view
        self.card_scroll = QScrollArea(page)
        self.card_scroll.setObjectName("statusCardScroll")
        self.card_scroll.setWidgetResizable(True)
        self.card_scroll.setFrameShape(QFrame.NoFrame)
        self.card_scroll.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.card_scroll.setStyleSheet("QScrollArea#statusCardScroll { background: transparent; border: none; }")
        self.card.setSizePolicy(self.card.sizePolicy().horizontalPolicy(), QSizePolicy.Maximum)
        self.card_scroll.setWidget(self.card)

        self.vsplit = _splitter(Qt.Vertical, page, "statusVSplit")
        self.vsplit.addWidget(self.card_scroll)
        self.vsplit.addWidget(self.plot_box)
        self.vsplit.setStretchFactor(0, 0)
        self.vsplit.setStretchFactor(1, 1)
        self.vsplit.handle(1).setToolTip("Drag up for a taller graph")

        self.hsplit = _splitter(Qt.Horizontal, page, "statusHSplit")
        self.hsplit.addWidget(self.vsplit)
        self.hsplit.addWidget(self.panel)
        self.hsplit.setStretchFactor(0, 1)
        self.hsplit.setStretchFactor(1, 0)
        self.hsplit.handle(1).setToolTip("Drag left / right to make the Reference panel wider / narrower")

        mx = self.panel.maximumWidth()
        self.panel_w0 = mx if mx < QT_MAX else max(self.panel.width(), 236)      # its fixed width so far
        self.panel.setMinimumWidth(self._panel_min())
        self.panel.setMaximumWidth(QT_MAX)
        # the card pane never gets lower than the card's first row (Status, Start ... Release)
        cl = self.card.layout()
        if cl is not None and cl.count():
            m = cl.contentsMargins()
            self.card_scroll.setMinimumHeight(cl.itemAt(0).minimumSize().height() + m.top() + m.bottom())

        lay.insertWidget(i, self.hsplit, 1)
        for w in (self.card, self.plot_box, self.panel, self.vsplit, self.card_scroll):
            w.show()

        self.moved_v = False
        self.moved_h = False
        self.vsplit.splitterMoved.connect(lambda *_: setattr(self, "moved_v", True))
        self.hsplit.splitterMoved.connect(lambda *_: setattr(self, "moved_h", True))
        self.card.installEventFilter(self)            # Basic / Advanced mode, wrapped rows: card height changes
        self.hsplit.installEventFilter(self)
        self.pending = False
        self.schedule()

    def _panel_min(self):
        """Narrowest Reference panel whose contents are not squeezed (its own scroll area never scrolls
        sideways)."""
        need = PANEL_MIN
        sc = self.panel_scroll
        if sc is not None and sc.widget() is not None:
            m = self.panel.layout().contentsMargins() if self.panel.layout() is not None else None
            side = (m.left() + m.right()) if m is not None else 0
            need = max(need, QWidgetItem(sc.widget()).minimumSize().width()
                       + sc.verticalScrollBar().sizeHint().width() + side + 2)
        return need

    # ------------------------------------------------------------------ sizes
    def eventFilter(self, obj, ev):
        if ev.type() in (QEvent.LayoutRequest, QEvent.Resize, QEvent.Show):
            self.schedule()
        return False

    def schedule(self):
        if not self.pending:
            self.pending = True
            QTimer.singleShot(0, self.update)

    def update(self):
        self.pending = False
        try:
            self._card_height()
            self._first_sizes()
        except RuntimeError:
            pass                                       # window closing

    def _card_height(self):
        """The top pane is at most as high as the card (the bar only moves up from there)."""
        h = QWidgetItem(self.card).sizeHint().height()
        sizes = self.vsplit.sizes()
        if h <= 0 or len(sizes) != 2:
            return
        old_max = self.card_scroll.maximumHeight()
        was_full = sizes[0] >= min(old_max, QT_MAX) - 2         # the whole card was shown
        if old_max != h:
            self.card_scroll.setMaximumHeight(h)
        total = sizes[0] + sizes[1]
        if sizes[0] > h:                               # lower card (Basic mode): QSplitter keeps the old height
            self.vsplit.setSizes([h, total - h])
        elif was_full and h > sizes[0] and self.vsplit.isVisible():   # taller card (Advanced): still all shown
            top = min(h, total - QWidgetItem(self.plot_box).minimumSize().height())
            if top > sizes[0]:
                self.vsplit.setSizes([top, total - top])

    def _first_sizes(self):
        """Until the user drags: card at its natural height, Reference panel at its former width."""
        if not self.hsplit.isVisible():
            return
        if not self.moved_h:
            total = sum(self.hsplit.sizes())
            right = max(self.panel.minimumWidth(), self.panel_w0)
            if total > right and abs(self.hsplit.sizes()[1] - right) > 1:
                self.hsplit.setSizes([total - right, right])
        if not self.moved_v:
            total = sum(self.vsplit.sizes())
            top = min(self.card_scroll.maximumHeight(), total - QWidgetItem(self.plot_box).minimumSize().height())
            top = max(top, self.card_scroll.minimumSizeHint().height())
            if total > top > 0 and abs(self.vsplit.sizes()[0] - top) > 1:
                self.vsplit.setSizes([top, total - top])


def apply_status_split(window):
    split = getattr(window, "status_split", None)
    if split is not None:
        return split
    window.status_split = StatusSplit(window)
    return window.status_split
