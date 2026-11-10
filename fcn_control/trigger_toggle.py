"""
Control tab (KINETIQ): a Trigger ON / OFF toggle at the right end of the dimensions / Home ALL row, to test the
trigger output by hand.

    from fcn_control.trigger_toggle import add_trigger_toggle
    add_trigger_toggle(window, config_hlayout, config_frame)     # after the row's addStretch()

* Click: sends 'M42 P5 S1' (on) or 'M42 P5 S0' (off) through fcn_control.send_cmd, so it shows in the console
  like any command.  GPIO port 5 = out6 (config.g: M950 P5 C"out6"); the same port the plans switch.
* The button shows the output's REAL state, read from the board (state.gpOut[5].pwm): after each click and every
  REFRESH_S while the Control tab is visible and connected (a plan running on the board switches it as well).
  Not connected: OFF and a click only warns.
"""
import json
import threading

from PySide6.QtCore import QObject, Qt, QTimer, Signal, Slot
from PySide6.QtWidgets import QMessageBox, QPushButton, QSizePolicy

from fcn_plan.fcn_trigger import TRIGGER_PORT

ON_CMD = f"M42 P{TRIGGER_PORT} S1"
OFF_CMD = f"M42 P{TRIGGER_PORT} S0"
REFRESH_S = 2.0
READ_TIMEOUT_S = 2.0

OLIVE = "#4b6143"
OLIVE_DARK = "#354530"
OLIVE_HOVER = "#e9eee3"
AMBER = "#e6a817"           # ON: stands out from the olive buttons
AMBER_DARK = "#c48f0f"
TEXT = "#262d23"

STYLE = f"""
    QPushButton#triggerToggle {{ background-color: transparent; color: {OLIVE}; border: 2px solid {OLIVE};
                                border-radius: 6px; font-weight: bold; font-size: 16px; padding: 0px 14px; }}
    QPushButton#triggerToggle:hover {{ background-color: {OLIVE_HOVER}; }}
    QPushButton#triggerToggle:checked {{ background-color: {AMBER}; color: {TEXT}; border: 2px solid {AMBER_DARK}; }}
    QPushButton#triggerToggle:checked:hover {{ background-color: {AMBER_DARK}; }}
    QPushButton#triggerToggle:pressed {{ padding-top: 3px; padding-left: 3px; }}
"""


class _Bridge(QObject):
    state = Signal(object)          # True / False / None (unknown)

    def __init__(self, button):
        super().__init__(button)
        self._btn = button
        self.state.connect(self._show, Qt.QueuedConnection)

    @Slot(object)
    def _show(self, on):
        if on is not None:
            show_state(self._btn, bool(on))


def show_state(btn, on):
    try:
        btn.blockSignals(True)
        btn.setChecked(on)
        btn.blockSignals(False)
        btn.setText("Trigger: ON" if on else "Trigger: OFF")
        btn.setToolTip(f"Trigger output (out6) is {'ON' if on else 'OFF'} - click to switch it "
                       f"{'off' if on else 'on'} ({OFF_CMD if on else ON_CMD})")
    except RuntimeError:            # widget deleted
        pass


def parse_gpout(text, port=TRIGGER_PORT):
    """state.gpOut reply -> True / False, None when the port is not configured or the reply is unusable."""
    try:
        res = json.loads(text).get("result")
    except Exception:
        return None
    if not isinstance(res, list) or port >= len(res) or not isinstance(res[port], dict):
        return None
    pwm = res[port].get("pwm")
    return None if pwm is None else float(pwm) > 0.5


def read_state(window, bridge):
    """Reads state.gpOut on a background thread (one at a time) and shows it on the button."""
    if getattr(window, "_trigger_reading", False):
        return
    window._trigger_reading = True
    from fcn_control.fcn_filesystem import get_clean_duet_ip
    ip = get_clean_duet_ip(window)

    def work():
        try:
            from fcn_monitor.fcn_duet import duet_request
            r = duet_request(f"http://{ip}/rr_model?key=state.gpOut&flags=d99v", timeout=READ_TIMEOUT_S,
                             retry=False)
            if r.status_code == 200:
                bridge.state.emit(parse_gpout(r.text))
        except Exception:
            pass
        finally:
            window._trigger_reading = False

    threading.Thread(target=work, name="TriggerState", daemon=True).start()


def add_trigger_toggle(window, layout, parent):
    btn = QPushButton("Trigger: OFF", parent)
    btn.setObjectName("triggerToggle")
    btn.setCheckable(True)
    btn.setMinimumHeight(45)
    btn.setMinimumWidth(150)
    btn.setCursor(Qt.PointingHandCursor)
    QPushButton.setStyleSheet(btn, STYLE)
    btn.setStyleSheet = lambda css: None          # keep this style when other code restyles the tab's buttons
    show_state(btn, False)
    btn.setSizePolicy(btn.sizePolicy().horizontalPolicy(), QSizePolicy.Fixed)
    layout.addWidget(btn)

    def match_home_height():                      # same height as Home ALL in this row
        home = getattr(window, "HOME_ALL_PLATFORM", None)
        try:
            if home is not None and home.height() > 0:
                btn.setFixedHeight(home.height())
        except RuntimeError:
            pass

    QTimer.singleShot(0, match_home_height)
    if getattr(window, "HOME_ALL_PLATFORM", None) is not None:
        from PySide6.QtCore import QEvent

        class _Resize(QObject):
            def eventFilter(self, obj, ev):
                if ev.type() == QEvent.Resize:
                    match_home_height()
                return False

        window._trigger_height_filter = _Resize(btn)
        window.HOME_ALL_PLATFORM.installEventFilter(window._trigger_height_filter)
    window.btn_trigger_toggle = btn
    bridge = _Bridge(btn)

    def clicked(want_on):
        if not getattr(window, "duet_connected", False):
            show_state(btn, False)
            QMessageBox.warning(window, "Not Connected", "Please connect to Duet first.")
            return
        from fcn_control.fcn_control import send_cmd
        show_state(btn, want_on)
        send_cmd(window, ON_CMD if want_on else OFF_CMD)
        QTimer.singleShot(400, lambda: read_state(window, bridge))   # confirm from the board

    btn.clicked.connect(clicked)

    def tick():
        try:
            if not btn.isVisible():
                return
        except RuntimeError:
            timer.stop()
            return
        if getattr(window, "duet_connected", False):
            read_state(window, bridge)
        elif btn.isChecked():
            show_state(btn, False)

    timer = QTimer(btn)
    timer.setInterval(int(REFRESH_S * 1000))
    timer.timeout.connect(tick)
    timer.start()
    return btn
