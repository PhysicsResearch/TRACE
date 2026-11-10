"""
Checks for the stepped-motion bake and the faithful G-code emitter (fcn_plan/fcn_gcode.py).
Run:  C:\\Users\\gabri\\anaconda3\\envs\\TRACE\\python.exe scratch\\test_stepped_plan.py
"""
import os
import subprocess
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import numpy as np

from fcn_plan.fcn_gcode import (
    DUET_MIN_SPEED, bake_stepped_plan, generate_gcode_string, parse_gcode_timeline,
    compute_gcode_axes,
)

LIM6 = (40.0,) * 6
LIM3 = (40.0,) * 3
PLAT = dict(lat_dim=300.0, si_dim=500.0, off_ap=0.0, off_lat=0.0, off_si=0.0, axis_y_lo="'c")
FAILS = []


def check(cond, msg):
    print(("PASS  " if cond else "FAIL  ") + msg)
    if not cond:
        FAILS.append(msg)


def grid(dt, t_end):
    return np.round(np.arange(0.0, t_end + dt / 2.0, dt), 9)


def platform_cols(t, **kw):
    z = np.zeros_like(t)
    cols = {c: kw.get(c, z).astype(float) for c in ("LAT", "SI", "AP", "Roll", "Pitch", "Yaw")}
    return cols


def bake(device, t, cols, limits, min_step=0.05, **kw):
    out = bake_stepped_plan(device, t, cols, limits, min_step=min_step, max_speed=20.0, **kw)
    new = dict(cols)
    if out:
        new.update(out)
    return new


def gcode_and_timeline(device, t, cols, limits, overhead=0.0, **kw):
    info = {}
    g, _ = generate_gcode_string(device, t, cols, limits, speed=20, acc=500, jerk=300,
                                 step_overhead_ms=overhead, info=info, **kw)
    p = parse_gcode_timeline(g.splitlines())
    return g, p, info


def feeds(g):
    out = []
    for l in g.splitlines():
        if l.startswith("G1 "):
            out.append(float(l.split()[1][1:]))
    return out


def timeline_matches(p, t, baked_axis_vals, key, tol=2e-3):
    """Interpolate parsed timeline at plan times and compare with the expected axis values."""
    tt = np.array([r["time"] for r in p.rows])
    vv = np.array([r.get(key, np.nan) for r in p.rows])
    order = np.argsort(tt, kind="stable")
    rec = np.interp(t, tt[order], vv[order])
    return float(np.max(np.abs(rec - baked_axis_vals)))


def ramp_case(dt, amp=2.5):
    t = grid(dt, 40.0)
    si = np.where(t <= 25.0, amp * t / 25.0, amp)
    return t, si


# --------------------------------------------------------------------------
print("=== 1a. Ramp 2.5 mm / 25 s = 0.1 mm/s (platform SI): continuous with Duet min speed 0.1 mm/s ===")
for dt in (0.01, 0.001):
    t, si = ramp_case(dt, 2.5)
    cols = platform_cols(t, SI=si)
    b = bake("Motion Platform", t, cols, LIM6, **PLAT)
    bsi = b["SI"]
    check(np.max(np.abs(bsi - si)) <= 1e-9, f"dt={dt}: baked == plan (straight ramp kept, dev {np.max(np.abs(bsi - si)):.1e})")
    g, p, info = gcode_and_timeline("Motion Platform", t, b, LIM6, **PLAT)
    check("M203 I6" in g.splitlines()[:8], "header sets the Duet minimum speed: M203 I6")
    f = feeds(g)[1:]
    ramp_f = [x for x in f if x < 100]
    check(min(f) >= 6.0 - 1e-6, f"dt={dt}: no feed below F6 (min F{min(f):.3f})")
    check(len(ramp_f) >= 1 and all(abs(x - np.sqrt(2) * 0.1 * 60) < 1e-3 for x in ramp_f),
          f"dt={dt}: ramp F = sqrt2*0.1*60 = 8.485 ({len(ramp_f)} G1)")
    check(info["dwells"] == 1, f"dt={dt}: only the final hold is a dwell ({info['dwells']})")
    check(abs(p.time - t[-1]) <= 1e-3, f"dt={dt}: parsed duration {p.time:.4f} s == plan {t[-1]:.1f} s")

