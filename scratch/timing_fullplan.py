"""Full-plan replay on the controller with board timestamps: LogIQ's G-code as written vs the same G-code with the
unchanged axes left out of every G1 line.  Measured time of the motion vs the planned 60 s.

    python scratch/timing_fullplan.py demo/output/logs_analysis_62.gcode
"""
import re
import sys
import time

import requests

IP = "172.18.38.129"
S = requests.Session()
S.trust_env = False
B = f"http://{IP}"
OUT = "0:/gcodes/timing_test.txt"
AX = re.compile(r"('?[A-Za-z])([-+]?\d+(?:\.\d+)?)")


def strip_unchanged(lines):
    """G1 lines keep F and only the axes whose value differs from the previous position."""
    pos, out = {}, []
    for l in lines:
        if not l.startswith(("G1 ", "G0 ")):
            out.append(l)
            continue
        words = l.split()
        keep = [words[0]]
        for w in words[1:]:
            m = AX.fullmatch(w)
            if not m:
                keep.append(w)
                continue
            a, v = m.group(1), m.group(2)
            if a == "F" or pos.get(a) != v:
                keep.append(w)
            if a != "F":
                pos[a] = v
        if len([w for w in keep[1:] if not w.startswith("F")]) == 0:
            continue                                   # nothing moves: drop the line (it takes no time)
        out.append(" ".join(keep))
    return out


def status():
    try:
        return S.get(f"{B}/rr_model?key=state.status", timeout=3).json().get("result")
    except Exception:
        return None


def play(name, lines):
    first = next(k for k, l in enumerate(lines) if l.startswith("G1"))
    g = lines[:first + 1] + ["M400", "G4 P300", f'echo >>"{OUT}" "{name} start " ^ state.msUpTime ^ " " ^ state.upTime'] \
        + lines[first + 1:] + ["M400", f'echo >>"{OUT}" "{name} end " ^ state.msUpTime ^ " " ^ state.upTime']
    path = f"0:/gcodes/timing_{name}.gcode"
    S.post(f"{B}/rr_upload", params={"name": path}, data="\n".join(g).encode(), timeout=30)
    S.get(f"{B}/rr_gcode", params={"gcode": f'M32 "{path}"'}, timeout=4)
    t, seen = time.time(), False
    while time.time() - t < 200:
        s = status()
        if s in ("processing", "busy"):
            seen = True
        elif seen and s == "idle":
            break
        time.sleep(0.3)
    time.sleep(1)


def main():
    src = sys.argv[1]
    lines = open(src).read().splitlines()
    stripped = strip_unchanged(lines)
    open(src.replace(".gcode", "_stripped.gcode"), "w").write("\n".join(stripped) + "\n")
    print("lines:", len(lines), "->", len(stripped))
    if status() != "idle":
        sys.exit("controller not idle")
    S.get(f"{B}/rr_gcode", params={"gcode": f'echo >"{OUT}" "begin 0 0"'}, timeout=4)
    play("asis", lines)
    play("stripped", stripped)
    txt = S.get(f"{B}/rr_download", params={"name": OUT}, timeout=5).text
    st = {}
    for line in txt.splitlines():
        q = line.split()
        if len(q) >= 4:
            st.setdefault(q[0], {})[q[1]] = int(q[3]) * 1000 + int(q[2])
    for name in ("asis", "stripped"):
        d = st.get(name, {})
        if "start" in d and "end" in d:
            print(f"{name:9s} motion {(d['end'] - d['start']) / 1000:7.3f} s   (planned 60.000 s from the first move)")


if __name__ == "__main__":
    main()
