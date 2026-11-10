"""
Path tolerance of the G-code writer: consecutive planned samples are merged into one G1 while the straight line from
the first to the last sample stays within the tolerance of EVERY planned sample in between, at that sample's time
(position over time, per axis, in the axis' units: mm for the actuators / phantom axes).  Lines shorter than
MIN_LINE_S are merged further as long as the deviation stays within NOISE_TOL: this averages out sample-to-sample
noise of recorded curves, while sharp corners of fast motion (deviation above NOISE_TOL) are kept.

Why (measured on KINETIQ, 2026-11-10, scratch/timing_files.py / drift_analysis.py / planner_model.py): the controller
stops at every direction change (no jerk allowance on these moves, even with M566 P1), each stop costing about
speed / acceleration.  A recorded breathing curve (25 Hz, ~0.06 mm noise, 15 % of the samples reverse) therefore ran
1.4-2 % slower than planned on both controllers.  A tolerance alone (0.05-0.1 mm) keeps the zig-zags larger than the
tolerance (still +1.2 / +0.9 %); lines of at least ~100-150 ms ran within 0.2-0.3 % (patient VXP model: 0.10 s -> 0.75 %, 0.15 s -> 0.29 %).  Smooth plans and steps are not
affected (cos^6 and slow / fast ramps on time, ramp ends exact).

What stays exact:
* every merged line ends on a planned sample and takes exactly the planned time (the writer's feed rule);
* holds stay holds (a sample that does not move ends a merge), commands / pauses end a merge;
* a merged line is never slower than the controller's minimum speed (the writer's existing check), so the stepped
  motion ("hold, then quick step") of slow parts is kept as it is;
* a merge is limited to MAX_MERGE_S seconds.
With a tolerance <= fcn_gcode.PATH_TOL the writer uses its original rule (velocity spread), unchanged.
"""
import numpy as np

DEFAULT_PATH_TOL = 0.05      # mm: every planned point within this (lines of at least MIN_LINE_S: within NOISE_TOL)
MAX_PATH_TOL = 0.5           # mm (settings range)
MAX_MERGE_S = 5.0            # s, longest single merged G1
MIN_LINE_S = 0.15            # s: shorter lines are merged further (noise), within NOISE_TOL
NOISE_TOL = 0.25             # mm: largest deviation accepted for that (sharp corners of fast motion stay)


def chord_deviation(t, P, i, j):
    """Largest distance (any axis) of the samples i < k < j from the straight line (t[i], P[i]) -> (t[j], P[j])."""
    if j - i < 2:
        return 0.0
    ti, tj = float(t[i]), float(t[j])
    if tj <= ti:
        return float("inf")
    k = slice(i + 1, j)
    u = (np.asarray(t[k], dtype=float) - ti) / (tj - ti)
    a = np.asarray(P[i], dtype=float)
    b = np.asarray(P[j], dtype=float)
    line = a[None, :] + u[:, None] * (b - a)[None, :]
    return float(np.max(np.abs(np.asarray(P[k], dtype=float) - line)))


def within_tolerance(t, P, i, j, tol):
    """May samples i..j become one G1?  Within tol, or (shorter than MIN_LINE_S) within NOISE_TOL; never longer than
    MAX_MERGE_S."""
    span = float(t[j]) - float(t[i])
    if span > MAX_MERGE_S:
        return False
    dev = chord_deviation(t, P, i, j)
    if dev <= tol + 1e-12:
        return True
    return span <= MIN_LINE_S + 1e-9 and dev <= max(tol, NOISE_TOL) + 1e-12
