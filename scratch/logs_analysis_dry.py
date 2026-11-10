"""Dry run of the Log files video analysis: the tab's own functions on the 3 logs + the plan G-code; prints the
results views (alignment, peaks & periods, movements per axis, compare) so the narration quotes measured values.

    python scratch/logs_analysis_dry.py log1.csv log2.csv log3.csv [plan.gcode]
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, r"C:\TRACE")
sys.path.insert(0, r"C:\TRACE\demo")
os.chdir(r"C:\TRACE")
args = sys.argv[1:]
GC = next((a for a in args if a.endswith(".gcode")), r"C:\TRACE\demo\output\logs_analysis.gcode")
LOGS = [a for a in args if a.endswith(".csv")]

from PySide6.QtWidgets import QApplication
import shutil, tempfile
cfg = "configuration.json"; bak = os.path.join(tempfile.gettempdir(), "dry_cfg.json"); shutil.copy2(cfg, bak)
app = QApplication.instance() or QApplication(sys.argv)
from demo_planning import build_window
w = build_window(); w.show()
w.tabModules.setCurrentIndex(5)
for _ in range(20):
    app.processEvents()
from fcn_create_gui import tab_logs as T


def view(name):
    st = T._state(w)
    v = st.results.get(name)
    if not v:
        print(f"[{name}] -")
        return
    hdrs, rows = (v.get('headers'), v.get('rows')) if isinstance(v, dict) else (v[0], v[1])
    print(f"[{name}]", hdrs)
    for r in rows:
        print("   ", [round(x, 3) if isinstance(x, float) else x for x in r])


try:
    T.logs_add_files(w, LOGS)
    T.logs_add_reference(w, GC)
    for i, e in enumerate(T._state(w).entries):
        print(i, e.curve.name, e.curve.meta.get('n'), e.curve.meta.get('median_dt'), e.curve.meta.get('gcode'))
    T.logs_set_analysis_axis(w, 'AP')
    al = T.logs_auto_align(w, all_curves=True)
    print("align:", [(r.get('curve'), round(r.get('shift', 0), 3), round(r.get('corr', 0), 4)) for r in al or []])
    T.logs_find_peaks(w, kind='max')
    view('Peaks & periods')
    T.logs_compare(w)
    view('Compare')
    for ax, roi in (('LAT', (4, 23)), ('SI', (22, 41))):
        T.logs_set_analysis_axis(w, ax)
        T.logs_set_roi(w, *roi)
        T.logs_detect_movements(w)
        print(f"--- movements {ax} ROI {roi}")
        for m in T.logs_movement_list(w):
            print(f"   {m['curve'][:28]:28s} #{m['number']} start {m['t_start']:.3f} stop {m['t_stop']:.3f} "
                  f"dur {m['duration']:.3f} delta {m['delta']:.3f} peak {m['peak_speed']:.2f}")
        T.logs_clear_movements(w)
    T.logs_clear_roi(w)
finally:
    w.close()
    shutil.copy2(bak, cfg)
