"""
LogIQ user-guide video: the workflow end to end with KINETIQ (real platform: connect, home, plan, upload, run, log).

    python demo/demo_intro.py            record   -> demo/output/intro_workflow.mp4 (+ _silent, .srt, _narration)
    python demo/demo_intro.py --plan     offline: builds the plan only (fast) and prints the G-code ranges / duration

Environment: DEMO_IP (default 172.18.38.129), TRACE_DEMO_FFMPEG (recorder).  The platform must be switched on and
NOT homed, with the base plate disconnected.  configuration.json is restored afterwards.
"""
import os
import re
import shutil
import sys
import tempfile
import time

sys.path.insert(0, r"C:\TRACE")
sys.path.insert(0, r"C:\TRACE\demo")
os.chdir(r"C:\TRACE")

from PySide6.QtCore import Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLineEdit, QPushButton

import demo_kit as K

OUT = os.path.join(r"C:\TRACE\demo", "output")
TAG = "intro_workflow"
IP = os.environ.get("DEMO_IP", "172.18.38.129")
PLAN_ONLY = "--plan" in sys.argv
FILE_NAME = "intro_workflow.gcode"
TOTAL_S = 40

# (caption, sub-caption, narration)
STEPS = [
    ("LogIQ - the workflow", "an overview: every step has its own video",
     "This video gives a general view of the LogIQ workflow, from connecting the device to recording a log file. "
     "Each step is shown in detail in separate videos. Here we go through all of them once, end to end, with "
     "KINETIQ, the motion platform."),
    ("Step 1 - Connect", "Control tab",
     "In the Control tab, type the address of the platform and press the connect button. LogIQ recognises the "
     "platform and fills the KINETIQ button."),
    ("Step 2 - Home all", "the buttons turn green",
     "The motion buttons are red: the platform is not homed. Press Home ALL. Each motor moves to its switch, and "
     "the buttons turn green."),
    ("Step 3 - Plan the motion", "Planning tab - KINETIQ, 40 s",
     "Now open the Planning tab, choose KINETIQ, and set the total duration to forty seconds."),
    ("Step 4 - Lift AP to 30 mm", "ramp up, hold, ramp down",
     "First AP: a linear ramp up to thirty millimetres in five seconds, a constant thirty, and a ramp back down at "
     "the end."),
    ("Step 5 - Roll around it", "a sine of 3 degrees",
     "Then a rotation around this central position: Roll, a sine of three degrees. LogIQ computes the four vertical "
     "axes for you."),
    ("Step 6 - Upload to the controller", "Upload to Duet",
     "Upload to Duet turns the plan into G-code and stores it on the controller. Give the file a name and confirm."),
    ("Step 7 - Select the file", "Files tab - Run",
     "In the Files tab, select the file and press Run. LogIQ selects it for the run and opens the Status tab."),
    ("Step 8 - Reference and log", "Status tab",
     "In the Status tab, turn on the G-code reference, so the plan is drawn next to the measured position, and "
     "choose the curves to show, here AP and Roll. Record is on, so the run is saved in a log file."),
    ("Step 9 - Start", "",
     "Press Start. The platform first moves to the start position of the plan, then the plan runs."),
    ("Step 10 - The Status tab", "live position, reference, progress",
     "While it runs: the plot shows the measured position live, next to the dashed G-code reference. Above it, the "
     "progress bar and the time left, the speeds, and the position of every axis. Pause, Resume and Stop control "
     "the run, and the speed factor scales it."),
    ("Step 11 - Time offset", "Ref. offset lines the reference up",
     "Look at the start: the measured curve is slightly later than the reference. The controller needs a moment to "
     "open the file and start, and it updates the position it reports every two tenths of a second. Ref. offset "
     "shifts the reference in time: with zero point four seconds, the two curves match."),
    ("Step 12 - The log file", "import it back and evaluate it",
     "The run has finished, and the log file is saved in the output folder. Log files can be imported back and "
     "evaluated, in the Log files tab, and compared with the plan. Separate videos show this."),
    ("Done", "LogIQ - the workflow",
     "That is the whole workflow: connect, home, plan, upload, select, run and record. The detailed videos show "
     "each step."),
]


def QPoint_at(widget, fx, fy):
    from PySide6.QtCore import QPoint
    return QPoint(int(widget.width() * fx), int(widget.height() * fy))


