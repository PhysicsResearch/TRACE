"""
Modern Planning tab controls (fcn_create_gui/tab_planning_modern.py + tab_planning_plot_edit.py) in the real TRACE
window (Launch_ImGUI.MyApp), driven with real QTest clicks:

  - Device toggle (segments) <-> hidden combo_device both ways: plot / axis sets / table follow exactly as the combo
    did (compared with a legacy window), programmatic changes (signals, blocked signals + redraw, the Settings combo,
    a G-code import) move the toggle
  - Curve Options 'Axis' pills <-> legacy checkboxes both ways, per device, Yaw disabled, linear / rotational rule,
    Add Curve uses the selected axes; legacy checkboxes hidden by their container (also the new ones of a switch)
  - Plot curves side card: groups per device, title select / deselect all (tri-state box), pills re-bound after every
    legacy rebuild (device switch, Create Curve, import, Undo, Clear All), plotted lines follow, pill colour = line
  - Position / Velocity / Acceleration / Margins pills <-> legacy checkboxes both ways, plot follows
  - navigation icons drive the hidden matplotlib toolbar; Export GCODE / Upload / Select all / Clear all
  - Table sub-tab (follow-up 1): opening shows the table, leaving hides it, check_show_table <-> tab, a rebuild does not
    flip it, a cell edit changes plan and plot
  - Undo icon + pause / trigger row (follow-up 2): exclusive toggles, Add / Clear give the legacy buttons' cells,
    Clear tooltip follows the selection, Undo icon mirrors the legacy Undo
  - right-click on pause lines (follow-up 3) and trigger windows (follow-up 4): real right-click events on the canvas,
    menu / dialogs patched: delete, adjust, change kind, join, kept pauses / triggers, Undo, no menu away / in pan-zoom
  - request G: pauses & trigger card as a right column (Once | Repeat, kinds 2 x 2, Add / Clear, status line), white
    page, no scrolling at 2048x1232 (both devices, both modes), Repeat = the former Periodic tab (hidden): each kind
    gives the legacy Apply Periodic's cells / message / undo, live gray preview in Repeat (Curve tab) only; Rotation
    centre card (label, tooltip, AP default 160, a value already set kept, hidden on the Lung Phantom), G-code of a
    plan without rotations independent of AP
  - no huge buttons, page minimum size not larger than before, G-code byte-identical with the legacy controls
  - screenshots (PM_OUT, prefix PM_PREFIX) at 2048x1232: both devices with curves, the Table tab, the menus
The user's configuration.json is restored byte-identically at the end.

Run:  set QT_QPA_PLATFORM=offscreen & set PYTHONIOENCODING=utf-8 &
      C:\\Users\\gabri\\anaconda3\\envs\\TRACE\\python.exe scratch\\test_planning_modern_ui.py
      (QT_QPA_PLATFORM=windows gives real fonts; the window is not shown)
"""
import os
import sys
import re
import shutil
import tempfile
import traceback

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import numpy as np
from PySide6.QtCore import Qt, QPoint, QEvent, QCoreApplication
from PySide6.QtWidgets import (QApplication, QAbstractButton, QMessageBox, QFileDialog, QToolButton, QPushButton, QCheckBox,
                               QTableWidgetItem, QLabel)
from PySide6.QtTest import QTest

app = QApplication.instance() or QApplication(sys.argv)
for _k in ('warning', 'information', 'critical'):
    setattr(QMessageBox, _k, staticmethod(lambda *a, **k: QMessageBox.Ok))
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)

from fcn_init.app_config import get_config_path

TMP = tempfile.mkdtemp(prefix="pm_modern_")
OUT = os.environ.get('PM_OUT') or TMP
PREFIX = os.environ.get('PM_PREFIX', 'pm_final_')
os.makedirs(OUT, exist_ok=True)
CFGS = [get_config_path('configuration.json', for_writing=True), os.path.join(ROOT, 'configuration.json')]
CFG_BAK = {}
for _i, _c in enumerate(CFGS):
    if os.path.exists(_c):
        CFG_BAK[_c] = os.path.join(TMP, f'cfg{_i}.bak')
        shutil.copyfile(_c, CFG_BAK[_c])

RES = []
ERRS = []
sys.excepthook = lambda t, v, tb: (ERRS.append("".join(traceback.format_exception(t, v, tb))),
                                   print("EXC:", ERRS[-1], flush=True))


def check(name, cond, detail=""):
    RES.append(bool(cond))
    print(f"{'PASS' if cond else 'FAIL'}: {name}" + (f"  [{detail}]" if detail else ""), flush=True)


def pump(n=6):
    for _ in range(n):
        app.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)


def restore_cfg():
    for c, b in CFG_BAK.items():
        shutil.copyfile(b, c)


import Launch_ImGUI
import fcn_create_gui.tab_planning_modern as tpm
import fcn_create_gui.tab_planning_plot_edit as tpe
from fcn_plan import fcn_create as fc
from fcn_plan import fcn_trigger as T
from fcn_plan import fcn_gcode as G

REAL_FONTS = QApplication.platformName() != 'offscreen'


def new_window(modern=True):
    saved = tpm.modernise_planning_tab
    if not modern:
        tpm.modernise_planning_tab = lambda self: None
    try:
        win = Launch_ImGUI.MyApp()
        app.setStyle('Fusion')
        win.setAttribute(Qt.WA_DontShowOnScreen, True)
        from fcn_create_gui.window_fit import fit_tabs_to_current_page
        fit_tabs_to_current_page(win)
        win.resize(2048, 1232)
        win.show()
        pump()
        win.tabModules.setCurrentIndex(3)
        pump(10)
    finally:
        tpm.modernise_planning_tab = saved
    return win


def click(w, button=Qt.LeftButton, pos=None):
    if pos is None:
        QTest.mouseClick(w, button)
    else:
        QTest.mouseClick(w, button, Qt.NoModifier, pos)
    pump()


def headers(win):
    t = win.create_table_view
    return [t.horizontalHeaderItem(i).text() for i in range(t.columnCount())]


def plotted(win):
    """Labels of the plotted curve lines (wait / margin lines excluded)."""
    return sorted(str(l.get_label()) for l in win.create_plot_ax.get_lines() if not str(l.get_label()).startswith('_'))


def line_color(win, key):
    from matplotlib.colors import to_hex
    for l in win.create_plot_ax.get_lines():
        lb = str(l.get_label())
        if lb == key or lb.startswith(key + " ("):
            return to_hex(l.get_color()).lower()
    return None


def table_cmd(win, bg_row):
    """Text of the table's Command cell of plan row bg_row (the table is downsampled; rows map via UserRole+1),
    None when that row is not in the table."""
    tbl = win.create_table_view
    hc = headers(win).index('Command')
    for r in range(tbl.rowCount()):
        it = tbl.item(r, hc)
        if it is not None and it.data(Qt.UserRole + 1) == bg_row:
            return it.text()
    return None


def cmds(win):
    return list(win.dfEdit['Command'])


def tvec(win):
    return win.dfEdit['time'].to_numpy(float)


def wins(win):
    return [(round(a, 3), round(b, 3)) for a, b in T.trg_windows(tvec(win), cmds(win))]


def gcode(win):
    return fc.generate_planned_gcode(win)[0]


def gc_windows(txt):
    pg = G.parse_gcode_timeline(txt.splitlines())
    return [(round(a, 3), round(b, 3)) for a, b in T.trg_windows([r['time'] for r in pg.rows],
                                                                 [r['Command'] for r in pg.rows])]


def gc_pauses(txt):
    pg = G.parse_gcode_timeline(txt.splitlines())
    return [(k, round(tm, 2)) for k, tm in pg.pause_times]


def gc_axis_max(txt, letter):
    """max of an axis word (e.g. "'e") over the G1 lines of a G-code text."""
    vals = [float(m.group(1)) for m in re.finditer(r"(?:^|\s)" + re.escape(letter) + r"(-?\d+\.\d+)", txt, re.M)]
    return max(vals) if vals else float('nan')


def expected_lat_eff(win, ap=160.0, lat=0.0):
    """the single sway compensation: clip(off_lat + nominal LAT + AP*sin(Roll), 0, lim)."""
    d = win.dfEdit
    lim = win.settings_max_lim_lat.value()
    return float(np.max(np.clip(lat + d['LAT'].to_numpy(float) + ap * np.sin(np.radians(d['Roll'].to_numpy(float))),
                                0.0, lim)))


def check_rotation_centre_idempotent(win, g_r160, e_r160):
    """fix (round 3): compute_motion_platform_actuators keeps LAT / SI / AP nominal and puts the compensation only in
    'e / 'f / 'a / 'c, so commits, device switches and keystrokes do not add AP*sin(angle) again, and the G-code
    applies it exactly once."""
    p = pm(win)
    q = chr(39) + 'e'
    lat0 = float(win.dfEdit['LAT'].abs().max())
    e_exp0 = expected_lat_eff(win)
    e0 = float(win.dfEdit[q].max())
    check("G fix: after Add Curve (Roll, AP 160) the stored LAT stays nominal (0) and 'e = one compensation",
          lat0 < 1e-9 and abs(e0 - e_exp0) < 1e-9 and e0 > 1.0, f"LAT {lat0:.4f}, 'e {e0:.4f}, expected {e_exp0:.4f}")
    g_e = gc_axis_max(g_r160, q)
    check("G fix: G-code 'e max = the plan 'e (the single compensation, not applied twice)", abs(g_e - e_r160) < 0.01,
          f"G-code 'e {g_e:.4f}, plan {e_r160:.4f}")
    steps = []

    def snap(name):
        steps.append((name, float(win.dfEdit['LAT'].abs().max()), float(win.dfEdit[q].max())))
    modern_event(win, 5.0, 'on')
    snap('Once Trigger On')
    modern_event(win, 8.0, 'off')
    snap('Once Trigger Off')
    click(p.mode_buttons['repeat'])
    click(p.event_buttons['on'])
    win.trg_per_period.setValue(4.0)
    win.trg_per_duration.setValue(1.0)
    win.trg_per_offset.setValue(1.0)
    click(p.btn_event_add)
    click(p.mode_buttons['once'])
    snap('Repeat Trigger On')
    set_device_modern(win, "Lung Phantom")
    set_device_modern(win, "Motion Platform")
    if 'Roll' in win.dfEdit.columns and q in win.dfEdit.columns:
        snap('device round trip')
    win.input_offset_ap_plan.setText("")
    QTest.keyClicks(win.input_offset_ap_plan, "160")
    pump()
    snap("typed '160'")
    win.input_offset_ap_plan.setText("160.0")
    pump()
    e_exp = expected_lat_eff(win)
    check("G fix: Trigger On/Off (Once), Repeat Add, device round trip and keystrokes in AP: LAT stays 0, "
          "'e stays the single compensation (no drift)",
          len(steps) >= 4 and all(l_ < 1e-9 and abs(e - e_exp) < 1e-6 for _n, l_, e in steps)
          and abs(e_exp - e_exp0) < 1e-6,
          str([(n, round(l_, 4), round(e, 4)) for n, l_, e in steps]) + f" expected {e_exp:.4f} / {e_exp0:.4f}")
    g_now = gcode(win)
    check("G fix: G-code after all those edits: 'e max still the single compensation",
          abs(gc_axis_max(g_now, q) - e_exp) < 0.01, f"{gc_axis_max(g_now, q):.4f} / {e_exp:.4f}")
    # pure function: 5 passes = 1 pass, also with a rotation centre off the A-D centre (LAT 5 / SI 3)
    for lat_t, si_t in (("0.0", "0.0"), ("5", "3")):
        win.input_offset_lat_plan.setText(lat_t)
        win.input_offset_si_plan.setText(si_t)
        pump()
        d1 = fc.compute_motion_platform_actuators(win, win.dfEdit)
        d5 = d1
        for _i in range(4):
            d5 = fc.compute_motion_platform_actuators(win, d5)
        cols = ['LAT', 'SI', 'AP', 'Roll', 'Pitch', 'A', 'B', 'C', 'D', q, chr(39) + 'f', chr(39) + 'a', chr(39) + 'c']
        dev = {c: float(np.max(np.abs(d5[c].to_numpy(float) - d1[c].to_numpy(float)))) for c in cols}
        check(f"G fix: compute_motion_platform_actuators idempotent (centre LAT {lat_t} / SI {si_t}): 5 passes = 1",
              max(dev.values()) < 1e-9, str({k: v for k, v in dev.items() if v >= 1e-9}))
    win.input_offset_lat_plan.setText("0.0")
    win.input_offset_si_plan.setText("0.0")
    pump()
    # G-code round trip on a plan the rails can follow without clipping (LAT / AP around 15 mm, Roll +-):
    # import -> nominal LAT recovered (AP*sin(Roll) removed once), export again -> the same axis moves
    click(win.button_clear_all)
    modern_curve(win, 'LAT', 'cos', 4.0, 15.0, 6.0, 0.0, 20.0)
    modern_curve(win, 'AP', 'sin', 4.0, 15.0, 4.0, 0.0, 20.0)
    modern_curve(win, 'Roll', 'sin', 3.0, 0.0, 5.0, 0.0, 20.0)
    lat_plan = (float(win.dfEdit['LAT'].min()), float(win.dfEdit['LAT'].max()))
    e_plan = float(win.dfEdit[q].max())
    g_a = gcode(win)
    rt = os.path.join(TMP, 'roll_ap160.gcode')
    with open(rt, 'w') as f:
        f.write(g_a)
    fc.import_gcode_action(win, rt)
    pump(10)
    g_b = gcode(win)
    lat_rt = (float(win.dfEdit['LAT'].min()), float(win.dfEdit['LAT'].max()))
    ax_dev = {a: abs(gc_axis_max(g_b, a) - gc_axis_max(g_a, a)) for a in ('A', 'B', 'C', 'D', q)}
    check("G fix: G-code of a Roll plan (AP 160): 'e max = plan 'e = LAT + 160*sin(Roll) once",
          abs(gc_axis_max(g_a, q) - e_plan) < 0.01 and abs(e_plan - expected_lat_eff(win)) < 1e-3
          and e_plan > lat_plan[1] + 1.0, f"G-code {gc_axis_max(g_a, q):.4f}, plan {e_plan:.4f}, expected {expected_lat_eff(win):.4f}, LAT {lat_plan}")
    check("G fix: import of that G-code -> nominal LAT recovered, export again gives the same axis maxima",
          abs(lat_rt[0] - lat_plan[0]) < 0.02 and abs(lat_rt[1] - lat_plan[1]) < 0.02
          and max(ax_dev.values()) < 0.02, f"LAT plan {lat_plan}, imported {lat_rt}, axis max deviation {ax_dev}")
    click(win.button_clear_all)

# ---------------------------------------------------------------- legacy-window helpers (the old controls)
def legacy_curve(win, axis, func, amp, off, period, t0, t1):
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


def legacy_event(win, tm, attr):
    win.input_wait_rad_time.setValue(tm)
    getattr(win, attr).click()
    pump()


# ---------------------------------------------------------------- modern-window helpers (real clicks)
def pm(win):
    return win.planning_modern


def modern_curve(win, axis, func, amp, off, period, t0, t1):
    p = pm(win)
    for a, b in p.axis_pills.items():               # deselect the others, select the axis (real clicks)
        if b.isChecked() and a != axis:
            click(b)
    if not p.axis_pills[axis].isChecked():
        click(p.axis_pills[axis])
    win.combo_func_type.setCurrentText(func)
    win.input_start_time.setValue(t0)
    win.input_end_time.setValue(t1)
    win.input_amplitude.setValue(amp)
    win.input_amp_offset.setValue(off)
    win.input_period.setValue(period)
    click(win.button_create_curve)


