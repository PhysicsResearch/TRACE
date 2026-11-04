"""
G-code generation for planned motion (Lung Phantom, Motion Platform, Other).

Overview
--------
* ``compute_gcode_axes``  – plan columns -> positions of the axes written to the G-code.
* ``bake_stepped_plan``   – quantises the plan so that slow motion is executed as
  "hold, then a quick step" once the accumulated displacement reaches ``min_step``.
  The planning tab stores (bakes) this result, so the plot shows what will run.
* ``generate_gcode_string`` – faithful translator of the (baked) samples into G1/G4.
* ``GcodeTimelineParser`` – reads a G-code file back into a timeline with the same
  time model (used by the G-code importers and the Status-tab reference).

Time model (RepRapFirmware)
---------------------------
* Moves slower than the minimum movement speed (M203 I, default 30 mm/min = 0.5 mm/s)
  are raised to it, so slow motion must be expressed as holds (G4) + quick steps.
* Uppercase A-D are rotary axes by default; every other axis is linear. When any linear
  axis moves, F is applied to the Euclidean distance of the linear axes only; otherwise
  to the rotary axes.
* A G1 is also limited by the per-axis maximum speed (M203).
"""
import math
import re

import numpy as np

DUET_MIN_SPEED = 0.5       # mm/s  RRF default minimum movement speed (M203 I30) when a file sets none
DEFAULT_MIN_SPEED = 0.1    # mm/s  minimum speed written to the G-code header (M203 I6); slower motion is stepped
STEP_SPEED = 5.0           # mm/s  axis speed of a quick step (<= lowest jerk option, 300 mm/min)
DEFAULT_MIN_STEP = 0.05    # mm
EPS = 1e-9                 # positional tolerance for "not moving"
PATH_TOL = 1e-4            # mm  max deviation when merging samples into one G1 (~0.2 microstep)
SPEED_TOL = 1.0 - 1e-6     # motion at exactly Min. speed counts as continuous (float tolerance)
MAX_BAKE_PASSES = 6        # bake iterates to a fixed point (usually 1-2 passes)
POS_DECIMALS = 6           # decimals written to the G-code
ROTARY_AXES = ("A", "B", "C", "D")
PLATFORM_PLAN_COLS = ("LAT", "SI", "AP", "Roll", "Pitch", "Yaw")
PHANTOM_PLAN_COLS = ("X", "Y", "Z")


# ----------------------------------------------------------------------------
# Commands
# ----------------------------------------------------------------------------
def is_plan_command(cmd):
    """True for planning pause commands (wait radiation / wait user)."""
    if not isinstance(cmd, str):
        return False
    c = cmd.strip()
    if not c:
        return False
    return "sensor_wait" in c.lower() or "M226" in c.upper()


def format_command_lines(cmd):
    """Formats planning pause commands with clear descriptive comment lines."""
    cmd_str = str(cmd).strip()
    cmd_lower = cmd_str.lower()
    lines = []

    if "sensor_wait" in cmd_lower or "radiation" in cmd_lower:
        lines.append("; waiting for radiation")
    elif "m226" in cmd_lower or "release" in cmd_lower or "user" in cmd_lower or "m400" in cmd_lower or "pause" in cmd_lower:
        lines.append("; waiting for user release")
    elif not cmd_str.startswith(";"):
        lines.append("; waiting for user release")

    lines.append(cmd_str)
    return lines


# ----------------------------------------------------------------------------
# RRF time model
# ----------------------------------------------------------------------------
def rotary_mask(letters):
    """Per-axis flags: True for rotary axes (uppercase A-D without quote)."""
    return [str(l) in ROTARY_AXES for l in letters]


def feed_distance(rot_mask, delta):
    """Distance F applies to: linear axes if any moves, otherwise rotary axes."""
    lin_sq = 0.0
    rot_sq = 0.0
    lin_moves = False
    for is_rot, d in zip(rot_mask, delta):
        if is_rot:
            rot_sq += d * d
        else:
            lin_sq += d * d
            if abs(d) > EPS:
                lin_moves = True
    return math.sqrt(lin_sq) if lin_moves else math.sqrt(rot_sq)


def _vmax_for(vmax, i):
    if isinstance(vmax, (list, tuple)):
        return vmax[i]
    return vmax