class Intro:
    def __init__(self, w, d, ov):
        from demo_planning import Demo as PlanningDemo
        self.w, self.d, self.ov = w, d, ov
        self.pd = PlanningDemo(w, d, ov)            # planning helpers: segments, axis, modal answers
        self.ok = False

    # ---------------------------------------------------------------- helpers
    def type_text(self, widget, text, per_char_ms=100):
        yield from self.d.click(widget, pause_ms=200)
        widget.setFocus()
        QTest.keyClick(widget, Qt.Key_A, Qt.ControlModifier)
        yield 150
        for ch in text:
            QTest.keyClicks(widget, ch)
            yield per_char_ms
        yield 300

    def wait_for(self, cond, timeout_s, poll_ms=250):
        t_end = time.perf_counter() + timeout_s
        while time.perf_counter() < t_end:
            try:
                if cond():
                    return True
            except Exception:
                pass
            yield poll_ms
        return False

    def homed(self):
        from fcn_control.fcn_control import is_axis_homed
        return all(is_axis_homed(self.w, k) for k in ("LAT", "SI", "AP"))

    def nav(self, i):
        yield from self.d.click(self.w.nav_buttons[i])
        yield 900

    # ---------------------------------------------------------------- parts
    def connect_and_home(self):
        w, d = self.w, self.d
        yield from d.step(*STEPS[1])
        yield from self.nav(0)
        yield from self.type_text(w.DuetIPAddress.lineEdit(), IP)
        yield from d.click(w.setDuetIP)
        if not (yield from self.wait_for(lambda: getattr(w, 'duet_connected', False)
                                         and not getattr(w, '_connecting_in_progress', False), 25)):
            print("ABORT: could not connect to", IP, flush=True)
            return False
        yield 1200
        yield from d.point_at(w.btn_ip_trace, ms=700)
        yield 800
        if self.homed():
            print("ABORT: the platform is already homed - unhome it, then record again", flush=True)
            return False
        yield from d.step(*STEPS[2])
        yield from d.point_at(w.MIN_APAXIS, ms=600)
        yield 900
        yield from d.click(w.HOME_ALL_PLATFORM)
        t0 = time.perf_counter()
        if not (yield from self.wait_for(self.homed, 240)):
            print("ABORT: homing did not finish within 4 minutes", flush=True)
            return False
        print(f"  homed after {time.perf_counter() - t0:.1f} s", flush=True)
        yield 2500                                          # the last slow approaches finish
        yield from d.point_at(w.PLUS_APAXIS, ms=600)
        yield 900
        return True

    def plan(self):
        w, d, pd = self.w, self.d, self.pd
        yield from d.step(*STEPS[3])
        yield from self.nav(3)
        p = pd.p
        yield from d.click(p.device_buttons[1])           # KINETIQ
        yield 1000
        yield from pd.type_value(pd.cc.total_spin, TOTAL_S)
        yield from pd.answer_modal(timeout_ms=1500)
        yield 600
        yield from d.step(*STEPS[4])
        yield from pd.set_axis('AP')
        yield from pd.segment('linear', 0, 30, 5, start=0)
        yield from d.click(w.button_create_curve, pause_ms=400)
        yield 900
        yield from pd.segment('constant', 30, 0, 4, start=5, end=TOTAL_S - 5)
        yield from d.click(w.button_create_curve, pause_ms=400)
        yield 900
        yield from pd.segment('linear', 30, 0, 5, start=TOTAL_S - 5)
        yield from d.click(w.button_create_curve, pause_ms=400)
        yield 1200
        yield from d.step(*STEPS[5])
        yield from pd.set_axis('Roll')
        yield from pd.segment('sin', 3, None, 6, start=9, end=33)
        yield from d.click(w.button_create_curve, pause_ms=400)
        yield 1200
        yield from pd.show_only(['AP', 'Roll', 'A', 'B', 'C', 'D'])
        yield 1500

    def upload(self):
        w, d, p = self.w, self.d, self.pd.p
        yield from d.step(*STEPS[6])
        yield from d.click(p.btn_upload)
        yield from d.wait_popup(5000)
        dlg = d.popup
        if dlg is None:
            print("ABORT: no upload name dialog", flush=True)
            return False
        le = next((x for x in dlg.findChildren(QLineEdit) if x.isVisible()), None)
        if le is not None:
            yield from self.type_text(le, FILE_NAME, per_char_ms=70)
        ok = next((b for b in dlg.findChildren(QPushButton) if b.isVisible() and 'ok' in b.text().lower()), None)
        if ok is not None:
            yield from d.click(ok, pause_ms=250)
        else:
            dlg.accept()
        yield 1500
        yield from self.pd.answer_modal(timeout_ms=15000)      # "Upload Successful"
        yield 800
        return True

    def select_file(self):
        w, d = self.w, self.d
        yield from d.step(*STEPS[7])
        yield from self.nav(2)
        yield 1500
        tv, model = w.fileTreeView, w.model
        idx = None
        for _k in range(20):
            for r in range(model.rowCount()):
                it = model.item(r, 0)
                if it is not None and it.text().strip() == FILE_NAME:
                    idx = model.index(r, 0)
            if idx is not None:
                break
            yield 300
        if idx is None:
            print("ABORT: uploaded file not in the Files list", flush=True)
            return False
        tv.scrollTo(idx)                                   # a long file list: bring the row into view first
        yield 500
        rect = tv.visualRect(idx)
        yield from d.click(tv.viewport(), rect.center())
        yield 300
        if tv.currentIndex().row() != idx.row():
            print("ABORT: the file row was not selected", flush=True)
            return False
        yield 700
        yield from d.click(w.gcodeRun)
        if not (yield from self.wait_for(lambda: w.tabModules.currentIndex() == 1, 10)):
            print("ABORT: Run did not open the Status tab", flush=True)
            return False
        yield 1500
        return True

    def status_and_run(self):
        w, d = self.w, self.d
        st = w.status_modern
        yield from d.step(*STEPS[8])
        if not st.ref_pill.isChecked():
            yield from d.click(st.ref_pill)
            yield 900
        title = st.sections['phantom'][0]                    # DYNAMIQ curves off, AP and Roll on
        if any(st.pills[k].isChecked() for k in st.sections['phantom'][1]):
            yield from d.click(title)
            yield 500
        for k in ('AP', 'Roll'):
            if not st.pills[k].isChecked():
                yield from d.click(st.pills[k])
                yield 400
        if not st.btn_record.isChecked():
            yield from d.click(st.btn_record)
        else:
            yield from d.point_at(st.btn_record, ms=600)
        yield 1200
        yield from d.step(*STEPS[9])
        yield from d.click(w.gcodeStart)
        started = yield from self.wait_for(lambda: getattr(w, 'run_active', False) is True, 60)
        if not started:
            print("ABORT: the run did not start", flush=True)
            return False
        t_run = time.perf_counter()
        yield from d.step(*STEPS[10])
        for target, hold in ((w.statusCanvas, 3500), (w.printProgressBar, 2500), (w.labelTimeRemaining, 1500),
                             (w.statusReqSpeed, 1500), (w.statusPosA, 1200), (w.statusPosRoll, 1500),
                             (w.gcodePause, 900), (w.gcodeResume, 700), (w.gcodeStopJob, 900), (w.labelSf, 1500)):
            yield from d.point_at(target, ms=600)
            yield hold
        yield from d.point_at(w.statusCanvas, ms=700)
        if not (yield from self.wait_for(lambda: getattr(w, 'run_active', False) is not True, 150)):
            print("ABORT: the run did not finish within the time", flush=True)
            return False
        print(f"  run took {time.perf_counter() - t_run:.1f} s", flush=True)
        yield 2000
        return True

    def run(self):
        w, d = self.w, self.d
        yield from d.step(*STEPS[0])
        yield 1500
        if not (yield from self.connect_and_home()):
            return
        yield from self.plan()
        if not (yield from self.upload()):
            return
        if not (yield from self.select_file()):
            return
        if not (yield from self.status_and_run()):
            return
        yield from d.step(*STEPS[11])
        if not w.input_ref_offset.isVisible() and getattr(w, 'check_advanced_mode', None) is not None:
            yield from d.click(w.check_advanced_mode)
            yield 800
        yield from d.point_at(w.statusCanvas, QPoint_at(w.statusCanvas, 0.12, 0.35), ms=800)
        yield 2500
        yield from d.until_left(5.5)
        yield from self.type_text(w.input_ref_offset, "0.4", per_char_ms=250)
        yield 1500
        yield from d.point_at(w.statusCanvas, QPoint_at(w.statusCanvas, 0.12, 0.35), ms=700)
        yield 2500
        yield from d.step(*STEPS[12])
        yield from d.point_at(w.status_modern.btn_record, ms=700)
        yield 1500
        yield from self.nav(5)
        yield 2500
        yield from d.step(*STEPS[13])
        yield from self.nav(1)
        self.ok = True


