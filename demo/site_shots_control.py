"""
Screenshots of the Control tab with KINETIQ connected (for the website).  Sends only M115; nothing moves.

    python demo/site_shots_control.py [out_dir]       default: C:\\LogIQ_site\\public\\images\\app
Environment: DEMO_IP (default 172.18.38.129).  configuration.json is restored afterwards.
"""
import os
import shutil
import sys
import tempfile
import time

sys.path.insert(0, r"C:\TRACE")
sys.path.insert(0, r"C:\TRACE\demo")
os.chdir(r"C:\TRACE")
OUT = sys.argv[1] if len(sys.argv) > 1 else r"C:\LogIQ_site\public\images\app"
IP = os.environ.get("DEMO_IP", "172.18.38.129")

from PySide6.QtWidgets import QApplication

cfg = os.path.join(r"C:\TRACE", "configuration.json")
bak = os.path.join(tempfile.gettempdir(), "logiq_shots_control_cfg.json")
shutil.copy2(cfg, bak)
app = QApplication.instance() or QApplication(sys.argv)
from demo_planning import build_window

w = build_window()
w.showMaximized()


def pump(s):
    t = time.time() + s
    while time.time() < t:
        app.processEvents()
        time.sleep(0.02)


saved = []


def grab(widget, name):
    pump(0.3)
    pm = widget.grab()
    pm.save(os.path.join(OUT, name + ".png"))
    saved.append(name)


try:
    pump(1.5)
    w.DuetIPAddress.setText(IP)
    from fcn_control.fcn_control import setDuetIP, send_cmd
    setDuetIP(w, show_dialog=False)
    t = time.time() + 20
    while time.time() < t and not (getattr(w, 'duet_connected', False) and not getattr(w, '_connecting_in_progress', False)):
        pump(0.2)
    if not w.duet_connected:
        raise SystemExit("not connected")
    w.tabWidget.setCurrentWidget(w.tab_platform)
    w.step_buttons["1"].click()
    send_cmd(w, "M115")
    pump(4.0)                                           # status poll fills positions and homed colours
    grab(w, "control-kinetiq")
    grab(w.MIN_LATAXIS.parentWidget(), "ctl-control-jog")
    grab(w.btn_go_to_center.parentWidget(), "ctl-control-config")
    grab(w.duet_log_console.parentWidget(), "ctl-control-console")
    print("saved:", saved, flush=True)
finally:
    w.close()
    shutil.copy2(bak, cfg)

from PIL import Image
for n in saved:
    p = os.path.join(OUT, n + ".png")
    Image.open(p).convert("RGB").save(os.path.join(OUT, n + ".webp"), "WEBP", quality=88, method=6)
    os.remove(p)
print("webp:", saved, flush=True)
