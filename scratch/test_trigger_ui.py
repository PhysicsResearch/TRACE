"""
Beam trigger in the real TRACE window (Launch_ImGUI.MyApp, offscreen): the Trigger On / Off / Clear buttons, the
'Periodic' and 'Trigger' tabs, Apply and Undo, the light-green windows (from the full plan, also when the plot is
downsampled), the table colour, waits and triggers sharing a row, the 'Margins' checkbox (survives the checkbox-row
rebuild) and its live gray preview, a device switch, export -> import through fcn_import, manual windows entered in
any order (an On before a later window keeps it; an On inside a run places a window start, so every On may come first;
an Off at a later window's start joins touching windows as in time order; all 2- and 3-window press orders, random
interleavings, touching windows; Undo per press; table / plot / G-code agree; the round trip), no dialog.
Screenshots (1600x900 and 1366x768) go to scratch/trigger_ui_out/ (or the folder given as the first argument).
Run:  C:\\Users\\gabri\\anaconda3\\envs\\TRACE\\python.exe scratch\\test_trigger_ui.py
"""
import io
import os
import shutil
import sys
import time
import traceback

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts'))
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
os.chdir(ROOT)
sys.path.insert(0, ROOT)
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "scratch", "trigger_ui_out")
shutil.rmtree(OUT, ignore_errors=True)
os.makedirs(OUT)


class Tee(io.TextIOBase):
    def __init__(self, s):
        self.s, self.buf = s, []

    def write(self, x):
        self.buf.append(x)
        self.s.write(x)
        return len(x)

    def flush(self):
        self.s.flush()

    def fileno(self):
        return self.s.fileno()

    @property
    def encoding(self):
        return getattr(self.s, 'encoding', 'utf-8')


ERR_TEE = Tee(sys.stderr)
sys.stderr = ERR_TEE
import numpy as np
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QMessageBox, QFileDialog, QScrollArea

app = QApplication.instance() or QApplication([])
app.setFont(QFont("Segoe UI", 9))
BOX, ERRS, RES = [], [], []
for _k in ('warning', 'information', 'critical', 'question'):
    setattr(QMessageBox, _k, staticmethod(lambda *a, _k=_k, **kw: (BOX.append((_k, a[1] if len(a) > 1 else '')),
                                                                     QMessageBox.Yes)[1]))
EXPORT = os.path.join(OUT, "trigger_plan.gcode")
QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: (EXPORT, ''))
sys.excepthook = lambda t, v, tb: (ERRS.append("".join(traceback.format_exception(t, v, tb))),
                                   print("EXC:", ERRS[-1], flush=True))


def check(name, cond, detail=""):
    RES.append(bool(cond))
    print(f"{'PASS' if cond else 'FAIL'}: {name}" + (f"  [{detail}]" if detail else ""), flush=True)


def pump(n=8):
    for _ in range(n):
        app.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)


import Launch_ImGUI
from fcn_plan import fcn_create as fc
from fcn_plan import fcn_trigger as T
from fcn_plan.fcn_gcode import parse_gcode_timeline
import fcn_create_gui.tab_planning_trigger as tpt

win = Launch_ImGUI.MyApp()
app.setStyle('Fusion')
win.resize(1600, 900)
win.show()
pump()
win.tabModules.setCurrentIndex(3)
pump()
tw = win.create_settings_tab_widget


def wins():
    return T.trg_windows(win.dfEdit['time'].to_numpy(float), win.dfEdit['Command'].tolist())


def same_w(a, b, tol=1e-9):
    return len(a) == len(b) and all(abs(x - y) <= tol and abs(u - v) <= tol for (x, u), (y, v) in zip(a, b))


def drawn(gid):
    out = []
    for c in win.create_plot_ax.collections:
        if c.get_gid() == gid:
            out += [(round(float(p.vertices[:, 0].min()), 6), round(float(p.vertices[:, 0].max()), 6))
                    for p in c.get_paths()]
    return out


def legend_texts():
    lg = win.create_plot_ax.get_legend()
    return [t.get_text() for t in lg.get_texts()] if lg else []


def curve(axis, func, amp, off, period, t0, t1):
    for a, cb in win.create_curve_axis_checkboxes.items():
        cb.setChecked(a == axis)
    win.combo_func_type.setCurrentText(func)
    win.input_start_time.setValue(t0)
    win.input_end_time.setValue(t1)
    win.input_amplitude.setValue(amp)
    win.input_amp_offset.setValue(off)
    win.input_period.setValue(period)
    win.button_create_curve.click()
    pump()


def at(tm, button):
    win.input_wait_rad_time.setValue(tm)
    button.click()
    pump()


def cell_at(tm):
    i = int(np.argmin(np.abs(win.dfEdit['time'].to_numpy(float) - tm)))
    return win.dfEdit['Command'].iat[i]


def undo_snapshot():
    st = getattr(win, '_curve_undo_stack', [])
    return st[0]['df'] if st else None


def settle():
    time.sleep(tpt.PREVIEW_DEBOUNCE_MS / 1000.0 + 0.15)
    pump()


# ---------------------------------------------------------------- layout
check("sub-tabs: Curve, Periodic, Trigger, Tools, Settings (+ 'Table' last: modern Planning controls)",
      [tw.tabText(i) for i in range(tw.count())] == ["Curve", "Periodic", "Trigger", "Tools", "Settings", "Table"])
lay = win.create_plot_checkboxes_layout


def margins_beside_acc():
    """'Margins' sits right under 'Acceleration', in one column of the checkbox row (right after Velocity)."""
    col = win.check_show_trg_margins.parentWidget()
    v = col.layout() if col is not None else None
    return (v is not None and win.check_show_acc.parentWidget() is col and v.indexOf(win.check_show_acc) == 0
            and v.indexOf(win.check_show_trg_margins) == 1 and lay.indexOf(col) == lay.indexOf(win.check_show_vel) + 1
            and win.check_show_trg_margins.text() == "Margins")


check("'Margins' checkbox next to 'Acceleration' (right under it, one column)", margins_beside_acc())
gb = win.groupBox_BrCv_createCurve
_eb = win.planning_modern.event_buttons
p_wait = _eb['rad'].mapTo(gb, _eb['rad'].rect().topLeft())
p_on = _eb['on'].mapTo(gb, _eb['on'].rect().topLeft())
p_add = win.planning_modern.btn_event_add.mapTo(gb, win.planning_modern.btn_event_add.rect().topLeft())
p_box = win.input_wait_rad_time.mapTo(gb, win.input_wait_rad_time.rect().topLeft())
# (adapted to request G: the pause / trigger controls are a column card on the right, kinds 2 x 2)
_card = win.planning_modern.event_card
p_off = _eb['off'].mapTo(gb, _eb['off'].rect().topLeft())
check("Trigger On / Off: in the pauses & trigger card with the wait toggles (2 x 2, above Time (s) and Add / Clear); "
      "legacy Trigger On / Off / Clear Trigger kept (hidden)",
      _eb['on'].isVisible() and _card.isAncestorOf(_eb['on']) and _card.isAncestorOf(win.input_wait_rad_time)
      and abs(p_on.x() - p_wait.x()) <= 2 and p_on.y() > p_wait.y() and abs(p_off.y() - p_on.y()) <= 2
      and p_off.x() > p_on.x() and p_box.y() > p_on.y() and p_add.y() > p_box.y()
      and not win.button_trigger_on.isVisible()
      and [b.text() for b in (win.button_trigger_on, win.button_trigger_off, win.button_clear_trigger)]
      == ["Trigger On", "Trigger Off", "Clear Trigger"], f"wait {p_wait}, trigger {p_on}, add {p_add}, box {p_box}")

# ---------------------------------------------------------------- Motion Platform plan, manual windows
win.combo_device.setCurrentText("Motion Platform")
pump()
curve("LAT", "sin", 10.0, 15.0, 8.0, 0.0, 60.0)   # <= 7.9 mm/s: within any Max Speed setting
curve("AP", "cos", 5.0, 7.5, 5.0, 0.0, 60.0)
t_end = float(win.dfEdit['time'].max())
for tm, b in ((3.0, win.button_trigger_on), (5.5, win.button_trigger_off), (12.0, win.button_trigger_on),
              (14.0, win.button_trigger_off), (20.0, win.button_trigger_on)):
    at(tm, b)