print("\n=== 1b. Ramp 0.5 mm / 25 s = 0.02 mm/s (< 0.1 mm/s): staircase of 0.05 mm ===")
for dt in (0.01, 0.001):
    t, si = ramp_case(dt, 0.5)
    cols = platform_cols(t, SI=si)
    b = bake("Motion Platform", t, cols, LIM6, **PLAT)
    bsi = b["SI"]
    levels = np.unique(np.round(bsi, 9))
    check(np.max(np.abs(bsi - si)) <= 0.05 + 1e-9, f"dt={dt}: |baked-plan| <= 0.05 (got {np.max(np.abs(bsi - si)):.4f})")
    check(abs(bsi[-1] - 0.5) < 1e-12 and abs(bsi[np.searchsorted(t, 30.0)] - 0.5) < 1e-12, f"dt={dt}: hold value exact (0.5)")
    check(len(levels) >= 11, f"dt={dt}: staircase has {len(levels)} levels")
    b2 = bake("Motion Platform", t, b, LIM6, **PLAT)
    check(np.max(np.abs(b2["SI"] - bsi)) <= 1e-9, f"dt={dt}: bake is idempotent")

    for ov in (0.0, 25.0):
        g, p, info = gcode_and_timeline("Motion Platform", t, b, LIM6, overhead=ov, **PLAT)
        f = feeds(g)[1:]
        check(min(f) >= 6.0 - 1e-6, f"dt={dt} ov={ov}: no feed below F6 (min F{min(f):.1f})")
        check(abs(p.time - t[-1]) <= 1e-3, f"dt={dt} ov={ov}: parsed duration {p.time:.4f} s == plan {t[-1]:.1f} s")
        n_g4 = sum(1 for l in g.splitlines() if l.startswith("G4"))
        check(8 <= n_g4 <= 14, f"dt={dt} ov={ov}: {n_g4} dwells, {info['moves']} moves")
        err = timeline_matches(p, t, bsi, "'a")
        check(err <= 0.051, f"dt={dt} ov={ov}: parsed G-code follows the baked curve (max err {err:.4f} mm)")

print("\n=== 2. Slow ramps on Lung Phantom X and Other A ===")
for amp in (2.5, 0.5):
    t, si = ramp_case(0.01, amp)
    z = np.zeros_like(t)
    cols_p = {"X": si, "Y": z, "Z": z}
    b = bake("Lung Phantom", t, cols_p, LIM3)
    g, p, _ = gcode_and_timeline("Lung Phantom", t, b, LIM3)
    check(abs(p.time - t[-1]) <= 1e-3 and min(feeds(g)[1:]) >= 6 - 1e-6,
          f"Lung Phantom {amp} mm: duration {p.time:.4f} s, min F {min(feeds(g)[1:]):.2f}")
    cols_o = {"A": si, "B": z}
    b = bake("Other", t, cols_o, [40.0])
    g, p, _ = gcode_and_timeline("Other", t, b, [40.0])
    check(abs(p.time - t[-1]) <= 1e-3 and min(feeds(g)[1:]) >= 6 - 1e-6,
          f"Other {amp} mm: duration {p.time:.4f} s, min F {min(feeds(g)[1:]):.2f}")

