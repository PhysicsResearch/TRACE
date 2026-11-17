"""
Advanced mode switches on the Control page (KINETIQ) and the Status page: an outlined button, filled when on.

    from fcn_create_gui.advanced_mode import apply_advanced_mode
    apply_advanced_mode(window)          # after apply_logiq_shell, before apply_small_screen_layout

Control, KINETIQ: an 'Advanced mode' button left of 'Trigger'.
  Off (Basic): the actuator rows A | B and C | D, Home LAT / Home SI / Home AP and the KINETIQ dimensions /
  Offset Rot. fields are hidden.  On: everything as before.
Status: the 'Advanced mode' check box gets the same look (outline, filled when on).  It is still the same check
  box, so its handlers (Basic / Advanced layout, saving the setting) are unchanged.
Both start OFF at every start of the app: Status no longer comes back in the mode of the last session.

Only visibility changes: hidden fields keep their values and keep updating.
"""
from PySide6.QtCore import QEvent, QObject, Qt, QTimer
from PySide6.QtWidgets import QCheckBox, QFrame, QPushButton, QSizePolicy, QWidget

from fcn_create_gui.logiq_shell import NAV_HOVER, OLIVE, OLIVE_DARK

ACTUATOR_ROWS = (4, 5)          # KINETIQ table rows 'A | B' and 'C | D' (work_zero_ui._add_actuator_rows)
HOME_GROUPS = ("LAT", "SI", "AP")

BUTTON_CSS = f"""
    QPushButton#controlAdvancedMode {{ background-color: transparent; color: {OLIVE}; border: 2px solid {OLIVE};
                                      border-radius: 6px; font-weight: bold; font-size: 16px; padding: 0px 14px; }}
    QPushButton#controlAdvancedMode:hover {{ background-color: {NAV_HOVER}; }}
    QPushButton#controlAdvancedMode:checked {{ background-color: {OLIVE}; color: #ffffff; }}
    QPushButton#controlAdvancedMode:checked:hover {{ background-color: {OLIVE_DARK}; }}
    QPushButton#controlAdvancedMode:pressed {{ padding-top: 3px; padding-left: 3px; }}
"""

CHECK_CSS = f"""
    QCheckBox#statusAdvancedMode {{ background-color: transparent; color: {OLIVE}; border: 2px solid {OLIVE};
                                   border-radius: 6px; font-weight: bold; font-size: 16px; padding: 4px 14px;
                                   spacing: 0px; }}
    QCheckBox#statusAdvancedMode::indicator {{ width: 0px; height: 0px; border: none; image: none; }}
    QCheckBox#statusAdvancedMode:hover {{ background-color: {NAV_HOVER}; }}
    QCheckBox#statusAdvancedMode:checked {{ background-color: {OLIVE}; color: #ffffff; }}
    QCheckBox#statusAdvancedMode:checked:hover {{ background-color: {OLIVE_DARK}; }}
"""


def _is_line(w):
    return isinstance(w, QFrame) and w.frameShape() in (QFrame.VLine, QFrame.HLine)


