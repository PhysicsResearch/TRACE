"""How long the slow AP step 'G1 F14.047043 A..+0.0538' takes (modelled 0.46 s) after different preceding moves.
The board stamps right before and after the step (M400 + echo uptime).   python scratch/timing_step_after.py"""
import sys
import time

import requests

IP = "172.18.38.129"
S = requests.Session()
S.trust_env = False
B = f"http://{IP}"
OUT = "0:/gcodes/timing_test.txt"
HEAD = ["M566 A600 B600 C600 D600 'c600 'a600  'f600 'e600", "M201 A1000 B1000 C1000 D1000 'c1000 'a1000  'f1000 'e1000",
        "M203 A1200 B1200 C1200 D1200 'c1200 'a1200  'f1200 'e1200", "M203 I6", "G90"]


def L(ap, e=0.0, a=0.0, f=600.0):
    return f"G1 F{f:.6f} A{ap:.6f} B{ap:.6f} C{ap:.6f} D{ap:.6f} 'e{e:.6f} 'f{e:.6f} 'a{a:.6f} 'c{a:.6f}"


STEP = "G1 F14.047043 A10.053848 B10.053848 C10.053848 D10.053848 'e{e:.6f} 'f{e:.6f} 'a{a:.6f} 'c{a:.6f}"
STEP_AD = "G1 F14.047043 A10.053848 B10.053848 C10.053848 D10.053848"          # unchanged axes left out

# name: (start line, lines before the step, (e, a) during the step)
CASES = {
    "rest":            (L(10.000001), [], (0, 0)),
    "after_ap_only":   (L(10.1), [L(10.000001, f=24)], (0, 0)),
    "after_si_to0":    (L(10.0, a=2.0), [L(10.000001, a=0.0, f=381.837662)], (0, 0)),
    "after_si_to1":    (L(10.0, a=3.0), [L(10.000001, a=1.0, f=381.837662)], (0, 1)),
    "after_lat_to0":   (L(10.0, e=2.0), [L(10.000001, e=0.0, f=381.837662)], (0, 0)),
    "si_at0_noprev":   (L(10.000001, a=0.0), [], (0, 0)),
    "si_at1_noprev":   (L(10.000001, a=1.0), [], (0, 1)),
    "AD_after_si_to0": (L(10.0, a=2.0), [L(10.000001, a=0.0, f=381.837662)], None),
    "AD_after_si_to1": (L(10.0, a=3.0), [L(10.000001, a=1.0, f=381.837662)], None),
    "AD_after_lat_to0": (L(10.0, e=2.0), [L(10.000001, e=0.0, f=381.837662)], None),
}
import os
if os.environ.get("ONLY_AD"):
    CASES = {k: v for k, v in CASES.items() if k.startswith("AD_") or k == "after_si_to0"}


def status():
    try:
        return S.get(f"{B}/rr_model?key=state.status", timeout=3).json().get("result")
    except Exception:
        return None


def main():
    if status() != "idle":
        sys.exit("controller not idle")
    S.get(f"{B}/rr_gcode", params={"gcode": f'echo >"{OUT}" "begin 0 0"'}, timeout=4)
    for name, (start, before, ea) in CASES.items():
        step = STEP_AD if ea is None else STEP.format(e=ea[0], a=ea[1])
        g = HEAD + [start, "M400"] + before + ["M400", "G4 P200",
                    f'echo >>"{OUT}" "{name} start " ^ state.msUpTime ^ " " ^ state.upTime',
                    step, "M400",
                    f'echo >>"{OUT}" "{name} end " ^ state.msUpTime ^ " " ^ state.upTime',
                    "G1 F600 A0 B0 C0 D0 'e0 'f0 'a0 'c0"]
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
        time.sleep(0.8)
        print("ran", name, flush=True)
    txt = S.get(f"{B}/rr_download", params={"name": OUT}, timeout=5).text
    st = {}
    for line in txt.splitlines():
        q = line.split()
        if len(q) >= 4:
            st.setdefault(q[0], {})[q[1]] = int(q[3]) * 1000 + int(q[2])
    print("\nstep modelled 0.460 s (stamp overhead ~0.04-0.08 s)")
    for name in CASES:
        d = st.get(name, {})
        if "start" in d and "end" in d:
            print(f"{name:16s} measured {(d['end'] - d['start']) / 1000:6.3f} s")


if __name__ == "__main__":
    main()
