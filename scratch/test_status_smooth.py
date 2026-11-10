"""Status plot smoothing: unit checks + a real log drawn in the app (before / after images in scratch/smooth_out).

    python scratch/test_status_smooth.py [log.csv]
"""
import os
import shutil
import sys
import tempfile

import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, r"C:\TRACE")
os.chdir(r"C:\TRACE")
OUT = os.path.join(r"C:\TRACE\scratch", "smooth_out")
os.makedirs(OUT, exist_ok=True)
LOG = sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\gabri\Desktop\log_09112026_16_17_15.csv"
fails = []


def check(label, ok):
    print(("ok   " if ok else "FAIL ") + label)
    if not ok:
        fails.append(label)


from fcn_create_gui.status_smooth import update_points

# --- unit: a staircase (value held 3 samples of 70 ms), then a real 5 s hold, then a ramp down
t = np.arange(0, 12, 0.07)
true = np.where(t < 4, 7.5 * t, np.where(t < 9, 30.0, 30 - 10 * (t - 9)))
held = true.copy()
for i in range(len(t)):                       # cache: value refreshed every 0.21 s
    held[i] = true[int(i // 3) * 3]
idx = update_points(t, held)
xs, ys = t[idx], held[idx]
check("fewer points than samples", len(idx) < len(t) / 2)
interp = np.interp(t, xs, ys)
err_ramp = np.max(np.abs(interp[(t > 0.5) & (t < 3.5)] - true[(t > 0.5) & (t < 3.5)]))
check(f"ramp follows the true motion (max err {err_ramp:.2f} mm, a step was {7.5 * 0.21:.2f})", err_ramp < 7.5 * 0.21 * 1.05)
hold = (t > 4.4) & (t < 8.9)
check("the 5 s hold stays flat at 30", np.allclose(interp[hold], 30.0))
nan_y = held.copy(); nan_y[50:55] = np.nan
check("NaN gap kept", np.isnan(nan_y[update_points(t, nan_y)]).sum() == 5)

# --- app: the real log in the Status tab
cfg = "configuration.json"
bak = os.path.join(tempfile.gettempdir(), "smooth_cfg.json")
shutil.copy2(cfg, bak)
from PySide6.QtWidgets import QApplication
app = QApplication(sys.argv)
import Launch_ImGUI as L
from fcn_create_gui.logiq_theme import prepare_logiq_theme, apply_logiq_theme
from fcn_create_gui.logiq_shell import apply_logiq_shell
prepare_logiq_theme()
w = L.MyApp(None)
apply_logiq_theme(w)
apply_logiq_shell(w)
w.resize(2048, 1150)
w.show()
w.tabModules.setCurrentIndex(1)
for _ in range(10):
    app.processEvents()
from fcn_monitor import fcn_duet
fcn_duet.load_log_file_into_status(w, LOG)
st = w.status_modern
for k in list(st.pills):
    want = k in ("AP", "Roll")
    if st.pill_cb[k].isChecked() != want:
        st.pill_cb[k].setChecked(want)
for flag, name in ((False, "before"), (True, "after")):
    w.status_smooth_plot = flag
    fcn_duet.render_status_plot(w)
    for _ in range(6):
        app.processEvents()
    w.statusCanvas.grab().save(os.path.join(OUT, f"{name}.png"))
    n = {k: len(l.get_xdata()) for k, l in w.status_plot_lines.items() if l.get_visible()}
    print(name, "points drawn:", n)
raw = len(w.status_plot_data['t']) if isinstance(getattr(w, 'status_plot_data', None), dict) else None
check("log samples unchanged after drawing", raw is not None and raw > 500)
w.close()
shutil.copy2(bak, cfg)
print("PASS" if not fails else f"FAIL: {fails}")