def move_time(rot_mask, delta, feed_mm_min, vmax=None, min_speed=DUET_MIN_SPEED):
    """Duration RRF needs for one G1 (min-speed clamp + per-axis max speed)."""
    fd = feed_distance(rot_mask, delta)
    speed = max((feed_mm_min or 0.0) / 60.0, min_speed)
    t = fd / speed if speed > 0 else 0.0
    if vmax:
        for i, d in enumerate(delta):
            vm = _vmax_for(vmax, i)
            if vm and vm > 0:
                t = max(t, abs(d) / vm)
    return t


def step_feed(rot_mask, delta, min_speed=DUET_MIN_SPEED):
    """Feed (mm/min) for a quick step: the fastest-moving axis travels at STEP_SPEED."""
    fd = feed_distance(rot_mask, delta)
    dmax = max(abs(d) for d in delta) if len(delta) else 0.0
    if dmax <= 0.0 or fd <= 0.0:
        return max(STEP_SPEED, min_speed) * 60.0
    return max(STEP_SPEED * fd / dmax, min_speed) * 60.0


def step_time(rot_mask, delta, vmax=None, min_speed=DUET_MIN_SPEED):
    return move_time(rot_mask, delta, step_feed(rot_mask, delta, min_speed), vmax, min_speed)


# ----------------------------------------------------------------------------
# Plan columns -> G-code axes
# ----------------------------------------------------------------------------
def _uniform_grid(t_orig):
    t_orig = np.asarray(t_orig, dtype=float)
    if len(t_orig) > 1:
        dt = t_orig[1] - t_orig[0]
        if dt <= 0.0:
            dt = 0.001
    else:
        dt = 0.001
    t_max = float(t_orig.max()) if len(t_orig) else 0.0
    t_new = np.arange(0.0, t_max + dt / 2.0, dt)
    if len(t_new) == len(t_orig) and np.allclose(t_new, t_orig, atol=1e-9, rtol=0.0):
        return t_orig.copy(), False
    return t_new, True


def platform_actuators(LAT, SI, AP, Roll, Pitch, Yaw, max_limits, lat_dim, si_dim, off_ap, off_lat, off_si):
    """
    Motion Platform kinematics used for the G-code (vectorised; same formulas as before).
    Returns (A, B, C, D, LAT_eff, SI_eff).
    """
    lim_lat, lim_si, lim_ap = max_limits[0], max_limits[1], max_limits[2]
    if lat_dim <= 0.0:
        lat_dim = 100.0
    if si_dim <= 0.0:
        si_dim = 100.0

    r = np.radians(Roll)
    p = -np.radians(Pitch)  # Negated to match step buttons convention
    y = np.radians(Yaw)
    cos_r, sin_r = np.cos(r), np.sin(r)
    cos_p, sin_p = np.cos(p), np.sin(p)
    cos_y, sin_y = np.cos(y), np.sin(y)
    zc = off_ap

    support_points = (
        (-lat_dim / 2.0, -si_dim / 2.0),   # A
        (lat_dim / 2.0, -si_dim / 2.0),    # B
        (lat_dim / 2.0, si_dim / 2.0),     # C
        (-lat_dim / 2.0, si_dim / 2.0),    # D
    )
    acts = []
    for px, py in support_points:
        x1, y1, z1 = px, py, -zc
        x2 = cos_y * x1 - sin_y * y1
        y2 = sin_y * x1 + cos_y * y1
        z2 = z1
        z3 = -x2 * sin_r + z2 * cos_r
        y3 = y2
        z4 = y3 * sin_p + z3 * cos_p
        acts.append(np.clip(z4 + zc + AP, 0.0, lim_ap))

    roll_rad = np.radians(Roll)
    pitch_rad = np.radians(Pitch)
    LAT_eff = np.clip(off_lat + LAT + off_ap * np.sin(roll_rad), 0.0, lim_lat)
    SI_eff = np.clip(off_si + SI + off_ap * np.sin(pitch_rad), 0.0, lim_si)
    return acts[0], acts[1], acts[2], acts[3], LAT_eff, SI_eff