snap_before = undo_snapshot()
at(23.5, win.button_trigger_off)
W3 = [(3.0, 5.5), (12.0, 14.0), (20.0, 23.5)]
check("manual On / Off: three windows", same_w(wins(), W3), str(wins()))
check("light-green cover of every window (PolyCollection under the curves), legend 'Trigger on (M42 P5)'",
      same_w(drawn("trg_windows"), W3, 1e-6) and "Trigger on (M42 P5)" in legend_texts()
      and all(c.get_zorder() < 2 for c in win.create_plot_ax.collections if c.get_gid() == "trg_windows"))
coll = [c for c in win.create_plot_ax.collections if c.get_gid() == "trg_windows"][0]
from matplotlib import colors as mcolors
check("cover colour #a5d6a7, alpha 0.3", mcolors.same_color(coll.get_facecolor()[0][:3], mcolors.to_rgb(T.TRIGGER_COLOR))
      and abs(coll.get_alpha() - 0.3) < 1e-9)
check("stored in the device DataFrame, status line says what happened",
      win.dfEdit_motion_platform is win.dfEdit and "window 20.000-23.500 s" in win.trg_status_label.text())
snap = undo_snapshot()
at(3.0, win.button_trigger_on)
check("[round 3, was 'On 4 inside a window: already on'] Trigger On where a window already starts: nothing changes, "
      "an orange status message, no dialog, no undo step",
      same_w(wins(), W3) and "A window already starts at 3.000 s" in win.trg_status_label.text()
      and "#e65100" in win.trg_status_label.styleSheet() and not BOX and undo_snapshot() is snap, win.trg_status_label.text())
at(8.0, win.button_trigger_off)
check("Trigger Off outside a window: nothing changes, says so", same_w(wins(), W3) and "not on" in win.trg_last_message)
win.button_undo_curve.click()
pump()
check("Undo (one step): the last Off is undone, the window runs to the plan end",
      same_w(wins(), [(3.0, 5.5), (12.0, 14.0), (20.0, t_end)]) and same_w(drawn("trg_windows"), wins(), 1e-6))
at(23.5, win.button_trigger_off)
check("Off again", same_w(wins(), W3))
snap = undo_snapshot()
at(4.0, win.button_trigger_on)
check("[round 3, was 'nothing changes'] Trigger On inside a window (4 s in 3-5.5 s): a window start placed there, the "
      "windows unchanged, a dotted mark at 4 s, an orange status line, one undo step",
      same_w(wins(), W3) and drawn("trg_inner_starts") == [(4.0, 4.0)] and undo_snapshot() is not snap
      and "window start placed inside the run 3.000-5.500 s" in win.trg_status_label.text()
      and "#e65100" in win.trg_status_label.styleSheet() and not BOX, win.trg_status_label.text())
win.button_undo_curve.click()
pump()
check("  Undo removes that start again (one step)", same_w(wins(), W3) and not drawn("trg_inner_starts")
      and not T.trg_inner_starts(win.dfEdit['time'].to_numpy(float), win.dfEdit['Command'].tolist()))

# ---------------------------------------------------------------- waits and triggers in one row, table colour
at(12.0, win.button_wait_radiation)
at(14.0, win.button_wait_user)
check("Wait Radiation / Wait User are added to the row's trigger switch (S1 before the wait, S0 after it)",
      cell_at(12.0) == f"M42 P5 S1 ; {T.WAIT_RAD_CMD}" and cell_at(14.0) == "M226 ; M42 P5 S0" and same_w(wins(), W3))
win.button_clear_rad.click()
pump()
win.button_clear_user.click()
pump()
check("Clear Rad / Clear Usr Pauses remove only the waits; the trigger stays",
      cell_at(12.0) == "M42 P5 S1" and cell_at(14.0) == "M42 P5 S0" and same_w(wins(), W3))
at(12.0, win.button_wait_radiation)
tbl = win.create_table_view
hdr = [tbl.horizontalHeaderItem(c).text() for c in range(tbl.columnCount())]
ccol = hdr.index("Command")
bg = {}
for r in range(tbl.rowCount()):
    txt = tbl.item(r, ccol).text()
    if txt:
        bg[txt] = tbl.item(r, 0).background().color().name()
check("table: trigger rows light green (#c8e6c9), a row with a wait keeps the wait colour",
      bg.get("M42 P5 S0") == "#c8e6c9" and bg.get(f"M42 P5 S1 ; {T.WAIT_RAD_CMD}") == "#ffcdd2", str(bg))
n_win = T.trg_describe(wins())
win.button_clear_trigger.click()
pump()
check("Clear Trigger: all windows gone, the wait stays", wins() == [] and cell_at(12.0) == T.WAIT_RAD_CMD
      and drawn("trg_windows") == [] and "3 windows removed" in win.trg_last_message)
win.button_undo_curve.click()
pump()
check("Undo restores the windows", same_w(wins(), W3))

# ---------------------------------------------------------------- Periodic tab
tw.setCurrentWidget(win.trg_periodic_tab)
pump()
win.trg_per_action.setCurrentIndex(win.trg_per_action.findData("trigger_on"))
win.trg_per_period.setValue(2.0)
win.trg_per_duration.setValue(0.5)
win.trg_per_offset.setValue(0.0)
win.trg_per_range['subset'].setChecked(True)
win.trg_per_range['r0'].setValue(30.0)
win.trg_per_range['r1'].setValue(40.0)
win.trg_per_combine.setCurrentIndex(win.trg_per_combine.findData("add"))
win.button_trg_periodic_apply.click()
pump()
pw = [(30.0 + 2 * k, 30.5 + 2 * k) for k in range(5)]
check("Periodic 'Trigger on' 0.5 s every 2 s in 30..40 s, Add: five more windows, summary",
      same_w(wins(), W3 + pw) and win.trg_per_summary.text().startswith("5 windows of 0.5 s every 2 s from 30 to 40 s"),
      win.trg_per_summary.text())
win.button_undo_curve.click()
pump()
check("Undo removes the periodic windows (one step)", same_w(wins(), W3))
win.trg_per_range['r0'].setValue(0.0)
win.trg_per_range['r1'].setValue(30.0)
win.trg_per_combine.setCurrentIndex(win.trg_per_combine.findData("intersect"))
win.button_trg_periodic_apply.click()
pump()
exp = [(4.0, 4.5), (12.0, 12.5), (20.0, 20.5), (22.0, 22.5)]
check("Periodic 'Only where both' in 0..30 s: the pulses inside the manual windows", same_w(wins(), exp), str(wins()))
win.button_undo_curve.click()
pump()
win.trg_per_action.setCurrentIndex(win.trg_per_action.findData("beam_off"))
win.trg_per_period.setValue(1.0)
win.trg_per_duration.setValue(0.25)
win.button_trg_periodic_apply.click()
pump()
w_off = wins()
exp_off = [(3.25, 4.0), (4.25, 5.0), (5.25, 5.5), (12.25, 13.0), (13.25, 14.0), (20.25, 21.0), (21.25, 22.0),
           (22.25, 23.0), (23.25, 23.5)]
check("Periodic 'Beam off' 0.25 s every 1 s in 0..30 s: every window cut (existing AND NOT pulse)",
      same_w(w_off, exp_off), str(w_off))
win.button_undo_curve.click()
pump()
win.trg_per_action.setCurrentIndex(win.trg_per_action.findData("wait_user"))
win.trg_per_period.setValue(10.0)
win.trg_per_range['full'].setChecked(True)
win.button_trg_periodic_apply.click()
pump()
users = [round(float(tm), 3) for tm, c in zip(win.dfEdit['time'], win.dfEdit['Command']) if "M226" in str(c)]
check("Periodic 'Wait user' every 10 s over the full plan: 6 pauses, the windows kept",
      users == [0.0, 10.0, 20.0, 30.0, 40.0, 50.0] and same_w(wins(), W3) and "6 Wait User pauses" in win.trg_per_summary.text(),
      str(users))
