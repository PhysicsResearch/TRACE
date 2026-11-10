"""Console replies on the real Duet (no motion): M115 twice and an unknown command.  DEMO_IP (default .129)."""
import os, sys, time, shutil, tempfile
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, r"C:\TRACE"); os.chdir(r"C:\TRACE")
bak = os.path.join(tempfile.gettempdir(), "console_reply_cfg.json"); shutil.copy2("configuration.json", bak)
from PySide6.QtWidgets import QApplication
app = QApplication(sys.argv)
import Launch_ImGUI as L
w = L.MyApp(None)
def pump(s):
    t = time.time() + s
    while time.time() < t:
        app.processEvents(); time.sleep(0.02)
w.DuetIPAddress.setText(os.environ.get("DEMO_IP", "172.18.38.129"))
from fcn_control.fcn_control import setDuetIP, send_cmd
setDuetIP(w, show_dialog=False)
t = time.time() + 15
while time.time() < t and not (getattr(w, 'duet_connected', False) and not getattr(w, '_connecting_in_progress', False)):
    pump(0.2)
print("connected:", w.duet_connected, "| reply poller running:", getattr(getattr(w, 'duet_reply_poller', None), 'isActive', lambda: False)())
n0 = len(w.duet_log_console.toPlainText().splitlines())
for cmd in ("M115", "M115", "M9999"):
    send_cmd(w, cmd); pump(2.5)
lines = w.duet_log_console.toPlainText().splitlines()[n0:]
print("\n".join(lines))
ok = sum("Reply: FIRMWARE_NAME" in l for l in lines) == 2 and any("Reply:" in l and "9999" in l for l in lines) \
     and not any('"buff"' in l for l in lines)
print("PASS" if ok else "FAIL")
w.close(); shutil.copy2(bak, "configuration.json")
