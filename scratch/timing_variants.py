"""Variants of the last-cycle stretch (50.2-51.6 s of logs_analysis.gcode) timed on the controller, to find what makes
the slow AP step 'G1 F14.047043 A10.053848 ...' after 'G4 P5' run fast.   python scratch/timing_variants.py"""
import re, sys, time
sys.path.insert(0, r"C:\TRACE"); sys.path.insert(0, r"C:\TRACE\scratch")
src = open(r"C:\TRACE\scratch\timing_snippets.py").read().split('if status() != "idle"')[0]
exec(src)
start, body, _m = snippet(50.2, 51.6)
for k, l in enumerate(body):
    print(k, l[:100])
i_g4 = next(k for k, l in enumerate(body) if l.startswith("G4"))
i_step = len(body) - 1


def model(b):
    st = ["G90", re.sub(r"F[\d.]+", "F600", start)]
    return parse_gcode_timeline(head + st + b).time - parse_gcode_timeline(head + st).time


def no_si(l):                       # the SI axes stay where they are at 50.2 s
    m = re.search(r"'a([\d.]+)", start)
    return re.sub(r"'a[\d.]+", f"'a{m.group(1)}", re.sub(r"'c[\d.]+", f"'c{m.group(1)}", l)) if l.startswith("G1") else l


V = {
    "orig": body,
    "g4_p100": body[:i_g4] + ["G4 P100"] + body[i_g4 + 1:],
    "m400_before_step": body[:i_step] + ["M400"] + body[i_step:],
    "no_tiny_before_g4": body[:i_g4 - 1] + body[i_g4:],
    "step_F_again": body[:i_step] + ["G1 F14.047043"] + body[i_step:],
}
res = {}
for name, b in V.items():
    m = model(b)
    g = head + ["G90", re.sub(r"F[\d.]+", "F600", start), "M400", "G4 P300",
                f'echo >>"{OUT}" "{name} start " ^ state.msUpTime ^ " " ^ state.upTime'] + b + \
        ["M400", f'echo >>"{OUT}" "{name} end " ^ state.msUpTime ^ " " ^ state.upTime', "G1 F600 A0 B0 C0 D0 'e0 'f0 'a0 'c0"]
    path = f"0:/gcodes/timing_{name}.gcode"
    S.post(f"{B}/rr_upload", params={"name": path}, data="\n".join(g).encode(), timeout=20)
    S.get(f"{B}/rr_gcode", params={"gcode": f'M32 "{path}"'}, timeout=4)
    t, seen = time.time(), False
    while time.time() - t < 120:
        s = status()
        if s in ("processing", "busy"):
            seen = True
        elif seen and s == "idle":
            break
        time.sleep(0.2)
    res[name] = m
    time.sleep(0.8)
txt = S.get(f"{B}/rr_download", params={"name": OUT}, timeout=5).text
st = {}
for line in txt.splitlines():
    q = line.split()
    if len(q) >= 4:
        st.setdefault(q[0], {})[q[1]] = int(q[3]) * 1000 + int(q[2])
for name, m in res.items():
    d = st.get(name, {})
    if "start" in d and "end" in d:
        meas = (d["end"] - d["start"]) / 1000
        print(f"{name:20s} model {m:6.3f}  measured {meas:6.3f}  diff {meas - m:+.3f}")