print("\n=== 3. Fast motion stays continuous, F follows RRF rules ===")
t = grid(0.01, 20.0)
sine = 10.0 + 10.0 * np.sin(2 * np.pi * t / 4.0)
cols = platform_cols(t, SI=sine)
b = bake("Motion Platform", t, cols, LIM6, **PLAT)
check(np.max(np.abs(b["SI"] - sine)) <= 0.05, f"SI sine: |baked-plan| = {np.max(np.abs(b['SI'] - sine)):.4f}")
g, p, info = gcode_and_timeline("Motion Platform", t, b, LIM6, **PLAT)
check(info["dwells"] <= 30, f"SI sine: {info['dwells']} dwells, {info['moves']} moves")
check(abs(p.time - t[-1]) <= 1e-3, f"SI sine: duration {p.time:.4f} == {t[-1]}")
# pick a fast G1 and compare F with sqrt(2) * v_SI
lines = [l for l in g.splitlines() if l.startswith("G1 ")]
mid = len(lines) // 4
prev, line = lines[mid - 1], lines[mid]
def val(l, key):
    for part in l.split():
        if part.startswith(key):
            return float(part[len(key):])
dsi = val(line, "'a") - val(prev, "'a")
F = val(line, "F")
dur = abs(dsi) * np.sqrt(2) / (F / 60.0)
check(0.0 < dur <= 0.2, f"SI sine: F counts both 'a and 'c (sqrt2*dSI/F = {dur*1000:.1f} ms per move)")

ap = 10.0 + 5.0 * np.sin(2 * np.pi * t / 4.0)
cols = platform_cols(t, AP=ap)
b = bake("Motion Platform", t, cols, LIM6, **PLAT)
g, p, _ = gcode_and_timeline("Motion Platform", t, b, LIM6, **PLAT)
check(abs(p.time - t[-1]) <= 1e-3, f"AP sine (A-D only, rotary feed): duration {p.time:.4f}")

print("\n=== 4. Idempotence on noisy and interpolated data ===")
rng = np.random.default_rng(3)
for dt in (0.01, 0.001):
    t = grid(dt, 30.0)
    # realistic noise (per-sample speed stays below the 20 mm/s max speed)
    noisy = 10 + 8 * np.sin(2 * np.pi * t / 4.0) + rng.normal(0, 0.01 if dt >= 0.01 else 0.002, len(t))
    t50 = np.arange(0, 30.0001, 0.02)
    interp = np.interp(t, t50, 10 + 8 * np.sin(2 * np.pi * t50 / 5.0) ** 6)
    drift = np.interp(t, t50, 0.02 * t50 + rng.normal(0, 0.005, len(t50)))
    harsh = 10 + 8 * np.sin(2 * np.pi * t / 4.0) + rng.normal(0, 0.03, len(t))  # exceeds max speed at dt=0.001
    for name, x in (("noisy", noisy), ("interp50Hz", interp), ("slow drift", drift), ("harsh noise", harsh)):
        cols = platform_cols(t, SI=x)
        b1 = bake("Motion Platform", t, cols, LIM6, **PLAT)
        b2 = bake("Motion Platform", t, b1, LIM6, **PLAT)
        b3 = bake("Motion Platform", t, b2, LIM6, **PLAT)
        d = max(np.max(np.abs(b2["SI"] - b1["SI"])), np.max(np.abs(b3["SI"] - b2["SI"])))
        check(d <= 1e-9, f"dt={dt} {name}: re-bake change {d:.2e}")
        g, p, info = gcode_and_timeline("Motion Platform", t, b1, LIM6, **PLAT)
        lag = p.time - t[-1]
        if name == "harsh noise":
            # infeasible plan: the lag must be reported as residual (negative carry)
            check(abs(lag + info["residual_ms"] / 1000.0) <= 2e-3,
                  f"dt={dt} {name}: lag {lag:.3f} s reported as residual {info['residual_ms']:.0f} ms")
        else:
            check(abs(lag) <= 1e-3, f"dt={dt} {name}: duration {p.time:.4f} == {t[-1]}")

