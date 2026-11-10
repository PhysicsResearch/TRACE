"""
The plan for the Log files video, built in the app, and its 3 recorded runs on KINETIQ (not filmed).

Plan (KINETIQ, 60 s):
  AP   0 -> 10 mm in 3 s, cos^6 breathing 10..20 mm, period 4 s, 3..55 s (13 cycles), 10 -> 0 in 3 s
  LAT  steps of +3 mm: 0->3 at 6 s (0.5 s ramp), 3->6 at 12 s (1 s), 6->9 at 18 s (2 s); 9->0 at 46 s (2 s)
  SI   steps of +3 mm: 0->3 at 24 s (0.5 s ramp), 3->6 at 30 s (1 s), 6->9 at 36 s (2 s); 9->0 at 49 s (2 s)

    python demo/logs_runs.py --plan      offline: builds the plan, prints the G-code ranges (nothing sent)
    python demo/logs_runs.py             uploads logs_analysis.gcode and runs it RUNS times, Record on
Environment: DEMO_IP (default 172.18.38.129), RUNS (default 3).  The platform must be homed.
The log files are written to the app's output folder; their paths are printed at the end.
"""
import glob
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
from PySide6.QtWidgets import QApplication, QLineEdit, QPushButton

import demo_kit as K

IP = os.environ.get("DEMO_IP", "172.18.38.129")
RUNS = int(os.environ.get("RUNS", "3"))
PLAN_ONLY = "--plan" in sys.argv
GCODE_FILE = os.environ.get("GCODE_FILE")          # run this ready G-code file instead of planning in the app
FILE_NAME = os.path.basename(GCODE_FILE) if GCODE_FILE else "logs_analysis.gcode"
TOTAL_S = 60
STEP_OVERHEAD_MS = float(os.environ.get("STEP_OVERHEAD_MS", "90"))   # measured: a G4 within motion costs ~90 ms
                                                                     # on this controller (scratch/timing_tests.py)

AP_BASE, AP_AMP, AP_PERIOD, AP_T0, AP_T1 = 10, 10, 4, 3, 55
STEP_MM = 3
LAT_STEPS = [(6, 0.5), (12, 1.0), (18, 2.0)]      # (start s, ramp s)
SI_STEPS = [(24, 0.5), (30, 1.0), (36, 2.0)]
LAT_BACK = (46, 2.0)
SI_BACK = (49, 2.0)


def plan_segments():
    """(axis, [(func, amp, off, period, start, end, phase)])  - linear: amp = from, off = to, period = duration."""
    ap = [('linear', 0, AP_BASE, AP_T0, 0, None, None),
          ('cos^6', AP_AMP, AP_BASE, AP_PERIOD, AP_T0, AP_T1, 180),
          ('linear', AP_BASE, 0, 3, AP_T1, None, None)]

    def steps(seq, back):
        out, v = [], 0
        for k, (t, ramp) in enumerate(seq):
            out.append(('linear', v, v + STEP_MM, ramp, t, None, None))
            v += STEP_MM
            t_next = seq[k + 1][0] if k + 1 < len(seq) else back[0]
            out.append(('constant', v, 0, 4, t + ramp, t_next, None))
        out.append(('linear', v, 0, back[1], back[0], None, None))
        return out

    return [('AP', ap), ('LAT', steps(LAT_STEPS, LAT_BACK)), ('SI', steps(SI_STEPS, SI_BACK))]


class Runs:
    def __init__(self, w, d, ov):
        from demo_planning import Demo as PlanningDemo
        import demo_intro
        from demo_intro import Intro
        demo_intro.FILE_NAME = FILE_NAME         # its upload / select helpers use this name
        self.w, self.d = w, d
        self.pd = PlanningDemo(w, d, ov)
        self.it = Intro(w, d, ov)                # connect / upload / select helpers
        self.logs = []
        self.ok = False

    def plan(self):
        w, d, pd = self.w, self.d, self.pd
        yield from self.it.nav(3)
        yield from d.click(pd.p.device_buttons[1])           # KINETIQ
        yield 800
        yield from pd.type_value(pd.cc.total_spin, TOTAL_S)
        yield from pd.answer_modal(timeout_ms=1500)
        w.settings_step_overhead_plat.setValue(STEP_OVERHEAD_MS)
        if os.environ.get("MIN_SPEED"):
            w.settings_min_speed_plat.setValue(float(os.environ["MIN_SPEED"]))
        for axis, segs in plan_segments():
            yield from pd.set_axis(axis)
            for func, amp, off, period, start, end, phase in segs:
                yield from pd.segment(func, amp, off, period, start=start, end=end, phase=phase)
                yield from d.click(w.button_create_curve, pause_ms=300)
                yield 500
                if phase is not None:                          # back to 0 for the next segments
                    yield from pd.type_value(w.input_phase, 0)
        yield from pd.show_only(['LAT', 'SI', 'AP', 'A', 'B', 'C', 'D'])
        yield 800

    def connect(self):
        w = self.w
        yield from self.it.nav(0)
        w.DuetIPAddress.setText(IP)
        yield from self.d.click(w.setDuetIP)
        ok = yield from self.it.wait_for(lambda: getattr(w, 'duet_connected', False)
                                         and not getattr(w, '_connecting_in_progress', False), 25)
        if not ok:
            print("ABORT: could not connect to", IP, flush=True)
            return False
        yield 1500
        if not self.it.homed():
            print("ABORT: the platform is not homed", flush=True)
            return False
        return True

    def one_run(self, k):
        w, d, it = self.w, self.d, self.it
        if not (yield from it.select_file()):
            return False
        st = w.status_modern
        if not st.ref_pill.isChecked():                       # plan drawn next to the measured position
            yield from d.click(st.ref_pill)
            yield 500
        title = st.sections['phantom'][0]                     # DYNAMIQ curves off, KINETIQ LAT / SI / AP on
        if any(st.pills[k].isChecked() for k in st.sections['phantom'][1]):
            yield from d.click(title)
            yield 500
        for k in ('LAT', 'SI', 'AP'):
            if not st.pills[k].isChecked():
                yield from d.click(st.pills[k])
                yield 300
        if not st.btn_record.isChecked():
            yield from d.click(st.btn_record)
            yield 500
        folder = log_folder(w)
        before = set(glob.glob(os.path.join(folder, "log_*.csv")))
        yield from d.click(w.gcodeStart)
        if not (yield from it.wait_for(lambda: getattr(w, 'run_active', False) is True, 60)):
            print("ABORT: the run did not start", flush=True)
            return False
        t0 = time.perf_counter()
        if not (yield from it.wait_for(lambda: getattr(w, 'run_active', False) is not True, plan_seconds() + 90)):
            print("ABORT: the run did not finish", flush=True)
            return False
        yield 3000
        new = sorted(set(glob.glob(os.path.join(folder, "log_*.csv"))) - before, key=os.path.getmtime)
        print(f"  run {k}: {time.perf_counter() - t0:.1f} s, log {new[-1] if new else None}", flush=True)
        if new:
            self.logs.append(new[-1])
        return True

    def run(self):
        yield 1000
        if not (yield from self.connect()):
            return
        if GCODE_FILE:
            import requests
            sess = requests.Session()
            sess.trust_env = False
            r = sess.post(f"http://{IP}/rr_upload", params={"name": f"0:/gcodes/{FILE_NAME}"},
                          data=open(GCODE_FILE, "rb").read(), timeout=30)
            print("uploaded", FILE_NAME, r.status_code, r.text.strip(), flush=True)
        else:
            yield from self.plan()
            if not (yield from self.it.upload()):
                return
        for k in range(1, RUNS + 1):
            if not (yield from self.one_run(k)):
                return
            yield 4000
        self.ok = True