win.button_undo_curve.click()
pump()
snap = undo_snapshot()
win.trg_per_action.setCurrentIndex(win.trg_per_action.findData("trigger_on"))
win.trg_per_period.setValue(2.0)
win.trg_per_duration.setValue(3.0)
win.button_trg_periodic_apply.click()
pump()
check("validation: D > P gives a clear message, no change, no dialog, no undo step",
      "must not exceed the period" in win.trg_per_summary.text() and same_w(wins(), W3) and not BOX
      and undo_snapshot() is snap, win.trg_per_summary.text())
win.trg_per_duration.setValue(0.004)
win.button_trg_periodic_apply.click()
pump()
check("validation: a window below the row resolution", "below the row resolution" in win.trg_per_summary.text())
win.trg_per_duration.setValue(0.5)

# periodic preview (Margins on + Periodic tab open)
win.check_show_trg_margins.setChecked(True)
pump()
ov = win.trg_overlay
pv = T.trg_periodic_preview(win.dfEdit['time'].to_numpy(float), 2.0, 0.5, 0.0, None, "trigger_on")['windows']
check("Margins on with the Periodic tab open: its windows previewed in gray (hatched), the applied ones stay green",
      ov['preview_kind'] == "periodic" and same_w(drawn("trg_preview"), pv, 1e-6) and same_w(drawn("trg_windows"), W3, 1e-6)
      and "Trigger preview (periodic)" in legend_texts())