def compute_gcode_axes(device, t_orig, columns_data, max_limits, lat_dim=100.0, si_dim=100.0,
                       off_ap=0.0, off_lat=0.0, off_si=0.0, axis_y_lo="'c", resample=True):
    """
    Returns (t, letters, P, exceeds_limits) where P[n x k] holds the (unrounded) positions of
    the G-code axes ``letters``. With ``resample`` the data is put on a uniform grid starting
    at 0 (identity when it already is one); without it the original samples are used.
    """
    t_orig = np.asarray(t_orig, dtype=float)
    if resample:
        t_new, needs_interp = _uniform_grid(t_orig)
    else:
        t_new, needs_interp = t_orig.copy(), False

    def col(name):
        arr = np.asarray(columns_data[name], dtype=float)
        return np.interp(t_new, t_orig, arr) if needs_interp else arr.copy()

    exceeds_limits = False

    if device == "Lung Phantom":
        X = np.clip(col("X"), 0.0, None)
        Y = np.clip(col("Y"), 0.0, None)
        Z = np.clip(col("Z"), 0.0, None)
        lim_x, lim_y, lim_z = max_limits
        if np.any(np.abs(X) > lim_x) or np.any(np.abs(Y) > lim_y) or np.any(np.abs(Z) > lim_z):
            exceeds_limits = True
        letters = ["X", "Y", "Z"]
        P = np.column_stack([X, Y, Z])

    elif device == "Motion Platform":
        lim_lat, lim_si, lim_ap, lim_roll, lim_pitch, lim_yaw = max_limits
        LAT = np.clip(col("LAT"), 0.0, lim_lat)
        SI = np.clip(col("SI"), 0.0, lim_si)
        AP = np.clip(col("AP"), 0.0, lim_ap)
        Roll = col("Roll")
        Pitch = col("Pitch")
        Yaw = col("Yaw")
        if (np.any(np.abs(LAT) > lim_lat) or np.any(np.abs(SI) > lim_si) or
                np.any(np.abs(AP) > lim_ap) or np.any(np.abs(Roll) > lim_roll) or
                np.any(np.abs(Pitch) > lim_pitch) or np.any(np.abs(Yaw) > lim_yaw)):
            exceeds_limits = True
        A, B, C, D, LAT_eff, SI_eff = platform_actuators(
            LAT, SI, AP, Roll, Pitch, Yaw, max_limits, lat_dim, si_dim, off_ap, off_lat, off_si)
        letters = ["A", "B", "C", "D", "'e", "'f", "'a", axis_y_lo]
        P = np.column_stack([A, B, C, D, LAT_eff, LAT_eff, SI_eff, SI_eff])

    else:  # Other
        letters = sorted(c for c in columns_data.keys() if c != "Command")
        cols = [col(c) for c in letters]
        if max_limits and len(max_limits) > 0:
            lim = max_limits[0]
            for arr in cols:
                if np.any(np.abs(arr) > lim):
                    exceeds_limits = True
        P = np.column_stack(cols) if cols else np.zeros((len(t_new), 0))

    return t_new, letters, P, exceeds_limits


def plan_columns_for(device, columns_data):
    if device == "Lung Phantom":
        return list(PHANTOM_PLAN_COLS)
    if device == "Motion Platform":
        return list(PLATFORM_PLAN_COLS)
    return sorted(c for c in columns_data.keys() if c != "Command")


# ----------------------------------------------------------------------------
# Step quantisation (bake)
# ----------------------------------------------------------------------------
def _linear_run_ends(t, P, V, rot, min_step, still, min_speed):
    """Ends of maximal runs (>= 2 intervals) that are straight in the plan columns (equal slope,
    also on non-uniform grids) and at least as fast as ``min_speed``. Forcing knots there keeps
    already-baked chords (and their corners) unchanged on re-bake."""
    n = len(t)
    forced = set()
    if n < 3 or V.shape[1] == 0:
        return forced
    dt = np.diff(t)
    vel = np.diff(V, axis=0) / dt[:, None]
    same = np.zeros(n - 1, dtype=bool)  # same[j]: interval j continues interval j-1
    tol = 1e-9 + 1e-9 * np.maximum(np.abs(vel[1:]), np.abs(vel[:-1]))
    same[1:] = np.all(np.abs(vel[1:] - vel[:-1]) <= tol, axis=1)
    still_arr = np.asarray(still, dtype=bool)
    same[1:] &= ~still_arr[1:] & ~still_arr[:-1]
    j = 1
    while j < n - 1:
        if same[j]:
            s = j - 1
            e = j
            while e + 1 < n - 1 and same[e + 1]:
                e += 1
            a, b = s, e + 1
            T = t[b] - t[a]
            dP = (P[b] - P[a]).tolist()
            if T > 0 and feed_distance(rot, dP) / T >= min_speed * SPEED_TOL:
                forced.add(a)
                forced.add(b)
            j = e + 1
        else:
            j += 1
    return forced