def plan_seconds():
    """Length of the plan: the '; TIME:' line of a ready G-code file (GCODE_FILE), else TOTAL_S."""
    if GCODE_FILE:
        import re
        with open(GCODE_FILE) as f:
            for line in f:
                m = re.match(r";\s*TIME:\s*([\d.]+)", line)
                if m:
                    return float(m.group(1))
    return float(TOTAL_S)


def log_folder(w):
    f = getattr(w, 'PhOperFolder', None)
    txt = f.text().strip() if f is not None else ""
    return txt or os.path.join(os.path.expanduser("~"), "Desktop")


def gcode_ranges(w):
    from fcn_plan.fcn_create import generate_planned_gcode
    text, name = generate_planned_gcode(w)
    rng = {}
    for line in (text or "").splitlines():
        if not line.startswith(("G1", "G0")):
            continue
        for m in re.finditer(r"('[a-z]|[A-Z])(-?\d+(?:\.\d+)?)", line.split(";")[0]):
            ax, v = m.group(1), float(m.group(2))
            if ax in ("G", "F", "P", "S"):
                continue
            lo, hi = rng.get(ax, (v, v))
            rng[ax] = (min(lo, v), max(hi, v))
    L = (text or '').splitlines()
    print("lines:", len(L), "| G4:", sum(1 for l in L if l.startswith("G4")),
          "|", next((l for l in L if "STEP_OVERHEAD" in l), ""))
    for ax in sorted(rng):
        print(f"  {ax:3s} {rng[ax][0]:8.3f} .. {rng[ax][1]:8.3f}")
    df = w.dfEdit
    for c in ('LAT', 'SI', 'AP'):
        if c in df.columns:
            print(f"  plan {c}: {df[c].min():.3f} .. {df[c].max():.3f}")
    return text


def main():
    cfg = os.path.join(r"C:\TRACE", "configuration.json")
    cfg_bak = os.path.join(tempfile.gettempdir(), "logiq_logs_runs_cfg.json")
    shutil.copy2(cfg, cfg_bak)
    from fcn_init.app_config import get_config_path      # the settings the app really saves (AppData)
    cfg_user = get_config_path("configuration.json", for_writing=True)
    cfg_user_bak = cfg_bak.replace(".json", "_user.json")
    if os.path.exists(cfg_user):
        shutil.copy2(cfg_user, cfg_user_bak)
    app = QApplication.instance() or QApplication(sys.argv)
    from demo_planning import build_window
    w = build_window()
    w.showMaximized()
    ov = K.Overlay()
    ov.show()
    d = K.Director(ov, speed=6.0)
    r = Runs(w, d, ov)

    def gen():
        if PLAN_ONLY:
            yield 1000
            yield from r.plan()
            r.ok = True
        else:
            yield from r.run()

    def finish():
        try:
            if GCODE_FILE:
                raise StopIteration
            text = gcode_ranges(w)
            if text:
                with open(os.path.join(r"C:\TRACE\demo\output", "logs_analysis.gcode"), "w") as f:
                    f.write(text)
        except StopIteration:
            pass
        except Exception:
            import traceback
            traceback.print_exc()
        print("completed:", r.ok, "| logs:", r.logs, flush=True)
        ov.close()
        w.close()
        shutil.copy2(cfg_bak, cfg)
        if os.path.exists(cfg_user_bak):
            shutil.copy2(cfg_user_bak, cfg_user)
        app.quit()

    d.run(gen(), on_finish=finish)
    app.exec()


if __name__ == "__main__":
    main()
