"""
White Planning sub-tabs (request K: "trigger tools settings table ... everything has grey background remove it").

``whiten_planning_subtabs(pm)`` (called by tab_planning_modern.ModernPlanning.build()) gives every page of the
Planning sub-tab widget (Curve, the hidden Periodic, Trigger, Tools, Settings, Table) the look of the Status page:
white pages, scroll areas and viewports, white sub-tab strip and pane, group boxes as white cards (1px #cfd8dc
border, radius 6, bold 16 px title as before).  Inputs keep their own borders (no rule touches them).

Inputs (spin boxes, line edits, combos) keep the Fusion look and their borders; only their palette is whitened
(``whiten_inputs``): a disabled box is white with grey text instead of a filled grey box (the Trigger page's Min / Max
/ From / To boxes are disabled until 'Use' / 'Subset' is ticked), a plain combo is white instead of the light-grey
button gradient.  Widgets with their own style sheet are left alone (their sheet decides).  The Table header is white
with thin #cfd8dc lines.

The Settings pages (Lung Phantom, Motion Platform) show their fields in three columns instead of two
(``settings_three_columns``), so the Settings sub-tab fits without scrolling at 2048x1232.

Everything else is one style sheet on the sub-tab widget (object name 'pmSubTabs'), scoped by that name and by the
dynamic property pmWhite on the container widgets, so no other tab of the window is affected.  The Curve Options
group box keeps its own (more specific) card style from tab_planning_modern.
"""

from PySide6.QtCore import Qt, QObject, QEvent
from PySide6.QtGui import QPalette, QColor
from PySide6.QtWidgets import (QWidget, QScrollArea, QStackedWidget, QAbstractSpinBox, QLineEdit, QComboBox,
                               QGridLayout)

from fcn_create_gui.tab_status_modern import CARD_BORDER

TAB_WIDGET_NAME = 'pmSubTabs'
WHITE = '#ffffff'
DISABLED_TEXT = '#90a4ae'          # the Status page's disabled field text

SUBTAB_STYLE = (
    "QTabWidget#pmSubTabs { background: #ffffff; }"
    "QTabWidget#pmSubTabs::pane { background: #ffffff; border: 1px solid " + CARD_BORDER + "; top: -1px; }"
    "QTabWidget#pmSubTabs::tab-bar { left: 0px; }"
    "QTabWidget#pmSubTabs > QTabBar { background: #ffffff; }"
    "QTabWidget#pmSubTabs QWidget[pmWhite=\"true\"] { background: #ffffff; }"
    "QTabWidget#pmSubTabs QScrollArea[pmWhite=\"true\"] { background: #ffffff; border: none; }"
    "QTabWidget#pmSubTabs QGroupBox { background: #ffffff; border: 1px solid " + CARD_BORDER + "; "
    "border-radius: 6px; margin-top: 24px; font-weight: bold; font-size: 16px; padding-top: 4px; }"
    "QTabWidget#pmSubTabs QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; left: 6px; "
    "top: 2px; padding: 0px 4px; color: #263238; background: transparent; }"
    "QTabWidget#pmSubTabs QHeaderView::section { background: #ffffff; color: #263238; font-weight: bold; "
    "border: none; border-right: 1px solid #e0e6ea; border-bottom: 1px solid " + CARD_BORDER + "; padding: 2px 4px; }"
    "QTabWidget#pmSubTabs QTableCornerButton::section { background: #ffffff; border: none; "
    "border-bottom: 1px solid " + CARD_BORDER + "; }"
)


def _white_palette(wd, button=False):
    pal = QPalette(wd.palette())
    white = QColor(WHITE)
    pal.setColor(QPalette.Disabled, QPalette.Base, white)
    pal.setColor(QPalette.Disabled, QPalette.Window, white)
    pal.setColor(QPalette.Disabled, QPalette.Text, QColor(DISABLED_TEXT))
    pal.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(DISABLED_TEXT))
    if button:                         # a read-only combo is drawn as a button (Fusion: light-grey gradient)
        for grp in (QPalette.Active, QPalette.Inactive, QPalette.Disabled):
            pal.setColor(grp, QPalette.Button, white)
    wd.setPalette(pal)


def _is_input(wd):
    if isinstance(wd, QLineEdit) and isinstance(wd.parentWidget(), (QAbstractSpinBox, QComboBox)):
        return False                   # the inner edit of a box: its box handles it
    return isinstance(wd, (QAbstractSpinBox, QLineEdit, QComboBox))


def _whiten_one(wd):
    """One input without a style sheet of its own: white palette (False when skipped)."""
    if not _is_input(wd) or (wd.styleSheet() or "").strip():
        return False
    is_combo = isinstance(wd, QComboBox)
    _white_palette(wd, button=is_combo and not wd.isEditable())
    inner = wd.lineEdit()
    if inner is not None:
        _white_palette(inner)
    return True