def find_step_knots(t, P, V, rot, min_step, force_idx=(), min_speed=DEFAULT_MIN_SPEED):
    """Knot indices: start, end, pauses, stationary-run boundaries, straight-run ends and the
    first sample where the accumulated displacement reaches ``min_step``."""
    n = len(t)
    if n <= 2:
        return list(range(n))
    still = (np.max(np.abs(np.diff(P, axis=0)), axis=1) <= EPS).tolist() if P.shape[1] else [True] * (n - 1)
    forced = set(int(i) for i in force_idx if 0 < int(i) < n - 1)
    forced |= _linear_run_ends(t, P, V, rot, min_step, still, min_speed)
    rows = P.tolist()
    K = [0]
    anchor = rows[0]
    thr = min_step - 1e-12
    for i in range(1, n):
        row = rows[i]
        if i == n - 1 or i in forced:
            K.append(i)
            anchor = row
            continue
        d = max(abs(x - y) for x, y in zip(row, anchor)) if row else 0.0
        if d <= EPS:
            # end of a real stationary run: motion resumes after this sample
            if still[i - 1] and not still[i] and i > K[-1]:
                K.append(i)
                anchor = row
            continue
        if d >= thr or still[i]:
            K.append(i)
            anchor = row
    return K


def _max_chord_deviation(t, P, a, b):
    """(max deviation, index) of samples a+1..b-1 from the straight space-time line a->b."""
    f = ((t[a + 1:b] - t[a]) / (t[b] - t[a]))[:, None]
    dev = np.max(np.abs(P[a + 1:b] - (P[a] + f * (P[b] - P[a]))), axis=1)
    k = int(np.argmax(dev))
    return float(dev[k]), a + 1 + k


def plan_segments(t, P, K, rot, vmax=None, min_speed=DEFAULT_MIN_SPEED, min_step=None):
    """
    Classify knot intervals as ('hold'|'flat'|'chord'|'stair', a, b, ramp_start):
    * hold  - no displacement at all (plan columns kept as they are),
    * flat  - same start/end position but sub-threshold motion inside (flattened),
    * chord - at least ``min_speed``: straight line; split where the plan deviates > min_step,
    * stair - slower: hold, then a quick ramp over the last samples.
    """
    segs = []
    for a0, b0 in zip(K[:-1], K[1:]):
        work = [(a0, b0)]
        while work:
            a, b = work.pop()
            d = (P[b] - P[a]).tolist()
            dmax = max(abs(x) for x in d) if d else 0.0
            if dmax <= EPS:
                inner = P[a + 1:b]
                moves = inner.size > 0 and float(np.max(np.abs(inner - P[a]))) > EPS
                segs.append(("flat" if moves else "hold", a, b, b))
                continue
            T = t[b] - t[a]
            if T <= 0.0 or feed_distance(rot, d) / T >= min_speed * SPEED_TOL:
                if min_step is not None and b - a > 1:
                    dev, s = _max_chord_deviation(t, P, a, b)
                    if dev > min_step + 1e-9:
                        work.append((s, b))
                        work.append((a, s))
                        continue
                segs.append(("chord", a, b, a))
                continue
            ts = step_time(rot, d, vmax, min_speed)
            j = b - 1
            while j > a and (t[b] - t[j]) < ts - 1e-9:
                j -= 1
            if j == a and b - a >= 2:
                j = a + 1  # keep a held sample so the segmentation is stable on re-bake
            segs.append(("stair", a, b, j))
    return segs


def apply_segments(t, V, segs):
    """Rebuild plan columns: holds unchanged, flats held, chords linear, stairs hold + ramp."""
    B = np.array(V, dtype=float, copy=True)
    for kind, a, b, j in segs:
        if kind == "hold":
            continue
        if kind == "flat":
            B[a:b] = V[a]
            continue
        if kind == "chord":
            if b - a > 1:
                f = ((t[a + 1:b] - t[a]) / (t[b] - t[a]))[:, None]
                B[a + 1:b] = V[a] + f * (V[b] - V[a])
            continue
        # stair
        B[a:j + 1] = V[a]
        if b - j > 1:
            f = ((t[j + 1:b] - t[j]) / (t[b] - t[j]))[:, None]
            B[j + 1:b] = V[a] + f * (V[b] - V[a])
    return B


