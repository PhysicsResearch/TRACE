"""
End-to-end check through the Planning tab (offscreen): Add Curve bakes the stepped motion,
the exported G-code reproduces the stored (plotted) curve, and a G-code re-import keeps timing.
Run:  set QT_QPA_PLATFORM=offscreen  &  C:\\Users\\gabri\\anaconda3\\envs\\TRACE\\python.exe scratch\\test_stepped_plan_ui.py
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import numpy as np
from PySide6.QtWidgets import QApplication, QWidget, QTabWidget, QLineEdit, QMessageBox

app = QApplication.instance() or QApplication(sys.argv)

# Never block on modal message boxes
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
QMessageBox.warning = staticmethod(lambda *a, **k: print("  [warning]", a[1] if len(a) > 1 else ""))
QMessageBox.information = staticmethod(lambda *a, **k: None)

from fcn_create_gui.tab_planning import build_planning_tab
from fcn_plan.fcn_create import create_curve, generate_planned_gcode, bake_plan_steps, import_gcode_from_string
from fcn_plan.fcn_gcode import parse_gcode_timeline

FAILS = []


def check(cond, msg):
    print(("PASS  " if cond else "FAIL  ") + msg)
    if not cond:
        FAILS.append(msg)


class MockUI(QWidget):
    def __init__(self):
        super().__init__()
        self.tab_planning = QWidget(self)
        self.tabWidget = QTabWidget(self)
        self.tabWidget.addTab(self.tab_planning, "Planning")
        self.tabModules = QTabWidget(self)
        for _ in range(4):
            self.tabModules.addTab(QWidget(self), "tab")
        build_planning_tab(self)


def select_axes(ui, axes):
    for ax, cb in getattr(ui, 'create_curve_axis_checkboxes', {}).items():
        cb.setChecked(ax in axes)


def linear_curve(ui, axis, start, end, duration):
    select_axes(ui, [axis])
    ui.combo_func_type.setCurrentText("linear")
    ui.input_start_time.setValue(0.0)
    ui.input_amplitude.setValue(start)
    ui.input_amp_offset.setValue(end)
    ui.input_period.setValue(duration)
    create_curve(ui)


def reproduce(ui, gcode, key, col):
    p = parse_gcode_timeline(gcode.splitlines())
    tt = np.array([r['time'] for r in p.rows])
    vv = np.array([r.get(key, np.nan) for r in p.rows])
    o = np.argsort(tt, kind='stable')
    t = ui.dfEdit['time'].values
    rec = np.interp(t, tt[o], vv[o])
    diff = np.abs(rec - ui.dfEdit[col].values)
    # ignore the instantaneous drop at the end of the curve (t=25 s): faster than Max Speed
    diff[(t > 25.0) & (t < 25.2)] = 0.0
    if diff.max() > 1e-3:
        k = int(np.argmax(diff))
        print(f"  worst at t={t[k]:.3f}: G-code {rec[k]:.4f} vs plan {ui.dfEdit[col].values[k]:.4f}")
    return p.time, float(diff.max())


ui = MockUI()
ui.input_plat_lat = QLineEdit("300", ui)
ui.input_plat_si = QLineEdit("500", ui)

print("=== Lung Phantom: X 0 -> 0.5 mm in 25 s (0.02 mm/s, below Min. speed 0.1) ===")
ui.combo_device.setCurrentText("Lung Phantom")
linear_curve(ui, "X", 0.0, 0.5, 25.0)
x = ui.dfEdit['X'].values
levels = np.unique(np.round(x, 9))
check(10 <= len(levels) <= 12, f"stored curve is a staircase ({len(levels)} levels of ~0.05 mm)")
g, _ = generate_planned_gcode(ui)
dur, err = reproduce(ui, g, 'X', 'X')
t_end = ui.dfEdit['time'].values[-1]
check(abs(dur - t_end) < 1e-3, f"G-code duration {dur:.3f} s == plan {t_end:.2f} s")
check(err < 1e-3, f"G-code reproduces the plotted curve (max err {err:.2e} mm)")
check("M203 I6" in g.splitlines()[:9], "header has M203 I6")

print("\n=== Lung Phantom: X 0 -> 2.5 mm in 25 s (0.1 mm/s) stays continuous ===")
linear_curve(ui, "X", 0.0, 2.5, 25.0)
t = ui.dfEdit['time'].values
x = ui.dfEdit['X'].values
w = t <= 25.0
ideal = 2.5 * t[w] / 25.0
check(np.max(np.abs(x[w] - ideal)) < 1e-9, f"stored ramp unchanged (dev {np.max(np.abs(x[w] - ideal)):.1e})")
g, _ = generate_planned_gcode(ui)
f = [float(l.split()[1][1:]) for l in g.splitlines() if l.startswith("G1 ")][1:]
ramp_f = [v for v in f if v < 100]
check(1 <= len(ramp_f) <= 3 and all(abs(v - 6.0) < 1e-3 for v in ramp_f), f"ramp is {len(ramp_f)} G1 at F6 (all feeds {f})")
dur, err = reproduce(ui, g, 'X', 'X')
check(abs(dur - t[-1]) < 1e-3 and err < 1e-3, f"duration {dur:.3f} s, max err {err:.1e}")

print("\n=== Motion Platform: SI 0 -> 0.5 mm in 25 s ===")
ui.combo_device.setCurrentText("Motion Platform")
linear_curve(ui, "SI", 0.0, 0.5, 25.0)
si = ui.dfEdit['SI'].values
levels = np.unique(np.round(si, 9))
check(10 <= len(levels) <= 12, f"stored SI is a staircase ({len(levels)} levels)")
check(np.max(np.abs(ui.dfEdit["'a"].values - si)) < 1e-12, "actuator columns follow the baked SI")
g, _ = generate_planned_gcode(ui)
dur, err = reproduce(ui, g, "'a", 'SI')
check(abs(dur - ui.dfEdit['time'].values[-1]) < 1e-3, f"G-code duration {dur:.3f} s")
check(err < 1e-3, f"G-code reproduces the plotted SI (max err {err:.2e} mm)")
before = ui.dfEdit.copy()
again = bake_plan_steps(ui, ui.dfEdit, "Motion Platform")
check(again is ui.dfEdit, "re-bake of the stored plan is a no-op")

print("\n=== Safety net: unbaked slow data gets baked on export ===")
df = ui.dfEdit.copy()
tt = df['time'].values
df['SI'] = np.where(tt <= 25.0, 0.5 * tt / 25.0, 0.5)
ui.dfEdit = df
g, _ = generate_planned_gcode(ui)
levels = np.unique(np.round(ui.dfEdit['SI'].values, 9))
check(10 <= len(levels) <= 12, f"export baked and stored the plan ({len(levels)} levels)")
n_g4 = sum(1 for l in g.splitlines() if l.startswith("G4"))
check(n_g4 <= 15, f"{n_g4} dwells (not one per sample)")

print("\n=== Re-import of the exported G-code keeps the timing ===")
try:
    t_plan = ui.dfEdit['time'].values[-1]
    import_gcode_from_string(ui, g)
    t_imp = ui.dfEdit['time'].values[-1]
    check(abs(t_imp - t_plan) <= 0.011, f"imported duration {t_imp:.2f} s == {t_plan:.2f} s")
    si_imp = ui.dfEdit['SI'].values
    check(abs(si_imp.max() - 0.5) < 1e-3, f"imported SI reaches 0.5 mm ({si_imp.max():.4f})")
except Exception as e:
    check(False, f"import failed: {e!r}")

print("\n=== Extending the time window keeps the other axes at their last value ===")
ui.combo_device.setCurrentText("Lung Phantom")
select_axes(ui, ["Y"])
ui.combo_func_type.setCurrentText("constant")
ui.input_start_time.setValue(0.0)
ui.input_end_time.setValue(float(ui.dfEdit['time'].max()))
ui.input_amplitude.setValue(7.0)
ui.input_amp_offset.setValue(0.0)
create_curve(ui)
t_old = float(ui.dfEdit['time'].max())
select_axes(ui, ["X"])
ui.combo_func_type.setCurrentText("sin")
ui.input_start_time.setValue(t_old)
ui.input_end_time.setValue(t_old + 30.0)
ui.input_amplitude.setValue(5.0)
ui.input_amp_offset.setValue(10.0)
ui.input_period.setValue(4.0)
create_curve(ui)
ext = ui.dfEdit['time'].values > t_old + 1e-9
y_ext = ui.dfEdit['Y'].values[ext]
check(ext.any() and np.all(np.abs(y_ext - 7.0) < 1e-12),
      f"Y holds 7.0 mm in the extension ({y_ext.min():.3f}..{y_ext.max():.3f}), not 0")

print("\n" + ("ALL PASSED" if not FAILS else f"{len(FAILS)} FAILED"))
sys.exit(1 if FAILS else 0)