class _InputWhitener(QObject):
    """Event filter on the containers of a page: an input polished later (e.g. the Trigger page's per-axis rows,
    rebuilt on a device switch, or a box re-polished after a style sheet change) is whitened as well."""

    def eventFilter(self, obj, event):
        if event.type() == QEvent.ChildPolished:
            child = event.child()
            if isinstance(child, QWidget):
                if _is_input(child):
                    _whiten_one(child)
                else:
                    self.watch(child)
        return False

    def watch(self, wd):
        if not _is_input(wd) and not wd.property('pmWhiteWatched'):
            wd.setProperty('pmWhiteWatched', True)
            wd.installEventFilter(self)


def whiten_inputs(root, whitener=None):
    """White (also when disabled) spin boxes, line edits and combos under ``root`` that have no style sheet of
    their own; their borders and the Fusion look are kept.  With ``whitener`` (an _InputWhitener) the containers are
    watched, so inputs created later get the same palette.  Returns the input widgets changed."""
    done = []
    if whitener is not None:
        whitener.watch(root)
    for wd in root.findChildren(QWidget):
        if _whiten_one(wd):
            done.append(wd)
        elif whitener is not None and not _is_input(wd) and not isinstance(wd.parentWidget(), (QAbstractSpinBox,
                                                                                               QComboBox)):
            whitener.watch(wd)
    return done


SETTINGS_COLUMNS = 3


def settings_three_columns(win, columns=SETTINGS_COLUMNS):
    """The fields of each Settings page (a QGridLayout of label + box cells) re-flowed in reading order into
    ``columns`` equal columns (layout only: the same widgets, order and handlers).  Returns the pages changed."""
    stack = getattr(win, 'settings_stack', None)
    done = []
    if stack is None:
        return done
    for j in range(stack.count()):
        grid = stack.widget(j).layout()
        if not isinstance(grid, QGridLayout) or grid.columnCount() >= columns:
            continue
        cells = []
        for i in range(grid.count()):
            r, c, rs, cs = grid.getItemPosition(i)
            if rs != 1 or cs != 1:
                cells = None               # a spanning cell: not the simple field grid, left as it is
                break
            cells.append((r, c, i))
        if not cells or len(cells) <= columns:
            continue
        # Take the items out (Python then owns and frees them) and put their CONTENTS back.  Re-adding the same
        # QWidgetItem objects (itemAt + addItem) left PySide wrappers that Qt later freed without telling PySide;
        # a new Qt object at such an address then crashed in shiboken (LogIQ access violation, 12 Nov 2026).
        taken = [grid.takeAt(0) for _ in range(grid.count())]          # index order, as getItemPosition(i)
        old_cols = max(c for _r, c, _i in cells) + 1
        for k, (_r, _c, i) in enumerate(sorted(cells)):
            it, row, col = taken[i], k // columns, k % columns
            if it.layout() is not None:
                grid.addLayout(it.layout(), row, col, alignment=it.alignment())
            elif it.widget() is not None:
                grid.addWidget(it.widget(), row, col, alignment=it.alignment())
            elif it.spacerItem() is not None:
                grid.addItem(it.spacerItem(), row, col)
        del taken
        for c in range(max(columns, old_cols)):
            grid.setColumnStretch(c, 1 if c < columns else 0)
        done.append(stack.widget(j))
    return done


def _mark(widget):
    widget.setProperty('pmWhite', True)
    widget.setAttribute(Qt.WA_StyledBackground, True)


def whiten_planning_subtabs(pm):
    w = pm.win
    tw = getattr(w, 'create_settings_tab_widget', None)
    if tw is None:
        return None
    if not tw.objectName():
        tw.setObjectName(TAB_WIDGET_NAME)
    if tw.objectName() != TAB_WIDGET_NAME:
        return None
    tw.setAttribute(Qt.WA_StyledBackground, True)      # the strip right of the sub-tabs: white too
    marked = []
    for st in tw.findChildren(QStackedWidget, options=Qt.FindDirectChildrenOnly):
        _mark(st)
        marked.append(st)
    for i in range(tw.count()):
        page = tw.widget(i)
        _mark(page)
        marked.append(page)
        for sc in page.findChildren(QScrollArea):
            if sc is getattr(pm, 'panel_scroll', None):
                continue
            for wd in (sc, sc.viewport(), sc.widget()):
                if wd is not None:
                    _mark(wd)
                    marked.append(wd)
        # stacked pages inside a page (e.g. the per-device Settings pages)
        for st in page.findChildren(QStackedWidget):
            _mark(st)
            marked.append(st)
            for j in range(st.count()):
                _mark(st.widget(j))
                marked.append(st.widget(j))
    old = tw.styleSheet() or ""
    if SUBTAB_STYLE not in old:
        tw.setStyleSheet(old + "\n" + SUBTAB_STYLE)
    tw.tabBar().setAutoFillBackground(False)
    pm.white_widgets = marked
    pm.white_inputs = []
    pm.input_whitener = _InputWhitener(tw)
    pm.settings_reflowed = settings_three_columns(w)
    for i in range(tw.count()):
        pm.white_inputs += whiten_inputs(tw.widget(i), pm.input_whitener)
    return marked