def bake_stepped_plan(device, t, columns_data, max_limits, lat_dim=100.0, si_dim=100.0,
                      off_ap=0.0, off_lat=0.0, off_si=0.0, axis_y_lo="'c",
                      min_step=DEFAULT_MIN_STEP, max_speed=None, min_speed=DEFAULT_MIN_SPEED):
    """
    Quantises slow motion: positions change only once the accumulated displacement of the
    G-code axes reaches ``min_step``; intervals slower than the Duet minimum speed become
    "hold, then quick step", faster ones stay continuous (straight between knots).
    Returns {plan_column: baked array} or None when the data cannot be baked.
    """
    t = np.asarray(t, dtype=float)
    n = len(t)
    if n < 3 or np.any(np.diff(t) <= 0.0):
        return None
    plan_cols = [c for c in plan_columns_for(device, columns_data) if c in columns_data]
    if not plan_cols:
        return None
    force = []
    cmds = columns_data.get("Command", None)
    if cmds is not None:
        force = [i for i, c in enumerate(cmds) if is_plan_command(c)]
    step = max(float(min_step), 0.0)

    V = np.column_stack([np.asarray(columns_data[c], dtype=float) for c in plan_cols])
    work = dict(columns_data)
    # Iterate to a fixed point: a pass can straighten a corner shallower than min_step that the
    # previous pass created; the stored plan must re-bake unchanged (it is re-baked on every edit).
    for _ in range(MAX_BAKE_PASSES):
        for k, c in enumerate(plan_cols):
            work[c] = V[:, k]
        try:
            _, letters, P, _ = compute_gcode_axes(device, t, work, max_limits, lat_dim, si_dim,
                                                  off_ap, off_lat, off_si, axis_y_lo, resample=False)
        except (KeyError, ValueError):
            return None
        P = np.round(P, POS_DECIMALS)
        rot = rotary_mask(letters)
        K = find_step_knots(t, P, V, rot, step, force, min_speed)
        segs = plan_segments(t, P, K, rot, max_speed, min_speed, step)
        B = apply_segments(t, V, segs)
        converged = float(np.max(np.abs(B - V))) <= 1e-12 if B.size else True
        V = B
        if converged:
            break
    return {c: V[:, k] for k, c in enumerate(plan_cols)}


# ----------------------------------------------------------------------------
# G-code emitter
# ----------------------------------------------------------------------------
def _fmt_axes(letters, row):
    return " ".join(f"{l}{v:.6f}" for l, v in zip(letters, row))


