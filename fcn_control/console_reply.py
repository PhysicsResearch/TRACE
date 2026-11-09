"""
Control tab console: the Duet's reply to a command (M115 -> firmware name and version, errors of a move ...).

rr_gcode only answers {"buff": n} (free space in the command buffer); the reply text waits in rr_reply, and the Duet
hands each reply out once.  The Status tab's ReplyPoller reads it while it runs - then it is asked to read now.
Otherwise (Status tab not opened yet) this reads rr_reply a few times shortly after the command, on a background
thread, and writes every text to the console as 'Reply: ...'.
"""
import threading
import time

from PySide6.QtCore import QObject, Qt, Signal, Slot

READ_DELAYS_S = (0.3, 0.6, 1.2)      # reads after the command (a slow reply, e.g. a G28 error, still arrives)
READ_TIMEOUT_S = 2.5


class _Bridge(QObject):
    got = Signal(str)

    def __init__(self, window):
        super().__init__(window)
        self._w = window
        self.got.connect(self._show, Qt.QueuedConnection)

    @Slot(str)
    def _show(self, text):
        show_reply(self._w, text)


def show_reply(window, text):
    text = str(text or "").strip()
    if not text:
        return
    window._last_duet_reply = text
    lbl = getattr(window, 'statusDuetMessage', None)
    if lbl is not None:
        try:
            lbl.setText(text)
        except RuntimeError:
            pass
    from fcn_control.fcn_control import log_to_duet_console
    for line in text.splitlines():
        if line.strip():
            log_to_duet_console(window, f"Reply: {line.strip()}", color="#00acc1")


def is_buffer_ack(text):
    """True for rr_gcode's plain acknowledgement {"buff": n}."""
    import json
    try:
        js = json.loads(text)
    except Exception:
        return False
    return isinstance(js, dict) and set(js) == {"buff"}


def after_command(window):
    """Called after a command was sent (fcn_control.send_cmd): makes sure its reply reaches the console."""
    poller = getattr(window, 'duet_reply_poller', None)
    try:
        if poller is not None and poller.isActive():
            window._last_duet_reply = ""                   # handle_duet_reply skips a text equal to the last one:
            poller.request_now(READ_DELAYS_S[0])           # the reply to THIS command must show (e.g. M115 twice)
            return
    except Exception:
        pass
    bridge = getattr(window, '_console_reply_bridge', None)
    if bridge is None:
        bridge = window._console_reply_bridge = _Bridge(window)
    from fcn_control.fcn_filesystem import get_clean_duet_ip
    ip = get_clean_duet_ip(window)
    lock = getattr(window, '_console_reply_lock', None)
    if lock is None:
        lock = window._console_reply_lock = threading.Lock()

    def work():
        from fcn_monitor.fcn_duet import duet_request
        with lock:                                        # one reader at a time (each reply is handed out once)
            t0 = time.perf_counter()
            for delay in READ_DELAYS_S:
                wait = t0 + delay - time.perf_counter()
                if wait > 0:
                    time.sleep(wait)
                p = getattr(window, 'duet_reply_poller', None)
                try:
                    if p is not None and p.isActive():
                        p.request_now()
                        return
                    r = duet_request(f"http://{ip}/rr_reply", timeout=READ_TIMEOUT_S, retry=False)
                    if r.status_code == 200 and r.text.strip():
                        bridge.got.emit(r.text)
                except Exception:
                    return

    threading.Thread(target=work, name="ConsoleReply", daemon=True).start()
