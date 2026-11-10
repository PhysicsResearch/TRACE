"""
Offscreen test of the "Log files" tab (fcn_create_gui/tab_logs.py).

Builds the tab into a minimal QWidget window (self.tab_logs = QWidget(), as the integrator does),
then drives the public logs_* functions with the real sample files: case_02 log, two 5 Nov
Check_log logs, one 3 Nov log and curve2.gcode as reference.  Covers loading, axes, ROI (also by
dragging on the plot), the logged sensor waits (the dummy v2 copy of case_02 and synthetic v2 logs
written by scratch/test_log_analysis.write_wait_log: Show / Remove modes, the pause period, the
colour key, overlays across mode switches, analyses on the cut curves, the 'Waits' view; no pause
estimation any more), auto-alignment, compare + difference plot, ensemble band, peaks, movements,
reference points (also by clicking on the plot), table widgets, the Duet reference download
(patched), exports (v2 style: ';' columns, decimal comma), removal and the warnings shown instead
of exceptions.

Prints PASS / FAIL lines and ends with "ALL PASSED" or "<n> FAILED" (exit code 1 on failure).
Run:  set QT_QPA_PLATFORM=offscreen  &  C:\\Users\\gabri\\anaconda3\\envs\\TRACE\\python.exe scratch\\test_logs_tab_ui.py
"""
import csv
import glob
import math
import os
import shutil
import sys
import tempfile
import time
import traceback

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)

import numpy as np
import pandas as pd
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton

APP = QApplication.instance() or QApplication([])

import fcn_create_gui.tab_logs as tl          # noqa: E402
from fcn_logs import log_analysis as la       # noqa: E402

HOME = os.path.expanduser("~")
CASE02 = os.path.join(ROOT, "log_06112026_12_34_12_case_02.csv")
DUMMY = os.path.join(ROOT, "log_06112026_12_34_12_case_02_DUMMY_wait.csv")     # v2, one logged wait
CURVE2 = os.path.join(ROOT, "curve2.gcode")
CHECK_LOGS = [os.path.join(HOME, "Desktop", "Check_log", n) for n in ("log_14_05_39_.csv", "log_14_17_58_.csv")]
NOV3_LOG = os.path.join(HOME, "Documents", "TriggeredImaging0311", "log_15_03_42_.csv")

RESULTS = []
TMP = tempfile.mkdtemp(prefix="trace_logs_tab_")


def check(name, cond, detail=""):
    ok = bool(cond)
    RESULTS.append(ok)
    print(f"{'PASS' if ok else 'FAIL'}: {name}" + (f"  [{detail}]" if detail else ""))
    return ok


class FakeBox:
    """Records QMessageBox calls instead of opening modal dialogs (and the override cursor shown
    while each warning opens)."""
    calls = []
    cursors = []

    @staticmethod
    def warning(parent, title, text, *a, **k):
        FakeBox.calls.append(('warning', title, str(text)))
        cur = QApplication.overrideCursor()
        FakeBox.cursors.append(None if cur is None else cur.shape())
        return 0

    @staticmethod
    def information(parent, title, text, *a, **k):
        FakeBox.calls.append(('information', title, str(text)))
        return 0

    critical = warning
    question = information


tl.QMessageBox = FakeBox


def warnings_since(n):
    return [c for c in FakeBox.calls[n:] if c[0] == 'warning']


class Window(QWidget):
    pass


def make_window():
    w = Window()
    w.resize(1600, 1000)
    lay = QVBoxLayout(w)
    w.tab_logs = QWidget(w)
    lay.addWidget(w.tab_logs)
    return w


def idx_of(w, name_part):
    for i, e in enumerate(w.logs_state.entries):
        if name_part in e.curve.name:
            return i
    raise KeyError(name_part)


def lines_labels(w):
    return [ln.get_label() for ln in w.logs_ax.get_lines() if not ln.get_label().startswith('_')]


def finite(*xs):
    return all(x is not None and isinstance(x, (int, float, np.floating)) and math.isfinite(float(x)) for x in xs)


def mouse(w, kind, x_px, y_px, button=1):
    from matplotlib.backend_bases import MouseEvent
    ev = MouseEvent(kind, w.logs_canvas, x_px, y_px, button=button)
    w.logs_canvas.callbacks.process(kind, ev)


def main():
    for p in [CASE02, CURVE2, DUMMY] + CHECK_LOGS + [NOV3_LOG]:
        if not os.path.isfile(p):
            print(f"SKIP: sample file missing: {p}")
            return

    w = make_window()
    before = set(vars(w))
    t0 = time.perf_counter()
    tl.build_logs_tab(w)
    check("build_logs_tab builds the tab", getattr(w, 'logs_built', False) and isinstance(w.logs_state, tl.LogsState),
          f"{time.perf_counter() - t0:.2f} s")
    tl.build_logs_tab(w)          # second call is a no-op
    from PySide6.QtCore import SignalInstance
    new = [k for k in set(vars(w)) - before if not isinstance(getattr(w, k, None), SignalInstance)]
    check("every new attribute of the window uses the logs_ prefix", new and all(k.startswith('logs_') for k in new),
          str(sorted(k for k in new if not k.startswith('logs_'))))
    w.show()
    APP.processEvents()
    st = w.logs_state

    # ------------------------------------------------------------------ files
    n0 = len(FakeBox.calls)
    t0 = time.perf_counter()
    added = tl.logs_add_files(w, [CASE02] + CHECK_LOGS + [NOV3_LOG])
    t_add = time.perf_counter() - t0
    check("4 logs loaded", added is not None and len(added) == 4 and len(st.entries) == 4, f"{t_add:.2f} s")
    ref = tl.logs_add_reference(w, CURVE2)
    check("curve2.gcode loaded as reference", ref is not None and ref.kind == 'reference'
          and st.ref_uid == st.entries[-1].uid and len(st.entries) == 5)
    check("no warning during loading", not warnings_since(n0), str(warnings_since(n0)))
    check("curves table: one row per curve", w.logs_curves_table.rowCount() == 5)
    check("default analysis axis is SI (largest range of case_02)", st.analysis_axis == 'SI', st.analysis_axis)
    check("reference combo defaults to the G-code", w.logs_ref_combo.currentText().startswith('curve2'),
          w.logs_ref_combo.currentText())
    colors = [e.color for e in st.entries]
    check("distinct tab10 colours", len(set(colors)) == 5 and all(c in tl._TAB10 for c in colors), str(colors))
    i_case = idx_of(w, 'case_02')
    i_ref = idx_of(w, 'curve2')
    info = w.logs_curves_table.item(i_case, 6).text()
    check("info column (n, duration, dt, End)", 'n=1214' in info and 'End: job finished' in info, info)
    w.logs_canvas.draw()
    check("plot shows one line per visible curve on SI",
          sorted(lines_labels(w)) == sorted(f"{e.curve.name} · SI" for e in st.entries), str(lines_labels(w)))
    ref_line = [ln for ln in w.logs_ax.get_lines() if ln.get_label() == 'curve2 · SI'][0]
    log_line = [ln for ln in w.logs_ax.get_lines() if ln.get_label().startswith('log_06112026')][0]
    check("reference drawn thicker", ref_line.get_linewidth() > log_line.get_linewidth())

    # all-zero (6 Nov broken) log warned in the info column
    broken = sorted(glob.glob(os.path.join(HOME, "Desktop", "log_10_*.csv")))
    if broken:
        tl.logs_add_files(w, [broken[0]])
        r = len(st.entries) - 1
        txt = w.logs_curves_table.item(r, 6).text()
        check("all-zero log: visible warning in the info column", txt.startswith('WARNING') and
              w.logs_curves_table.item(r, 6).foreground().color().name() == '#c62828', txt[:60])
        tl.logs_remove_curves(w, [r])
        check("remove the broken log", len(st.entries) == 5 and 'X' not in st.known_axes, str(st.known_axes[:4]))

    # connection gap lines (newest format): hatched span + broken line, End reason in the info
    gap_log = os.path.join(TMP, "log_gap.csv")
    rows = ["# Computer Time: 2026-11-07 10:00:00.000", "# G-code: 0:/gcodes/job_platform.gcode",
            "# Device: Motion Platform", "# Axes (Duet order): X,Y,Z,A,B,C,D,'a,'c,'e,'f",
            "Time_s,Pos_LAT_mm,Pos_SI_mm,Pos_AP_mm,Pos_Roll_deg,Pos_Pitch_deg,Pos_Yaw_deg,Probe"]
    state_ = 'before'
    for k in range(40):
        t_ = 0.05 + 0.08 * k
        if state_ == 'before' and t_ > 1.6:
            rows.append("# Gap: connection lost at 1.581 s")
            state_ = 'gap'
        if state_ == 'gap':
            if t_ < 2.7:
                continue
            rows.append("# Gap end: reconnected at 2.713 s")
            state_ = 'after'
        rows.append(f"{t_:.3f},50.000,{25 + 0.1 * k:.3f},35.000,0.000,0.000,0.000,{1000 if 10 < k < 14 else 0}")
    rows.append("# End: job finished at 3.200 s")
    with open(gap_log, 'w', encoding='utf-8') as f:
        f.write(chr(10).join(rows) + chr(10))
    tl.logs_add_files(w, [gap_log])
    r = idx_of(w, 'log_gap')
    gc = st.entries[r].curve
    tl.logs_set_display(w, show_gaps=True, show_probe=True)
    w.logs_canvas.draw()
    hatched = [c for c in st.artists if c.__class__.__name__ == 'PolyCollection' and c.get_hatch()]
    gline = [ln for ln in w.logs_ax.get_lines() if ln.get_label() == 'log_gap · SI'][0]
    check("gap log: hatched gap span and the line is broken in the gap",
          gc.meta['gaps'] == [(1.581, 2.713)] and len(hatched) == 1 and np.isnan(gline.get_ydata()).sum() == 1,
          str(gc.meta['gaps']))
    info = w.logs_curves_table.item(r, 6).text()
    check("gap log info: G-code, End reason and gap count", 'G-code: job_platform.gcode' in info
          and 'End: job finished' in info and '1 gap(s)' in info, info)
    tl.logs_remove_curves(w, [r])

    # ------------------------------------------------------------------ axes
    tl.logs_set_axis_enabled(w, 'LAT', True)
    w.logs_canvas.draw()
    check("enable LAT: checkbox on and LAT lines drawn", w.logs_axis_checks['LAT'].isChecked()
          and any(lb.endswith('· LAT') for lb in lines_labels(w)))
    styles = {ln.get_label().split(' · ')[-1]: ln.get_linestyle() for ln in w.logs_ax.get_lines()
              if ' · ' in ln.get_label()}
    check("line style per axis", styles.get('SI') != styles.get('LAT'), str(styles))
    w.logs_axis_checks['LAT'].setChecked(False)          # through the widget signal
    check("disable LAT from its checkbox", 'LAT' not in st.enabled_axes
          and not any(lb.endswith('· LAT') for lb in lines_labels(w)))
    tl.logs_set_axis_enabled(w, 'Cmd SI', True)
    check("Cmd axes listed after the positions and drawable", "Cmd SI" in st.known_axes
          and st.known_axes.index('Cmd SI') > st.known_axes.index("'c")
          and any(lb.endswith('· Cmd SI') for lb in lines_labels(w)))
    tl.logs_set_axis_enabled(w, 'Cmd SI', False)
    n0 = len(FakeBox.calls)
    r = tl.logs_set_axis_enabled(w, 'NoSuchAxis', True)
    check("unknown axis -> warning, no exception", r is None and len(warnings_since(n0)) == 1)
    tl.logs_set_analysis_axis(w, 'AP')
    check("analysis axis AP (combo + enabled)", st.analysis_axis == 'AP' and w.logs_axis_combo.currentData() == 'AP'
          and 'AP' in st.enabled_axes)
    w.logs_axis_combo.setCurrentIndex(st.known_axes.index('SI'))     # through the widget
    check("analysis axis SI from the combo", st.analysis_axis == 'SI')
    tl.logs_set_axis_enabled(w, 'AP', False)
    tl.logs_set_display(w, show_probe=True, show_gaps=True)
    w.logs_canvas.draw()
    probe_cols = [c for c in st.artists if c.__class__.__name__ == 'PolyCollection']
    check("probe events shaded (release button of case_02)", len(probe_cols) >= 1)
    tl.logs_set_display(w, show_probe=False)
    check("probe shading off", not w.logs_chk_probe.isChecked() and st.show_probe is False)
    tl.logs_set_display(w, show_probe=True)

    # ------------------------------------------------------------------ visibility / table widgets
    it = w.logs_curves_table.item(0, 0)
    it.setCheckState(Qt.Unchecked)
    check("hide a curve from the table checkbox", st.entries[0].visible is False
          and not any(lb.startswith(st.entries[0].curve.name) for lb in lines_labels(w)))
    it.setCheckState(Qt.Checked)
    check("show it again", st.entries[0].visible is True)
    sp = w.logs_toff_spins[1]
    sp.setValue(1.234)
    check("time offset spin -> curve time_offset", abs(st.entries[1].curve.time_offset - 1.234) < 1e-12)
    tl.logs_set_time_offset(w, 1, 0.0)
    check("logs_set_time_offset updates the spin", abs(w.logs_toff_spins[1].value()) < 1e-12)
    w.logs_voff_spins[1].setValue(0.5)
    check("value offset spin -> value_offsets[SI]", abs(st.entries[1].curve.value_offsets.get('SI', 0) - 0.5) < 1e-12)
    tl.logs_set_value_offset(w, 1, 0.0)
    tl.logs_set_curve_color(w, 1, '#123456')
    check("curve colour change", st.entries[1].color == '#123456')
    tl.logs_select_curve(w, i_case)
    check("select curve", st.selected == i_case and 'case_02' in w.logs_selected_label.text())

    # ------------------------------------------------------------------ ROI
    tl.logs_set_roi(w, 80.0, 15.0)
    check("ROI set (sorted) and spins synced", st.roi == (15.0, 80.0) and abs(w.logs_spin_roi0.value() - 15) < 1e-9
          and abs(w.logs_spin_roi1.value() - 80) < 1e-9)
    w.logs_spin_roi1.setValue(85.0)
    check("ROI end spin -> ROI", st.roi == (15.0, 85.0), str(st.roi))
    n0 = len(FakeBox.calls)
    tl.logs_set_roi(w, 5.0, 5.0)
    check("zero-length ROI -> warning, ROI unchanged", st.roi == (15.0, 85.0) and len(warnings_since(n0)) == 1)
    tl.logs_zoom_to_roi(w)
    xl = w.logs_ax.get_xlim()
    check("zoom to ROI", 12.0 < xl[0] < 15.0 and 85.0 < xl[1] < 88.0, str(xl))
    tl.logs_zoom_all(w)
    # drag on the plot in ROI mode (SpanSelector)
    tl.logs_set_pick_mode(w, 'roi')
    check("ROI select mode: toggle checked, span active", w.logs_btn_roi_select.isChecked() and w.logs_span.active
          and not w.logs_btn_points_mode.isChecked())
    w.logs_canvas.draw()
    tr = w.logs_ax.transData
    ymid = float(np.mean(w.logs_ax.get_ylim()))
    xa, ya = tr.transform((30.0, ymid))
    xb, yb = tr.transform((60.0, ymid))
    mouse(w, 'button_press_event', xa, ya)
    mouse(w, 'motion_notify_event', (xa + xb) / 2, ya)
    mouse(w, 'motion_notify_event', xb, yb)
    mouse(w, 'button_release_event', xb, yb)
    check("ROI dragged on the plot", st.roi is not None and abs(st.roi[0] - 30.0) < 0.5 and abs(st.roi[1] - 60.0) < 0.5,
          str(st.roi))
    tl.logs_clear_roi(w)
    check("clear ROI", st.roi is None and w.logs_roi_label.text() == 'ROI: all data')
    tl.logs_set_pick_mode(w, None)
    tl.logs_set_roi(w, 15.0, 85.0)

    # ------------------------------------------------------------------ pauses / alignment
    n0 = len(FakeBox.calls)
    pt_ = w.logs_pause_table
    hdr_p = [pt_.horizontalHeaderItem(c).text() for c in range(pt_.columnCount())]
    check("pause table: #, Pause, G-code t (s), Length (s), Ended by, Note, read-only; the sensor_wait pause has length 0 "
          "(no loaded log has logged waits: shown as recorded, nothing estimated)",
          hdr_p == tl._PAUSE_HEADERS and pt_.rowCount() == 1 and pt_.item(0, 1).text() == 'sensor_wait'
          and pt_.item(0, 3).text() == '0.000' and not (pt_.item(0, 3).flags() & Qt.ItemIsEditable)
          and pt_.cellWidget(0, 3) is None and 'no logged waits' in w.logs_pause_label.text()
          and st.entries[i_ref].curve.meta['pause_durations'] == [0.0], f"{hdr_p} {w.logs_pause_label.text()}")
    check("pause estimation is gone: no 'Estimate pauses' button, no pause-length spin boxes, no estimate / set functions",
          not hasattr(w, 'logs_btn_est_pauses') and not hasattr(w, 'logs_pause_spins')
          and not any(hasattr(tl, n) for n in ('logs_estimate_pauses', 'logs_set_pause_durations', '_on_pause_spin'))
          and not hasattr(la, 'estimate_pause_durations')
          and not any(b.text().lower().startswith('estimate') for b in w.logs_root.findChildren(QPushButton)))
    check("Pauses: 'Show (real time)' checked by default, 'Pause lengths from:' disabled without logged waits",
          w.logs_radio_pause_show.isChecked() and not w.logs_radio_pause_remove.isChecked()
          and not w.logs_pause_source_combo.isEnabled() and st.pause_mode == 'show')
    tl.logs_add_point(w, i_ref, 26.0)                 # on the reference, after the pause
    tq0, vq0 = tl._point_tv(st, st.points[-1])
    traw0 = st.points[-1]['t_raw']
    tl.logs_add_files(w, [DUMMY])
    i_dummy = idx_of(w, 'DUMMY')
    d = st.entries[i_ref].curve.meta['pause_durations']
    check("a log with a logged wait loaded: the pause takes its logged length (end - received = 1.739 s, Show)",
          len(d) == 1 and abs(d[0] - 1.7391) < 1e-9 and 'DUMMY_wait' in w.logs_pause_source_combo.currentText()
          and w.logs_pause_source_combo.isEnabled(), str(d))
    check("status line after loading: '<name>: 1 logged sensor wait (1.74 s)'",
          'log_06112026_12_34_12_case_02_DUMMY_wait: 1 logged sensor wait (1.74 s)' in st.summary, st.summary)
    tq1, vq1 = tl._point_tv(st, st.points[-1])
    check("point on the reference follows the pause change (same motion, later by the pause)",
          abs(vq1 - vq0) < 1e-9 and abs((tq1 - tq0) - d[0]) < 1e-6, f"t {tq0:.3f} -> {tq1:.3f} s, v {vq1:.4f}")
    tip = pt_.item(0, 3).toolTip()
    check("pause table: 1.739 s, Release button, logged; the tooltip gives the full logged timing",
          pt_.item(0, 3).text() == '1.739' and pt_.item(0, 4).text() == 'Release button' and pt_.item(0, 5).text() == 'logged'
          and 'between 9.640 and 10.110 s' in tip and 'received at 10.110 s' in tip and '11.849' in tip, tip)
    check("reference rebuilt with the pause (longer)",
          abs(st.entries[i_ref].curve.meta['total_time'] - (89.65 + d[0])) < 0.05,
          f"{st.entries[i_ref].curve.meta['total_time']:.3f}")
    tl.logs_remove_curves(w, [i_dummy])
    check("the log with the wait removed: the pause back to 0 s, the reference point exactly where it was",
          st.entries[i_ref].curve.meta['pause_durations'] == [0.0] and st.points[-1]['t_raw'] == traw0
          and len(st.entries) == 5 and 'Waits' not in st.results)
    tl.logs_clear_points(w)

    t0 = time.perf_counter()
    res = tl.logs_auto_align(w, all_curves=True)
    t_align = time.perf_counter() - t0
    check("auto-align all: one result per visible log", res is not None and len(res) == 4, f"{t_align:.2f} s")
    r_case = [r for r in res if 'case_02' in r['curve']][0]
    check("case_02 (v1, no logged wait, shown as recorded): the real pause length remains for auto-align "
          "(shift -2.5 .. -2.8 s in the ROI after the pause, corr > 0.999)",
          -2.8 < r_case['shift'] < -2.5 and r_case['corr'] > 0.999, f"{r_case['shift']:+.4f} s, {r_case['corr']:.5f}")
    check("time offsets applied and shown in the table",
          abs(st.entries[i_case].curve.time_offset - r_case['shift']) < 1e-9
          and abs(w.logs_toff_spins[i_case].value() - round(r_case['shift'], 3)) < 1e-9)
    check("alignment results view", st.current_results == 'Alignment' and w.logs_results_table.rowCount() == 4)
    off_before = st.entries[i_case].curve.time_offset
    tl.logs_select_curve(w, i_case)
    res1 = tl.logs_auto_align(w, all_curves=False)
    check("auto-align selected (already aligned: ~0 shift)", res1 is not None and len(res1) == 1
          and abs(st.entries[i_case].curve.time_offset - off_before) < 0.02)
    tl.logs_select_curve(w, i_ref)
    n0 = len(FakeBox.calls)
    check("auto-align the reference itself -> warning", tl.logs_auto_align(w) is None and len(warnings_since(n0)) == 1)

    # ------------------------------------------------------------------ compare
    tl.logs_set_display(w, show_diff=True)
    t0 = time.perf_counter()
    cmp_rows = tl.logs_compare(w)
    t_cmp = time.perf_counter() - t0
    tbl = w.logs_results_table
    n_vis = sum(1 for e in st.entries if e.visible and e.uid != st.ref_uid and e.curve.has('SI'))
    check("compare: one results row per visible curve", cmp_rows is not None and tbl.rowCount() == n_vis == 4,
          f"{tbl.rowCount()} rows, {t_cmp:.2f} s")
    hdrs = [tbl.horizontalHeaderItem(c).text() for c in range(tbl.columnCount())]
    num_cols = [hdrs.index(h) for h in hdrs if h.split(' (')[0] in ('Mean diff', 'STD', 'RMS', 'Max |diff|', 'P95 |diff|')]
    cells = [tbl.item(r, c).text() for r in range(tbl.rowCount()) for c in num_cols]
    check("compare: finite numbers in the table", len(num_cols) == 5 and all(
        _is_number(x) for x in cells), str(cells[:6]))
    rc = [r for r in cmp_rows if 'case_02' in r['curve']][0]
    check("case_02 vs curve2 on SI: rms < 0.05 mm, corr > 0.999",
          rc['rms'] < 0.05 and rc['corr'] > 0.999 and finite(rc['mean'], rc['std'], rc['max_abs'], rc['p95_abs']),
          f"mean {rc['mean']:+.4f}, std {rc['std']:.4f}, rms {rc['rms']:.4f}, corr {rc['corr']:.5f}")
    w.logs_canvas.draw()
    check("difference plot visible with one line per curve", w.logs_ax_diff.get_visible()
          and len([ln for ln in w.logs_ax_diff.get_lines() if ln.get_linewidth() > 1.0]) == 4)
    check("summary label: compare + ensemble STD", 'Compare to' in w.logs_summary.text()
          and 'mean STD' in w.logs_summary.text(), w.logs_summary.text())

    tl.logs_set_display(w, show_band=True, band_k=2.0, show_envelope=True)
    w.logs_canvas.draw()
    labels = [h.get_label() for h in w.logs_ax.get_legend().legend_handles] if hasattr(
        w.logs_ax.get_legend(), 'legend_handles') else [t.get_text() for t in w.logs_ax.get_legend().get_texts()]
    texts = [t.get_text() for t in w.logs_ax.get_legend().get_texts()]
    check("ensemble band + envelope + mean in the legend",
          any('mean ± 2·STD' in t for t in texts) and any('envelope' in t for t in texts)
          and any(t.startswith('mean ·') for t in texts), str(texts[:4]))
    check("summary shows N, mean STD and max STD", 'N=4' in w.logs_summary.text()
          and 'max STD' in w.logs_summary.text(), w.logs_summary.text())
    tl.logs_set_display(w, band_k=3.0)
    check("k spin follows", abs(w.logs_spin_band_k.value() - 3.0) < 1e-12 and st.band_k == 3.0)

    # ------------------------------------------------------------------ peaks
    # the sample jobs are ramps (no peaks): add a synthetic periodic log (sine, period 4 s, 200 ms staircase)
    sine_log = os.path.join(TMP, "log_synthetic_sine.csv")
    ts = np.arange(0.0, 60.0, 0.08)
    held = np.floor(ts / 0.2 + 1e-9) * 0.2
    si = 26.0 + 2.0 * np.sin(2.0 * np.pi * held / 4.0)
    header = ["# Computer Time: 2026-11-07 10:00:00.000", "# Device: Motion Platform",
              "# Axes (Duet order): X,Y,Z,A,B,C,D,'a,'c,'e,'f",
              "Time_s,Pos_LAT_mm,Pos_SI_mm,Pos_AP_mm,Pos_Roll_deg,Pos_Pitch_deg,Pos_Yaw_deg,Probe"]
    body = [f"{t_:.4f},50.000,{v_:.3f},35.000,0.000,0.000,0.000,0" for t_, v_ in zip(ts, si)]
    with open(sine_log, 'w', encoding='utf-8') as f:
        f.write(chr(10).join(header + body) + chr(10))
    tl.logs_add_files(w, [sine_log])
    i_sine = idx_of(w, 'synthetic_sine')
    t0 = time.perf_counter()
    pk = tl.logs_find_peaks(w, prominence=0.0, min_distance=0.5, kind='both')
    t_pk = time.perf_counter() - t0
    check("find peaks: result row per visible curve", pk is not None and len(pk) == 6
          and st.current_results == 'Peaks & periods' and w.logs_results_table.rowCount() == 6, f"{t_pk:.2f} s")
    hdr_pk = st.results['Peaks & periods'][0]
    row = [r for r in st.results['Peaks & periods'][1] if 'synthetic_sine' in r[0]][0]
    pk_sine = pk[st.entries[i_sine].curve.name]
    n_max = sum(1 for k in pk_sine['kind'] if k == 'max')
    n_min = sum(1 for k in pk_sine['kind'] if k == 'min')
    check("sine in ROI 15-85 s: maxima and minima found", 10 <= n_max <= 12 and 10 <= n_min <= 12, f"{n_max} max, {n_min} min")
    pm = row[hdr_pk.index('Period mean (s)')]
    dp = row[hdr_pk.index('Dominant period (s)')]
    check("period mean ~4 s and dominant period ~4 s", abs(pm - 4.0) < 0.1 and abs(dp - 4.0) < 0.1,
          f"mean {pm:.3f} s, std {row[hdr_pk.index('Period STD (s)')]:.3f}, dominant {dp:.3f} s, "
          f"freq {row[hdr_pk.index('Freq (Hz)')]:.4f} Hz")
    check("peak list view: one row per peak", 'Peak list' in st.results and len(st.results['Peak list'][1]) ==
          sum(len(v['t']) for v in pk.values()))
    w.logs_canvas.draw()
    markers = [ln for ln in w.logs_ax.get_lines() if ln.get_marker() in ('^', 'v')]
    check("peak markers drawn (max ^ and min v)", {ln.get_marker() for ln in markers} == {'^', 'v'})
    tl.logs_show_results(w, 'Peak list')
    check("switch results view", st.current_results == 'Peak list' and w.logs_results_combo.currentText() == 'Peak list')
    pk2 = tl.logs_find_peaks(w, prominence=0.0, min_distance=0.5, kind='max')
    check("maxima only", pk2 is not None and set(pk2[st.entries[i_sine].curve.name]['kind']) == {'max'})
    tl.logs_remove_curves(w, [i_sine])
    check("synthetic log removed with its peaks", len(st.entries) == 5 and len(st.peaks) == 5)
    tl.logs_clear_peaks(w)
    check("clear peaks", not st.peaks)

    # ------------------------------------------------------------------ movements
    t0 = time.perf_counter()
    mv = tl.logs_detect_movements(w, threshold=0.02, settle_time=0.5, min_duration=0.0, merge_gap=0.0)
    t_mv = time.perf_counter() - t0
    mv_case = [v for k, v in mv.items() if 'case_02' in k][0] if mv else []
    check("case_02 gives several SI movements (3)", len(mv_case) == 3,
          ", ".join(f"{m['t_start']:.2f}-{m['t_stop']:.2f}s" for m in mv_case) + f" ({t_mv:.2f} s)")
    rows = st.results['Movements'][1]
    check("movement rows: start < stop, duration > 0", all(r[3] < r[4] and r[5] > 0 for r in rows), str(len(rows)))
    check("movement results view shown", st.current_results == 'Movements'
          and w.logs_results_table.rowCount() == len(rows))
    w.logs_canvas.draw()
    lanes = [c for c in st.artists if c.__class__.__name__ == 'PolyCollection' and c.get_paths()
             and max(float(pth.vertices[:, 1].max()) for pth in c.get_paths()) < 0.3]
    n_with = sum(1 for v in mv.values() if v)
    check("one thin movement lane per curve with movements", len(lanes) == n_with, f"{len(lanes)} lanes")
    yl = w.logs_ax.get_ylim()
    frac = (25.0 - yl[0]) / (yl[1] - yl[0])
    check("y-range leaves room for the lanes below the data", frac > tl._LANE_Y0 + len(mv) * tl._LANE_STEP,
          f"data min at {frac:.3f} of the axes")

    # ------------------------------------------------------------------ reference points
    tl.logs_clear_points(w)
    p1 = tl.logs_add_point(w, i_ref, 26.0 + st.entries[i_ref].curve.time_offset)
    p2 = tl.logs_add_point(w, i_case, 35.0)
    check("2 points added", p1 == 1 and p2 == 2 and w.logs_points_table.rowCount() == 2)
    (ta, va), (tb, vb) = tl._point_tv(st, st.points[0]), tl._point_tv(st, st.points[1])
    dt_cell = w.logs_points_table.item(1, 5).text()
    check("points table dt to previous", abs(float(dt_cell) - (tb - ta)) < 1e-3, dt_cell)
    off0 = st.entries[i_case].curve.time_offset
    voff0 = st.entries[i_case].curve.value_offsets.get('SI', 0.0)
    r = tl.logs_align_points(w, 0, 1, match_value=True)
    off1 = st.entries[i_case].curve.time_offset
    voff1 = st.entries[i_case].curve.value_offsets.get('SI', 0.0)
    tb2, vb2 = tl._point_tv(st, st.points[1])
    check("align at points: time offset changes by t1 - t2", r is not None and abs((off1 - off0) - (ta - tb)) < 1e-9,
          f"{off1 - off0:+.4f} vs {ta - tb:+.4f}")
    check("align at points: value offset changes by v1 - v2", abs((voff1 - voff0) - (va - vb)) < 1e-9)
    check("points coincide after alignment", abs(tb2 - ta) < 1e-9 and abs(vb2 - va) < 1e-9)
    check("offset spin updated", abs(w.logs_toff_spins[i_case].value() - round(off1, 3)) < 1e-9)
    n0 = len(FakeBox.calls)
    p3 = tl.logs_add_point(w, i_case, 40.0)
    check("align 2 points on the same curve -> warning", tl.logs_align_points(w, 1, 2) is None
          and len(warnings_since(n0)) == 1)
    tl.logs_delete_points(w, [2])
    check("delete a point", len(st.points) == 2 and w.logs_points_table.rowCount() == 2)
    # click on the plot in points mode (snaps to the nearest sample of the nearest visible curve);
    # away from the two points at ~26 s: a press on an existing point drags it (round 5)
    tl.logs_set_pick_mode(w, 'points')
    w.logs_canvas.draw()
    rc_ = st.entries[i_ref].curve
    t_corner = float(rc_.times()[np.argmin(np.abs(rc_.times() - (50.0 + rc_.time_offset)))])
    v_corner = float(np.interp(t_corner, rc_.times(), rc_.values('SI')))
    x_px, y_px = w.logs_ax.transData.transform((t_corner + 0.05, v_corner + 0.01))
    mouse(w, 'button_press_event', x_px, y_px)
    check("click adds a snapped point", len(st.points) == 3, str(st.points[-1] if st.points else None))
    if len(st.points) == 3:
        tp, vp = tl._point_tv(st, st.points[-1])
        e = tl._entry_by_uid(st, st.points[-1]['uid'])
        check("clicked point snapped to a sample of a curve near the click",
              abs(tp - t_corner) < 1.0 and abs(vp - v_corner) < 0.1 and e.curve.has('SI'),
              f"{e.curve.name} t={tp:.3f} v={vp:.4f}")
    w.logs_toolbar.pan()                     # pan / zoom active -> clicks are ignored
    mouse(w, 'button_press_event', x_px, y_px)
    check("click ignored while the toolbar is in pan mode", len(st.points) == 3)
    w.logs_toolbar.pan()
    tl.logs_set_pick_mode(w, None)
    mouse(w, 'button_press_event', x_px, y_px)
    check("click ignored when points mode is off", len(st.points) == 3)
    check("Points results view kept up to date", len(st.results.get('Points', (None, []))[1]) == 3)

    # ------------------------------------------------------------------ Duet reference (patched download)
    hdr_log = os.path.join(TMP, "log_with_gcode.csv")
    with open(CASE02, encoding='utf-8') as f:
        lines = f.read().splitlines()
    lines.insert(1, "# G-code: 0:/gcodes/job_platform.gcode")
    with open(hdr_log, 'w', encoding='utf-8', newline='\n') as f:
        f.write("\n".join(lines) + "\n")
    tl.logs_add_files(w, [hdr_log])
    i_hdr = idx_of(w, 'log_with_gcode')
    tl.logs_select_curve(w, i_hdr)
    w.duet_connected = False
    tl._update_duet_button(w)
    check("Duet reference button disabled without a connection", not w.logs_btn_duet_ref.isEnabled())
    w.duet_connected = True
    w.duet_ip = '10.1.2.3'
    tl._update_duet_button(w)
    check("Duet reference button enabled (connected + log with G-code)", w.logs_btn_duet_ref.isEnabled())
    import fcn_monitor.fcn_duet as fd
    requested = []

    class Resp:
        status_code = 200
        with open(CURVE2, encoding='utf-8') as f:
            text = f.read()

    orig = fd.duet_request
    fd.duet_request = lambda url, *a, **k: (requested.append(url), Resp())[1]
    try:
        c = tl.logs_reference_from_duet(w)
    finally:
        fd.duet_request = orig
    check("reference downloaded from the Duet", c is not None and requested ==
          ['http://10.1.2.3/rr_download?name=/gcodes/job_platform.gcode'] and c.name == 'job_platform'
          and c.meta['gcode'] == 'job_platform.gcode' and st.ref_uid == st.entries[-1].uid, str(requested))
    tl.logs_remove_curves(w, [len(st.entries) - 1, i_hdr])
    tl.logs_set_reference(w, idx_of(w, 'curve2'))
    w.duet_connected = False
    check("back to 5 curves, curve2 reference", len(st.entries) == 5 and
          tl._ref_entry(st).curve.name == 'curve2')

    # ------------------------------------------------------------------ exports
    tl.logs_compare(w)
    p_res = os.path.join(TMP, "results.csv")
    out = tl.logs_export_results(w, p_res)
    notes, hdr_r, rows = la.read_rows_csv(p_res)
    raw_res = open(p_res, encoding='utf-8').read().splitlines()
    check("export results CSV (Compare view): v2 style ('#' notes with the time base, ';' columns, decimal comma)",
          out == p_res and hdr_r[:3] == ['Curve', 'Axis', 'Shift to align (s)'] and len(rows) == 4
          and any(n.startswith('Time base: as recorded') for n in notes) and raw_res[0].startswith('# ')
          and not any(';' in x for x in raw_res if x.startswith('#'))
          and raw_res[len(notes)].startswith('Curve;Axis;') and ',' in raw_res[len(notes) + 1], f"{len(rows)} rows")
    p_al = os.path.join(TMP, "aligned.csv")
    tl.logs_export_aligned(w, p_al)
    df = pd.read_csv(p_al, sep=';', decimal=',', comment='#')
    names = [e.curve.name for e in st.entries if e.visible and e.curve.has('SI')]
    al_cols = ['time [s]'] + [f"SI: {n} [mm]" for n in names]
    check("export aligned CSV: 'time [s]' + one 'SI: <curve> [mm]' column per visible curve, ROI applied",
          list(df.columns) == al_cols and df['time [s]'].min() >= 15.0 - 1e-9
          and df['time [s]'].max() <= 85.0 + 1e-9 and len(df) > 1000, f"{list(df.columns)[:3]}..., {len(df)} rows")
    case_col = [c for c in al_cols if 'case_02' in c][0]
    ref_col = 'SI: curve2 [mm]'
    dd = (df[case_col] - df[ref_col]).abs()
    check("aligned CSV carries the offsets (case_02 matches curve2)", float(dd.median()) < 0.6, f"{dd.median():.4f}")
    p_png = os.path.join(TMP, "plot.png")
    tl.logs_save_figure(w, p_png)
    with open(p_png, 'rb') as f:
        sig = f.read(8)
    check("save figure PNG", sig == b'\x89PNG\r\n\x1a\n' and os.path.getsize(p_png) > 20000,
          f"{os.path.getsize(p_png)} bytes")
    n0 = len(FakeBox.calls)
    st_cur = st.current_results
    st.current_results = None
    check("export without results -> warning", tl.logs_export_results(w, os.path.join(TMP, 'x.csv')) is None
          and len(warnings_since(n0)) == 1)
    st.current_results = st_cur

    # ------------------------------------------------------------------ unusable files / bad input
    bad = os.path.join(TMP, "bad.csv")
    with open(bad, 'w', encoding='utf-8') as f:
        f.write("hello\nworld\n")
    n_before = len(st.entries)
    n0 = len(FakeBox.calls)
    try:
        r = tl.logs_add_files(w, [bad, os.path.join(TMP, "missing.csv")])
        raised = False
    except Exception:
        raised = True
        traceback.print_exc()
    wn = warnings_since(n0)
    check("unusable files: one warning, no exception, nothing added", not raised and r == [] and len(wn) == 1
          and 'bad.csv' in wn[0][2] and 'missing.csv' in wn[0][2] and len(st.entries) == n_before,
          wn[0][2].replace('\n', ' | ')[:160] if wn else '')
    n0 = len(FakeBox.calls)
    r = tl.logs_add_files(w, [bad, CHECK_LOGS[0]])
    check("mixed good/bad files: good one added, warning for the bad one", r is not None and len(r) == 1
          and len(warnings_since(n0)) == 1 and len(st.entries) == n_before + 1)
    check("duplicate file gets a unique name", st.entries[-1].curve.name.endswith('(2)'), st.entries[-1].curve.name)
    n0 = len(FakeBox.calls)
    check("bad reference G-code -> warning", tl.logs_add_reference(w, "; nothing here\n") is None
          and len(warnings_since(n0)) == 1)

    # ------------------------------------------------------------------ remove / clear
    k_before = len(st.entries)
    removed_uid = st.entries[-1].uid
    tl.logs_remove_curves(w, [k_before - 1])
    check("remove selected curve", len(st.entries) == k_before - 1 and removed_uid not in st.peaks
          and w.logs_curves_table.rowCount() == k_before - 1)
    tl.logs_select_curve(w, idx_of(w, 'curve2'))
    tl.logs_remove_curves(w)
    check("removing the reference picks a new default reference", tl._ref_entry(st) is not None
          and tl._ref_entry(st).curve.kind == 'log' and w.logs_pause_table.rowCount() == 0)
    tl.logs_reset_offsets(w)
    check("reset offsets", all(e.curve.time_offset == 0.0 and not e.curve.value_offsets for e in st.entries))
    tl.logs_clear_all(w)
    w.logs_canvas.draw()
    check("clear all", not st.entries and not st.points and not st.results and w.logs_curves_table.rowCount() == 0
          and not lines_labels(w) and w.logs_results_table.rowCount() == 0)
    n0 = len(FakeBox.calls)
    check("compare with nothing loaded -> warning, no exception", tl.logs_compare(w) is None
          and len(warnings_since(n0)) == 1, warnings_since(n0)[0][2] if warnings_since(n0) else '')
    check("find peaks with nothing loaded -> warning", tl.logs_find_peaks(w) is None)
    tl.logs_set_display(w, show_diff=False)
    w.logs_canvas.draw()
    check("difference axes hidden again", not w.logs_ax_diff.get_visible())
    print(f"INFO: timings: add 4 logs {t_add:.2f} s, align all {t_align:.2f} s, compare {t_cmp:.2f} s, "
          f"peaks {t_pk:.2f} s, movements {t_mv:.2f} s")
    print(f"INFO: QMessageBox calls recorded: {len(FakeBox.calls)}")


