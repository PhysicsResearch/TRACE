"""Controller timing of G1 segment streams (KINETIQ, AP only, 10..20 mm): how long N short lines really take.

Each test file moves A B C D together (AP) up 10 mm and down again at constant speed, split into segments of a
given duration.  The board stamps its own uptime (ms) after M400 before and after the segment stream into
0:/gcodes/timing_test.txt, so the measured time does not depend on network polling.

    python scratch/timing_tests.py [IP]
"""
import json
import sys
import time

import requests

IP = sys.argv[1] if len(sys.argv) > 1 else "172.18.38.129"
BASE = f"http://{IP}"
S = requests.Session()
S.trust_env = False
OUT = "0:/gcodes/timing_test.txt"
ZERO = "'e0.000000 'f0.000000 'a0.000000 'c0.000000"

# (name, segment s, speed mm/s per axis, with the 4 idle axes on every line)
TESTS = [            # (name, segment s, speed, idle axes, dwell after each segment: None | 'g4p10' | 'hold')
    ("base_2lines", None, 1.0, True, None),
    ("seg20ms", 0.020, 1.0, True, None),
    ("seg400ms_g4p10", 0.400, 1.0, True, 'g4p10'),
    ("seg400ms_g4p0", 0.400, 1.0, True, 'g4p0'),
    ("seg400ms_hold", 0.400, 1.0, True, 'hold'),
]
DWELL = {'g4p10': ["G4 P10"], 'g4p0': ["G4 P0"],
         # the hold the G-code writer emits at the bottom of a cos^6 cycle (180 ms of dwell in 3 G4)
         'hold': ["G4 P20", "@tiny", "G4 P150", "@tiny", "G4 P10"]}
DWELL_S = {'g4p10': 0.010, 'g4p0': 0.0, 'hold': 0.180}


def gline(ap, f_vec, idle):
    s = f"G1 F{f_vec:.6f} A{ap:.6f} B{ap:.6f} C{ap:.6f} D{ap:.6f}"
    return s + (" " + ZERO if idle else "")


def make(name, seg, speed, idle, dwell=None):
    lines = ["G90", "M400", f"G1 F600 A10 B10 C10 D10 {ZERO}", "M400", "G4 P300",
             f'echo >>"{OUT}" "{name} start " ^ state.msUpTime ^ " " ^ state.upTime']
    f_vec = 2.0 * speed * 60.0                    # 4 axes move the same: |d| = 2 * d per axis
    reps = max(1, int(round(10.0 / speed)))       # about 20 s of motion
    planned = 0.0
    for _r in range(1):
        for a, b in ((10.0, 20.0), (20.0, 10.0)):
            if seg is None:
                lines.append(gline(b, f_vec, idle))
                planned += 10.0 / speed
                continue
            n = int(round((10.0 / speed) / seg))
            for k in range(1, n + 1):
                ap = a + (b - a) * k / n
                lines.append(gline(ap, f_vec, idle))
                if dwell:
                    for dl in DWELL[dwell]:
                        lines.append(f"G1 F600 A{ap + 1e-6:.6f} B{ap + 1e-6:.6f} C{ap + 1e-6:.6f} D{ap + 1e-6:.6f}"
                                     if dl == "@tiny" else dl)
                    planned += DWELL_S[dwell]
            planned += 10.0 / speed
    lines += ["M400", f'echo >>"{OUT}" "{name} end " ^ state.msUpTime ^ " " ^ state.upTime']
    return ("\n".join(lines) + "\n", planned, sum(1 for l in lines if l.startswith("G1 F") and "A10 B10" not in l),
            sum(1 for l in lines if l.startswith("G4")) - 1)          # without the G4 P300 before the start stamp


def status():
    try:
        return S.get(f"{BASE}/rr_model?key=state.status", timeout=3).json().get("result")
    except Exception:
        return None


def run(path):
    S.get(f"{BASE}/rr_gcode", params={"gcode": f'M32 "{path}"'}, timeout=4)
    t0 = time.time()
    seen = False
    while time.time() - t0 < 200:
        s = status()
        if s in ("processing", "busy", "simulating"):
            seen = True
        elif seen and s == "idle":
            return True
        time.sleep(0.2)
    return False


def main():
    if status() != "idle":
        sys.exit("controller not idle")
    S.get(f"{BASE}/rr_gcode", params={"gcode": f'echo >"{OUT}" "begin 0 0"'}, timeout=4)   # creates the file
    plan = {}
    for name, seg, speed, idle, dwell in TESTS:
        text, planned, n, n_g4 = make(name, seg, speed, idle, dwell)
        path = f"0:/gcodes/timing_{name}.gcode"
        r = S.post(f"{BASE}/rr_upload", params={"name": path}, data=text.encode(), timeout=20)
        if r.status_code != 200 or json.loads(r.text).get("err", 1) != 0:
            sys.exit(f"upload failed {name}: {r.text}")
        plan[name] = (planned, n, n_g4)
        print(f"run {name}: {n} lines, planned {planned:.2f} s", flush=True)
        if not run(path):
            sys.exit(f"{name} did not finish")
        time.sleep(1.0)
    txt = S.get(f"{BASE}/rr_download", params={"name": OUT}, timeout=5).text
    t = {}
    for line in txt.splitlines():
        p = line.split()
        if len(p) >= 4:
            t.setdefault(p[0], {})[p[1]] = int(p[3]) * 1000 + int(p[2])
    print("\n%-16s %6s %5s %9s %9s %9s %10s %9s" % ("test", "lines", "G4", "planned", "measured", "extra",
                                                    "ms / line", "ms / G4"))
    for name, (planned, n, n_g4) in plan.items():
        d = t.get(name, {})
        if "start" in d and "end" in d:
            meas = (d["end"] - d["start"]) / 1000.0
            print("%-16s %6d %5d %9.3f %9.3f %9.3f %10.3f %9s" % (
                name, n, n_g4, planned, meas, meas - planned, 1000 * (meas - planned) / max(n, 1),
                f"{1000 * (meas - planned) / n_g4:.1f}" if n_g4 > 0 else "-"))
    print("\nraw:", txt)


if __name__ == "__main__":
    main()
