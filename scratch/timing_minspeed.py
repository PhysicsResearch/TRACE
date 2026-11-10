"""Controller timing of very slow moves around the minimum speed (M203 I6 = 0.1 mm/s), KINETIQ AP only.

Each test: 10 small AP moves (A B C D together, 0.0437 mm per axis, between 10.000 and 10.044 mm), stamped by the
board (M400 + echo uptime).  Measured time vs the G-code time model of LogIQ (fcn_plan.fcn_gcode).

    python scratch/timing_minspeed.py
"""
import sys
import time

import requests

sys.path.insert(0, r"C:\TRACE")
from fcn_plan.fcn_gcode import parse_gcode_timeline

IP = "172.18.38.129"
S = requests.Session()
S.trust_env = False
B = f"http://{IP}"
OUT = "0:/gcodes/timing_test.txt"
HEAD = ["M566 A600 B600 C600 D600 'c600 'a600  'f600 'e600", "M201 A1000 B1000 C1000 D1000 'c1000 'a1000  'f1000 'e1000",
        "M203 A1200 B1200 C1200 D1200 'c1200 'a1200  'f1200 'e1200", "M203 I6", "; STEP_OVERHEAD_MS: 0"]
LO, HI = 10.000001, 10.043702
D = HI - LO
IDLE = "'e0.000000 'f0.000000 'a0.000000 'c0.000000"


def ap(v, f):
    return f"G1 F{f:.6f} A{v:.6f} B{v:.6f} C{v:.6f} D{v:.6f} {IDLE}"


def vec_f(per_axis_mm_s):            # 4 equal axes: |d| = 2 * d per axis
    return 2.0 * per_axis_mm_s * 60.0


def series(per_axis, lead=None, dwell=None, n=10):
    """n slow moves LO<->HI at per_axis mm/s; lead = per-axis speed of a 0.05 mm move before each slow move
    (context: the slow move follows a faster one), dwell = 'G4 Pxx' after each slow move."""
    out, pos = [], LO
    for k in range(n):
        if lead:
            pos2 = pos + (0.05 if pos == LO else -0.05)
            out.append(ap(pos2, vec_f(lead)))
            pos = pos2
            tgt = pos2 - D if pos2 > LO + D / 2 else pos2 + D
        else:
            tgt = HI if pos == LO else LO
        out.append(ap(tgt, vec_f(per_axis)))
        pos = tgt
        if dwell:
            out.append(dwell)
    return out


TESTS = [
    ("rest_0.0993", series(0.0993)),            # the plan's F11.918 move, from rest each time
    ("rest_0.117", series(0.117)),              # the plan's F14.047 move speed
    ("rest_0.15", series(0.15)),
    ("rest_0.20", series(0.20)),
    ("rest_0.05", series(0.05)),                # below the minimum
    ("lead_0.0993", series(0.0993, lead=0.33)),  # after a faster move, as inside the plan
    ("rest_0.0993_g4", series(0.0993, dwell="G4 P85")),
]


def status():
    try:
        return S.get(f"{B}/rr_model?key=state.status", timeout=3).json().get("result")
    except Exception:
        return None


def run(name, body):
    start = ap(LO, 600.0)
    g = HEAD + ["G90", start, "M400", "G4 P300",
                f'echo >>"{OUT}" "{name} start " ^ state.msUpTime ^ " " ^ state.upTime'] + body + \
        ["M400", f'echo >>"{OUT}" "{name} end " ^ state.msUpTime ^ " " ^ state.upTime']
    model = parse_gcode_timeline(HEAD + ["G90", start] + body).time - parse_gcode_timeline(HEAD + ["G90", start]).time
    path = f"0:/gcodes/timing_{name}.gcode"
    S.post(f"{B}/rr_upload", params={"name": path}, data="\n".join(g).encode(), timeout=20)
    S.get(f"{B}/rr_gcode", params={"gcode": f'M32 "{path}"'}, timeout=4)
    t, seen = time.time(), False
    while time.time() - t < 200:
        s = status()
        if s in ("processing", "busy"):
            seen = True
        elif seen and s == "idle":
            break
        time.sleep(0.2)
    return model


def main():
    if status() != "idle":
        sys.exit("controller not idle")
    S.get(f"{B}/rr_gcode", params={"gcode": f'echo >"{OUT}" "begin 0 0"'}, timeout=4)
    models = {}
    for name, body in TESTS:
        models[name] = (run(name, body), sum(1 for l in body if l.startswith("G1")))
        print("ran", name, flush=True)
        time.sleep(0.8)
    txt = S.get(f"{B}/rr_download", params={"name": OUT}, timeout=5).text
    st = {}
    for line in txt.splitlines():
        q = line.split()
        if len(q) >= 4:
            st.setdefault(q[0], {})[q[1]] = int(q[3]) * 1000 + int(q[2])
    print(f"\n{'test':16s} {'moves':>5s} {'model s':>8s} {'meas s':>8s} {'diff s':>8s}")
    for name, (model, n) in models.items():
        d = st.get(name, {})
        if "start" in d and "end" in d:
            meas = (d["end"] - d["start"]) / 1000
            print(f"{name:16s} {n:5d} {model:8.3f} {meas:8.3f} {meas - model:+8.3f}")
    S.get(f"{B}/rr_gcode", params={"gcode": "G1 F600 A0 B0 C0 D0"}, timeout=4)


if __name__ == "__main__":
    main()
