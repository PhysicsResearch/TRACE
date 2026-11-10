"""Trigger toggle + connect console: connects live (nothing is switched or moved), checks the button reads the
board's out6 state, the console has no 'Legacy check failed' line, and saves images in scratch/trigger_toggle_out.

    python scratch/test_trigger_toggle.py          (DEMO_IP, default 172.18.38.129)
"""
import os, shutil, sys, tempfile, time
sys.path.insert(0, r"C:\TRACE"); sys.path.insert(0, r"C:\TRACE\demo"); os.chdir(r"C:\TRACE")
OUT = r"C:\TRACE\scratch\trigger_toggle_out"
IP = os.environ.get("DEMO_IP", "172.18.38.129")
fails = []
def check(label, ok):
    print(("ok   " if ok else "FAIL ") + label, flush=True)
    if not ok: fails.append(label)

from PySide6.QtWidgets import QApplication
cfg = "configuration.json"; bak = os.path.join(tempfile.gettempdir(), "trigger_toggle_cfg.json"); shutil.copy2(cfg, bak)
app = QApplication.instance() or QApplication(sys.argv)
from demo_planning import build_window
w = build_window(); w.showMaximized()
def pump(s):
    t = time.time() + s
    while time.time() < t:
        app.processEvents(); time.sleep(0.02)
try:
    pump(1.5)
    w.tabWidget.setCurrentWidget(w.tab_platform); pump(0.5)
    b = getattr(w, "btn_trigger_toggle", None)
    check("toggle exists", b is not None)
    row = w.btn_go_to_center.parentWidget().layout()
    check("toggle is the last widget of the row (right of Home ALL, after the stretch)",
          row.itemAt(row.count() - 1).widget() is b and row.indexOf(w.HOME_ALL_PLATFORM) < row.indexOf(b))
    check("not connected: OFF", not b.isChecked() and b.text() == "Trigger: OFF")
    w.btn_go_to_center.parentWidget().grab().save(os.path.join(OUT, "row_not_connected.png"))
    w.DuetIPAddress.setText(IP)
    from fcn_control.fcn_control import setDuetIP
    setDuetIP(w, show_dialog=False)
    t = time.time() + 20
    while time.time() < t and not (getattr(w, 'duet_connected', False) and not getattr(w, '_connecting_in_progress', False)):
        pump(0.2)
    check("connected", w.duet_connected)
    pump(3.0)
    con = w.duet_log_console.toPlainText()
    check("no 'Legacy check failed' line on connect", "Legacy check" not in con)
    check("modern API line still logged", "modern API (/rr_model)" in con)
    from fcn_monitor.fcn_duet import duet_request
    from fcn_control.trigger_toggle import parse_gpout
    real = parse_gpout(duet_request(f"http://{IP}/rr_model?key=state.gpOut&flags=d99v", timeout=3).text)
    check(f"button shows the board state ({real})", b.isChecked() == bool(real))
    b.setStyleSheet("QPushButton { background: red; }")
    check("style kept against restyling", "triggerToggle" in b.styleSheet())
    check(f"same height as Home ALL ({b.height()} / {w.HOME_ALL_PLATFORM.height()})", b.height() == w.HOME_ALL_PLATFORM.height())
    w.btn_go_to_center.parentWidget().grab().save(os.path.join(OUT, "row_connected.png"))
    from fcn_control.trigger_toggle import show_state
    show_state(b, True); pump(0.2)
    w.btn_go_to_center.parentWidget().grab().save(os.path.join(OUT, "row_on_look.png"))   # look only, nothing sent
    show_state(b, bool(real))
    w.duet_log_console.parentWidget().grab().save(os.path.join(OUT, "console.png"))
    print(con[-600:])
finally:
    w.close(); shutil.copy2(bak, cfg)
print("PASS" if not fails else f"FAIL: {fails}")