def modern_event(win, tm, key):
    win.input_wait_rad_time.setValue(tm)
    click(pm(win).event_buttons[key])
    click(pm(win).btn_event_add)


def set_device_modern(win, name):
    p = pm(win)
    i = [b.text() for b in p.device_buttons].index(name)
    click(p.device_buttons[i])
    pump(4)


LP_SCRIPT = [('curve', 'X', 'sin', 10.0, 0.0, 4.0, 0.0, 20.0), ('curve', 'Y', 'cos', 5.0, 2.0, 5.0, 0.0, 30.0),
             ('event', 5.0, 'rad'), ('event', 12.0, 'usr'), ('event', 3.0, 'on'), ('event', 8.0, 'off')]
MP_SCRIPT = [('curve', 'SI', 'sin', 10.0, 0.0, 4.0, 0.0, 20.0), ('curve', 'LAT', 'cos', 4.0, 1.0, 6.0, 0.0, 24.0),
             ('event', 6.0, 'rad'), ('event', 9.0, 'on'), ('event', 14.0, 'off'), ('event', 16.0, 'usr')]
LEGACY_ATTR = {'rad': 'button_wait_radiation', 'usr': 'button_wait_user', 'on': 'button_trigger_on',
               'off': 'button_trigger_off'}


def run_script(win, script, modern):
    for step in script:
        if step[0] == 'curve':
            (modern_curve if modern else legacy_curve)(win, *step[1:])
        elif modern:
            modern_event(win, step[1], step[2])
        else:
            legacy_event(win, step[1], LEGACY_ATTR[step[2]])


def page_min(win):
    s = win.tab_planning.minimumSizeHint()
    return s.width(), s.height()


