"""Connect to the platform, then to an unreachable IP, Cancel, and back: the window must stay responsive
(GUI-thread gaps measured with a 50 ms timer).  Nothing is sent to the platform except status reads.

    python scratch/test_connect_wrong_ip.py        (DEMO_IP default 172.18.38.129, BAD_IP default 192.168.8.2)
"""
import os, shutil, sys, tempfile, time
sys.path.insert(0, r"C:\TRACE"); sys.path.insert(0, r"C:\TRACE\demo"); os.chdir(r"C:\TRACE")
IP = os.environ.get("DEMO_IP", "172.18.38.129"); BAD = os.environ.get("BAD_IP", "192.168.8.2")
fails = []
def check(label, ok):
    print(("ok   " if ok else "FAIL ") + label, flush=True)
    if not ok: fails.append(label)
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
cfg = "configuration.json"; bak = os.path.join(tempfile.gettempdir(), "wrong_ip_cfg.json"); shutil.copy2(cfg, bak)
app = QApplication.instance() or QApplication(sys.argv)
from demo_planning import build_window
w = build_window(); w.showMaximized()
last = [time.perf_counter()]; gap = [0.0]
def beat():
    t = time.perf_counter(); gap[0] = max(gap[0], t - last[0]); last[0] = t
tm = QTimer(); tm.setInterval(50); tm.timeout.connect(beat); tm.start()
def pump(s):
    t = time.time() + s
    while time.time() < t:
        app.processEvents(); time.sleep(0.01)
def connect(ip, wait=25):
    w.DuetIPAddress.setText(ip)
    from fcn_control.fcn_control import setDuetIP
    setDuetIP(w, show_dialog=False)
try:
    pump(1.5)
    connect(IP)
    t = time.time() + 20
    while time.time() < t and (getattr(w, '_connecting_in_progress', False) or not w.duet_connected):
        pump(0.2)
    check("connected to the platform", w.duet_connected)
    pump(3)
    gap[0] = 0; last[0] = time.perf_counter()
    connect(BAD)
    check("old connection dropped when the new connect starts", not w.duet_connected)
    pump(8)
    check(f"GUI responsive while testing the wrong IP (max gap {gap[0]:.2f} s)", gap[0] < 0.5)
    wk = w._current_conn_worker; wk.cancel(); w._connecting_in_progress = False      # = the Cancel button
    gap[0] = 0; last[0] = time.perf_counter()
    pump(8)
    check(f"GUI responsive after Cancel (max gap {gap[0]:.2f} s)", gap[0] < 0.5)
    check("not connected after Cancel", not w.duet_connected and "NOT CONNECTED" in w.windowTitle())
    connect(IP)
    t = time.time() + 25
    while time.time() < t and (getattr(w, '_connecting_in_progress', False) or not w.duet_connected):
        pump(0.2)
    check("reconnects to the platform afterwards", w.duet_connected)
    pump(1)
    check("KINETIQ filled again", w._device_buttons["KINETIQ"].isChecked())
    print(w.duet_log_console.toPlainText()[-700:])
finally:
    w.close(); shutil.copy2(bak, cfg)
print("PASS" if not fails else f"FAIL: {fails}")