def generate_gcode_string(
    device,
    t_orig,
    columns_data,
    max_limits,
    lat_dim=100.0,
    si_dim=100.0,
    off_ap=0.0,
    off_lat=0.0,
    off_si=0.0,
    axis_y_lo="'c",
    speed=None,
    acc=None,
    jerk=None,
    step_overhead_ms=0.0,
    min_speed=DEFAULT_MIN_SPEED,
    info=None
):
    """
    Translates the planned samples into G-code, faithfully:
    * unchanged samples -> G4 dwell, moving samples -> G1 at the planned speed,
    * a sample slower than ``min_speed`` -> dwell + quick step (the header sets the Duet
      minimum movement speed to ``min_speed`` with M203 I),
    * consecutive samples on a straight line (space and time) are merged into one G1.
    Slow motion is expected to be baked (``bake_stepped_plan``) beforehand.
    ``step_overhead_ms`` shortens every dwell to compensate the restart delay after a G4.
    If ``info`` is a dict it receives statistics (moves, dwells, duration_s, residual_ms).
    Returns (gcode_string, exceeds_limits).
    """
    t_orig = np.asarray(t_orig, dtype=float)
    t_max = float(t_orig.max()) if len(t_orig) else 0.0
    total_time_seconds = int(round(float(t_orig.max() - t_orig.min()))) if len(t_orig) else 0

    t, letters, P_raw, exceeds_limits = compute_gcode_axes(
        device, t_orig, columns_data, max_limits, lat_dim, si_dim, off_ap, off_lat, off_si, axis_y_lo,
        resample=True)
    P = np.round(P_raw, POS_DECIMALS)
    rot = rotary_mask(letters)
    n = len(t)

    # Header (unchanged layout; M566/M201/M203 within the first lines)
    if device == "Lung Phantom":
        jerk_val = int(round(float(jerk))) if jerk is not None else 300
        acc_val = int(round(float(acc))) if acc is not None else 1000
        speed_val = int(round(float(speed) * 60.0)) if speed is not None else 3000
        header = [
            f"; TIME: {total_time_seconds}",
            "G90",
            f"M566 X{jerk_val} Y{jerk_val} Z{jerk_val}",
            f"M201 X{acc_val} Y{acc_val} Z{acc_val}",
            f"M203 X{speed_val} Y{speed_val} Z{speed_val}",
        ]
    elif device == "Motion Platform":
        jerk_val = int(round(float(jerk))) if jerk is not None else 300
        acc_val = int(round(float(acc))) if acc is not None else 500
        speed_val = int(round(float(speed) * 60.0)) if speed is not None else 1200
        header = [
            f"; TIME: {total_time_seconds}",
            "G90",
            f"M566 A{jerk_val} B{jerk_val} C{jerk_val} D{jerk_val} 'c{jerk_val} 'a{jerk_val}  'f{jerk_val} 'e{jerk_val}",
            f"M201 A{acc_val} B{acc_val} C{acc_val} D{acc_val} 'c{acc_val} 'a{acc_val}  'f{acc_val} 'e{acc_val}",
            f"M203 A{speed_val} B{speed_val} C{speed_val} D{speed_val} 'c{speed_val} 'a{speed_val}  'f{speed_val} 'e{speed_val}",
        ]
    else:
        jerk_val = int(round(float(jerk))) if jerk is not None else 300
        acc_val = int(round(float(acc))) if acc is not None else 500
        speed_val = int(round(float(speed) * 60.0)) if speed is not None else 1200
        header = [
            f"; TIME: {total_time_seconds}",
            "G90",
            "M566 " + " ".join(f"{c}{jerk_val}" for c in letters),
            "M201 " + " ".join(f"{c}{acc_val}" for c in letters),
            "M203 " + " ".join(f"{c}{speed_val}" for c in letters),
        ]
    vmax = speed_val / 60.0
    min_speed = max(float(min_speed or DEFAULT_MIN_SPEED), 0.01)  # RRF floor 0.6 mm/min
    header.append(f"M203 I{min_speed * 60.0:g}")  # Duet minimum movement speed (mm/min)
    ov = max(0.0, float(step_overhead_ms or 0.0)) / 1000.0
    header.append(f"; STEP_OVERHEAD_MS: {ov * 1000.0:g}")
    header.append("; --- Execution time: 0s ---")
    lines = list(header)

    # Pause commands -> sample index (several commands on one sample are kept in order)
    cmd_at = {}
    if "Command" in columns_data:
        for idx, cmd in enumerate(columns_data["Command"]):
            if is_plan_command(cmd):
                new_idx = int(np.argmin(np.abs(t - t_orig[idx])))
                cmd_at.setdefault(new_idx, []).append(str(cmd).strip())

    stats = {"moves": 0, "dwells": 0}
    state = {"carry": 0.0, "pending": 0.0, "pending_start": 0.0, "next_mark": 10.0}
    rows = P.tolist()
    raw_rows = P_raw.tolist()
    cur = rows[0] if n else []

    def mark(ts):
        while ts >= state["next_mark"] - 1e-9 and state["next_mark"] <= t_max + 1e-9:
            lines.append(f"; --- Execution time: {int(round(state['next_mark']))}s ---")
            state["next_mark"] += 10.0

    def add_dwell(start, dur):
        if dur <= 0.0:
            return
        if state["pending"] <= 0.0:
            state["pending_start"] = start
        state["pending"] += dur

    def flush_dwell():
        if state["pending"] <= 0.0:
            return
        want = state["pending"] + state["carry"]
        if want - ov >= 0.001 - 1e-12:
            mark(state["pending_start"])
            ms = int(round((want - ov) * 1000.0))
            lines.append(f"G4 P{ms}")
            stats["dwells"] += 1
            state["carry"] = (want - ov) - ms / 1000.0
        else:
            state["carry"] = want
        state["pending"] = 0.0

    def emit_move(start, target, feed, planned):
        nonlocal cur
        flush_dwell()
        mark(start)
        delta = [a - b for a, b in zip(target, cur)]
        lines.append(f"G1 F{feed:.6f} {_fmt_axes(letters, target)}")
        stats["moves"] += 1
        state["carry"] += planned - move_time(rot, delta, feed, vmax, min_speed)
        cur = target

    def emit_commands(i):
        flush_dwell()
        mark(t[i])
        for c in cmd_at.get(i, []):
            lines.extend(format_command_lines(c))

    if n:
        lines.append(f"G1 F1000.000000 {_fmt_axes(letters, cur)}")
        if 0 in cmd_at:
            emit_commands(0)

    def max_abs_diff(r1, r2):
        return max((abs(x - y) for x, y in zip(r1, r2)), default=0.0)

    i = 0
    while i < n - 1:
        if i > 0 and i in cmd_at:
            emit_commands(i)

        if max_abs_diff(rows[i + 1], rows[i]) <= EPS:
            j = i + 1
            while j < n - 1 and j not in cmd_at and max_abs_diff(rows[j + 1], rows[j]) <= EPS:
                j += 1
            add_dwell(t[i], t[j] - t[i])
            i = j
            continue

        T1 = t[i + 1] - t[i]
        d1 = [a - b for a, b in zip(rows[i + 1], rows[i])]
        v1 = feed_distance(rot, d1) / T1 if T1 > 0 else float("inf")
        if v1 >= min_speed * SPEED_TOL:
            # Extend while the samples stay on a straight space-time line (velocity spread bound)
            vel0 = [(a - b) / T1 for a, b in zip(raw_rows[i + 1], raw_rows[i])]
            vlo = list(vel0)
            vhi = list(vel0)
            j = i + 1
            while j < n - 1 and j not in cmd_at:
                Tn = t[j + 1] - t[j]
                if Tn <= 0:
                    break
                dn = [a - b for a, b in zip(rows[j + 1], rows[j])]
                if max((abs(x) for x in dn), default=0.0) <= EPS:
                    break
                vel = [(a - b) / Tn for a, b in zip(raw_rows[j + 1], raw_rows[j])]
                nlo = [min(x, y) for x, y in zip(vlo, vel)]
                nhi = [max(x, y) for x, y in zip(vhi, vel)]
                span = t[j + 1] - t[i]
                if max((h - l for h, l in zip(nhi, nlo)), default=0.0) * span > PATH_TOL:
                    break
                dtot = [a - b for a, b in zip(rows[j + 1], rows[i])]
                if feed_distance(rot, dtot) / span < min_speed * SPEED_TOL:
                    break
                vlo, vhi = nlo, nhi
                j += 1
            T = t[j] - t[i]
            dtot = [a - b for a, b in zip(rows[j], cur)]
            feed = max(feed_distance(rot, dtot) / T * 60.0, min_speed * 60.0)
            emit_move(t[i], rows[j], feed, T)
            i = j
        else:
            # Slower than the Duet minimum speed: hold, then a quick step
            ts = step_time(rot, d1, vmax, min_speed)
            add_dwell(t[i], max(0.0, T1 - ts))
            emit_move(t[i], rows[i + 1], step_feed(rot, d1, min_speed), min(ts, T1))
            i += 1

    if n:
        flush_dwell()
        if n - 1 > 0 and (n - 1) in cmd_at:
            emit_commands(n - 1)
        mark(t_max)

    if isinstance(info, dict):
        info.update(stats)
        info["duration_s"] = float(t[-1] - t[0]) if n else 0.0
        info["residual_ms"] = state["carry"] * 1000.0 + state["pending"] * 1000.0

    return "\n".join(lines), exceeds_limits


