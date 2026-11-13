"""
Emergency STOP that always reaches the Duet.

The old path (send_cmd(self, 'M112')) refused to send while LogIQ showed NOT CONNECTED, and one failed status poll
is enough for that.  Here M112 goes straight to the IP in the address field, whatever the connection state:

* ``rr_gcode?gcode=M112`` -- RepRapFirmware scans every character arriving on the HTTP G-code input for M112 and
  stops at once (GCodeInput::CheckForUrgentCommand), so it is not queued behind a running job;
* a fresh socket per attempt (no stale keep-alive connection), up to ``ATTEMPTS`` tries of ``TIMEOUT_S`` each;
* in a background thread, so a slow or dead WiFi link never freezes the window; the result is reported on the GUI
  thread (console line + message box saying plainly whether the Duet acknowledged).
"""
import threading
import time

import requests

ATTEMPTS = 4
TIMEOUT_S = 1.5


def _send_m112(ip):
    """Returns (ok, detail). Runs in a worker thread."""
    last = ""
    for k in range(ATTEMPTS):
        s = requests.Session()
        s.trust_env = False                      # no system proxy for a local IP
        try:
            r = s.get(f"http://{ip}/rr_gcode", params={"gcode": "M112"}, timeout=TIMEOUT_S,
                      headers={"Connection": "close"})
            if r.status_code == 200:
                return True, f"acknowledged on attempt {k + 1}"
            last = f"HTTP {r.status_code}"
        except requests.RequestException as e:
            last = type(e).__name__
        finally:
            s.close()
        time.sleep(0.1)
    return False, f"{ATTEMPTS} attempts failed ({last})"


def _report(self, ip, ok, detail):
    from PySide6.QtWidgets import QMessageBox
    try:
        from fcn_control.fcn_control import log_to_duet_console
        log_to_duet_console(self, f"EMERGENCY STOP (M112) to {ip}: {'sent, ' + detail if ok else 'NOT DELIVERED, ' + detail}")
    except Exception:
        pass
    if ok:
        QMessageBox.warning(self, "Emergency STOP",
                            f"M112 reached the Duet at {ip} ({detail}).\n\n"
                            "The Duet is halted and the motors are off.  To continue: send M999 (reset) or "
                            "power-cycle, then home all axes before running anything.")
    else:
        QMessageBox.critical(self, "Emergency STOP NOT delivered",
                             f"LogIQ could not reach the Duet at {ip}: {detail}.\n\n"
                             "CUT THE MOTOR POWER NOW.")


def emergency_stop(self):
    """Button handler: send M112 to the Duet in the IP field, connected or not."""
    from PySide6.QtCore import QTimer
    from fcn_monitor.fcn_duet import get_clean_duet_ip
    ip = get_clean_duet_ip(self)
    result = {}

    def work():
        result["v"] = _send_m112(ip)

    th = threading.Thread(target=work, name="estop-m112", daemon=True)
    th.start()

    def poll():
        if "v" in result:
            _report(self, ip, *result["v"])
        else:
            QTimer.singleShot(50, poll)

    QTimer.singleShot(50, poll)
