"""Offscreen screenshots of every main tab (and the Planning sub-tabs) -> scratch/theme_shots/<tag>_*.png

    python scratch/shoot_tabs.py before          (no theme hook changes; tag only names the files)
"""
import os
import shutil
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, r"C:\TRACE")
os.chdir(r"C:\TRACE")
TAG = sys.argv[1] if len(sys.argv) > 1 else "shot"
OUT = os.path.join(r"C:\TRACE\scratch", "theme_shots")
os.makedirs(OUT, exist_ok=True)
cfg = "configuration.json"
bak = os.path.join(tempfile.gettempdir(), "kq_shot_cfg.json")
shutil.copy2(cfg, bak)

from PySide6.QtWidgets import QApplication
app = QApplication(sys.argv)
import Launch_ImGUI as L
from fcn_create_gui.window_fit import fit_tabs_to_current_page
from fcn_create_gui.top_bar_style import style_top_bar
from fcn_create_gui.console_theme import add_console_theme_button

THEME = TAG != 'before'
if THEME:
    from fcn_create_gui.logiq_theme import prepare_logiq_theme
    prepare_logiq_theme()
w = L.MyApp(None)
app.setStyle('Fusion')
fit_tabs_to_current_page(w)
style_top_bar(w)
add_console_theme_button(w)
if THEME:
    from fcn_create_gui.logiq_theme import apply_logiq_theme
    apply_logiq_theme(w)
w.resize(2048, 1150)
w.show()


def settle(n=6):
    for _ in range(n):
        app.processEvents()


def shot(name, widget=None):
    settle()
    (widget or w).grab().save(os.path.join(OUT, f"{TAG}_{name}.png"))


tm = w.tabModules
for i in range(tm.count()):
    tm.setCurrentIndex(i)
    settle()
    name = tm.tabText(i).strip().replace(' ', '_') or f"tab{i}"
    shot(f"{i}_{name}")
    if name == "Planning":
        sw = getattr(w, 'create_settings_tab_widget', None)
        if sw is not None:
            for k in range(sw.count()):
                sw.setCurrentIndex(k)
                shot(f"{i}_{name}_sub{k}_{sw.tabText(k)}")
            sw.setCurrentIndex(0)
        p = getattr(w, 'planning_modern', None)
        if p is not None:
            p.device_buttons[1].click()
            shot(f"{i}_{name}_platform")
            p.device_buttons[0].click()
    if name == "Control":
        ct = getattr(w, 'console_theme', None)
        if ct is not None:
            ct.apply("light", save=False)
            shot(f"{i}_{name}_console_light")
            ct.apply("dark", save=False)
            shot(f"{i}_{name}_console_dark")
print("title:", w.windowTitle(), "| tabs:", [tm.tabText(i) for i in range(tm.count())])
shutil.copy2(bak, cfg)
w.close()