def _is_number(s):
    try:
        return math.isfinite(float(s))
    except ValueError:
        return False


# ---------------------------------------------------------------------------------------------
# Review fixes (own window at 1600x900; independent of the flow above)
# ---------------------------------------------------------------------------------------------
def wheel(widget, dy=120):
    """One wheel notch delivered to a widget as the window system does; returns whether the event
    ended up accepted.  Qt 6 passes an ignored wheel event on to the parents (up to the scroll area
    of the left panel) only when it is spontaneous - a synthetic sendEvent stops at the widget - so
    the spontaneous flag is set in the QEvent (Qt 6 layout: byte 11, bit 0; checked with
    ev.spontaneous()) and the event goes through QApplication.notify.  Without that (other Qt
    layout) the event is sent normally and WHEEL_SPONTANEOUS is False."""
    global WHEEL_SPONTANEOUS
    import ctypes
    import shiboken6
    from PySide6.QtCore import QPointF, QPoint
    from PySide6.QtGui import QWheelEvent
    pos = QPointF(widget.width() / 2.0, widget.height() / 2.0)
    gpos = QPointF(widget.mapToGlobal(pos.toPoint()))
    ev = QWheelEvent(pos, gpos, QPoint(0, 0), QPoint(0, dy), Qt.NoButton, Qt.NoModifier, Qt.NoScrollPhase, False)
    if WHEEL_SPONTANEOUS is not False:
        b = ctypes.c_uint8.from_address(shiboken6.getCppPointer(ev)[0] + 11)
        old = b.value
        b.value = old | 1
        WHEEL_SPONTANEOUS = bool(ev.spontaneous())
        if not WHEEL_SPONTANEOUS:
            b.value = old
            print("INFO: cannot mark a wheel event spontaneous with this Qt: wheel checks use sendEvent")
    if WHEEL_SPONTANEOUS:
        APP.notify(widget, ev)               # sendEvent() would clear the spontaneous flag again
    else:
        QApplication.sendEvent(widget, ev)
    return ev.isAccepted()


WHEEL_SPONTANEOUS = None


