"""
LogIQ user-guide video: the Log files tab - three runs of one plan analysed (peaks, axes, movements, compare).

    python demo/demo_logs.py            record   -> demo/output/logs_analysis.mp4 (+ _silent, .srt, _narration)
    python demo/demo_logs.py --check    fast run without voice / recording (checks the flow)

The three logs (demo/logs_runs.py, KINETIQ, logs_analysis.gcode) are read from LOG_DIR.  LogIQ connects to the
platform before recording (the reference G-code is downloaded from the controller; nothing moves).
Environment: DEMO_IP (default 172.18.38.129), TRACE_DEMO_FFMPEG.  configuration.json is restored afterwards.
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

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialogButtonBox, QFileDialog, QListView, QPushButton

import demo_kit as K

OUT = os.path.join(r"C:\TRACE\demo", "output")
TAG = "logs_analysis"
IP = os.environ.get("DEMO_IP", "172.18.38.129")
CHECK = "--check" in sys.argv
LOG_DIR = os.path.join(OUT, "logs_video")
LAT_ROI = (4.0, 23.0)
SI_ROI = (22.0, 41.0)

# (caption, sub-caption, narration)   numbers: measured with scratch/logs_analysis_dry.py on these logs
STEPS = [
    ("Log files tab", "LogIQ user guide - analysing runs",
     "This video shows how to analyse recorded runs in the Log files tab. The same plan was run three times on "
     "KINETIQ. AP follows a cos to the power six breathing curve, with a period of four seconds. LAT and SI each make "
     "three steps of three millimetres, with ramps of half a second, one second and two seconds."),
    ("Step 1 - Add the log files", "three runs of the same plan",
     "Open the Log files tab and press Add logs. Select the three log files, one per run, and open them. The table "
     "lists every curve with its colour, its type and its offsets."),
    ("Step 2 - The plan as reference", "the G-code named in the log",
     "Each log names the G-code it ran. Select a log, and press Reference from log's G-code: LogIQ downloads that "
     "file from the controller and adds the plan as the reference curve."),
    ("Step 3 - One axis at a time", "Show on plot",
     "A log holds every axis. Show on plot chooses what is drawn. Here AP, the breathing curve. Then LAT with its "
     "three steps, and SI, which steps later. The analysis axis, above, is the axis every tool works on."),
    ("Step 4 - Align", "the start delay removed",
     "The runs start slightly later than the plan: the controller needs a moment to open the file. With AP as the "
     "analysis axis, Auto-align all shifts each run in time to match the reference: here by about three tenths of a "
     "second. The results list the shift and the correlation of every run."),
    ("Step 5 - Peaks of the breathing curve", "maxima and periods",
     "Find peaks marks the maxima of every curve. The results give the number of peaks and the period: "
     "{PERIOD_TXT}"),
    ("Step 6 - LAT: the moving positions", "region of interest and movements",
     "Now LAT. Select a region of interest on the plot, around the three steps, and zoom in. Detect movements finds "
     "where each curve starts and stops moving. {LAT_TXT}"),
    ("Step 7 - SI: the same tools", "",
     "The same for SI: a new region around its steps, then detect movements. {SI_TXT}"),
    ("Step 8 - Compare with the plan", "differences and the band of the runs",
     "Back to AP, over the whole run. Compare to reference gives, per run, the mean difference, the spread and the "
     "largest difference. {CMP_TXT} The difference plot shows them over time, and the band shows the mean of the "
     "three runs plus and minus two standard deviations."),
    ("Step 9 - Export", "results, aligned data, figure",
     "Finally, the results, the aligned data and the figure can be exported, for a report or for further analysis."),
    ("Done", "Log files tab",
     "That is the Log files tab: add the runs and their plan, align them, and measure peaks, movements and "
     "differences, one axis at a time."),
]

NUM = {
    "PERIOD_TXT": "thirteen peaks in every curve, and a mean period of four seconds, within about a hundredth of a "
                  "second, in all three runs. The peak list gives the time and the value of each peak.",
    "LAT_TXT": "Each run makes three movements of three millimetres, and they take close to the planned half second, "
               "one second and two seconds. The table lists the start, stop, duration and size of every movement, "
               "for the runs and for the plan.",
    "SI_TXT": "Again three steps of three millimetres in every run, with durations close to the planned ramps.",
    "CMP_TXT": "Here the runs follow the plan within about a third of a millimetre RMS. Differences above one "
               "millimetre occur only on the steep flanks of the peaks, where the platform moves fastest and the "
               "position, updated by the controller every two tenths of a second, changes most between updates.",
}


def narration(i):
    return STEPS[i][2].format(**NUM)


def plot_point(w, t, frac=0.5):
    canvas, ax = w.logs_canvas, w.logs_ax
    xpx, _ = ax.transData.transform((t, 0.0))
    bb = ax.get_window_extent()
    ypx = bb.y0 + frac * bb.height
    dpr = float(getattr(canvas, 'device_pixel_ratio', 1.0)) or 1.0
    return QPoint(int(round(xpx / dpr)), int(round(canvas.height() - ypx / dpr)))


def qt_file_dialog():
    """Add logs: a Qt file dialog in LOG_DIR instead of the Windows one (it can be filmed and driven)."""
    def open_files(parent, caption, _folder, filt):
        dlg = QFileDialog(parent, caption, LOG_DIR, filt)
        dlg.setOption(QFileDialog.DontUseNativeDialog, True)
        dlg.setFileMode(QFileDialog.ExistingFiles)
        dlg.setViewMode(QFileDialog.Detail)
        dlg.resize(1150, 640)
        if dlg.exec():
            return dlg.selectedFiles(), filt
        return [], ""
    QFileDialog.getOpenFileNames = staticmethod(open_files)


class Logs:
    def __init__(self, w, d, ov):
        self.w, self.d, self.ov = w, d, ov
        self.ok = False

    # ------------------------------------------------------------------ helpers
    def step(self, i):
        c, s, _n = STEPS[i]
        yield from self.d.step(c, s, narration(i))

    def show(self, widget):
        self.w.logs_left_scroll.ensureWidgetVisible(widget, 20, 80)
        yield 250

    def click(self, widget, **kw):
        yield from self.show(widget)
        yield from self.d.click(widget, **kw)

    def choose_combo(self, combo, text):
        yield from self.show(combo)
        i = combo.findData(text)
        if i < 0:
            i = combo.findText(text)
        if i < 0:
            print("  no item", text, "in combo", flush=True)
            return
        yield from self.d.click(combo, pause_ms=200)
        yield 500
        view = combo.view()
        r = view.visualRect(view.model().index(i, 0))
        if view.isVisible() and r.isValid():
            yield from self.d.move_to(view.viewport().mapToGlobal(r.center()), 500)
            yield 300
            self.ov.click_ripple(view.viewport().mapToGlobal(r.center()))
        combo.setCurrentIndex(i)
        combo.hidePopup()
        yield 700

    def check(self, axis, on):
        cb = self.w.logs_axis_checks.get(axis)
        if cb is not None and cb.isChecked() != on:
            # on the tick box: the checkbox is stretched over its grid cell and a click beside the label is ignored
            yield from self.click(cb, local=QPoint(9, cb.height() // 2), pause_ms=150)
            yield 350
            cb = self.w.logs_axis_checks.get(axis)
            if cb is not None and cb.isChecked() != on:
                print(f"  (axis {axis}: click did not toggle, set directly)", flush=True)
                cb.click()
                yield 300

    def only(self, axes):
        """Show only these axes; the analysis axis is always drawn, so it moves to the first of them first."""
        if self.w.logs_axis_combo.currentData() not in axes:
            yield from self.choose_combo(self.w.logs_axis_combo, axes[0])
        for a in list(self.w.logs_axis_checks):
            if a not in axes:
                yield from self.check(a, False)
        for a in axes:
            yield from self.check(a, True)

    def roi_drag(self, t0, t1):
        w = self.w
        yield from self.click(w.logs_btn_roi_select)
        yield 400
        yield from self.d.drag(w.logs_canvas, plot_point(w, t0, 0.55), plot_point(w, t1, 0.55), ms=1300)
        yield 500
        if w.logs_btn_roi_select.isChecked():
            yield from self.click(w.logs_btn_roi_select, pause_ms=150)
        yield 400
        yield from self.click(w.logs_btn_roi_zoom)
        yield 900

    def dismiss(self, label=""):
        """A message box opened by the last action: print its text and press OK on screen."""
        from PySide6.QtWidgets import QMessageBox
        yield 400
        box = QApplication.activeModalWidget()
        if isinstance(box, QMessageBox) and box.isVisible():
            print(f"  message box after {label}: {box.windowTitle()!r}: {box.text()[:300]!r}", flush=True)
            yield 1800
            ok = next((b for b in box.findChildren(QPushButton) if b.isVisible()), None)
            if ok is not None:
                yield from self.d.click(ok, pause_ms=300)
            else:
                box.accept()
            yield 500

    def shown(self, label):
        """Check mode: which axes are drawn now (and a screenshot)."""
        if CHECK:
            on = [a for a, cb in self.w.logs_axis_checks.items() if cb.isChecked()]
            print(f"  [{label}] axes shown: {on} | analysis: {self.w.logs_axis_combo.currentData()}", flush=True)
            self.w.grab().save(os.path.join(OUT, "logs_check", f"{label}.png"))

    def results(self, ms=700, hold=1800):
        yield from self.d.point_at(self.w.logs_results_table, ms=ms)
        yield hold

    # ------------------------------------------------------------------ parts
    def add_logs(self):
        w, d = self.w, self.d
        yield from self.step(1)
        yield from d.click(w.nav_buttons[5])
        yield 1200
        yield from self.click(w.logs_btn_add)
        yield from d.wait_popup(5000)
        dlg = d.popup
        if not isinstance(dlg, QFileDialog):
            print("ABORT: no file dialog", flush=True)
            return False
        yield 1500                                           # the folder listing fills in
        view = next((v for v in dlg.findChildren(QListView) if v.isVisible()), None)
        from PySide6.QtWidgets import QTreeView
        view = next((v for v in dlg.findChildren(QTreeView) if v.isVisible()), view)
        names = sorted(os.path.basename(p) for p in glob.glob(os.path.join(LOG_DIR, "log_*.csv")))
        model, root = view.model(), view.rootIndex()
        rows = {}
        for r in range(model.rowCount(root)):
            ix = model.index(r, 0, root)
            rows[model.data(ix)] = ix
        picks = [rows[n] for n in names if n in rows]
        if len(picks) != 3:
            print("ABORT: logs not listed in the dialog:", list(rows), flush=True)
            return False
        for k, ix in enumerate(picks):
            rect = view.visualRect(ix)
            pt = QPoint(rect.left() + 90, rect.center().y())
            yield from d.point_at(view.viewport(), pt, ms=600, outline=False)
            yield 250
            self.ov.click_ripple(view.viewport().mapToGlobal(pt))
            mod = Qt.NoModifier if k == 0 else Qt.ControlModifier
            QTest.mouseClick(view.viewport(), Qt.LeftButton, mod, pt)
            yield 500
        yield 600
        bb = dlg.findChild(QDialogButtonBox)
        ok = bb.button(QDialogButtonBox.Open) if bb is not None else None
        if ok is None and bb is not None:
            ok = next((b for b in bb.findChildren(QPushButton) if b.isVisible()), None)
        if ok is not None:
            yield from d.click(ok, pause_ms=300)
        else:
            dlg.accept()
        yield 2500
        yield from self.dismiss('add logs')
        yield from d.point_at(w.logs_curves_table, ms=700)
        yield 1500
        from fcn_create_gui.tab_logs import _state
        if len(_state(w).entries) != 3:
            print("ABORT: logs not loaded:", [e.curve.name for e in _state(w).entries], flush=True)
            return False
        return True

    def reference(self):
        w, d = self.w, self.d
        yield from self.step(2)
        tbl = w.logs_curves_table
        rect = tbl.visualRect(tbl.model().index(0, 2))
        yield from d.click(tbl.viewport(), rect.center())
        yield 2300                                           # the Duet button follows the selection (2 s timer)
        from fcn_create_gui.tab_logs import _update_duet_button
        _update_duet_button(w)
        if not w.logs_btn_duet_ref.isEnabled():
            print("ABORT: Reference from log's G-code is disabled (not connected?)", flush=True)
            return False
        yield from self.click(w.logs_btn_duet_ref)
        yield from self.dismiss('reference')
        yield 2500
        yield from d.point_at(w.logs_canvas, plot_point(w, 30, 0.6), ms=800)
        yield 1500
        return True

    def axes(self):
        w, d = self.w, self.d
        yield from self.step(3)
        yield from self.show(w.logs_axes_box)
        yield from d.point_at(w.logs_axes_box, ms=700)
        yield 900
        yield from self.only(['AP'])
        self.shown('3a_AP')
        yield 1800
        yield from self.only(['LAT'])
        self.shown('3b_LAT')
        yield 2000
        yield from self.only(['SI'])
        self.shown('3c_SI')
        yield 2000
        yield from self.only(['AP'])
        self.shown('3d_AP')
        yield 800

    def align(self):
        w, d = self.w, self.d
        yield from self.step(4)
        yield from d.point_at(w.logs_canvas, plot_point(w, 4.0, 0.7), ms=800)
        yield 1500
        yield from self.click(w.logs_btn_align_all)
        yield from self.dismiss('align')
        yield 1800
        yield from self.results()
        yield from d.point_at(w.logs_curves_table, ms=700)
        yield 1500

    def peaks(self):
        w, d = self.w, self.d
        yield from self.step(5)
        yield from self.show(w.logs_combo_peakkind)
        yield from d.point_at(w.logs_combo_peakkind, ms=600)
        yield 800
        yield from self.click(w.logs_btn_peaks)
        yield from self.dismiss('peaks')
        yield 1800
        yield from d.point_at(w.logs_canvas, plot_point(w, 13.0, 0.92), ms=800)
        yield 1500
        yield from self.results(hold=2500)

    def movements(self, step_i, axis, roi):
        w, d = self.w, self.d
        yield from self.step(step_i)
        yield from self.click(w.logs_btn_peaks_clear)
        yield 400
        yield from self.choose_combo(w.logs_axis_combo, axis)
        yield from self.only([axis])
        yield 800
        if w.logs_btn_movements_clear.isEnabled():
            yield from self.click(w.logs_btn_movements_clear)
        yield from self.click(w.logs_btn_zoom_all)
        yield 700
        yield from self.roi_drag(*roi)
        self.shown(f'{step_i}_{axis}_roi')
        yield from self.click(w.logs_btn_movements)
        yield from self.dismiss('movements')
        yield 1800
        yield from d.point_at(w.logs_canvas, plot_point(w, (roi[0] + roi[1]) / 2, 0.5), ms=700)
        yield 1500
        yield from self.show(w.logs_movements_table)
        yield from d.point_at(w.logs_movements_table, ms=700)
        yield 2000
        yield from self.results(hold=2200)

    def compare(self):
        w, d = self.w, self.d
        yield from self.step(8)
        yield from self.click(w.logs_btn_movements_clear)
        yield from self.click(w.logs_btn_roi_clear)
        yield from self.choose_combo(w.logs_axis_combo, 'AP')
        yield from self.only(['AP'])
        yield from self.click(w.logs_btn_zoom_all)
        yield 700
        self.shown('8_compare')
        yield from self.click(w.logs_btn_compare)
        yield from self.dismiss('compare')
        yield 1500
        yield from self.results(hold=2500)
        yield from self.click(w.logs_chk_diff, local=QPoint(9, w.logs_chk_diff.height() // 2))
        yield 1800
        yield from self.click(w.logs_chk_band, local=QPoint(9, w.logs_chk_band.height() // 2))
        yield 1500
        yield from self.roi_drag(20.0, 34.0)
        yield from d.point_at(w.logs_canvas, plot_point(w, 27.0, 0.8), ms=800)
        yield 2000

    def export(self):
        w, d = self.w, self.d
        yield from self.step(9)
        for b in (w.logs_btn_export_results, w.logs_btn_export_aligned, w.logs_btn_save_fig):
            yield from self.show(b)
            yield from d.point_at(b, ms=600)
            yield 900

    def run(self):
        w, d = self.w, self.d
        yield from self.step(0)
        yield 2500
        if not (yield from self.add_logs()):
            return
        if not (yield from self.reference()):
            return
        yield from self.axes()
        yield from self.align()
        yield from self.peaks()
        yield from self.movements(6, 'LAT', LAT_ROI)
        yield from self.movements(7, 'SI', SI_ROI)
        yield from self.compare()
        yield from self.export()
        yield from self.step(10)
        yield from self.click(w.logs_btn_zoom_all)
        self.ok = True


def main():
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(os.path.join(OUT, "logs_check"), exist_ok=True)
    cfg = os.path.join(r"C:\TRACE", "configuration.json")
    cfg_bak = os.path.join(tempfile.gettempdir(), "logiq_demo_logs_cfg.json")
    shutil.copy2(cfg, cfg_bak)
    from fcn_init.app_config import get_config_path      # the settings the app really saves (AppData)
    cfg_user = get_config_path("configuration.json", for_writing=True)
    cfg_user_bak = cfg_bak.replace(".json", "_user.json")
    if os.path.exists(cfg_user):
        shutil.copy2(cfg_user, cfg_user_bak)
    if CHECK:
        clips, durs = [], [0.3] * len(STEPS)
    else:
        clips = K.tts_clips([narration(i) for i in range(len(STEPS))], os.path.join(OUT, f"{TAG}_clips"),
                            rate=-1, speed=0.95)
        durs = [dd for _p, dd in clips]

    app = QApplication.instance() or QApplication(sys.argv)
    for eff in (Qt.UI_AnimateMenu, Qt.UI_FadeMenu, Qt.UI_AnimateCombo, Qt.UI_AnimateTooltip, Qt.UI_FadeTooltip):
        QApplication.setEffectEnabled(eff, False)
    qt_file_dialog()
    from demo_planning import build_window
    w = build_window()
    w.showMaximized()
    ov = K.Overlay()
    ov.show()

    def overlay_on_top():
        ov.raise_()
        if sys.platform == "win32":
            try:
                import ctypes
                ctypes.windll.user32.SetWindowPos(int(ov.winId()), -1, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010)
            except Exception:
                pass

    seen_boxes = set()

    def watch_boxes():
        m = QApplication.activeModalWidget()
        if m is not None and m.isVisible() and id(m) not in seen_boxes:
            seen_boxes.add(id(m))
            txt = getattr(m, 'text', lambda: '')()
            print(f"  [dialog] {type(m).__name__} {m.windowTitle()!r}: {str(txt)[:200]!r}", flush=True)

    keep_top = QTimer()
    keep_top.timeout.connect(watch_boxes)
    keep_top.timeout.connect(overlay_on_top)
    keep_top.start(250)
    d = K.PacedDirector(ov, durs, speed=4.0 if CHECK else 1.0)
    demo = Logs(w, d, ov)
    rec = K.Recorder(os.path.join(OUT, f"{TAG}_silent.mp4"), None)

    def run():
        yield 1500
        w.DuetIPAddress.setText(IP)                       # connected before the recording starts (nothing moves)
        from fcn_control.fcn_control import setDuetIP
        setDuetIP(w, show_dialog=False)
        t_end = time.perf_counter() + 25
        while time.perf_counter() < t_end and not (getattr(w, 'duet_connected', False)
                                                   and not getattr(w, '_connecting_in_progress', False)):
            yield 250
        if not w.duet_connected:
            print("ABORT: could not connect to", IP, flush=True)
            return
        yield 1500
        if CHECK:
            d.start_clock()
            yield from demo.run()
            return
        front = False
        for _k in range(30):
            K.bring_to_front(w, ov)
            yield 500
            if K.window_on_screen(w):
                front = True
                break
        if not front:
            print("ABORTED: the LogIQ window is covered by another program - nothing recorded", flush=True)
            return
        print("LogIQ window is in front - recording", flush=True)
        rec.rect = K.physical_rect(w)
        rec.start()
        yield 1200
        d.start_clock()
        d.t0 = rec.t_start
        yield from demo.run()
        if demo.ok:
            yield from d.finish()
        ov.caption = ""
        yield 1500

    def finish():
        total = time.perf_counter() - (rec.t_start or d.t0 or time.perf_counter())
        if not CHECK and rec.t_start is not None:
            rec.stop()
            if demo.ok:
                starts = [t for t, _c, _n in d.steps]
                d.write_srt(os.path.join(OUT, f"{TAG}.srt"), total)
                K.assemble_narration(clips, starts, os.path.join(OUT, f"{TAG}_narration.wav"), total)
                rc, merr = K.mux_audio(os.path.join(OUT, f"{TAG}_silent.mp4"),
                                       os.path.join(OUT, f"{TAG}_narration.wav"), os.path.join(OUT, f"{TAG}.mp4"))
                print("mux:", rc, (merr or "").strip()[:300], flush=True)
                bl = K.black_segments(os.path.join(OUT, f"{TAG}_silent.mp4"))
                print("black stretches:", bl if bl else "none", flush=True)
            else:
                print("recording stopped early (demo aborted): video not assembled", flush=True)
        try:
            from fcn_create_gui.tab_logs import _state
            st = _state(w)
            print("curves:", [e.curve.name for e in st.entries], "| results:", list(st.results), flush=True)
            if CHECK:
                w.grab().save(os.path.join(OUT, f"{TAG}_check_end.png"))
        except Exception as e:
            print("state:", e)
        print("completed:", demo.ok, "| steps:", [(round(tt, 1), c) for tt, c, _n in d.steps], "| total",
              round(total, 1), flush=True)
        keep_top.stop()
        ov.close()
        w.close()
        shutil.copy2(cfg_bak, cfg)
        if os.path.exists(cfg_user_bak):
            shutil.copy2(cfg_user_bak, cfg_user)
        app.quit()

    d.run(run(), on_finish=finish)
    app.exec()


if __name__ == "__main__":
    main()
