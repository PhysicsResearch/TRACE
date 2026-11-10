"""
Screenshots of the Log files tab for the website (the three KINETIQ runs of demo/logs_runs.py and their plan).
Offline: the logs and the reference G-code are read from demo/output (no controller needed).

    python demo/site_shots_logs.py [out_dir]       default: C:\\LogIQ_site\\public\\images\\app
Both configuration files (C:\\TRACE and AppData) are restored afterwards.
"""
import glob
import os
import shutil
import sys
import tempfile
import time

sys.path.insert(0, r"C:\TRACE")
sys.path.insert(0, r"C:\TRACE\demo")
os.chdir(r"C:\TRACE")
OUT = sys.argv[1] if len(sys.argv) > 1 else r"C:\LogIQ_site\public\images\app"
LOGS = sorted(glob.glob(r"C:\TRACE\demo\output\logs_video\log_*.csv"))
REF = r"C:\TRACE\demo\output\logs_analysis.gcode"

from PySide6.QtWidgets import QApplication

from fcn_init.app_config import get_config_path

cfgs = [os.path.join(r"C:\TRACE", "configuration.json"), get_config_path("configuration.json", for_writing=True)]
baks = []
for k, c in enumerate(cfgs):
    if os.path.exists(c):
        b = os.path.join(tempfile.gettempdir(), f"logiq_shots_logs_cfg{k}.json")
        shutil.copy2(c, b)
        baks.append((b, c))

app = QApplication.instance() or QApplication(sys.argv)
from demo_planning import build_window

w = build_window()
w.showMaximized()
saved = []


def pump(s):
    t = time.time() + s
    while time.time() < t:
        app.processEvents()
        time.sleep(0.02)


def grab(widget, name):
    pump(0.4)
    widget.grab().save(os.path.join(OUT, name + ".png"))
    saved.append(name)


def show_only(axes):
    from fcn_create_gui import tab_logs as T
    T.logs_set_analysis_axis(w, axes[0])
    for a in list(w.logs_axis_checks):
        T.logs_set_axis_enabled(w, a, a in axes)


try:
    if len(LOGS) != 3:
        raise SystemExit(f"expected 3 logs, found {LOGS}")
    pump(1.0)
    w.nav_buttons[5].click()
    pump(1.5)
    from fcn_create_gui import tab_logs as T
    T.logs_add_files(w, LOGS)
    T.logs_add_reference(w, REF)
    show_only(['AP'])
    T.logs_auto_align(w, all_curves=True)
    pump(0.8)
    grab(w, "tab-log-files")                                 # whole window: three runs + plan, aligned
    grab(w.logs_curves_table.parentWidget(), "logs-files")
    T.logs_find_peaks(w, kind='max')
    pump(0.8)
    grab(w.logs_right_split, "logs-peaks")
    T.logs_clear_peaks(w)
    show_only(['LAT'])
    T.logs_set_roi(w, 4.0, 23.0)
    T.logs_zoom_to_roi(w)
    T.logs_detect_movements(w)
    pump(0.8)
    grab(w.logs_right_split, "logs-movements")
    T.logs_clear_movements(w)
    T.logs_clear_roi(w)
    show_only(['AP'])
    T.logs_compare(w)
    T.logs_set_display(w, show_diff=True, show_band=True)
    T.logs_set_roi(w, 20.0, 34.0)
    T.logs_zoom_to_roi(w)
    pump(0.8)
    grab(w.logs_right_split, "logs-compare")
    print("saved:", saved, flush=True)
finally:
    w.close()
    for b, c in baks:
        shutil.copy2(b, c)

from PIL import Image

for n in saved:
    p = os.path.join(OUT, n + ".png")
    Image.open(p).convert("RGB").save(os.path.join(OUT, n + ".webp"), "WEBP", quality=88, method=6)
    os.remove(p)
print("webp:", saved, flush=True)