win.trg_per_period.setValue(4.0)
pump()
check("  the preview waits for the debounce", same_w(drawn("trg_preview"), pv, 1e-6))
settle()
check("  ... then follows the new period", len(drawn("trg_preview")) == len(pv) // 2, f"{len(drawn('trg_preview'))}")

# ---------------------------------------------------------------- Trigger tab (position-gated)
tw.setCurrentWidget(win.trg_gate_tab)
pump()
rows = win.trg_gate_rows
check("Trigger tab rows = the platform DOF with the plot colours",
      list(rows) == ["LAT", "SI", "AP", "Roll", "Pitch", "Yaw"]
      and "#1976d2" in rows['LAT']['label'].styleSheet() and "#388e3c" in rows['AP']['label'].styleSheet())
rows['LAT']['use'].setChecked(True)
check("ticking 'Use' on an axis without margins starts from its data range",
      rows['LAT']['min'].value() <= 5.01 and rows['LAT']['max'].value() >= 24.99,
      f"{rows['LAT']['min'].value()}..{rows['LAT']['max'].value()}")
rows['LAT']['min'].setValue(10.0)
rows['LAT']['max'].setValue(20.0)
rows['AP']['use'].setChecked(True)
rows['AP']['min'].setValue(5.0)
rows['AP']['max'].setValue(10.0)
check("per-axis Min / Max enabled for used axes only", rows['LAT']['min'].isEnabled() and not rows['SI']['min'].isEnabled()
      and not win.trg_same_min.isEnabled())
settle()
frame = fc.compute_motion_platform_actuators(win, win.dfEdit)
tt = win.dfEdit['time'].to_numpy(float)
vals = {a: frame[a].to_numpy(float) for a in ("LAT", "AP")}
gp = T.trg_gate_preview(tt, vals, {"LAT": (10.0, 20.0), "AP": (5.0, 10.0)})
ov = win.trg_overlay
ml = sorted((a, y) for a, y, _ in ov['margin_lines'])
cols_ = {a: c for a, _, c in ov['margin_lines']}
check("Margins: dashed lines at LAT 10 / 20 and AP 5 / 10 in the axis colours",
      ml == [("AP", 5.0), ("AP", 10.0), ("LAT", 10.0), ("LAT", 20.0)] and cols_ == {"LAT": "#1976d2", "AP": "#388e3c"}
      and all(ln.get_linestyle() == '--' for ln in win.create_plot_ax.get_lines() if str(ln.get_gid()).startswith("trg_margin")),
      str(ov['margin_lines']))
check("gray preview = where LAT and AP are both inside their margins (from the plotted values); green unchanged",
      ov['preview_kind'] == "margins" and len(gp) > 3 and same_w(drawn("trg_preview"), gp, 1e-6)
      and same_w(drawn("trg_windows"), W3, 1e-6) and "Trigger preview (margins)" in legend_texts())
rows['LAT']['max'].setValue(18.0)
settle()
gp2 = T.trg_gate_preview(tt, vals, {"LAT": (10.0, 18.0), "AP": (5.0, 10.0)})
check("live preview follows a changed Max (debounced)", same_w(drawn("trg_preview"), gp2, 1e-6) and gp2 != gp)
rows['LAT']['max'].setValue(20.0)
win.trg_flip_cb.setChecked(True)
win.trg_gate_range['subset'].setChecked(True)
win.trg_gate_range['r0'].setValue(10.0)
win.trg_gate_range['r1'].setValue(30.0)
settle()
gp3 = T.trg_gate_preview(tt, vals, {"LAT": (10.0, 20.0), "AP": (5.0, 10.0)}, flip=True, rng=(10.0, 30.0))
check("flip + range 10..30 s: preview is the complement inside the range",
      same_w(drawn("trg_preview"), gp3, 1e-6) and all(a >= 10.0 - 1e-9 and b <= 30.0 + 1e-9 for a, b in gp3))
win.trg_flip_cb.setChecked(False)
win.trg_gate_range['full'].setChecked(True)
win.trg_same_cb.setChecked(True)
win.trg_same_min.setValue(5.0)
win.trg_same_max.setValue(12.0)
settle()
gp4 = T.trg_gate_preview(tt, vals, {"LAT": (5.0, 12.0), "AP": (5.0, 12.0)})
check("same margins for all used axes: per-axis fields disabled, one Min / Max pair for LAT and AP",
      not rows['LAT']['min'].isEnabled() and win.trg_same_min.isEnabled() and same_w(drawn("trg_preview"), gp4, 1e-6)
      and sorted((a, y) for a, y, _ in win.trg_overlay['margin_lines']) == [("AP", 5.0), ("AP", 12.0), ("LAT", 5.0), ("LAT", 12.0)])
win.trg_same_cb.setChecked(False)
settle()
# Apply (Only where both): manual windows cut by the margins
win.trg_gate_combine.setCurrentIndex(win.trg_gate_combine.findData("intersect"))
win.button_trg_gate_apply.click()
pump()
Sw = np.zeros(len(tt), bool)
for a, b in W3:
    Sw[int(round(a / 0.01)):int(round(b / 0.01))] = True
G_ = T.trg_gate_mask(vals, {"LAT": (10.0, 20.0), "AP": (5.0, 10.0)})
exp_w = T.trg_windows_from_states(tt, Sw & G_)
check("Apply 'Only where both': the manual windows cut by the LAT / AP margins; summary with windows and on-time",
      same_w(wins(), exp_w) and "Result:" in win.trg_gate_summary.text() and "s on in total" in win.trg_gate_summary.text(),
      f"{len(wins())} windows; {win.trg_gate_summary.text()[:90]}")
win.button_undo_curve.click()
pump()
win.trg_gate_combine.setCurrentIndex(win.trg_gate_combine.findData("add"))
win.button_trg_gate_apply.click()
pump()
exp_add = T.trg_windows_from_states(tt, Sw | G_)
check("Apply 'Add (union)'", same_w(wins(), exp_add))
win.button_undo_curve.click()
pump()
win.trg_gate_combine.setCurrentIndex(win.trg_gate_combine.findData("replace"))
win.trg_gate_range['subset'].setChecked(True)
win.trg_gate_range['r0'].setValue(10.0)
win.trg_gate_range['r1'].setValue(20.0)
win.button_trg_gate_apply.click()
pump()
R_ = T.trg_range_mask(tt, (10.0, 20.0))
exp_rep = T.trg_windows_from_states(tt, (Sw & ~R_) | (G_ & R_))
check("Apply 'Replace in range' 10..20 s", same_w(wins(), exp_rep))
win.button_undo_curve.click()
pump()
win.trg_gate_range['full'].setChecked(True)
win.trg_gate_combine.setCurrentIndex(win.trg_gate_combine.findData("add"))
for a in rows:
    rows[a]['use'].setChecked(False)
win.button_trg_gate_apply.click()
pump()
check("Apply with no axis used: a clear message, nothing changes", "at least one axis" in win.trg_gate_summary.text()
      and same_w(wins(), W3) and not BOX)
rows['LAT']['use'].setChecked(True)
check("the error line is cleared as soon as an input changes", win.trg_gate_summary.text() == "")
rows['AP']['use'].setChecked(True)
settle()

# ---------------------------------------------------------------- Margins checkbox: rebuild, off
fc.rebuild_axis_checkboxes(win, list(win.create_axis_checkboxes))
pump()
fc.trigger_plot_update(win)
check("the Margins checkbox survives the checkbox-row rebuild (still on, under Acceleration, overlay still drawn)",
      win.check_show_trg_margins.isChecked() and win.trg_overlay['preview_kind'] == "margins" and drawn("trg_preview")
      and margins_beside_acc())

# ---------------------------------------------------------------- screenshots (Trigger tab with LAT / AP margins)
SHOTS = {}


def curve_scroll():
    sa = win.button_trigger_on.parent()
    while sa is not None and not isinstance(sa, QScrollArea):
        sa = sa.parent()
    return sa


def shot(name):
    win.create_plot_canvas.draw()
    pump(4)
    p = os.path.join(OUT, name)
    win.grab().save(p)
    SHOTS[name] = p
    return p


def shots_at(tag):
    tw.setCurrentWidget(win.trg_gate_tab)
    win.check_show_trg_margins.setChecked(True)
    settle()
    shot(f"trigger_tab_margins_{tag}.png")
    win.check_show_trg_margins.setChecked(False)
    pump()
    tw.setCurrentIndex(0)
    pump()
    curve_scroll().ensureWidgetVisible(win.trg_status_label, 10, 10)
    pump()
    shot(f"planning_curve_windows_{tag}.png")
    tw.setCurrentWidget(win.trg_periodic_tab)
    pump()
    shot(f"periodic_tab_{tag}.png")


# Periodic tab state for the screenshot: an applied pattern with its summary
win.trg_per_action.setCurrentIndex(win.trg_per_action.findData("trigger_on"))
win.trg_per_period.setValue(2.0)
win.trg_per_duration.setValue(0.5)
win.trg_per_offset.setValue(0.0)
win.trg_per_range['subset'].setChecked(True)
win.trg_per_range['r0'].setValue(30.0)
win.trg_per_range['r1'].setValue(40.0)
win.trg_per_combine.setCurrentIndex(win.trg_per_combine.findData("add"))
win.button_trg_periodic_apply.click()
pump()
shots_at("1600x900")
win.resize(1366, 768)
pump(10)
shots_at("1366x768")
win.resize(1600, 900)
pump(10)
check("Margins off: no gray preview, no margin lines", not win.check_show_trg_margins.isChecked()
      and not drawn("trg_preview") and not win.trg_overlay['margin_lines'])
win.button_undo_curve.click()
pump()

# ---------------------------------------------------------------- G-code export -> fcn_import
gcode, _name = fc.generate_planned_gcode(win)
L = gcode.splitlines()
m42 = [l for l in L if l.startswith("M42")]
p = parse_gcode_timeline(L)
gw = T.trg_windows([r['time'] for r in p.rows], [r['Command'] for r in p.rows])
check("G-code: 'M42 P5 S0' at the start and the end, one S1 / S0 per window",
      m42[0] == "M42 P5 S0" and m42[-1] == "M42 P5 S0" and L[-1] == "M42 P5 S0" and len(m42) == 2 + 2 * len(W3))
check("G-code -> parse: the same windows (within one row)",
      len(gw) == 3 and all(abs(a - c) <= 0.0101 and abs(b - d) <= 0.0101 for (a, b), (c, d) in zip(gw, W3)), str(gw))
win.btn_export_gcode.click()
pump()
check("Export GCODE button wrote the file (the app's own success box only)", os.path.isfile(EXPORT)
      and open(EXPORT).read() == gcode and [b[0] for b in BOX] == ['information'], str(BOX))
BOX.clear()
from fcn_plan.fcn_import import unified_import_action
unified_import_action(win, file_path=EXPORT)
pump()
iw = wins()
check("import through fcn_import (unified_import_action): the same three windows on the platform plan",
      win.combo_device.currentText() == "Motion Platform" and len(iw) == 3
      and all(abs(a - c) <= 0.0101 and abs(b - d) <= 0.0101 for (a, b), (c, d) in zip(iw, W3))
      and same_w(drawn("trg_windows"), iw, 1e-6), str(iw))

# ---------------------------------------------------------------- device switch (gate rows rebuild, values kept)
win.combo_device.setCurrentText("Lung Phantom")
pump()
tw.setCurrentWidget(win.trg_gate_tab)
pump()
check("device switch to Lung Phantom: rows X, Y, Z", list(win.trg_gate_rows) == ["X", "Y", "Z"])
curve("X", "sin", 5.0, 10.0, 3.0, 0.0, 250.0)       # 25001 rows: the plot is downsampled
n_rows = len(win.dfEdit)
at(100.01, win.button_trigger_on)
at(100.53, win.button_trigger_off)
check("long plan (plot downsampled): the window comes from the full plan, exact to the row",
      n_rows > 20000 and same_w(wins(), [(100.01, 100.53)]) and same_w(drawn("trg_windows"), [(100.01, 100.53)], 1e-6),
      f"{n_rows} rows, drawn {drawn('trg_windows')}")
win.combo_device.setCurrentText("Motion Platform")
pump()
r = win.trg_gate_rows
check("back to Motion Platform: rows rebuilt, LAT / AP values kept per axis name",
      list(r) == ["LAT", "SI", "AP", "Roll", "Pitch", "Yaw"] and r['LAT']['use'].isChecked()
      and r['LAT']['min'].value() == 10.0 and r['LAT']['max'].value() == 20.0 and r['AP']['max'].value() == 10.0)

# ---------------------------------------------------------------- regressions (verifier round 1)
print("\n--- regressions (verifier round 1) ---", flush=True)


def r3(w):
    return [(round(a, 3), round(b, 3)) for a, b in w]


# [MEDIUM] Motion Platform: the window fits a 1920 px screen (Margins adds no width to the checkbox row)
win.resize(1366, 768)
pump(8)
mw = win.minimumSizeHint().width()
row_w = win.create_plot_checkboxes_widget.minimumSizeHint().width()
win.check_show_trg_margins.setVisible(False)
pump(4)
row_w0 = win.create_plot_checkboxes_widget.minimumSizeHint().width()
win.check_show_trg_margins.setVisible(True)
pump(4)
check("Motion Platform: window minimum width fits a 1920 px screen; Margins adds no width to the checkbox row",
      mw <= 1906 and row_w == row_w0 and margins_beside_acc(), f"window min {mw} px, row {row_w} px (without Margins {row_w0} px)")
win.resize(1600, 900)
pump(8)

# [LOW] margin lines: the used axis' own curve in front, no rescale by a wide margin, none without Position
tw.setCurrentWidget(win.trg_gate_tab)
pump()
gr = win.trg_gate_rows
gr['LAT']['use'].setChecked(True)
gr['AP']['use'].setChecked(True)
win.check_show_trg_margins.setChecked(True)
settle()
curves = [ln for ln in win.create_plot_ax.get_lines() if not str(ln.get_label()).startswith('_')]
front = {}
for a in ("LAT", "AP"):
    own = [ln for ln in curves if ln.get_label() == a]
    front[a] = bool(own) and all(own[0].get_zorder() > ln.get_zorder() for ln in curves if ln.get_label() not in ("LAT", "AP"))
check("Margins on (14 platform curves shown): the LAT / AP curves are drawn in front of the actuator curves that share "
      "their values, so the dashed lines cross a curve of their own colour", all(front.values()) and len(curves) == 14, str(front))
yl0 = win.create_plot_ax.get_ylim()
gr['LAT']['max'].setValue(200.0)
settle()
yl1 = win.create_plot_ax.get_ylim()
check("a wide margin (LAT Max 200 mm) does not rescale the plot",
      abs(yl1[0] - yl0[0]) < 1e-9 and abs(yl1[1] - yl0[1]) < 1e-9 and ("LAT", 200.0) in [(a, y) for a, y, _ in win.trg_overlay['margin_lines']],
      f"{yl0} -> {yl1}")
gr['LAT']['max'].setValue(20.0)
win.check_show_vel.setChecked(True)
win.check_show_pos.setChecked(False)
settle()
check("Velocity only: no position margin lines on the velocity axis, the gray preview stays",
      not win.trg_overlay['margin_lines'] and drawn("trg_preview") and win.trg_overlay.get('margin_lines_hidden'))
win.check_show_pos.setChecked(True)
win.check_show_vel.setChecked(False)
win.check_show_trg_margins.setChecked(False)
settle()

# Lung Phantom 60 s plan for the plan-editing regressions
win.combo_device.setCurrentText("Lung Phantom")
pump()
tw.setCurrentIndex(0)
pump()
win.dfEdit = None
win.dfEdit_lung_phantom = None
fc.initialize_default_curve_data(win)
pump()
curve("X", "sin", 5.0, 10.0, 4.0, 0.0, 60.0)
base60 = win.dfEdit.copy(deep=True)


def set_plan(spec):
    win.dfEdit = base60.copy(deep=True)
    win.dfEdit_lung_phantom = win.dfEdit
    fc.trigger_plot_update(win)
    pump()
    for tm, on in spec:
        at(tm, win.button_trigger_on if on else win.button_trigger_off)


def crop_trim(mode, a, b):
    dlg = fc.CropTrimDialog(win, mode=mode)
    dlg.input_start.setValue(a)
    dlg.input_end.setValue(b)
    dlg.execute_action()
    pump()
    BOX[:] = [x for x in BOX if x != ('information', 'Success')]   # the dialog's own success box


# [HIGH] Crop / Trim keep the trigger state of every kept row
set_plan([(2.0, True), (6.0, False), (8.0, True), (9.0, False)])
crop_trim("trim", 5.0, 7.0)
check("Trim [5, 7] s with windows (2,6) and (8,9): (2, 5.00) ends at the joint, (8,9) moves to (5.99, 6.99); drawn green",
      r3(wins()) == [(2.0, 5.0), (5.99, 6.99)] and same_w(drawn("trg_windows"), wins(), 1e-6), str(r3(wins())))
set_plan([(2.0, True), (6.0, False)])
crop_trim("trim", 5.0, 7.0)
g_tr = fc.generate_planned_gcode(win)[0].splitlines()
# Trim joins 4.99 s (X = 15 mm) to 7.01 s (X = 5 mm) in one row: the app's own Timing Warning for that jump
BOX[:] = [x for x in BOX if x != ('question', 'Timing Warning')]
check("Trim of a window's end: the window ends at the joint, not at the plan end; the G-code has its S0",
      r3(wins()) == [(2.0, 5.0)] and [l for l in g_tr if l.startswith("M42")] == ["M42 P5 S0", "M42 P5 S1", "M42 P5 S0", "M42 P5 S0"],
      f"{r3(wins())}, {[l for l in g_tr if l.startswith('M42')]}")
win.button_undo_curve.click()
pump()
check("Undo of the Trim restores (2, 6)", r3(wins()) == [(2.0, 6.0)])
crop_trim("crop", 4.0, 10.0)
check("Crop [4, 10] s with window (2,6): the part inside stays, as (0, 2) after the shift", r3(wins()) == [(0.0, 2.0)], str(r3(wins())))

# [MEDIUM] a window that reaches the plan end keeps its end when Create Curve extends the plan
set_plan([])
tw.setCurrentWidget(win.trg_periodic_tab)
pump()
win.trg_per_action.setCurrentIndex(win.trg_per_action.findData("trigger_on"))
win.trg_per_period.setValue(2.0)
win.trg_per_duration.setValue(0.5)
win.trg_per_offset.setValue(1.5)
win.trg_per_range['full'].setChecked(True)
win.trg_per_combine.setCurrentIndex(win.trg_per_combine.findData("add"))
win.button_trg_periodic_apply.click()
pump()
w60 = r3(wins())
tw.setCurrentIndex(0)
pump()
curve("X", "sin", 5.0, 10.0, 4.0, 60.0, 70.0)
check("periodic pulse clipped at the plan end (59.5, 60) is still 0.5 s after Create Curve extends the plan to 70 s",
      w60[-1] == (59.5, 60.0) and r3(wins())[-1] == (59.5, 60.0) and float(win.dfEdit['time'].max()) > 69.9,
      f"{w60[-1]} -> {r3(wins())[-1]}, plan end {float(win.dfEdit['time'].max()):.2f}")

# [LOW] a row holding both waits shows both lines
set_plan([])
at(5.0, win.button_wait_user)
at(5.0, win.button_wait_radiation)
vcols = sorted(ln.get_color() for ln in win.create_plot_ax.get_lines()
               if len(set(np.atleast_1d(ln.get_xdata()))) == 1 and abs(float(np.atleast_1d(ln.get_xdata())[0]) - 5.0) < 1e-9)
check("Wait User + Wait Radiation on one row: both dashed lines (red and yellow)",
      vcols == ['#e53935', '#fbc02d'] and cell_at(5.0) == f"M226 ; {T.WAIT_RAD_CMD}", f"{vcols}, {cell_at(5.0)!r}")

# [LOW] periodic: off gaps below the row resolution are reported (orange, applied)
set_plan([])
tw.setCurrentWidget(win.trg_periodic_tab)
pump()
win.trg_per_offset.setValue(0.0)
win.trg_per_period.setValue(1.0)
win.trg_per_duration.setValue(0.996)
win.button_trg_periodic_apply.click()
pump()
check("Periodic P = 1 s, D = 0.996 s: the summary says the gaps merged, in orange",
      "off gaps of 0.004 s below the row resolution (0.01 s) merged" in win.trg_per_summary.text()
      and "#e65100" in win.trg_per_summary.styleSheet() and len(wins()) == 1, win.trg_per_summary.text())
win.button_undo_curve.click()
pump()
win.trg_per_duration.setValue(0.5)

# [MEDIUM] every wait is drawn on a downsampled plan (from the full plan); thousands of waits as one collection
tw.setCurrentIndex(0)
pump()
curve("X", "sin", 5.0, 10.0, 3.0, 60.0, 250.0)          # 25001 rows: the plot keeps every 2nd row
tw.setCurrentWidget(win.trg_periodic_tab)
pump()
win.trg_per_action.setCurrentIndex(win.trg_per_action.findData("wait_rad"))
win.trg_per_period.setValue(7.33)
win.button_trg_periodic_apply.click()
pump()
n_rad = sum('sensor_wait' in str(c) for c in win.dfEdit['Command'])
n_red = sum(1 for ln in win.create_plot_ax.get_lines() if ln.get_color() == '#e53935')
check("downsampled 25001-row plan: every periodic Wait Radiation has its red line", len(win.dfEdit) > 20000 and n_red == n_rad > 30,
      f"{n_red} of {n_rad}")
win.trg_per_action.setCurrentIndex(win.trg_per_action.findData("wait_user"))
win.trg_per_period.setValue(0.1)
t0_ = time.perf_counter()
win.button_trg_periodic_apply.click()
pump()
dt_ = time.perf_counter() - t0_
n_usr = sum('M226' in str(c) for c in win.dfEdit['Command'])
segs = sum(len(c.get_segments()) for c in win.create_plot_ax.collections if c.get_gid() == "wait_lines_usr")
check("2500 Wait User pauses: all drawn as one dashed collection (fast), the red lines unchanged",
      n_usr == segs == 2500 and sum(1 for ln in win.create_plot_ax.get_lines() if ln.get_color() == '#e53935') == n_rad,
      f"{segs} of {n_usr} in the collection, apply + redraw {dt_:.2f} s")
tw.setCurrentIndex(0)
pump()

# [LOW] export -> import -> export: the same M42 lines (the window open at the end has its S0 on the last row)
set_plan([(10.0, True), (12.0, False), (55.0, True)])
g_a = fc.generate_planned_gcode(win)[0]
re_path = os.path.join(OUT, "reexport_a.gcode")
with open(re_path, "w") as f:
    f.write(g_a)
unified_import_action(win, file_path=re_path)
pump()
last_cell = win.dfEdit['Command'].iat[-1]
g_b = fc.generate_planned_gcode(win)[0]
ma, mb = [l for l in g_a.splitlines() if l.startswith("M42")], [l for l in g_b.splitlines() if l.startswith("M42")]
check("export -> import -> export: the same M42 lines, the imported last row holds the window's S0",
      ma == mb and len(ma) == 6 and last_cell == "M42 P5 S0" and r3(wins()) == [(10.0, 12.0), (55.0, 60.0)],
      f"{len(ma)} -> {len(mb)} M42 lines, last cell {last_cell!r}, windows {r3(wins())}")

# ---------------------------------------------------------------- regressions (verifier round 2)
print("\n--- regressions (verifier round 2): manual windows in any order ---", flush=True)


def cells():
    return win.dfEdit['Command'].tolist()


def m42_lines(g):
    return [l for l in g.splitlines() if l.startswith("M42")]


def gcode_w(g):
    pg = parse_gcode_timeline(g.splitlines())
    return r3(T.trg_windows([r['time'] for r in pg.rows], [r['Command'] for r in pg.rows]))


def table_switches():
    """(time, cell text, row colour) of the table rows holding a trigger switch."""
    tb = win.create_table_view
    hd = [tb.horizontalHeaderItem(c).text() for c in range(tb.columnCount())]
    cc_ = hd.index("Command")
    out = []
    for r_ in range(tb.rowCount()):
        txt = tb.item(r_, cc_).text()
        if T.cell_has_trigger(txt):
            out.append((round(float(tb.item(r_, 0).text()), 3), txt, tb.item(r_, 0).background().color().name()))
    return out


def status_color():
    ss = win.trg_status_label.styleSheet()
    return "orange" if "#e65100" in ss else "green" if "#1b5e20" in ss else ss


def gcode_now():
    g = fc.generate_planned_gcode(win)[0]
    BOX[:] = [x for x in BOX if x != ('question', 'Timing Warning')]
    return g


# [MEDIUM] On 15, Off 20, On 3, Off 4 in the Curve tab: the 15-20 s window must survive (it was merged and deleted)
set_plan([(15.0, True), (20.0, False), (3.0, True)])
msg3 = win.trg_status_label.text()
check("On 15, Off 20, then On 3: shown on 3..20 (one green run, as the G-code runs it), a dotted mark where the "
      "15 s window starts, the status line (orange) says to press Trigger Off",
      r3(wins()) == [(3.0, 20.0)] and same_w(drawn("trg_windows"), wins(), 1e-6) and drawn("trg_inner_starts") == [(15.0, 15.0)]
      and "on until the window at 15.000 s starts; press Trigger Off to end it earlier" in msg3 and status_color() == "orange"
      and "Later window start (trigger already on)" in legend_texts(), f"{r3(wins())}, {drawn('trg_inner_starts')}, {msg3}")
check("  table: the 15 s start is still a light-green switch row, like 3 s and 20 s",
      table_switches() == [(3.0, "M42 P5 S1", "#c8e6c9"), (15.0, "M42 P5 S1", "#c8e6c9"), (20.0, "M42 P5 S0", "#c8e6c9")],
      str(table_switches()))
g3 = gcode_now()
check("  G-code agrees: S1 at 3 s, the repeated S1 at 15 s, S0 at 20 s; parsed (3, 20)",
      m42_lines(g3) == ["M42 P5 S0", "M42 P5 S1", "M42 P5 S1", "M42 P5 S0", "M42 P5 S0"] and gcode_w(g3) == [(3.0, 20.0)],
      f"{m42_lines(g3)} {gcode_w(g3)}")
at(4.0, win.button_trigger_off)
check("  ... Off 4: [(3,4),(15,20)], drawn green, no dotted mark left, status green says the 15-20 s window is kept",
      r3(wins()) == [(3.0, 4.0), (15.0, 20.0)] and same_w(drawn("trg_windows"), wins(), 1e-6) and not drawn("trg_inner_starts")
      and "the window 15.000-20.000 s is kept" in win.trg_status_label.text() and status_color() == "green",
      f"{r3(wins())} | {win.trg_status_label.text()}")
g4 = gcode_now()
check("  G-code windows [(3,4),(15,20)]; table rows = the switches", gcode_w(g4) == [(3.0, 4.0), (15.0, 20.0)]
      and [x[:2] for x in table_switches()] == [(3.0, "M42 P5 S1"), (4.0, "M42 P5 S0"), (15.0, "M42 P5 S1"), (20.0, "M42 P5 S0")],
      f"{gcode_w(g4)} {table_switches()}")
# Undo steps back one press: every press of the any-order sequence, undone right after it, gives the plan before it
seq_ao = [(15.0, True), (20.0, False), (3.0, True), (4.0, False)]
set_plan([])
undo_ok = []
for tm, on in seq_ao:
    before_c = cells()
    before_w = r3(wins())
    at(tm, win.button_trigger_on if on else win.button_trigger_off)
    after_c = cells()
    win.button_undo_curve.click()
    pump()
    undo_ok.append(cells() == before_c and r3(wins()) == before_w and same_w(drawn("trg_windows"), wins(), 1e-6))
    at(tm, win.button_trigger_on if on else win.button_trigger_off)
    undo_ok.append(cells() == after_c)
check("Undo after each press (On 15, Off 20, On 3, Off 4) restores exactly the plan before that press (the 15 s start "
      "too); pressing again gives the same plan", all(undo_ok) and r3(wins()) == [(3.0, 4.0), (15.0, 20.0)], str(undo_ok))
win.button_undo_curve.click()
pump()
check("  Undo of the Off 4: back to on 3..20 with the 15 s start; Off 4 again restores [(3,4),(15,20)]",
      r3(wins()) == [(3.0, 20.0)] and drawn("trg_inner_starts") == [(15.0, 15.0)])
at(4.0, win.button_trigger_off)
check("  ...", r3(wins()) == [(3.0, 4.0), (15.0, 20.0)])
# extending a window: (2,4),(10,12), then On 4 and Off 6
set_plan([(2.0, True), (4.0, False), (10.0, True), (12.0, False), (4.0, True)])
check("(2,4),(10,12) + On 4: the window goes on into (10,12): shown (2,12), status says it runs until 10 s",
      r3(wins()) == [(2.0, 12.0)] and "on until the window at 10.000 s starts" in win.trg_status_label.text()
      and drawn("trg_inner_starts") == [(10.0, 10.0)], f"{r3(wins())} | {win.trg_status_label.text()}")
at(6.0, win.button_trigger_off)
g6 = gcode_now()
check("  ... Off 6: [(2,6),(10,12)], also in the G-code", r3(wins()) == [(2.0, 6.0), (10.0, 12.0)]
      and gcode_w(g6) == [(2.0, 6.0), (10.0, 12.0)], f"{r3(wins())} {gcode_w(g6)}")
# any order of windows gives the same plan and byte-identical G-code as the time order
set_plan([(40.0, True), (52.25, False), (15.0, True), (20.0, False), (3.0, True), (4.0, False), (25.5, True), (26.0, False)])
c_any = cells()
g_any = gcode_now()
set_plan([(3.0, True), (4.0, False), (15.0, True), (20.0, False), (25.5, True), (26.0, False), (40.0, True), (52.25, False)])
check("4 windows entered out of order: the same cells and byte-identical G-code as in time order",
      c_any == cells() and g_any == gcode_now() and r3(wins()) == [(3.0, 4.0), (15.0, 20.0), (25.5, 26.0), (40.0, 52.25)])
# export -> import -> export of the merged state (On 3 before (15,20)): the repeated S1 survives once
set_plan([(15.0, True), (20.0, False), (3.0, True)])
g_m = gcode_now()
rt_path = os.path.join(OUT, "reexport_merged.gcode")
with open(rt_path, "w") as f:
    f.write(g_m)
unified_import_action(win, file_path=rt_path)
pump()
g_m2 = gcode_now()
check("export -> import -> export of 'On 3 before (15,20)': the same M42 lines (the repeated S1 once), the import "
      "shows on 3..20 with the 15 s mark", m42_lines(g_m2) == m42_lines(g_m) and r3(wins()) == [(3.0, 20.0)]
      and len(drawn("trg_inner_starts")) == 1 and abs(drawn("trg_inner_starts")[0][0] - 15.0) < 0.0101,
      f"{m42_lines(g_m)} -> {m42_lines(g_m2)}, {r3(wins())}")
at(4.0, win.button_trigger_off)
check("  ... Off 4 on the imported plan: [(3,4),(15,20)] (the window survived the import)",
      r3(wins()) == [(3.0, 4.0), (15.0, 20.0)], str(r3(wins())))

# ---------------------------------------------------------------- regressions (verifier round 3)
print("\n--- regressions (verifier round 3): every On before the Offs, any interleaving, touching windows ---", flush=True)
import itertools
import random


def time_order(ws):
    return [x for a, b in sorted(ws) for x in ((a, True), (b, False))]


def valid_orders(ws):
    """Every press order of the windows' On / Off events in which each window's On comes before its Off."""
    evs = [(a, True, k) for k, (a, b) in enumerate(ws)] + [(b, False, k) for k, (a, b) in enumerate(ws)]
    for p_ in itertools.permutations(evs):
        pos = {(e[1], e[2]): j for j, e in enumerate(p_)}
        if all(pos[(True, k)] < pos[(False, k)] for k in range(len(ws))):
            yield [(e[0], e[1]) for e in p_]


def joined(ws):
    """The windows the time-order presses give: touching windows form one run."""
    out = []
    for a, b in sorted(ws):
        if out and abs(out[-1][1] - a) < 1e-9:
            out[-1] = (out[-1][0], b)
        else:
            out.append((a, b))
    return r3(out)


_GW = {}


def gcode_w_now():
    """Parsed windows of the exported G-code (memoised on the plan: the export is a function of it)."""
    key = (tuple(cells()), win.dfEdit['X'].to_numpy(float).tobytes())
    if key not in _GW:
        _GW[key] = gcode_w(gcode_now())
    return _GW[key]


def agree(exp):
    """The plan windows are ``exp``; the green cover is the plan windows; the parsed G-code windows are ``exp``."""
    return r3(wins()) == exp and same_w(drawn("trg_windows"), wins(), 1e-6) and gcode_w_now() == exp


W2r, W3r = [(3.0, 4.0), (15.0, 20.0)], [(3.0, 4.0), (15.0, 20.0), (25.0, 30.0)]
# [MEDIUM] On 3, On 15, Off 4, Off 20: the On at 15 was rejected ('already on'), so the 15-20 s window was lost
set_plan([(3.0, True)])
snap = undo_snapshot()
at(15.0, win.button_trigger_on)
m15 = win.trg_status_label.text()
check("On 3, then On 15 (the trigger is already on there): a window start placed at 15 s, one run 3..60 with a dotted "
      "mark at 15 s, an orange status saying an Off before 15 s ends only the earlier part, one undo step",
      r3(wins()) == [(3.0, 60.0)] and drawn("trg_inner_starts") == [(15.0, 15.0)] and status_color() == "orange"
      and "window start placed inside the run 3.000-60.000 s" in m15 and "A Trigger Off before 15.000 s ends only the earlier part" in m15
      and undo_snapshot() is not snap and [x[:2] for x in table_switches()][:2] == [(3.0, "M42 P5 S1"), (15.0, "M42 P5 S1")], m15)
at(4.0, win.button_trigger_off)
check("  ... Off 4: [(3,4),(15,60)], the status names the kept 15 s window, no dotted mark left",
      r3(wins()) == [(3.0, 4.0), (15.0, 60.0)] and "the window 15.000-60.000 s is kept" in win.trg_status_label.text()
      and not drawn("trg_inner_starts") and status_color() == "green", win.trg_status_label.text())
at(20.0, win.button_trigger_off)
c_aof = cells()
check("  ... Off 20: [(3,4),(15,20)] in the plan, the green cover and the parsed G-code; the table rows are the switches",
      agree(W2r) and [x[:2] for x in table_switches()] == [(3.0, "M42 P5 S1"), (4.0, "M42 P5 S0"), (15.0, "M42 P5 S1"), (20.0, "M42 P5 S0")],
      f"{r3(wins())} {gcode_w_now()} {table_switches()}")
g_aof = gcode_now()
set_plan(time_order(W2r))
check("  the same cells and byte-identical G-code as the presses in time order", cells() == c_aof and gcode_now() == g_aof)
set_plan([(3.0, True), (15.0, True), (25.0, True), (4.0, False), (20.0, False), (30.0, False)])
check("On 3, On 15, On 25, Off 4, Off 20, Off 30 -> 3 windows (plan, plot, G-code: one S1 / S0 per window)",
      agree(W3r) and m42_lines(gcode_now()) == ["M42 P5 S0"] + ["M42 P5 S1", "M42 P5 S0"] * 3 + ["M42 P5 S0"], str(r3(wins())))
# one undo snapshot per press while every On comes first
set_plan([])
undo_ok = []
for tm, on in [(3.0, True), (15.0, True), (25.0, True), (4.0, False), (20.0, False), (30.0, False)]:
    before_c = cells()
    at(tm, win.button_trigger_on if on else win.button_trigger_off)
    after_c = cells()
    st_ = getattr(win, '_curve_undo_stack', [])
    undo_ok.append(len(st_) == 1 and st_[0]['df']['Command'].tolist() == before_c)
    win.button_undo_curve.click()
    pump()
    undo_ok.append(cells() == before_c and same_w(drawn("trg_windows"), wins(), 1e-6) and not getattr(win, '_curve_undo_stack', []))
    at(tm, win.button_trigger_on if on else win.button_trigger_off)
    undo_ok.append(cells() == after_c)
check("every On first: each press is one undo snapshot (the plan before it); Undo restores it, pressing again gives the "
      "same plan", all(undo_ok) and r3(wins()) == W3r, str(undo_ok))
# [LOW] On 15, Off 20, On 3, Off 15: the Off at the 15 s start deleted the 15-20 s window ([(3,15)]; time order: (3,20))
set_plan([(15.0, True), (20.0, False), (3.0, True)])
snap = undo_snapshot()
at(15.0, win.button_trigger_off)
mj = win.trg_status_label.text()
iss2_cells = cells()
check("[round 3b] On 15, Off 20, On 3, Off 15 -> [(3,20)] as in time order (plan, plot, G-code); the 15 s start removed "
      "(no dotted mark), one undo step, green status",
      agree([(3.0, 20.0)]) and status_color() == "green" and "the window start at 15.000 s removed" in mj
      and undo_snapshot() is not snap and drawn("trg_inner_starts") == [], mj)
set_plan([(3.0, True), (15.0, False), (15.0, True), (20.0, False)])
check("  the same presses in time order: [(3,20)], the same cells", agree([(3.0, 20.0)]) and cells() == iss2_cells)
# every press order of 2 and 3 windows, and of touching windows: plan, plot and G-code.  On the first 32 s of the plan
# (3201 rows; the same buttons and code path): every press re-bakes and reloads the whole table (~0.3 s at 6001 rows)
base32 = base60[base60['time'] <= 32.0 + 1e-9].reset_index(drop=True)


def set_plan32(spec):
    win.dfEdit = base32.copy(deep=True)
    win.dfEdit_lung_phantom = win.dfEdit
    fc.trigger_plot_update(win)
    pump()
    for tm, on in spec:
        at(tm, win.button_trigger_on if on else win.button_trigger_off)


for ws, every in ((W2r, 1), (W3r, 1), ([(3.0, 15.0), (15.0, 20.0)], 1), ([(3.0, 10.0), (10.0, 15.0), (15.0, 20.0)], 6)):
    touching = any(abs(b - a2) < 1e-9 for _a, b in ws for a2, _b in ws)
    set_plan32(time_order(ws))
    ref_c = cells()
    bad, tot = [], 0
    for k_, seq in enumerate(valid_orders(ws)):
        if k_ % every:
            continue
        tot += 1
        set_plan32(seq)
        if not agree(joined(ws)) or (not touching and cells() != ref_c):
            bad.append((seq, r3(wins()), gcode_w_now()))
    n_all = 6 if len(ws) == 2 else 90
    check(f"{'touching ' if touching else ''}{ws}: {'all ' if every == 1 else ''}{tot} {'' if every == 1 else f'of the {n_all} '}"
          f"press orders (each On before its Off, real buttons) -> {joined(ws)} in the plan, the green cover and the "
          f"parsed G-code" + ("" if touching else "; the same cells as in time order"),
          not bad and tot == -(-n_all // every), f"{len(bad)} wrong {bad[:1]}")
# random interleavings of 2-5 windows (some touching), real buttons
rnd = random.Random(7)
bad = []
for trial in range(12):
    k_ = rnd.randint(2, 5)
    while True:
        pts = sorted(rnd.sample(range(1, 3100), 2 * k_))
        if all(pts[q + 1] - pts[q] >= 2 for q in range(len(pts) - 1)):
            break
    ws = [[pts[2 * q] / 100.0, pts[2 * q + 1] / 100.0] for q in range(k_)]
    for q in range(1, k_):
        if trial % 3 == 2 and rnd.random() < 0.5:
            ws[q][0] = ws[q - 1][1]
    ws = [tuple(w_) for w_ in ws]
    evs = [(a, True, q) for q, (a, b) in enumerate(ws)] + [(b, False, q) for q, (a, b) in enumerate(ws)]
    while True:
        rnd.shuffle(evs)
        pos = {(e[1], e[2]): j for j, e in enumerate(evs)}
        if all(pos[(True, q)] < pos[(False, q)] for q in range(k_)):
            break
    set_plan32([(e[0], e[1]) for e in evs])
    if not agree(joined(ws)):
        bad.append((ws, r3(wins()), gcode_w_now()))
check("12 random interleavings of 2-5 windows (every 3rd with touching windows), real buttons: the time-order windows in "
      "the plan, the green cover and the parsed G-code", not bad, str(bad[:1]))
# edges: Off at 0, On at the plan end, On / Off on the same row, waits on those rows
set_plan([])
snap = undo_snapshot()
at(0.0, win.button_trigger_off)
e_off0 = win.trg_status_label.text()
at(60.0, win.button_trigger_on)
check("Off at 0 / On at the plan end on an empty plan: nothing changes, orange messages, no undo step",
      wins() == [] and "not on at 0.000 s" in e_off0 and "plan end" in win.trg_status_label.text() and status_color() == "orange"
      and undo_snapshot() is snap and not BOX, f"{e_off0} | {win.trg_status_label.text()}")
set_plan([(0.0, True), (15.0, True), (0.0, False), (20.0, False)])
check("On 0, On 15, Off 0, Off 20 -> (15,20): the Off at 0 removes the window from 0 up to the 15 s start",
      agree([(15.0, 20.0)]), str(r3(wins())))
set_plan([(5.0, True), (5.0, False)])
check("On / Off on the same row alone: no window, no switch row", wins() == [] and not table_switches())
set_plan([(3.0, True), (5.0, True), (5.0, False), (4.0, False)])
check("[round 3b] On 3, On 5, Off 5 (same row, inside the run: cancels the On 5), Off 4 -> (3,4): no beam to the plan end",
      agree([(3.0, 4.0)]), str(r3(wins())))
set_plan([(3.0, True), (5.001, True), (5.004, False), (4.0, False)])
check("[round 3b] On 3, On 5.001, Off 5.004 (sub-row window inside the run), Off 4 -> (3,4)", agree([(3.0, 4.0)]),
      str(r3(wins())))
set_plan([(3.0, True), (50.0, True), (60.0, False), (4.0, False)])
check("On 3, On 50, Off at the plan end (already ends there), Off 4 -> (3,4),(50,60), the last row holds the S0",
      agree([(3.0, 4.0), (50.0, 60.0)]) and cells()[-1] == "M42 P5 S0", str(r3(wins())))
# [round 3b] Periodic Apply while a manual window is still open (its Off not entered yet): applied, with an orange note
set_plan([(3.0, True)])
tw.setCurrentWidget(win.trg_periodic_tab)
pump()
win.trg_per_action.setCurrentIndex(win.trg_per_action.findData("trigger_on"))
win.trg_per_period.setValue(5.0)
win.trg_per_duration.setValue(1.0)
win.trg_per_offset.setValue(0.0)
win.trg_per_range['subset'].setChecked(True)
win.trg_per_range['r0'].setValue(10.0)
win.trg_per_range['r1'].setValue(25.0)
win.trg_per_combine.setCurrentIndex(win.trg_per_combine.findData("replace"))
win.button_trg_periodic_apply.click()
pump()
m_open = win.trg_per_summary.text()
check("[round 3b] Periodic Replace over a window still on to the plan end (On 3, no Off yet): applied, orange note to "
      "enter the Off first", "on up to the plan end and overlaps this range" in m_open
      and win.trg_per_summary.property("trg_kind") == "warn" and status_color() == "orange", m_open)
tw.setCurrentIndex(0)
pump()
set_plan([(3.0, True), (4.0, False)])
tw.setCurrentWidget(win.trg_periodic_tab)
pump()
win.button_trg_periodic_apply.click()
pump()
m_closed = win.trg_per_summary.text()
check("  ... with its Off entered first: no note, the manual window kept and the pattern inside 10-25 s",
      "plan end" not in m_closed and r3(wins())[:2] == [(3.0, 4.0), (10.0, 11.0)], f"{m_closed} {r3(wins())}")
tw.setCurrentIndex(0)
pump()
set_plan([])
at(3.0, win.button_wait_user)
at(15.0, win.button_wait_radiation)
at(20.0, win.button_wait_user)
for tm, on in [(3.0, True), (15.0, True), (4.0, False), (20.0, False)]:
    at(tm, win.button_trigger_on if on else win.button_trigger_off)
g_w = gcode_now()
order_w = [l for l in g_w.splitlines() if l.startswith("M42") or l == "M226" or "sensor_wait" in l]
check("waits on the 3 / 15 / 20 s rows, every On first: S1 before the wait, S0 after it; windows [(3,4),(15,20)]",
      agree(W2r) and cell_at(3.0) == "M42 P5 S1 ; M226" and cell_at(15.0) == f"M42 P5 S1 ; {T.WAIT_RAD_CMD}"
      and cell_at(20.0) == "M226 ; M42 P5 S0" and order_w == ["M42 P5 S0", "M42 P5 S1", "M226", "M42 P5 S0", "M42 P5 S1",
                                                           T.WAIT_RAD_CMD, "M226", "M42 P5 S0", "M42 P5 S0"], str(order_w))
# export -> import -> export of the state with every On placed, then the Offs on the imported plan
set_plan([(3.0, True), (15.0, True), (25.0, True)])
g_r1 = gcode_now()
rt3 = os.path.join(OUT, "reexport_all_on.gcode")
with open(rt3, "w") as f:
    f.write(g_r1)
unified_import_action(win, file_path=rt3)
pump()
g_r2 = gcode_now()
inner_imp = [round(a, 2) for a, _ in drawn("trg_inner_starts")]
check("export -> import -> export after On 3, On 15, On 25: the same M42 lines (S1 x3, no multiplying switches), the "
      "import shows one run 3..60 with dotted marks at 15 / 25 s",
      m42_lines(g_r2) == m42_lines(g_r1) == ["M42 P5 S0", "M42 P5 S1", "M42 P5 S1", "M42 P5 S1", "M42 P5 S0", "M42 P5 S0"]
      and r3(wins()) == [(3.0, 60.0)] and len(inner_imp) == 2 and abs(inner_imp[0] - 15.0) < 0.0101
      and abs(inner_imp[1] - 25.0) < 0.0101, f"{m42_lines(g_r1)} -> {m42_lines(g_r2)}; {r3(wins())} {inner_imp}")
for tm in (20.0, 4.0, 30.0):
    at(tm, win.button_trigger_off)
w_imp = r3(wins())
check("  ... Off 20, Off 4, Off 30 on the imported plan: the 3 windows (within one row), also in its G-code",
      len(w_imp) == 3 and all(abs(a - c) <= 0.0101 and abs(b - d) <= 0.0101 for (a, b), (c, d) in zip(w_imp, W3r))
      and same_w(gcode_w(gcode_now()), w_imp, 0.0021), f"{w_imp}")

for name, pth in SHOTS.items():
    check(f"screenshot {name}", os.path.isfile(pth) and os.path.getsize(pth) > 30000, pth)
win.close()
pump(10)
check("no message box", not BOX, str(BOX))
check("no exception through excepthook", not ERRS, "\n".join(ERRS)[:1500])
err_txt = "".join(ERR_TEE.buf)
check("no traceback printed on stderr", 'Traceback' not in err_txt, err_txt[-1500:])
n_fail = RES.count(False)
print(f"\n{'ALL PASSED' if not n_fail else f'{n_fail} FAILED'} ({len(RES)} checks)", flush=True)
sys.stdout.flush()
os._exit(1 if n_fail else 0)