print("\n=== 5. Pauses and markers ===")
t, si = ramp_case(0.01)
cols = platform_cols(t, SI=si)
cmd = [""] * len(t)
cmd[0] = "M226"
cmd[int(round(12.34 / 0.01))] = 'M98 P"0:macros/sensor_wait.g"'   # mid ramp
cmd[int(round(30.0 / 0.01))] = "M226"                             # mid hold
cmd[int(round(5.0 / 0.01))] = "M566 A300 ; M201 A500"              # imported header -> ignored
cols["Command"] = cmd
b = bake("Motion Platform", t, cols, LIM6, **PLAT)
g, p, _ = gcode_and_timeline("Motion Platform", t, b, LIM6, **PLAT)
gl = g.splitlines()
check(sum(1 for l in gl if l.strip() == "M226") == 2, "two M226 pauses emitted (t=0 and mid hold)")
check(sum(1 for l in gl if "sensor_wait" in l) == 1, "sensor_wait pause emitted mid ramp")
check(not any(l.startswith("M566 A300 ;") for l in gl), "imported header string not re-emitted")
pts = dict((k, tm) for k, tm in p.pause_times)
times = sorted(tm for _, tm in p.pause_times)
check(abs(times[0]) < 1e-9 and abs(times[1] - 12.34) < 0.06 and abs(times[2] - 30.0) < 0.06,
      f"pause times {['%.3f' % x for x in times]}")
first_g1 = next(i for i, l in enumerate(gl) if l.startswith("G1 "))
check(gl[first_g1 + 2].strip() == "M226", "t=0 pause follows the positioning move")
marks = [int(l.split(":")[1].strip().rstrip("s -")) for l in gl if l.startswith("; --- Execution time")]
check(marks == sorted(marks) and marks[-1] == 40 and len(marks) == 5, f"markers {marks}")