def wheel_scrolls(w, widget, dy=120):
    """(scrolled, accepted): one notch over `widget` with the left panel (and the tables) scrolled
    to the middle; scrolled = the left panel or the table around the widget moved."""
    bars = [w.logs_left_scroll.verticalScrollBar()]
    for tbl in (w.logs_curves_table, w.logs_pause_table):
        if tbl.isAncestorOf(widget):
            bars.append(tbl.verticalScrollBar())
    for b in bars:
        b.setValue((b.minimum() + b.maximum()) // 2)
    APP.processEvents()
    before = [b.value() for b in bars]
    acc = wheel(widget, dy)
    APP.processEvents()
    return [b.value() for b in bars] != before, acc


def wait_ms(ms):
    t_end = time.perf_counter() + ms / 1000.0
    while time.perf_counter() < t_end:
        APP.processEvents()
        time.sleep(0.005)


def expected_diff_ylim(w):
    """Independent fit of the difference panel: the drawn diff lines inside the main xlim (plus one
    sample beyond each edge), 0 included, 8 % padding."""
    x0, x1 = sorted(w.logs_ax.get_xlim())
    lo, hi = np.inf, -np.inf
    for ln in w.logs_ax_diff.get_lines():
        if ln.get_linewidth() <= 1.0:             # the zero line
            continue
        x = np.asarray(ln.get_xdata(), dtype=float)
        y = np.asarray(ln.get_ydata(), dtype=float)
        i0 = max(0, int(np.searchsorted(x, x0)) - 1)
        i1 = min(x.size, int(np.searchsorted(x, x1, side='right')) + 1)
        seg = y[i0:i1]
        seg = seg[np.isfinite(seg)]
        if seg.size:
            lo, hi = min(lo, float(seg.min())), max(hi, float(seg.max()))
    lo, hi = min(lo, 0.0), max(hi, 0.0)
    pad = (hi - lo) * 0.08 if hi > lo else max(abs(hi) * 0.1, 0.01)
    return lo - pad, hi + pad


def write_log(path, t, si, extra=()):
    hdr = ["# Computer Time: 2026-11-07 10:00:00.000", "# Device: Motion Platform"] + list(extra) + \
          ["Time_s,Pos_LAT_mm,Pos_SI_mm,Pos_AP_mm,Pos_Roll_deg,Pos_Pitch_deg,Pos_Yaw_deg,Probe"]
    body = [x if isinstance(x, str) else f"{x[0]:.3f},50.000,{x[1]:.3f},35.000,0.000,0.000,0.000,0"
            for x in (zip(t, si) if not isinstance(t, list) else t)]
    with open(path, 'w', encoding='utf-8') as f:
        f.write("\n".join(hdr + body) + "\n")


def label_fits(lbl):
    """The text an _ElidedLabel shows fits it: its width (QLabel's own size hint for that text, i.e.
    the widest shown line plus the label's margins), at most its max lines, and the label is as
    high as those lines (not squeezed by the layout, which would clip them)."""
    from PySide6.QtWidgets import QLabel
    shown = lbl.shownText()
    return (QLabel.sizeHint(lbl).width() <= lbl.width() and shown.count('\n') + 1 <= lbl.maxLines()
            and lbl.height() >= lbl.sizeHint().height())


def layout_measure(w):
    tbl = w.logs_curves_table
    s = w.logs_summary
    return {'window': [w.width(), w.height()], 'min_w': w.minimumSizeHint().width(),
            'splitter': w.logs_splitter.sizes(), 'viewport': tbl.viewport().width(),
            'cols_end': tbl.columnViewportPosition(5) + tbl.columnWidth(5),
            'hscroll': w.logs_left_scroll.horizontalScrollBar().maximum(),
            'canvas': [w.logs_canvas.width(), w.logs_canvas.height()],
            'summary': {'chars': len(s.text()), 'lines': s.shownText().count('\n') + 1, 'elided': s.isElided(),
                        'fits': label_fits(s), 'width': s.width(), 'height': s.height(),
                        'full': s.text() == w.logs_state.summary and s.toolTip() == w.logs_state.summary},
            'left_labels_fit': all(label_fits(x) for x in (w.logs_selected_label, w.logs_pause_label,
                                                           w.logs_roi_label))}


def layout_probe():
    """--layout-probe (subprocess with QT_QPA_FONTDIR = Windows fonts): measure the curves table at
    1600x900 and 1366x768, then the window after long status messages (Detect movements with 4
    curves, the hidden-axis message, a 2000-character message, a short one) and after loading a log
    with a very long name; print one 'LAYOUT {json}' line."""
    import json
    from PySide6.QtGui import QFont
    APP.setFont(QFont("Segoe UI", 9))
    APP.setStyle('Fusion')                       # as Launch_ImGUI
    tl.QMessageBox = FakeBox
    w = make_window()
    tl.build_logs_tab(w)
    tl.logs_add_files(w, [CASE02] + CHECK_LOGS)
    tl.logs_add_reference(w, CURVE2)
    long_log = os.path.join(TMP, "log_" + "very_long_file_name_" * 6 + "end.csv")
    shutil.copyfile(CASE02, long_log)
    out = {}

    def pump(n=8):
        for _ in range(n):
            APP.processEvents()
    for W, H in ((1600, 900), (1366, 768)):
        w.resize(W, H)
        w.show()
        pump(5)
        d = out[f"{W}x{H}"] = layout_measure(w)
        tl.logs_detect_movements(w)              # 4 curves: the longest message of a normal action
        pump()
        d['movements'] = layout_measure(w)
        tl.logs_add_files(w, [CASE02, CASE02])   # 6 curves, 3 with the long case_02 name (> 1198 px)
        tl.logs_detect_movements(w)
        pump()
        d['movements_6'] = layout_measure(w)
        tl.logs_remove_curves(w, [len(w.logs_state.entries) - 1, len(w.logs_state.entries) - 2])
        tl.logs_set_reference(w, idx_of(w, 'curve2'))
        tl.logs_set_axis_enabled(w, 'LAT', True)
        tl.logs_set_axis_enabled(w, 'SI', False)
        tl.logs_set_pick_mode(w, 'points')       # the hidden-axis message
        pump()
        d['hidden_axis'] = layout_measure(w)
        tl.logs_set_pick_mode(w, None)
        tl.logs_set_axis_enabled(w, 'SI', True)
        tl.logs_set_axis_enabled(w, 'LAT', False)
        tl._set_summary(w, "Exported to " + "C:\\a_folder_without_spaces" * 40 + " · " + "word " * 300)
        pump()
        d['huge'] = layout_measure(w)
        tl._set_summary(w, "Ready.")
        pump()
        d['short'] = layout_measure(w)
        tl.logs_add_files(w, [long_log])         # long name: selected label, reference combo, pause label
        tl.logs_set_reference(w, len(w.logs_state.entries) - 1)
        pump()
        d['long_name'] = layout_measure(w)
        tl.logs_remove_curves(w, [len(w.logs_state.entries) - 1])
        tl.logs_set_reference(w, len(w.logs_state.entries) - 1)
        tl.logs_clear_movements(w)
        pump()
        # the aligned export read back: long column names on the axis checkboxes and the combo
        lmin0 = w.logs_left_scroll.widget().minimumSizeHint().width()
        cmin0 = w.logs_axis_combo.minimumSizeHint().width()
        p_al = os.path.join(TMP, f"aligned_{W}.csv")
        tl.logs_export_aligned(w, p_al)
        tl.logs_add_files(w, [p_al])
        pump()
        rb = d['readback'] = layout_measure(w)
        cbs = w.logs_axis_checks
        rb.update(left_min0=lmin0, left_min=w.logs_left_scroll.widget().minimumSizeHint().width(),
                  scroll_min=w.logs_left_scroll.minimumWidth(), n_axes=len(cbs),
                  n_elided=sum('…' in cb.text() for cb in cbs.values()),
                  max_px=max([cb.fontMetrics().horizontalAdvance(cb.text()) for a, cb in cbs.items()
                              if not tl._std_axis(a)] or [0]),
                  std_whole=all('…' not in cb.text() for a, cb in cbs.items() if tl._std_axis(a)),
                  combo_min0=cmin0, combo_min=w.logs_axis_combo.minimumSizeHint().width())
        tl.logs_remove_curves(w, [len(w.logs_state.entries) - 1])
        pump()
        # logged waits (round 7): the pause table and the two legends, Show and Remove
        tl.logs_add_files(w, [DUMMY])
        pump()
        for mode, key in (('show', 'waits'), ('remove', 'waits_remove')):
            tl.logs_set_pause_mode(w, mode)
            pump()
            w.logs_canvas.draw()
            d[key] = _wait_layout(w)
        tl.logs_set_pause_mode(w, 'show')
        tl.logs_remove_curves(w, [idx_of(w, 'DUMMY')])
        pump()
    print("LAYOUT " + json.dumps(out))
    w.close()


def _wait_layout(w):
    """Pause table and legends with a logged wait loaded: main pause columns vs the table viewport, the
    left panel's sideways scroll, the pause label, the colour key vs the curve legend (overlap, inside the
    axes, fraction of the plotted curve points under either box)."""
    pt = w.logs_pause_table
    st = w.logs_state
    ax = w.logs_ax
    r = w.logs_canvas.get_renderer()
    out = {'pause_cols': sum(pt.columnWidth(c) for c in range(5)), 'pause_viewport': pt.viewport().width(),
           'left_hscroll': w.logs_left_scroll.horizontalScrollBar().maximum(),
           'label_fits': label_fits(w.logs_pause_label), 'key_classes': list(st.key_classes)}
    key, leg = st.key_artist, ax.get_legend()
    if key is None or leg is None:
        out.update(overlap=None, inside=False, data_frac=1.0)
        return out
    kb, lb, ab = key.get_window_extent(r), leg.get_window_extent(r), ax.get_window_extent(r)
    pts = [ln.get_transform().transform(np.column_stack([ln.get_xdata(), ln.get_ydata()]))
           for ln in ax.get_lines() if ' · ' in ln.get_label()]
    pts = np.vstack(pts) if pts else np.empty((0, 2))
    pts = pts[np.all(np.isfinite(pts), axis=1)]
    under = int(kb.count_contains(pts)) + int(lb.count_contains(pts)) if pts.size else 0
    out.update(overlap=bool(kb.overlaps(lb)), data_frac=float(under / max(1, len(pts))),
               inside=all(b.x0 >= ab.x0 - 1 and b.x1 <= ab.x1 + 1 and b.y0 >= ab.y0 - 1 and b.y1 <= ab.y1 + 1
                          for b in (kb, lb)), key=list(kb.bounds), legend=list(lb.bounds), axes=list(ab.bounds))
    return out


def layout_in_subprocess():
    import json
    import subprocess
    fontdir = os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts')
    if not os.path.isfile(os.path.join(fontdir, 'segoeui.ttf')):
        return None
    env = dict(os.environ, QT_QPA_PLATFORM='offscreen', QT_QPA_FONTDIR=fontdir, PYTHONIOENCODING='utf-8')
    r = subprocess.run([sys.executable, os.path.abspath(__file__), '--layout-probe'], env=env, capture_output=True,
                       text=True, encoding='utf-8', errors='replace', timeout=600)
    lines = [ln for ln in r.stdout.splitlines() if ln.startswith('LAYOUT ')]
    if not lines:
        print("layout probe output:\n" + r.stdout[-2000:] + r.stderr[-2000:])
        return {}
    return json.loads(lines[-1][len('LAYOUT '):])


_LAYOUT_CACHE = {}          # layout_in_subprocess() result of review_checks, reused by review3_checks


def line_x0(w, label):
    lns = [ln for ln in w.logs_ax.get_lines() if ln.get_label() == label]
    return float(lns[0].get_xdata()[0]) if lns else float('nan')


def review_checks():
    from matplotlib import colors as mcolors
    from PySide6.QtWidgets import QAbstractSpinBox, QComboBox, QLineEdit
    print("\n---- review fixes ----")
    w = make_window()
    w.resize(1600, 900)
    tl.build_logs_tab(w)
    w.show()
    APP.processEvents()
    st = w.logs_state
    tl.logs_add_files(w, [CASE02] + CHECK_LOGS)
    tl.logs_add_reference(w, CURVE2)
    for _ in range(3):
        APP.processEvents()
    i_case, i_ref = idx_of(w, 'case_02'), idx_of(w, 'curve2')

    # 13. layout: the main columns of the curves table fit the default left panel.  Measured in a
    # subprocess with the Windows fonts (Segoe UI 9 pt as in the app): the generic offscreen
    # fallback font is far wider and makes the toolbar alone wider than 1600 px.
    lay = _LAYOUT_CACHE['lay'] = layout_in_subprocess()
    if lay is None:
        print("INFO: Windows fonts not available: layout check skipped")
    else:
        a, b = lay.get('1600x900', {}), lay.get('1366x768', {})
        check("13 1600x900: Show .. v offset columns visible, no horizontal scroll of the left panel",
              a and a['window'][0] == 1600 and a['cols_end'] <= a['viewport'] and a['hscroll'] == 0, str(a))
        check("13 1366x768: same, and the plot keeps >= 700 px",
              b and b['window'][0] == 1366 and b['cols_end'] <= b['viewport'] and b['hscroll'] == 0
              and b['canvas'][0] >= 700, str(b))
        # A. long status messages (the status line had no word wrap: Detect movements with 4 curves
        # needed 1198 px and made the window 1672 px wide; it never shrank back)
        for key, W in (('1600x900', 1600), ('1366x768', 1366)):
            d = lay.get(key, {})
            sub = {k: d.get(k) or {} for k in ('movements', 'movements_6', 'hidden_axis', 'huge', 'short', 'long_name')}
            brief = {k: (s.get('window'), s.get('min_w'), s.get('summary', {}).get('chars'),
                         s.get('summary', {}).get('lines'), s.get('summary', {}).get('elided')) for k, s in sub.items()}
            check(f"A {key}: after Detect movements (4 and 6 curves), the hidden-axis message, a 2000-character "
                  f"message and a log with a long name the window stays {W} px wide and the main curve "
                  "columns stay visible",
                  d and all(s.get('window', [0])[0] == W and s['cols_end'] <= s['viewport'] and s['hscroll'] == 0
                            and s['min_w'] <= d['min_w'] for s in sub.values()), str(brief))
            sm = {k: s.get('summary', {}) for k, s in sub.items()}
            check(f"A {key}: the status line wraps to its width over <= 3 lines; Detect movements and the "
                  "hidden-axis message are shown whole, the 2000-character one ends in '…'; text() / tooltip "
                  "keep the full text",
                  d and all(x.get('fits') and x.get('full') for x in sm.values())
                  and not sm['movements'].get('elided') and not sm['movements_6'].get('elided')
                  and not sm['hidden_axis'].get('elided')
                  and sm['huge'].get('elided') and sm['huge'].get('lines') == 3, str(sm))
            check(f"A {key}: a short message again: one line, the label one line high again, the window's "
                  "minimum width as before",
                  d and sm['short'].get('lines') == 1 and not sm['short'].get('elided')
                  and sm['short'].get('height', 99) < sm['huge'].get('height', 0)
                  and sub['short'].get('min_w') == d['min_w'], str(sm['short']))
            check(f"A {key}: a log with a {len('very_long_file_name_') * 6 + 7}-character name: the selected-curve, "
                  "pause and ROI labels fit the left panel, which does not scroll sideways",
                  d and sub['long_name'].get('left_labels_fit') and sub['long_name'].get('hscroll') == 0
                  and d.get('left_labels_fit'), str(sub['long_name'].get('left_labels_fit')))
    tbl = w.logs_curves_table

    # 1. mouse wheel over unfocused spin boxes / combos
    wdgs = w.logs_root.findChildren(QAbstractSpinBox) + w.logs_root.findChildren(QComboBox)
    wrong = [type(x).__name__ for x in wdgs if x.focusPolicy() != Qt.StrongFocus]
    check("1 every spin box / combo of the tab (table cells included) has StrongFocus",
          wdgs and not wrong and len(w.logs_toff_spins) == 4 and w.logs_pause_source_combo in wdgs,
          f"{len(wdgs)} widgets, wrong: {wrong}")
    w.activateWindow()
    w.logs_btn_add.setFocus()
    APP.processEvents()
    # real (spontaneous) wheel events: the ignored event must reach the left panel's scroll area
    # and scroll it (with a synthetic sendEvent only 'not accepted' can be checked)
    vmax = w.logs_left_scroll.verticalScrollBar().maximum()

    def passed_on(scrolled, accepted):
        return scrolled if WHEEL_SPONTANEOUS else not accepted
    roi0 = w.logs_spin_roi0.value()
    res = [wheel_scrolls(w, w.logs_spin_roi0), wheel_scrolls(w, w.logs_spin_roi0.findChild(QLineEdit), -120)]
    check("1 wheel over the unfocused ROI start (box and its text field): ROI unchanged, the left panel scrolls",
          vmax > 0 and st.roi is None and w.logs_spin_roi0.value() == roi0 and all(passed_on(*r) for r in res),
          f"roi {st.roi}, (scrolled, accepted) {res}, scroll max {vmax}, spontaneous {WHEEL_SPONTANEOUS}")
    toff0 = st.entries[i_case].curve.time_offset
    pd0 = list(st.entries[i_ref].curve.meta.get('pause_durations') or [])
    res = [wheel_scrolls(w, x) for x in (w.logs_toff_spins[i_case], w.logs_voff_spins[i_case],
                                         w.logs_toff_spins[i_case].findChild(QLineEdit))]
    check("1 wheel over unfocused table spin boxes (t / v offset): nothing changes, a panel scrolls",
          st.entries[i_case].curve.time_offset == toff0 and not st.entries[i_case].curve.value_offsets
          and list(st.entries[i_ref].curve.meta.get('pause_durations') or []) == pd0
          and all(passed_on(*r) for r in res), str(res))
    axis0, ref0, kind0 = st.analysis_axis, st.ref_uid, w.logs_combo_peakkind.currentIndex()
    res = [wheel_scrolls(w, c, d) for c in (w.logs_axis_combo, w.logs_ref_combo, w.logs_combo_peakkind)
           for d in (120, -120)]
    rc0 = w.logs_results_combo.currentIndex()
    for d in (120, -120):
        wheel(w.logs_results_combo, d)
    check("1 wheel over unfocused combos: analysis axis, reference curve, peak kind, results view unchanged; "
          "the left panel scrolls",
          st.analysis_axis == axis0 and st.ref_uid == ref0 and w.logs_combo_peakkind.currentIndex() == kind0
          and w.logs_results_combo.currentIndex() == rc0 and all(passed_on(*r) for r in res), str(res))
    w.logs_spin_band_k.setFocus()
    APP.processEvents()
    if w.logs_spin_band_k.hasFocus():
        k0 = w.logs_spin_band_k.value()
        wheel(w.logs_spin_band_k)
        check("1 wheel over a focused spin box still steps it", abs(w.logs_spin_band_k.value() - (k0 + 0.5)) < 1e-9
              and abs(st.band_k - (k0 + 0.5)) < 1e-9, f"{k0} -> {w.logs_spin_band_k.value()}")
    else:
        print("INFO: no keyboard focus offscreen: focused-wheel check skipped")
    w.logs_btn_add.setFocus()
    tl.logs_set_display(w, band_k=2.0)

    # 4. results table keeps the stored row order
    tl.logs_compare(w)
    rtbl = w.logs_results_table
    names = [r[0] for r in st.results['Compare'][1]]
    tab = [rtbl.item(r, 0).text() for r in range(rtbl.rowCount())]
    check("4 results table shows the stored row order (= exported CSV), no sort column",
          tab == names and names != sorted(names, reverse=True) and rtbl.horizontalHeader().sortIndicatorSection() == -1,
          str(tab))
    rtbl.sortByColumn(0, Qt.DescendingOrder)          # the user clicks a header
    sorted_tab = [rtbl.item(r, 0).text() for r in range(rtbl.rowCount())]
    tl.logs_compare(w)
    tab2 = [rtbl.item(r, 0).text() for r in range(rtbl.rowCount())]
    check("4 header click still sorts; the next fill is again in the stored order",
          sorted_tab == sorted(names, reverse=True) and tab2 == names and rtbl.isSortingEnabled())

    # 5. difference panel y-range follows the shown time range
    tl.logs_set_display(w, show_diff=True)
    w.logs_canvas.draw()
    full = w.logs_ax_diff.get_ylim()
    check("5 difference y-range fitted to the shown range", np.allclose(full, expected_diff_ylim(w), atol=1e-9),
          f"{full}")
    tl.logs_set_roi(w, 5.0, 25.0)
    tl.logs_zoom_to_roi(w)
    roi_lim = w.logs_ax_diff.get_ylim()
    check("5 zoom to ROI refits the difference y-range to the ROI",
          np.allclose(roi_lim, expected_diff_ylim(w), atol=1e-9) and not np.allclose(roi_lim, full),
          f"all {full[0]:+.3f}..{full[1]:+.3f} -> ROI {roi_lim[0]:+.3f}..{roi_lim[1]:+.3f}")
    w.logs_ax.set_xlim(40.0, 60.0)                 # what the toolbar zoom / pan does on the main axes
    check("5 zoom / pan of the main axes refits it (xlim_changed callback)",
          np.allclose(w.logs_ax_diff.get_ylim(), expected_diff_ylim(w), atol=1e-9) and not st.in_xlim_cb)
    w.logs_ax_diff.set_xlim(60.0, 80.0)            # zoom on the difference panel itself
    check("5 zoom of the difference axes refits it too",
          np.allclose(w.logs_ax_diff.get_ylim(), expected_diff_ylim(w), atol=1e-9)
          and np.allclose(w.logs_ax.get_xlim(), (60.0, 80.0)))
    tl.logs_zoom_all(w)
    check("5 Show all: whole range again", np.allclose(w.logs_ax_diff.get_ylim(), expected_diff_ylim(w), atol=1e-9)
          and np.allclose(w.logs_ax_diff.get_ylim(), full, atol=1e-9))
    tl.logs_clear_roi(w)

    # 3. hidden analysis axis: no snapping to it, its peaks / points are not drawn
    def markers():
        return [ln for ln in w.logs_ax.get_lines() if ln.get_marker() in ('^', 'v', 'o')]
    tl.logs_clear_points(w)
    tl.logs_find_peaks(w, prominence=0.0, min_distance=0.5, kind='both')
    tl.logs_add_point(w, i_case, 30.0)
    w.logs_canvas.draw()
    n_mk = len(markers())
    tl.logs_set_axis_enabled(w, 'LAT', True)
    tl.logs_set_axis_enabled(w, 'SI', False)
    w.logs_canvas.draw()
    check("3 analysis axis hidden: its peak and point markers are not drawn", n_mk >= 1 and not markers(),
          f"{n_mk} markers with SI shown")
    n0, n_pts = len(FakeBox.calls), len(st.points)
    r = tl.logs_pick_point(w, 30.0, 50.0)
    wn = warnings_since(n0)
    check("3 logs_pick_point with the analysis axis hidden: refused with a clear message",
          r is None and len(st.points) == n_pts and len(wn) == 1 and 'hidden' in wn[0][2]
          and 'hidden' in w.logs_summary.text(), wn[0][2] if wn else '')
    tl.logs_set_pick_mode(w, 'points')
    check("3 points mode says the axis is hidden", 'hidden' in w.logs_summary.text())
    x_px, y_px = w.logs_ax.transData.transform((30.0, float(np.mean(w.logs_ax.get_ylim()))))
    n0 = len(FakeBox.calls)
    mouse(w, 'button_press_event', x_px, y_px)
    check("3 click with the axis hidden: no point, status message only (no box per click)",
          len(st.points) == n_pts and not warnings_since(n0) and 'hidden' in w.logs_summary.text())
    tl.logs_set_pick_mode(w, None)
    tl.logs_set_axis_enabled(w, 'SI', True)
    tl.logs_set_axis_enabled(w, 'LAT', False)
    w.logs_canvas.draw()
    check("3 axis shown again: markers drawn again", len(markers()) == n_mk)
    tl.logs_clear_peaks(w)

    # 6. legend clicks in points mode
    tl.logs_set_pick_mode(w, 'points')
    w.logs_canvas.draw()
    bb = w.logs_ax.get_legend().get_window_extent()
    n_pts = len(st.points)
    mouse(w, 'button_press_event', (bb.x0 + bb.x1) / 2.0, (bb.y0 + bb.y1) / 2.0)
    mouse(w, 'button_release_event', (bb.x0 + bb.x1) / 2.0, (bb.y0 + bb.y1) / 2.0)
    check("6 click / drag on the legend in points mode: no point added", len(st.points) == n_pts)
    cc = st.entries[i_case].curve
    # away from the point at 30 s: a press on an existing point drags it (round 5)
    x_px, y_px = w.logs_ax.transData.transform((45.0, float(np.interp(45.0, cc.times(), cc.values('SI')))))
    mouse(w, 'button_press_event', x_px, y_px)
    check("6 a click on a curve outside the legend still adds a point", len(st.points) == n_pts + 1)
    tl.logs_set_pick_mode(w, None)

    # 2. points / curves selection after deleting or removing
    tl.logs_clear_points(w)
    i_c1 = idx_of(w, 'log_14_05')
    for idx, t_ in ((i_c1, 20.0), (i_case, 30.0), (i_case, 40.0), (i_case, 50.0)):
        tl.logs_add_point(w, idx, t_)
    ids = [p['id'] for p in st.points]
    pt = w.logs_points_table
    check("2 points carry unique ids", len(set(ids)) == 4 and None not in ids)
    pt.selectRow(2)
    tl._on_delete_points_clicked(w)
    check("2 delete the selected point: that point goes and nothing stays selected",
          [p['id'] for p in st.points] == [ids[0], ids[1], ids[3]] and not pt.selectedIndexes()
          and tl._selected_point_rows(w) == [])
    n0 = len(FakeBox.calls)
    tl._on_delete_points_clicked(w)
    check("2 a second Delete press: warning, no other point deleted", len(st.points) == 3
          and len(warnings_since(n0)) == 1)
    pt.selectRow(1)                                 # point id[1]
    sel_name = st.entries[st.selected].curve.name if st.selected >= 0 else None
    tl.logs_remove_curves(w, [i_c1])                # removes point id[0]: the rows shift up
    check("2 removing a curve: the point selection follows the point, not the row number",
          [p['id'] for p in st.points] == [ids[1], ids[3]] and tl._selected_point_ids(w) == {ids[1]}
          and tl._selected_point_rows(w) == [0])
    check("2 removing another curve keeps the selected curve",
          sel_name is not None and st.selected >= 0 and st.entries[st.selected].curve.name == sel_name, str(sel_name))
    tl.logs_remove_curves(w)                        # the selected curve
    n_e = len(st.entries)
    check("2 removing the selected curve clears the selection", st.selected == -1 and not tbl.selectedIndexes()
          and 'Selected: –' in w.logs_selected_label.text())
    n0 = len(FakeBox.calls)
    tl.logs_remove_curves(w)
    check("2 a second Remove press removes nothing (warning)", len(st.entries) == n_e and len(warnings_since(n0)) == 1)
    tl.logs_add_files(w, CHECK_LOGS)
    tl.logs_clear_points(w)
    i_case, i_ref = idx_of(w, 'case_02'), idx_of(w, 'curve2')

    # 12. movements spanning a connection gap (in_gap from the core; .get() also works without it)
    orig_dm = la.detect_movements

    def fake_dm(curve, axis, **kw):
        out = [dict(m) for m in orig_dm(curve, axis, **kw)]
        for m in out:
            m.pop('in_gap', None)                   # as before the core change
        if 'case_02' in curve.name and len(out) >= 2:
            out[1]['in_gap'], out[1]['complete'] = True, False
        return out
    la.detect_movements = fake_dm
    try:
        tl.logs_detect_movements(w, threshold=0.02, settle_time=0.5)
    finally:
        la.detect_movements = orig_dm
    hdr, rows = st.results['Movements']
    case_rows = [r for r in rows if 'case_02' in r[0]]
    ig, cp = hdr.index('In gap'), hdr.index('Complete')
    check("12 Movements view has 'In gap' and 'Note' columns", hdr[-2:] == ['In gap', 'Note'], str(hdr[-3:]))
    check("12 movement spanning a gap: In gap yes, Complete no, note says so; the others (no key): no",
          len(case_rows) >= 2 and case_rows[1][ig] is True and case_rows[1][cp] is False and 'gap' in case_rows[1][-1]
          and all(r[ig] is False for r in rows if r is not case_rows[1]), case_rows[1][-1] if len(case_rows) > 1 else '')
    ri = rows.index(case_rows[1])
    check("12 results table shows it", rtbl.item(ri, ig).text() == 'yes' and 'gap' in rtbl.item(ri, len(hdr) - 1).text()
          and 'span a connection gap' in w.logs_summary.text(), w.logs_summary.text()[-80:])
    w.logs_canvas.draw()
    color = mcolors.to_rgb(st.entries[i_case].color)
    lanes = [c for c in st.artists if c.__class__.__name__ == 'PolyCollection' and c.get_paths()
             and max(float(p.vertices[:, 1].max()) for p in c.get_paths()) < 0.3
             and np.allclose(c.get_facecolor()[0][:3], color)]
    ok = False
    if lanes:
        fc, ls = lanes[0].get_facecolor(), lanes[0].get_linestyle()
        ok = len(fc) >= 2 and abs(fc[1][3] - 0.30) < 1e-6 and abs(fc[0][3] - 0.85) < 1e-6 and ls[1][1] is not None \
            and ls[0][1] is None
    check("12 lane: the in-gap movement is drawn faint with a dashed outline, in the same lane", len(lanes) == 1 and ok)
    # the real core (once detect_movements sets in_gap): a ramp that continues across a gap
    gap_rows = [(t_, 25.0 if t_ < 2.5 else min(26.0, 25.0 + (t_ - 2.5) * 2.0)) for t_ in np.arange(0.05, 3.0, 0.08)]
    lines = [f"{a:.3f},50.000,{b:.3f},35.000,0.000,0.000,0.000,0" for a, b in gap_rows]
    lines += ["# Gap: connection lost at 3.000 s", "# Gap end: reconnected at 6.000 s"]
    lines += [f"{a:.3f},50.000,30.000,35.000,0.000,0.000,0.000,0" for a in np.arange(6.03, 12.0, 0.08)]
    gap_log = os.path.join(TMP, "log_review_gap.csv")
    write_log(gap_log, lines, None)
    tl.logs_add_files(w, [gap_log])
    gi = idx_of(w, 'log_review_gap')
    core = la.detect_movements(st.entries[gi].curve, 'SI', threshold=0.02, settle_time=0.5)
    if any('in_gap' in m for m in core):
        tl.logs_detect_movements(w, threshold=0.02, settle_time=0.5)
        hdr, rows = st.results['Movements']
        g_rows = [r for r in rows if r[0] == st.entries[gi].curve.name]
        check("12 real core: the movement across the gap is flagged In gap in the view",
              any(r[hdr.index('In gap')] is True and 'gap' in r[-1] for r in g_rows), str([r[-3:] for r in g_rows]))
    else:
        print("INFO: core detect_movements has no 'in_gap' yet: real-core gap check skipped "
              f"({len(core)} movement(s) found)")
    tl.logs_remove_curves(w, [gi])

    # 8. results of removed curves / of a removed reference
    tl.logs_select_curve(w, i_case)
    # (no pause estimate any more: a log without logged waits is shown as recorded)
    tl.logs_auto_align(w, all_curves=True)
    tl.logs_compare(w)
    tl.logs_detect_movements(w, threshold=0.02, settle_time=0.5)
    tl.logs_find_peaks(w, prominence=0.0, min_distance=0.5, kind='both')

    def views_with(name):
        return sorted(n for n, (h, rr) in st.results.items() if 'Curve' in h and any(r[h.index('Curve')] == name for r in rr))

    def combo_items():
        c = w.logs_results_combo
        return [c.itemText(i) for i in range(c.count())]
    gone = st.entries[idx_of(w, 'log_14_05')].curve.name
    had = views_with(gone)
    n_other = {n: sum(1 for r in rr if r[0] != gone) for n, (h, rr) in st.results.items() if 'Curve' in h}
    tl.logs_remove_curves(w, [idx_of(w, 'log_14_05')])
    kept = {n: len(rr) for n, (h, rr) in st.results.items() if 'Curve' in h}
    check("8 removing a log drops its rows from every results view (others kept)",
          len(had) >= 4 and not views_with(gone) and all(kept.get(n, 0) == k for n, k in n_other.items() if k)
          and set(combo_items()) == set(st.results), f"had rows in {had}")
    cur = st.current_results
    check("8 combo and table refreshed", cur in st.results and w.logs_results_combo.currentText() == cur
          and rtbl.rowCount() == len(st.results[cur][1]))
    check("8 Pauses / Compare / Alignment kept while their reference is loaded",
          all(n in st.results for n in ('Pauses', 'Compare', 'Alignment')))
    tl.logs_remove_curves(w, [idx_of(w, 'curve2')])
    cur = st.current_results
    check("8 removing the reference drops Alignment, Compare and Pauses and its own rows",
          not any(n in st.results for n in ('Alignment', 'Compare', 'Pauses')) and not views_with('curve2')
          and set(combo_items()) == set(st.results) and set(st.results_ref) <= set(st.results)
          and (cur is None or rtbl.rowCount() == len(st.results[cur][1])), str(combo_items()))
    tl.logs_add_reference(w, CURVE2)
    i_case, i_ref = idx_of(w, 'case_02'), idx_of(w, 'curve2')

    # 9. warnings of busy actions open with the normal cursor
    n0, c0 = len(FakeBox.calls), len(FakeBox.cursors)
    tl.logs_add_files(w, [os.path.join(TMP, "missing_review.csv")])
    check("9 'could not be loaded' warning opens after the wait cursor is restored",
          len(warnings_since(n0)) == 1 and FakeBox.cursors[c0:] == [None] and QApplication.overrideCursor() is None,
          str(FakeBox.cursors[c0:]))
    n0, c0 = len(FakeBox.calls), len(FakeBox.cursors)
    tl.logs_auto_align(w, all_curves=False, index=99)
    check("9 error of a busy action: warning with the normal cursor", len(warnings_since(n0)) == 1
          and FakeBox.cursors[c0:] == [None] and not st.pending_warnings and st.busy_depth == 0)

    # 10. dialogs reopen in the last folder used; 11. export names are not 'log_*'
    nc = os.path.normcase
    phoper = tempfile.mkdtemp(prefix="phoper_", dir=TMP)
    w.PhOperFolder = QLineEdit(phoper)
    last = st.last_folder
    st.last_folder = None
    check("10 nothing used yet: the Status tab's log folder", nc(tl._default_folder(w)) == nc(phoper))
    st.last_folder = last
    tl.logs_add_files(w, [NOV3_LOG])
    check("10 after loading: the folder of that file, not PhOperFolder",
          nc(tl._default_folder(w)) == nc(os.path.dirname(NOV3_LOG)), tl._default_folder(w))
    tl.logs_export_results(w, os.path.join(TMP, "review_results.csv"))
    check("10 after an export: its folder", nc(tl._default_folder(w)) == nc(TMP))
    tl.logs_save_figure(w, os.path.join(phoper, "fig.png"))
    check("10 after saving the figure: its folder", nc(tl._default_folder(w)) == nc(phoper))
    tl.logs_export_aligned(w, os.path.join(TMP, "review_aligned.csv"))
    captured = []

    class FakeDialog:
        @staticmethod
        def getOpenFileNames(parent, title, folder, filt):
            captured.append(folder)
            return [], ''

        @staticmethod
        def getOpenFileName(parent, title, folder, filt):
            captured.append(folder)
            return '', ''

        @staticmethod
        def getSaveFileName(parent, title, path, filt):
            captured.append(path)
            return '', ''
    orig_dlg = tl.QFileDialog
    tl.QFileDialog = FakeDialog
    try:
        tl._on_add_logs_clicked(w)
        tl._on_add_ref_clicked(w)
        tl._on_export_results_clicked(w)
        tl._on_export_aligned_clicked(w)
        tl._on_save_fig_clicked(w)
    finally:
        tl.QFileDialog = orig_dlg
    check("10 every file dialog opens in the last folder used", len(captured) == 5 and all(
        nc(c if i < 2 else os.path.dirname(c)) == nc(TMP) for i, c in enumerate(captured)), str(captured[:2]))
    sug = [os.path.basename(c) for c in captured[2:]]
    check("11 suggested export names do not start with 'log_'", len(sug) == 3
          and not any(n.lower().startswith('log_') for n in sug), str(sug))
    try:
        from fcn_plan.fcn_import import is_trace_log_file
    except Exception as e:
        is_trace_log_file = None
        print(f"INFO: fcn_plan.fcn_import not importable ({e}): importer check skipped")
    if is_trace_log_file is not None and len(sug) == 3:
        p_res, p_al = os.path.join(TMP, sug[0]), os.path.join(TMP, sug[1])
        tl.logs_export_results(w, p_res)
        tl.logs_export_aligned(w, p_al)
        old = os.path.join(TMP, "log_aligned_SI.csv")
        shutil.copyfile(p_al, old)
        # the old name 'log_aligned_SI.csv' was taken for a log (log_ + Time_s); the header of the
        # aligned export ('time [s]', '<axis>: <curve> [<unit>]') is not, whatever the file name
        check("11 the Planning importer does not take the exports for TRACE logs, not even named log_*",
              os.path.isfile(p_res) and not is_trace_log_file(p_res) and not is_trace_log_file(p_al)
              and not is_trace_log_file(old))

    # 7. long logs: capped drawing grid, decimated fills, debounced spin box redraws
    tl.logs_clear_all(w)
    rng = np.random.default_rng(3)
    long_paths = []
    for k in range(2):
        t_ = np.cumsum(rng.uniform(0.06, 0.10, 12000))
        held = np.floor(t_ / 0.2 + 1e-9) * 0.2
        p = os.path.join(TMP, f"log_review_long_{k}.csv")
        write_log(p, t_, 25.0 + 5.0 * np.sin(2.0 * np.pi * held / 4.0))
        long_paths.append(p)
    tl.logs_add_files(w, long_paths)
    tl.logs_set_reference(w, 0)
    t0 = time.perf_counter()
    tl.logs_set_display(w, show_band=True, show_envelope=True, show_diff=True)
    w.logs_canvas.draw()
    t_draw = time.perf_counter() - t0
    grid = st.band_fills[0][0] if st.band_fills else np.empty(0)
    dlines = [ln for ln in w.logs_ax_diff.get_lines() if ln.get_linewidth() > 1.0]
    span = float(grid[-1] - grid[0]) if grid.size else 0.0
    check("7 drawing grid of band / envelope / difference capped", 0.9 * tl._DRAW_MAX_POINTS < grid.size
          <= tl._DRAW_MAX_POINTS + 2 and dlines and all(len(ln.get_xdata()) <= tl._DRAW_MAX_POINTS + 2 for ln in dlines),
          f"{span:.0f} s span: {grid.size} points (dt {span / max(grid.size - 1, 1):.3f} s), "
          f"diff {[len(ln.get_xdata()) for ln in dlines]}")
    cmp_ = tl.logs_compare(w)
    check("7 statistics keep the fine grid (dt 0.01 s)", cmp_ is not None and cmp_[0]['n'] > 80000,
          str(cmp_[0]['n']) if cmp_ else '')
    verts = [len(p.vertices) for a in st.band_artists for p in a.get_paths()]
    x0, x1 = sorted(w.logs_ax.get_xlim())
    t_, lo_, hi_, _ = st.band_fills[0]
    i0 = max(0, int(np.searchsorted(t_, x0)) - 1)
    i1 = min(t_.size, int(np.searchsorted(t_, x1, side='right')) + 1)
    vy = np.concatenate([p.vertices[:, 1] for p in st.band_artists[0].get_paths()])
    check("7 fills decimated to the plot width, covering the same values",
          len(st.band_artists) == 2 and max(verts) < grid.size and abs(vy.min() - np.nanmin(lo_[i0:i1])) < 1e-9
          and abs(vy.max() - np.nanmax(hi_[i0:i1])) < 1e-9, f"{verts} vertices vs {2 * grid.size} undecimated")
    w.logs_ax.set_xlim(100.0, 110.0)
    vx = np.concatenate([p.vertices[:, 0] for a in st.band_artists for p in a.get_paths()])
    dtg = span / max(grid.size - 1, 1)
    check("7 zoom: fills redrawn for the new range at the grid resolution",
          st.band_view[:2] == (100.0, 110.0) and vx.min() >= 100.0 - 1.01 * dtg and vx.max() <= 110.0 + 1.01 * dtg,
          f"{vx.min():.3f}..{vx.max():.3f}")
    tl.logs_zoom_all(w)
    timer = w.logs_redraw_timer

    def leg_txt():
        return " | ".join(t.get_text() for t in w.logs_ax.get_legend().get_texts())
    w.logs_canvas.draw()
    w.logs_spin_band_k.setValue(3.5)                # spin box slot: debounced
    check("7 spin box: state at once, redraw debounced", st.band_k == 3.5 and timer.isActive()
          and '2·STD' in leg_txt(), leg_txt()[:60])
    w.logs_spin_band_k.setValue(4.0)                # the next step restarts the timer
    wait_ms(tl._REDRAW_DELAY_MS + 200)
    check("7 one redraw after the last step", not timer.isActive() and st.pending_redraw is None and '4·STD' in leg_txt())
    lab = f"{st.entries[1].curve.name} · SI"
    xa = line_x0(w, lab)
    w.logs_toff_spins[1].setValue(5.0)
    check("7 time offset spin: offset at once, plot after the debounce", st.entries[1].curve.time_offset == 5.0
          and timer.isActive() and line_x0(w, lab) == xa)
    tl.logs_set_display(w, show_probe=True)        # a public call redraws at once (and absorbs the pending one)
    check("7 a public logs_* call redraws synchronously", not timer.isActive() and st.pending_redraw is None
          and abs(line_x0(w, lab) - (xa + 5.0)) < 1e-9)
    t0 = time.perf_counter()
    tl.logs_redraw(w)
    w.logs_canvas.draw()
    print(f"INFO: 2 logs x 12000 rows with band + envelope + difference: first draw {t_draw:.2f} s, "
          f"redraw {time.perf_counter() - t0:.2f} s")
    tl.logs_clear_all(w)
    w.close()


# ---------------------------------------------------------------------------------------------
# Second review round (own window at 1600x900)
# ---------------------------------------------------------------------------------------------
def pan_drag(w, ax, steps=5, dx=-40, dy=12):
    """Toolbar pan drag on `ax` (pan mode must be on) from its centre; returns the pixel offsets."""
    bb = ax.bbox
    x0, y0 = bb.x0 + bb.width * 0.5, bb.y0 + bb.height * 0.5
    mouse(w, 'button_press_event', x0, y0)
    for k in range(1, steps + 1):
        mouse(w, 'motion_notify_event', x0 + dx * k, y0 + dy * k)
    mouse(w, 'button_release_event', x0 + dx * steps, y0 + dy * steps)


def review2_checks():
    """A status line / variable labels never widen the window, B difference panel after a pan /
    Back / Forward / zoom rectangle, C held spin arrows and the debounce, D aligned export vs the
    Planning importer (adversarial curve names) and read back, E pause labels outside the zoom vs
    constrained_layout, F gap flags of the newer core (start_in_gap / stop_in_gap)."""
    import warnings
    import matplotlib.text as mtext
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QLabel, QSizePolicy, QStyle, QStyleFactory, QStyleOptionSpinBox
    print("\n---- second review round ----")
    w = make_window()
    w.resize(1600, 900)
    tl.build_logs_tab(w)
    w.show()
    APP.processEvents()
    st = w.logs_state
    tl.logs_add_files(w, [CASE02] + CHECK_LOGS)
    tl.logs_add_reference(w, CURVE2)
    for _ in range(5):
        APP.processEvents()
    i_case, i_ref = idx_of(w, 'case_02'), idx_of(w, 'curve2')

    # ------------------------------------------------------------------ A. variable-text labels
    s = w.logs_summary
    labels = {'summary': s, 'selected': w.logs_selected_label, 'pause': w.logs_pause_label, 'roi': w.logs_roi_label}
    check("A every label with variable text (status, selected curve, pauses, ROI) is an _ElidedLabel with the "
          "Ignored horizontal policy", all(isinstance(x, tl._ElidedLabel)
                                           and x.sizePolicy().horizontalPolicy() == QSizePolicy.Ignored
                                           for x in labels.values()),
          str({k: type(x).__name__ for k, x in labels.items()}))
    in_toolbar = set(id(x) for x in w.logs_toolbar.findChildren(QLabel))
    fixed = [x for x in w.logs_root.findChildren(QLabel) if not isinstance(x, tl._ElidedLabel)
             and id(x) not in in_toolbar]
    fixed_txt = [x.text() for x in fixed]
    mw0, lw0 = w.minimumSizeHint().width(), w.logs_left_scroll.widget().minimumSizeHint().width()
    tl._set_summary(w, "Ready.")
    for _ in range(3):
        APP.processEvents()
    h1 = s.height()
    huge = "Exported to " + "C:\\a_folder_without_spaces" * 40 + " · " + "word " * 600
    tl._set_summary(w, huge)
    for _ in range(3):
        APP.processEvents()
    check("A a 4000-character status message does not raise the window's minimum width",
          w.minimumSizeHint().width() == mw0 and w.tab_logs.minimumSizeHint().width() <= mw0,
          f"{mw0} -> {w.minimumSizeHint().width()}")
    check("A it is shown over 3 lines that fit the label (3 lines high, not squeezed) and end in '…'; text() "
          "and the tooltip keep it whole",
          s.isElided() and s.shownText().count('\n') == 2 and s.shownText().endswith('…') and label_fits(s)
          and s.text() == huge and s.toolTip() == huge and st.summary == huge and s.height() > h1
          and s.height() >= s.sizeHint().height(),
          f"{s.shownText().count(chr(10)) + 1} lines, height {h1} -> {s.height()} (hint {s.sizeHint().height()})")
    w.resize(900, 900)                          # narrower: wrapped again for the new width
    APP.processEvents()
    fits_narrow = label_fits(s) and s.isElided()
    w.resize(1600, 900)
    APP.processEvents()
    tl._set_summary(w, "Ready.")
    APP.processEvents()
    check("A re-wrapped on resize; a short message: one line, not elided, one line high again",
          fits_narrow and s.shownText() == "Ready." and not s.isElided() and s.height() == h1, f"height {s.height()}")
    long_log = os.path.join(TMP, "log_" + "very_long_file_name_" * 6 + "end.csv")
    shutil.copyfile(CASE02, long_log)
    rc_w0 = w.logs_ref_combo.minimumSizeHint().width()
    tl.logs_add_files(w, [long_log])
    tl.logs_set_reference(w, len(st.entries) - 1)
    APP.processEvents()
    long_name = st.entries[-1].curve.name
    check("A a curve with a 127-character name: the selected and pause labels elide it, the reference combo and "
          "the left panel keep their minimum width (full name in the tooltips)",
          w.logs_selected_label.isElided() and label_fits(w.logs_selected_label) and long_name in
          w.logs_selected_label.text() and label_fits(w.logs_pause_label)
          and w.logs_ref_combo.minimumSizeHint().width() == rc_w0 and long_name in w.logs_ref_combo.toolTip()
          and w.logs_left_scroll.widget().minimumSizeHint().width() <= lw0,
          f"left min width {lw0} -> {w.logs_left_scroll.widget().minimumSizeHint().width()}, combo {rc_w0} -> "
          f"{w.logs_ref_combo.minimumSizeHint().width()}")
    tl.logs_remove_curves(w, [len(st.entries) - 1])
    tl.logs_set_reference(w, idx_of(w, 'curve2'))
    i_case, i_ref = idx_of(w, 'case_02'), idx_of(w, 'curve2')

    # ------------------------------------------------------------------ B. difference panel y-range
    tl.logs_select_curve(w, i_case)
    # (no pause estimate any more: a log without logged waits is shown as recorded)
    tl.logs_set_display(w, show_diff=True)
    w.logs_canvas.draw()
    tb, axd = w.logs_toolbar, w.logs_ax_diff

    def diff_ok():
        return np.allclose(axd.get_ylim(), expected_diff_ylim(w), atol=1e-9)

    def pump(n=3):
        for _ in range(n):
            APP.processEvents()
    x_home = w.logs_ax.get_xlim()
    tb.pan()
    pan_drag(w, axd)
    stale = not diff_ok()                       # matplotlib's drag_pan set the dragged y-range last
    pump()
    x_pan = w.logs_ax.get_xlim()
    check("B pan on the difference panel (toolbar): matplotlib leaves the dragged y-range, the tab refits it "
          "to the new time range once back in the event loop",
          stale and not np.allclose(x_pan, x_home) and diff_ok(), f"x {x_home} -> {x_pan}, y {axd.get_ylim()}")
    pan_drag(w, w.logs_ax, dx=30, dy=-10)
    pump()
    x_pan2 = w.logs_ax.get_xlim()
    check("B pan on the main axes: difference y-range refitted too", diff_ok() and not np.allclose(x_pan2, x_pan))
    tb.back()
    pump()
    ok_back = np.allclose(w.logs_ax.get_xlim(), x_pan) and diff_ok()
    tb.back()
    pump()
    check("B toolbar Back (twice): the earlier views, the difference y-range fitted to each",
          ok_back and np.allclose(w.logs_ax.get_xlim(), x_home) and diff_ok(), str(w.logs_ax.get_xlim()))
    tb.forward()
    pump()
    check("B toolbar Forward: the panned view again, y fitted", np.allclose(w.logs_ax.get_xlim(), x_pan) and diff_ok())
    tb.pan()                                    # pan mode off
    tb.zoom()                                   # zoom rectangle on the difference panel: x and y on purpose
    bb = axd.bbox                               # whole pixels: matplotlib's mouse events truncate to int
    xa, ya = int(bb.x0 + bb.width * 0.3), int(bb.y0 + bb.height * 0.3)
    xb, yb = int(bb.x0 + bb.width * 0.6), int(bb.y0 + bb.height * 0.85)
    inv = axd.transData.inverted()
    (ta, va), (tb_, vb) = inv.transform((xa, ya)), inv.transform((xb, yb))
    mouse(w, 'button_press_event', xa, ya)
    mouse(w, 'motion_notify_event', xb, yb)
    mouse(w, 'button_release_event', xb, yb)
    pump()
    check("B zoom rectangle on the difference panel: its time range and its y-range are kept",
          np.allclose(w.logs_ax.get_xlim(), (ta, tb_), atol=1e-6) and np.allclose(axd.get_ylim(), (va, vb), atol=1e-6),
          f"x {w.logs_ax.get_xlim()} y {axd.get_ylim()} vs ({va:.4f}, {vb:.4f})")
    tb.zoom()                                   # zoom mode off
    tl.logs_zoom_all(w)
    pump()
    check("B Show all: whole range, fitted", diff_ok() and not st.in_xlim_cb and not w.logs_diff_refit_timer.isActive())

    # ------------------------------------------------------------------ C. held spin arrows / debounce
    tl.logs_set_display(w, show_band=True, band_k=2.0)
    w.logs_canvas.draw()
    timer = w.logs_redraw_timer

    def leg_txt():
        return " | ".join(t.get_text() for t in w.logs_ax.get_legend().get_texts())
    rate = max(QStyleFactory.create('Fusion').styleHint(QStyle.SH_SpinBox_ClickAutoRepeatRate),
               APP.style().styleHint(QStyle.SH_SpinBox_ClickAutoRepeatRate))
    check("C the redraw debounce is longer than the spin arrows' auto-repeat (Fusion and this style)",
          tl._REDRAW_DELAY_MS > rate and timer.interval() == tl._REDRAW_DELAY_MS, f"{tl._REDRAW_DELAY_MS} ms vs {rate} ms")
    calls = []
    orig_draw = tl._do_redraw

    def counting(self_, *a, **k):
        calls.append(time.perf_counter())
        return orig_draw(self_, *a, **k)
    tl._do_redraw = counting
    try:
        sp = w.logs_spin_band_k
        w.logs_left_scroll.ensureWidgetVisible(sp)
        APP.processEvents()
        opt = QStyleOptionSpinBox()
        sp.initStyleOption(opt)
        up = sp.style().subControlRect(QStyle.CC_SpinBox, opt, QStyle.SC_SpinBoxUp, sp).center()
        k0 = sp.value()
        QTest.mousePress(sp, Qt.LeftButton, Qt.NoModifier, up)
        wait_ms(1300)
        n_held, k_held, pend = len(calls), sp.value(), st.pending_redraw is not None
        QTest.mouseRelease(sp, Qt.LeftButton, Qt.NoModifier, up)
        n_rel = len(calls)
        wait_ms(tl._REDRAW_DELAY_MS + 150)
        check("C holding a spin arrow 1.3 s: the value auto-repeats and the state follows, no redraw while held",
              k_held >= k0 + 3 * sp.singleStep() and abs(st.band_k - k_held) < 1e-9 and n_held == 0 and pend,
              f"k {k0} -> {k_held}, {n_held} redraws while held")
        check("C releasing the arrow redraws once, at once (no debounce wait)",
              n_rel == 1 and len(calls) == 1 and st.pending_redraw is None and not timer.isActive()
              and f"{k_held:g}·STD" in leg_txt() and st.held_spin is None, leg_txt()[:70])
        calls.clear()
        for k in range(4):                      # steps at the auto-repeat rate without a held button
            sp.setValue(3.0 + 0.5 * k)
            wait_ms(150)
        n_mid = len(calls)
        wait_ms(tl._REDRAW_DELAY_MS + 150)
        check("C steps 150 ms apart: no redraw between them, one after the last", n_mid == 0 and len(calls) == 1
              and '4.5·STD' in leg_txt(), f"{n_mid} between, {len(calls)} in all")
        calls.clear()
        sp.setValue(2.0)
        pend = st.pending_redraw is not None and timer.isActive()
        sp.editingFinished.emit()               # Enter / leaving the box
        check("C editingFinished draws a pending redraw at once", pend and len(calls) == 1
              and st.pending_redraw is None and not timer.isActive() and '2·STD' in leg_txt())
        calls.clear()
        st.held_spin = sp                       # a press whose release never arrived (button is up)
        sp.setValue(2.5)
        wait_ms(tl._REDRAW_DELAY_MS + 150)
        check("C a hold without a pressed button does not block the debounced redraw", len(calls) == 1
              and st.held_spin is None and st.pending_redraw is None)
        calls.clear()
        QTest.mousePress(sp, Qt.LeftButton, Qt.NoModifier, up)
        n_press = len(calls)
        tl.logs_set_display(w, band_k=3.0)      # public call while the arrow is held
        n_pub = len(calls)
        QTest.mouseRelease(sp, Qt.LeftButton, Qt.NoModifier, up)
        wait_ms(tl._REDRAW_DELAY_MS + 100)
        check("C a public logs_* call while an arrow is held still redraws synchronously (and absorbs the step)",
              n_press == 0 and n_pub == 1 and len(calls) == 1 and st.band_k == 3.0 and '3·STD' in leg_txt(),
              f"{n_press}/{n_pub}/{len(calls)}")
    finally:
        tl._do_redraw = orig_draw
        st.held_spin = None
    tl.logs_set_display(w, show_band=False, show_diff=False)

    # ------------------------------------------------------------------ E. pause labels outside the zoom
    tl.logs_add_point(w, i_case, 30.0)
    w.logs_canvas.draw()
    texts = [a for a in st.artists if isinstance(a, mtext.Text) and 'sensor_wait' in a.get_text()]
    anns = [a for a in st.artists if isinstance(a, mtext.Annotation)]
    check("E pause labels are clipped to the axes and kept out of constrained_layout (point numbers too)",
          texts and all(t.get_clip_on() and not t.get_in_layout() for t in texts) and anns
          and all(not a.get_in_layout() for a in anns), f"{len(texts)} labels, {len(anns)} numbers")
    t_pause = float(st.entries[i_ref].curve.meta['pauses'][0][1]) + st.entries[i_ref].curve.time_offset
    heights = []
    with warnings.catch_warnings(record=True) as wl:
        warnings.simplefilter('always')
        tl.logs_set_roi(w, 30.0, 40.0)
        tl.logs_zoom_to_roi(w)
        w.logs_canvas.draw()
        h_roi = w.logs_ax.get_position().height
        n_roi = sum('constrained_layout' in str(x.message) for x in wl)
        for diff in (False, True):
            tl.logs_set_display(w, show_diff=diff)
            wins = [(x0, x0 + width) for x0 in np.linspace(-30.0, 120.0, 9) for width in (0.5, 12.0)]
            wins += [(t_pause + 0.05, t_pause + 3.0), (t_pause - 3.0, t_pause - 0.05), (t_pause - 0.5, t_pause + 0.5)]
            for a, b in wins:
                w.logs_ax.set_xlim(a, b)
                w.logs_canvas.draw()
                heights.append(w.logs_ax.get_position().height)
    cl = [str(x.message) for x in wl if 'constrained_layout' in str(x.message)]
    check(f"E Zoom to ROI 30..40 s (pause label at {t_pause:.2f} s outside): no constrained_layout warning",
          n_roi == 0 and h_roi > 0.5, f"{n_roi} warnings, axes height {h_roi:.3f}")
    check(f"E {len(heights)} zoom windows across and past the data, around the pause, with and without the "
          "difference panel: no warning, the plot never collapses", not cl and min(heights) > 0.3,
          f"{len(cl)} warnings, axes height {min(heights):.3f}..{max(heights):.3f}")
    tl.logs_clear_roi(w)
    tl.logs_clear_points(w)
    tl.logs_zoom_all(w)

    # ------------------------------------------------------------------ F. gap flags of the newer core
    orig_dm = la.detect_movements

    def fake_dm(curve, axis, **kw):
        out = [dict(m) for m in orig_dm(curve, axis, **kw)]
        for m in out:
            for key in ('in_gap', 'start_in_gap', 'stop_in_gap'):
                m.pop(key, None)
        if 'case_02' in curve.name and len(out) >= 3:
            out[0]['start_in_gap'] = True                            # no 'in_gap' key: still a gap
            out[1].update(in_gap=True, stop_in_gap=True, complete=False)
            out[2].update(in_gap=True, start_in_gap=True, stop_in_gap=True)
        return out
    la.detect_movements = fake_dm
    try:
        tl.logs_detect_movements(w, threshold=0.02, settle_time=0.5)
    finally:
        la.detect_movements = orig_dm
    hdr, rows = st.results['Movements']
    ig = hdr.index('In gap')
    case_rows = [r for r in rows if 'case_02' in r[0]]
    notes = [r[-1] for r in case_rows]
    check("F start_in_gap / stop_in_gap (read with .get): In gap yes, the note says which time is uncertain",
          len(case_rows) >= 3 and all(r[ig] is True for r in case_rows[:3]) and 'starts in a connection gap' in notes[0]
          and 'stops in a connection gap' in notes[1] and 'incomplete' in notes[1]
          and 'starts and stops' in notes[2], str(notes[:3]))
    mvc = st.movements[st.entries[i_case].uid]
    check("F flags stored per movement; curves without any gap key: In gap no",
          mvc['start_in_gap'][:3] == [True, False, True] and mvc['stop_in_gap'][:3] == [False, True, True]
          and mvc['in_gap'][:3] == [True, True, True] and all(r[ig] is False for r in rows if 'case_02' not in r[0]))
    tl.logs_clear_movements(w)

    # ------------------------------------------------------------------ fixed labels stay fixed
    check("A every other QLabel of the tab (outside the plot toolbar) kept its fixed text through the workflow",
          [x.text() for x in fixed] == fixed_txt and len(fixed) >= 10, f"{len(fixed)} labels")

    # ------------------------------------------------------------------ D. aligned export vs the importer
    try:
        from fcn_plan.fcn_import import is_trace_log_file
    except Exception as e:
        is_trace_log_file = None
        print(f"INFO: fcn_plan.fcn_import not importable ({e}): importer checks skipped")
    tl.logs_clear_all(w)
    adv = tempfile.mkdtemp(prefix="adv_", dir=TMP)
    tt = np.arange(0.0, 20.0, 0.1)
    names = ["x_sensor_probe", "y_mm", "pos_z", "a,t,b", "c;time_s", "w_deg", "Time_s", "t", "probe", "Pos_SI_mm"]
    for n in names:
        write_log(os.path.join(adv, n + ".csv"), tt, 25.0 + np.sin(tt))
    tl.logs_add_files(w, [os.path.join(adv, n + ".csv") for n in names])
    tl.logs_add_reference(w, CURVE2, name='ref "q"\tpos_x_mm\n,t,sensor')
    loaded = [e.curve.name for e in st.entries]
    taken = []
    n_exp = 0
    for k in range(len(st.entries)):
        for j in range(k + 1, len(st.entries)):
            for q, e in enumerate(st.entries):
                e.visible = q in (k, j)
            p = os.path.join(adv, f"aligned_{k}_{j}.csv")
            tl.logs_export_aligned(w, p)
            n_exp += 1
            p_log = os.path.join(adv, f"log_aligned_{k}_{j}.csv")
            shutil.copyfile(p, p_log)
            if is_trace_log_file is not None and (is_trace_log_file(p) or is_trace_log_file(p_log)):
                taken.append((loaded[k], loaded[j]))
    for e in st.entries:
        e.visible = True
    p_all = os.path.join(adv, "aligned_all.csv")
    tl.logs_export_aligned(w, p_all)
    with open(p_all, encoding='utf-8') as f:            # v2 style: '#' notes, then ';' columns
        header = next(csv.reader((ln for ln in f if not ln.startswith('#')), delimiter=';'))
    if is_trace_log_file is not None:
        check(f"D {n_exp} pair exports + the all-curve export with adversarial curve names (probe / sensor / _mm / "
              "pos_ / time_s / t / separators / quotes / newline), also copied to log_* names: none is taken for a "
              "TRACE log by the Planning importer",
              len(loaded) == 11 and not taken and not is_trace_log_file(p_all), str(taken[:3]))
    exp_cols = ['time [s]'] + [f"SI: {n} [mm]" for n in ("x_sensor_probe", "y_mm", "pos_z", "a t b", "c time-s",
                                                           "w_deg", "Time-s", "t", "probe", "Pos_SI_mm",
                                                           'ref q pos_x_mm t sensor')]
    df = pd.read_csv(p_all, sep=';', decimal=',', comment='#')
    check("D aligned export header: 'time [s]' + '<axis>: <curve> [<unit>]' (separators / quotes as spaces, "
          "'time_s' as 'time-s'), one column per curve, pandas reads it back (';', decimal comma)",
          header == exp_cols and list(df.columns) == exp_cols and len(df) > 100, str(header[:4]))
    n0 = len(FakeBox.calls)
    back = tl.logs_add_files(w, [p_all])
    wn = warnings_since(n0)
    if back:
        c = back[0]
        units = c.meta.get('units') if isinstance(c.meta.get('units'), dict) else {}
        # the axis names are the reader's: the exported column names, or (newer reader) short names
        # with the unit in meta['units']
        check("D the tab reads its own aligned export back: one curve with one axis per exported column",
              len(c.data) == len(exp_cols) - 1 and c.t.size == len(df)
              and (sorted(c.data) == sorted(exp_cols[1:]) or all(units.get(a, 'mm') == 'mm' for a in c.data)),
              str(sorted(c.data)[:3]))
    else:
        check("D reading the aligned export back fails with a clear message", wn and 'time' in wn[0][2].lower(),
              wn[0][2] if wn else '')
    tl.logs_clear_all(w)
    w.close()


# ---------------------------------------------------------------------------------------------
# Third review round (own window: 1600x900 for the toolbar, 1366x768 for the legend / read-back)
# ---------------------------------------------------------------------------------------------
def review3_checks():
    """A toolbar Home / Back / Forward refit the difference panel in every mode (Zoom checked, after a
    data change; call and button), B legend with 127-character curve names (elided, out of
    constrained_layout, 'best' inside the axes), C the aligned export read back (axis checkboxes /
    combo elided, no sideways scroll, per-curve units of meta['units']), D no constrained_layout
    warning and the window never widens."""
    import warnings
    from PySide6.QtWidgets import QComboBox
    print("\n---- third review round ----")
    w = make_window()
    w.resize(1600, 900)
    tl.build_logs_tab(w)
    w.show()
    APP.processEvents()
    st = w.logs_state

    def pump(n=5):
        for _ in range(n):
            APP.processEvents()
    tl.logs_add_files(w, [CASE02])
    tl.logs_add_reference(w, CURVE2)
    i_case = idx_of(w, 'case_02')
    tl.logs_select_curve(w, i_case)
    # (no pause estimate any more: a log without logged waits is shown as recorded)
    tl.logs_set_display(w, show_diff=True)
    w.logs_canvas.draw()
    pump()
    tb, ax, axd = w.logs_toolbar, w.logs_ax, w.logs_ax_diff

    def diff_ok():
        return np.allclose(axd.get_ylim(), expected_diff_ylim(w), atol=1e-9)

    # ------------------------------------------------------------------ A. Home / Back / Forward, Zoom on
    check("A the plot toolbar is still matplotlib's Qt navigation toolbar (subclass) and the canvas' toolbar",
          isinstance(tb, tl.NavigationToolbar) and w.logs_canvas.toolbar is tb)
    x_home, y_home_old = ax.get_xlim(), axd.get_ylim()
    tb.zoom()                                   # Zoom stays checked through this section
    bb = ax.bbox                                # zoom rectangle on the main axes: a second view
    xa, ya = int(bb.x0 + bb.width * 0.3), int(bb.y0 + bb.height * 0.8)
    xb, yb = int(bb.x0 + bb.width * 0.5), int(bb.y0 + bb.height * 0.2)
    mouse(w, 'button_press_event', xa, ya)
    mouse(w, 'motion_notify_event', xb, yb)
    mouse(w, 'button_release_event', xb, yb)
    pump()
    x_zoom, y_zoom_old = ax.get_xlim(), axd.get_ylim()
    ok_rect = diff_ok() and not np.allclose(x_zoom, x_home)
    tl.logs_set_time_offset(w, i_case, 0.6)     # data change: the stored views hold the old diff y-range
    pump()
    mode = tl._toolbar_mode(w)
    tb.back()
    pump()
    check("A Zoom checked, after a time offset: Back restores the home time range with the difference y-range "
          "fitted to the new data (not the stored one)",
          ok_rect and mode == 'zoom rect' and np.allclose(ax.get_xlim(), x_home) and diff_ok()
          and not np.allclose(axd.get_ylim(), y_home_old, atol=1e-6),
          f"mode {mode!r}, y {axd.get_ylim()} vs stored {y_home_old} / fit {expected_diff_ylim(w)}")
    tb.forward()
    pump()
    ok_fwd = np.allclose(ax.get_xlim(), x_zoom) and diff_ok() and not np.allclose(axd.get_ylim(), y_zoom_old, atol=1e-6)
    tb.home()
    pump()
    check("A Forward and Home (Zoom checked): refitted too", ok_fwd and np.allclose(ax.get_xlim(), x_home) and diff_ok(),
          f"y {axd.get_ylim()} vs {expected_diff_ylim(w)}")
    acts = getattr(tb, '_actions', {})
    if 'forward' in acts and 'back' in acts:
        tl.logs_set_time_offset(w, i_case, 1.2)
        pump()
        y_old = axd.get_ylim()
        acts['back'].trigger()                  # the toolbar buttons (Home pushed the home view: Back
        pump()                                  # goes to the zoomed view, Forward to home again)
        ok_btn = np.allclose(ax.get_xlim(), x_zoom) and diff_ok()
        acts['forward'].trigger()
        pump()
        check("A the toolbar's Back / Forward buttons (Zoom checked, after another offset): refitted",
              ok_btn and np.allclose(ax.get_xlim(), x_home) and diff_ok()
              and not np.allclose(axd.get_ylim(), y_home_old, atol=1e-6), f"y {y_old} -> {axd.get_ylim()}")
    tb.zoom()                                   # Zoom off
    tl.logs_set_display(w, show_diff=False)
    pump()
    tb.back()                                   # no difference panel: nothing to refit
    started = w.logs_diff_refit_timer.isActive()
    tb.home()
    pump()
    check("A Home / Back without the difference panel: no refit scheduled, the time range restored",
          not started and not w.logs_diff_refit_timer.isActive() and np.allclose(ax.get_xlim(), x_home))
    tl.logs_set_time_offset(w, i_case, 0.0)

    # ------------------------------------------------------------------ B. legend with long curve names
    w.resize(1366, 768)
    pump(10)
    w0 = w.width()
    w.logs_canvas.draw()
    ax_w0 = ax.get_position().width
    long_log = os.path.join(TMP, "log_" + "very_long_file_name_" * 6 + "end.csv")    # 127-character name
    shutil.copyfile(CASE02, long_log)
    with warnings.catch_warnings(record=True) as wl:
        warnings.simplefilter('always')
        tl.logs_add_files(w, [long_log, long_log])
        pump()
        w.logs_canvas.draw()
        leg = ax.get_legend()
        texts = [t.get_text() for t in leg.get_texts()]
        names = [e.curve.name for e in st.entries]
        long_names = [n for n in names if n.startswith('log_very_long')]
        r = w.logs_canvas.get_renderer()
        lb, ab = leg.get_window_extent(r), ax.get_window_extent(r)
        ax_w1 = ax.get_position().width
        cl_b = [str(x.message) for x in wl if 'constrained_layout' in str(x.message)]
    long_txt = [t for t in texts if 'very_long' in t]
    check("B two 127-character curve names: legend entries elided in the middle to <= "
          f"{tl._LEGEND_MAX_CHARS} characters, still distinct (the ' (2)' suffix stays)",
          len(long_names) == 2 and len(long_names[0]) == 127 and len(long_txt) == 2 and long_txt[0] != long_txt[1]
          and all('…' in t and len(t) <= tl._LEGEND_MAX_CHARS and t.endswith(' · SI') for t in long_txt)
          and long_txt[1].endswith('(2) · SI') and max(len(t) for t in texts) <= tl._LEGEND_MAX_CHARS, str(long_txt))
    check("B the full names stay in the plotted lines' labels and the curves table",
          all(f"{n} · SI" in lines_labels(w) for n in long_names)
          and [w.logs_curves_table.item(k, 2).text() for k in range(len(names))] == names)
    check("B legend out of constrained_layout, 'best' location inside the axes, draggable",
          not leg.get_in_layout() and getattr(leg, '_loc', None) == 0 and leg.get_draggable()
          and lb.x0 >= ab.x0 - 1 and lb.x1 <= ab.x1 + 1 and lb.width < ab.width,
          f"legend {lb.x0:.0f}..{lb.x1:.0f} axes {ab.x0:.0f}..{ab.x1:.0f}")
    check("B at 1366x768 the plot keeps its width (no constrained_layout warning, no collapse), window not wider",
          not cl_b and abs(ax_w1 - ax_w0) < 0.01 and ax_w1 > 0.7 and w.width() == w0,
          f"axes width {ax_w0:.3f} -> {ax_w1:.3f}, {len(cl_b)} warnings, window {w.width()}")
    old_max = tl._LEGEND_BEST_MAX_POINTS
    tl._LEGEND_BEST_MAX_POINTS = 10
    try:
        tl.logs_redraw(w)
        w.logs_canvas.draw()
        lg_h = ax.get_legend()
        heavy_flag = getattr(lg_h, '_logs_heavy', None)
        r_h = w.logs_canvas.get_renderer()
        lbh, abh = lg_h.get_window_extent(r_h), ax.get_window_extent(r_h)
        upper_right = abs(lbh.x1 - abh.x1) < 20 and abs(lbh.y1 - abh.y1) < 20
    finally:
        tl._LEGEND_BEST_MAX_POINTS = old_max
    tl.logs_redraw(w)
    check("B a plot with more points than _LEGEND_BEST_MAX_POINTS: the legend's 'best' skips the slow data test "
          "(only labels / the key) and puts it upper right first; a light plot tests the data again",
          heavy_flag is True and upper_right and getattr(ax.get_legend(), '_logs_heavy', None) is False
          and getattr(ax.get_legend(), '_loc', None) == 0, f"{heavy_flag} {lbh.bounds} {abh.bounds}")
    tl.logs_remove_curves(w, [k for k, e in enumerate(st.entries) if 'very_long' in e.curve.name])

    # ------------------------------------------------------------------ C. aligned export read back
    tl.logs_add_files(w, [CASE02, CASE02])
    tl.logs_set_reference(w, idx_of(w, 'curve2'))
    pump()
    lhs = w.logs_left_scroll.horizontalScrollBar()
    combo = w.logs_axis_combo
    hs0, lmin0, cmin0 = lhs.maximum(), w.logs_left_scroll.widget().minimumSizeHint().width(), \
        combo.minimumSizeHint().width()
    std_texts = {a: cb.text() for a, cb in w.logs_axis_checks.items()}
    p_al = os.path.join(TMP, "r3_aligned_SI.csv")
    tl.logs_export_aligned(w, p_al)
    # columns with long names whatever the reader makes of the export's '<axis>: <curve> [<unit>]'
    p_long = os.path.join(TMP, "log_long_columns.csv")
    long_cols = ["marker_displacement_superior_inferior_left_A", "marker_displacement_superior_inferior_right_B"]
    with open(p_long, 'w', encoding='utf-8') as f:
        f.write("Time_s," + ",".join(long_cols) + ",Probe\n")
        f.write("".join(f"{0.1 * k:.3f},{25 + math.sin(0.1 * k):.3f},{25 + math.cos(0.1 * k):.3f},0\n"
                        for k in range(300)))
    orig_read = la.read_trace_log

    def read_with_units(path):                  # the reader's optional per-curve units (meta['units'])
        c = orig_read(path)
        if os.path.basename(path) == os.path.basename(p_al):
            c.meta['units'] = {a: ('deg' if k == 0 else 'mm') for k, a in enumerate(c.data)}
        return c

    def shown_ok(cb, a):
        """checkbox text: the name part within the pixel budget, whole when it fits, else elided with
        '…'; the tooltip starts with the full name"""
        fm = cb.fontMetrics()
        txt = cb.text()
        suffix = " (deg)" if txt.endswith(" (deg)") else ""
        name = txt[:len(txt) - len(suffix)]
        fits = fm.horizontalAdvance(a) <= tl._AXIS_CHECK_TEXT_PX - fm.horizontalAdvance(suffix) or tl._std_axis(a)
        return (fm.horizontalAdvance(name) <= tl._AXIS_CHECK_TEXT_PX and (name == a if fits else '…' in name)
                and cb.toolTip().startswith(a))
    la.read_trace_log = read_with_units
    try:
        with warnings.catch_warnings(record=True) as wl:
            warnings.simplefilter('always')
            back = tl.logs_add_files(w, [p_al, p_long])
            pump(10)
            rb_axes = list(back[0].data) if len(back) == 2 else []
            lc_axes = list(back[1].data) if len(back) == 2 else []
            a0 = rb_axes[0] if rb_axes else None
            new_axes = rb_axes + lc_axes
            boxes = [w.logs_axis_checks.get(a) for a in new_axes]
            check("C aligned export + a log with long column names read back: one checkbox per column, each "
                  f"name whole or elided to {tl._AXIS_CHECK_TEXT_PX} px (middle '…'), full name in the tooltip; "
                  "standard axes unchanged",
                  len(rb_axes) == 4 and lc_axes == long_cols and all(boxes)
                  and all(shown_ok(cb, a) for cb, a in zip(boxes, new_axes))
                  and all('…' in w.logs_axis_checks[a].text() for a in long_cols)
                  and all(w.logs_axis_checks[a].text() == t and '…' not in t for a, t in std_texts.items()),
                  str([cb.text() for cb in boxes if cb]))
            check("C read-back: no more sideways scroll of the left panel than before, its minimum width at most "
                  "the scroll area's minimum (or as before), window width kept",
                  lhs.maximum() <= hs0 and w.width() == w0
                  and w.logs_left_scroll.widget().minimumSizeHint().width()
                  <= max(lmin0, w.logs_left_scroll.minimumWidth()),
                  f"h-scroll {hs0} -> {lhs.maximum()}, left min {lmin0} -> "
                  f"{w.logs_left_scroll.widget().minimumSizeHint().width()}")
            k0, kl = combo.findData(a0), combo.findData(long_cols[0])
            check("C axis combo sized by a minimum contents length (not its items), full item text in the item "
                  "tooltip; the reference and results combos too",
                  combo.sizeAdjustPolicy() == QComboBox.AdjustToMinimumContentsLengthWithIcon
                  and combo.minimumSizeHint().width() == cmin0 and k0 >= 0 and kl >= 0
                  and combo.itemData(k0, Qt.ToolTipRole) == f"{a0} (deg)"
                  and combo.itemData(kl, Qt.ToolTipRole) == f"{long_cols[0]} (mm)"
                  and w.logs_ref_combo.sizeAdjustPolicy() == QComboBox.AdjustToMinimumContentsLengthWithIcon
                  and w.logs_results_combo.sizeAdjustPolicy() == QComboBox.AdjustToMinimumContentsLengthWithIcon,
                  f"combo min {cmin0} -> {combo.minimumSizeHint().width()}")
            check("C per-curve unit (meta['units']) shown where present, la.axis_unit otherwise",
                  w.logs_axis_checks[a0].text().endswith(" (deg)") and combo.itemText(k0).endswith(" (deg)")
                  and combo.itemText(combo.findData('SI')) == "SI (mm)" and w.logs_axis_checks['SI'].text() == 'SI'
                  and tl._axis_unit(st, a0) == 'deg' and tl._axis_unit(st, rb_axes[1]) == 'mm'
                  and tl._axis_unit(st, long_cols[0]) == la.axis_unit(long_cols[0]),
                  f"{w.logs_axis_checks[a0].text()!r} / {combo.itemText(k0)!r}")
            tl.logs_set_analysis_axis(w, a0)
            pump()
            hdr = w.logs_curves_table.horizontalHeaderItem(5)
            check("C analysis axis with a per-curve unit: unit suffixes, the v offset header and the combo "
                  "tooltip follow it",
                  w.logs_spin_prom.suffix() == " deg" and w.logs_spin_mv_thr.suffix() == " deg"
                  and hdr.text().endswith(" deg)") and combo.toolTip().startswith(f"{a0} (deg)"),
                  f"{hdr.text()!r} {w.logs_spin_prom.suffix()!r} {combo.toolTip()!r}")
            tl.logs_set_analysis_axis(w, long_cols[0])
            tl.logs_set_display(w, show_diff=True)
            pump()
            w.logs_canvas.draw()
            hdr = w.logs_curves_table.horizontalHeaderItem(5)
            check("C long analysis axis: the v offset header, the difference label and the legend elide it (full "
                  "name in the header and combo tooltips); no sideways scroll, window width kept",
                  '…' in hdr.text() and long_cols[0] in hdr.toolTip()
                  and w.logs_diff_caption is not None and '…' in w.logs_diff_caption.get_text()
                  and len(w.logs_diff_caption.get_text()) < 70
                  and len(axd.get_ylabel()) < 12 and combo.toolTip().startswith(long_cols[0])
                  and max(len(t.get_text()) for t in ax.get_legend().get_texts()) <= tl._LEGEND_MAX_CHARS
                  and lhs.maximum() <= hs0 and w.width() == w0,
                  f"{hdr.text()!r} {axd.get_ylabel()!r} "
                  f"{w.logs_diff_caption.get_text() if w.logs_diff_caption is not None else None!r}")
            for z in ((0.0, 5.0), (40.0, 41.0), (-50.0, -10.0)):
                ax.set_xlim(*z)
                w.logs_canvas.draw()
            ax_w2 = ax.get_position().width
            cl_c = [str(x.message) for x in wl if 'constrained_layout' in str(x.message)]
        check("D read-back with the difference panel at 1366x768: no constrained_layout warning, plot not collapsed",
              not cl_c and ax_w2 > 0.7, f"{len(cl_c)} warnings, axes width {ax_w2:.3f}")
    finally:
        la.read_trace_log = orig_read
    tl.logs_set_display(w, show_diff=False)
    tl.logs_remove_curves(w, [len(st.entries) - 2, len(st.entries) - 1])
    pump()
    lay = _LAYOUT_CACHE['lay'] if 'lay' in _LAYOUT_CACHE else layout_in_subprocess()
    if lay is None:
        print("INFO: Windows fonts not available: read-back layout check skipped")
    else:
        for key, W in (('1600x900', 1600), ('1366x768', 1366)):
            rb = (lay.get(key) or {}).get('readback') or {}
            check(f"C {key} (Windows fonts): the aligned export of 4 curves read back: window {W} px wide, no "
                  "sideways scroll of the left panel, its minimum width within the scroll area's, the new axis "
                  f"names within {tl._AXIS_CHECK_TEXT_PX} px, standard ones whole, the axis combo's minimum width "
                  "unchanged",
                  rb and rb['window'][0] == W and rb['hscroll'] == 0
                  and rb['left_min'] <= max(rb['left_min0'], rb['scroll_min']) and 0 < rb['max_px'] <= tl._AXIS_CHECK_TEXT_PX
                  and rb['std_whole'] and rb['combo_min'] == rb['combo_min0'] and rb['cols_end'] <= rb['viewport'],
                  str({k: rb.get(k) for k in ('window', 'hscroll', 'left_min0', 'left_min', 'scroll_min', 'n_axes',
                                              'n_elided', 'max_px', 'std_whole', 'combo_min0', 'combo_min')}))
    check("C read-back removed: standard axis checkboxes again (no '…', no unit from the removed curve), "
          "window width kept",
          all(w.logs_axis_checks[a].text() == t for a, t in std_texts.items())
          and list(w.logs_axis_checks) == list(std_texts) and lhs.maximum() <= hs0 and w.width() == w0)
    tl.logs_clear_all(w)
    w.close()


def review4_checks():
    """Round 4: elided legend / axis-checkbox texts stay distinct when several runs of an aligned
    export are read back; the difference panel's y-label is short ('Δ (unit)') and the axis is in a
    caption inside the panel."""
    print("\n---- fourth review round ----")
    names = ["SI log_06112026_12_34_12_case_02", "SI log_06112026_12_40_05_case_02",
             "SI log_06112026_12_47_51_case_02"]
    shown = [tl._elide_mid(n, 14) for n in names]
    out = tl._distinct_texts(shown, names, 14)
    check("_distinct_texts: names elided to the same text are elided again around the part that differs "
          "(all distinct, each <= n characters)",
          len(set(shown)) == 1 and len(set(out)) == 3 and all(len(s) <= 14 for s in out)
          and all(k in s for k, s in zip(("34_12", "40_05", "47_51"), out)), str(out))
    same = tl._distinct_texts(["a…b", "a…b", "c"], ["aXb", "aXb", "c"], 8)
    check("_distinct_texts: equal full texts get ' #2', distinct texts are kept", same == ["a…b", "a…b #2", "c"],
          str(same))

    w = make_window()
    w.resize(1366, 768)
    tl.build_logs_tab(w)
    w.show()
    APP.processEvents()
    st = w.logs_state

    def pump(n=5):
        for _ in range(n):
            APP.processEvents()
    d = os.path.join(TMP, "review4")
    os.makedirs(d, exist_ok=True)
    runs = []
    for stamp in ("12_34_12", "12_40_05", "12_47_51"):
        p = os.path.join(d, f"log_06112026_{stamp}_case_02.csv")
        shutil.copy(CASE02, p)
        runs.append(p)
    tl.logs_add_files(w, runs)
    tl.logs_add_reference(w, CURVE2)
    p_al = os.path.join(d, "aligned_SI.csv")
    tl.logs_export_aligned(w, p_al)
    tl.logs_clear_all(w)
    tl.logs_add_files(w, [p_al])
    for a in list(st.known_axes):
        tl.logs_set_axis_enabled(w, a, True)
    pump()
    w.logs_canvas.draw()
    leg = w.logs_ax.get_legend()
    texts = [t.get_text() for t in leg.get_texts()] if leg is not None else []
    check("legend of 3 runs + curve2 read back from an aligned export: 4 distinct texts, each at most "
          "_LEGEND_MAX_CHARS characters", len(texts) == 4 and len(set(texts)) == 4
          and max(len(t) for t in texts) <= tl._LEGEND_MAX_CHARS, str(texts))
    cbt = [cb.text() for cb in w.logs_axis_checks.values()]
    check("axis checkboxes of the read-back runs: 4 distinct texts, the full names in the tooltips",
          len(cbt) == 4 and len(set(cbt)) == 4
          and all(cb.toolTip().startswith(a) for a, cb in w.logs_axis_checks.items()), str(cbt))
    long_ax = [a for a in st.known_axes if 'case_02' in a]
    if long_ax:
        tl.logs_set_analysis_axis(w, long_ax[0])
        tl.logs_set_display(w, show_diff=True)
        pump()
        w.logs_canvas.draw()
        cap = w.logs_diff_caption
        check("difference panel: y-label 'Δ (mm)', the analysis axis (whole up to _LEGEND_MAX_CHARS, else elided) "
              "in a caption inside the panel, out of the layout",
              w.logs_ax_diff.get_ylabel() == "Δ (mm)" and cap is not None
              and cap.get_text() == f"{tl._elide_mid(long_ax[0], tl._LEGEND_MAX_CHARS)}: curve − reference"
              and not cap.get_in_layout(),
              f"{w.logs_ax_diff.get_ylabel()!r} {cap.get_text() if cap is not None else None!r}")
    else:
        check("difference panel caption: a read-back axis exists", False, str(st.known_axes))
    w.close()


# ---------------------------------------------------------------------------------------------
# Fifth round: editing reference points and movements (tables and dragging on the plot)
# ---------------------------------------------------------------------------------------------
def _qpt(w, x, y):
    """Canvas pixel (matplotlib display coordinates, device pixels from the bottom) -> Qt point."""
    from PySide6.QtCore import QPoint
    cv = w.logs_canvas
    dpr = cv.devicePixelRatioF() or 1.0
    return QPoint(int(round(x / dpr)), int(round(cv.height() - y / dpr)))


def _qdrag(w, p0, p1, steps=8, release=True):
    """Left-button drag on the canvas with real Qt mouse events (QTest)."""
    from PySide6.QtTest import QTest
    cv = w.logs_canvas
    QTest.mouseMove(cv, p0)
    APP.processEvents()
    QTest.mousePress(cv, Qt.LeftButton, Qt.NoModifier, p0)
    for k in range(1, steps + 1):
        QTest.mouseMove(cv, p0 + (p1 - p0) * (k / steps))
        APP.processEvents()
    if release:
        QTest.mouseRelease(cv, Qt.LeftButton, Qt.NoModifier, p1)
    for _ in range(3):
        APP.processEvents()


def _marker_px(w, pid):
    """Pixel position of a point marker, from the drawn artist and its transform."""
    mk = w.logs_state.point_artists[pid]['marker']
    return mk.get_transform().transform((mk.get_xdata()[0], mk.get_ydata()[0]))


def _lane_px(w, uid, mid, where):
    """Pixel position of a lane segment's start / stop edge or its middle (centre of the lane band),
    from the PolyCollection's vertices and transform."""
    lane = w.logs_state.lane_artists[uid]
    col = lane['col']
    j = lane['ids'].index(mid)
    v = col.get_transform().transform(col.get_paths()[j].vertices[:4])
    x0, x1 = float(v[:, 0].min()), float(v[:, 0].max())
    y = float(v[:, 1].mean())
    return ({'start': x0, 'stop': x1, 'mid': (x0 + x1) / 2.0}[where], y)


def _edit_cell(tbl, r, c, text, how='dclick'):
    """Type `text` into cell (r, c) the way a user does: double-click (or F2, or typing over the
    current cell) opens the editor, the text is typed, Return commits.  False when no editor opened."""
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QLineEdit
    tbl.scrollToItem(tbl.item(r, c))
    APP.processEvents()
    rect = tbl.visualItemRect(tbl.item(r, c))
    if how == 'dclick':
        QTest.mouseClick(tbl.viewport(), Qt.LeftButton, Qt.NoModifier, rect.center())
        QTest.mouseDClick(tbl.viewport(), Qt.LeftButton, Qt.NoModifier, rect.center())
    else:
        tbl.setCurrentCell(r, c)
        tbl.setFocus()
        QTest.keyClick(tbl, Qt.Key_F2 if how == 'f2' else text[0])
    APP.processEvents()
    eds = [e for e in tbl.viewport().findChildren(QLineEdit) if e.isVisible()]
    if not eds:
        return False
    ed = eds[0]
    if how == 'type':
        QTest.keyClicks(ed, text[1:])
    else:
        ed.selectAll()
        QTest.keyClicks(ed, text)
    QTest.keyClick(ed, Qt.Key_Return)
    for _ in range(3):
        APP.processEvents()
    return True


def _lanes_match_table(w):
    """Every drawn lane segment has its movements-table row (same id) with the same start / stop (displayed),
    and every row of a visible curve has its lane segment."""
    st = w.logs_state
    tbl = w.logs_movements_table
    rows = {}
    for r in range(tbl.rowCount()):
        mid = tbl.item(r, 0).data(Qt.UserRole)
        rows[mid] = (float(tbl.item(r, 2).text()), float(tbl.item(r, 3).text()), tbl.item(r, 1).text())
    seen = set()
    for uid, lane in st.lane_artists.items():
        e = tl._entry_by_uid(st, uid)
        for j, mid in enumerate(lane['ids']):
            v = lane['col'].get_paths()[j].vertices
            a, b = float(v[:, 0].min()), float(v[:, 0].max())
            if mid not in rows or abs(rows[mid][0] - a) > 6e-4 or abs(rows[mid][1] - b) > 6e-4 \
                    or rows[mid][2] != e.curve.name:
                return False, f"lane {e.curve.name} #{j + 1} id {mid}: {a:.3f}-{b:.3f} vs {rows.get(mid)}"
            seen.add(mid)
    vis_rows = [it for it in tl.logs_movement_list(w) if tl._entry_by_uid(st, it['uid']).visible]
    missing = [it['id'] for it in vis_rows if it['id'] not in seen]
    return not missing, f"rows without a lane segment: {missing}"


def review5_checks():
    """Round 5: reference points and movement regions are edited by typing in their tables and by
    dragging on the plot (real Qt mouse events, blitting), with movement_stats for edited movements."""
    from PySide6.QtCore import QPoint
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QLineEdit
    print("\n---- fifth review round: editing points and movements ----")
    # windows left open by the sections above are hidden: offscreen, every top-level window sits at
    # the same place, and QTest delivers a mouse move without a button (hover) to the top one
    for tw in QApplication.topLevelWidgets():
        if tw.isVisible():
            tw.hide()
    w = make_window()
    w.resize(1600, 900)
    tl.build_logs_tab(w)
    w.show()
    w.raise_()
    w.activateWindow()
    APP.processEvents()
    st = w.logs_state
    cv = w.logs_canvas
    mt, pt = w.logs_movements_table, w.logs_points_table

    def pump(n=5):
        for _ in range(n):
            APP.processEvents()

    def redraw_now():
        cv.draw()
        pump(3)

    tl.logs_add_files(w, [CASE02])
    tl.logs_add_reference(w, CURVE2)
    i_case, i_ref = idx_of(w, 'case_02'), idx_of(w, 'curve2')
    tl.logs_select_curve(w, i_case)
    # (no pause estimate any more: a log without logged waits is shown as recorded)
    tl.logs_detect_movements(w, threshold=0.02, settle_time=0.5)
    pump()
    redraw_now()
    uid_case, uid_ref = st.entries[i_case].uid, st.entries[i_ref].uid

    # ---------------- A. movements table
    hdrs = [mt.horizontalHeaderItem(c).text() for c in range(mt.columnCount())]
    check("A movements table in section 7: #, Curve, Start (s), Stop (s), Duration (s), Delta (mm), Note",
          hdrs == ['#', 'Curve', 'Start (s)', 'Stop (s)', 'Duration (s)', 'Delta (mm)', 'Note'], str(hdrs))
    ml = tl.logs_movement_list(w)
    check("A one row per movement (3 per curve), sorted by curve (table order) then start, # per curve",
          mt.rowCount() == 6 == len(ml) and [d['uid'] for d in ml] == [uid_case] * 3 + [uid_ref] * 3
          and [mt.item(r, 0).text() for r in range(6)] == ['1', '2', '3'] * 2
          and all(ml[k]['t_start'] < ml[k + 1]['t_start'] for k in (0, 1, 3, 4)), str([mt.item(r, 0).text() for r in range(6)]))
    rows = st.results['Movements'][1]
    check("A table times / duration / delta = the Movements results view (displayed time base)",
          all(abs(float(mt.item(r, 2).text()) - rows[r][3]) < 6e-4 and abs(float(mt.item(r, 3).text()) - rows[r][4]) < 6e-4
              and abs(float(mt.item(r, 4).text()) - rows[r][5]) < 6e-4 and abs(float(mt.item(r, 5).text()) - rows[r][8]) < 6e-5
              for r in range(6)))
    ed = [[bool(mt.item(r, c).flags() & Qt.ItemIsEditable) for c in range(7)] for r in range(6)]
    check("A only Start / Stop are editable", all(row == [False, False, True, True, False, False, False] for row in ed))
    sb = mt.horizontalScrollBar()
    main_w = sum(mt.columnWidth(c) for c in range(6))
    check("A main columns fit the table without sideways scrolling (left panel ~530 px)",
          main_w <= mt.viewport().width() and sb.maximum() == 0, f"{main_w} px in {mt.viewport().width()} px")
    check("A Curve cell: colour icon, full name and axis in the tooltip", not mt.item(0, 1).icon().isNull()
          and mt.item(0, 1).toolTip().startswith(st.entries[i_case].curve.name + " · SI"))
    check("A Detect movements tooltip says it replaces the edits", 'edited by hand' in w.logs_btn_movements.toolTip())
    ok, det = _lanes_match_table(w)
    check("A every lane segment has its table row (same id, same start / stop)", ok, det)

    # ---------------- B. editing Start / Stop in the table
    n_box = len(FakeBox.calls)
    c_case = st.entries[i_case].curve
    tt = c_case.times()
    m1 = ml[1]
    mt.selectRow(1)
    want = m1['t_start'] - 1.0
    opened = _edit_cell(mt, 1, 2, f"{want:.3f}", how='dclick')
    d1 = tl.logs_movement_list(w)[1]
    i_exp = int(np.argmin(np.abs(tt - want)))
    check("B double-click + type + Return in Start: the movement starts at the nearest sample, marked edited",
          opened and d1['t_start'] == float(c_case.t[i_exp] + c_case.time_offset) and d1['edited']
          and d1['t_stop'] == m1['t_stop'] and d1['id'] == m1['id'], f"{m1['t_start']:.3f} -> {d1['t_start']:.4f}")
    mv = st.movements[uid_case]
    check("B stored as a raw segment (a sample of the curve) with edited = True; the others unchanged",
          mv['segments'][1][0] == float(c_case.t[i_exp]) and mv['edited'] == [False, True, False])
    s_exp = la.movement_stats(c_case, 'SI', d1['t_start'], d1['t_stop'])
    hdr, rows = st.results['Movements']
    r1 = rows[1]
    check("B Movements results view rebuilt: the row has la.movement_stats' numbers and 'edited by hand'",
          abs(r1[3] - s_exp['t_start']) < 1e-9 and abs(r1[5] - s_exp['duration']) < 1e-9
          and abs(r1[hdr.index('Peak speed (mm/s)')] - s_exp['peak_speed']) < 1e-12 and r1[-1] == 'edited by hand'
          and len(rows) == 6, str(r1))
    check("B table cells updated (start, duration, note), selection stays on the row",
          mt.item(1, 2).text() == f"{d1['t_start']:.3f}" and mt.item(1, 4).text() == f"{d1['duration']:.3f}"
          and mt.item(1, 6).text() == 'edited by hand' and {ix.row() for ix in mt.selectedIndexes()} == {1})
    check("B summary line says so", 'Movement 2' in w.logs_summary.text() and 'edited by hand' in w.logs_summary.text(),
          w.logs_summary.text())
    redraw_now()
    ok, det = _lanes_match_table(w)
    check("B the lane is redrawn with the edited span (thicker outline)", ok and
          st.lane_artists[uid_case]['col'].get_linewidths()[1] > st.lane_artists[uid_case]['col'].get_linewidths()[0], det)
    # F2 and typing over the current cell
    opened = _edit_cell(mt, 1, 3, f"{d1['t_stop'] + 0.5:.3f}", how='f2')
    d1b = tl.logs_movement_list(w)[1]
    check("B F2 + type + Return in Stop: stop moved ~0.5 s", opened and abs(d1b['t_stop'] - (d1['t_stop'] + 0.5)) < 0.1,
          f"{d1['t_stop']:.3f} -> {d1b['t_stop']:.3f}")
    opened = _edit_cell(mt, 1, 3, f"{d1['t_stop']:.3f}", how='type')
    d1c = tl.logs_movement_list(w)[1]
    check("B typing over the current Stop cell edits it", opened and abs(d1c['t_stop'] - d1['t_stop']) < 0.06,
          f"{d1c['t_stop']:.3f}")
    # refused entries: cell restored, status message, no box, nothing changed
    before = [dict(d) for d in tl.logs_movement_list(w)]
    segs_before = [list(m_['segments']) for m_ in st.movements.values()]
    nxt = before[2]
    prv = before[0]
    for text, col, why in (("abc", 2, "not a number"), (f"{nxt['t_start'] + 1.0:.3f}", 3, "overlap"),
                           (f"{prv['t_stop'] - 1.0:.3f}", 2, "overlap"), (f"{before[1]['t_stop'] + 0.0:.3f}", 2, "before the stop"),
                           ("-500", 2, "outside the data"), ("1e9", 3, "outside the data")):
        cell0 = mt.item(1, col).text()
        mt.item(1, col).setText(text)                  # the table's edit path (setData -> itemChanged)
        pump(2)
        ok = mt.item(1, col).text() == cell0 and [list(m_['segments']) for m_ in st.movements.values()] == segs_before
        check(f"B refused ({why}: {text!r}): cell restored, nothing changed, reason in the status line",
              ok and 'restored' in w.logs_summary.text() and not warnings_since(n_box), w.logs_summary.text()[-110:])
    check("B no warning box for refused cell entries", not warnings_since(n_box), str(warnings_since(n_box)))

    # ---------------- C. results view export follows the edits
    p_csv = os.path.join(TMP, "r5_movements.csv")
    tl.logs_export_results(w, p_csv, name='Movements')
    _n, _h, _r = la.read_rows_csv(p_csv)               # v2 style: '#' notes, ';' columns, decimal comma
    exp_rows = [_h] + _r
    check("C exported Movements view has the edited row (note 'edited by hand')",
          len(exp_rows) == 7 and exp_rows[2][-1] == 'edited by hand' and exp_rows[1][-1] == '', str(exp_rows[2]))

    # ---------------- D. dragging lane edges / segments with real mouse events
    redraw_now()
    xl0, yl0 = w.logs_ax.get_xlim(), w.logs_ax.get_ylim()
    m0 = tl.logs_movement_list(w)[0]
    x, y = _lane_px(w, uid_case, m0['id'], 'stop')
    tr = w.logs_ax.transData
    x_to = tr.transform((m0['t_stop'] + 2.0, 0.0))[0]
    _qdrag(w, _qpt(w, x, y), _qpt(w, x_to, y))
    d0 = tl.logs_movement_list(w)[0]
    t_mouse = tr.inverted().transform((_qpt(w, x_to, y).x() * (cv.devicePixelRatioF() or 1.0), 0.0))[0]
    i_exp = int(np.argmin(np.abs(tt - t_mouse)))
    check("D drag a lane's stop edge +2 s: snapped to the curve sample under the mouse, start unchanged, edited",
          d0['t_stop'] == float(tt[i_exp]) and d0['t_start'] == m0['t_start'] and d0['edited'],
          f"{m0['t_stop']:.3f} -> {d0['t_stop']:.3f} (sample {tt[i_exp]:.3f})")
    check("D the view did not move (no rescale on commit)", w.logs_ax.get_xlim() == xl0 and w.logs_ax.get_ylim() == yl0,
          f"{w.logs_ax.get_xlim()} {w.logs_ax.get_ylim()}")
    s_exp = la.movement_stats(c_case, 'SI', d0['t_start'], d0['t_stop'])
    check("D committed: table row, results view and status line show it",
          mt.item(0, 3).text() == f"{d0['t_stop']:.3f}" and abs(st.results['Movements'][1][0][4] - s_exp['t_stop']) < 1e-9
          and 'stop dragged' in w.logs_summary.text(), w.logs_summary.text())
    redraw_now()
    ok, det = _lanes_match_table(w)
    check("D lane and table agree after the drag", ok, det)
    # clamp at the next movement's start
    nxt = tl.logs_movement_list(w)[1]
    x, y = _lane_px(w, uid_case, d0['id'], 'stop')
    _qdrag(w, _qpt(w, x, y), _qpt(w, tr.transform((nxt['t_start'] + 4.0, 0.0))[0], y))
    d0b = tl.logs_movement_list(w)[0]
    check("D stop dragged past the next movement: clamped at its start", d0b['t_stop'] == nxt['t_start'],
          f"{d0b['t_stop']:.4f} vs {nxt['t_start']:.4f}")
    # the start cannot pass the stop (one sample at least)
    x, y = _lane_px(w, uid_case, d0b['id'], 'start')
    _qdrag(w, _qpt(w, x, y), _qpt(w, tr.transform((d0b['t_stop'] + 3.0, 0.0))[0], y))
    d0c = tl.logs_movement_list(w)[0]
    j_stop = int(np.argmin(np.abs(tt - d0c['t_stop'])))
    check("D start dragged past the stop: one sample before it", d0c['t_start'] == float(tt[j_stop - 1]),
          f"{d0c['t_start']:.4f} / stop {d0c['t_stop']:.4f}")
    tl.logs_set_movement(w, 0, t_start=m0['t_start'], t_stop=m0['t_stop'])
    # whole segment
    redraw_now()
    m2 = tl.logs_movement_list(w)[2]
    x, y = _lane_px(w, uid_case, m2['id'], 'mid')
    _qdrag(w, _qpt(w, x, y), _qpt(w, x + (tr.transform((3.0, 0))[0] - tr.transform((0.0, 0))[0]), y))
    d2 = tl.logs_movement_list(w)[2]
    check("D drag inside a lane segment moves the whole movement (~ +3 s, same duration within a sample)",
          abs(d2['t_start'] - m2['t_start'] - 3.0) < 0.15 and abs(d2['duration'] - m2['duration']) < 0.15 and d2['edited'],
          f"{m2['t_start']:.3f}-{m2['t_stop']:.3f} -> {d2['t_start']:.3f}-{d2['t_stop']:.3f}")
    # Escape cancels (focus elsewhere: the points table)
    redraw_now()
    m2 = tl.logs_movement_list(w)[2]
    col = st.lane_artists[uid_case]['col']
    x, y = _lane_px(w, uid_case, m2['id'], 'start')
    _qdrag(w, _qpt(w, x, y), _qpt(w, x - 60, y), release=False)
    moved = st.drag is not None and st.drag.get('started') and \
        abs(float(col.get_paths()[2].vertices[:, 0].min()) - m2['t_start']) > 1.0
    QTest.keyClick(pt, Qt.Key_Escape)
    pump(2)
    back = abs(float(col.get_paths()[2].vertices[:, 0].min()) - m2['t_start']) < 1e-9
    QTest.mouseRelease(cv, Qt.LeftButton, Qt.NoModifier, _qpt(w, x - 60, y))
    pump(3)
    d2b = tl.logs_movement_list(w)[2]
    check("D Escape during a lane drag: the lane goes back, nothing stored (also after the release)",
          moved and back and st.drag is None and d2b['t_start'] == m2['t_start'] and d2b['t_stop'] == m2['t_stop'],
          w.logs_summary.text())
    # a press-release without movement changes nothing
    x, y = _lane_px(w, uid_case, m2['id'], 'stop')
    segs0 = [list(m_['segments']) for m_ in st.movements.values()]
    _qdrag(w, _qpt(w, x, y), _qpt(w, x + 1, y), steps=1)
    check("D press-release moving < 3 px: nothing changes", [list(m_['segments']) for m_ in st.movements.values()] == segs0
          and st.drag is None)

    # ---------------- E. delete / add from ROI / re-detect
    mt.clearSelection()
    n_box = len(FakeBox.calls)
    tl._on_delete_movements_clicked(w)
    check("E Delete without a selection: warning, nothing deleted", len(tl.logs_movement_list(w)) == 6
          and len(warnings_since(n_box)) == 1)
    ids_before = [d['id'] for d in tl.logs_movement_list(w)]
    mt.selectRow(4)
    QTest.mouseClick(w.logs_btn_movements_del, Qt.LeftButton)
    pump(3)
    ids_after = [d['id'] for d in tl.logs_movement_list(w)]
    check("E 'Delete selected movement(s)' removes the selected row's movement (by id), the others keep theirs",
          ids_after == ids_before[:4] + ids_before[5:] and mt.rowCount() == 5 and not mt.selectedIndexes()
          and len(st.results['Movements'][1]) == 5, f"{ids_before} -> {ids_after}")
    redraw_now()
    ok, det = _lanes_match_table(w)
    check("E lanes follow the deletion", ok and len(st.lane_artists[uid_ref]['ids']) == 2, det)
    n_box = len(FakeBox.calls)
    tl.logs_clear_roi(w)
    check("E Add movement from ROI without a ROI: refused with a warning",
          tl.logs_add_movement_from_roi(w) is None and len(warnings_since(n_box)) == 1
          and 'region of interest' in warnings_since(n_box)[0][2])
    ml = tl.logs_movement_list(w)
    tl.logs_set_roi(w, ml[0]['t_stop'] - 0.5, ml[0]['t_stop'] + 2.0)
    n_box = len(FakeBox.calls)
    tl.logs_select_curve(w, i_case)
    check("E Add from a ROI overlapping a movement of the selected curve: refused",
          tl.logs_add_movement_from_roi(w) is None and len(warnings_since(n_box)) == 1
          and 'overlaps' in warnings_since(n_box)[0][2], str(warnings_since(n_box)))
    gap_a, gap_b = ml[0]['t_stop'] + 1.0, ml[1]['t_start'] - 1.0
    tl.logs_set_roi(w, gap_a, gap_b)
    QTest.mouseClick(w.logs_btn_movements_add, Qt.LeftButton)
    pump(3)
    ml2 = tl.logs_movement_list(w)
    new = [d for d in ml2 if d['id'] not in {x['id'] for x in ml}]
    check("E 'Add movement from ROI' on the selected curve: inserted in start order, inside the ROI, edited",
          len(new) == 1 and new[0]['uid'] == uid_case and new[0]['number'] == 2 and gap_a <= new[0]['t_start']
          and new[0]['t_stop'] <= gap_b and new[0]['edited'] and mt.rowCount() == 6
          and [d['number'] for d in ml2 if d['uid'] == uid_case] == [1, 2, 3, 4], str(new))
    st.selected = -1
    w.logs_curves_table.clearSelection()
    tl.logs_set_roi(w, 0.0, 24.0)                       # before every movement; holds 2 rows of curve2 (0, 9.99 s)
    n0 = len(tl.logs_movement_list(w))
    k = tl.logs_add_movement_from_roi(w)
    check("E no curve selected: one movement on every visible curve with the analysis axis",
          k == 2 and len(tl.logs_movement_list(w)) == n0 + 2, str(k))
    tl.logs_clear_roi(w)
    redraw_now()
    ok, det = _lanes_match_table(w)
    check("E lanes and rows agree after the adds", ok, det)
    tl.logs_detect_movements(w, threshold=0.02, settle_time=0.5)
    check("E Detect movements again replaces every edit, and says so",
          not any(d['edited'] for d in tl.logs_movement_list(w)) and len(tl.logs_movement_list(w)) == 6
          and 'edited by hand were replaced' in w.logs_summary.text(), w.logs_summary.text()[-80:])

    # ---------------- F. consistency after offsets / hide / axis / pauses / removal
    ml = tl.logs_movement_list(w)
    off0 = c_case.time_offset
    tl.logs_set_time_offset(w, i_case, off0 + 1.25)
    redraw_now()
    ml_b = tl.logs_movement_list(w)
    ok, det = _lanes_match_table(w)
    check("F time offset +1.25 s: the curve's rows and lanes shift with it, the reference's do not",
          ok and all(abs(b['t_start'] - a['t_start'] - (1.25 if a['uid'] == uid_case else 0.0)) < 1e-9
                     for a, b in zip(ml, ml_b)) and mt.item(0, 2).text() == f"{ml_b[0]['t_start']:.3f}", det)
    tl.logs_set_movement(w, 0, t_stop=ml_b[0]['t_stop'] + 0.3)
    s_exp = la.movement_stats(c_case, 'SI', tl.logs_movement_list(w)[0]['t_start'], tl.logs_movement_list(w)[0]['t_stop'])
    check("F an edit after the offset change: movement_stats at the displayed times", abs(
        st.results['Movements'][1][0][4] - s_exp['t_stop']) < 1e-9)
    tl.logs_set_time_offset(w, i_case, off0)
    tl.logs_set_visible(w, i_case, False)
    redraw_now()
    ok, det = _lanes_match_table(w)
    check("F hidden curve: its rows stay (grey), its lane is not drawn (nothing to drag)",
          ok and uid_case not in st.lane_artists and mt.rowCount() == 6
          and mt.item(0, 1).foreground().color().name() == tl._HIDDEN_FG, det)
    tl.logs_set_visible(w, i_case, True)
    redraw_now()
    check("F shown again: lane back, rows normal", uid_case in st.lane_artists and mt.item(0, 1).data(Qt.ForegroundRole) is None)
    tl.logs_set_analysis_axis(w, 'LAT')
    redraw_now()
    ok, det = _lanes_match_table(w)
    check("F analysis axis changed: the SI movements keep their rows and lanes", ok and mt.rowCount() == 6, det)
    tl.logs_set_analysis_axis(w, 'SI')
    ml_before = tl.logs_movement_list(w)
    segs_ref = list(st.movements[uid_ref]['segments'])
    tl.logs_add_files(w, [DUMMY])                     # a log with a logged wait: the pause gets 1.739 s
    redraw_now()
    d_p = st.entries[i_ref].curve.meta['pause_durations'][0]
    ok, det = _lanes_match_table(w)
    ml_mid = tl.logs_movement_list(w)
    moved = [b['t_start'] - a['t_start'] for a, b in zip(ml_before, ml_mid) if a['uid'] == uid_ref]
    check("F pause length changed (a log with a logged wait loaded): the reference's movements stay, moved by the "
          "pause, table and plot together",
          ok and mt.rowCount() == 6 and uid_ref in st.lane_artists and abs(d_p - 1.7391) < 1e-9
          and len(moved) == 3 and all(abs(x - d_p) < 1e-6 for x in moved), f"{det} {moved}")
    tl.logs_remove_curves(w, [idx_of(w, 'DUMMY')])
    redraw_now()
    i_case, i_ref = idx_of(w, 'case_02'), idx_of(w, 'curve2')
    ok, det = _lanes_match_table(w)
    check("F the log removed: the pause back to 0 s, the reference's movements exactly where they were",
          ok and st.movements[uid_ref]['segments'] == segs_ref and tl.logs_movement_list(w) == ml_before, det)

    # ---------------- G. points: typing in the table
    tl.logs_clear_points(w)
    tl.logs_add_point(w, i_case, 30.0)
    tl.logs_add_point(w, i_ref, 50.0)
    tl.logs_add_point(w, i_case, 70.0)
    pids = [p['id'] for p in st.points]
    pt.selectRow(1)
    c_ref = st.entries[i_ref].curve
    opened = _edit_cell(pt, 0, 3, "35.0", how='dclick')
    t0_, v0_ = tl._point_tv(st, st.points[0])
    ts_, vs_ = la.nearest_point(c_case, 'SI', 35.0)
    t1_, v1_ = tl._point_tv(st, st.points[1])
    check("G type t: the point re-snaps to the nearest sample of its own curve (t_raw = sample - offset)",
          opened and (t0_, v0_) == (ts_, vs_) and st.points[0]['t_raw'] == float(c_case.t[np.argmin(np.abs(tt - ts_))])
          and st.points[0]['uid'] == uid_case, f"{t0_:.4f} {v0_:.4f}")
    check("G derived columns, 'Points' view, summary updated; selection stays on the edited point (by id)",
          pt.item(0, 3).text() == f"{t0_:.3f}" and abs(float(pt.item(1, 5).text()) - (t1_ - t0_)) < 1e-3
          and abs(st.results['Points'][1][1][5] - (t1_ - t0_)) < 1e-9 and 'Point 1' in w.logs_summary.text()
          and tl._selected_point_ids(w) == {pids[0]} and [p['id'] for p in st.points] == pids)
    pt.selectRow(1)
    pt.item(0, 3).setText("36.0")                       # edit path of another row: the selection is kept
    pump(2)
    check("G an edit keeps the table selection (by id)", tl._selected_point_ids(w) == {pids[1]}
          and tl._point_tv(st, st.points[0]) == la.nearest_point(c_case, 'SI', 36.0))
    tl.logs_set_point_time(w, 0, 35.0)
    t0_, v0_ = tl._point_tv(st, st.points[0])
    tc_ = la.nearest_crossing(c_case, 'SI', 26.0, t0_)
    opened = _edit_cell(pt, 0, 4, "26", how='f2')
    t0b, v0b = tl._point_tv(st, st.points[0])
    check("G type a Value: the point moves where its curve reaches it nearest to its time (crossing, then the sample)",
          opened and tc_ is not None and (t0b, v0b) == la.nearest_point(c_case, 'SI', tc_) and abs(v0b - 26.0) < 0.05,
          f"crossing {tc_}, now {t0b:.3f} / {v0b:.4f}")
    n_box = len(FakeBox.calls)
    msgs = []
    for text, why in (("99", "never reached"), ("x1", "not a number"), ("", "empty")):
        cell0 = pt.item(0, 4).text()
        pt.item(0, 4).setText(text)
        pump(2)
        msgs.append(w.logs_summary.text())
        check(f"G Value {text!r} ({why}): refused in the status line, cell restored, point unchanged",
              pt.item(0, 4).text() == cell0 and tl._point_tv(st, st.points[0]) == (t0b, v0b)
              and 'restored' in w.logs_summary.text() and not warnings_since(n_box), w.logs_summary.text()[-100:])
    check("G 'never reaches' message names the curve's value range", 'never reaches 99 mm' in msgs[0]
          and '25.0010' in msgs[0] and '28.5000' in msgs[0], msgs[0])
    pt.item(0, 3).setText("47,5")                       # decimal comma accepted, as the dimension fields
    pump(2)
    check("G t '47,5' (decimal comma) accepted", tl._point_tv(st, st.points[0]) == la.nearest_point(c_case, 'SI', 47.5))
    ed = [[bool(pt.item(0, c).flags() & Qt.ItemIsEditable) for c in range(7)]]
    check("G points table: only t and Value are editable", ed[0] == [False, False, False, True, True, False, False])
    r = tl.logs_set_point_value(w, 1, 1000.0)
    check("G logs_set_point_value never reached: warning, None", r is None and len(warnings_since(n_box)) == 1)
    r = tl.logs_set_point_time(w, 1, 60.0)
    check("G logs_set_point_time: (t, value) of the nearest sample of its curve", r == la.nearest_point(c_ref, 'SI', 60.0))

    # ---------------- H. points: dragging on the plot
    redraw_now()
    pid0 = st.points[0]['id']
    t_a, v_a = tl._point_tv(st, st.points[0])
    x, y = _marker_px(w, pid0)
    xl0, yl0 = w.logs_ax.get_xlim(), w.logs_ax.get_ylim()
    x_to = tr.transform((t_a + 5.0, v_a))[0]
    _qdrag(w, _qpt(w, x, y), _qpt(w, x_to, y + 40))
    t_b, v_b = tl._point_tv(st, st.points[0])
    t_mouse = tr.inverted().transform((_qpt(w, x_to, y).x() * (cv.devicePixelRatioF() or 1.0), y))[0]
    check("H drag a marker (pick mode None): it follows the mouse in x, snapped to a sample of ITS curve (value follows "
          "the curve)", (t_b, v_b) == la.nearest_point(c_case, 'SI', t_mouse) and st.points[0]['uid'] == uid_case,
          f"{t_a:.3f} -> {t_b:.3f} (mouse {t_mouse:.3f})")
    check("H view unchanged, table and status updated", w.logs_ax.get_xlim() == xl0 and w.logs_ax.get_ylim() == yl0
          and pt.item(0, 3).text() == f"{t_b:.3f}" and 'dragged' in w.logs_summary.text())
    # clamp to the curve's time range
    redraw_now()
    x, y = _marker_px(w, pid0)
    w.logs_ax.set_xlim(tt[0] - 50.0, xl0[1])
    redraw_now()
    x, y = _marker_px(w, pid0)
    _qdrag(w, _qpt(w, x, y), _qpt(w, tr.transform((tt[0] - 40.0, 0))[0], y))
    check("H dragged before the data: clamped to the first sample", tl._point_tv(st, st.points[0])[0] == float(tt[0]))
    w.logs_ax.set_xlim(*xl0)
    tl.logs_set_point_time(w, 0, t_b)
    redraw_now()
    # points mode: a press on a marker drags it, no point added; a click on it adds nothing
    tl.logs_set_pick_mode(w, 'points')
    n_pts = len(st.points)
    x, y = _marker_px(w, pid0)
    _qdrag(w, _qpt(w, x, y), _qpt(w, x - 50, y))
    check("H points mode: a press on a marker drags it instead of adding a point",
          len(st.points) == n_pts and tl._point_tv(st, st.points[0])[0] < t_b - 2.0)
    redraw_now()
    x, y = _marker_px(w, pid0)
    before = tl._point_tv(st, st.points[0])
    QTest.mouseClick(cv, Qt.LeftButton, Qt.NoModifier, _qpt(w, x, y))
    pump(3)
    check("H points mode: a click on a marker (no move) adds nothing and moves nothing",
          len(st.points) == n_pts and tl._point_tv(st, st.points[0]) == before)
    xc, yc = tr.transform((40.0, float(np.interp(40.0, tt, c_case.values('SI')))))
    QTest.mouseClick(cv, Qt.LeftButton, Qt.NoModifier, _qpt(w, xc, yc))
    pump(3)
    check("H points mode: a click away from the markers still adds a point", len(st.points) == n_pts + 1)
    tl.logs_delete_points(w, [len(st.points) - 1])
    # ROI mode and toolbar modes: no drag
    redraw_now()
    tl.logs_set_pick_mode(w, 'roi')
    x, y = _marker_px(w, pid0)
    before = tl._point_tv(st, st.points[0])
    _qdrag(w, _qpt(w, x, y), _qpt(w, x + 80, y))
    check("H ROI mode: a drag from a marker selects a ROI, the point stays",
          tl._point_tv(st, st.points[0]) == before and st.roi is not None)
    tl.logs_set_pick_mode(w, None)
    tl.logs_clear_roi(w)
    redraw_now()
    for mode in ('pan', 'zoom'):
        getattr(w.logs_toolbar, mode)()
        x, y = _marker_px(w, pid0)
        before = tl._point_tv(st, st.points[0])
        segs0 = [list(m_['segments']) for m_ in st.movements.values()]
        _qdrag(w, _qpt(w, x, y), _qpt(w, x + 60, y - 20))
        getattr(w.logs_toolbar, mode)()
        check(f"H toolbar {mode} mode: no point / movement drag", tl._point_tv(st, st.points[0]) == before
              and [list(m_['segments']) for m_ in st.movements.values()] == segs0 and st.drag is None)
        tl.logs_zoom_all(w)
        redraw_now()
    # the legend: a press on it never drags a point under it (the legend is put over a marker, as the
    # user's own legend drag would: its loc in axes coordinates)
    tl.logs_clear_points(w)
    tl.logs_add_point(w, i_case, 30.0)
    redraw_now()
    pid_l = st.points[0]['id']
    x, y = _marker_px(w, pid_l)
    fx, fy = w.logs_ax.transAxes.inverted().transform((x, y))
    leg = w.logs_ax.get_legend()
    leg.set_loc((float(fx) - 0.03, float(fy) - 0.03))
    cv.draw()
    pump(2)
    on_leg = leg.get_window_extent().contains(x, y)
    before = tl._point_tv(st, st.points[0])
    _qdrag(w, _qpt(w, x, y), _qpt(w, x + 70, y))
    check("H a drag that starts on the legend (over a marker) moves the legend, never the point",
          on_leg and tl._point_tv(st, st.points[0]) == before and st.drag is None, f"marker on the legend: {on_leg}")
    tl.logs_redraw(w)
    redraw_now()
    # Escape and a redraw from elsewhere during a point drag
    x, y = _marker_px(w, pid_l)
    mk = st.point_artists[pid_l]['marker']
    _qdrag(w, _qpt(w, x, y), _qpt(w, x + 90, y), release=False)
    moved = st.drag is not None and float(mk.get_xdata()[0]) != before[0]
    QTest.keyClick(cv, Qt.Key_Escape)
    pump(2)
    QTest.mouseRelease(cv, Qt.LeftButton, Qt.NoModifier, _qpt(w, x + 90, y))
    pump(2)
    check("H Escape on the canvas cancels a point drag: marker restored, point unchanged",
          moved and float(mk.get_xdata()[0]) == before[0] and tl._point_tv(st, st.points[0]) == before)
    redraw_now()
    x, y = _marker_px(w, pid_l)
    _qdrag(w, _qpt(w, x, y), _qpt(w, x + 90, y), release=False)
    dragging = st.drag is not None and st.drag.get('started')
    w.logs_spin_band_k.setValue(w.logs_spin_band_k.value() + 0.5)     # debounced redraw: fires during the drag
    wait_ms(tl._REDRAW_DELAY_MS + 150)
    for k in range(3):
        QTest.mouseMove(cv, _qpt(w, x + 100 + 10 * k, y))
        APP.processEvents()
    QTest.mouseRelease(cv, Qt.LeftButton, Qt.NoModifier, _qpt(w, x + 130, y))
    pump(3)
    check("H a debounced redraw during a drag drops it cleanly (nothing stored, the status line says so)",
          dragging and st.drag is None and tl._point_tv(st, st.points[0]) == before
          and 'redrawn' in w.logs_summary.text(), w.logs_summary.text())
    # hover cursor
    redraw_now()
    x, y = _marker_px(w, pid_l)
    QTest.mouseMove(cv, _qpt(w, x + 2, y))
    pump(1)
    c_marker = cv.cursor().shape()
    mm = max(tl.logs_movement_list(w), key=lambda d: d['duration'])
    xe, ye = _lane_px(w, mm['uid'], mm['id'], 'stop')
    QTest.mouseMove(cv, _qpt(w, xe, ye))
    pump(1)
    c_edge = cv.cursor().shape()
    xm, ym = _lane_px(w, mm['uid'], mm['id'], 'mid')
    QTest.mouseMove(cv, _qpt(w, xm, ym))
    pump(1)
    c_mid = cv.cursor().shape()
    bbx = w.logs_ax.bbox
    QTest.mouseMove(cv, _qpt(w, bbx.x0 + 0.5 * bbx.width, bbx.y0 + 0.97 * bbx.height))
    pump(1)
    c_else = cv.cursor().shape()
    check("H hover: horizontal-move cursor over a marker and a lane edge, move cursor inside a lane segment, arrow "
          "elsewhere", (c_marker, c_edge, c_mid, c_else) == (Qt.SizeHorCursor, Qt.SizeHorCursor, Qt.SizeAllCursor,
                                                             Qt.ArrowCursor), str((c_marker, c_edge, c_mid, c_else)))
    tl.logs_remove_curves(w, [i_ref])
    redraw_now()
    ok, det = _lanes_match_table(w)
    check("F curve removed: its rows and lanes go, the other curve's stay", ok and mt.rowCount() == 3, det)
    check("no warning box during the editing / dragging (except the refused actions)",
          all(c[1] in ('Movements', 'Reference points') for c in FakeBox.calls[n_box:]), str(FakeBox.calls[n_box:]))
    w.close()

    # ---------------- P. performance: three 100k-row logs + curve2, band / envelope / difference on
    w = make_window()
    w.resize(1600, 900)
    tl.build_logs_tab(w)
    w.show()
    APP.processEvents()
    st = w.logs_state
    cv = w.logs_canvas
    paths = []
    rng = np.random.default_rng(5)
    for k in range(3):
        t_ = np.cumsum(rng.uniform(0.05, 0.11, 100_000))
        held = np.floor(t_ / 0.2) * 0.2
        si = 26.0 + 2.0 * np.sin(2 * np.pi * held / 40.0) * (np.sin(2 * np.pi * held / 700.0) > 0)
        p = os.path.join(TMP, f"log_r5_big_{k}.csv")
        write_log(p, t_, si)
        paths.append(p)
    tl.logs_add_files(w, paths)
    tl.logs_add_reference(w, CURVE2)
    tl.logs_set_display(w, show_band=True, show_envelope=True, show_diff=True)
    tl.logs_set_roi(w, 0.0, 3000.0)
    tl.logs_detect_movements(w)
    tl.logs_clear_roi(w)
    tl.logs_add_point(w, 0, 1000.0)
    w.logs_ax.set_xlim(900.0, 1100.0)
    cv.draw()
    APP.processEvents()
    tr = w.logs_ax.transData
    blits = []
    orig_blit = cv.blit

    def timed_blit(bbox=None):
        a = time.perf_counter()
        orig_blit(bbox)
        blits.append(time.perf_counter() - a)
    cv.blit = timed_blit

    def measure(p0, p1, steps=40):
        QTest.mouseMove(cv, p0)
        APP.processEvents()
        QTest.mousePress(cv, Qt.LeftButton, Qt.NoModifier, p0)
        net = []
        for k in range(1, steps + 1):
            n0 = len(blits)
            a = time.perf_counter()
            QTest.mouseMove(cv, p0 + (p1 - p0) * (k / steps))
            net.append(time.perf_counter() - a - sum(blits[n0:]))
        QTest.mouseRelease(cv, Qt.LeftButton, Qt.NoModifier, p1)
        APP.processEvents()
        return np.array(net) * 1000.0
    pid = st.points[0]['id']
    x, y = _marker_px(w, pid)
    t_pt = measure(_qpt(w, x, y), _qpt(w, x + 300, y))
    uid0 = st.entries[0].uid
    mvs = [d for d in tl.logs_movement_list(w) if d['uid'] == uid0 and 905.0 < d['t_stop'] < 1095.0]
    t_ln = np.array([0.0])
    if mvs:
        xe, ye = _lane_px(w, uid0, mvs[0]['id'], 'stop')
        t_ln = measure(_qpt(w, xe, ye), _qpt(w, xe + 40, ye))
    rest = np.concatenate([np.sort(t_pt)[:-1], np.sort(t_ln)[:-1]])
    print(f"INFO: drag with 3 x 100k rows + curve2, band / envelope / diff: background capture (first move) "
          f"{max(t_pt.max(), t_ln.max()):.0f} ms; per motion event without the blit: median {np.median(rest):.2f} ms, "
          f"p95 {np.percentile(rest, 95):.2f} ms, max {rest.max():.1f} ms (point {np.median(t_pt):.2f} ms, "
          f"lane {np.median(t_ln):.2f} ms)")
    check("P dragging stays smooth with 3 x 100k-row logs (motion event < 30 ms without the blit: median and p95)",
          bool(mvs) and np.median(rest) < 30.0 and np.percentile(rest, 95) < 30.0 and st.drag is None
          and tl.logs_movement_list(w) and any(d['edited'] for d in tl.logs_movement_list(w)),
          f"median {np.median(rest):.2f} ms, p95 {np.percentile(rest, 95):.2f} ms")
    cv.blit = orig_blit
    w.close()


# ---------------------------------------------------------------------------------------------
# Sixth round: fixes after the fifth round's review
# ---------------------------------------------------------------------------------------------
def _model_watch(tbl):
    """Record what a QTableWidget's model emits until the returned stop() is called: the rows of its
    dataChanged signals, model resets, row insertions and removals (a refill shows as a reset)."""
    m = tbl.model()
    rec = {'rows': set(), 'reset': 0, 'ins': 0, 'rem': 0}

    def dc(a, b, roles=None):
        rec['rows'].update(range(a.row(), b.row() + 1))

    def rs():
        rec['reset'] += 1

    def ins(*a):
        rec['ins'] += 1

    def rem(*a):
        rec['rem'] += 1
    conns = [(m.dataChanged, dc), (m.modelReset, rs), (m.rowsInserted, ins), (m.rowsRemoved, rem)]
    for sig, f in conns:
        sig.connect(f)

    def stop():
        for sig, f in conns:
            try:
                sig.disconnect(f)
            except Exception:
                pass
        return rec
    return stop


def _write_fast_log(path, t, si):
    """A TRACE log written with numpy (100k rows in a fraction of a second)."""
    with open(path, 'w', newline='', encoding='utf-8') as f:
        f.write("# Computer Time: 2026-11-07 10:00:00.000\n# Device: Motion Platform\n")
        f.write("Time_s,Pos_LAT_mm,Pos_SI_mm,Pos_AP_mm,Pos_Roll_deg,Pos_Pitch_deg,Pos_Yaw_deg,Probe\n")
        z = np.zeros(len(t))
        np.savetxt(f, np.column_stack([t, z + 50.0, si, z + 35.0, z, z, z, z]),
                   fmt=['%.4f', '%.3f', '%.3f', '%.3f', '%.3f', '%.3f', '%.3f', '%d'], delimiter=',')


def review6_checks():
    """Round 6 (fixes of the fifth round's review): the movements table and the 'Movements' view are
    rewritten only where something changed and stay in step with the table and the lanes (offsets,
    pauses, Clear); a click next to another curve's marker still adds a point; a lane drag moves one
    segment; a whole segment keeps its width on sparse rows; an edit back onto the same sample changes
    nothing; a curve without movements takes no lane; speed with ~3850 movements."""
    from PySide6.QtCore import QPoint
    from PySide6.QtTest import QTest
    print("\n---- sixth review round: fixes ----")
    n_box0 = len(FakeBox.calls)
    for tw in QApplication.topLevelWidgets():
        if tw.isVisible():
            tw.hide()
    w = make_window()
    w.resize(1600, 900)
    tl.build_logs_tab(w)
    w.show()
    w.raise_()
    w.activateWindow()
    APP.processEvents()
    st = w.logs_state
    cv = w.logs_canvas
    mt, rt = w.logs_movements_table, w.logs_results_table

    def pump(n=5):
        for _ in range(n):
            APP.processEvents()

    def redraw_now():
        cv.draw()
        pump(3)

    def ml_():
        return tl.logs_movement_list(w)

    tl.logs_add_files(w, [CASE02])
    tl.logs_add_reference(w, CURVE2)
    i_case, i_ref = idx_of(w, 'case_02'), idx_of(w, 'curve2')
    tl.logs_select_curve(w, i_case)
    # (no pause estimate any more: a log without logged waits is shown as recorded)
    tl.logs_detect_movements(w, threshold=0.02, settle_time=0.5)
    pump()
    redraw_now()
    uid_case, uid_ref = st.entries[i_case].uid, st.entries[i_ref].uid
    c_case = st.entries[i_case].curve

    def view_matches():
        """The 'Movements' view rows and its CSV export = the movements list (= the table and the lanes)."""
        ml = ml_()
        res = st.results.get('Movements')
        rows = res[1] if res else []
        probs = []
        if len(rows) != len(ml) or mt.rowCount() != len(ml):
            probs.append(f"view {len(rows)} rows, table {mt.rowCount()}, list {len(ml)}")
        for r, (row, d) in enumerate(zip(rows, ml)):
            if row[0] != d['curve'] or abs(row[3] - d['t_start']) > 1e-9 or abs(row[4] - d['t_stop']) > 1e-9 \
                    or row[-1] != d['note'] or row[10] != d['complete']:
                probs.append(f"row {r}: {row[0][:12]} {row[3]:.4f}-{row[4]:.4f} vs {d['curve'][:12]} "
                             f"{d['t_start']:.4f}-{d['t_stop']:.4f}")
        if res:
            summary = st.summary
            p_csv = os.path.join(TMP, "r6_movements.csv")
            tl.logs_export_results(w, p_csv, name='Movements')
            tl._set_summary(w, summary)
            ex = la.read_rows_csv(p_csv)[2]            # v2 style: '#' notes, ';' columns, decimal comma
            if len(ex) != len(ml) or any(abs(float(x[3]) - d['t_start']) > 1e-6 or abs(float(x[4]) - d['t_stop']) > 1e-6
                                         for x, d in zip(ex, ml)):
                probs.append(f"CSV {len(ex)} rows: {[x[3:5] for x in ex][:3]}")
        ok, det = _lanes_match_table(w)
        if not ok:
            probs.append(det)
        return not probs, "; ".join(probs[:4])

    # ---------------- issue 1: nothing rewritten when nothing about the movements changed
    check("1 precondition: the 'Movements' view is the one shown", st.current_results == 'Movements' and rt.rowCount() == 6)
    item0 = mt.item(0, 2)
    stop_m, stop_r = _model_watch(mt), _model_watch(rt)
    tl.logs_set_display(w, show_probe=not st.show_probe)
    tl.logs_add_point(w, i_case, 30.0)
    tl.logs_redraw(w)
    tl.logs_set_display(w, show_probe=not st.show_probe)
    rm, rr = stop_m(), stop_r()
    check("1 redraws that change no movement (display toggles, a point added, logs_redraw) leave the movements table "
          "and the shown 'Movements' view untouched (no cell rewritten, no refill)",
          not rm['rows'] and not rm['reset'] and not rm['ins'] and not rm['rem'] and not rr['rows'] and not rr['reset']
          and mt.item(0, 2) is item0 and tl._sync_movements(w) is False, f"{rm} {rr}")

    # ---------------- issue 4 (+ 1): an offset change moves the view / CSV too, only that curve's rows
    off0 = c_case.time_offset
    ml0 = ml_()
    case_rows = {r for r, d in enumerate(ml0) if d['uid'] == uid_case}
    stop_m, stop_r = _model_watch(mt), _model_watch(rt)
    tl.logs_set_time_offset(w, i_case, off0 + 1.5)
    rm, rr = stop_m(), stop_r()
    ok, det = view_matches()
    ml1 = ml_()
    check("4 time offset +1.5 s: the 'Movements' view and its CSV export move with the table and the lanes", ok
          and all(abs(b['t_start'] - a['t_start'] - (1.5 if a['uid'] == uid_case else 0.0)) < 1e-9 for a, b in zip(ml0, ml1)),
          det)
    check("1 the offset change rewrote only the shifted curve's rows, in place, in both tables",
          rm['rows'] == case_rows and not rm['reset'] and not rm['ins'] and rr['rows'] == case_rows and not rr['reset'],
          f"{rm} {rr} (expected rows {sorted(case_rows)})")
    tl.logs_set_value_offset(w, i_case, 0.25)
    ok, det = view_matches()
    rows = st.results['Movements'][1]
    check("4 value offset: the view's start / end values follow, the delta does not change",
          ok and all(abs(r[6] - (a['v_start'] + (0.25 if a['uid'] == uid_case else 0.0))) < 1e-9 and abs(r[8] - a['delta']) < 1e-12
                     for r, a in zip(rows, ml1)), det)
    tl.logs_set_value_offset(w, i_case, 0.0)
    sp = w.logs_toff_spins[i_case]
    sp.setValue(off0 + 0.75)                         # the spin box: debounced redraw
    wait_ms(tl._REDRAW_DELAY_MS + 200)
    ok, det = view_matches()
    check("4 time offset typed in the curves table's spin box (debounced): view and CSV follow after the redraw",
          ok and abs(ml_()[0]['t_start'] - ml0[0]['t_start'] - 0.75) < 1e-9, det)
    tl.logs_auto_align(w, index=i_case)
    ok, det = view_matches()
    check("4 Auto align: view and CSV follow the new offset", ok, det)
    tl.logs_set_time_offset(w, i_case, off0)

    # ---------------- issue 1: one edit rewrites one row (also in a view the user sorted)
    tl.logs_show_results(w, 'Movements')            # (Auto align showed the 'Alignment' view)
    rt.sortItems(3, Qt.DescendingOrder)              # the user sorts the shown view by Start
    pump()
    ml = ml_()
    r_ed = 1
    stop_m, stop_r = _model_watch(mt), _model_watch(rt)
    opened = _edit_cell(mt, r_ed, 3, f"{ml[r_ed]['t_stop'] + 0.5:.3f}")
    rm, rr = stop_m(), stop_r()
    d1 = ml_()[r_ed]
    hdr, rows = st.results['Movements']
    shown = sorted(tuple(rt.item(r, c).text() for c in range(rt.columnCount())) for r in range(rt.rowCount()))
    want = sorted(tuple(tl._fmt_value(v, h) for v, h in zip(row, hdr)) for row in rows)
    starts = [float(rt.item(r, 3).text()) for r in range(rt.rowCount())]
    check("1 a Stop typed in the movements table rewrites that one row of the movements table and of the shown view "
          "(in place: it keeps the user's sort by Start, its cells = the stored rows)",
          opened and d1['edited'] and abs(d1['t_stop'] - ml[r_ed]['t_stop'] - 0.5) < 0.1 and rm['rows'] == {r_ed}
          and not rm['reset'] and len(rr['rows']) == 1 and not rr['reset'] and shown == want
          and starts == sorted(starts, reverse=True), f"{rm} {rr}")
    tl.logs_show_results(w, 'Movements')            # refilled in the stored order
    check("1 the view shown again: refilled in the stored order", [rt.item(r, 3).text() for r in range(rt.rowCount())]
          == [tl._fmt_value(r[3], hdr[3]) for r in st.results['Movements'][1]])

    # ---------------- issue 7: an edit that snaps back onto the same sample stores nothing
    tl.logs_set_roi(w, 20.0, 62.0)
    tl.logs_detect_movements(w, threshold=0.02, settle_time=0.5)
    ml = ml_()
    m3 = ml[2]
    check("7 precondition: the case's 3rd movement is cut by the ROI (incomplete)",
          m3['uid'] == uid_case and not m3['complete'] and 'incomplete' in m3['note'], m3['note'])
    opened = _edit_cell(mt, 2, 2, f"{m3['t_start']:.2f}")
    a3 = ml_()[2]
    check("7 a Start typed that snaps to the sample it is on: nothing stored (not edited, still incomplete, same note "
          "in the table and the view), cell restored, the status line says unchanged",
          opened and not a3['edited'] and not a3['complete'] and a3['note'] == m3['note'] and a3['t_start'] == m3['t_start']
          and mt.item(2, 2).text() == f"{m3['t_start']:.3f}" and st.results['Movements'][1][2][-1] == m3['note']
          and 'unchanged' in w.logs_summary.text() and 'restored' in w.logs_summary.text(), w.logs_summary.text())
    r_ref = next(i for i, d in enumerate(ml) if d['uid'] == uid_ref)
    b = ml[r_ref]
    mt.item(r_ref, 3).setText(f"{b['t_stop'] + 0.3:.1f}")       # sparse G-code rows: the same row
    pump(2)
    a = ml_()[r_ref]
    check("7 curve2: a Stop 0.3 s later snaps to the same G-code row: unchanged, not edited, cell restored",
          not a['edited'] and a['t_stop'] == b['t_stop'] and mt.item(r_ref, 3).text() == f"{b['t_stop']:.3f}"
          and 'unchanged' in w.logs_summary.text(), w.logs_summary.text())
    r = tl.logs_set_movement(w, 2, t_start=m3['t_start'], t_stop=m3['t_stop'])
    a3 = ml_()[2]
    check("7 logs_set_movement onto the samples it is on: returns its values, stores nothing",
          isinstance(r, dict) and r['id'] == m3['id'] and not a3['edited'] and not a3['complete']
          and 'unchanged' in w.logs_summary.text(), w.logs_summary.text())
    tl.logs_clear_roi(w)

    # ---------------- issue 6: pause change / Clear take the movements out of the view too
    tl.logs_detect_movements(w, threshold=0.02, settle_time=0.5)
    rows0 = [list(r) for r in st.results['Movements'][1]]
    tl.logs_add_files(w, [DUMMY])                 # its logged wait gives the pause 1.739 s
    ok, det = view_matches()
    rows = st.results['Movements'][1]
    d_p = st.entries[idx_of(w, 'curve2')].curve.meta['pause_durations'][0]
    check("6 pause length changed: the reference's movements stay in the 'Movements' view and its CSV with the "
          "table, moved by the pause",
          ok and len(rows) == 6 and all(abs(b[3] - a[3] - (d_p if a[0] == 'curve2' else 0.0)) < 1e-6
                                        for a, b in zip(rows0, rows)), det)
    tl.logs_remove_curves(w, [idx_of(w, 'DUMMY')])
    i_case, i_ref = idx_of(w, 'case_02'), idx_of(w, 'curve2')
    check("6 the log removed: the 'Movements' view as before, exactly", view_matches()[0]
          and [list(r) for r in st.results['Movements'][1]] == rows0)
    tl.logs_clear_movements(w)
    names = [w.logs_results_combo.itemText(i) for i in range(w.logs_results_combo.count())]
    check("6 Clear: the 'Movements' view goes too (nothing stale left to export)",
          'Movements' not in st.results and 'Movements' not in names and mt.rowCount() == 0, str(names))

    # ---------------- issue 8: a curve whose movements were all deleted takes no lane
    tl.logs_detect_movements(w, threshold=0.02, settle_time=0.5)
    redraw_now()
    y_ref0 = st.lane_artists[uid_ref]['y0']
    tl.logs_delete_movements(w, [i for i, d in enumerate(ml_()) if d['uid'] == uid_case])
    redraw_now()
    check("8 every movement of the case deleted: no lane for it, curve2's lane moves to the first slot, 1 lane reserved",
          uid_case not in st.lane_artists and y_ref0 > tl._LANE_Y0
          and abs(st.lane_artists[uid_ref]['y0'] - tl._LANE_Y0) < 1e-12 and tl._n_lanes(st) == 1,
          f"y0 {st.lane_artists.get(uid_ref, {}).get('y0')} n_lanes {tl._n_lanes(st)}")

    # ---------------- issue 5: a whole-segment drag keeps the width on sparse G-code rows
    tl.logs_detect_movements(w, threshold=0.02, settle_time=0.5)
    tl.logs_zoom_all(w)
    redraw_now()
    tr = w.logs_ax.transData
    px_s = float(tr.transform((1.0, 0.0))[0] - tr.transform((0.0, 0.0))[0])
    mr = [d for d in ml_() if d['uid'] == uid_ref]
    for k, ds in ((1, 1.6), (1, 3.2), (2, -3.2), (2, 3.2)):
        redraw_now()
        x, y = _lane_px(w, uid_ref, mr[k]['id'], 'mid')
        _qdrag(w, _qpt(w, x, y), _qpt(w, x + ds * px_s, y), steps=10)
        m2 = next(d for d in ml_() if d['id'] == mr[k]['id'])
        check(f"5 whole drag of curve2's sparse movement {k + 1} by {ds:+.1f} s: its width is kept (no sample position "
              f"with the same width there: it stays, not edited)",
              abs(m2['duration'] - mr[k]['duration']) < 1e-9 and (m2['t_start'], m2['t_stop']) == (mr[k]['t_start'], mr[k]['t_stop'])
              and not m2['edited'] and st.drag is None, f"{mr[k]['duration']:.3f} -> {m2['duration']:.3f} s")
    redraw_now()
    x, y = _lane_px(w, uid_ref, mr[1]['id'], 'mid')
    _qdrag(w, _qpt(w, x, y), _qpt(w, x + 3.2 * px_s, y), steps=6, release=False)
    loc = getattr(w.logs_toolbar, 'locLabel', None)
    msg = loc.text() if loc is not None else ''
    QTest.keyClick(cv, Qt.Key_Escape)
    pump(2)
    QTest.mouseRelease(cv, Qt.LeftButton, Qt.NoModifier, _qpt(w, x + 3.2 * px_s, y))
    pump(3)
    check("5 while it cannot follow, the toolbar says why", loc is None or 'stays' in msg, msg)
    mc = [d for d in ml_() if d['uid'] == uid_case]
    redraw_now()
    x, y = _lane_px(w, uid_case, mc[1]['id'], 'mid')
    _qdrag(w, _qpt(w, x, y), _qpt(w, x + 2.0 * px_s, y), steps=10)
    m2 = next(d for d in ml_() if d['id'] == mc[1]['id'])
    tt = c_case.times()
    dt_med = float(np.median(np.diff(tt)))
    check("5 on the dense log a whole drag still moves it (~ +2 s) with its width (within one sample interval)",
          abs(m2['t_start'] - mc[1]['t_start'] - 2.0) < 0.2 and abs(m2['duration'] - mc[1]['duration']) <= dt_med
          and m2['edited'], f"{mc[1]['t_start']:.3f}/{mc[1]['duration']:.4f} -> {m2['t_start']:.3f}/{m2['duration']:.4f}")

    # ---------------- issue 3: a lane-edge drag replaces only the dragged segment's path
    tl.logs_detect_movements(w, threshold=0.02, settle_time=0.5)
    redraw_now()
    lane = st.lane_artists[uid_case]
    col = lane['col']
    paths0 = list(col.get_paths())
    m = ml_()[0]
    j = lane['ids'].index(m['id'])
    x, y = _lane_px(w, uid_case, m['id'], 'stop')
    _qdrag(w, _qpt(w, x, y), _qpt(w, x + 25, y), release=False)
    paths1 = list(col.get_paths())
    moved = st.drag is not None and st.drag.get('started') and paths1[j] is not paths0[j] \
        and float(paths1[j].vertices[:, 0].max()) > m['t_stop'] + 0.5
    others = len(paths1) == len(paths0) and all(paths1[k] is paths0[k] for k in range(len(paths0)) if k != j)
    QTest.keyClick(cv, Qt.Key_Escape)
    pump(2)
    back = col.get_paths()[j] is paths0[j]
    QTest.mouseRelease(cv, Qt.LeftButton, Qt.NoModifier, _qpt(w, x + 25, y))
    pump(3)
    check("3 a lane-edge drag replaces only the dragged segment's path (the lane's other segments stay the same "
          "objects); Escape puts the original back, nothing stored",
          moved and others and back and ml_()[0]['t_stop'] == m['t_stop'] and not ml_()[0]['edited'])

    # ---------------- issue 2: points mode, a click next to another curve's marker
    tl.logs_clear_points(w)
    tl.logs_set_pick_mode(w, 'points')
    c_ref = st.entries[i_ref].curve
    t_ref, v_ref = float(c_ref.times()[3]), float(c_ref.values('SI')[3])       # curve2's corner
    tl.logs_add_point(w, i_case, t_ref)
    redraw_now()
    pid1 = st.points[0]['id']
    dist = float('nan')
    xs = ys = 0.0
    for half in (0.5, 1.0, 1.5, 2.5, 4.0, 8.0, 16.0, 40.0):      # the two 2-7 px apart: inside the drag radius
        w.logs_ax.set_xlim(t_ref - half, t_ref + half)
        redraw_now()
        xm, ym = _marker_px(w, pid1)
        xs, ys = w.logs_ax.transData.transform((t_ref, v_ref))
        dist = math.hypot(xm - xs, ym - ys)
        if 2.0 <= dist <= 7.0:
            break
    n0 = len(st.points)
    QTest.mouseClick(cv, Qt.LeftButton, Qt.NoModifier, _qpt(w, xs, ys))
    pump(3)
    check("2 points mode: a click on curve2's sample next to the log's marker (within its drag radius) adds the point "
          "on curve2, as before the drag feature",
          2.0 <= dist <= tl._DRAG_POINT_PX and len(st.points) == n0 + 1 and st.points[-1]['uid'] == uid_ref
          and 'Point 2: curve2' in w.logs_summary.text(), f"{dist:.1f} px apart; {w.logs_summary.text()}")
    xm, ym = _marker_px(w, pid1)
    QTest.mouseClick(cv, Qt.LeftButton, Qt.NoModifier, _qpt(w, xm, ym))
    pump(3)
    check("2 a click exactly on a marker adds no duplicate; the status line says how to add one next to it",
          len(st.points) == n0 + 1 and 'Point 1 is here' in w.logs_summary.text(), w.logs_summary.text())
    tl.logs_zoom_all(w)
    redraw_now()
    mc = [d for d in ml_() if d['uid'] == uid_case]
    x, y = _lane_px(w, uid_case, mc[0]['id'], 'mid')
    n1 = len(st.points)
    QTest.mouseClick(cv, Qt.LeftButton, Qt.NoModifier, _qpt(w, x, y))
    pump(3)
    check("2 points mode: a click on a movement lane adds a point as any click does (nothing dragged)",
          len(st.points) == n1 + 1 and [(d['t_start'], d['t_stop']) for d in ml_() if d['uid'] == uid_case]
          == [(d['t_start'], d['t_stop']) for d in mc])
    tl.logs_set_pick_mode(w, None)
    n2 = len(st.points)
    xm, ym = _marker_px(w, pid1)
    QTest.mouseClick(cv, Qt.LeftButton, Qt.NoModifier, _qpt(w, xm + 3, ym))
    pump(3)
    check("2 pick mode None: a click on a marker adds nothing", len(st.points) == n2)
    check("no warning box in the sixth-round checks (no-op edits, clicks, drags)", not warnings_since(n_box0),
          str(warnings_since(n_box0)))
    w.close()

    # ---------------- speed with ~3850 movements (3 x 100k-row logs + curve2, band / envelope / diff)
    w = make_window()
    w.resize(1600, 900)
    tl.build_logs_tab(w)
    w.show()
    APP.processEvents()
    st = w.logs_state
    cv = w.logs_canvas
    mt = w.logs_movements_table
    paths = []
    rng = np.random.default_rng(7)
    for k in range(3):
        t_ = np.cumsum(rng.uniform(0.06, 0.094, 100_000))
        held = np.floor(t_ / 0.2) * 0.2
        ph = np.mod(held + 0.3 * k, 6.0)
        si = 25.0 + np.where(ph < 4.0, 1.5 * (1 - np.cos(np.pi * ph / 2.0)), 0.0)
        p = os.path.join(TMP, f"log_r6_many_{k}.csv")
        _write_fast_log(p, t_, si)
        paths.append(p)
    tl.logs_add_files(w, paths)
    tl.logs_add_reference(w, CURVE2)
    tl.logs_set_display(w, show_band=True, show_envelope=True, show_diff=True)
    pump()

    def timed(fn, n=3):
        r = []
        for _ in range(n):
            a = time.perf_counter()
            fn()
            r.append(1000.0 * (time.perf_counter() - a))
            pump(2)
        return float(np.median(r))

    def off_step():
        tl.logs_set_time_offset(w, 0, st.entries[0].curve.time_offset + 0.01)

    def toggle():
        tl.logs_set_display(w, show_probe=not st.show_probe)
    t_off0, t_tog0 = timed(off_step), timed(toggle)
    tl.logs_detect_movements(w)
    pump()
    cv.draw()
    pump()
    n_mv = len(tl.logs_movement_list(w))
    t_off, t_tog = timed(off_step), timed(toggle)
    w.logs_ax.set_xlim(2900.0, 3100.0)
    cv.draw()
    pump()
    uid0 = st.entries[0].uid
    blits = []
    orig_blit = cv.blit

    def timed_blit(bbox=None):
        a = time.perf_counter()
        orig_blit(bbox)
        blits.append(time.perf_counter() - a)
    cv.blit = timed_blit
    lane = st.lane_artists[uid0]
    col = lane['col']
    paths0 = list(col.get_paths())
    m = next(d for d in tl.logs_movement_list(w) if d['uid'] == uid0 and 2950.0 < d['t_stop'] < 3050.0)
    j = lane['ids'].index(m['id'])
    xe, ye = _lane_px(w, uid0, m['id'], 'stop')
    p0 = _qpt(w, xe, ye)
    QTest.mouseMove(cv, p0)
    APP.processEvents()
    QTest.mousePress(cv, Qt.LeftButton, Qt.NoModifier, p0)
    net = []
    for k in range(1, 31):
        n_b = len(blits)
        a = time.perf_counter()
        QTest.mouseMove(cv, p0 + QPoint(k, 0))
        net.append(1000.0 * (time.perf_counter() - a - sum(blits[n_b:])))
    paths1 = list(col.get_paths())
    others = all(paths1[k] is paths0[k] for k in range(len(paths0)) if k != j)
    a = time.perf_counter()
    QTest.mouseRelease(cv, Qt.LeftButton, Qt.NoModifier, p0 + QPoint(30, 0))
    t_rel = 1000.0 * (time.perf_counter() - a)
    pump(3)
    cv.blit = orig_blit
    net = np.sort(np.array(net))[:-1]                # without the first move's background capture
    d_after = next(d for d in tl.logs_movement_list(w) if d['id'] == m['id'])
    print(f"INFO: {n_mv} movements ({len(paths0)} segments in the lane): offset change {t_off0:.0f} -> {t_off:.0f} ms, "
          f"display toggle {t_tog0:.0f} -> {t_tog:.0f} ms (without -> with movements); lane-edge drag per motion event "
          f"without the blit median {np.median(net):.2f} ms, max {net.max():.2f} ms; release (commit + redraw) {t_rel:.0f} ms")
    check("1 ~3850 movements detected, one table row each", n_mv > 3000 and mt.rowCount() == n_mv, str(n_mv))
    check("1 with ~3850 movements a display toggle costs about what it costs without them (< +100 ms; it was ~+700)",
          t_tog - t_tog0 < 100.0, f"{t_tog0:.0f} -> {t_tog:.0f} ms")
    check("1 an offset change that shifts ~1284 rows in both tables: < +450 ms over the same without movements "
          "(it was ~+800)", t_off - t_off0 < 450.0, f"{t_off0:.0f} -> {t_off:.0f} ms")
    check("1 a lane-edge drag release (commit, one row of each table, one redraw) < 600 ms (it was 1.2-2.5 s)",
          t_rel < 600.0 and d_after['edited'] and d_after['t_stop'] > m['t_stop'], f"{t_rel:.0f} ms")
    check("3 lane-edge drag with ~1284 segments in the lane: only the dragged path changes, motion events < 30 ms "
          "without the blit (median < 2 ms)", others and net.max() < 30.0 and np.median(net) < 2.0,
          f"median {np.median(net):.2f} max {net.max():.2f} ms")
    w.close()


# ---------------------------------------------------------------------------
# Round 7: logged sensor waits (log format v2): Show / Remove, the pause period, the colour key,
# overlays across mode switches, analyses on the cut curves, the 'Waits' view, exports,
# synthetic multi-wait logs, performance
# ---------------------------------------------------------------------------
def _tla():
    """scratch/test_log_analysis.py (its v2 log writer write_wait_log and the WAIT3 G-code)."""
    here = os.path.dirname(os.path.abspath(__file__))
    if here not in sys.path:
        sys.path.insert(0, here)
    keep = sys.dont_write_bytecode
    sys.dont_write_bytecode = True                  # no scratch/__pycache__ file from this import
    try:
        import test_log_analysis as tla
    finally:
        sys.dont_write_bytecode = keep
    return tla


def _rgba(c):
    from matplotlib import colors as mcolors
    return np.asarray(mcolors.to_rgba(c), dtype=float)


def _same_rgba(a, b, tol=1e-6):
    return np.allclose(_rgba(a), _rgba(b), atol=tol)


def _drawn_classes(w):
    """Event classes found among the drawn artists (independent of the tab's own bookkeeping)."""
    from matplotlib.collections import PolyCollection
    from matplotlib.lines import Line2D
    st = w.logs_state
    found = set()
    for a in st.artists:
        if isinstance(a, PolyCollection):
            fc = a.get_facecolor()
            if not len(fc) or not a.get_paths():
                continue
            ys = np.concatenate([p.vertices[:, 1] for p in a.get_paths()])
            if ys.max() < 0.5:                       # a movement lane
                continue
            if a.get_hatch() == tl._SENT_HATCH:
                found.add('sent')
            elif a.get_hatch() == tl._GAP_HATCH:
                found.add('gap')
            elif _same_rgba(fc[0], (*_rgba(tl._PROBE_DET_COLOR)[:3], tl._DET_ALPHA)):
                found.add('det')
            elif _same_rgba(fc[0], (*_rgba(tl._PROBE_REL_COLOR)[:3], tl._REL_ALPHA)):
                found.add('rel')
            elif _same_rgba(fc[0], (*_rgba(tl._WAIT_COLOR)[:3], tl._WAIT_ALPHA)):
                found.add('wait')
        elif isinstance(a, Line2D) and len(a.get_xdata()) == 2 and a.get_label().startswith('_'):
            c, ls = a.get_color(), a.get_linestyle()
            if _same_rgba(c, tl._WAIT_COLOR) and ls == '--':
                found.add('not_marked')
            elif _same_rgba(c, tl._WAIT_COLOR) and ls == ':':
                found.add('cut')
            elif _same_rgba(c, tl._READFAIL_COLOR) and ls == ':':
                found.add('read_failed')
            elif _same_rgba(c, tl._PAUSE_COLOR) and ls == '--':
                found.add('pause')
        elif a.__class__.__name__ in ('Rectangle', 'Polygon'):
            if _same_rgba(a.get_facecolor(), (*_rgba(tl._ROI_COLOR)[:3], tl._ROI_ALPHA)):
                found.add('roi')
    return [c for c in tl._KEY_ORDER if c in found]


def _key_ok(w):
    """The colour key lists exactly the drawn event classes (labels in key order) and looks like them."""
    st = w.logs_state
    drawn = _drawn_classes(w)
    key = st.key_artist
    texts = [t.get_text() for t in key.get_texts()] if key is not None else []
    ok = texts == [tl._KEY_LABELS[c] for c in drawn] and st.key_classes == drawn
    if key is not None:
        ok = ok and not key.get_in_layout() and key.get_draggable() and key in w.logs_ax.get_children()
        for h, c in zip(key.legend_handles, drawn):
            if c == 'sent':
                ok = ok and h.get_hatch() == tl._SENT_HATCH
            elif c == 'gap':
                ok = ok and h.get_hatch() == tl._GAP_HATCH
            elif c in ('det', 'rel', 'wait', 'roi'):
                col = {'det': (tl._PROBE_DET_COLOR, tl._DET_ALPHA), 'rel': (tl._PROBE_REL_COLOR, tl._REL_ALPHA),
                       'wait': (tl._WAIT_COLOR, tl._WAIT_ALPHA), 'roi': (tl._ROI_COLOR, tl._ROI_ALPHA)}[c]
                ok = ok and _same_rgba(h.get_facecolor(), (*_rgba(col[0])[:3], col[1]))
            elif c in ('not_marked', 'cut', 'read_failed'):
                col = tl._READFAIL_COLOR if c == 'read_failed' else tl._WAIT_COLOR
                ok = ok and _same_rgba(h.get_color(), col) and h.get_linestyle() == ('--' if c == 'not_marked' else ':')
            elif c == 'pause':
                strips = _pause_strips(w)
                if strips:          # the pause period drawn: the key shows the same strip (and dashed ends)
                    ok = ok and h.__class__.__name__ == 'Rectangle' and _same_rgba(
                        h.get_facecolor(), (*_rgba(tl._PAUSE_COLOR)[:3], tl._PAUSE_STRIP_ALPHA))
                else:
                    ok = ok and h.__class__.__name__ == 'Line2D' and _same_rgba(h.get_color(), tl._PAUSE_COLOR) \
                        and h.get_linestyle() == '--'
    return ok, f"key {texts} / drawn {drawn}"


def _labels_covered(w):
    """[(legend, label text, covered px)] of the vertical pause / cut labels that the colour key or the curve
    legend covers (labels clipped to the axes, as drawn).  Draws the canvas first."""
    from matplotlib.text import Text
    from matplotlib.transforms import Bbox
    st, ax = w.logs_state, w.logs_ax
    w.logs_canvas.draw()
    r = w.logs_canvas.get_renderer()
    out = []
    for a in st.artists:
        if not isinstance(a, Text) or not a.get_text().strip() or a.get_rotation() != 90:
            continue
        bb = Bbox.intersection(a.get_window_extent(r), ax.bbox)
        if bb is None or bb.width <= 0 or bb.height <= 0:
            continue
        for name, box in (('curve legend', ax.get_legend()), ('colour key', st.key_artist)):
            if box is None:
                continue
            kb = box.get_window_extent(r)
            ww = min(kb.x1, bb.x1) - max(kb.x0, bb.x0)
            hh = min(kb.y1, bb.y1) - max(kb.y0, bb.y0)
            if ww > 0 and hh > 0:
                out.append((name, a.get_text().strip(), round(float(hh), 1)))
    return out


def _pause_strips(w):
    """(x0, x1, y0) of the pause-period strips drawn (purple, along the top of the axes)."""
    out = []
    for a in w.logs_state.artists:
        if a.__class__.__name__ == 'Rectangle' and _same_rgba(a.get_facecolor(),
                                                              (*_rgba(tl._PAUSE_COLOR)[:3], tl._PAUSE_STRIP_ALPHA)):
            out.append((float(a.get_x()), float(a.get_x() + a.get_width()), float(a.get_y())))
    return sorted(out)


def _x_ranges(w, pred):
    """x ranges (data) of the full-height PolyCollection paths whose collection matches pred."""
    from matplotlib.collections import PolyCollection
    out = []
    for a in w.logs_state.artists:
        if isinstance(a, PolyCollection) and pred(a):
            out += [(float(p.vertices[:, 0].min()), float(p.vertices[:, 0].max())) for p in a.get_paths()]
    return sorted(out)


def _texts(w, start):
    return [a.get_text() for a in w.logs_state.artists if hasattr(a, 'get_text') and a.get_text().startswith(start)]


def _snapshot(st):
    """Everything about the overlays that a pause-mode switch must not change (recorded time)."""
    pts = [(p['id'], p['uid'], p['axis'], p['t_raw']) for p in st.points]
    mvs = {u: tuple(tuple(m.get(k) or []) for k in ('ids', 'segments', 'edited', 'complete', 'in_gap',
                                                     'start_in_gap', 'stop_in_gap')) + (m.get('axis'),)
           for u, m in st.movements.items()}
    pks = {u: (tuple(np.asarray(p['t_raw'], dtype=float)), tuple(np.asarray(p['v_raw'], dtype=float)), tuple(p['kind']))
           for u, p in st.peaks.items()}
    offs = [(e.uid, e.curve.time_offset, dict(e.curve.value_offsets)) for e in st.entries]
    return pts, mvs, pks, offs, st.roi


def review7_checks():
    from PySide6.QtTest import QTest
    tla = _tla()
    print("\n---- round 7: logged sensor waits (Show / Remove, colour key) ----")
    w = make_window()
    w.resize(1600, 900)
    tl.build_logs_tab(w)
    w.show()
    st = w.logs_state
    cv, ax = w.logs_canvas, w.logs_ax

    def pump(n=5):
        for _ in range(n):
            APP.processEvents()

    def redraw_now():
        cv.draw()
        pump(3)

    tl.logs_add_files(w, [DUMMY])
    tl.logs_add_reference(w, CURVE2)
    i_d, i_ref = idx_of(w, 'DUMMY'), idx_of(w, 'curve2')
    ed, er = st.entries[i_d], st.entries[i_ref]
    redraw_now()

    # ---------------- A. Show (real time): the wait, its uncertainty, the pause period, the key
    w0 = ed.curve.meta['waits'][0]
    check("A Show is the default: curve2's sensor_wait pause = the dummy's logged wait (end - received = 1.7391 s)",
          st.pause_mode == 'show' and w.logs_radio_pause_show.isChecked()
          and er.curve.meta['pause_durations'] == [w0['length']] and abs(w0['length'] - 1.7391) < 1e-9)
    tp = float(er.curve.meta['pauses'][0][1]) + er.curve.time_offset
    spans = _pause_strips(w)
    ends = sorted(round(float(ln.get_xdata()[0]), 6) for ln in ax.get_lines() if ln.get_label().startswith('_')
                  and _same_rgba(ln.get_color(), tl._PAUSE_COLOR) and ln.get_linestyle() == '--')
    check("A 'Show G-code pauses' draws the pause period: a purple strip along the top of 1.739 s from the pause, "
          "dashed lines at both ends, label 'sensor_wait 1.74 s (logged)'",
          len(spans) == 1 and abs(spans[0][0] - tp) < 1e-9 and abs(spans[0][1] - spans[0][0] - 1.7391) < 1e-9
          and abs(spans[0][2] - tl._PAUSE_STRIP[0]) < 1e-12 and ends == [round(tp, 6), round(tp + 1.7391, 6)]
          and _texts(w, ' sensor_wait') == [' sensor_wait 1.74 s (logged)'], f"{spans} {ends} {_texts(w, ' sensor')}")
    amber = _x_ranges(w, lambda a: len(a.get_facecolor()) and not a.get_hatch()
                      and _same_rgba(a.get_facecolor()[0], (*_rgba(tl._WAIT_COLOR)[:3], tl._WAIT_ALPHA)))
    hatched = _x_ranges(w, lambda a: a.get_hatch() == tl._SENT_HATCH)
    check("A the logged wait drawn amber over [received, end] = [10.110, 11.8491] and the window in which the Duet "
          "sent its message hatched over [9.640, 10.110] (the real start lies in it)",
          len(amber) == 1 and np.allclose(amber[0], (10.11, 11.8491)) and len(hatched) == 1
          and np.allclose(hatched[0], (9.64, 10.11)), f"{amber} {hatched}")
    ok, det = _key_ok(w)
    check("A colour key: Release button, Waiting for sensor, Wait message sent, G-code pause (exactly what is drawn, "
          "same look), out of constrained_layout, draggable, on the axes (in saved figures)",
          ok and st.key_classes == ['rel', 'wait', 'sent', 'pause'], det)
    r_ = cv.get_renderer()
    kb, lb, ab = st.key_artist.get_window_extent(r_), ax.get_legend().get_window_extent(r_), ax.get_window_extent(r_)
    check("A the curve legend and the key do not cover each other, both inside the axes (1600x900)",
          not kb.overlaps(lb) and kb.x0 >= ab.x0 - 1 and kb.x1 <= ab.x1 + 1 and lb.x0 >= ab.x0 - 1
          and lb.x1 <= ab.x1 + 1, f"key {kb.bounds} legend {lb.bounds}")
    p_png = os.path.join(TMP, "r7_show.png")
    tl.logs_save_figure(w, p_png)
    check("A saved figure written with the key", os.path.getsize(p_png) > 20000 and st.key_artist is not None)
    tips = (w.logs_chk_probe.toolTip(), w.logs_chk_gaps.toolTip(), w.logs_chk_pauses.toolTip())
    check("A section 2 checkbox tooltips state the colours", 'red' in tips[0] and 'blue' in tips[0]
          and 'amber' in tips[0] and 'hatched' in tips[0] and 'grey' in tips[1].lower() and 'purple' in tips[2].lower())
    for flag in ('show_probe', 'show_pauses'):
        tl.logs_set_display(w, **{flag: False})
        ok, det = _key_ok(w)
        check(f"A {flag} off: the key follows (only the classes still drawn)", ok, det)
        tl.logs_set_display(w, **{flag: True})
    tl.logs_set_roi(w, 30.0, 40.0)
    ok, det = _key_ok(w)
    check("A an ROI drawn: 'Region of interest' in the key", ok and 'roi' in st.key_classes, det)
    tl.logs_clear_roi(w)

    # ---------------- B. Remove logged waits
    t0 = time.perf_counter()
    QTest.mouseClick(w.logs_radio_pause_remove, Qt.LeftButton)
    pump()
    t_sw = time.perf_counter() - t0
    vc = tl._vc(st, ed)
    check("B Remove (radio button): the dummy is shown without its wait (no -1000 row left, 1.7391 s shorter), curve2's "
          "pause 0 s, 'Pause lengths from' disabled",
          st.pause_mode == 'remove' and w.logs_radio_pause_remove.isChecked() and not np.any(vc.probe == -1000)
          and abs((ed.curve.t[-1] - vc.t[-1]) - 1.7391) < 1e-9 and er.curve.meta['pause_durations'] == [0.0]
          and not w.logs_pause_source_combo.isEnabled(), f"switch {t_sw * 1000:.0f} ms")
    line = [ln for ln in ax.get_lines() if ln.get_label() == f"{ed.curve.name} · SI"][0]
    check("B the plotted line is the cut curve (its x = cut time)", np.isclose(np.nanmax(line.get_xdata()), vc.t[-1]))
    redraw_now()
    cuts = [ln for ln in ax.get_lines() if ln.get_label().startswith('_') and _same_rgba(ln.get_color(), tl._WAIT_COLOR)
            and ln.get_linestyle() == ':']
    check("B a thin amber dotted line at the cut (10.110 s), labelled once 'wait removed (1.74 s)'; the G-code pause "
          "'sensor_wait (wait removed)' (its one log's wait was cut there)",
          len(cuts) == 1 and abs(cuts[0].get_xdata()[0] - 10.11) < 1e-9 and _texts(w, ' wait') == [' wait removed (1.74 s)']
          and _texts(w, ' sensor_wait') == [' sensor_wait (wait removed)'], f"{_texts(w, ' wait')}")
    ok, det = _key_ok(w)
    check("B key in Remove mode: 'Wait removed', no 'Waiting for sensor' band", ok and 'cut' in st.key_classes
          and 'wait' not in st.key_classes, det)
    pt_ = w.logs_pause_table
    check("B pause table in Remove mode: length 0, the note says the logged wait was removed (with its length); "
          "summary line says so",
          pt_.item(0, 3).text() == '0.000' and pt_.item(0, 5).text() == 'removed (1.739 s)'
          and 'removed' in w.logs_pause_label.text() and 'logged waits removed' in st.summary, w.logs_pause_label.text())
    QTest.mouseClick(w.logs_radio_pause_show, Qt.LeftButton)
    pump()
    check("B back to Show (radio button): the pause 1.7391 s again, the combo enabled",
          st.pause_mode == 'show' and er.curve.meta['pause_durations'] == [w0['length']]
          and w.logs_pause_source_combo.isEnabled())
    n0 = len(FakeBox.calls)
    check("B logs_set_pause_mode refuses an unknown mode", tl.logs_set_pause_mode(w, 'estimate') is None
          and len(warnings_since(n0)) == 1 and st.pause_mode == 'show')

    # ---------------- C. overlays across Show -> Remove -> Show: nothing moves
    tl.logs_add_files(w, [CASE02])                    # a log without waits next to it
    i_v1 = [k for k, e in enumerate(st.entries) if e.curve.name == 'log_06112026_12_34_12_case_02'][0]
    i_d, i_ref = idx_of(w, 'DUMMY'), idx_of(w, 'curve2')
    tl.logs_detect_movements(w, threshold=0.02, settle_time=0.5)
    ml = tl.logs_movement_list(w)
    md = [d for d in ml if d['uid'] == ed.uid]
    tl.logs_set_movement(w, ml.index(md[0]), t_start=md[0]['t_start'] - 0.5)       # a hand edit
    tl.logs_set_roi(w, 10.5, 13.0)
    tl.logs_add_movement_from_roi(w, i_d)               # its start lies inside the wait (recorded)
    tl.logs_clear_roi(w)
    tl.logs_add_point(w, i_d, 30.0)
    tl.logs_add_point(w, i_d, 11.0)                     # inside the wait
    tl.logs_add_point(w, i_ref, 50.0)
    tl.logs_add_point(w, i_v1, 40.0)
    tl.logs_set_time_offset(w, i_v1, 0.25)
    snap = _snapshot(st)
    ml_show = tl.logs_movement_list(w)
    rows_show = [list(r) for r in st.results['Movements'][1]]
    pts_show = [tl._point_tv(st, p) for p in st.points]
    tl.logs_set_pause_mode(w, 'remove')
    redraw_now()
    ml_rm = tl.logs_movement_list(w)
    tl.logs_set_pause_mode(w, 'show')
    redraw_now()
    check("C Show -> Remove -> Show: every point (t_raw), movement (segments, ids, edited and gap flags), offset and "
          "the ROI exactly as before", _snapshot(st) == snap)
    check("C ... and the movements' numbers, the 'Movements' view and the points' displayed times exactly as before",
          tl.logs_movement_list(w) == ml_show and [list(r) for r in st.results['Movements'][1]] == rows_show
          and [tl._point_tv(st, p) for p in st.points] == pts_show)
    after = [(a, b) for a, b in zip(ml_show, ml_rm) if a['uid'] == ed.uid and a['t_start'] > 12.0]
    check("C in Remove mode the dummy's movements after the wait are shown 1.7391 s earlier, with the same numbers "
          "(duration, delta); the log without waits and its offset are unchanged",
          after and all(abs((a['t_start'] - b['t_start']) - 1.7391) < 1e-6 and a['duration'] == b['duration']
                        and a['delta'] == b['delta'] for a, b in after)
          and [d for d in ml_rm if d['uid'] == st.entries[i_v1].uid] == [d for d in ml_show if d['uid'] == st.entries[i_v1].uid],
          str([(round(a['t_start'], 3), round(b['t_start'], 3)) for a, b in after][:3]))

    # ---------------- D. Remove mode: points and movement edges inside a removed wait, analyses on the cut curves
    tl.logs_set_pause_mode(w, 'remove')
    redraw_now()
    vc = tl._vc(st, ed)
    p_in = st.points[1]
    check("D a point inside a removed wait is not drawn; the points table and the 'Points' view say 'inside a "
          "removed wait'", p_in['id'] not in st.point_artists and w.logs_points_table.item(1, 7).text().startswith(
              'inside a removed wait') and st.results['Points'][1][1][7].startswith('inside a removed wait')
          and all(p['id'] in st.point_artists for k, p in enumerate(st.points) if k != 1))
    n0 = len(FakeBox.calls)
    r = tl.logs_set_point_time(w, 1, 20.0)
    check("D editing that point is refused with a message (nothing changes)", r is None and len(warnings_since(n0)) == 1
          and 'inside a removed wait' in warnings_since(n0)[0][2] and st.points[1]['t_raw'] == p_in['t_raw'])
    ok_e = _edit_cell(w.logs_points_table, 1, 3, "20")
    pump(3)
    check("D typing a time into its cell is refused too: cell restored, reason in the status line",
          ok_e and st.points[1]['t_raw'] == snap[0][1][3] and 'inside a removed wait' in st.summary, st.summary[-120:])
    mv_d = st.movements[ed.uid]
    k_roi = [k for k, (a, b) in enumerate(mv_d['segments']) if 10.5 <= a <= 11.0][0]
    x_lane = st.lane_artists[ed.uid]['ranges'][k_roi]
    check("D a movement edge inside a removed wait is drawn at the cut point (10.110 s)",
          abs(x_lane[0] - (10.11 + ed.curve.time_offset)) < 1e-9, str(x_lane))
    tl.logs_detect_movements(w, threshold=0.02, settle_time=0.5)
    segs = st.movements[ed.uid]['segments']
    cm = vc.meta['cut_map']
    check("D Detect movements in Remove mode: found on the cut curve, stored in recorded time (recorded row times, "
          "none inside the wait); shown = cut(t) + offset",
          segs and all(a in set(ed.curve.t) and b in set(ed.curve.t) and not cm.inside(a) for a, b in segs)
          and all(abs(d['t_start'] - (cm.forward(a) + ed.curve.time_offset)) < 1e-9
                  for d, (a, _) in zip([x for x in tl.logs_movement_list(w) if x['uid'] == ed.uid], segs)))
    tl.logs_set_roi(w, 20.0, 40.0)
    n_before = len(st.movements[ed.uid]['segments'])
    tl.logs_set_roi(w, 14.0, 20.0)
    added = tl.logs_add_movement_from_roi(w, i_d)
    segs = st.movements[ed.uid]['segments']
    check("D Add movement from ROI in Remove mode: the ROI is plot time, the new segment recorded rows (14..20 s "
          "shown = 15.74..21.74 s recorded)", added == 1 and len(segs) == n_before + 1
          and any(abs(a - 15.74) < 0.1 and abs(b - 21.74) < 0.1 and a in set(ed.curve.t) for a, b in segs), str(segs[:3]))
    tl.logs_set_pause_mode(w, 'show')
    check("D the ROI keeps its numbers across a mode switch, and the status line says so",
          st.roi == (14.0, 20.0) and 'ROI keeps its numbers' in st.summary, st.summary)
    tl.logs_set_pause_mode(w, 'remove')
    tl.logs_clear_roi(w)
    pk = tl.logs_find_peaks(w, prominence=0.0, min_distance=0.5, kind='both')
    check("D Find peaks in Remove mode runs on the cut curves (stored in recorded time)", pk is not None)
    tl.logs_set_display(w, show_band=True, show_envelope=True, show_diff=True)
    redraw_now()
    check("D band / envelope / difference drawn on the cut curves", st.band_fills and st.diff_series
          and all(np.all(np.isfinite(t[np.isfinite(d)])) for t, d in st.diff_series))
    cmp_ = tl.logs_compare(w)
    rd = [r for r in cmp_ if r['curve'] == ed.curve.name][0]
    check("D Compare in Remove mode on the cut curve; its results note says the waits were removed",
          finite(rd['rms']) and st.results_notes['Compare'].startswith('Time base: logged sensor waits removed'),
          st.results_notes['Compare'])
    tl.logs_set_time_offset(w, i_d, 0.0)
    res = tl.logs_auto_align(w, all_curves=False, index=i_d)
    check("D Auto-align in Remove mode: the remaining Release delay (-0.6 .. -1.1 s), offset applied after the cut",
          res and -1.1 < res[0]['shift'] < -0.6 and abs(ed.curve.time_offset - res[0]['shift']) < 1e-12,
          str(res and res[0]['shift']))
    tl.logs_set_display(w, show_band=False, show_envelope=False, show_diff=False)
    tl.logs_clear_points(w)
    tl.logs_add_point(w, i_d, 40.0)
    tl.logs_add_point(w, i_ref, 40.0)
    t_d0 = tl._point_tv(st, st.points[0])[0]
    r = tl.logs_align_points(w, 1, 0)
    check("D Align at 2 points in Remove mode: the dummy's offset moves its (cut) point onto curve2's",
          r is not None and abs(tl._point_tv(st, st.points[0])[0] - tl._point_tv(st, st.points[1])[0]) < 1e-9
          and st.points[0]['t_raw'] in set(ed.curve.t), f"{t_d0:.3f}")
    # click-to-add and drags with real mouse events, on the cut curve
    tl.logs_clear_points(w)
    tl.logs_set_pick_mode(w, 'points')
    redraw_now()
    tt_c, vv_c = vc.times(), vc.values('SI')
    i_c = int(np.searchsorted(tt_c, 45.0))
    x_px, y_px = ax.transData.transform((tt_c[i_c], vv_c[i_c]))
    mouse(w, 'button_press_event', x_px, y_px)
    mouse(w, 'button_release_event', x_px, y_px)
    tl.logs_set_pick_mode(w, None)
    pc = st.points[-1] if st.points else None
    check("D click-to-add on the cut curve: the point is stored in recorded time (a recorded row) and shown at "
          "cut(t) + offset", pc is not None and pc['t_raw'] in set(ed.curve.t)
          and abs(tl._point_tv(st, pc)[0] - (cm.forward(pc['t_raw']) + ed.curve.time_offset)) < 1e-9
          if pc is not None and pc['uid'] == ed.uid else pc is not None, str(pc))
    redraw_now()
    if pc is not None:
        x, y = _marker_px(w, pc['id'])
        t_a = tl._point_tv(st, pc)[0]
        _qdrag(w, _qpt(w, x, y), _qpt(w, ax.transData.transform((t_a + 5.0, 0))[0], y))
        e_pc = tl._entry_by_uid(st, pc['uid'])
        check("D a point dragged ~5 s on the cut curve (real mouse events): stored at a recorded row of its log",
              abs(tl._point_tv(st, pc)[0] - t_a - 5.0) < 0.2 and pc['t_raw'] in set(e_pc.curve.t),
              f"{t_a:.3f} -> {tl._point_tv(st, pc)[0]:.3f}")
    redraw_now()
    m1 = [d for d in tl.logs_movement_list(w) if d['uid'] == ed.uid and d['t_start'] > 20.0][0]
    x, y = _lane_px(w, ed.uid, m1['id'], 'start')
    _qdrag(w, _qpt(w, x, y), _qpt(w, ax.transData.transform((m1['t_start'] - 2.0, 0))[0], y))
    k1 = st.movements[ed.uid]['ids'].index(m1['id'])
    a1, b1 = st.movements[ed.uid]['segments'][k1]
    m1b = [d for d in tl.logs_movement_list(w) if d['id'] == m1['id']][0]
    check("D a lane edge dragged ~2 s on the cut curve: stored in recorded time, edited",
          abs(m1b['t_start'] - (m1['t_start'] - 2.0)) < 0.2 and a1 in set(ed.curve.t) and m1b['edited']
          and abs(cm.forward(a1) + ed.curve.time_offset - m1b['t_start']) < 1e-9, f"{m1['t_start']:.3f} -> {m1b['t_start']:.3f}")
    row = [r for r in range(w.logs_movements_table.rowCount())
           if w.logs_movements_table.item(r, 0).data(Qt.UserRole) == m1['id']][0]
    ok_e = _edit_cell(w.logs_movements_table, row, 3, f"{m1b['t_stop'] + 1.0:.3f}")
    pump(3)
    m1c = [d for d in tl.logs_movement_list(w) if d['id'] == m1['id']][0]
    check("D a movement stop typed in its table on the cut curve: stored in recorded time",
          ok_e and abs(m1c['t_stop'] - m1b['t_stop'] - 1.0) < 0.1
          and st.movements[ed.uid]['segments'][k1][1] in set(ed.curve.t), f"{m1b['t_stop']:.3f} -> {m1c['t_stop']:.3f}")
    # exports say whether waits were removed
    p_mv = os.path.join(TMP, "r7_movements.csv")
    tl.logs_export_results(w, p_mv, name='Movements')
    notes, hdr_, rows_ = la.read_rows_csv(p_mv)
    p_al = os.path.join(TMP, "r7_aligned.csv")
    tl.logs_export_aligned(w, p_al)
    raw = open(p_al, encoding='utf-8').read().splitlines()
    back = la.read_trace_log(p_al)
    check("D exports in Remove mode: the results CSV and the aligned CSV say the waits were removed (a '#' note "
          "without ';'), ';' columns, decimal comma; the aligned export reads back",
          any('logged sensor waits removed' in n for n in notes) and len(rows_) == len(tl.logs_movement_list(w))
          and any('logged sensor waits removed' in x for x in raw if x.startswith('#'))
          and not any(';' in x for x in raw if x.startswith('#')) and back.meta['decimal'] == ','
          and back.meta['format'] == 'aligned-export', str(notes))
    tl.logs_set_pause_mode(w, 'show')

    # ---------------- E. 'Waits' results view
    hdr_w, rows_w = st.results['Waits']
    wd = [r for r in rows_w if r[0] == ed.curve.name]
    check("E 'Waits' view: Curve, #, Received, Duet sent from, Duet sent to, Ended, Length, Ended by, Timing note, "
          "-1000 rows; the dummy's wait (the sent window as two numbers, the note with a decimal point)",
          hdr_w == tl._WAITS_HEADERS and len(wd) == 1
          and wd[0][1:8] == [1, 10.11, 9.64, 10.11, 11.849, w0['length'], 'Release button'] and wd[0][9] == 21
          and wd[0][8] == 'exact to one sample, previous sample at 11.777 s', str(wd))
    p_w = os.path.join(TMP, "r7_waits.csv")
    tl.logs_export_results(w, p_w, name='Waits')
    n_w, h_w, r_w = la.read_rows_csv(p_w)
    check("E the 'Waits' view exports (the logs' own recorded run time stated)", h_w == tl._WAITS_HEADERS
          and len(r_w) == len(rows_w) and any("recorded run time" in n for n in n_w), str(n_w))
    w.close()

    # ---------------- F. three synthetic multi-wait v2 logs and their G-code
    w = make_window()
    w.resize(1366, 768)
    tl.build_logs_tab(w)
    w.show()
    st = w.logs_state
    cv, ax = w.logs_canvas, w.logs_ax
    logs = tla._wait_logs(tmp=TMP)
    names = list(logs)
    tl.logs_add_files(w, [logs[n]['path'] for n in names])
    tl.logs_add_reference(w, tla.WAIT3_GCODE, name='wait3')
    tl.logs_set_analysis_axis(w, 'X')
    redraw_now()
    er = st.entries[idx_of(w, 'wait3')]
    curves = {n: st.entries[idx_of(w, n)].curve for n in names}
    wa = curves['log_wait_A'].meta['waits']
    check("F Show: the source is the first log with waits; the G-code pauses get its logged lengths, 0 for the wait "
          "not marked", w.logs_pause_source_combo.currentText() == 'log_wait_A'
          and er.curve.meta['pause_durations'] == [wa[0]['length'], 0.0, wa[1]['length']]
          and [w.logs_pause_source_combo.itemText(k) for k in range(w.logs_pause_source_combo.count())] == names,
          str(er.curve.meta['pause_durations']))
    pt_ = w.logs_pause_table
    check("F pause table: 3 rows; the second says 'wait not marked', ended by is empty; tooltips with the timing",
          pt_.rowCount() == 3 and pt_.item(1, 5).text().startswith('wait not marked') and pt_.item(1, 4).text() == ''
          and pt_.item(0, 4).text() == 'detector 1000' and 'received at' in pt_.item(0, 0).toolTip())
    w.logs_pause_source_combo.setCurrentIndex(1)            # through the widget
    pump()
    wb = curves['log_wait_B'].meta['waits']
    check("F 'Pause lengths from:' log_wait_B (combo): lengths from its waits",
          er.curve.meta['pause_durations'] == [wb[0]['length'], 0.0, wb[1]['length']], str(er.curve.meta['pause_durations']))
    n0 = len(FakeBox.calls)
    check("F logs_set_pause_source refuses the G-code (no logged waits); None = the first log with waits",
          tl.logs_set_pause_source(w, idx_of(w, 'wait3')) is None and len(warnings_since(n0)) == 1
          and tl.logs_set_pause_source(w, None) == 'log_wait_A'
          and er.curve.meta['pause_durations'] == [wa[0]['length'], 0.0, wa[1]['length']])
    redraw_now()
    ok, det = _key_ok(w)
    check("F key with the synthetic logs: detector, waiting, sent window, wait not marked, read failed, G-code pause, "
          "connection gap (= drawn)", ok and set(st.key_classes) >= {'det', 'wait', 'sent', 'not_marked',
                                                                    'read_failed', 'pause', 'gap'}, det)
    r_ = cv.get_renderer()
    kb, lb, ab = st.key_artist.get_window_extent(r_), ax.get_legend().get_window_extent(r_), ax.get_window_extent(r_)
    check("F 1366x768: key and curve legend do not cover each other, inside the axes",
          not kb.overlaps(lb) and kb.x0 >= ab.x0 - 1 and kb.x1 <= ab.x1 + 1, f"key {kb.bounds} legend {lb.bounds}")
    tl.logs_detect_movements(w, threshold=0.02, settle_time=0.5)
    tl.logs_find_peaks(w, prominence=0.0, min_distance=0.5, kind='both')
    for k, n in enumerate(names):
        tl.logs_add_point(w, idx_of(w, n), 9.0 + k)
    tl.logs_add_point(w, idx_of(w, 'wait3'), 12.0)
    snap = _snapshot(st)
    ml_show = tl.logs_movement_list(w)
    t0 = time.perf_counter()
    tl.logs_set_pause_mode(w, 'remove')
    pump()
    t_rm = time.perf_counter() - t0
    vcs = {n: tl._vc(st, st.entries[idx_of(w, n)]) for n in names}
    check("F Remove: no -1000 row left in any log; the G-code pauses 0 s", all(not np.any(c.probe == -1000)
                                                                               for c in vcs.values())
          and er.curve.meta['pause_durations'] == [0.0, 0.0, 0.0], f"{t_rm * 1000:.0f} ms")
    redraw_now()
    labels = _texts(w, ' wait')
    check("F one label per cut position (2), not one per log: 'waits removed (a-b s)'",
          len(labels) == 2 and all(x.startswith(' waits removed (') and '-' in x for x in labels), str(labels))
    shifts = [la.estimate_shift(er.curve, vcs[n], 'X', max_lag=3.0)['shift'] for n in names]
    ens = la.ensemble(list(vcs.values()), 'X', dt=0.02)
    raw_ens = la.ensemble(list(curves.values()), 'X', dt=0.02)
    check("F Remove: every log lines up with the G-code within the staircase / sample error (|shift| < 0.35 s), "
          "and with each other (ensemble STD << as recorded)", all(abs(s) < 0.35 for s in shifts)
          and ens['std_mean'] < 0.25 * raw_ens['std_mean'], f"{np.round(shifts, 3)} {ens['std_mean']:.3f} / "
                                                             f"{raw_ens['std_mean']:.3f}")
    tl.logs_set_pause_mode(w, 'show')
    check("F Show -> Remove -> Show with peaks, movements and points on 3 logs and the G-code: all exactly as before",
          _snapshot(st) == snap and tl.logs_movement_list(w) == ml_show)
    tl.logs_set_pause_mode(w, 'remove')
    pk = tl.logs_find_peaks(w, prominence=0.0, min_distance=0.5, kind='both')
    ea = st.entries[idx_of(w, 'log_wait_A')]
    cma = vcs['log_wait_A'].meta['cut_map']
    tr_ = np.asarray(st.peaks[ea.uid]['t_raw'])
    check("F Find peaks in Remove mode: stored in recorded time (shown = cut(t) + offset = the found times)",
          pk is not None and tr_.size and np.allclose(cma.forward(tr_) + ea.curve.time_offset, pk['log_wait_A']['t'],
                                                      atol=1e-9))
    # a source log whose wait count does not match the G-code: nothing paired
    two = tla.write_wait_log(os.path.join(TMP, "log_wait_two.csv"), la.read_reference_gcode(tla.WAIT3_GCODE.replace(
        'M98 P"0:macros/sensor_wait.g"\nG1 X12', 'G1 X12')), [('marked', 2.0), ('marked', 3.0)], seed=3)
    tl.logs_set_pause_mode(w, 'show')
    tl.logs_add_files(w, [two['path']])
    tl.logs_set_pause_source(w, idx_of(w, 'log_wait_two'))
    check("F a source log with 2 waits for 3 sensor_wait pauses: nothing paired, every pause 0 s, the note says why",
          er.curve.meta['pause_durations'] == [0.0, 0.0, 0.0]
          and all(pt_.item(r, 5).text().startswith('not paired') for r in range(3)), pt_.item(0, 5).text())
    tl.logs_remove_curves(w, [idx_of(w, 'log_wait_two')])
    hdr_w, rows_w = st.results['Waits']
    ra = [r for r in rows_w if r[0] == 'log_wait_A']
    kinds = [r[1] for r in ra]
    check("F 'Waits' view: per log its rows in time order: the failed read, then sensor waits 1, 2 (not marked), 3 "
          "numbered as the G-code pauses they pair with",
          kinds == ['read failed', 1, 2, 3] and len(rows_w) == 12 and [r[2] for r in ra] == sorted(r[2] for r in ra)
          and ra[2][8].startswith('wait not marked') and ra[1][7] == 'detector 1000', str(kinds))
    w.close()

    # ---------------- G. performance: three 100k-row v2 logs + the G-code, band / envelope / difference on
    w = make_window()
    w.resize(1600, 900)
    tl.build_logs_tab(w)
    w.show()
    st = w.logs_state
    ref_long = la.read_reference_gcode(tla.long_wait_gcode(8000.0), name='long')
    paths = []
    for k, (n, plan) in enumerate(tla.WAIT_PLANS.items()):
        paths.append(tla.write_wait_log(os.path.join(TMP, f"{n}_100k.csv"), ref_long, plan, seed=200 + k,
                                        gap=(3000.0 + k, 3001.5 + k), read_fail=500.0)['path'])
    tl.logs_add_files(w, paths)
    tl.logs_add_reference(w, tla.long_wait_gcode(8000.0), name='long')
    tl.logs_set_analysis_axis(w, 'X')
    tl.logs_set_display(w, show_band=True, show_envelope=True, show_diff=True)
    pump()
    n_rows = [e.curve.t.size for e in st.entries if e.curve.kind == 'log']

    def timed(fn, reps=3):
        best = []
        for _ in range(reps):
            t0 = time.perf_counter()
            fn()
            w.logs_canvas.draw()
            best.append(time.perf_counter() - t0)
        return min(best), float(np.median(best))
    rd_show = timed(lambda: tl._do_redraw(w))

    def switch(mode):
        t0 = time.perf_counter()
        tl.logs_set_pause_mode(w, mode)
        t1 = time.perf_counter()
        w.logs_canvas.draw()
        return t1 - t0, time.perf_counter() - t0
    t_sw1, t_sw1p = switch('remove')
    rd_rm = timed(lambda: tl._do_redraw(w))
    t_sw2, t_sw2p = switch('show')
    t_sw4, t_sw4p = switch('remove')
    t_sw3, t_sw3p = switch('show')
    print(f"INFO: perf mode switch incl. the canvas paint: Show->Remove {t_sw1p * 1000:.0f} ms (first), "
          f"Remove->Show {t_sw2p * 1000:.0f} ms, Show->Remove {t_sw4p * 1000:.0f} ms, Remove->Show {t_sw3p * 1000:.0f} ms")
    print(f"INFO: perf 3 x {min(n_rows)}..{max(n_rows)}-row v2 logs + G-code, band / envelope / difference on: redraw "
          f"Show {rd_show[0] * 1000:.0f} ms (median {rd_show[1] * 1000:.0f}), Remove {rd_rm[0] * 1000:.0f} ms (median "
          f"{rd_rm[1] * 1000:.0f}); mode switch Show->Remove {t_sw1 * 1000:.0f} ms (first, cuts made), "
          f"Remove->Show {t_sw2 * 1000:.0f} ms, again {t_sw3 * 1000:.0f} ms (each incl. its redraw, before the "
          f"canvas paint)")
    w.logs_canvas.draw()
    r_ = w.logs_canvas.get_renderer()
    for mode in ('show', 'remove'):
        tl.logs_set_pause_mode(w, mode)
        w.logs_canvas.draw()
        kb, lb = st.key_artist.get_window_extent(r_), w.logs_ax.get_legend().get_window_extent(r_)
        cov = _labels_covered(w)
        check(f"G heavy plot ({mode}): both legends skip the slow data test, the key and the curve legend do not cover "
              f"each other nor any pause / cut label (they sit at the start of the 8000 s run)",
              st.key_artist._logs_heavy and w.logs_ax.get_legend()._logs_heavy and not kb.overlaps(lb) and not cov,
              f"key {kb.bounds} legend {lb.bounds} covered {cov}")
    tl.logs_set_pause_mode(w, 'show')
    check("G performance: 3 x 100k rows + G-code with band / envelope / difference: mode switch well under 1 s, "
          "redraws < 1.5 s", min(n_rows) > 99_000 and max(t_sw1p, t_sw2p, t_sw3p, t_sw4p) < 1.0
          and max(rd_show[0], rd_rm[0]) < 1.5, f"{t_sw1:.2f} / {t_sw2:.2f} / {t_sw3:.2f} s")
    w.close()

    # ---------------- H. layout of the pause table and the two legends (Windows fonts, from the layout probe)
    lay = _LAYOUT_CACHE.get('lay') or {}
    for key_ in ('1600x900', '1366x768'):
        d = (lay.get(key_) or {}).get('waits') or {}
        dr = (lay.get(key_) or {}).get('waits_remove') or {}
        if not d:
            print(f"INFO: layout probe without wait measurements ({key_}): skipped")
            continue
        check(f"H {key_}: pause table '#'..'Ended by' visible without sideways scroll, left panel not scrolling "
              f"sideways, pause label fits", d['pause_cols'] <= d['pause_viewport'] and d['left_hscroll'] == 0
              and d['label_fits'], str({k: d[k] for k in ('pause_cols', 'pause_viewport', 'left_hscroll')}))
        check(f"H {key_}: the key and the curve legend do not cover each other (Show and Remove), inside the axes, "
              f"over little data", all(x and not x['overlap'] and x['inside'] and x['data_frac'] < 0.05
                                       for x in (d, dr)), str({k: (d.get(k), dr.get(k)) for k in ('overlap', 'data_frac')}))
    shutil.rmtree(tla.TMP, ignore_errors=True)


def _comma_numbers(texts):
    """Numbers written with a decimal comma ('11,777') in on-screen texts (the tab shows '.' everywhere)."""
    import re
    rx = re.compile(r'(?<![\w.,])\d+,\d+(?![\w,])')
    return [t for t in texts if t and rx.search(t)]


def _table_texts(tbl, tips=True):
    out = []
    for r in range(tbl.rowCount()):
        for c in range(tbl.columnCount()):
            it = tbl.item(r, c)
            if it is not None:
                out.append(it.text())
                if tips:
                    out.append(it.toolTip())
    return out


def review8_checks():
    """Round 8 (verifier findings on the logged-wait feature): one regression check per issue."""
    import re
    from PySide6.QtGui import QFontMetrics
    from PySide6.QtTest import QTest
    from matplotlib import colors as mcolors
    tla = _tla()
    print("\n---- round 8: verifier findings (logged waits, key, exports) ----")

    def window(wh=(1600, 900)):
        w = make_window()
        w.resize(*wh)
        tl.build_logs_tab(w)
        w.show()
        for _ in range(5):
            APP.processEvents()
        return w

    def pump(n=5):
        for _ in range(n):
            APP.processEvents()

    # ---------------- issue 12: the pause period stays purple on top of the amber band; the key shows the same
    w = window()
    st, ax, cv = w.logs_state, w.logs_ax, w.logs_canvas
    tl.logs_add_files(w, [DUMMY])
    tl.logs_add_reference(w, CURVE2)
    ed, er = st.entries[idx_of(w, 'DUMMY')], st.entries[idx_of(w, 'curve2')]
    tp = float(er.curve.meta['pauses'][0][1])
    ax.set_xlim(7.0, 15.0)
    cv.draw()
    pump()
    buf = np.asarray(cv.buffer_rgba()).copy()
    H = buf.shape[0]

    def rgb(t, yfrac):
        x = ax.transData.transform((t, 0))[0]
        y = ax.transAxes.transform((0, yfrac))[1]
        return np.array(buf[int(round(H - y)), int(round(x)), :3], dtype=int)
    y_strip = 0.5 * sum(tl._PAUSE_STRIP)
    c_strip, c_mid, c_amber = rgb(10.85, y_strip), rgb(10.85, 0.5), rgb(11.8, 0.5)
    pure = np.array([round(255 * (1 - tl._PAUSE_STRIP_ALPHA) + c * 255 * tl._PAUSE_STRIP_ALPHA)
                     for c in mcolors.to_rgb(tl._PAUSE_COLOR)])
    r_ = cv.get_renderer()
    key = st.key_artist
    i_p = [t.get_text() for t in key.get_texts()].index(tl._KEY_LABELS['pause'])
    hb = key.legend_handles[i_p].get_window_extent(r_)
    c_key = np.array(buf[int(round(H - (hb.y1 - 0.15 * hb.height))), int(round((hb.x0 + hb.x1) / 2)), :3], dtype=int)
    check("12 Show: the pause period is a purple strip along the top (rendered purple over the amber band, no "
          "purple / amber mix below it: mid-height is the amber band's colour)",
          c_strip[2] > 150 and abs(int(c_strip[0]) - int(c_strip[2])) < 60 and c_strip[1] < 200
          and np.array_equal(c_mid, c_amber), f"strip {c_strip} mid {c_mid} amber {c_amber}")
    check("12 the key's 'G-code pause' handle is drawn like the period (the same purple strip colour over white "
          "as the plot strip over white, dashed ends)", np.abs(c_key - pure).max() <= 6
          and key.legend_handles[i_p].__class__.__name__ == 'Rectangle', f"{c_key} vs {pure}")
    lab = [a for a in st.artists if hasattr(a, 'get_text') and a.get_text().endswith('(logged)')]
    check("12 the label starts below the strip, inside the period (not over the hatched window before it), on a "
          "light box", len(lab) == 1 and lab[0].get_ha() == 'left' and abs(lab[0].get_position()[0] - tp) < 1e-9
          and lab[0].get_position()[1] < tl._PAUSE_STRIP[0] and lab[0].get_bbox_patch() is not None)

    # ---------------- issue 15: no decimal comma on screen
    pt = w.logs_pause_table
    tl.logs_show_results(w, 'Waits')
    ct = w.logs_curves_table
    bad = _comma_numbers(_table_texts(pt) + _table_texts(w.logs_results_table, tips=False)
                         + [ct.item(r, 6).toolTip() for r in range(ct.rowCount()) if ct.item(r, 6) is not None])
    check("15 no number with a decimal comma on screen (pause table and tooltips, 'Waits' view, curves table Info "
          "tooltip): the notes' '11,777 s' is shown '11.777 s'", not bad and any('11.777 s' in x for x in _table_texts(pt)),
          str(bad[:3]))

    # ---------------- issue 10: the 'Pauses' view follows the reference's offset at once
    tl.logs_show_results(w, 'Pauses')
    hp = st.results['Pauses'][0]
    i_st = hp.index('Start on plot (s)')
    tl.logs_set_time_offset(w, idx_of(w, 'curve2'), 1.5)
    p_csv = os.path.join(TMP, "r8_pauses.csv")
    tl.logs_export_results(w, p_csv, 'Pauses')
    _, h_csv, r_csv = la.read_rows_csv(p_csv)
    check("10 'Pauses' view: 'Start on plot (s)' follows the reference's time offset at once (table, view, export)",
          abs(st.results['Pauses'][1][0][i_st] - 11.49) < 1e-9 and w.logs_results_table.item(0, i_st).text() == '11.490'
          and abs(float(r_csv[0][i_st]) - 11.49) < 1e-9 and 'on the plot at 11.490 s' in pt.item(0, 2).toolTip())
    # ---------------- issues 6 / 16: 'G-code t (s)' is the planner time
    check("6/16 'G-code t (s)' = the planner time of the pause (9.990 s) in the pause table and the 'Pauses' view, "
          "whatever the offset", pt.horizontalHeaderItem(2).text() == 'G-code t (s)' and pt.item(0, 2).text() == '9.990'
          and st.results['Pauses'][1][0][2] == 9.99 and hp[2] == 'G-code t (s)')
    tl.logs_set_time_offset(w, idx_of(w, 'curve2'), 0.0)

    # ---------------- issue 11: a point on the row that ended the wait, with any offset
    off = 4.504636963259353
    tl.logs_set_time_offset(w, idx_of(w, 'DUMMY'), off)
    tl.logs_add_point(w, idx_of(w, 'DUMMY'), 11.8491 + off)
    p11 = st.points[-1]
    tl.logs_set_pause_mode(w, 'remove')
    check("11 a point put in Show mode on the trigger row (offset 4.5046... s) is stored on that row exactly and is "
          "shown / editable in Remove mode (that row is kept)", p11['t_raw'] == 11.8491 and p11['id'] in st.point_artists
          and w.logs_points_table.item(len(st.points) - 1, 7).text() == '')
    p11['t_raw'] = float(np.nextafter(11.8491, 0.0))          # an ulp below the row (older state / float rounding)
    tl.logs_redraw(w)
    check("11 ... an ulp below that row is still the kept row (not 'inside a removed wait')",
          p11['id'] in st.point_artists and not tl._in_removed(st, ed, p11['t_raw']))
    tl.logs_set_pause_mode(w, 'show')
    tl.logs_clear_points(w)
    tl.logs_set_time_offset(w, idx_of(w, 'DUMMY'), 0.0)

    # ---------------- issue 8: editing / dragging one edge keeps the other edge's recorded time
    i_d = idx_of(w, 'DUMMY')
    tl.logs_set_analysis_axis(w, 'SI')

    def roi_movement(a, b):
        tl.logs_clear_movements(w)
        tl.logs_set_roi(w, a, b)
        tl.logs_add_movement_from_roi(w, i_d)
        tl.logs_clear_roi(w)
        return st.movements[ed.uid]
    mv = roi_movement(8.0, 11.0)
    seg0 = tuple(mv['segments'][0])
    cm = ed.curve.meta['waits'][0]['cut']
    tl.logs_set_pause_mode(w, 'remove')
    tl.logs_set_movement(w, 0, t_start=7.5)
    s_api = tuple(mv['segments'][0])
    check("8 Remove mode, stop inside the wait: logs_set_movement(t_start=...) keeps the stop's recorded time",
          cm[0] <= seg0[1] < cm[1] and s_api[1] == seg0[1] and s_api[0] != seg0[0], f"{seg0} -> {s_api}")
    tl.logs_set_pause_mode(w, 'show')
    mv = roi_movement(8.0, 11.0)
    tl.logs_set_pause_mode(w, 'remove')
    redraw = tl.logs_redraw
    redraw(w)
    pump()
    ok_e = _edit_cell(w.logs_movements_table, 0, 2, "7.5")
    pump(3)
    s_tab = tuple(mv['segments'][0])
    check("8 ... the Start cell typed with the real table editor: the stop keeps its recorded time",
          ok_e and s_tab[1] == seg0[1] and abs(s_tab[0] - 7.5) < 0.1, f"{seg0} -> {s_tab}")
    tl.logs_set_pause_mode(w, 'show')
    mv = roi_movement(8.0, 11.0)
    tl.logs_set_pause_mode(w, 'remove')
    cv.draw()
    pump()
    mid = mv['ids'][0]
    x, y = _lane_px(w, ed.uid, mid, 'start')
    _qdrag(w, _qpt(w, x, y), _qpt(w, ax.transData.transform((tl._r2d(st, ed, seg0[0]) - 1.0, 0))[0], y))
    s_drag = tuple(mv['segments'][0])
    check("8 ... the start edge dragged ~1 s on the plot (real mouse events): the stop keeps its recorded time",
          s_drag[1] == seg0[1] and s_drag[0] < seg0[0] - 0.5 and mv['edited'][0], f"{seg0} -> {s_drag}")
    tl.logs_set_pause_mode(w, 'show')
    d_show = [d for d in tl.logs_movement_list(w) if d['id'] == mid][0]
    check("8 ... back in Show the movement still stops where it did (10.944 s), only its start moved",
          abs(d_show['t_stop'] - seg0[1]) < 1e-9, f"{d_show['t_start']:.4f}-{d_show['t_stop']:.4f}")
    # the mirror case: the START inside the wait, the stop edited
    mv = roi_movement(11.0, 14.0)
    seg1 = tuple(mv['segments'][0])
    tl.logs_set_pause_mode(w, 'remove')
    tl.logs_set_movement(w, 0, t_stop=tl._r2d(st, ed, seg1[1]) + 1.0)
    s_m = tuple(mv['segments'][0])
    check("8 Remove mode, start inside the wait: setting only the stop keeps the start's recorded time",
          cm[0] <= seg1[0] < cm[1] and s_m[0] == seg1[0] and s_m[1] > seg1[1] + 0.5, f"{seg1} -> {s_m}")
    tl.logs_set_movement(w, 0, t_start=tl._r2d(st, ed, s_m[0]) - 0.5, t_stop=tl._r2d(st, ed, s_m[1]))
    check("8 both edges typed: both snap to shown samples (recorded rows outside the wait)",
          not tl._in_removed(st, ed, mv['segments'][0][0]) and mv['segments'][0][0] in set(ed.curve.t))
    tl.logs_set_pause_mode(w, 'show')
    tl.logs_clear_movements(w)

    # ---------------- issue 9: visibility in Remove mode: summary, notes and plot label agree with a rebuild
    tl.logs_set_pause_mode(w, 'remove')

    def views():
        return (w.logs_pause_label.text(), [pt.item(0, c).text() for c in range(pt.columnCount())],
                _texts(w, ' sensor_wait'), [list(r) for r in st.results['Pauses'][1]])
    for on in (False, True):
        it = w.logs_curves_table.item(i_d, 0)
        it.setCheckState(Qt.Checked if on else Qt.Unchecked)          # the curves table's Show checkbox
        pump()
        shown = views()
        tl._refresh_pause_table(w, rebuild=True)
        tl._refresh_pauses_view(w)
        tl.logs_redraw(w)
        check(f"9 Remove mode, dummy {'shown again' if on else 'hidden'} by its checkbox: pause summary, pause table, "
              f"plot label and 'Pauses' view equal a rebuild and agree ({shown[1][5]!r}, {shown[2]})",
              shown == views() and (shown[1][5] == 'removed (1.739 s)') == on
              and (on or shown[1][5] == 'not removed: the log with this wait is hidden')
              and (shown[2] == [' sensor_wait (wait removed)']) == on
              and (on or shown[2] == [' sensor_wait (no logged wait)']), str(shown[:3]))
    tl.logs_set_pause_mode(w, 'show')

    # ---------------- issues 2 / 17: results views and the time base on screen
    tl.logs_add_files(w, [CASE02])
    tl.logs_set_reference(w, idx_of(w, 'curve2'))
    tl.logs_compare(w)
    tl.logs_find_peaks(w, prominence=0.0, min_distance=0.5, kind='both')
    tl.logs_auto_align(w, all_curves=False, index=idx_of(w, 'DUMMY'))
    note = w.logs_results_note
    tl.logs_show_results(w, 'Compare')
    cap0, style0 = note.text(), note.styleSheet()
    rows_c0 = [list(r) for r in st.results['Compare'][1]]
    tl.logs_set_pause_mode(w, 'remove')
    cap1, style1 = note.text(), note.styleSheet()
    check("2/17 the caption above the results shows the view's time base (grey); after Show -> Remove a Compare made "
          "in real time is marked in orange: computed in real time, run Compare again (numbers unchanged)",
          cap0.startswith('Time base: as recorded') and '#607d8b' in style0 and cap1.startswith('Computed in real time')
          and 'run Compare again' in cap1 and '#e65100' in style1
          and [list(r) for r in st.results['Compare'][1]] == rows_c0, f"{cap0[:60]} | {cap1[:90]}")
    stale = {n: tl._results_stale(st, n) for n in st.results}
    check("2/17 Compare, Alignment and Peaks & periods are marked stale; the views rebuilt from the state (Pauses, "
          "Waits, Movements, Points, Peak list) never are",
          stale.get('Compare') and stale.get('Alignment') and stale.get('Peaks & periods')
          and not any(stale.get(n) for n in tl._LIVE_VIEWS), str(stale))
    i_cmb = w.logs_results_combo.findText('Alignment')
    check("2/17 the results combo's item tooltip says it too", 'run Auto-align again' in str(
        w.logs_results_combo.itemData(i_cmb, Qt.ToolTipRole)))
    p_st = os.path.join(TMP, "r8_compare_stale.csv")
    tl.logs_export_results(w, p_st, 'Compare')
    n_st, _, _ = la.read_rows_csv(p_st)
    check("2/17 the export of a stale view keeps the time base of its numbers and says the plot is in another one",
          any(n.startswith('Time base: as recorded') for n in n_st) and any(n.startswith('Computed in real time')
                                                                            for n in n_st), str(n_st))
    tl.logs_compare(w)
    tl.logs_show_results(w, 'Compare')
    check("2/17 Compare run again in Remove mode: not stale, the caption says the waits were removed",
          not tl._results_stale(st, 'Compare') and note.text().startswith('Time base: logged sensor waits removed')
          and '#607d8b' in note.styleSheet(), note.text()[:80])
    tl.logs_set_pause_mode(w, 'show')
    check("2/17 ... and back in Show it is marked (computed with the waits removed)",
          tl._results_stale(st, 'Compare') and note.text().startswith('Computed with the logged waits removed'),
          note.text()[:80])
    tl.logs_show_results(w, 'Waits')
    check("17 the 'Waits' view's caption: the logs' own recorded run time", 'recorded run time' in note.text())

    # ---------------- issue 7: aligned export in Remove mode (a cut log next to an uncut one) read back
    tl.logs_set_pause_mode(w, 'remove')
    p_al = os.path.join(TMP, "r8_aligned_remove.csv")
    tl.logs_export_aligned(w, p_al)
    back = la.read_trace_log(p_al)
    kd = [k for k in back.data if 'DUMMY' in k][0]
    kv = [k for k in back.data if k.endswith('case_02')][0]
    t_end_cut = float(tl._vc(st, ed).times()[-1])
    t_beg_cut = float(tl._vc(st, ed).times()[0])
    vd = back.data[kd]
    check("7 aligned export (Remove mode) read back: the cut log's column is empty after its own end (no value held "
          "for the 1.7 s it does not have); the uncut log's column runs to its end",
          np.isnan(vd[back.t > t_end_cut + 0.011]).all()
          and np.isfinite(vd[(back.t > t_beg_cut + 0.011) & (back.t < t_end_cut - 0.011)]).all()
          and np.isfinite(back.data[kv][back.t > 0.06]).all() and back.t[-1] > t_end_cut + 1.0, f"{t_end_cut:.3f} {back.t[-1]:.3f}")
    raw = open(p_al, encoding='utf-8').read().splitlines()
    notes_al = [x for x in raw if x.startswith('#')]
    check("3 aligned export notes: ASCII only, decimal comma, '-' (no en dash), no ';'",
          all(x.isascii() and ';' not in x and not re.search(r'\d\.\d', x) for x in notes_al), str(notes_al))
    tl.logs_set_pause_mode(w, 'show')
    w.close()

    # ---------------- issues 3 / 5: the 'Waits' view and its export
    w = window()
    st = w.logs_state
    src = open(DUMMY, encoding='utf-8', newline='').read()
    before = src.replace("(Duet sent it between 9,640 and 10,110 s)", "(Duet sent it before 10,110 s (no earlier read))")
    p_b = os.path.join(TMP, "log_r8_before.csv")
    open(p_b, 'w', encoding='utf-8', newline='').write(before)
    logs = tla._wait_logs(tmp=TMP)
    tl.logs_add_files(w, [DUMMY, p_b] + [logs[n]['path'] for n in logs])
    hdr_w, rows_w = st.results['Waits']
    ra = [r for r in rows_w if r[0] == 'log_wait_A']
    check("5 'Waits' view: each log's rows in time order; '#' numbers the sensor waits (marked and not marked) as the "
          "G-code pauses they pair with; a failed read is 'read failed'",
          [r[1] for r in ra] == ['read failed', 1, 2, 3] and [r[2] for r in ra] == sorted(r[2] for r in ra)
          and ra[2][8].startswith('wait not marked'), str([(r[1], r[2]) for r in ra]))
    rb = [r for r in rows_w if r[0] == 'log_r8_before'][0]
    check("3 'Duet sent from (s)' / 'Duet sent to (s)' are numbers; 'before 10.110 s (no earlier read)' gives an empty "
          "'from' and the note says so", hdr_w[3:5] == ['Duet sent from (s)', 'Duet sent to (s)']
          and isinstance(rows_w[0][3], float) and rows_w[0][3] == 9.64 and math.isnan(rb[3]) and rb[4] == 10.11
          and 'before 10.110 s (no earlier read)' in rb[8], str(rb))
    p_w = os.path.join(TMP, "r8_waits.csv")
    tl.logs_export_results(w, p_w, 'Waits')
    txt = open(p_w, encoding='utf-8').read()
    lines = txt.splitlines()
    cells = [c for l in lines if not l.startswith('#') for c in l.split(';')]
    check("3 'Waits' export: ASCII only (Excel reads a file without BOM as cp1252), no '.' decimal anywhere (numbers "
          "and notes: '11,777 s', '9,64'), the window as two numeric columns",
          txt.isascii() and not any(re.search(r'(?<![\w.])\d+\.\d+(?![\w.])', c) for c in cells)
          and 'previous sample at 11,777 s' in txt and ';9,64;10,11;' in txt, lines[4][:120])
    w.close()

    # ---------------- issue 13: Remove-mode labels and notes per pause, not per plot
    w = window()
    st = w.logs_state
    tl.logs_add_files(w, [logs[n]['path'] for n in logs])
    tl.logs_add_reference(w, tla.WAIT3_GCODE, name='wait3')
    tl.logs_set_analysis_axis(w, 'X')
    tl.logs_find_peaks(w, prominence=0.0, min_distance=0.5, kind='both')
    n_pk = sum(len(p['kind']) for p in st.peaks.values())
    for mode in ('remove', 'show'):
        tl.logs_set_pause_mode(w, mode)
        w.logs_canvas.draw()
        hdr_pl, rows_pl = st.results['Peak list']
        listed = sorted(r[4] for r in rows_pl if math.isfinite(r[4]))
        drawn = sorted(float(x) for ln in w.logs_ax.get_lines() if ln.get_marker() in ('^', 'v')
                       and ln.get_linestyle() == 'None' for x in ln.get_xdata())
        hidden = [r for r in rows_pl if not math.isfinite(r[4])]
        check(f"2 'Peak list' follows the plot after switching to {mode}: its times are exactly where the peaks are "
              f"drawn; {'a peak inside a removed wait (a wait plateau) is listed with its note' if mode == 'remove' else 'all shown'}",
              len(rows_pl) == n_pk and listed == drawn and hdr_pl[-1] == 'Note'
              and ((mode == 'remove') == bool(hidden)) and all(r[7].startswith('inside a removed wait') for r in hidden),
              f"{len(listed)} listed / {len(drawn)} drawn / {len(hidden)} hidden of {n_pk}")
    tl.logs_set_pause_mode(w, 'remove')
    pt = w.logs_pause_table
    labs = sorted((round(a.get_position()[0], 3), a.get_text()) for a in st.artists
                  if hasattr(a, 'get_text') and a.get_text().startswith(' sensor_wait'))
    check("13 Remove, 3 logs whose 2nd wait was not marked: 'waits removed' only at pauses 1 and 3, pause 2 says "
          "'wait not marked: not removed' (plot labels and pause-table notes)",
          [t for _, t in labs] == [' sensor_wait (waits removed)', ' sensor_wait (wait not marked: not removed)',
                                   ' sensor_wait (waits removed)']
          and pt.item(0, 5).text().startswith('removed (') and pt.item(1, 5).text().startswith(
              'no wait removed here: wait not marked') and pt.item(2, 5).text().startswith('removed ('), str(labs))
    fm = QFontMetrics(pt.font())
    check("16 Remove-mode notes are short: 'removed (2.151-4.500 s)' fits its column", fm.horizontalAdvance(
        pt.item(0, 5).text()) + 8 <= pt.columnWidth(5), f"{pt.item(0, 5).text()} {pt.columnWidth(5)}")
    lost = tla.write_wait_log(os.path.join(TMP, "log_wait_lost.csv"), la.read_reference_gcode(tla.WAIT3_GCODE.replace(
        'M98 P"0:macros/sensor_wait.g"\nG1 X12', 'G1 X12')), [('marked', 3.0), ('marked', 2.0)], seed=5)
    for n in list(logs):
        tl.logs_set_visible(w, idx_of(w, n), False)
    tl.logs_add_files(w, [lost['path']])
    labs = [a.get_text() for a in st.artists if hasattr(a, 'get_text') and a.get_text().startswith(' sensor_wait')]
    cuts = _texts(w, ' wait removed')
    check("13 Remove, a log with 2 waits for 3 sensor_wait pauses (one lost): no pause claims a removal ('not paired: "
          "no wait removed here'); its 2 cuts keep their own labels; the notes say why",
          labs == [' sensor_wait (not paired: no wait removed here)'] * 3 and len(cuts) == 2
          and all(pt.item(r, 5).text().startswith('no wait removed here: not paired') for r in range(3)),
          f"{labs} {cuts} {pt.item(0, 5).text()}")
    tl.logs_set_visible(w, idx_of(w, 'log_wait_A'), True)
    labs = [a.get_text() for a in st.artists if hasattr(a, 'get_text') and a.get_text().startswith(' sensor_wait')]
    check("13 ... with log_wait_A shown too: 'waits removed from 1 of 2 logs' at pauses 1 and 3",
          labs[0] == ' sensor_wait (waits removed from 1 of 2 logs)' and labs[2] == labs[0], str(labs))
    w.close()

    # ---------------- issue 14: the legends keep clear of the pause / cut labels
    for wh in ((1366, 768), (1600, 900)):
        w = window(wh)
        st = w.logs_state
        tl.logs_add_files(w, [DUMMY])
        tl.logs_add_reference(w, CURVE2)
        pump()
        cov = {}
        for mode in ('show', 'remove'):
            tl.logs_set_pause_mode(w, mode)
            tl.logs_zoom_all(w)
            cov[mode] = _labels_covered(w)
        tl.logs_set_pause_mode(w, 'show')
        tl.logs_clear_all(w)
        tl.logs_add_files(w, [logs[n]['path'] for n in logs])
        tl.logs_add_reference(w, tla.WAIT3_GCODE, name='wait3')
        tl.logs_set_analysis_axis(w, 'X')
        for mode in ('show', 'remove'):
            tl.logs_set_pause_mode(w, mode)
            w.logs_ax.set_xlim(0.0, 20.0)
            cov['syn_' + mode] = _labels_covered(w)
        check(f"14 {wh[0]}x{wh[1]}: neither the curve legend nor the colour key covers a pause / cut label (dummy full "
              f"view, 3 synthetic logs zoomed to 0..20 s; Show and Remove)", not any(cov.values()), str(cov))
        w.close()

    # ---------------- issue 1: an Excel-saved v2 log loads with its noted wait
    p_x = os.path.join(TMP, "log_r8_excel.csv")
    lines = src.split('\r\n')
    width = max(l.count(';') for l in lines if l and not l.startswith('#'))
    out = ['"' + l.replace('"', '""') + '"' + ';' * width if l.startswith('#') and '"' in l else l for l in lines]
    open(p_x, 'w', encoding='utf-8', newline='').write('\r\n'.join(out))
    w = window()
    tl.logs_add_files(w, [p_x])
    st = w.logs_state
    wx = st.entries[0].curve.meta['waits']
    check("1 an Excel-saved v2 log (quoted '#' lines) loads: its wait from the notes (sent window 9.640-10.110 s), "
          "status '1 logged sensor wait (1.74 s)'",
          len(wx) == 1 and wx[0]['source'] == 'notes' and wx[0]['sent_from'] == 9.64
          and '1 logged sensor wait (1.74 s)' in st.summary, st.summary)
    w.close()


# ---------------------------------------------------------------------------------------------
# Round 9: the recheck of round 8 (time-base notes of a hidden cut log, stale marks without waits,
# 'Peak list' rewritten in place)
# ---------------------------------------------------------------------------------------------
def _table_matches_rows(tbl, headers, rows):
    """The results table shows exactly `rows`: each table row is the stored row of its column-0
    UserRole (each once), every cell's text = _fmt_value and its sort key = _num_key.  (ok, detail)"""
    if tbl.rowCount() != len(rows) or tbl.columnCount() != len(headers):
        return False, f"table {tbl.rowCount()}x{tbl.columnCount()} vs {len(rows)}x{len(headers)}"
    role = Qt.UserRole
    seen = set()
    for tr in range(tbl.rowCount()):
        it0 = tbl.item(tr, 0)
        sr = it0.data(role) if it0 is not None else None
        if sr is None or sr in seen or not 0 <= sr < len(rows):
            return False, f"table row {tr}: stored row {sr}"
        seen.add(sr)
        for c, val in enumerate(rows[sr]):
            it = tbl.item(tr, c)
            want = tl._fmt_value(val, headers[c])
            if it is None or it.text() != want:
                return False, f"cell ({tr}, {c}): {it.text() if it is not None else None!r} != {want!r}"
            k, kk = tl._num_key(val), getattr(it, '_key', None)
            if not (k == kk or (k is not None and kk is not None and math.isnan(k) and math.isnan(kk))):
                return False, f"cell ({tr}, {c}): sort key {kk!r} != {k!r}"
    return True, ""


def _sorted_by(tbl, col, ascending=True):
    """The table rows are in the order of column col's sort keys (as _NumItem.__lt__: NaN / inf first)."""
    ks = []
    for tr in range(tbl.rowCount()):
        k = getattr(tbl.item(tr, col), '_key', None)
        ks.append(-math.inf if k is None or not math.isfinite(k) else k)
    return all(a <= b for a, b in zip(ks, ks[1:])) if ascending else all(a >= b for a, b in zip(ks, ks[1:]))


def review9_checks():
    """Round 9 (recheck of round 8): one regression check (group) per issue."""
    tla = _tla()
    print("\n---- round 9: recheck of round 8 (time-base notes, stale marks, 'Peak list' in place) ----")

    def window(wh=(1600, 900)):
        w = make_window()
        w.resize(*wh)
        tl.build_logs_tab(w)
        w.show()
        for _ in range(5):
            APP.processEvents()
        return w

    def pump(n=5):
        for _ in range(n):
            APP.processEvents()

    def notes_ok(st, w):
        """Every live view's stored note (= its CSV export's) is a fresh _time_base_note, and the caption
        above the results table is the shown view's text."""
        bad = [n for n in tl._LIVE_VIEWS if n in st.results and st.results_notes.get(n) != tl._time_base_note(st, n)]
        cap, want = w.logs_results_note.text(), tl._results_note_text(st, st.current_results)[0]
        return not bad and cap == want, f"stale notes {bad}; caption {cap[:70]!r} vs {want[:70]!r}"

    # ---------------- issue 1: Remove mode, a cut log hidden: the notes of the views that keep its rows
    # (a) the recheck's case: the dummy + curve2, Movements shown, the dummy hidden, then an offset on curve2
    w = window()
    st = w.logs_state
    tl.logs_add_files(w, [DUMMY])
    tl.logs_add_reference(w, CURVE2)
    tl.logs_set_analysis_axis(w, 'SI')
    i_d, i_r = idx_of(w, 'DUMMY'), idx_of(w, 'curve2')
    n_d = st.entries[i_d].curve.name
    tl.logs_detect_movements(w)
    tl.logs_add_point(w, i_d, 30.0)
    rows_show_d = [(r[3], r[4]) for r in st.results['Movements'][1] if r[0] == n_d]
    tl.logs_set_pause_mode(w, 'remove')
    tl.logs_show_results(w, 'Movements')
    rows_rm_d = [(r[3], r[4]) for r in st.results['Movements'][1] if r[0] == n_d]
    tl.logs_set_visible(w, i_d, False)
    ok_h, det_h = notes_ok(st, w)
    tl.logs_set_time_offset(w, i_r, 0.5)               # the shown Movements view rewritten in place
    pump()
    rows_d = [(r[3], r[4]) for r in st.results['Movements'][1] if r[0] == n_d]
    p_mv = os.path.join(TMP, "r9_movements_hidden.csv")
    tl.logs_export_results(w, p_mv, 'Movements')
    head = [x for x in open(p_mv, encoding='utf-8').read().splitlines() if x.startswith('#')]
    ok, det = notes_ok(st, w)
    mv, pt = st.results_notes['Movements'], st.results_notes.get('Points', '')
    check("r9-1 the recheck's case: Remove mode, the dummy hidden, then an offset on curve2: the dummy's Movements rows "
          "stay in cut time; the export's '# Time base' line = the stored note = the caption, naming it '(hidden)', "
          "never 'as recorded' (the Points note too)",
          ok_h and ok and rows_rm_d and rows_rm_d != rows_show_d and rows_d == rows_rm_d and len(head) > 1
          and head[1] == la.comment_line(tl._csv_text(mv)) and f"{n_d} (hidden)" in mv and 'as recorded' not in mv
          and f"{n_d} (hidden)" in pt and w.logs_results_note.text() == mv, f"{det_h} | {det} | {head[1:2]}")
    w.close()

    # (b) two logs with marked waits (synthetic, with peaks), one hidden: Movements, Points and Peak list
    w = window()
    st = w.logs_state
    wl = tla._wait_logs(tmp=TMP)
    tl.logs_add_files(w, [wl['log_wait_A']['path'], wl['log_wait_B']['path']])
    tl.logs_add_reference(w, tla.WAIT3_GCODE, name='wait3')
    tl.logs_set_analysis_axis(w, 'X')
    i_a, i_b, i_r = idx_of(w, 'log_wait_A'), idx_of(w, 'log_wait_B'), idx_of(w, 'wait3')
    n_a, n_b = st.entries[i_a].curve.name, st.entries[i_b].curve.name
    tl.logs_detect_movements(w)
    tl.logs_add_point(w, i_a, 9.0)
    tl.logs_find_peaks(w, prominence=0.0, min_distance=0.5, kind='both')
    tl.logs_set_pause_mode(w, 'remove')
    tl.logs_show_results(w, 'Peak list')
    views = ['Movements', 'Points', 'Peak list']

    def curves_in(view):
        h, rows = st.results[view]
        ci = h.index('Curve')
        return {r[ci] for r in rows}
    check("r9-1 precondition: Remove mode; Movements, Points and Peak list hold rows of log_wait_A; 'Pauses' is there",
          all(v in st.results and n_a in curves_in(v) for v in views) and 'Pauses' in st.results,
          str([(v, sorted(curves_in(v)) if v in st.results else None) for v in views]))
    tl.logs_set_visible(w, i_a, False)
    ok, det = notes_ok(st, w)
    live = {v: st.results_notes.get(v, '') for v in views}
    check("r9-1 log_wait_A hidden (Remove mode): the notes of Movements / Points / Peak list (they keep its rows, in cut "
          "time) name it '(hidden)' next to the shown log_wait_B, never 'as recorded'; the caption follows at once",
          ok and all(f"{n_a} (hidden)" in v and n_b in v and f"{n_b} (hidden)" not in v and 'as recorded' not in v
                     for v in live.values()), det + " | " + live['Peak list'][:150])
    p_al = os.path.join(TMP, "r9_aligned_hidden.csv")
    tl.logs_export_aligned(w, p_al)
    al_note = [x for x in open(p_al, encoding='utf-8').read().splitlines() if x.startswith('# Time base')]
    pv = st.results_notes.get('Pauses', '')
    check("r9-1 ... the aligned export (visible curves only) and 'Pauses' (its From column: the visible cut logs) "
          "name only the shown log_wait_B", len(al_note) == 1 and n_b in al_note[0] and n_a not in al_note[0]
          and n_b in pv and n_a not in pv, f"{al_note} | {pv[:120]}")
    tl.logs_set_visible(w, i_b, False)
    ok, det = notes_ok(st, w)
    pl = st.results_notes['Peak list']
    check("r9-1 both cut logs hidden: the live views name both '(hidden)'; the aligned export (no visible cut log) "
          "says as recorded", ok and f"{n_a} (hidden)" in pl and f"{n_b} (hidden)" in pl
          and 'no visible log has logged waits' in tl._time_base_note(st), det + " | " + pl[:150])
    tl.logs_set_visible(w, i_a, True)
    tl.logs_set_visible(w, i_b, True)
    ok, det = notes_ok(st, w)
    check("r9-1 both shown again: no '(hidden)' left in any note, the caption follows",
          ok and not any('(hidden)' in st.results_notes.get(v, '') for v in views), det)
    # the reference: in Show mode the notes name the G-code pause lengths only with a G-code reference
    tl.logs_set_pause_mode(w, 'show')
    note0 = st.results_notes['Peak list']
    tl.logs_set_reference(w, i_b)                      # a log: no G-code pause
    ok1, det1 = notes_ok(st, w)
    note1 = st.results_notes['Peak list']
    tl.logs_set_reference(w, i_r)
    ok2, det2 = notes_ok(st, w)
    check("r9-1 Show mode, reference wait3 -> a log -> wait3: the live views' notes and the caption follow each change "
          "at once", ok1 and ok2 and note1 != note0 and 'G-code' in note0 and 'G-code' not in note1
          and st.results_notes['Peak list'] == note0, f"{det1} | {det2} | {note1[:90]}")
    # an in-place rewrite of the shown view that changes its stored note refreshes the caption too
    tl.logs_show_results(w, 'Movements')
    st.results_notes['Movements'] = 'Time base: (r9 test: an outdated note)'
    tl._refresh_results_note(w)
    cap_old = w.logs_results_note.text()
    tl.logs_set_time_offset(w, i_r, 0.25)              # wait3's Movements rows rewritten in place
    pump()
    ok, det = notes_ok(st, w)
    check("r9-1 the shown 'Movements' view rewritten in place with a new note (_update_results_view): the caption "
          "shows the new note", cap_old.startswith('Time base: (r9 test') and ok
          and w.logs_results_note.text() == st.results_notes['Movements'] == tl._time_base_note(st, 'Movements'), det)
    w.close()

    # ---------------- issue 2: no marked wait anywhere: Show <-> Remove marks nothing stale
    def no_stale_after_switch(w, label):
        st = w.logs_state
        note = w.logs_results_note
        tl.logs_show_results(w, 'Compare')
        key0, cap0 = tl._time_base_key(st), note.text()
        out = []
        for mode in ('remove', 'show'):
            if mode == 'remove':
                w.logs_radio_pause_remove.click()      # the radio button, as the user does
            else:
                tl.logs_set_pause_mode(w, mode)
            pump()
            stale = {n: tl._results_stale(st, n) for n in st.results}
            tips = [str(w.logs_results_combo.itemData(i, Qt.ToolTipRole)) for i in range(w.logs_results_combo.count())]
            p = os.path.join(TMP, f"r9_compare_{label}_{mode}.csv")
            tl.logs_export_results(w, p, 'Compare')
            notes_x = la.read_rows_csv(p)[0]
            out.append(st.pause_mode == mode and not any(stale.values()) and tl._time_base_key(st) == key0
                       and note.text() == cap0 == st.results_notes['Compare'] and '#607d8b' in note.styleSheet()
                       and not any('again' in t for t in tips) and not any(n.startswith('Computed') for n in notes_x))
        return all(out), f"{out} key {tl._time_base_key(st)} caption {note.text()[:60]!r}"

    w = window()
    st = w.logs_state
    tl.logs_add_files(w, [CASE02])
    tl.logs_add_reference(w, CURVE2)
    tl.logs_set_analysis_axis(w, 'SI')
    tl.logs_compare(w)
    tl.logs_find_peaks(w, prominence=0.0, min_distance=0.5, kind='both')
    tl.logs_auto_align(w, all_curves=False, index=idx_of(w, 'case_02'))
    ok, det = no_stale_after_switch(w, 'v1')
    check("r9-2 a v1 log + G-code (no logged wait): Show -> Remove -> Show marks neither Compare, Alignment nor Peaks & "
          "periods stale (grey caption = its note, no 'run ... again' tooltip, no 'Computed ...' export line)", ok, det)
    w.close()
    w = window()
    st = w.logs_state
    ref3 = la.read_reference_gcode(tla.WAIT3_GCODE, name='wait3')
    p_nm = tla.write_wait_log(os.path.join(TMP, "log_r9_not_marked.csv"), ref3,
                              [('not_marked', 0.05), ('not_marked', 0.04), ('not_marked', 0.06)], seed=900)['path']
    tl.logs_add_files(w, [p_nm])
    tl.logs_add_reference(w, tla.WAIT3_GCODE, name='wait3')
    tl.logs_set_analysis_axis(w, 'X')
    c_nm = st.entries[idx_of(w, 'r9_not_marked')].curve
    tl.logs_compare(w)
    tl.logs_find_peaks(w, prominence=0.0, min_distance=0.5, kind='both')
    tl.logs_auto_align(w, all_curves=False, index=idx_of(w, 'r9_not_marked'))
    ok, det = no_stale_after_switch(w, 'not_marked')
    check("r9-2 a log whose waits are all 'not marked' (nothing cut): Show -> Remove -> Show marks nothing stale either",
          tl._has_waits(c_nm) and not c_nm.meta['waits'] and len(c_nm.meta['waits_not_marked']) == 3 and ok, det)
    # control: a marked wait still makes the switch mark them (the times do change)
    tl.logs_add_files(w, [tla._wait_logs(tmp=TMP)['log_wait_A']['path']])
    tl.logs_compare(w)
    tl.logs_set_pause_mode(w, 'remove')
    check("r9-2 control: with a log with marked waits loaded, Show -> Remove still marks the Compare made in Show "
          "(orange, 'Computed in real time')", tl._results_stale(st, 'Compare')
          and w.logs_results_note.text().startswith('Computed in real time'), w.logs_results_note.text()[:80])
    w.close()

    # ---------------- issue 3: 'Peak list' shown: offset changes / mode switches rewrite its cells in place
    w = window()
    st = w.logs_state
    rt = w.logs_results_table
    g_text = tla.long_wait_gcode(2400.0)
    ref_m = la.read_reference_gcode(g_text, name='long')
    paths = [tla.write_wait_log(os.path.join(TMP, f"{n}_r9.csv"), ref_m, plan, seed=300 + k)['path']
             for k, (n, plan) in enumerate(tla.WAIT_PLANS.items())]
    tl.logs_add_files(w, paths)
    tl.logs_add_reference(w, g_text, name='long')
    tl.logs_set_analysis_axis(w, 'X')
    tl.logs_find_peaks(w, prominence=0.5, min_distance=0.5, kind='both')
    n_pl = len(st.results['Peak list'][1])

    def cycle():
        ts = []
        for off in (0.25, 0.5):
            t0 = time.perf_counter()
            tl.logs_set_time_offset(w, 0, off)
            ts.append(time.perf_counter() - t0)
            pump(2)
        for mode in ('remove', 'show'):
            t0 = time.perf_counter()
            tl.logs_set_pause_mode(w, mode)
            ts.append(time.perf_counter() - t0)
            pump(2)
        return ts
    tl.logs_show_results(w, 'Peaks & periods')
    pump()
    t_pp = [min(x) for x in zip(*(cycle() for _ in range(2)))]
    tl.logs_show_results(w, 'Peak list')
    pump()
    item0 = rt.item(0, 0)
    stop = _model_watch(rt)
    t_pl = [min(x) for x in zip(*(cycle() for _ in range(2)))]
    rec = stop()
    hdr, rows = st.results['Peak list']
    ok, det = _table_matches_rows(rt, hdr, rows)
    check(f"r9-3 'Peak list' shown ({n_pl} rows): offset changes and Show <-> Remove rewrite its changed cells in place "
          f"(no refill: no model reset / row insertion, the same items) and the table shows exactly the stored rows",
          n_pl > 3000 and rec['rows'] and not rec['reset'] and not rec['ins'] and not rec['rem'] and rt.item(0, 0) is item0
          and ok, f"{det} {dict(rec, rows=len(rec['rows']))}")
    print("INFO: r9 calls with 'Peaks & periods' / 'Peak list' shown (best of 2, ms): offset "
          + ", ".join(f"{1000 * a:.0f} / {1000 * b:.0f}" for a, b in zip(t_pp[:2], t_pl[:2])) + "; Show->Remove "
          f"{1000 * t_pp[2]:.0f} / {1000 * t_pl[2]:.0f}; Remove->Show {1000 * t_pp[3]:.0f} / {1000 * t_pl[3]:.0f}")
    check("r9-3 ... each such call with 'Peak list' shown takes about as long as with 'Peaks & periods' shown "
          "(< 2 x + 50 ms; the refill it replaces took ~15 x as long)", all(b < 2.0 * a + 0.05 for a, b in zip(t_pp, t_pl)),
          f"{[round(1000 * x) for x in t_pp]} vs {[round(1000 * x) for x in t_pl]} ms")
    tl.logs_set_pause_mode(w, 'remove')
    pump()
    hdr, rows = st.results['Peak list']
    cn = hdr.index('Note')
    notes_rm = [r[cn] for r in rows if r[cn]]
    fm = rt.fontMetrics()
    need = max((fm.horizontalAdvance(tl._fmt_value(x, 'Note')) for x in notes_rm), default=0)
    check("r9-3 ... Show -> Remove in place: the Note column grows to fit the longest new note (a peak inside a "
          "removed wait; the old refill's fit samples 1000 rows and left it narrow)", notes_rm and rt.columnWidth(cn) >= need,
          f"{len(notes_rm)} notes, need {need} px, width {rt.columnWidth(cn)} px")
    tl.logs_set_pause_mode(w, 'show')
    pump()
    ci = hdr.index('t (s)')
    rt.sortItems(ci, Qt.DescendingOrder)               # the user sorted the list by time
    pump()
    for mode in ('remove', 'show'):
        tl.logs_set_pause_mode(w, mode)
        pump()
        hdr, rows = st.results['Peak list']
        ok, det = _table_matches_rows(rt, hdr, rows)
        check(f"r9-3 ... a 'Peak list' the user sorted by time, after switching to {mode}: right cells, still sorted",
              ok and _sorted_by(rt, ci, ascending=False) and rt.horizontalHeader().sortIndicatorSection() == ci, det)
    tl.logs_set_time_offset(w, 0, 0.0)
    hdr, rows = st.results['Peak list']
    ok, det = _table_matches_rows(rt, hdr, rows)
    check("r9-3 ... and after an offset change", ok and _sorted_by(rt, ci, ascending=False), det)
    w.close()


# ---------------------------------------------------------------------------------------------
# Round 10: the recheck of round 9 (stale marks per curve, the notes of the analyses of visible
# curves, a user-sorted results table kept sorted in place)
# ---------------------------------------------------------------------------------------------
def _lt_counter():
    """Count the calls of _NumItem.__lt__ (Qt comparing results-table items through Python) until the
    returned stop() is called (it returns the count).  A profile hook on its code: PySide holds the
    method it calls, so a patched class attribute would not see them."""
    code = tl._NumItem.__lt__.__code__
    n = [0]
    prev = sys.getprofile()

    def prof(frame, event, arg):
        if event == 'call' and frame.f_code is code:
            n[0] += 1
    sys.setprofile(prof)

    def stop():
        sys.setprofile(prev)
        return n[0]
    return stop


def _inversions(tbl, col, ascending=True):
    """Neighbouring table rows out of the order Qt sorts column col in (_NumItem.__lt__: numbers by key,
    NaN / inf first, else by text): [(table row, text, text next)]."""
    out = []
    for tr in range(tbl.rowCount() - 1):
        a, b = tbl.item(tr, col), tbl.item(tr + 1, col)
        if (b < a) if ascending else (a < b):
            out.append((tr, a.text(), b.text()))
    return out


def _selected_stored(tbl):
    """The stored rows (column-0 UserRole) of the selected table rows."""
    return sorted(tbl.item(r, 0).data(Qt.UserRole) for r in {ix.row() for ix in tbl.selectedIndexes()})


def review10_checks():
    """Round 10 (recheck of round 9): one regression check (group) per issue."""
    tla = _tla()
    print("\n---- round 10: recheck of round 9 (stale marks per curve, analysis notes, sorted tables in place) ----")

    def window(wh=(1600, 900)):
        w = make_window()
        w.resize(*wh)
        tl.build_logs_tab(w)
        w.show()
        for _ in range(5):
            APP.processEvents()
        return w

    def pump(n=5):
        for _ in range(n):
            APP.processEvents()

    def grey(w, view):
        """The caption shows the view's own note in grey and no combo tooltip asks for a re-run."""
        st, note = w.logs_state, w.logs_results_note
        tips = [str(w.logs_results_combo.itemData(i, Qt.ToolTipRole)) for i in range(w.logs_results_combo.count())]
        return (st.current_results == view and note.text() == st.results_notes[view] and '#607d8b' in note.styleSheet()
                and not any('again' in t for t in tips))

    def cut_named(note):
        """The logs a Remove-mode note names as shown without their waits."""
        head, tail = 'Pauses: Remove logged waits) from ', ', G-code pauses with length 0'
        return note.split(head, 1)[1].split(tail, 1)[0].split(', ') if head in note and tail in note else []

    # ---------------- issue 1: the stale mark compares the curves loaded both then and now
    # (a) the recheck's case (a): Remove mode, Compare / Find peaks of the v1 log + curve2, then the dummy loaded
    w = window()
    st = w.logs_state
    note = w.logs_results_note
    tl.logs_add_files(w, [CASE02])
    tl.logs_add_reference(w, CURVE2)
    tl.logs_set_analysis_axis(w, 'SI')
    tl.logs_set_pause_mode(w, 'remove')
    tl.logs_compare(w)
    tl.logs_find_peaks(w, prominence=0.3, min_distance=0.5, kind='max')
    tl.logs_show_results(w, 'Compare')
    cap0, rows0 = note.text(), [list(r) for r in st.results['Compare'][1]]
    tl.logs_add_files(w, [DUMMY])
    pump()
    stale = {v: tl._results_stale(st, v) for v in ('Compare', 'Peaks & periods')}
    check("r10-1 Remove mode, Compare / Find peaks of the v1 log + curve2, then the dummy (marked waits) loaded: "
          "neither view is marked stale (grey caption = its unchanged note, no 'run ... again' tooltip)",
          not any(stale.values()) and grey(w, 'Compare') and note.text() == cap0, f"{stale} {note.text()[:90]!r}")
    tl.logs_set_pause_mode(w, 'show')
    check("r10-1 ... then Show: curve2's pause lengths now come from the dummy's wait (a time of curve2 changes): "
          "marked 'Computed with other G-code pause lengths' (not 'in real time': no log of the view is cut)",
          tl._results_stale(st, 'Compare') and note.text().startswith('Computed with other G-code pause lengths')
          and 'run Compare again' in note.text(), note.text()[:90])
    tl.logs_set_pause_mode(w, 'remove')
    check("r10-1 ... and back in Remove: not stale, the same numbers", not tl._results_stale(st, 'Compare')
          and grey(w, 'Compare') and [list(r) for r in st.results['Compare'][1]] == rows0, note.text()[:90])
    w.close()

    # (b) the recheck's case (b): Remove mode, Compare of the dummy + the v1 log vs curve2, then the dummy removed
    w = window()
    st = w.logs_state
    note = w.logs_results_note
    tl.logs_add_files(w, [DUMMY, CASE02])
    tl.logs_add_reference(w, CURVE2)
    tl.logs_set_analysis_axis(w, 'SI')
    n_d = st.entries[idx_of(w, 'DUMMY')].curve.name
    tl.logs_set_pause_mode(w, 'remove')
    tl.logs_compare(w)
    tl.logs_show_results(w, 'Compare')
    named0 = cut_named(st.results_notes['Compare'])
    tl.logs_remove_curves(w, [idx_of(w, 'DUMMY')])
    pump()
    kept = [list(r) for r in st.results['Compare'][1]]
    stale_b = tl._results_stale(st, 'Compare')
    grey_b, note_b = grey(w, 'Compare'), st.results_notes['Compare']
    p_b = os.path.join(TMP, "r10_compare_removed.csv")
    tl.logs_export_results(w, p_b, 'Compare')
    tb_b = [x for x in open(p_b, encoding='utf-8').read().splitlines() if x.startswith('# Time base')]
    tl.logs_compare(w)
    check("r10-1 Remove mode, Compare of the dummy + the v1 log, then the dummy (the only cut log) removed: the v1 row "
          "is not marked stale (Compare run again gives the same numbers); its note (caption, export) no longer names "
          "the removed dummy", named0 == [n_d] and not stale_b and grey_b and st.results['Compare'][1] == kept
          and n_d not in note_b and 'no analysed log has logged waits' in note_b and len(tb_b) == 1 and n_d not in tb_b[0],
          f"{named0} stale {stale_b} | {note_b[:100]!r} | {tb_b}")
    w.close()

    # (c) kept: real stale marks with a marked wait, none with a second log with waits loaded in Remove mode
    w = window()
    st = w.logs_state
    note = w.logs_results_note
    wl = tla._wait_logs(tmp=TMP)
    tl.logs_add_files(w, [DUMMY, CASE02])
    tl.logs_add_reference(w, CURVE2)
    tl.logs_set_analysis_axis(w, 'SI')
    tl.logs_compare(w)
    tl.logs_show_results(w, 'Compare')
    tl.logs_set_pause_mode(w, 'remove')
    ok1 = tl._results_stale(st, 'Compare') and note.text().startswith('Computed in real time')
    tl.logs_compare(w)
    tl.logs_set_pause_mode(w, 'show')
    ok2 = tl._results_stale(st, 'Compare') and note.text().startswith('Computed with the logged waits removed')
    tl.logs_set_pause_mode(w, 'remove')
    ok3 = not tl._results_stale(st, 'Compare') and grey(w, 'Compare')
    check("r10-1 kept: with the dummy (marked wait) a Show -> Remove switch marks a Compare made in Show ('Computed in "
          "real time'), Remove -> Show one made in Remove ('Computed with the logged waits removed')", ok1 and ok2 and ok3,
          f"{ok1} {ok2} {ok3} {note.text()[:70]!r}")
    tl.logs_add_files(w, [wl['log_wait_A']['path']])
    pump()
    check("r10-1 kept: a second log with marked waits loaded in Remove mode marks nothing stale",
          not tl._results_stale(st, 'Compare') and grey(w, 'Compare'), note.text()[:90])
    w.close()

    # (d) the rule itself (_base_change: curves loaded then and now)
    k0 = (frozenset({1}), frozenset({1, 2, 3}), ((3, (1.5,)),))           # (cut, loaded, G-code pause lengths)
    keys = [(frozenset({1, 4}), frozenset({1, 2, 3, 4}), ((3, (1.5,)),)),     # a cut log added
            (frozenset(), frozenset({2, 3}), ((3, (1.5,)),)),                  # the cut log removed
            (frozenset(), frozenset({1, 2, 3}), ((3, (1.5,)),)),               # its cut undone (Show)
            (frozenset({1}), frozenset({1, 2, 3}), ((3, (0.0,)),)),            # other pause lengths
            (frozenset({1}), frozenset({1, 2, 3, 5}), ((3, (1.5,)), (5, (2.0,))))]     # a G-code added
    got = [tl._base_change(k0, k) for k in keys]
    want_ok = [got[0] is None, got[1] is None, got[2] is not None and got[2][:2] == ({1}, set()) and not got[2][2],
               got[3] is not None and got[3][2] and got[3][0] == got[3][1] == {1}, got[4] is None]
    check("r10-1 _base_change: a curve added / removed (a cut log too, a G-code too) changes nothing; a cut undone or "
          "other pause lengths of a G-code loaded then and now do", all(want_ok), f"{want_ok} {got}")

    # ---------------- issue 2: the notes of Compare / Alignment / Peaks & periods name the cut logs they used
    w = window()
    st = w.logs_state
    tl.logs_add_files(w, [DUMMY, CASE02])
    tl.logs_add_reference(w, CURVE2)
    tl.logs_set_analysis_axis(w, 'SI')
    i_d, i_r = idx_of(w, 'DUMMY'), idx_of(w, 'curve2')
    n_d = st.entries[i_d].curve.name
    tl.logs_set_pause_mode(w, 'remove')
    tl.logs_set_visible(w, i_d, False)
    tl.logs_compare(w)
    tl.logs_find_peaks(w, prominence=0.0, min_distance=0.5, kind='both')
    tl.logs_detect_movements(w)
    notes = {v: st.results_notes.get(v, '') for v in ('Compare', 'Peaks & periods', 'Movements', 'Peak list')}
    p_c = os.path.join(TMP, "r10_compare_hidden.csv")
    tl.logs_export_results(w, p_c, 'Compare')
    tb_c = [x for x in open(p_c, encoding='utf-8').read().splitlines() if x.startswith('# Time base')]
    curves = {v: {r[0] for r in st.results[v][1]} for v in ('Compare', 'Peaks & periods')}
    check("r10-2 Remove mode, the dummy (the only cut log) hidden: Compare of the v1 log vs curve2 and Peaks & periods "
          "(no dummy row) name no cut log ('no analysed log has logged waits'), also in the Compare CSV's '# Time base' "
          "line; Movements / Peak list (they keep a hidden log's rows) still name it '(hidden)'",
          not any(n_d in c for v in curves.values() for c in v)
          and all(n_d not in notes[v] and 'no analysed log has logged waits' in notes[v] for v in ('Compare', 'Peaks & periods'))
          and len(tb_c) == 1 and n_d not in tb_c[0] and 'Movements' in st.results
          and all(cut_named(notes[v]) == [f"{n_d} (hidden)"] for v in ('Movements', 'Peak list') if v in st.results),
          f"{notes['Compare'][:90]!r} | {tb_c} | {notes['Movements'][:90]!r}")
    tl.logs_set_reference(w, i_d)
    tl.logs_compare(w)
    tl.logs_find_peaks(w, prominence=0.0, min_distance=0.5, kind='both')
    check("r10-2 kept: the hidden cut dummy as the reference of Compare is named '(hidden)' (its cut time is used); "
          "Peaks & periods (visible curves only, not the reference) does not name it",
          cut_named(st.results_notes['Compare']) == [f"{n_d} (hidden)"]
          and n_d not in st.results_notes['Peaks & periods'], st.results_notes['Compare'][:120])
    tl.logs_set_reference(w, i_r)
    tl.logs_auto_align(w, all_curves=False, index=i_d)
    check("r10-2 the hidden dummy aligned alone to curve2 (Auto-align of the selected curve): the Alignment note names "
          "it '(hidden)'", cut_named(st.results_notes['Alignment']) == [f"{n_d} (hidden)"],
          st.results_notes['Alignment'][:120])
    tl.logs_set_visible(w, i_d, True)
    tl.logs_auto_align(w, all_curves=True)
    check("r10-2 ... and all visible curves aligned with the dummy shown: it is named without '(hidden)'",
          cut_named(st.results_notes['Alignment']) == [n_d], st.results_notes['Alignment'][:120])
    w.close()

    # ---------------- issue 3: a 'Peak list' the user sorted, rewritten in place, stays sorted without Qt's re-sort
    w = window()
    st = w.logs_state
    rt = w.logs_results_table
    g_text = tla.long_wait_gcode(2400.0)
    ref_m = la.read_reference_gcode(g_text, name='long')
    paths = [tla.write_wait_log(os.path.join(TMP, f"{n}_r10.csv"), ref_m, plan, seed=300 + k)['path']
             for k, (n, plan) in enumerate(tla.WAIT_PLANS.items())]
    tl.logs_add_files(w, paths)
    tl.logs_add_reference(w, g_text, name='long')
    tl.logs_set_analysis_axis(w, 'X')
    tl.logs_find_peaks(w, prominence=0.5, min_distance=0.5, kind='both')
    tl.logs_show_results(w, 'Peak list')
    pump()
    hdr = st.results['Peak list'][0]
    n_pl = len(st.results['Peak list'][1])
    ci, cv = hdr.index('t (s)'), hdr.index('Value (mm)')
    ops = [('offset +0.37', lambda: tl.logs_set_time_offset(w, 0, 0.37)),
           ('Remove', lambda: tl.logs_set_pause_mode(w, 'remove')),
           ('value offset +0.3', lambda: tl.logs_set_value_offset(w, 2, 0.3, 'X')),
           ('offset -0.8', lambda: tl.logs_set_time_offset(w, 1, -0.8)),
           ('Show', lambda: tl.logs_set_pause_mode(w, 'show')),
           ('offsets back', lambda: (tl.logs_set_time_offset(w, 0, 0.0), tl.logs_set_time_offset(w, 1, 0.0),
                                     tl.logs_set_value_offset(w, 2, 0.0, 'X')))]
    rt.sortItems(ci, Qt.AscendingOrder)                # the user sorts the list by time
    pump()
    rt.selectRow(n_pl // 3)
    sel0 = _selected_stored(rt)
    stop = _model_watch(rt)
    bad, n_lt = [], 0
    for name, fn in ops:
        cnt = _lt_counter()
        fn()
        n_lt += cnt()
        pump(2)
        hdr, rows = st.results['Peak list']
        ok, det = _table_matches_rows(rt, hdr, rows)
        inv = _inversions(rt, ci)
        if not ok or inv or _selected_stored(rt) != sel0 or rt.horizontalHeader().sortIndicatorSection() != ci:
            bad.append((name, det, inv[:2], _selected_stored(rt)))
    rec = stop()
    check(f"r10-3 'Peak list' ({n_pl} rows) sorted by t (s) by the user, then offsets, Show <-> Remove, a value offset: "
          f"after each the table shows exactly the stored rows, sorted (no inversion), the indicator kept, the selected "
          f"peak still selected; rewritten in place (no refill) and without Qt comparing items in Python "
          f"(_NumItem.__lt__ calls: {n_lt}; Qt's re-sort made ~10^5)",
          n_pl > 3000 and not bad and n_lt == 0 and not rec['reset'] and not rec['ins'] and not rec['rem'],
          f"{bad[:2]} lt {n_lt} {dict(rec, rows=len(rec['rows']))}")
    # every column, both orders
    fails = []
    for col in (hdr.index('Curve'), hdr.index('#'), ci, cv, hdr.index('dt to previous (s)'), hdr.index('Note')):
        for order in (Qt.AscendingOrder, Qt.DescendingOrder):
            tl.logs_show_results(w, 'Peak list')       # refill (unsorted), then the user's sort
            rt.sortItems(col, order)
            for name, fn in ops[:3] + ops[4:]:
                fn()
                hdr, rows = st.results['Peak list']
                ok, det = _table_matches_rows(rt, hdr, rows)
                inv = _inversions(rt, col, order == Qt.AscendingOrder)
                if not ok or inv:
                    fails.append((hdr[col], order.name, name, det, inv[:1]))
    check("r10-3 ... sorted by any of Curve / # / t / Value / dt / Note, either order: right cells and in Qt's order "
          "(_NumItem: numbers by key, NaN first; texts) after each in-place change", not fails, str(fails[:3]))
    # time: as with the list unsorted, about
    tl.logs_set_pause_mode(w, 'show')

    def cycle():
        ts = []
        for fn in (lambda: tl.logs_set_time_offset(w, 0, 0.25), lambda: tl.logs_set_time_offset(w, 0, 0.5),
                   lambda: tl.logs_set_pause_mode(w, 'remove'), lambda: tl.logs_set_pause_mode(w, 'show'),
                   lambda: tl.logs_set_time_offset(w, 0, 0.0)):
            t0 = time.perf_counter()
            fn()
            ts.append(time.perf_counter() - t0)
            pump(2)
        return ts
    tl.logs_show_results(w, 'Peak list')
    pump()
    t_un = [min(x) for x in zip(*(cycle() for _ in range(2)))]
    rt.sortItems(ci, Qt.AscendingOrder)
    pump()
    t_so = [min(x) for x in zip(*(cycle() for _ in range(2)))]
    print("INFO: r10 'Peak list' unsorted / sorted by t (best of 2, ms): " + ", ".join(
        f"{1000 * a:.0f} / {1000 * b:.0f}" for a, b in zip(t_un, t_so)))
    check("r10-3 ... an offset change / mode switch with the list sorted by time takes about as long as unsorted "
          "(< 2 x + 60 ms; Qt's re-sort made it 5-12 x)", all(b < 2.0 * a + 0.06 for a, b in zip(t_un, t_so)),
          f"{[round(1000 * x) for x in t_un]} vs {[round(1000 * x) for x in t_so]} ms")
    w.close()

    # few rows changed (Qt re-sorts cell by cell): a new sort key with the same text ('%.4f') is still re-sorted
    w = window()
    st = w.logs_state
    rt = w.logs_results_table
    tl.logs_add_files(w, [wl['log_wait_A']['path'], wl['log_wait_B']['path'], wl['log_wait_C']['path']])
    tl.logs_add_reference(w, tla.WAIT3_GCODE, name='wait3')
    tl.logs_set_analysis_axis(w, 'X')
    tl.logs_find_peaks(w, prominence=0.0, min_distance=0.5, kind='both')
    tl.logs_show_results(w, 'Peak list')
    pump()
    hdr, rows = st.results['Peak list']
    cv = hdr.index('Value (mm)')
    fails = []
    for order in (Qt.AscendingOrder, Qt.DescendingOrder):
        for i_log in range(3):
            for dv in (1e-7, -1e-7, 0.0):
                rt.sortItems(cv, order)
                tl.logs_set_value_offset(w, i_log, dv, 'X')
                hdr, rows = st.results['Peak list']
                ok, det = _table_matches_rows(rt, hdr, rows)
                inv = _inversions(rt, cv, order == Qt.AscendingOrder)
                if not ok or inv:
                    fails.append((order.name, i_log, dv, det, inv[:1]))
    check(f"r10-3 a small 'Peak list' ({len(rows)} rows, equal values in several logs) sorted by Value: a value offset "
          f"of +-1e-7 mm (the same text, a new key) leaves it in key order (Qt is told of the key change)",
          len(rows) < tl._BULK_ROWS and not fails, str(fails[:2]))
    w.close()


if __name__ == '__main__':
    if '--layout-probe' in sys.argv:
        try:
            layout_probe()
        finally:
            shutil.rmtree(TMP, ignore_errors=True)
        sys.exit(0)
    try:
        try:
            main()
        except Exception:
            RESULTS.append(False)
            print("FAIL: test raised\n" + traceback.format_exc())
        if all(os.path.isfile(p) for p in [CASE02, CURVE2] + CHECK_LOGS + [NOV3_LOG]):
            try:
                review_checks()
            except Exception:
                RESULTS.append(False)
                print("FAIL: review checks raised\n" + traceback.format_exc())
            try:
                review2_checks()
            except Exception:
                RESULTS.append(False)
                print("FAIL: second-round checks raised\n" + traceback.format_exc())
            try:
                review3_checks()
            except Exception:
                RESULTS.append(False)
                print("FAIL: third-round checks raised\n" + traceback.format_exc())
            try:
                review4_checks()
            except Exception:
                RESULTS.append(False)
                print("FAIL: fourth-round checks raised\n" + traceback.format_exc())
            try:
                review5_checks()
            except Exception:
                RESULTS.append(False)
                print("FAIL: fifth-round checks raised\n" + traceback.format_exc())
            try:
                review6_checks()
            except Exception:
                RESULTS.append(False)
                print("FAIL: sixth-round checks raised\n" + traceback.format_exc())
            try:
                review7_checks()
            except Exception:
                RESULTS.append(False)
                print("FAIL: seventh-round (logged waits) checks raised\n" + traceback.format_exc())
            try:
                review8_checks()
            except Exception:
                RESULTS.append(False)
                print("FAIL: eighth-round (verifier findings) checks raised\n" + traceback.format_exc())
            try:
                review9_checks()
            except Exception:
                RESULTS.append(False)
                print("FAIL: ninth-round (recheck) checks raised\n" + traceback.format_exc())
            try:
                review10_checks()
            except Exception:
                RESULTS.append(False)
                print("FAIL: tenth-round (recheck) checks raised\n" + traceback.format_exc())
    finally:
        shutil.rmtree(TMP, ignore_errors=True)
    n_fail = RESULTS.count(False)
    if n_fail == 0 and RESULTS:
        print(f"\nALL PASSED ({len(RESULTS)} checks)")
        sys.exit(0)
    print(f"\n{n_fail} FAILED of {len(RESULTS)} checks")
    sys.exit(1)
