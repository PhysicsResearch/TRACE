"""Screenshots of the LogIQ shell layout (connection bar on top, icon tabs on the left) -> scratch/shell_shots/

    python scratch/shoot_shell.py
"""
import os
import shutil
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, r"C:\TRACE")
os.chdir(r"C:\TRACE")
OUT = os.path.join(r"C:\TRACE\scratch", "shell_shots")
os.makedirs(OUT, exist_ok=True)
cfg = "configuration.json"
bak = os.path.join(tempfile.gettempdir(), "logiq_shell_cfg.json")
shutil.copy2(cfg, bak)

from PySide6.QtWidgets import QApplication
app = QApplication(sys.argv)
import Launch_ImGUI as L
from fcn_create_gui.window_fit import fit_tabs_to_current_page
from fcn_create_gui.top_bar_style import style_top_bar
from fcn_create_gui.console_theme import add_console_theme_button
from fcn_create_gui.logiq_theme import prepare_logiq_theme, apply_logiq_theme
from fcn_create_gui.logiq_shell import apply_logiq_shell

prepare_logiq_theme()
w = L.MyApp(None)
app.setStyle('Fusion')
fit_tabs_to_current_page(w)
style_top_bar(w)
add_console_theme_button(w)
apply_logiq_theme(w)
apply_logiq_shell(w)
w.resize(2048, 1150)
w.show()


def settle(n=8):
    for _ in range(n):
        app.processEvents()


try:
    tm = w.tabModules
    names = ["control", "status", "files", "planning", "editor", "log-files"]
    for i in range(tm.count()):
        w.nav_buttons[i].click()            # through the left column
        settle()
        assert tm.currentIndex() == i, (i, tm.currentIndex())
        assert w.nav_buttons[i].isChecked()
        w.grab().save(os.path.join(OUT, f"{i}_{names[i]}.png"))
    # DYNAMIQ / KINETIQ follow the IP
    w.DuetIPAddress.setText("192.168.8.3"); settle()
    print("ip .3 ->", w.btn_ip_lungphan.isChecked(), w.btn_ip_trace.isChecked())
    w.DuetIPAddress.setText("192.168.8.2"); settle()
    print("ip .2 ->", w.btn_ip_lungphan.isChecked(), w.btn_ip_trace.isChecked())
    w.DuetIPAddress.setText("10.0.0.5"); settle()
    print("other ->", w.btn_ip_lungphan.isChecked(), w.btn_ip_trace.isChecked())
    w.DuetIPAddress.setText("192.168.8.3"); settle()
    tm.setCurrentIndex(0); settle()
    w.grab().save(os.path.join(OUT, "0_control_dynamiq.png"))
    from fcn_control.fcn_control import update_connection_status_ui
    update_connection_status_ui(w, True); settle()
    w.grab().save(os.path.join(OUT, "0_control_connected.png"))
    update_connection_status_ui(w, False)
    print("bar visible on tab 3:", (tm.setCurrentIndex(3), settle(), w.top_bar_frame.isVisible())[2])
    print("tab bar hidden:", not tm.tabBar().isVisible())
    print("clear text:", w.button_clear_all.text())
finally:
    w.close()
    shutil.copy2(bak, cfg)
print("saved to", OUT)