print("\n=== 6. Kinematics unchanged vs. previous generator (HEAD) ===")
try:
    src = subprocess.run(["git", "-C", ROOT, "show", "HEAD:fcn_plan/fcn_gcode.py"], capture_output=True, text=True, check=True).stdout
    old = types.ModuleType("old_gcode")
    exec(compile(src, "old_gcode", "exec"), old.__dict__)
    t = grid(0.01, 10.0)
    cols = platform_cols(t, SI=5 + 3 * np.sin(t), LAT=4 + 2 * np.cos(t), AP=10 + 2 * np.sin(0.5 * t),
                         Roll=3 * np.sin(0.7 * t), Pitch=2 * np.cos(0.3 * t), Yaw=4 * np.sin(0.2 * t))
    kw = dict(lat_dim=300.0, si_dim=500.0, off_ap=12.0, off_lat=1.0, off_si=2.0, axis_y_lo="'c")
    _, letters, P, _ = compute_gcode_axes("Motion Platform", t, cols, LIM6, **kw)
    g_old, _ = old.generate_gcode_string("Motion Platform", t, cols, LIM6, **kw)
    # old generator wrote a G1 for (almost) every sample of this fast motion: compare positions
    old_rows = []
    for l in g_old.splitlines()[7:]:
        if l.startswith("G1 "):
            old_rows.append([float(p_[len(k):]) for p_, k in zip(l.split()[2:], ["A", "B", "C", "D", "'e", "'f", "'a", "'c"])])
    old_rows = np.array(old_rows)
    # match each old row to the closest new sample
    newP = np.round(P, 6)
    err = 0.0
    for r in old_rows[:: max(1, len(old_rows) // 200)]:
        err = max(err, np.min(np.max(np.abs(newP - r), axis=1)))
    check(err <= 2e-6, f"vectorised actuators match old loop (max err {err:.1e} mm)")
except Exception as e:  # pragma: no cover
    check(False, f"could not compare with HEAD: {e}")

print("\n=== 7. Review regressions ===")
def phantom(t, x):
    z = np.zeros_like(t)
    return {"X": x, "Y": z, "Z": z}

def bake_x(t, x, min_step=0.05):
    return bake("Lung Phantom", t, phantom(t, x), LIM3, min_step=min_step)["X"]

t = grid(0.01, 5.0)
x = np.where(t <= 2.0, 2.0 + 0.02 * t, 2.0 + 0.02 * 2.0 + 0.3)        # creep, then one-sample 0.3 mm step
bx = bake_x(t, x)
check(np.max(np.abs(bx - x)) <= 0.05 + 1e-9, f"creep + 0.3 mm step: |baked-plan| {np.max(np.abs(bx - x)):.4f} <= 0.05")
x = np.where(t <= 3.0, 1.0 + 0.01 * t, 6.0)                              # creep, then 5 mm jump
bx = bake_x(t, x)
check(np.max(np.abs(bx - x)) <= 0.05 + 1e-9, f"creep + 5 mm jump: |baked-plan| {np.max(np.abs(bx - x)):.4f} <= 0.05")
rng2 = np.random.default_rng(7)
x = 3.0 + rng2.uniform(-0.003, 0.003, len(t))
x[t >= 3.0] += np.clip((t[t >= 3.0] - 3.0) / 0.03, 0, 1) * 2.0          # noisy hold, then 2 mm shift over 3 samples
bx = bake_x(t, x)
check(np.max(np.abs(bx - x)) <= 0.05 + 1e-9, f"noisy hold + 2 mm shift: |baked-plan| {np.max(np.abs(bx - x)):.4f} <= 0.05")

for amp, per in ((0.2, 20.0), (0.03, 4.0)):                             # slow / tiny sines below Min. speed
    t = grid(0.01, 20.0)
    x = 5.0 + amp * np.sin(2 * np.pi * t / per)
    b = bake("Lung Phantom", t, phantom(t, x), LIM3)
    g, p, info = gcode_and_timeline("Lung Phantom", t, b, LIM3)
    check(info["dwells"] <= 25 and abs(p.time - t[-1]) <= 1e-3,
          f"slow sine A={amp} T={per}: {info['dwells']} dwells / {info['moves']} moves, duration {p.time:.3f}")

worst = 0.0
for dt, amp, per, ph in ((0.001, 2.0, 4.0, 0.1234), (0.002, 10.0, 4.0, 0.61), (0.01, 5.0, 3.0, 0.1234)):
    t = grid(dt, 8.0)
    x = 15.0 + amp * np.sin(2 * np.pi * t / per + ph)
    worst = max(worst, float(np.max(np.abs(bake_x(t, x) - x))))
check(worst <= 0.05 + 1e-9, f"turning points: |baked-plan| {worst:.4f} <= 0.05 on clean sines")

t = np.cumsum(np.r_[0.0, np.random.default_rng(11).uniform(0.008, 0.012, 2999)])  # non-uniform grid
x = 10 + 8 * np.sin(2 * np.pi * t / 4.0) + np.random.default_rng(12).normal(0, 0.01, len(t))
b1 = bake_x(t, x)
b2 = bake_x(t, b1)
check(np.max(np.abs(b2 - b1)) <= 1e-9, f"non-uniform grid: re-bake change {np.max(np.abs(b2 - b1)):.2e}")

p = parse_gcode_timeline(["G90", "M203 X600 Y600 Z600", "G1X0Y0Z0F600", "G1X10", "G4P500", "M226", "G1 X-5 F600"])
check(abs(p.time - (1.0 + 0.5 + 1.5)) < 1e-9 and p.rows[-1]["X"] == -5.0,
      f"compact G-code (G1X10, G4P500) and negative values parsed: {p.time:.3f} s")
p = parse_gcode_timeline(["M203 S1 X5 I0.2", "G1 X0 F600", "G1 X10 F600"])
check(abs(p.vmax["X"] - 5.0) < 1e-12 and abs(p.min_speed - 0.2) < 1e-12 and abs(p.time - 2.0) < 1e-9,
      f"M203 S1 units applied to I and axis caps (vmax {p.vmax['X']}, min {p.min_speed}, t {p.time:.3f})")

print("\n" + ("ALL PASSED" if not FAILS else f"{len(FAILS)} FAILED"))
sys.exit(1 if FAILS else 0)