class ControlAdvanced(QObject):
    """KINETIQ 'Advanced mode' button and what it shows / hides."""

    def __init__(self, window):
        super().__init__(window)
        self.window = w = window
        self.trigger = w.findChild(QPushButton, "triggerToggle")
        go = w.btn_go_to
        self.frame = go.parentWidget()                   # KINETIQ dimensions + button row
        row = self.frame.layout()
        if self.trigger is None or row is None or row.indexOf(self.trigger) < 0:
            raise RuntimeError("KINETIQ button row not as expected")

        # A | B and C | D rows of the KINETIQ table (the vertical Set zero spans rows 1-5: it stays)
        self.grid = w.POS_CURR_LATAXIS.parentWidget().layout()
        self.row_widgets = []
        for i in range(self.grid.count()):
            r, c, rs, cs = self.grid.getItemPosition(i)
            wd = self.grid.itemAt(i).widget()
            if wd is not None and r in ACTUATOR_ROWS and rs == 1 and not wd.isHidden():
                self.row_widgets.append(wd)
        self.row_stretch = {r: self.grid.rowStretch(r) for r in ACTUATOR_ROWS}
        self.homes = [b for b in (getattr(w, f"HOME_{g}_PLATFORM", None) for g in HOME_GROUPS)
                      if b is not None and not b.isHidden()]
        # KINETIQ dimensions / Offset Rot.: everything before 'Go to ...' (the last one is the separator line)
        i_go = row.indexOf(go)
        self.dims = [row.itemAt(k).widget() for k in range(i_go)
                     if row.itemAt(k).widget() is not None and not row.itemAt(k).widget().isHidden()]
        self.sep = self.dims[-1] if self.dims and _is_line(self.dims[-1]) else None

        btn = QPushButton("Advanced mode", self.trigger.parentWidget())
        btn.setObjectName("controlAdvancedMode")
        btn.setCheckable(True)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setToolTip("Advanced mode: actuators A B C D, Home LAT / SI / AP and the KINETIQ dimensions")
        btn.setMinimumHeight(self.trigger.minimumHeight())
        btn.setSizePolicy(btn.sizePolicy().horizontalPolicy(), QSizePolicy.Fixed)
        QPushButton.setStyleSheet(btn, BUTTON_CSS)
        btn.setStyleSheet = lambda css: None             # keep this style when other code restyles the tab's buttons
        row.insertWidget(row.indexOf(self.trigger), btn)
        self.button = btn
        w.btn_control_advanced = btn

        self.trigger.installEventFilter(self)            # same height as Trigger (it follows Home ALL)
        self.frame.installEventFilter(self)
        btn.toggled.connect(self.apply)
        self.apply(False)                                # Basic at every start
        QTimer.singleShot(0, self._match_height)

    # ------------------------------------------------------------------ mode
    def apply(self, adv):
        adv = bool(adv)
        for wd in self.row_widgets:
            wd.setVisible(adv)
        for r, st in self.row_stretch.items():           # hidden rows take no height
            self.grid.setRowStretch(r, st if adv else 0)
        for b in self.homes:
            b.setVisible(adv)
        for wd in self.dims:
            if wd is self.sep:
                self._separator(adv)
            else:
                wd.setVisible(adv)
        QTimer.singleShot(0, self._frame_visibility)
        split = getattr(self.window, "control_natural_split", None)
        if split is not None:
            QTimer.singleShot(0, split)                  # controls lower in Basic: more room for the console

    def _separator(self, adv):
        """The line before 'Go to ...' is also hidden by the small-screen row wrap while the buttons are on their own
        line: then only the state it comes back to is set."""
        wraps = getattr(self.window, "small_screen_wraps", None)
        for rw in (getattr(wraps, "rows", None) or []):
            if self.sep in getattr(rw, "hide_when_wrapped", ()) and rw.wrapped:
                self.sep.setProperty("_wrap_hidden", not adv)
                return
        self.sep.setVisible(adv)

    def _frame_visibility(self):
        """The dimensions frame without any shown item (Basic mode, buttons on their own line on a very narrow
        window) is hidden instead of an empty box."""
        try:
            lay = self.frame.layout()
            shown = any(lay.itemAt(i).widget() is not None and not lay.itemAt(i).widget().isHidden()
                        for i in range(lay.count()))
            if self.frame.isHidden() == shown:
                self.frame.setVisible(shown)
        except RuntimeError:
            pass

    # ------------------------------------------------------------------ events
    def eventFilter(self, obj, ev):
        if obj is self.trigger and ev.type() == QEvent.Resize:
            self._match_height()
        elif obj is self.frame and ev.type() == QEvent.LayoutRequest:
            QTimer.singleShot(0, self._frame_visibility)
        return False

    def _match_height(self):
        try:
            h = self.trigger.height()
            if h > 0 and self.button.height() != h:
                self.button.setFixedHeight(h)
        except RuntimeError:
            pass


def style_status_advanced(window):
    """Status 'Advanced mode' check box: outline button, filled when on (still the same check box)."""
    cb = getattr(window, "check_advanced_mode", None)
    if not isinstance(cb, QCheckBox) or cb.property("advButton"):
        return
    cb.setProperty("advButton", True)
    if not cb.objectName():
        cb.setObjectName("statusAdvancedMode")
    QWidget.setStyleSheet(cb, CHECK_CSS.replace("statusAdvancedMode", cb.objectName()))
    cb.setCursor(Qt.PointingHandCursor)
    cb.setToolTip("Advanced mode: all axes, speeds and plot settings")
    start = getattr(window, "gcodeStart", None)
    if start is not None:
        cb.setMinimumHeight(start.sizeHint().height())


def apply_advanced_mode(window):
    if getattr(window, "advanced_mode_ui", None) is not None:
        return window.advanced_mode_ui

    # Status starts in Basic mode: the setting saved by the last session is not used for the start
    window.status_advanced_mode = False
    cb = getattr(window, "check_advanced_mode", None)
    if isinstance(cb, QCheckBox) and cb.isChecked():
        cb.setChecked(False)

    try:
        window.advanced_mode_ui = ControlAdvanced(window)
    except Exception as e:                               # never stops the window from being built
        print(f"Advanced mode: Control button failed: {e}")
        window.advanced_mode_ui = False

    def on_tab(index):                                   # the Status tab is built on its first opening
        if index == 1:
            try:
                style_status_advanced(window)
            except Exception as e:
                print(f"Advanced mode: Status button failed: {e}")

    window.tabModules.currentChanged.connect(on_tab)
    on_tab(window.tabModules.currentIndex())
    return window.advanced_mode_ui
