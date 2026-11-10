"""Connected-device recognition (board name / axis count) and the filled DYNAMIQ / KINETIQ button in the top bar.

    python scratch/test_device_identity.py
"""
import os
import shutil
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, r"C:\TRACE")
os.chdir(r"C:\TRACE")
cfg = "configuration.json"
bak = os.path.join(tempfile.gettempdir(), "logiq_devid_cfg.json")
shutil.copy2(cfg, bak)

from PySide6.QtWidgets import QApplication
app = QApplication(sys.argv)
import fcn_control.device_identity as DI

fails = []


def check(label, got, want):
    ok = got == want
    print(f"{'ok  ' if ok else 'FAIL'} {label}: {got!r}" + ("" if ok else f" (want {want!r})"))
    if not ok:
        fails.append(label)


# --- names
for name, want in [("KINETIQ", "KINETIQ"), ("kinetiq", "KINETIQ"), ("TRACE", "KINETIQ"), ("MotionPlatform", "KINETIQ"),
                   ("DYNAMIQ", "DYNAMIQ"), ("LungPhantom", "DYNAMIQ"), ("Lung Phantom", "DYNAMIQ"),
                   ("Duet 3", None), ("", None), (None, None)]:
    check(f"name {name!r}", DI.device_from_name(name), want)

# --- axis count when the name says nothing
DI.axis_count = lambda ip, timeout=2.0: {"10.0.0.3": 3, "10.0.0.2": 11}.get(ip)
check("no name, 3 axes", DI.identify_device("Duet 3", "10.0.0.3")[0], "DYNAMIQ")
check("no name, 11 axes", DI.identify_device(None, "10.0.0.2")[0], "KINETIQ")
check("no name, no reply", DI.identify_device(None, "10.0.0.9")[0], None)
check("name wins over axes", DI.identify_device("KINETIQ", "10.0.0.3")[0], "KINETIQ")

# --- the window: top bar follows the connected device
import Launch_ImGUI as L
from fcn_create_gui.logiq_theme import prepare_logiq_theme, apply_logiq_theme
from fcn_create_gui.logiq_shell import apply_logiq_shell
from fcn_control.fcn_control import update_connection_status_ui
prepare_logiq_theme()
w = L.MyApp(None)
apply_logiq_theme(w)
apply_logiq_shell(w)
dyn, kin = w.btn_ip_lungphan, w.btn_ip_trace
state = lambda: ("DYNAMIQ" if dyn.isChecked() else "") + ("KINETIQ" if kin.isChecked() else "") or "none"

check("start (not connected)", state(), "none")
w.DuetIPAddress.setText("192.168.8.2"); app.processEvents()
check("IP .2 typed, not connected", state(), "none")

w.duet_connected = True
update_connection_status_ui(w, True)
DI.apply_connected_device(w, "10.0.0.2", "KINETIQ"); app.processEvents()
check("connected, name KINETIQ", state(), "KINETIQ")
check("Control sub-tab", w.tabWidget.currentWidget() is w.tab_platform, True)

DI.apply_connected_device(w, "10.0.0.3", "LungPhantom"); app.processEvents()
check("connected, name LungPhantom", state(), "DYNAMIQ")
check("Control sub-tab", w.tabWidget.currentWidget() is w.tab, True)

DI.apply_connected_device(w, "10.0.0.2", None); app.processEvents()
check("connected, no name, 11 axes", state(), "KINETIQ")

# a click on the other preset starts a connection but does not fill it by itself
import fcn_control.fcn_control as FC
FC.setDuetIP = lambda self, show_dialog=True: None          # no real connection in the test
w.setDuetIP.clicked.disconnect()
dyn.click(); app.processEvents()
check("click DYNAMIQ while KINETIQ connected", state(), "KINETIQ")

w.duet_connected = False
update_connection_status_ui(w, False); app.processEvents()
check("disconnected", state(), "none")

w.close()
shutil.copy2(bak, cfg)
print("PASS" if not fails else f"FAIL: {fails}")
