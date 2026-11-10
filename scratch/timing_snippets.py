"""Plays two stretches of logs_analysis.gcode on the controller with board timestamps (M400 + echo uptime) and
compares the measured time with the G-code time model: the last breathing cycle (hold right after the SI return)
and an earlier cycle (normal hold).   python scratch/timing_snippets.py [IP]"""
import json, re, sys, time
import requests
sys.path.insert(0, r"C:\TRACE")
from fcn_plan.fcn_gcode import parse_gcode_timeline
IP = "172.18.38.129"
S = requests.Session(); S.trust_env = False
B = f"http://{IP}"
OUT = "0:/gcodes/timing_test.txt"
import os
L = open(os.environ.get("SNIP_GCODE", r"C:\TRACE\demo\output\logs_analysis.gcode")).read().splitlines()
head = [l for l in L[:12] if l.startswith(("M566", "M201", "M203", "; STEP_OVERHEAD"))]
p = parse_gcode_timeline(L)
mv_idx = [k for k, l in enumerate(L) if l.startswith(("G1", "G4"))]
times = [r['time'] for r in p.rows]


def snippet(t0, t1):
    ks = [k for k, t in zip(mv_idx, times) if t0 <= t <= t1]
    start = L[ks[0] - 1] if L[ks[0] - 1].startswith("G1") else L[ks[0]]
    body = [L[k] for k in range(ks[0], ks[-1] + 1) if L[k].startswith(("G1", "G4"))]
    model = parse_gcode_timeline(head + ["G90", re.sub(r"F[\d.]+", "F600", start)] + body).time - \
        parse_gcode_timeline(head + ["G90", re.sub(r"F[\d.]+", "F600", start)]).time
    return start, body, model


def status():
    try:
        return S.get(f"{B}/rr_model?key=state.status", timeout=3).json().get("result")
    except Exception:
        return None


def run(name, t0, t1):
    start, body, model = snippet(t0, t1)
    if name.endswith("noG4"):
        body = [l for l in body if not l.startswith("G4")]
        st0 = ["G90", re.sub(r"F[\d.]+", "F600", start)]
        model = parse_gcode_timeline(head + st0 + body).time - parse_gcode_timeline(head + st0).time
    g = head + ["G90", re.sub(r"F[\d.]+", "F600", start), "M400", "G4 P300",
                f'echo >>"{OUT}" "{name} start " ^ state.msUpTime ^ " " ^ state.upTime'] + body + \
        ["M400", f'echo >>"{OUT}" "{name} end " ^ state.msUpTime ^ " " ^ state.upTime',
         "G1 F600 A0 B0 C0 D0 'e0 'f0 'a0 'c0"]
    path = f"0:/gcodes/timing_{name}.gcode"
    S.post(f"{B}/rr_upload", params={"name": path}, data="\n".join(g).encode(), timeout=20)
    S.get(f"{B}/rr_gcode", params={"gcode": f'M32 "{path}"'}, timeout=4)
    t = time.time(); seen = False
    while time.time() - t < 120:
        s = status()
        if s in ("processing", "busy"):
            seen = True
        elif seen and s == "idle":
            break
        time.sleep(0.2)
    return model, len(body)


if status() != "idle":
    sys.exit("controller not idle")
S.get(f"{B}/rr_gcode", params={"gcode": f'echo >"{OUT}" "begin 0 0"'}, timeout=4)
res = {}
PARTS = [a for a in sys.argv[2:]] or None
SN = (("cyc", 41.0, 45.0), ("cyc_noG4", 41.0, 45.0), ("cyc3", 37.0, 49.0))
for name, a, b in SN:
    res[name] = run(name, a, b)
    time.sleep(1)
txt = S.get(f"{B}/rr_download", params={"name": OUT}, timeout=5).text
st = {}
for line in txt.splitlines():
    q = line.split()
    if len(q) >= 4:
        st.setdefault(q[0], {})[q[1]] = int(q[3]) * 1000 + int(q[2])
for name, (model, n) in res.items():
    d = st.get(name, {})
    if "start" in d and "end" in d:
        meas = (d["end"] - d["start"]) / 1000
        print(f"{name:14s} lines {n:4d}  model {model:7.3f} s  measured {meas:7.3f} s  diff {meas - model:+.3f} s")