# ----------------------------------------------------------------------------
# G-code -> timeline (same time model)
# ----------------------------------------------------------------------------
_AXIS_PATTERN = re.compile(r"('?[a-zA-Z])([-+]?(?:\d+\.\d*|\.\d+|\d+))")
_CMD_PATTERN = re.compile(r"\s*([GgMm])0*(\d+)(?![\d.])")
_OVERHEAD_PATTERN = re.compile(r"STEP_OVERHEAD_MS:\s*([-+]?(?:\d+\.\d*|\.\d+|\d+))", re.IGNORECASE)


class GcodeTimelineParser:
    """
    Incremental G-code reader producing timeline rows ({axis: value, 'time', 'timestamp',
    'Command'}) using the RRF time model: per-move duration from feed (min-speed clamp, linear
    vs rotary axes, M203 caps), G4 dwells plus the file's ``; STEP_OVERHEAD_MS:`` value.
    Pause commands (sensor_wait / M226) are added as rows at the time they occur.
    """

    def __init__(self, bare_lowercase_as_quoted=False):
        self.bare_lowercase_as_quoted = bare_lowercase_as_quoted
        self.time = 0.0
        self.feed = 1000.0
        self.min_speed = DUET_MIN_SPEED
        self.vmax = {}
        self.overhead_s = 0.0
        self.last = {}
        self.rows = []
        self.pause_times = []
        self._pending_cmds = []

    def _key(self, axis):
        if axis.startswith("'"):
            return axis
        if self.bare_lowercase_as_quoted and len(axis) == 1 and axis in "efacb":
            return "'" + axis
        return axis.upper()

    def _row(self, cmd=""):
        row = dict(self.last)
        row["time"] = self.time
        row["timestamp"] = self.time * 1000.0
        row["Command"] = cmd
        self.rows.append(row)

    def feed_line(self, line):
        if ";" in line:
            code, comment = line.split(";", 1)
            m = _OVERHEAD_PATTERN.search(comment)
            if m and not code.strip():
                try:
                    self.overhead_s = max(0.0, float(m.group(1)) / 1000.0)
                except ValueError:
                    pass
        else:
            code = line
        code = code.strip()
        if not code:
            return
        m = _CMD_PATTERN.match(code)  # also accepts compact words: G1X10, G4P500, M203I6
        cmd = (m.group(1).upper(), int(m.group(2))) if m else (None, None)
        rest = code[m.end():] if m else code
        if cmd in (("G", 0), ("G", 1)):
            self._move(rest)
        elif cmd == ("G", 4):
            self._dwell(rest)
        elif cmd == ("M", 203):
            self._m203(rest)
        else:
            upper = code.upper()
            if "M226" in upper or cmd in (("M", 0), ("M", 1)):
                self.pause_times.append(("M226", self.time))
            elif "sensor_wait" in code.lower():
                self.pause_times.append(("sensor_wait", self.time))
            if is_plan_command(code):
                if self.last:
                    self._row(code)
                else:
                    self._pending_cmds.append(code)

    def _move(self, rest):
        vals = {}
        for axis, val in _AXIS_PATTERN.findall(rest):
            key = self._key(axis)
            if key == "F":
                self.feed = float(val)
            elif key in ("G",):
                continue
            else:
                vals[key] = float(val)
        keys = [k for k in vals if k in self.last]
        if keys:
            delta = [vals[k] - self.last[k] for k in keys]
            rot = [k in ROTARY_AXES for k in keys]
            vmax = [self.vmax.get(k, 0.0) for k in keys]
            if max(abs(d) for d in delta) > 0.0:
                self.time += move_time(rot, delta, self.feed, vmax, self.min_speed)
        self.last.update(vals)
        cmd = " ; ".join(self._pending_cmds) if self._pending_cmds else ""
        self._pending_cmds = []
        self._row(cmd)

    def _dwell(self, rest):
        m_p = re.search(r"[pP]\s*([-+]?(?:\d+\.\d*|\.\d+|\d+))", rest)
        m_s = re.search(r"[sS]\s*([-+]?(?:\d+\.\d*|\.\d+|\d+))", rest)
        sec = 0.0
        if m_p:
            sec = float(m_p.group(1)) / 1000.0
        elif m_s:
            sec = float(m_s.group(1))
        if sec <= 0.0:
            return
        self.time += sec + self.overhead_s
        if self.last:
            self._row()

    def _m203(self, rest):
        pairs = [(self._key(a), float(v)) for a, v in _AXIS_PATTERN.findall(rest)]
        # S1: all values of this M203 are in mm/s (RRF applies the flag to I and every axis)
        scale = 1.0 if any(k == "S" and v == 1.0 for k, v in pairs) else 1.0 / 60.0
        for key, v in pairs:
            if key == "I":
                self.min_speed = max(v * scale, 0.0)
            elif key == "S":
                continue
            else:
                self.vmax[key] = v * scale


def parse_gcode_timeline(lines, bare_lowercase_as_quoted=False):
    parser = GcodeTimelineParser(bare_lowercase_as_quoted=bare_lowercase_as_quoted)
    for line in lines:
        parser.feed_line(line)
    return parser