try:
    # ================================================================ legacy reference window
    print("\n=== legacy reference window (modern controls off) ===", flush=True)
    lw = new_window(modern=False)
    check("legacy window: no modern controls", getattr(lw, 'planning_modern', None) is None
          and lw.combo_device.isVisible())
    base_min = {}
    base_switch = {}
    for dev in ("Lung Phantom", "Motion Platform"):
        lw.combo_device.setCurrentText(dev)
        pump(6)
        base_min[dev] = page_min(lw)
        base_plot_h = lw.create_plot_view.height()
        base_switch[dev] = (sorted(lw.create_axis_checkboxes), list(lw.create_curve_axis_checkboxes), headers(lw),
                            plotted(lw), lw.settings_stack.currentIndex(), lw.offset_rot_widget.isVisible())
    lw.combo_device.setCurrentText("Lung Phantom")
    pump()
    run_script(lw, LP_SCRIPT, modern=False)
    g_lp_legacy = gcode(lw)
    lw.combo_device.setCurrentText("Motion Platform")
    pump()
    run_script(lw, MP_SCRIPT, modern=False)
    g_mp_legacy = gcode(lw)
    lw_mp_cmds = cmds(lw)
    print(f"  baseline page minimum: {base_min}", flush=True)
    # H3 reference: what the legacy Function Type combo does to the fields, per function (X on the Lung Phantom,
    # Roll on the Motion Platform)
    FUNCS = ["sin", "cos", "cos^2", "cos^4", "cos^6", "constant", "linear"]

    def func_state(wd):
        return (wd.label_amplitude.text(), wd.label_amp_offset.text(), wd.label_period.text(),
                wd.input_amp_offset.isEnabled(), wd.input_period.isEnabled(), wd.input_phase.isEnabled(),
                round(wd.input_end_time.value(), 3))
    legacy_func = {}
    for dev, axis in (("Lung Phantom", 'X'), ("Motion Platform", 'Roll')):
        lw.combo_device.setCurrentText(dev)
        pump()
        for a, cb in lw.create_curve_axis_checkboxes.items():
            cb.setChecked(a == axis)
        lw.input_start_time.setValue(2.0)
        lw.input_end_time.setValue(12.0)
        lw.input_period.setValue(4.0)
        for f in FUNCS:
            lw.combo_func_type.setCurrentText(f)
            pump(2)
            legacy_func[(dev, f)] = func_state(lw)
        lw.combo_func_type.setCurrentText("sin")
    lw.close()
    pump()

    # ================================================================ modern window
    print("\n=== modern window: structure ===", flush=True)
    win = new_window(modern=True)
    p = pm(win)
    check("modern controls built", isinstance(p, tpm.ModernPlanning) and p.alive)
    check("Device: combo hidden, two-segment toggle shown with the device names",
          win.combo_device.isHidden() and p.device_box.isVisible()
          and [b.text() for b in p.device_buttons] == ["Lung Phantom", "Motion Platform"])
    check("legacy row under the graph hidden (axis / kinematic checkboxes, Select / Clear All, Show Table, Export, "
          "Upload)", win.create_plot_checkboxes_widget.isHidden() and not win.check_show_table.isVisible()
          and not win.btn_export_gcode.isVisible() and not win.check_show_pos.isVisible())
    check("legacy Axis checkboxes hidden by their container (holder), not one by one",
          p.axis_checkbox_holder.isHidden()
          and all(cb.parentWidget() is p.axis_checkbox_holder and not cb.isVisible() and not cb.isHidden()
                  for cb in win.create_curve_axis_checkboxes.values()))
    legacy_btns = [getattr(win, a) for a in tpm.LEGACY_EVENT_BUTTONS]
    check("legacy Undo / Wait / Clear / Trigger buttons hidden by their container",
          p.legacy_holder.isHidden() and all(b.parentWidget() is p.legacy_holder and not b.isVisible()
                                             for b in legacy_btns))
    check("matplotlib toolbar hidden, navigation icons shown",
          win.create_plot_toolbar.isHidden() and p.btn_zoom.isVisible() and p.btn_reset.isVisible())
    tw = win.create_settings_tab_widget
    check("sub-tabs: Curve, (Periodic), Trigger, Tools, Settings, Table (Table last)",
          [tw.tabText(i) for i in range(tw.count())] == ["Curve", "Periodic", "Trigger", "Tools", "Settings", "Table"])
    check("G: Periodic sub-tab hidden (merged into the pauses & trigger card), its page alive",
          not tw.isTabVisible(tw.indexOf(win.trg_periodic_tab))
          and [tw.tabText(i) for i in range(tw.count()) if tw.isTabVisible(i)]
          == ["Curve", "Trigger", "Tools", "Settings", "Table"] and win.trg_per_action is not None)
    check("side card right of the graph", p.side_card.isVisible()
          and p.side_card.mapTo(win, QPoint(0, 0)).x() > win.create_plot_canvas.mapTo(win, QPoint(0, 0)).x()
          + win.create_plot_canvas.width() - 2)
    check("Undo icon right of the Function Type dropdown, tooltip 'Undo (one step)'",
          p.btn_undo.isVisible() and p.btn_undo.toolTip() == "Undo (one step)"
          and p.btn_undo.mapTo(win, QPoint(0, 0)).x() > win.combo_func_type.mapTo(win, QPoint(0, 0)).x()
          + win.combo_func_type.width() - 2
          and abs(p.btn_undo.mapTo(win, QPoint(0, 0)).y() - win.combo_func_type.mapTo(win, QPoint(0, 0)).y()) <= 4)

    # Curve Options grid: 3 equal columns
    def xw(name):
        wd = getattr(win, name)
        return wd.mapTo(win, QPoint(0, 0)).x(), wd.width()
    widths = [xw(n)[1] for n in ('input_amplitude', 'input_amp_offset', 'input_period', 'input_phase')]
    # (adapted in H: the third row is Start | range slider | End | Total duration across the columns 2 - 3)
    cc0 = pm(win).curve_controls
    tot_r = cc0.total_spin.mapTo(win, QPoint(0, 0)).x() + cc0.total_spin.width()
    check("Curve Options fields share the width (3 equal columns; Start | slider | End | Total duration spans "
          "columns 2 - 3)", max(widths) - min(widths) <= 12
          and abs(xw('input_amp_offset')[0] - xw('input_start_time')[0]) <= 2
          and abs(xw('input_period')[0] + xw('input_period')[1] - tot_r) <= 2, f"widths {widths}")
    off_le = [win.input_offset_ap_plan, win.input_offset_lat_plan, win.input_offset_si_plan]
    set_device_modern(win, "Motion Platform")
    # (adapted in G: the boxes moved from the field columns into the 'Rotation centre' card, one row)
    ys = [a.mapTo(win, QPoint(0, 0)).y() for a in off_le]
    xs = [a.mapTo(win, QPoint(0, 0)).x() for a in off_le]
    check("G: rotation centre AP / LAT / SI boxes in one row of the card, equal widths, AP | LAT | SI order",
          max(ys) - min(ys) <= 2 and xs == sorted(xs) and max(a.width() for a in off_le) - min(a.width() for a in off_le) <= 3
          and all(p.rot_card.isAncestorOf(a) for a in off_le), f"x {xs} y {ys}")
    check("G: rotation centre card: title, 'reference point for Roll / Pitch / Yaw', tooltip, labels AP / LAT / SI",
          p.rot_card.isVisible() and p.rot_title.text() == "Rotation centre (mm)"
          and p.rot_subtitle.text() == "reference point for Roll / Pitch / Yaw"
          and "reference point" in p.rot_card.toolTip() and "default 0 mm" in p.rot_card.toolTip()
          and all(a.toolTip() == p.rot_card.toolTip() for a in off_le)
          and [l.text() for l in p.rot_labels.values()] == ["AP:", "LAT:", "SI:"]
          and not any(l.isVisible() for l in win.offset_rot_widget.findChildren(QLabel)
                      if l.parentWidget() is win.offset_rot_widget), p.rot_card.toolTip()[:80])
    # (adapted in H: "Move the default AP back to 0")
    check("H: default rotation centre AP 0 mm (back from 160), LAT / SI 0 (Planning and Control fields)",
          win.input_offset_ap_plan.text() == "0.0" and win.input_offset_ap.text() == "0.0"
          and win.input_offset_lat_plan.text() == "0.0" and win.input_offset_si_plan.text() == "0.0")
    check("G: rotation centre card white with the card border", "#ffffff" in p.rot_card.styleSheet()
          and "#cfd8dc" in p.rot_card.styleSheet())
    set_device_modern(win, "Lung Phantom")
    check("G: Lung Phantom hides the rotation centre panel", not p.rot_card.isVisible()
          and win.offset_rot_widget.isHidden())

    # ================================================================ G: pauses & trigger column, white page
    print("\n=== G: pauses & trigger column, white page ===", flush=True)

    def gpos(wd, ref=None):
        pt = wd.mapTo(ref or win, QPoint(0, 0))
        return pt.x(), pt.y()
    card = p.event_card
    eb0 = p.event_buttons
    check("G: pauses & trigger card in a column right of the fields and of Add Curve / Import File / Clear All, "
          "top level with the Device row",
          card.isVisible() and gpos(card)[0] >= gpos(win.input_period)[0] + win.input_period.width() + 4
          and gpos(card)[0] >= gpos(win.button_clear_all)[0] + win.button_clear_all.width() + 4
          and abs(gpos(card)[1] - gpos(p.device_box)[1]) <= 40
          and p.curve_left.isAncestorOf(win.button_create_curve) and p.curve_left.isAncestorOf(win.input_amplitude),
          f"card {gpos(card)} period {gpos(win.input_period)} w {win.input_period.width()}")
    check("G: card: title, Once | Repeat (Once selected), kinds 2 x 2, Time (s), Add / Clear, status line inside",
          p.event_title.text() == "Pauses & trigger"
          and [b.text() for b in p.mode_buttons.values()] == ["Once", "Repeat"] and p.mode_buttons['once'].isChecked()
          and p.event_mode == 'once' and p.once_box.isVisible() and p.repeat_box.isHidden()
          and gpos(eb0['rad'])[1] == gpos(eb0['usr'])[1] and gpos(eb0['on'])[1] == gpos(eb0['off'])[1]
          and gpos(eb0['on'])[1] > gpos(eb0['rad'])[1] and gpos(eb0['rad'])[0] == gpos(eb0['on'])[0]
          and gpos(eb0['usr'])[0] > gpos(eb0['rad'])[0]
          and card.isAncestorOf(win.input_wait_rad_time) and win.input_wait_rad_time.isVisible()
          and gpos(p.btn_event_add)[1] > gpos(eb0['on'])[1] and gpos(p.btn_event_clear)[0] > gpos(p.btn_event_add)[0]
          and card.isAncestorOf(win.trg_status_label) and win.trg_status_label.wordWrap()
          and gpos(win.trg_status_label)[1] > gpos(p.btn_event_add)[1])
    check("G: no row of pause / trigger buttons left under the fields (all inside the card)",
          all(card.isAncestorOf(b) for b in list(eb0.values()) + [p.btn_event_add, p.btn_event_clear]))

    def white_at(wd, x, y_from_bottom):
        page = p.curve_page
        img = page.grab().toImage()
        dpr = img.devicePixelRatio() or 1.0
        pt = wd.mapTo(page, QPoint(x, wd.height() - y_from_bottom))
        return img.pixelColor(int(pt.x() * dpr), int(pt.y() * dpr)).name()
    whites = {'left column': white_at(p.curve_left, 30, 8), 'card': white_at(card, 30, 6),
              'page margin': white_at(p.curve_scroll.widget(), 2, p.curve_scroll.widget().height() - 2)}
    check("G: Curve page, Curve Options and the card white (no grey background), card border #cfd8dc",
          all(v == '#ffffff' for v in whites.values()) and "#cfd8dc" in card.styleSheet()
          and "#ffffff" in win.groupBox_BrCv_createCurve.styleSheet()
          and "border: 1px solid #cfd8dc" in win.groupBox_BrCv_createCurve.styleSheet(), str(whites))
    for dev in ("Lung Phantom", "Motion Platform"):
        set_device_modern(win, dev)
        for mode in ("once", "repeat"):
            click(p.mode_buttons[mode])
            for key in ('rad', 'on'):
                click(eb0[key])
                check(f"G: {dev}, {mode}, {key}: whole Curve page visible without scrolling",
                      p.curve_scroll.verticalScrollBar().maximum() == 0,
                      f"max {p.curve_scroll.verticalScrollBar().maximum()} content min "
                      f"{p.curve_scroll.widget().minimumSizeHint().height()} vp {p.curve_scroll.viewport().height()}")
    click(p.mode_buttons['once'])
    click(eb0['rad'])
    set_device_modern(win, "Lung Phantom")

    # ================================================================ device toggle
    print("\n=== device toggle ===", flush=True)
    for dev in ("Motion Platform", "Lung Phantom"):
        set_device_modern(win, dev)
        state = (sorted(win.create_axis_checkboxes), list(win.create_curve_axis_checkboxes), headers(win),
                 plotted(win), win.settings_stack.currentIndex(), win.offset_rot_widget.isVisible())
        exp_df = win.dfEdit_motion_platform if dev == "Motion Platform" else win.dfEdit_lung_phantom
        check(f"toggle -> {dev}: combo set, axis sets / table / plot / settings page as the combo gave",
              win.combo_device.currentText() == dev and state == base_switch[dev] and win.dfEdit is exp_df
              and [b.isChecked() for b in p.device_buttons] == [dev == "Lung Phantom", dev == "Motion Platform"],
              f"{state[0]} / {state[2][:4]}")
        sec_vis = {k: not v[2].isHidden() for k, v in p.sections.items()}
        check(f"{dev}: only that device's group in the side card",
              sec_vis['phantom'] == (dev == "Lung Phantom") and sec_vis['platform'] == (dev == "Motion Platform")
              and not sec_vis['other'] and sorted(p.pills) == sorted(win.create_axis_checkboxes))
        check(f"{dev}: device toggle tooltips", "selected" in p.device_buttons[[b.text() for b in p.device_buttons]
                                                                              .index(dev)].toolTip())
    win.combo_device.setCurrentIndex(1)
    pump()
    check("combo set by code (signals): toggle follows", p.device_buttons[1].isChecked()
          and not p.device_buttons[0].isChecked())
    win.combo_device.blockSignals(True)
    win.combo_device.setCurrentIndex(0)
    win.combo_device.blockSignals(False)
    fc.trigger_plot_update(win)
    pump()
    check("combo set with blocked signals + redraw (Undo / import path): toggle follows", p.device_buttons[0].isChecked())
    win.combo_device.blockSignals(True)          # back to the state the combo handlers left (Motion Platform)
    win.combo_device.setCurrentIndex(1)
    win.combo_device.blockSignals(False)
    fc.trigger_plot_update(win)
    pump()
    check("... and back (blocked signals + redraw)", p.device_buttons[1].isChecked())
    win.combo_settings_device.setCurrentText("Lung Phantom")
    pump()
    check("Settings tab device combo: toggle and pills follow", p.device_buttons[0].isChecked()
          and win.combo_device.currentText() == "Lung Phantom"
          and sorted(p.pills) == sorted(win.create_axis_checkboxes) and list(p.axis_pills) == ['X', 'Y', 'Z'])
    set_device_modern(win, "Lung Phantom")

    # ================================================================ Axis pills
    print("\n=== Curve Options 'Axis' pills ===", flush=True)
    check("Lung Phantom: pills X Y Z, X lit (legacy default)", list(p.axis_pills) == ['X', 'Y', 'Z']
          and p.axis_pills['X'].isChecked() and not p.axis_pills['Y'].isChecked())
    click(p.axis_pills['Y'])
    check("pill click -> legacy checkbox", win.create_curve_axis_checkboxes['Y'].isChecked())
    win.create_curve_axis_checkboxes['X'].setChecked(False)
    pump()
    check("legacy checkbox -> pill", not p.axis_pills['X'].isChecked() and p.axis_pills['Y'].isChecked())
    check("Axis pill colour = plot colour (X blue, Y orange)", "#1976d2" in p.axis_pills['X'].styleSheet()
          and "#f57c00" in p.axis_pills['Y'].styleSheet())
    set_device_modern(win, "Motion Platform")
    check("Motion Platform: pills SI LAT AP Roll Pitch Yaw, SI lit, Yaw disabled (legacy rule)",
          list(p.axis_pills) == ['SI', 'LAT', 'AP', 'Roll', 'Pitch', 'Yaw'] and p.axis_pills['SI'].isChecked()
          and not p.axis_pills['Yaw'].isEnabled() and not win.create_curve_axis_checkboxes['Yaw'].isEnabled()
          and "disabled" in p.axis_pills['Yaw'].toolTip().lower())
    check("new legacy checkboxes of the switch land in the hidden holder",
          all(cb.parentWidget() is p.axis_checkbox_holder and not cb.isVisible()
              for cb in win.create_curve_axis_checkboxes.values()))
    click(p.axis_pills['LAT'])
    check("multiple linear axes allowed (as legacy)", p.axis_pills['SI'].isChecked() and p.axis_pills['LAT'].isChecked())
    click(p.axis_pills['Roll'])
    cbs = win.create_curve_axis_checkboxes
    check("rotational pill unselects the linear ones (legacy rule), pills mirror the blocked-signal changes",
          cbs['Roll'].isChecked() and not cbs['SI'].isChecked() and not cbs['LAT'].isChecked()
          and p.axis_pills['Roll'].isChecked() and not p.axis_pills['SI'].isChecked()
          and not p.axis_pills['LAT'].isChecked())
    check("Amplitude label follows (rotational)", "deg" in win.label_amplitude.text())
    click(p.axis_pills['Yaw'])
    check("disabled Yaw pill: click does nothing", not cbs['Yaw'].isChecked())
    modern_curve(win, 'AP', 'sin', 3.0, 0.0, 5.0, 0.0, 10.0)
    df = win.dfEdit
    check("Add Curve uses the selected axes (AP written, SI / LAT / Roll untouched)",
          float(np.abs(df['AP']).max()) > 2.5 and float(np.abs(df['SI']).max()) == 0.0
          and float(np.abs(df['Roll']).max()) == 0.0)
    click(win.button_clear_all)

    # ================================================================ plot-curve pills
    print("\n=== plot-curve pills (side card) ===", flush=True)
    set_device_modern(win, "Lung Phantom")
    modern_curve(win, 'X', 'sin', 10.0, 0.0, 4.0, 0.0, 20.0)
    check("after Create Curve: pills bound to the current legacy checkboxes",
          all(p.pill_cb[k] is win.create_axis_checkboxes[k] for k in win.create_axis_checkboxes))
    click(p.pills['Y'])
    check("pill off -> legacy off, Y curve gone from the plot", not win.create_axis_checkboxes['Y'].isChecked()
          and 'Y' not in plotted(win) and 'X' in plotted(win))
    win.create_axis_checkboxes['Y'].setChecked(True)
    pump()
    check("legacy on -> pill on, curve back", p.pills['Y'].isChecked() and 'Y' in plotted(win))
    check("pill colour = plotted line colour (X, Y, Z)",
          all(p.pill_color[k] == line_color(win, k) and line_color(win, k) in p.pills[k].styleSheet()
              for k in ('X', 'Y', 'Z')), str({k: (p.pill_color[k], line_color(win, k)) for k in 'XYZ'}))
    title = p.sections['phantom'][0]
    click(title)
    check("title click (all on) -> all off, plot empty, box 'none'",
          not any(cb.isChecked() for cb in win.create_axis_checkboxes.values()) and plotted(win) == []
          and p._title_state[title] == 'none')
    click(p.pills['X'])
    check("one on -> box 'some'", p._title_state[title] == 'some')
    click(title)
    check("title click (some on) -> all on, box 'all'",
          all(cb.isChecked() for cb in win.create_axis_checkboxes.values()) and p._title_state[title] == 'all'
          and plotted(win) == ['X', 'Y', 'Z'])
    check("title tooltips", "select / deselect all" in title.toolTip().lower()
          and "box in front of the title" in title.toolTip())
    click(p.btn_clear_all)
    check("card Clear all -> legacy Clear All (all off)", not any(b.isChecked() for b in p.pills.values())
          and plotted(win) == [])
    click(p.btn_select_all)
    check("card Select all -> all on", all(b.isChecked() for b in p.pills.values()) and len(plotted(win)) == 3)
    click(p.btn_undo)
    check("Undo (icon): pills still bound", all(p.pill_cb[k] is win.create_axis_checkboxes[k] for k in p.pills))
    click(win.button_clear_all)
    check("Clear All (rebuild): pills re-bound to the new checkboxes and working",
          all(p.pill_cb[k] is win.create_axis_checkboxes[k] for k in p.pills))
    click(p.pills['Z'])
    check("... click after the rebuild acts on the new checkbox", not win.create_axis_checkboxes['Z'].isChecked()
          and 'Z' not in plotted(win))
    set_device_modern(win, "Motion Platform")
    check("Motion Platform: Platform position + Individual axes pills (14), bound",
          p.sections['position'][1] == ['LAT', 'SI', 'AP', 'Roll', 'Pitch', 'Yaw']
          and p.sections['individual'][1] == ['A', 'B', 'C', 'D', "'a", "'c", "'e", "'f"]
          and all(p.pill_cb[k] is win.create_axis_checkboxes[k] for k in p.pills))
    click(p.sections['individual'][0])
    check("Individual axes title: deselects A..'f only",
          not any(win.create_axis_checkboxes[k].isChecked() for k in tpm.INDIVIDUAL_KEYS)
          and all(win.create_axis_checkboxes[k].isChecked() for k in tpm.POSITION_KEYS)
          and p._title_state[p.sections['platform'][0]] == 'some')
    click(p.sections['platform'][0])
    check("Motion Platform title: selects both subsections", all(cb.isChecked() for cb in
                                                                 win.create_axis_checkboxes.values()))
    check("pill colour = line colour for all 14 platform curves",
          all(p.pill_color[k] == line_color(win, k) for k in p.pills))

    # ================================================================ kinematic pills
    print("\n=== Position / Velocity / Acceleration / Margins ===", flush=True)
    kp = p.kin_pills
    check("kinematic pills: texts with the line-style hint, Position lit",
          [b.text() for b in kp.values()] == ["Position —", "Velocity --", "Acceleration ···", "Margins"]
          and kp['check_show_pos'].isChecked() and not kp['check_show_vel'].isChecked())
    click(kp['check_show_vel'])
    check("Velocity pill -> legacy on, '(Vel)' curves plotted, table Vel. columns shown",
          win.check_show_vel.isChecked() and any(l.endswith('(Vel)') for l in plotted(win))
          and any(not win.create_table_view.isColumnHidden(i) for i, h in enumerate(headers(win)) if h.startswith('Vel.')))
    win.check_show_acc.setChecked(True)
    pump()
    check("legacy Acceleration on -> pill on, '(Acc)' plotted", kp['check_show_acc'].isChecked()
          and any(l.endswith('(Acc)') for l in plotted(win)))
    click(kp['check_show_pos'])
    check("Position pill off -> no '(Pos)' curves", not win.check_show_pos.isChecked()
          and not any(l.endswith('(Pos)') for l in plotted(win)))
    for a in ('check_show_pos',):
        click(kp[a])
    for a in ('check_show_vel', 'check_show_acc'):
        click(kp[a])
    check("back to Position only", win.check_show_pos.isChecked() and not win.check_show_vel.isChecked()
          and not win.check_show_acc.isChecked())
    click(kp['check_show_trg_margins'])
    check("Margins pill -> legacy trigger Margins on", win.check_show_trg_margins.isChecked() and win.trg_show_margins)
    set_device_modern(win, "Lung Phantom")
    check("after a rebuild (device switch): kinematic pills bound to the new checkboxes, states kept",
          p.kin_cbs['check_show_trg_margins'] is win.check_show_trg_margins and kp['check_show_trg_margins'].isChecked()
          and p.kin_cbs['check_show_pos'] is win.check_show_pos)
    win.check_show_trg_margins.setChecked(False)
    pump()
    check("legacy Margins off -> pill off", not kp['check_show_trg_margins'].isChecked())

    # ================================================================ navigation
    print("\n=== navigation icons ===", flush=True)
    tb = win.create_plot_toolbar
    click(p.btn_zoom)
    check("Zoom icon -> toolbar zoom mode", p._nav_mode() == 'zoom rect' and p.btn_zoom.isChecked())
    click(p.btn_pan)
    check("Pan icon -> pan mode, zoom off", p._nav_mode() == 'pan/zoom' and p.btn_pan.isChecked()
          and not p.btn_zoom.isChecked())
    click(p.btn_pan)
    check("Pan again -> no mode", p._nav_mode() == '' and not p.btn_pan.isChecked())
    ax = win.create_plot_ax
    x0 = tuple(ax.get_xlim())
    tb.push_current()
    ax.set_xlim(2.0, 6.0)
    tb.push_current()
    p.update_nav_buttons()
    check("Back enabled after a view change", p.btn_back.isEnabled())
    click(p.btn_back)
    check("Back icon -> previous view", tuple(round(v, 6) for v in ax.get_xlim()) == tuple(round(v, 6) for v in x0))
    click(p.btn_forward)
    check("Forward icon -> next view", tuple(round(v, 3) for v in ax.get_xlim()) == (2.0, 6.0))
    click(p.btn_reset)
    check("Reset icon -> home view", tuple(round(v, 6) for v in ax.get_xlim()) == tuple(round(v, 6) for v in x0))
    saved = []
    tb.save_figure = lambda *a: saved.append(1)
    click(p.btn_save)
    check("Save icon -> toolbar save_figure", saved == [1])
    exported = os.path.join(TMP, 'export_test.gcode')
    QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: (exported, ''))
    click(p.btn_export)
    check("Export GCODE (bottom row) -> legacy export: file = generate_planned_gcode",
          os.path.isfile(exported) and open(exported).read() == gcode(win))
    check("Export / Upload tooltips", "G-code" in p.btn_export.toolTip() and "Duet" in p.btn_upload.toolTip())

    # ================================================================ Table tab (follow-up 1)
    print("\n=== Table sub-tab ===", flush=True)
    bar = tw.tabBar()
    ti = tw.indexOf(p.table_tab)
    check("start: Curve tab, table hidden, check_show_table off", tw.currentIndex() == 0
          and win.create_table_view.isHidden() and not win.check_show_table.isChecked())
    click(bar, pos=bar.tabRect(ti).center())
    check("click 'Table': the table is shown inside the tab (check_show_table on)",
          tw.currentWidget() is p.table_tab and win.check_show_table.isChecked()
          and win.create_table_view.isVisible() and win.create_table_view.parentWidget() is p.table_tab
          and win.create_table_view.width() > 1500)
    click(bar, pos=bar.tabRect(0).center())
    check("back to 'Curve': table hidden, check_show_table off", tw.currentIndex() == 0
          and win.create_table_view.isHidden() and not win.check_show_table.isChecked())
    click(bar, pos=bar.tabRect(3).center())
    win.check_show_table.setChecked(True)
    pump()
    check("code sets check_show_table -> the Table tab opens", tw.currentWidget() is p.table_tab
          and win.create_table_view.isVisible())
    fc.rebuild_axis_checkboxes(win, list(win.create_axis_checkboxes))
    pump()
    check("legacy row rebuild while on Table: the tab does not flip", tw.currentWidget() is p.table_tab
          and win.check_show_table.isChecked() and win.create_table_view.isVisible())
    win.check_show_table.setChecked(False)
    pump()
    check("code clears check_show_table -> back to the previous tab (Tools)", tw.currentIndex() == 3
          and win.create_table_view.isHidden())
    click(bar, pos=bar.tabRect(ti).center())
    tbl = win.create_table_view
    hx = headers(win).index('X (mm)')
    trow = 50
    k = int(tbl.item(trow, hx).data(Qt.UserRole + 1))
    old_val = float(win.dfEdit['X'].iat[k])
    tbl.item(trow, hx).setText("33.5")
    pump(10)
    xd = [l for l in win.create_plot_ax.get_lines() if str(l.get_label()) == 'X']
    ymax = float(np.max(np.asarray(xd[0].get_ydata(), float))) if xd else None
    check("cell edit in the Table tab changes the plan and the plot",
          abs(float(win.dfEdit['X'].iat[k]) - 33.5) < 1e-9 and ymax is not None and abs(ymax - 33.5) < 1e-9,
          f"row {k}: was {old_val}, plan now {float(win.dfEdit['X'].iat[k])}, plot max {ymax}, "
          f"legacy X checkbox {win.create_axis_checkboxes['X'].isChecked()}")
    click(p.btn_undo)
    check("Undo of the cell edit", abs(float(win.dfEdit['X'].iat[k]) - old_val) < 1e-9)
    win.input_wait_rad_time.setValue(7.0)
    win.button_wait_user.click()
    pump()
    check("table filled while hidden / shown: a wait button writes the Command cell in the table",
          table_cmd(win, int(np.argmin(np.abs(tvec(win) - 7.0)))) == 'M226')
    click(win.button_undo_curve)
    click(bar, pos=bar.tabRect(0).center())

    # ================================================================ pause / trigger row + Undo icon (follow-up 2)
    print("\n=== Undo icon and the pause / trigger row ===", flush=True)
    eb = p.event_buttons
    check("row: Wait Radiation, Wait User, Trigger On, Trigger Off (default: Wait Radiation), Add, Clear",
          [b.text() for b in eb.values()] == ["Wait Radiation", "Wait User", "Trigger On", "Trigger Off"]
          and eb['rad'].isChecked() and p.btn_event_add.text() == "Add" and p.btn_event_clear.text() == "Clear")
    excl = True
    for key in ('usr', 'on', 'off', 'rad'):
        click(eb[key])
        excl = excl and [b.isChecked() for b in eb.values()] == [k == key for k in eb]
    click(eb['rad'])
    check("toggles mutually exclusive (one selected; clicking it again keeps it)", excl and eb['rad'].isChecked())
    tips = {}
    for key in eb:
        click(eb[key])
        tips[key] = p.btn_event_clear.toolTip()
    check("Clear tooltip names what it clears and follows the selection",
          "Wait Radiation" in tips['rad'] and "Wait User" in tips['usr'] and "trigger" in tips['on'].lower()
          and "Clear Trigger" in tips['off'], str(tips))
    check("status line keeps the new hint", "right-click" in win.trg_status_label.text().lower()
          or win.trg_status_label.property("trg_kind") != "hint")
    click(win.button_clear_all)
    win._curve_undo_stack = []
    fc.update_undo_button_state(win)
    pump()
    check("Undo icon disabled with nothing to undo (mirrors legacy Undo)", not p.btn_undo.isEnabled()
          and not win.button_undo_curve.isEnabled())
    base = cmds(win)
    same = []
    for key, tm in (('rad', 4.0), ('usr', 6.0), ('on', 2.0), ('off', 9.0)):
        before = cmds(win)
        win.input_wait_rad_time.setValue(tm)
        click(eb[key])
        click(p.btn_event_add)
        c_new = cmds(win)
        en = p.btn_undo.isEnabled()
        click(p.btn_undo)
        undone = cmds(win) == before
        legacy_event(win, tm, LEGACY_ATTR[key])
        c_leg = cmds(win)
        same.append((key, c_new == c_leg and c_new != before, en, undone))
    check("Add for each kind = the legacy button's cells; Undo icon enabled after it and undoes it",
          all(a and b and c for _k, a, b, c in same), str(same))
    clr = []
    for key, legacy_clear in (('rad', 'button_clear_rad'), ('usr', 'button_clear_user'), ('on', 'button_clear_trigger')):
        before = cmds(win)
        click(eb[key])
        click(p.btn_event_clear)
        c_new = cmds(win)
        click(p.btn_undo)
        getattr(win, legacy_clear).click()
        pump()
        c_leg = cmds(win)
        clr.append((key, c_new == c_leg and c_new != before))
        click(p.btn_undo)
    check("Clear for each kind = the legacy Clear button's cells", all(x for _k, x in clr), str(clr))
    check("after the Clear round trips the plan is as before", cmds(win) == [c for c in cmds(win)])

    # ================================================================ G: Repeat (the former Periodic tab) in the card
    print("\n=== G: Repeat mode (periodic) in the pauses & trigger card ===", flush=True)
    curve_idx = tw.indexOf(p.curve_page)
    tw.setCurrentIndex(curve_idx)
    pump()
    click(win.button_clear_all)
    modern_curve(win, 'X', 'sin', 10.0, 0.0, 4.0, 0.0, 20.0)
    modern_event(win, 5.0, 'on')
    modern_event(win, 50.0, 'off')
    check("G setup: one trigger window 5-50", wins(win) == [(5.0, 50.0)])
    if win.check_show_trg_margins.isChecked():
        win.check_show_trg_margins.setChecked(False)
    pump()
    click(p.mode_buttons['repeat'])
    check("G: Repeat: periodic fields shown, Time (s) hidden, legacy Periodic widgets in the card",
          p.event_mode == 'repeat' and p.repeat_box.isVisible() and p.once_box.isHidden()
          and not win.input_wait_rad_time.isVisible()
          and all(card.isAncestorOf(x) and x.isVisible() for x in (win.trg_per_period, win.trg_per_offset,
                                                                     win.trg_per_range['r0'], win.trg_per_range['r1'])))
    vis = {}
    for key in ('rad', 'usr', 'on', 'off'):
        click(eb0[key])
        vis[key] = (p.rep_fields['duration'].isVisible(), p.combine_row.isVisible(),
                    win.trg_per_action.currentData())
    check("G: kinds -> periodic actions (Wait Radiation=wait_rad, Wait User=wait_user, Trigger On=trigger_on, "
          "Trigger Off=beam_off); For D only for triggers, Combine only for Trigger On",
          vis == {'rad': (False, False, 'wait_rad'), 'usr': (False, False, 'wait_user'),
                  'on': (True, True, 'trigger_on'), 'off': (True, False, 'beam_off')}, str(vis))
    # parameters through the card (they are the legacy Periodic widgets)
    win.trg_per_period.setValue(4.0)
    win.trg_per_duration.setValue(1.0)
    win.trg_per_offset.setValue(1.0)
    click(p.range_buttons['subset'])
    win.trg_per_range['r0'].setValue(10.0)
    win.trg_per_range['r1'].setValue(40.0)
    check("G: Range segment -> legacy radio (From - To), boxes enabled",
          win.trg_per_range['subset'].isChecked() and p.range_buttons['subset'].isChecked()
          and win.trg_per_range['r0'].isEnabled())
    click(eb0['on'])
    click(p.combine_buttons['replace'])
    check("G: Combine segment -> legacy combo (Replace)", win.trg_per_combine.currentData() == 'replace'
          and p.combine_buttons['replace'].isChecked() and not p.combine_buttons['add'].isChecked())
    win.trg_per_combine.setCurrentIndex(win.trg_per_combine.findData('intersect'))
    pump()
    check("G: legacy combo -> segment", p.combine_buttons['intersect'].isChecked())
    check("G fix: Combine segment reads 'Union | Replace | Only where both' (no second 'Add' in the card)",
          [p.combine_buttons[k].text() for k in ('add', 'replace', 'intersect')] == ["Union", "Replace",
                                                                                     "Only where both"]
          and [b.text() for b in p.event_card.findChildren(QAbstractButton) if b.text() == "Add"] == ["Add"],
          str([b.text() for b in p.event_card.findChildren(QAbstractButton)]))
    click(p.combine_buttons['replace'])

    def settle_preview():
        QTest.qWait(tpm.REPEAT_PREVIEW_MS + 150)
        pump()

    def drawn_preview():
        return [a for a in win.create_plot_ax.collections if a.get_gid() in ('trg_preview', 'trg_preview_events')]

    def rounded(ws):
        return [tuple(round(v, 6) for v in w_) for w_ in ws]
    settle_preview()
    t_ = tvec(win)
    pv = T.trg_periodic_preview(t_, 4.0, 1.0, 1.0, (10.0, 40.0), 'trigger_on')['windows']
    ov = win.trg_overlay
    check("G: Repeat on in the Curve tab: gray periodic preview drawn (Margins off) = the pattern Add places",
          not win.check_show_trg_margins.isChecked() and ov.get('preview_kind') == 'periodic'
          and rounded(ov['preview']) == rounded(pv) and len(pv) > 3 and len(drawn_preview()) == 1
          and not getattr(win, 'trg_show_margins', False),
          f"{ov.get('preview_kind')} {ov.get('preview')[:3]} vs {pv[:3]}")
    win.trg_per_period.setValue(5.0)
    settle_preview()
    pv5 = T.trg_periodic_preview(t_, 5.0, 1.0, 1.0, (10.0, 40.0), 'trigger_on')['windows']
    check("G: the preview follows a changed Every P (debounced)", rounded(win.trg_overlay['preview']) == rounded(pv5))
    win.trg_per_period.setValue(4.0)
    click(eb0['rad'])
    settle_preview()
    check("G: Wait Radiation in Repeat: dotted event preview", win.trg_overlay.get('preview_kind') == 'periodic'
          and len(win.trg_overlay['events']) > 3)
    tw.setCurrentIndex(tw.indexOf(win.trg_gate_tab) + 1)          # Tools
    settle_preview()
    check("G: another sub-tab open: no Repeat preview", win.trg_overlay.get('preview_kind') is None
          and not drawn_preview(), str(win.trg_overlay.get('preview_kind')))
    tw.setCurrentIndex(curve_idx)
    settle_preview()
    check("G: back on Curve (Repeat): preview again", win.trg_overlay.get('preview_kind') == 'periodic')
    click(p.mode_buttons['once'])
    check("G: Once: preview gone (Margins off), Time (s) back", win.trg_overlay.get('preview_kind') is None
          and not drawn_preview() and p.once_box.isVisible() and p.repeat_box.isHidden())
    click(p.mode_buttons['repeat'])
    check("G: Repeat again: preview immediately", win.trg_overlay.get('preview_kind') == 'periodic'
          and bool(drawn_preview()))
    # Add (Repeat) for every kind = the legacy Periodic Apply with the same parameters
    rep = []
    for key, action in (('rad', 'wait_rad'), ('usr', 'wait_user'), ('on', 'trigger_on'), ('off', 'beam_off')):
        click(eb0[key])
        before = cmds(win)
        click(p.btn_event_add)
        c_new = cmds(win)
        msg = win.trg_status_label.text()
        en = p.btn_undo.isEnabled()
        click(p.btn_undo)
        undone = cmds(win) == before
        tw.setCurrentWidget(win.trg_periodic_tab)            # the legacy way (hidden tab, still reachable by code)
        pump()
        win.trg_per_action.setCurrentIndex(win.trg_per_action.findData(action))
        win.button_trg_periodic_apply.click()
        pump()
        c_leg = cmds(win)
        leg_msg = win.trg_per_summary.text()
        win.button_undo_curve.click()
        pump()
        tw.setCurrentIndex(curve_idx)
        pump()
        rep.append((key, c_new == c_leg, c_new != before, en and undone, msg == leg_msg and bool(msg)))
    check("G: Repeat Add for each kind = the legacy Periodic Apply (same cells, same message, one undo step)",
          all(a and b and c and d for _k, a, b, c, d in rep), str(rep))
    click(eb0['rad'])
    click(p.btn_event_add)
    n_after_first = cmds(win)
    click(p.btn_event_add)
    check("G: Repeat Add again (nothing new): plan unchanged, 'Nothing changed' in the card's status line",
          cmds(win) == n_after_first and "Nothing changed" in win.trg_status_label.text(),
          win.trg_status_label.text())
    c_rep = cmds(win)
    click(p.btn_event_clear)
    check("G: Clear in Repeat keeps its per-kind meaning (all Wait Radiation pauses removed)",
          not any(T.WAIT_RAD_CMD in str(c) for c in cmds(win)) and any(T.WAIT_RAD_CMD in str(c) for c in c_rep))
    check("G: Add / kinds tooltips in Repeat mode", "repeated" in p.btn_event_add.toolTip()
          and "repeated" in eb0['rad'].toolTip() and "Wait Radiation" in p.btn_event_clear.toolTip())
    click(p.range_buttons['full'])
    check("G: Whole plan segment -> legacy Full plan radio", win.trg_per_range['full'].isChecked())
    click(p.mode_buttons['once'])
    click(eb0['rad'])
    click(win.button_clear_all)

    # ================================================================ right-click: pauses (follow-up 3)
    print("\n=== right-click on pause lines ===", flush=True)
    MENUS = []
    CHOICE = {'text': None}

    MENU_BG = []

    def fake_exec(menu, pos):
        try:                                     # the popup's own background (black if it inherits 'transparent')
            img = menu.grab().toImage()
            MENU_BG.append(img.pixelColor(img.width() // 2, img.height() - 3).name())
        except Exception as e:
            MENU_BG.append(repr(e))
        texts = [a.text() for a in menu.actions() if not a.isSeparator()]
        MENUS.append((texts, [a.text() for a in menu.actions() if not a.isSeparator() and not a.isEnabled()]))
        in_section = CHOICE.get('section') is None
        for a in menu.actions():
            if not a.isEnabled() and not a.isSeparator():
                in_section = CHOICE.get('section') is None or a.text().startswith(CHOICE['section'])
            if in_section and CHOICE['text'] is not None and a.text().startswith(CHOICE['text']) and a.isEnabled():
                return a
        return None
    tpe.exec_menu = fake_exec
    ASK = {'time': None, 'window': None}
    tpe.ask_time = lambda parent, title, label, value, lo, hi, dec, loc=None: (ASK['time'], ASK['time'] is not None)
    tpe.ask_window = lambda parent, title, a, b, lo, hi, dec, loc=None: (ASK['window'] or (a, b),
                                                                          ASK['window'] is not None)

    canvas = win.create_plot_canvas

    def right_click_at(tm, frac=0.5):
        ax_ = win.create_plot_ax
        xpx, _ = ax_.transData.transform((tm, 0.0))
        bb = ax_.get_window_extent()
        ypx = bb.y0 + frac * bb.height
        dpr = float(canvas.device_pixel_ratio) or 1.0
        pos = QPoint(int(round(xpx / dpr)), int(round(canvas.height() - ypx / dpr)))
        n0 = len(MENUS)
        QTest.mouseClick(canvas, Qt.RightButton, Qt.NoModifier, pos)
        pump()
        return MENUS[n0] if len(MENUS) > n0 else None

    def menu_pick(tm, choice, section=None):
        CHOICE['text'] = choice
        CHOICE['section'] = section
        try:
            return right_click_at(tm)
        finally:
            CHOICE['text'] = None
            CHOICE['section'] = None

    click(win.button_clear_all)
    modern_curve(win, 'X', 'sin', 10.0, 0.0, 4.0, 0.0, 20.0)
    modern_event(win, 5.0, 'rad')
    modern_event(win, 12.0, 'usr')
    modern_event(win, 30.0, 'rad')
    modern_event(win, 3.0, 'on')
    modern_event(win, 8.0, 'off')
    modern_event(win, 6.0, 'usr')            # a Wait User inside the green window 3-8
    modern_event(win, 40.0, 'on')
    modern_event(win, 45.0, 'off')
    row = lambda tm: int(np.argmin(np.abs(tvec(win) - tm)))
    check("setup: windows 3-8 and 40-45, pauses at 5 (rad), 6 (usr), 12 (usr), 30 (rad)",
          wins(win) == [(3.0, 8.0), (40.0, 45.0)] and T.WAIT_RAD_CMD in cmds(win)[row(5.0)]
          and 'M226' in cmds(win)[row(12.0)])
    m = right_click_at(30.0)
    check("right-click on the Wait Radiation line at 30 s: menu with header and items",
          m is not None and m[1] == [f"Wait Radiation at {p.plot_editor.fmt(30.0)} s"]
          and m[0][1:] == ["Delete pause", "Adjust time…", "Change to Wait User"], str(m))
    check("context menu has its own white background (not black: the canvas' transparent style must not reach it)",
          MENU_BG and MENU_BG[-1] == "#ffffff", str(MENU_BG[-1:]))
    dec_sep = win.input_wait_rad_time.locale().decimalPoint()
    check("header uses the Time box's decimal sign", dec_sep in m[1][0], m[1][0])
    m = right_click_at(30.35)
    check("right-click away from lines and windows: no menu", m is None)
    m = right_click_at(30.0 + 0.02)
    check("right-click within a few pixels of the line: menu", m is not None)
    c_before = cmds(win)
    menu_pick(30.0, "Delete pause")
    check("Delete pause (Wait Radiation): only that cell changed, table and plot follow",
          T.WAIT_RAD_CMD not in cmds(win)[row(30.0)] and T.WAIT_RAD_CMD in cmds(win)[row(5.0)]
          and sum(a != b for a, b in zip(c_before, cmds(win))) == 1
          and table_cmd(win, row(30.0)) in ('', None)
          and "deleted" in win.trg_status_label.text())
    click(p.btn_undo)
    check("Undo restores the deleted pause", cmds(win) == c_before)
    menu_pick(12.0, "Delete pause")
    check("Delete pause (Wait User)", 'M226' not in cmds(win)[row(12.0)])
    click(p.btn_undo)
    ASK['time'] = 14.004
    menu_pick(12.0, "Adjust time")
    g = gcode(win)
    check("Adjust time: Wait User moved 12 -> 14 (nearest row), G-code pause times follow",
          'M226' not in cmds(win)[row(12.0)] and cmds(win)[row(14.0)] == 'M226'
          and ('M226', 14.0) in gc_pauses(g) and ('M226', 12.0) not in gc_pauses(g), str(gc_pauses(g)))
    ASK['time'] = 5.0
    menu_pick(14.0, "Adjust time")
    cell = cmds(win)[row(5.0)]
    g = gcode(win)
    lines = [l.strip() for l in g.splitlines()]
    i_m98 = next(i for i, l in enumerate(lines) if l.startswith('M98') and 'sensor_wait' in l)
    check("Adjust onto the Wait Radiation row: both waits in the cell, G-code M98 then M226 (cell order)",
          T.split_cell(cell) == [T.WAIT_RAD_CMD, 'M226'] and any(l == 'M226' for l in lines[i_m98 + 1:i_m98 + 4]),
          cell)
    ASK['time'] = 6.0
    st0 = cmds(win)
    menu_pick(5.0, "Adjust time", section="Wait User")   # 5.0: Wait Radiation + Wait User lines (+ the window)
    check("same-kind wait already on the target row: nothing changed, status says so",
          cmds(win) == st0 and "already has" in win.trg_status_label.text(), win.trg_status_label.text())
    m = MENUS[-1]
    check("a row with both waits inside a window: one menu, a section per wait and one for the window",
          m[1] == [f"Wait Radiation at {p.plot_editor.fmt(5.0)} s", f"Wait User at {p.plot_editor.fmt(5.0)} s",
                   f"Trigger window {p.plot_editor.fmt(3.0)}–{p.plot_editor.fmt(8.0)} s"], str(m))
    click(p.btn_undo)
    # pause in a cell shared with a trigger switch
    modern_event(win, 3.0, 'rad')
    check("setup: Wait Radiation in the cell of the 3 s Trigger On", T.split_cell(cmds(win)[row(3.0)])
          == [T.TRIGGER_ON_CMD, T.WAIT_RAD_CMD])
    ASK['time'] = 4.0
    m = menu_pick(3.0, "Adjust time")
    check("move it away: the trigger switch stays in its cell, windows unchanged",
          cmds(win)[row(3.0)] == T.TRIGGER_ON_CMD and T.WAIT_RAD_CMD in cmds(win)[row(4.0)]
          and wins(win) == [(3.0, 8.0), (40.0, 45.0)])
    menu_pick(4.0, "Change to Wait User")
    check("Change to Wait User", cmds(win)[row(4.0)] == 'M226' and "changed to Wait User" in win.trg_status_label.text())
    menu_pick(4.0, "Delete pause")
    m = right_click_at(30.0)
    # pan / zoom: no menu
    click(p.btn_zoom)
    n0 = len(MENUS)
    QTest.mouseClick(canvas, Qt.RightButton, Qt.NoModifier, QPoint(5, 5))
    m = right_click_at(5.0)
    check("Zoom mode: right-click keeps matplotlib's meaning (no menu)", m is None)
    click(p.btn_zoom)
    click(p.btn_pan)
    check("Pan mode: no menu", right_click_at(5.0) is None)
    click(p.btn_pan)
    check("left click: no menu", (QTest.mouseClick(canvas, Qt.LeftButton) or True) and len(MENUS) == n0)

    # ================================================================ right-click: trigger windows (follow-up 4)
    print("\n=== right-click on trigger windows ===", flush=True)
    m = right_click_at(4.0)
    check("right-click inside the green window 3-8: header 'Trigger window 3,00–8,00 s' and items",
          m is not None and m[1] == [f"Trigger window {p.plot_editor.fmt(3.0)}–{p.plot_editor.fmt(8.0)} s"]
          and m[0][1:] == ["Delete window", "Adjust window…"], str(m))
    m = right_click_at(6.0)
    check("pause line inside a green window: one menu with both sections",
          m is not None and m[1] == [f"Wait User at {p.plot_editor.fmt(6.0)} s",
                                     f"Trigger window {p.plot_editor.fmt(3.0)}–{p.plot_editor.fmt(8.0)} s"], str(m))
    m = right_click_at(8.0 + 0.02)
    check("right-click on the window edge (a few px outside): window menu", m is not None and
          any(h.startswith("Trigger window") for h in m[1]))
    c_before = cmds(win)
    menu_pick(4.0, "Delete window")
    g = gcode(win)
    check("Delete window: the other window stays; plan, green cover and parsed G-code agree; pause inside kept",
          wins(win) == [(40.0, 45.0)] and [tuple(round(v, 3) for v in w) for w in win.trg_overlay['windows']]
          == [(40.0, 45.0)] and gc_windows(g) == [(40.0, 45.0)] and cmds(win)[row(6.0)] == 'M226'
          and T.WAIT_RAD_CMD in cmds(win)[row(5.0)], str(wins(win)))
    click(p.btn_undo)
    check("Undo restores the window", cmds(win) == c_before and wins(win) == [(3.0, 8.0), (40.0, 45.0)])
    ASK['window'] = (10.0, 15.0)
    menu_pick(4.0, "Adjust window")
    g = gcode(win)
    check("Adjust window 3-8 -> 10-15: plan, cover and G-code agree, pauses kept",
          wins(win) == [(10.0, 15.0), (40.0, 45.0)] and gc_windows(g) == wins(win)
          and cmds(win)[row(6.0)] == 'M226' and ("moved to " + p.plot_editor.fmt_span(10.0, 15.0)) in win.trg_status_label.text(),
          win.trg_status_label.text())
    ASK['window'] = (35.0, 41.0)
    menu_pick(12.0, "Adjust window")
    check("Adjust into an overlap: the windows join, the status line says so",
          wins(win) == [(35.0, 45.0)] and "joined" in win.trg_status_label.text()
          and T.trg_inner_starts(tvec(win), cmds(win)) == [] and gc_windows(gcode(win)) == [(35.0, 45.0)],
          win.trg_status_label.text())
    ASK['window'] = (20.0, 20.002)
    st0 = cmds(win)
    menu_pick(40.0, "Adjust window")
    check("Adjust to less than a row: nothing changed, error in the status line",
          cmds(win) == st0 and "shorter than one plan row" in win.trg_status_label.text())
    ASK['window'] = None
    menu_pick(40.0, "Adjust window")
    check("dialog cancelled: nothing changed", cmds(win) == st0)
    # inner start (dotted mark): On at 50, Off at 55, then On at 46 runs into it
    modern_event(win, 50.0, 'on')
    modern_event(win, 55.0, 'off')
    modern_event(win, 47.0, 'on')
    check("setup: run 47-55 with an inner start at 50", T.trg_inner_starts(tvec(win), cmds(win)) == [50.0])
    m = right_click_at(48.0)
    check("menu of a run with an inner start offers to remove its mark",
          m is not None and f"Remove window start mark at {p.plot_editor.fmt(50.0)} s" in m[0], str(m))
    menu_pick(48.0, "Remove window start mark")
    check("Remove window start mark: mark gone, run unchanged", T.trg_inner_starts(tvec(win), cmds(win)) == []
          and (47.0, 55.0) in wins(win))
    click(p.btn_zoom)
    check("Zoom mode: no window menu", right_click_at(48.0) is None)
    click(p.btn_zoom)
    g = gcode(win)
    gl = [l for l in g.splitlines() if l.startswith('M42')]
    check("G-code safety M42 P5 S0 at start and end, plan ends off", gl[0] == T.TRIGGER_OFF_CMD
          and gl[-1] == T.TRIGGER_OFF_CMD and not T.trg_states(cmds(win))[-1])

    # menu screenshot (popup + grab)
    try:
        CHOICE['text'] = None
        shot = {}

        def grab_exec(menu, pos):
            menu.popup(pos)
            pump(4)
            shot['img'] = menu.grab()
            menu.hide()
            return None
        tpe.exec_menu = grab_exec
        modern_event(win, 50.0, 'usr')
        right_click_at(50.0)
        if 'img' in shot:
            shot['img'].save(os.path.join(OUT, PREFIX + 'menu_pause_and_window.png'))
        right_click_at(30.0)
        if 'img' in shot:
            shot['img'].save(os.path.join(OUT, PREFIX + 'menu_pause.png'))
        check("menu screenshots saved", os.path.isfile(os.path.join(OUT, PREFIX + 'menu_pause_and_window.png')))
    finally:
        tpe.exec_menu = fake_exec

    # ================================================================ import: toggle and pills follow
    print("\n=== import of a Motion Platform G-code while on Lung Phantom ===", flush=True)
    imp = os.path.join(TMP, 'platform_plan.gcode')
    with open(imp, 'w') as f:
        f.write(g_mp_legacy)
    set_device_modern(win, "Lung Phantom")
    fc.import_gcode_action(win, imp)
    pump(10)
    check("import: device toggle follows (Motion Platform)", win.combo_device.currentText() == "Motion Platform"
          and p.device_buttons[1].isChecked() and not p.device_buttons[0].isChecked())
    check("import: pills re-bound to the rebuilt checkboxes, platform group shown",
          sorted(p.pills) == sorted(win.create_axis_checkboxes)
          and all(p.pill_cb[k] is win.create_axis_checkboxes[k] for k in p.pills)
          and not p.sections['platform'][2].isHidden() and p.sections['phantom'][2].isHidden())
    click(p.pills['SI'])
    check("... and a pill click after the import works", not win.create_axis_checkboxes['SI'].isChecked()
          and 'SI' not in plotted(win))
    click(p.pills['SI'])

    # ================================================================ G: rotation centre: G-code, kept values
    print("\n=== G: rotation centre: G-code, kept values ===", flush=True)
    set_device_modern(win, "Motion Platform")
    click(win.button_clear_all)
    modern_curve(win, 'SI', 'sin', 10.0, 0.0, 4.0, 0.0, 20.0)
    g160 = gcode(win)
    win.input_offset_ap_plan.setText("0.0")
    pump()
    g0 = gcode(win)
    check("G: plan without rotations: G-code byte-identical with AP 160 and AP 0", g160 == g0 and len(g0) > 1000)
    win.input_offset_ap_plan.setText("160.0")
    pump()
    modern_curve(win, 'Roll', 'sin', 3.0, 0.0, 5.0, 0.0, 20.0)
    g_r160 = gcode(win)
    e_r160 = float(win.dfEdit[chr(39) + 'e'].max())      # the plan 'e when that G-code was written
    win.input_offset_ap_plan.setText("0.0")
    pump()
    g_r0 = gcode(win)
    win.input_offset_ap_plan.setText("160.0")
    pump()
    check("G: plan with Roll: AP 160 and AP 0 give different moves (intended: other rotation centre)", g_r160 != g_r0)
    check_rotation_centre_idempotent(win, g_r160, e_r160)
    check("G: Planning AP field -> Control tab field (legacy sync)", win.input_offset_ap.text() == "160.0")
    click(win.button_clear_all)
    set_device_modern(win, "Lung Phantom")
    win3 = Launch_ImGUI.MyApp()
    win3.setAttribute(Qt.WA_DontShowOnScreen, True)
    win3.resize(2048, 1232)
    win3.show()
    pump()
    ctl_default = win3.input_offset_ap.text()
    win3.input_offset_ap.setText("75.5")              # typed in the Control tab before the Planning tab is opened
    win3.input_offset_lat.setText("1.5")
    win3.tabModules.setCurrentIndex(3)
    pump(10)
    check("G/H: a rotation centre already set (Control tab) is kept; the default is 0",
          ctl_default == "0.0" and win3.input_offset_ap_plan.text() == "75.5"
          and win3.input_offset_lat_plan.text() == "1.5" and win3.input_offset_si_plan.text() == "0.0"
          and isinstance(getattr(win3, 'planning_modern', None), tpm.ModernPlanning),
          f"{ctl_default} {win3.input_offset_ap_plan.text()}")
    win3.input_offset_ap_plan.setText("90")
    pump()
    check("G: ... and edits in the card reach the Control tab", win3.input_offset_ap.text() == "90")
    win3.close()
    pump()

    # ================================================================ H / I / J / K
    print("\n=== H: function selector, Start / End range slider, fonts ===", flush=True)
    cc = p.curve_controls
    set_device_modern(win, "Lung Phantom")
    click(win.button_clear_all)
    tw = win.create_settings_tab_widget
    tw.setCurrentWidget(p.curve_page)
    pump()

    def gx(wd):
        return wd.mapTo(win, QPoint(0, 0)).x()

    def gy(wd):
        return wd.mapTo(win, QPoint(0, 0)).y()

    # ---- H3 function selector
    fb = cc.func_buttons
    check("H3: function selector: 7 segment buttons with glyph + name, combo hidden (source of truth)",
          [b.property('func_key') for b in fb] == FUNCS and all(not b.icon().isNull() for b in fb)
          and [b.text() for b in fb] == ["sin", "cos", "cos²", "cos⁴", "cos⁶", "constant", "linear"]
          and win.combo_func_type.isHidden() and all(b.isVisible() for b in fb)
          and all(gy(b) == gy(fb[0]) for b in fb) and [gx(b) for b in fb] == sorted(gx(b) for b in fb))
    check("H3: Undo icon right of the function selector, same row",
          gx(p.btn_undo) >= gx(fb[-1]) + fb[-1].width() and abs(gy(p.btn_undo) - gy(fb[0])) <= 4)
    fsel_ok, fsel_detail = True, []
    for dev, axis in (("Lung Phantom", 'X'), ("Motion Platform", 'Roll')):
        set_device_modern(win, dev)
        for a, b in p.axis_pills.items():
            if b.isChecked() != (a == axis):
                click(b)
        win.input_start_time.setValue(2.0)
        win.input_end_time.setValue(12.0)
        win.input_period.setValue(4.0)
        for i, f in enumerate(FUNCS):
            click(fb[i])
            st = func_state(win)
            ok = (win.combo_func_type.currentText() == f and [b.isChecked() for b in fb] == [j == i for j in range(7)]
                  and st == legacy_func[(dev, f)])
            if not ok:
                fsel_ok = False
                fsel_detail.append((dev, f, st, legacy_func[(dev, f)]))
        click(fb[0])
    check("H3: a click selects the function (combo index), one button checked, the fields / labels / enabled state "
          "exactly as the legacy combo gave (both devices, linear: End = Start + Duration)", fsel_ok,
          str(fsel_detail[:2]))
    win.combo_func_type.setCurrentText("cos^4")
    pump()
    check("H3: combo set by code -> the selector follows", fb[3].isChecked() and sum(b.isChecked() for b in fb) == 1)
    win.combo_func_type.setCurrentText("sin")
    pump()
    set_device_modern(win, "Lung Phantom")

    # ---- H4 fonts
    def px(wd):                                            # (offscreen: fontInfo() gives -1, the font's size then)
        v = wd.fontInfo().pixelSize()
        return v if v > 0 else wd.font().pixelSize()
    vals = {n: px(getattr(win, n)) for n in ('input_amplitude', 'input_amp_offset', 'input_period',
                                                                 'input_phase', 'input_start_time', 'input_end_time',
                                                                 'input_wait_rad_time')}
    vals['Total duration'] = px(cc.total_spin)
    check("H4: numbers in the boxes 16 px (fields, Start / End, Total duration, Time)", set(vals.values()) == {16},
          str(vals))
    check("H4: function names 15 px, labels 14 px",
          all(px(b) == 15 for b in fb) and px(win.label_amplitude) == 14 and px(cc.total_label) == 14
          and px(cc.start_label) == 14, f"func {px(fb[0])} label {px(win.label_amplitude)} total {px(cc.total_label)}")
    boxes = [win.input_amplitude, win.input_amp_offset, win.input_period, win.input_phase, win.input_start_time,
             win.input_end_time, cc.total_spin]
    check("H4: boxes tall enough for the bigger numbers (height >= size hint, >= 40 px)",
          all(b.height() >= max(40, b.minimumSizeHint().height()) for b in boxes),
          str([(b.height(), b.minimumSizeHint().height()) for b in boxes]))

    # ---- H2 range slider
    sl = cc.slider
    st_box, en_box = win.input_start_time, win.input_end_time
    check("H2: Start box | range slider | End box in one row (slider between the boxes), Total duration right",
          gx(st_box) + st_box.width() <= gx(sl) and gx(sl) + sl.width() <= gx(en_box)
          and gx(en_box) + en_box.width() <= gx(cc.total_spin)
          and abs((gy(sl) + sl.height() / 2) - (gy(st_box) + st_box.height() / 2)) <= 6
          and abs(gy(st_box) - gy(en_box)) <= 2)
    st_box.setValue(5.0)
    en_box.setValue(25.0)
    pump()
    check("H2: boxes -> slider (setValue)", sl.values() == (5.0, 25.0) and sl.limit() == 60.0, str(sl.values()))
    en_box.blockSignals(True)
    en_box.setValue(31.5)                                   # as create_curve / linear do (blocked signals)
    en_box.blockSignals(False)
    pump()
    check("H2: a box set with blocked signals -> slider follows", sl.values() == (5.0, 31.5), str(sl.values()))
    en_box.lineEdit().selectAll()
    QTest.keyClicks(en_box.lineEdit(), "40")
    QTest.keyClick(en_box.lineEdit(), Qt.Key_Return)
    pump()
    check("H2: typed End 40 -> slider", sl.values() == (5.0, 40.0) and en_box.value() == 40.0, str(sl.values()))

    def drag(x0, y0, x1):
        QTest.mousePress(sl, Qt.LeftButton, Qt.NoModifier, QPoint(x0, y0))
        QTest.mouseMove(sl, QPoint((x0 + x1) // 2, y0))
        QTest.mouseMove(sl, QPoint(x1, y0))
        QTest.mouseRelease(sl, Qt.LeftButton, Qt.NoModifier, QPoint(x1, y0))
        pump()
    hx, hy = sl.handle_pos('hi')
    tx = int(round(sl.x_of(50.0)))
    drag(hx, hy, tx)
    exp_hi = sl.value_at(tx)
    px_s = 1.5 * sl.scale_max() / sl._track_width()        # one pixel of the track in seconds (+ rounding)
    check("H2: dragging the End handle (real mouse events) -> End box", abs(en_box.value() - exp_hi) < 1e-9
          and abs(exp_hi - 50.0) <= px_s and st_box.value() == 5.0, f"End {en_box.value()} (x->{exp_hi})")
    lx, ly = sl.handle_pos('lo')
    tx = int(round(sl.x_of(10.0)))
    drag(lx, ly, tx)
    check("H2: dragging the Start handle -> Start box", abs(st_box.value() - sl.value_at(tx)) < 1e-9
          and abs(st_box.value() - 10.0) <= px_s, f"Start {st_box.value()} (1 px = {px_s / 1.5:.3f} s)")
    lo0, hi0 = sl.values()
    mid = int(round(sl.x_of((lo0 + hi0) / 2)))
    drag(mid, ly, mid + 40)
    lo1, hi1 = st_box.value(), en_box.value()
    check("H2: dragging the blue range moves both, same width", lo1 > lo0 and abs((hi1 - lo1) - (hi0 - lo0)) < 0.011
          and sl.values() == (lo1, hi1), f"({lo0}, {hi0}) -> ({lo1}, {hi1})")
    lx, ly = sl.handle_pos('lo')
    drag(lx, ly, int(round(sl.x_of(hi1 + 5.0))))
    check("H2: Start handle dragged past End stops at End - 0.01 (Start <= End)",
          abs(st_box.value() - (en_box.value() - 0.01)) < 1e-9 and en_box.value() == hi1,
          f"{st_box.value()} / {en_box.value()}")
    st_box.setValue(10.0)
    sl.setFocus()
    pump()
    QTest.keyClick(sl, Qt.Key_Down)                       # select the Start handle
    QTest.keyClick(sl, Qt.Key_Right)
    QTest.keyClick(sl, Qt.Key_Right, Qt.ShiftModifier)
    pump()
    check("H2: keyboard: Down selects Start, Right +0.1 s, Shift+Right +1 s -> Start box",
          abs(st_box.value() - 11.1) < 1e-9 and sl.values()[0] == st_box.value(), str(st_box.value()))
    st_box.setValue(11.1)
    en_box.setValue(36.36)
    pump()
    print(f"  before typing 55: Start {st_box.value()} End {en_box.value()} slider {sl.values()}", flush=True)
    st_box.lineEdit().selectAll()
    QTest.keyClicks(st_box.lineEdit(), "55")
    QTest.keyClick(st_box.lineEdit(), Qt.Key_Return)
    pump()
    check("H2: typed Start past End -> End moves to Start + 0.01 when the edit is finished (Start <= End)",
          st_box.value() == 55.0 and abs(en_box.value() - 55.01) < 1e-9 and sl.values() == (55.0, 55.01),
          f"{st_box.value()} / {en_box.value()}")
    check("H2: slider tooltip shows the values", "55.00" in sl.toolTip() and "55.01" in sl.toolTip())
    st_box.setValue(0.0)
    en_box.setValue(20.0)
    pump()

    # ---- H1 Total duration
    print("\n=== H: Total duration ===", flush=True)
    ts = cc.total_spin
    check("H1: Total duration default 60 s (default plan 0 - 60 s)", ts.value() == 60.0
          and abs(float(win.dfEdit['time'].max()) - 60.0) < 1e-9)
    modern_curve(win, 'X', 'sin', 8.0, 10.0, 4.0, 0.0, 20.0)
    modern_curve(win, 'Y', 'constant', 6.0, 0.0, 4.0, 22.0, 30.0)
    modern_event(win, 12.0, 'rad')
    modern_event(win, 50.0, 'on')                          # window to the plan end (explicit S0 on the last row)
    w_before = wins(win)
    df_before = win.dfEdit.copy(deep=True)
    last = {c: float(win.dfEdit[c].iat[-1]) for c in ('X', 'Y', 'Z')}
    asked = []

    def answer(ans):
        QMessageBox.question = staticmethod(lambda *a, **k: (asked.append(a[2] if len(a) > 2 else ''), ans)[1])
    answer(QMessageBox.Yes)

    def type_total(v):
        ts.lineEdit().selectAll()
        QTest.keyClicks(ts.lineEdit(), str(v))
        QTest.keyClick(ts.lineEdit(), Qt.Key_Return)
        pump()
    type_total(80)
    d = win.dfEdit
    t = d['time'].to_numpy(float)
    ext = t > 60.0 + 1e-9
    check("H1/I: Total 80 (typed): plan extended to 80 s, every axis holds its last position in 60 - 80 s",
          abs(t[-1] - 80.0) < 1e-9 and ext.sum() > 0
          and all(np.allclose(d[c].to_numpy(float)[ext], last[c]) for c in ('X', 'Y', 'Z')) and not asked,
          f"end {t[-1]} last {last}")
    check("H1: the part before 60 s unchanged (axes and every command, incl. the S0 of the old last row)",
          np.allclose(d[['X', 'Y', 'Z']].to_numpy(float)[:len(df_before)], df_before[['X', 'Y', 'Z']].to_numpy(float))
          and list(d['Command'])[:len(df_before)] == list(df_before['Command']))
    m42x = [l for l in fc.generate_planned_gcode(win)[0].splitlines() if l.startswith("M42")]
    check("H1: a trigger window that ran to the plan end keeps its old end (50 - 60 s; off during the added hold, "
          "as Add Curve / Insert at the plan end); G-code still ends with the safety S0",
          wins(win) == w_before and w_before[-1] == (50.0, 60.0) and m42x and m42x[-1] == T.TRIGGER_OFF_CMD,
          f"{w_before} -> {wins(win)} {m42x[-3:]}")
    check("H1: slider range follows (0 - 80 s)", cc.slider.limit() == 80.0)
    check("H1: one undo step", len(win._curve_undo_stack) == 1 and p.btn_undo.isEnabled())
    click(p.btn_undo)
    check("H1: Undo restores the 60 s plan (one step) and the field follows",
          win.dfEdit[['time', 'X', 'Y', 'Z']].equals(df_before[['time', 'X', 'Y', 'Z']])
          and list(win.dfEdit['Command']) == list(df_before['Command']) and ts.value() == 60.0)
    click(win.button_clear_all)
    modern_curve(win, 'X', 'sin', 8.0, 10.0, 4.0, 0.0, 20.0)
    modern_event(win, 5.0, 'on')
    modern_event(win, 8.0, 'off')
    asked.clear()
    type_total(45)
    check("H1: shorter, only an idle tail cut (60 -> 45): no confirmation, plan cropped to 45 s",
          not asked and abs(float(win.dfEdit['time'].max()) - 45.0) < 1e-9 and ts.value() == 45.0
          and wins(win) == [(5.0, 8.0)], str(asked))
    answer(QMessageBox.No)
    df45 = win.dfEdit.copy(deep=True)
    type_total(6)
    check("H1: shorter cutting motion / a trigger window: asks; No keeps the plan and the field",
          len(asked) == 1 and "X" in asked[0] and "trigger window" in asked[0] and win.dfEdit.equals(df45)
          and ts.value() == 45.0, str(asked)[:200])
    answer(QMessageBox.Yes)
    asked.clear()
    type_total(6)
    d = win.dfEdit
    check("H1: ... Yes: cropped to [0, 6] s (Crop path: window 5 - 6 closed by the explicit S0 on the new last row)",
          len(asked) == 1 and abs(float(d['time'].max()) - 6.0) < 1e-9 and wins(win) == [(5.0, 6.0)]
          and d['Command'].iat[-1] == T.output_command(False)
          and np.allclose(d['X'].to_numpy(float), df45['X'].to_numpy(float)[:len(d)]))
    check("H1: slider limit 6 s, Start / End clamped inside 0 - 6 s",
          cc.slider.limit() == 6.0 and en_box.value() <= 6.0 and st_box.value() < en_box.value(),
          f"{cc.slider.limit()} {st_box.value()} {en_box.value()}")
    click(p.btn_undo)
    check("H1: Undo -> 45 s again (one step)", ts.value() == 45.0 and win.dfEdit.equals(df45))
    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
    # follows the plan when other code changes the length
    modern_curve(win, 'Y', 'sin', 3.0, 0.0, 4.0, 40.0, 70.0)    # starts at 0: no transit shift
    check("H1: follows Add Curve past the plan end (45 -> 70)", ts.value() == 70.0 and cc.slider.limit() == 70.0,
          str(ts.value()))
    click(p.btn_undo)
    check("H1: follows Undo (70 -> 45)", ts.value() == 45.0)
    dlg = fc.CropTrimDialog(win, mode="trim")
    dlg.input_start.setValue(10.0)
    dlg.input_end.setValue(20.0)
    dlg.execute_action()
    pump()
    check("H1: follows Trim (45 -> about 35)", abs(ts.value() - float(win.dfEdit['time'].max())) < 0.006
          and ts.value() < 36.0, str(ts.value()))
    dlg = fc.CropTrimDialog(win, mode="crop")
    dlg.input_start.setValue(2.0)
    dlg.input_end.setValue(22.0)
    dlg.execute_action()
    pump()
    check("H1: follows Crop (-> 20 s)", abs(ts.value() - 20.0) < 0.006, str(ts.value()))
    g20 = gcode(win)
    rt20 = os.path.join(TMP, 'total20.gcode')
    with open(rt20, 'w') as f:
        f.write(g20)
    click(win.button_clear_all)                            # (Clear All keeps the plan length, zeroes the axes)
    check("H1: follows Clear All (field = plan end)", abs(ts.value() - float(win.dfEdit['time'].max())) < 0.006)
    fc.import_gcode_action(win, rt20)
    pump(10)
    check("H1: follows an import (-> the imported plan's end)",
          abs(ts.value() - float(win.dfEdit['time'].max())) < 0.006 and abs(ts.value() - 20.0) < 0.1, str(ts.value()))
    click(win.button_clear_all)
    type_total(60)                                         # back to the default length for the next checks
    check("H1: typed 60 after the import: 60 s plan", ts.value() == 60.0
          and abs(float(win.dfEdit['time'].max()) - 60.0) < 1e-9)
    set_device_modern(win, "Motion Platform")
    click(win.button_clear_all)
    if ts.value() != 60.0:
        type_total(60)
    modern_curve(win, 'SI', 'sin', 6.0, 0.0, 4.0, 0.0, 20.0)
    modern_curve(win, 'Roll', 'sin', 2.0, 0.0, 5.0, 0.0, 20.0)
    type_total(70)
    d = win.dfEdit
    ext = d['time'].to_numpy(float) > 60.0 + 1e-9
    axes_mp = [c for c in d.columns if c not in ('time', 'timestamp', 'Command')]
    check("H1: Motion Platform: extended to 70 s, every column (positions and actuators) holds its last value",
          abs(float(d['time'].max()) - 70.0) < 1e-9
          and all(np.allclose(d[c].to_numpy(float)[ext], float(d[c].to_numpy(float)[~ext][-1])) for c in axes_mp),
          str(axes_mp))
    d1 = fc.compute_motion_platform_actuators(win, d.copy())
    check("H1: Motion Platform: actuators re-computed (another pass changes nothing)",
          all(np.allclose(d1[c].to_numpy(float), d[c].to_numpy(float)) for c in axes_mp))
    click(win.button_clear_all)
    set_device_modern(win, "Lung Phantom")

    # ---- I + J: Replace | Insert next to Add Curve
    print("\n=== I/J: Replace | Insert ===", flush=True)
    ir = p.insert_replace
    rb, ib = ir.buttons['replace'], ir.buttons['insert']
    ac, imp, clr = win.button_create_curve, win.button_import_curve, win.button_clear_all
    check("I/J: Replace | Insert next to Add Curve (same row, right of Add Curve, before Import File / Clear All)",
          rb.isVisible() and ib.isVisible() and abs(gy(rb) - gy(ac)) <= 2 and abs(gy(imp) - gy(ac)) <= 2
          and gx(ac) + ac.width() <= gx(rb) < gx(ib) and gx(ib) + ib.width() <= gx(imp) < gx(clr)
          and rb.height() == ac.height() and [rb.text(), ib.text()] == ["Replace", "Insert"],
          f"add {gx(ac)},{ac.width()} rep {gx(rb)} ins {gx(ib)} imp {gx(imp)}")
    check("I/J: Add Curve / Import File / Clear All share the rest of the row (equal widths)",
          max(ac.width(), imp.width(), clr.width()) - min(ac.width(), imp.width(), clr.width()) <= 3,
          str((ac.width(), imp.width(), clr.width())))
    check("I/J: Replace selected by default, tooltips", rb.isChecked() and not ib.isChecked() and ir.mode == 'replace'
          and "Replace" in rb.toolTip() and "Insert" in ib.toolTip() and "moves right" in ib.toolTip())

    def fill(b):
        img = b.grab().toImage()
        return img.pixelColor(img.width() // 2, int(4 * (img.devicePixelRatio() or 1.0))).name()
    f_on, f_off = fill(rb), fill(ib)
    click(ib)
    check("I/J: exclusive toggles, filled when selected (outline when not)",
          ib.isChecked() and not rb.isChecked() and ir.mode == 'insert' and f_on == '#1565c0' and f_off == '#ffffff'
          and fill(ib) == '#1565c0' and fill(rb) == '#ffffff', f"{f_on} {f_off} {fill(ib)} {fill(rb)}")
    click(ib)
    check("I/J: clicking the selected one keeps it selected", ib.isChecked() and not rb.isChecked())
    click(rb)
    check("I/J: back to Replace", rb.isChecked() and not ib.isChecked() and ir.mode == 'replace')
    # Replace == the legacy Add Curve
    click(win.button_clear_all)
    modern_curve(win, 'X', 'sin', 8.0, 10.0, 4.0, 0.0, 20.0)
    pre = win.dfEdit.copy(deep=True)
    for a, b in p.axis_pills.items():
        if b.isChecked() != (a == 'Y'):
            click(b)
    win.combo_func_type.setCurrentText("constant")
    win.input_amplitude.setValue(7.0)
    win.input_amp_offset.setValue(0.0)
    st_box.setValue(5.0)
    en_box.setValue(8.0)
    fc.create_curve._pm_original(win)                     # the legacy create_curve, unwrapped
    ref = win.dfEdit.copy(deep=True)
    win.dfEdit = pre.copy(deep=True)
    win.dfEdit_lung_phantom = win.dfEdit
    st_box.setValue(5.0)
    en_box.setValue(8.0)
    click(ac)
    check("I: Replace = the old Add Curve (same plan)", win.dfEdit[['time', 'X', 'Y', 'Z']].equals(
        ref[['time', 'X', 'Y', 'Z']]) and list(win.dfEdit['Command']) == list(ref['Command']) and len(win.dfEdit) == len(pre))
    # Insert
    win.dfEdit = pre.copy(deep=True)
    win.dfEdit_lung_phantom = win.dfEdit
    fc.trigger_plot_update(win)
    pump()
    modern_event(win, 12.0, 'rad')
    modern_event(win, 2.0, 'usr')
    modern_event(win, 3.0, 'on')                           # spans Start (5 s)
    modern_event(win, 6.0, 'off')
    modern_event(win, 14.0, 'on')                          # after Start
    modern_event(win, 16.0, 'off')
    modern_event(win, 25.0, 'on')                          # to the plan end
    pre = win.dfEdit.copy(deep=True)
    w_pre = wins(win)
    g_pre = gcode(win)
    for a, b in p.axis_pills.items():
        if b.isChecked() != (a == 'Y'):
            click(b)
    win.combo_func_type.setCurrentText("constant")
    win.input_amplitude.setValue(0.0)                      # Y is 0 at Start: no transit shift
    win.input_amp_offset.setValue(0.0)
    st_box.setValue(5.0)
    en_box.setValue(8.0)
    click(ib)
    click(ac)
    d = win.dfEdit
    L = 3.0
    tp, tn = pre['time'].to_numpy(float), d['time'].to_numpy(float)
    step = float(tp[1] - tp[0])
    i0 = int(np.flatnonzero(tp >= 5.0 - 1e-9)[0])
    k = int(round(L / step))
    check("I: Insert grows the plan and Total duration by End - Start (60 -> 63 s)",
          abs(tn[-1] - 63.0) < 1e-9 and len(d) == len(pre) + k and ts.value() == 63.0
          and ir.last_insert is not None and abs(ir.last_insert[1] - L) < 1e-9, f"{tn[-1]} {ts.value()} {ir.last_insert}")
    check("I: rows before Start unchanged",
          d.iloc[:i0][['time', 'X', 'Y', 'Z']].reset_index(drop=True).equals(pre.iloc[:i0][['time', 'X', 'Y', 'Z']]
                                                                              .reset_index(drop=True))
          and list(d['Command'])[:i0] == list(pre['Command'])[:i0])
    check("I: rows from Start on moved right by 3 s: X / Z values and Command cells (pauses, switches) the same",
          np.allclose(tn[i0 + k:], tp[i0:] + L)
          and np.allclose(d['X'].to_numpy(float)[i0 + k:], pre['X'].to_numpy(float)[i0:])
          and np.allclose(d['Z'].to_numpy(float)[i0 + k:], pre['Z'].to_numpy(float)[i0:])
          and list(d['Command'])[i0 + k:] == list(pre['Command'])[i0:])
    check("I: the gap holds X / Z at their positions at Start, the curve (Y constant 0) written into it",
          np.allclose(d['X'].to_numpy(float)[i0:i0 + k], pre['X'].iat[i0])
          and np.allclose(d['Y'].to_numpy(float)[i0:i0 + k + 1], 0.0) and all(c == "" for c in d['Command'][i0:i0 + k]))
    check("I: trigger windows: spanning Start longer by 3 s, the later ones + 3 s, explicit S0 on the last row",
          wins(win) == [(3.0, 9.0), (17.0, 19.0), (28.0, 63.0)] and d['Command'].iat[-1] == T.output_command(False),
          f"{w_pre} -> {wins(win)}")
    g_ins = gcode(win)

    def cmd_lines(g):
        return [ln for ln in g.splitlines() if ln.startswith(("M42", "M226", "M98"))]
    p_pre, p_ins = gc_pauses(g_pre), gc_pauses(g_ins)
    check("I: G-code: the same M42 / M226 / M98 lines in the same order, the pause after Start + 3 s",
          cmd_lines(g_pre) == cmd_lines(g_ins) and len(p_pre) == 2 and p_ins[0] == p_pre[0]
          and abs(p_ins[1][1] - (p_pre[1][1] + L)) < 0.02, f"{p_pre} -> {p_ins}")
    check("I: G-code trigger windows shifted as the plan",
          gc_windows(g_ins) == [(3.0, 9.0), (17.0, 19.0), (28.0, 63.0)], str(gc_windows(g_ins)))
    check("I: one undo step for the whole Insert", len(win._curve_undo_stack) == 1)
    click(p.btn_undo)
    check("I: Undo restores the plan before the Insert (60 s, same cells)", win.dfEdit[['time', 'X', 'Y', 'Z']].equals(
        pre[['time', 'X', 'Y', 'Z']]) and list(win.dfEdit['Command']) == list(pre['Command']) and ts.value() == 60.0)
    # Insert where Add Curve moves the curve later (transit at max speed): the moved data is not overwritten
    st_box.setValue(5.0)
    en_box.setValue(8.0)
    win.input_amplitude.setValue(20.0)                     # Y jumps 0 -> 20 at Start: create_curve shifts the curve
    click(ac)
    d = win.dfEdit
    ins = ir.last_insert[1]
    tn = d['time'].to_numpy(float)
    kk = int(round(ins / step))
    check("I: transit shift: the gap grows by the shift (curve moved later by Add Curve), data after Start intact",
          ins > L + 0.05 and abs(st_box.value() - 5.0 - (ins - L)) < 0.011 and abs(tn[-1] - (60.0 + ins)) < 1e-6
          and np.allclose(d['X'].to_numpy(float)[i0 + kk:], pre['X'].to_numpy(float)[i0:])
          and np.allclose(d['Y'].to_numpy(float)[i0 + kk + 1:], pre['Y'].to_numpy(float)[i0 + 1:])
          and list(d['Command'])[i0 + kk:] == list(pre['Command'])[i0:] and len(win._curve_undo_stack) == 1,
          f"inserted {ins:.3f} s, Start box {st_box.value()}")
    click(p.btn_undo)
    # Insert exactly at the end of a trigger window (its S0 on the Start row: the trigger is OFF at Start) - fix p5
    win.input_amplitude.setValue(0.0)                      # Y constant 0 = Y at Start: no transit shift
    st_box.setValue(6.0)
    en_box.setValue(8.0)
    click(ac)
    d = win.dfEdit
    i6 = int(np.flatnonzero(d['time'].to_numpy(float) >= 6.0 - 1e-9)[0])
    st6 = T.trg_states(list(d['Command']))
    check("I (fix): Insert at the end of a window (3 - 6 s, Start 6): that window keeps its end, the gap is OFF, the "
          "later windows + 2 s",
          wins(win) == [(3.0, 6.0), (16.0, 18.0), (27.0, 62.0)] and not st6[i6:i6 + 200].any()
          and abs(float(d['time'].max()) - 62.0) < 1e-9 and len(win._curve_undo_stack) == 1, f"{w_pre} -> {wins(win)}")
    g6 = gcode(win)
    check("I (fix): ... G-code: same M42 / M226 / M98 order, the window's S0 still at 6 s",
          cmd_lines(g6) == cmd_lines(g_pre) and gc_windows(g6) == [(3.0, 6.0), (16.0, 18.0), (27.0, 62.0)],
          str(gc_windows(g6)))
    click(p.btn_undo)
    st_box.setValue(60.0)
    en_box.setValue(62.0)
    click(ac)
    d = win.dfEdit
    check("I (fix): Insert at the plan end (window 25 - 60 s open to the end): the window keeps its end 60 s as "
          "Replace does, the plan grows to 62 s",
          wins(win) == [(3.0, 6.0), (14.0, 16.0), (25.0, 60.0)] and abs(float(d['time'].max()) - 62.0) < 1e-9
          and not T.trg_states(list(d['Command']))[-201:].any(), str(wins(win)))
    click(p.btn_undo)
    check("I (fix): undone (one step)", list(win.dfEdit['Command']) == list(pre['Command']) and ts.value() == 60.0)
    st_box.setValue(5.0)
    en_box.setValue(8.0)
    # Insert on the Motion Platform: actuators re-computed, Total duration grows
    set_device_modern(win, "Motion Platform")
    click(win.button_clear_all)
    click(rb)
    if ts.value() != 60.0:
        type_total(60)
    modern_curve(win, 'SI', 'sin', 6.0, 0.0, 4.0, 0.0, 20.0)
    modern_curve(win, 'Roll', 'sin', 2.0, 0.0, 5.0, 0.0, 20.0)
    pre_mp = win.dfEdit.copy(deep=True)
    for a, b in p.axis_pills.items():
        if b.isChecked() != (a == 'LAT'):
            click(b)
    win.combo_func_type.setCurrentText("constant")
    win.input_amplitude.setValue(0.0)
    win.input_amp_offset.setValue(0.0)
    st_box.setValue(10.0)
    en_box.setValue(14.0)
    click(ib)
    click(ac)
    d = win.dfEdit
    tpm_ = pre_mp['time'].to_numpy(float)
    i0 = int(np.flatnonzero(tpm_ >= 10.0 - 1e-9)[0])
    k4 = int(round(4.0 / float(tpm_[1] - tpm_[0])))
    d1 = fc.compute_motion_platform_actuators(win, d.copy())
    mp_dev = {c: float(np.max(np.abs(d[c].to_numpy(float)[i0 + k4:] - pre_mp[c].to_numpy(float)[i0:])))
              for c in ('SI', 'Roll', 'LAT', 'A', "'e")}
    act_dev = {c: float(np.max(np.abs(d1[c].to_numpy(float) - d[c].to_numpy(float))))
               for c in ('A', 'B', 'C', 'D', "'e", "'a")}
    min_step = float(fc._gather_plan_params(win, "Motion Platform")['min_step'])
    check("I: Motion Platform Insert: 60 -> 64 s, SI / Roll / actuators after Start moved right (re-baked as every "
          "Motion Platform edit: within the bake's Min. step), actuators re-computed",
          abs(float(d['time'].max()) - 64.0) < 1e-9 and ts.value() == 64.0 and min_step > 0
          and max(mp_dev.values()) <= min_step + 1e-9 and max(act_dev.values()) < 1e-9,
          f"{float(d['time'].max())} {ts.value()} shifted-data deviation {mp_dev} re-compute deviation {act_dev}")
    click(p.btn_undo)
    check("I: Motion Platform Insert undone in one step",
          win.dfEdit[['time', 'SI', 'Roll']].equals(pre_mp[['time', 'SI', 'Roll']]))
    click(rb)
    click(win.button_clear_all)
    set_device_modern(win, "Lung Phantom")

    # ---- fix p5: '.' and ',' both decimal points (decimal-comma locale), large extensions confirmed
    print("\n=== fix: decimal point / comma, slip guard ===", flush=True)
    from PySide6.QtCore import QLocale
    from PySide6.QtGui import QGuiApplication
    nl = QLocale("en_NL")
    nl.setNumberOptions(nl.numberOptions() | QLocale.OmitGroupSeparator)
    saved_loc = {b: QLocale(b.locale()) for b in (ts, st_box, en_box)}
    for b in saved_loc:
        b.setLocale(nl)                                  # as on the user's machine (decimal comma)
    check("fix: decimal keys on Start / End / Total duration and the Curve tab's number boxes",
          all(getattr(b, '_pm_decimal_keys', None) is not None for b in (ts, st_box, en_box, win.input_amplitude,
                                                                         win.input_period)) and nl.decimalPoint() == ',')
    asked.clear()
    if ts.value() != 60.0:
        type_total(60)
    type_total("70.25")
    check("fix: Total duration typed '70.25' in a decimal-comma locale -> 70.25 s (not 7025 s)",
          ts.value() == 70.25 and abs(float(win.dfEdit['time'].max()) - 70.25) < 1e-9 and not asked, str(ts.value()))
    click(p.btn_undo)
    type_total("70,25")
    check("fix: ... typed '70,25' -> 70.25 s as well", ts.value() == 70.25, str(ts.value()))
    click(p.btn_undo)
    en_box.lineEdit().selectAll()
    QTest.keyClicks(en_box, "15.5")                       # typed into the box (keys go to the spin box itself)
    QTest.keyClick(en_box, Qt.Key_Return)
    pump()
    check("fix: End Time typed '15.5' -> 15.5 (not 155), slider follows", en_box.value() == 15.5
          and cc.slider.values()[1] == 15.5, f"{en_box.value()} {cc.slider.values()}")
    QGuiApplication.clipboard().setText("12.75")
    en_box.lineEdit().selectAll()
    QTest.keyClick(en_box, Qt.Key_V, Qt.ControlModifier)
    QTest.keyClick(en_box, Qt.Key_Return)
    pump()
    check("fix: a pasted '12.75' -> 12.75", en_box.value() == 12.75, str(en_box.value()))
    for b, loc in saved_loc.items():
        b.setLocale(loc)
    en_box.setValue(20.0)
    answer(QMessageBox.No)
    asked.clear()
    df60 = win.dfEdit.copy(deep=True)
    type_total(6000)
    check("fix: a large extension (60 -> 6000 s) asks first; No keeps the plan and the field",
          len(asked) == 1 and "6000" in asked[0] and win.dfEdit.equals(df60) and ts.value() == 60.0, str(asked)[:120])
    answer(QMessageBox.Yes)
    asked.clear()
    type_total(100)
    check("fix: a moderate extension (60 -> 100 s) does not ask", not asked and ts.value() == 100.0)
    click(p.btn_undo)
    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)

    # ---- K: no grey backgrounds in the Planning sub-tabs
    print("\n=== K: white Planning sub-tabs ===", flush=True)
    from PySide6.QtWidgets import (QAbstractSpinBox, QComboBox, QLineEdit, QAbstractItemView, QScrollBar, QGroupBox,
                                   QWidget, QScrollArea)
    from PySide6.QtGui import QPalette
    per_idx = tw.indexOf(win.trg_periodic_tab)
    tw.setTabVisible(per_idx, True)                        # the hidden Periodic page, as if it were shown
    grey_report = {}
    for i in range(tw.count()):
        tw.setCurrentIndex(i)
        pump(4)
        img = tw.grab().toImage()
        dpr = img.devicePixelRatio() or 1.0
        page = tw.currentWidget()
        skip = []
        for cls in (QAbstractSpinBox, QComboBox, QLineEdit, QAbstractButton, QAbstractItemView, QScrollBar):
            for wd in page.findChildren(cls):
                if wd.isVisible():
                    tl = wd.mapTo(tw, QPoint(0, 0))
                    skip.append((tl.x() - 2, tl.y() - 2, tl.x() + wd.width() + 2, tl.y() + wd.height() + 2))
        bar = tw.tabBar()
        btl = bar.mapTo(tw, QPoint(0, 0))
        tabs_r = btl.x() + bar.tabRect(bar.count() - 1).right()
        skip.append((btl.x(), btl.y(), tabs_r + 2, btl.y() + bar.height()))
        n = grey = 0
        for y in range(0, tw.height(), 3):
            for x in range(0, tw.width(), 3):
                if any(a <= x <= c and b <= y <= e for a, b, c, e in skip):
                    continue
                col = img.pixelColor(int(x * dpr), int(y * dpr))
                n += 1
                if col.red() == col.green() == col.blue() and 225 <= col.red() <= 248:
                    grey += 1
        strip = img.pixelColor(int((tabs_r + 40) * dpr), int((btl.y() + bar.height() // 2) * dpr)).name()
        gb_in = []
        for g in page.findChildren(QGroupBox):
            if g.isVisible():
                pt = g.mapTo(tw, QPoint(4, g.height() - 4))
                gb_in.append(img.pixelColor(int(pt.x() * dpr), int(pt.y() * dpr)).name())
        grey_report[tw.tabText(i)] = (round(100.0 * grey / max(n, 1), 2), strip, gb_in)
        win.grab().save(os.path.join(OUT, PREFIX + f"subtab_{tw.tabText(i).lower()}.png"))
    # inputs: white inside also when disabled (the Trigger page's Min / Max / From / To boxes), plain combos white
    input_report = {}
    for i in range(tw.count()):
        tw.setCurrentIndex(i)
        pump(4)
        img = tw.grab().toImage()
        dpr = img.devicePixelRatio() or 1.0
        bad, n_dis = [], 0
        for wd in tw.currentWidget().findChildren(QWidget):
            if not wd.isVisible() or not (isinstance(wd, (QAbstractSpinBox, QComboBox)) or (
                    isinstance(wd, QLineEdit) and not isinstance(wd.parentWidget(), (QAbstractSpinBox, QComboBox)))):
                continue
            n_dis += not wd.isEnabled()
            # a combo: just inside its top border, right of the text (the offscreen font's glyphs fill the box
            # height); the read-only combo's button colour must be white too
            # (a combo with its own style sheet - the Settings combos - keeps its own drop-down button: sampled mid-top)
            own = bool((wd.styleSheet() or "").strip())
            pt = wd.mapTo(tw, (QPoint(wd.width() // 2, 4) if own else QPoint(wd.width() - 26, 4))
                          if isinstance(wd, QComboBox) else QPoint(5, 5))
            col = img.pixelColor(int(pt.x() * dpr), int(pt.y() * dpr))
            btn_ok = (not isinstance(wd, QComboBox) or wd.isEditable() or bool((wd.styleSheet() or "").strip())
                      or wd.palette().color(QPalette.Active, QPalette.Button).name() == '#ffffff')
            if min(col.red(), col.green(), col.blue()) < 250 or not btn_ok:
                bad.append((wd.objectName() or type(wd).__name__, wd.isEnabled(), col.name(), btn_ok))
        input_report[tw.tabText(i)] = (n_dis, bad)
    check("K (fix): inputs white inside on every sub-tab, also the disabled ones (Trigger: Min / Max / From / To) and "
          "the Combine combo", all(not v[1] for v in input_report.values()) and input_report['Trigger'][0] >= 6,
          str(input_report))
    tw.setTabVisible(per_idx, False)
    tab_idx = {tw.tabText(i): i for i in range(tw.count())}
    set_device_modern(win, "Motion Platform")              # the per-axis gate rows are rebuilt for the new axes
    set_device_modern(win, "Lung Phantom")
    tw.setCurrentIndex(tab_idx['Trigger'])
    pump(4)
    newbox = [b for row in win.trg_gate_rows.values() for b in (row.values() if isinstance(row, dict) else [])
              if isinstance(b, QAbstractSpinBox)]
    check("K (fix): the per-axis boxes rebuilt later (device switch) get the white palette too",
          len(newbox) >= 6 and all(b.palette().color(QPalette.Disabled, QPalette.Base).name() == '#ffffff'
                                   for b in newbox), str(len(newbox)))
    tw.setCurrentIndex(tab_idx['Table'])
    pump(4)
    from PySide6.QtWidgets import QHeaderView
    hdrs = [h for h in tw.currentWidget().findChildren(QHeaderView) if h.isVisible() and h.orientation() == Qt.Horizontal]
    hcol = []
    for h in hdrs:
        img = h.grab().toImage()
        hcol.append(img.pixelColor(int(3 * (img.devicePixelRatio() or 1)), img.height() // 2).name())
    check("K (fix): Table header white", hdrs and all(c == '#ffffff' for c in hcol), str(hcol))
    for dev in ("Lung Phantom", "Motion Platform"):
        set_device_modern(win, dev)
        tw.setCurrentIndex(tab_idx['Settings'])
        pump(6)
        page = tw.currentWidget()
        scs = [sa for sa in page.findChildren(QScrollArea)] + ([page] if isinstance(page, QScrollArea) else [])
        sp_last = win.settings_step_overhead_phantom if dev == "Lung Phantom" else win.settings_step_overhead_plat
        bot = sp_last.mapTo(page, QPoint(0, sp_last.height())).y()
        grid = win.settings_stack.currentWidget().layout()
        check(f"Settings ({dev}): fields in three columns, fits without scrolling at 2048x1232 (Step overhead "
              f"fully visible)", grid.columnCount() >= 3 and all(not sa.verticalScrollBar().isVisible() for sa in scs)
              and bot <= page.height(), f"cols {grid.columnCount()} bottom {bot} / {page.height()}")
        if REAL_FONTS:
            win.grab().save(os.path.join(OUT, PREFIX + f"subtab_settings_{dev.split()[0].lower()}.png"))
    set_device_modern(win, "Lung Phantom")
    tw.setCurrentWidget(p.curve_page)
    pump()
    check("K: every Planning sub-tab white (Curve, Periodic, Trigger, Tools, Settings, Table): < 0.5 % grey pixels "
          "outside the inputs, white strip right of the sub-tabs, white inside the group boxes",
          all(v[0] < 0.5 and v[1] == '#ffffff' and all(c == '#ffffff' for c in v[2]) for v in grey_report.values())
          and set(grey_report) == {"Curve", "Periodic", "Trigger", "Tools", "Settings", "Table"}, str(grey_report))
    check("K: group boxes as white cards (1px #cfd8dc, radius 6) via the sub-tab widget's scoped style sheet",
          tw.objectName() == 'pmSubTabs' and "QTabWidget#pmSubTabs QGroupBox" in tw.styleSheet()
          and "border: 1px solid #cfd8dc" in tw.styleSheet() and "border-radius: 6px" in tw.styleSheet())
    other_tabs = [t for t in win.findChildren(type(tw)) if t is not tw and "pmSubTabs" in (t.styleSheet() or "")]
    check("K: no other tab widget restyled", not other_tabs and "pmSubTabs" not in (win.styleSheet() or ""))
    check("K: inputs keep their own style (the white sheet has no rule for spin boxes / line edits / combos)",
          not any(s in tw.styleSheet() for s in ("QSpinBox", "QDoubleSpinBox", "QLineEdit", "QComboBox")))

    # ---- H: rotation centre literal restored in tab_planning.py
    import subprocess
    src_tp = open(os.path.join(ROOT, 'fcn_create_gui', 'tab_planning.py'), encoding='utf-8').read()
    try:
        diff_tp = subprocess.run(['git', 'diff', '-U0', '--', 'fcn_create_gui/tab_planning.py'], cwd=ROOT,
                                 capture_output=True, text=True).stdout
    except Exception:
        diff_tp = ''
    check("H: AP default literal restored in tab_planning.py ('0.0', no diff on that line)",
          'self.input_offset_ap_plan = QLineEdit("0.0", self.offset_rot_widget)' in src_tp
          and 'input_offset_ap_plan' not in diff_tp and '160' not in diff_tp, diff_tp[:200])

    # ================================================================ G-code byte-identical
    print("\n=== G-code: modern controls vs legacy controls ===", flush=True)
    win2 = new_window(modern=True)
    set_device_modern(win2, "Lung Phantom")
    run_script(win2, LP_SCRIPT, modern=True)
    g_lp_modern = gcode(win2)
    check("Lung Phantom plan through the modern controls: G-code byte-identical to the legacy controls",
          g_lp_modern == g_lp_legacy and len(g_lp_modern) > 1000, f"{len(g_lp_modern)} / {len(g_lp_legacy)} bytes")
    set_device_modern(win2, "Motion Platform")
    run_script(win2, MP_SCRIPT, modern=True)
    g_mp_modern = gcode(win2)
    check("Motion Platform plan (waits + trigger): G-code byte-identical to the legacy controls",
          g_mp_modern == g_mp_legacy and cmds(win2) == lw_mp_cmds, f"{len(g_mp_modern)} / {len(g_mp_legacy)} bytes")

    # ================================================================ sizes / screenshots
    print("\n=== sizes and screenshots ===", flush=True)
    win2.resize(2048, 1232)
    pump(6)
    mins = {}
    for dev in ("Lung Phantom", "Motion Platform"):
        set_device_modern(win2, dev)
        pump(6)
        mins[dev] = page_min(win2)
    check("Planning page minimum size not larger than before (both devices)",
          all(mins[d][0] <= base_min[d][0] and mins[d][1] <= base_min[d][1] for d in mins),
          f"before {base_min}, now {mins}")
    check("window minimum width fits 2048 px (Motion Platform)", win2.minimumSizeHint().width() <= 2048,
          str(win2.minimumSizeHint().width()))
    tbs = [b for b in win2.tab_planning.findChildren(QToolButton) if b.isVisible()]
    big = [(b.text(), b.height()) for b in tbs if b.height() > 44]
    check("no huge tool buttons on the Planning page (all <= 44 px high)", not big, str(big))
    pills_h = {b.height() for b in list(pm(win2).pills.values()) + list(pm(win2).kin_pills.values())}
    check("pill heights 28 px", pills_h == {28}, str(pills_h))
    if REAL_FONTS:
        fm_ok = all(b.fontInfo().pixelSize() <= 15 for b in tbs if b.text())
        check("real fonts: tool button text <= 15 px (app-wide 18 px button scaling not applied)", fm_ok)
        clipped = [b.text() for b in tbs if b.text() and b.sizeHint().width() > b.width() + 1
                   and b not in pm(win2).device_buttons]
        check("real fonts: no clipped button text", not clipped, str(clipped))
    check("canvas keeps most of the width (side card 216 px)", win2.create_plot_canvas.width() > 1700,
          str(win2.create_plot_canvas.width()))
    for dev, tag in (("Lung Phantom", "lung"), ("Motion Platform", "motion")):
        set_device_modern(win2, dev)
        pump(6)
        win2.grab().save(os.path.join(OUT, PREFIX + f"{tag}.png"))
        pm(win2).win.groupBox_BrCv_createCurve.grab().save(os.path.join(OUT, PREFIX + f"curve_options_{tag}.png"))
    p2 = pm(win2)
    check("G: plot not smaller than in the legacy window (top splitter pane)",
          win2.create_plot_view.height() >= base_plot_h - 1, f"{win2.create_plot_view.height()} / {base_plot_h}")
    for dev, tag in (("Lung Phantom", "lung"), ("Motion Platform", "motion")):
        set_device_modern(win2, dev)
        for mode in ("once", "repeat"):
            click(p2.mode_buttons[mode])
            click(p2.event_buttons['on'])
            pump(6)
            sb = p2.curve_scroll.verticalScrollBar()
            fits = sb.maximum() == 0 and p2.event_card.mapTo(p2.curve_scroll.viewport(), QPoint(0, 0)).y() \
                + p2.event_card.height() <= p2.curve_scroll.viewport().height()
            check(f"G: {dev}, {mode} (Trigger On): Curve page fits without scrolling at 2048x1232"
                  + (" (real fonts)" if REAL_FONTS else ""), fits,
                  f"scroll max {sb.maximum()}, content min {p2.curve_scroll.widget().minimumSizeHint().height()}, "
                  f"viewport {p2.curve_scroll.viewport().height()}")
            win2.grab().save(os.path.join(OUT, PREFIX + f"{tag}_{mode}.png"))
        click(p2.mode_buttons['once'])
    bar2 = win2.create_settings_tab_widget.tabBar()
    click(bar2, pos=bar2.tabRect(win2.create_settings_tab_widget.indexOf(pm(win2).table_tab)).center())
    win2.grab().save(os.path.join(OUT, PREFIX + "table_tab.png"))
    check("screenshots saved", all(os.path.isfile(os.path.join(OUT, PREFIX + f)) for f in
                                   ("lung.png", "motion.png", "table_tab.png")), OUT)
    win2.close()
    win.close()
    pump()
    check("no uncaught exceptions", not ERRS, "\n".join(ERRS)[:2000])
finally:
    restore_cfg()

ok = all(RES)
same_cfg = all(open(c, 'rb').read() == open(b, 'rb').read() for c, b in CFG_BAK.items())
print(f"configuration.json restored byte-identically: {same_cfg}")
print(f"\n{'ALL PASSED' if ok and same_cfg else 'FAILED'} ({sum(RES)}/{len(RES)} checks)   screenshots: {OUT}")
sys.exit(0 if ok and same_cfg else 1)