def check_plan(w):
    """--plan: G-code ranges per axis and the planned duration."""
    from fcn_plan.fcn_create import generate_planned_gcode
    text, name = generate_planned_gcode(w)
    rng, t, last = {}, 0.0, {}
    for line in (text or "").splitlines():
        if not line.startswith(("G1", "G0")):
            continue
        for m in re.finditer(r"('?[A-Z]|'[a-z])(-?\d+(?:\.\d+)?)", line.split(";")[0]):
            ax, v = m.group(1), float(m.group(2))
            if ax in ("G", "F", "P", "S"):
                continue
            lo, hi = rng.get(ax, (v, v))
            rng[ax] = (min(lo, v), max(hi, v))
    print("default name:", name, "| lines:", len((text or '').splitlines()))
    for ax in sorted(rng):
        print(f"  {ax:3s} {rng[ax][0]:8.3f} .. {rng[ax][1]:8.3f}")
    print("header:", [l for l in (text or '').splitlines()[:40] if l.startswith(('M203', 'M42', 'G90', 'G91', ';'))][:15])


def main():
    os.makedirs(OUT, exist_ok=True)
    cfg = os.path.join(r"C:\TRACE", "configuration.json")
    cfg_bak = os.path.join(tempfile.gettempdir(), "logiq_demo_intro_cfg.json")
    shutil.copy2(cfg, cfg_bak)
    if PLAN_ONLY:
        clips, durs = [], [0.2] * len(STEPS)
    else:
        clips = K.tts_clips([n for _c, _s, n in STEPS], os.path.join(OUT, f"{TAG}_clips"), rate=-1, speed=0.95)
        durs = [dd for _p, dd in clips]

    app = QApplication.instance() or QApplication(sys.argv)
    for eff in (Qt.UI_AnimateMenu, Qt.UI_FadeMenu, Qt.UI_AnimateCombo, Qt.UI_AnimateTooltip, Qt.UI_FadeTooltip):
        QApplication.setEffectEnabled(eff, False)
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

    keep_top = QTimer()
    keep_top.timeout.connect(overlay_on_top)
    keep_top.start(250)
    d = K.PacedDirector(ov, durs, speed=8.0 if PLAN_ONLY else 1.0)
    demo = Intro(w, d, ov)
    rec = K.Recorder(os.path.join(OUT, f"{TAG}_silent.mp4"), None)

    def run():
        yield 1500
        if PLAN_ONLY:
            yield from demo.plan()
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
        if PLAN_ONLY:
            try:
                check_plan(w)
            except Exception as e:
                import traceback
                traceback.print_exc()
        total = time.perf_counter() - (rec.t_start or d.t0 or time.perf_counter())
        if not PLAN_ONLY and rec.t_start is not None:
            err = rec.stop()
            if demo.ok:
                starts = [t for t, _c, _n in d.steps]
                d.write_srt(os.path.join(OUT, f"{TAG}.srt"), total)
                K.assemble_narration(clips, starts, os.path.join(OUT, f"{TAG}_narration.wav"), total)
                rc, merr = K.mux_audio(os.path.join(OUT, f"{TAG}_silent.mp4"),
                                       os.path.join(OUT, f"{TAG}_narration.wav"), os.path.join(OUT, f"{TAG}.mp4"))
                print("recorder:", (err or "").strip() or "ok", "| mux:", rc, (merr or "").strip()[:300], flush=True)
                bl = K.black_segments(os.path.join(OUT, f"{TAG}_silent.mp4"))
                print("black stretches:", bl if bl else "none", flush=True)
            else:
                print("recording stopped early (demo aborted): video not assembled", flush=True)
        print("completed:", demo.ok, "| steps:", [(round(tt, 1), c) for tt, c, _n in d.steps], "| total",
              round(total, 1), flush=True)
        print("log file:", getattr(w, 'last_log_path', None) or getattr(w, 'active_log_path', None), flush=True)
        keep_top.stop()
        ov.close()
        w.close()
        shutil.copy2(cfg_bak, cfg)
        app.quit()

    d.run(run(), on_finish=finish)
    app.exec()


if __name__ == "__main__":
    main()
