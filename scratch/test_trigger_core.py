"""
Beam trigger core (fcn_plan/fcn_trigger.py) and its G-code hooks (fcn_plan/fcn_gcode.py), no Qt.
Covers: M42 parsing, multi-command cells, state <-> commands normalisation, manual switches and overlaps, the clear
helpers not touching other kinds, periodic patterns and edge cases, the gated condition (one axis / all axes / same
margins / flip / range / every combine mode), the G-code (start / end 'M42 P5 S0', M42 between the right moves at the
right time, the round trip), manual windows entered in any order (event semantics: an On before a later window keeps
that window's S1, the next Off ends only the new part; an On inside a run places a window start there, so every On may
come before the Offs; an Off at a later window's start inside the run joins touching windows as in time order: all 2-
and 3-window press orders, random interleavings, touching windows, G-code and round trip) and byte-identical G-code for
plans without a trigger (against git HEAD's fcn_gcode.py).
Run:  C:\\Users\\gabri\\anaconda3\\envs\\TRACE\\python.exe scratch\\test_trigger_core.py
"""
import importlib.util
import itertools
import os
import random
import subprocess
import sys
import tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)
import numpy as np

from fcn_plan import fcn_trigger as T
from fcn_plan import fcn_gcode as G

FAILS = []
N = [0]


def check(cond, msg):
    N[0] += 1
    print(("PASS  " if cond else "FAIL  ") + msg)
    if not cond:
        FAILS.append(msg)


def raises(fn, text=None):
    try:
        fn()
    except ValueError as e:
        return text is None or text.lower() in str(e).lower()
    return False


RAD, USR, ON, OFF = T.WAIT_RAD_CMD, T.WAIT_USER_CMD, T.TRIGGER_ON_CMD, T.TRIGGER_OFF_CMD
t = np.round(np.arange(0.0, 20.0 + 1e-9, 0.01), 6)          # 2001 rows, 10 ms
n = len(t)
empty = [""] * n

print("=== M42 commands and cells ===")
check(T.TRIGGER_PORT == 5 and ON == "M42 P5 S1" and OFF == "M42 P5 S0", "TRIGGER_PORT 5: 'M42 P5 S1' / 'M42 P5 S0'")
check(T.parse_output_command("M42 P5 S1") == (5, True) and T.parse_output_command("m42 s0 p5") == (5, False)
      and T.parse_output_command("M42P5S1") == (5, True) and T.parse_output_command("M042 P5 S1.0") == (5, True)
      and T.parse_output_command("M42 P3 S0") == (3, False),
      "parse M42: any order / case / compact / S1.0 / other ports")
check(all(T.parse_output_command(c) is None for c in ("M42 P5 S0.5", "M42 P5", "M42 S1", "M420 P5 S1", "M226", RAD,
                                                    "M42 P5 S1 X2", "M42 P5.5 S1", "", None, 7)),
      "parse M42: PWM / missing parameter / other commands / junk are not switches")
check(T.split_cell(f"{ON} ; {RAD}") == [ON, RAD] and T.split_cell('M98 P"a;b.g" ; M226') == ['M98 P"a;b.g"', "M226"]
      and T.split_cell(" ; ;") == [] and T.split_cell(float("nan")) == [],
      "split_cell: ' ; ' separator, ';' inside quotes kept, empties dropped, non-str -> []")
check(T.order_cell([OFF, RAD, ON]) == [ON, RAD] and T.order_cell([RAD, OFF]) == [RAD, OFF]
      and T.order_cell([ON, USR, RAD]) == [ON, USR, RAD] and T.order_cell([RAD, ON]) == [ON, RAD],
      "order_cell: trigger-on before the waits, trigger-off after them, last switch of a port wins")
check(T.add_cell_command("", RAD) == RAD and T.add_cell_command(OFF, USR) == f"{USR} ; {OFF}"
      and T.add_cell_command(ON, RAD) == f"{ON} ; {RAD}" and T.add_cell_command(RAD, RAD) == RAD,
      "add_cell_command: adds (no duplicate) in the canonical order")
cell = f"{ON} ; {RAD} ; {USR}"
check(T.remove_cell_commands(cell, "sensor_wait.g") == f"{ON} ; {USR}" and T.remove_cell_commands(cell, "M226") ==
      f"{ON} ; {RAD}" and T.strip_trigger(cell) == f"{RAD} ; {USR}" and T.remove_cell_commands(RAD, "sensor_wait.g") == ""
      and np.isnan(T.remove_cell_commands(float("nan"), "M226")),
      "remove_cell_commands / strip_trigger remove only their kind (rad / usr / trigger)")
check(T.cell_trigger_state(f"{RAD} ; {OFF}") is False and T.cell_trigger_state(cell) is True
      and T.cell_trigger_state(RAD) is None and T.cell_trigger_state("M42 P3 S1") is None
      and T.cell_has_output_command("M42 P3 S1") and not T.cell_has_trigger("M42 P3 S1"),
      "cell_trigger_state / cell_has_trigger only for port 5; other ports are still output commands")
check(T.merge_cell("M226", f"{OFF} ; {RAD}") == f"M226 ; {OFF} ; {RAD}" and T.merge_cell("", ON) == ON,
      "merge_cell keeps the (chronological) order of imported commands")

print("\n=== state <-> commands, normalisation ===")
c = list(empty)
c[100], c[150], c[180], c[300], c[400] = ON, ON, OFF, OFF, f"{USR}"
c[500] = f"{RAD} ; {ON}"
S = T.trg_states(c)
check(S[99] == 0 and S[100] and S[179] and not S[180] and not S[300] and S[500] and S[-1],
      "trg_states: off at the start, S1 on, S0 off, a cell with a wait and S1 switches on, on to the end")
w = T.trg_windows(t, c)
check(w == [(1.0, 1.8), (5.0, 20.0)], f"windows {w} (redundant S1 / S0 ignored, last window to the plan end)")
cn = T.trg_normalise(c)
check(cn[150] == ON and cn[300] == "" and cn[100] == ON and cn[180] == OFF and cn[400] == USR
      and cn[500] == f"{ON} ; {RAD}" and T.trg_windows(t, cn) == w and T.trg_normalise(cn) == cn,
      "normalise: a redundant S0 removed, an S1 inside a window kept (explicit window start), waits kept, S1 placed "
      "before the wait, same windows, idempotent")
c2 = list(empty)
c2[-1] = OFF
c2[1990] = ON
c2[7] = float("nan")
cn2 = T.trg_write_states(c2, T.trg_states(c2))
check(cn2[-1] == OFF and cn2[1990] == ON and isinstance(cn2[7], float) and np.isnan(cn2[7]),
      "normalise: a window open at the plan end is closed by an explicit S0 on the last row; untouched cells stay")
check(T.trg_windows(t, cn2) == [(19.9, 20.0)], "a window ending at the plan end")
c2b = list(empty)
c2b[-1] = ON
check(T.trg_normalise(c2b)[-1] == "" and T.trg_windows(t, c2b) == [], "an S1 on the last row (no interval) is dropped")
st = np.zeros(n, bool)
st[10:20] = True
st[20:30] = True
check(T.trg_write_states(empty, st).count(ON) == 1 and T.trg_write_states(empty, st)[30] == OFF,
      "adjacent on-runs write one window (transitions only)")

print("\n=== manual switches, overlaps ===")
c, i1 = T.trg_switch_at(t, empty, 2.0, True)
c, i2 = T.trg_switch_at(t, c, 3.5, False)
c_in, i3 = T.trg_switch_at(t, c, 3.0, True)      # On inside a window: checked below (c goes on without it)
c, i4 = T.trg_switch_at(t, c, 8.0, False)
c, i5 = T.trg_switch_at(t, c, 10.0, True)
c, i6 = T.trg_switch_at(t, c, 12.004, False)
check(i1['changed'] and i2['changed'] and not i4['changed'] and "not on" in i4['message'] and i6['changed'],
      "Trigger Off outside a window changes nothing and says so")
check(i3['changed'] and i3['inner_start'] == 3.0 and T.trg_windows(t, c_in) == [(2.0, 3.5)] and c_in[300] == ON
      and T.trg_inner_starts(t, c_in) == [3.0] and "window start placed inside the run 2.000-3.500 s" in i3['message']
      and "A Trigger Off before 3.000 s ends only the earlier part" in i3['message'],
      f"[round 3, was 'nothing changed'] Trigger On inside a window: an explicit window start (S1) there, the window "
      f"shown unchanged, said so ({i3['message']})")
c_in2, _ = T.trg_switch_at(t, c_in, 2.5, False)
_, i3b = T.trg_switch_at(t, c_in, 3.0, True)
check(T.trg_windows(t, c_in2) == [(2.0, 2.5), (3.0, 3.5)] and not i3b['changed'] and "already starts at 3.000 s" in i3b['message'],
      f"  ... an Off before it ends only the earlier part; On again on that row changes nothing ({i3b['message']})")
check(T.trg_windows(t, c) == [(2.0, 3.5), (10.0, 12.0)], f"two windows, Off at 12.004 s snapped to 12.00 s: {T.trg_windows(t, c)}")
c3, i7 = T.trg_switch_at(t, c, 6.0, True)
check(T.trg_windows(t, c3) == [(2.0, 3.5), (6.0, 12.0)] and i7['merged_into'] == 10.0 and c3[1000] == ON
      and "on until the window at 10.000 s starts; press Trigger Off to end it earlier" in i7['message'],
      f"On before a later window: shown on until that window's off (one run), the later window keeps its S1 "
      f"({i7['message']})")
c4, i8 = T.trg_switch_at(t, c, 10.0, False)
check(T.trg_windows(t, c4) == [(2.0, 3.5)] and "removed" in i8['message'], "Off at a window's start removes it")
c5, i9 = T.trg_switch_at(t, c, 20.0, True)
check(not i9['changed'] and "plan end" in i9['message'], "On at the plan end: nothing to switch on")
c6, _ = T.trg_switch_at(t, c, 2.7, False)
check(T.trg_windows(t, c6) == [(2.0, 2.7), (10.0, 12.0)], "Off inside a window shortens it")
cw = list(c)
cw[200] = T.add_cell_command(cw[200], RAD)
cw[800] = RAD
cc, removed = T.trg_clear(cw)
check(removed == 4 and cc[200] == RAD and cc[800] == RAD and not T.plan_has_trigger(cc), "trg_clear keeps the waits")
check(all(T.remove_cell_commands(x, "M226") == x for x in cw if isinstance(x, str) and "M226" not in x),
      "clearing user pauses does not touch trigger / radiation cells")

print("\n=== periodic patterns ===")
rng24 = (0.0, 12.0)
cp, s = T.trg_apply_periodic(t, empty, "trigger_on", 2.0, 0.5, 0.0, rng24)
w = T.trg_windows(t, cp)
check(len(w) == 6 and w[0] == (0.0, 0.5) and w[-1] == (10.0, 10.5) and s['n_kept'] == 6
      and s['text'].startswith("6 windows of 0.5 s every 2 s from 0 to 12 s"), f"6 windows, summary: {s['text']}")
cp, s = T.trg_apply_periodic(t, empty, "trigger_on", 2.0, 0.5)
check(len(T.trg_windows(t, cp)) == 10 and "from 0 to 20 s" in s['text'], "full range: 10 windows")
cp, s = T.trg_apply_periodic(t, empty, "trigger_on", 3.0, 1.0, 0.5, (5.0, 15.0))
w = T.trg_windows(t, cp)
check(w[0] == (5.5, 6.5) and w[-1] == (14.5, 15.0) and len(w) == 4, f"offset 0.5 s from 5 s, last window clipped to 15 s: {w}")
cp, s = T.trg_apply_periodic(t, empty, "trigger_on", 2.0, 2.0, 0.0, (2.0, 8.0))
check(T.trg_windows(t, cp) == [(2.0, 8.0)], "D == P: contiguous windows merge into one")
check(raises(lambda: T.trg_apply_periodic(t, empty, "trigger_on", 2.0, 2.5), "must not exceed the period")
      and raises(lambda: T.trg_apply_periodic(t, empty, "trigger_on", 0.0, 0.5), "period")
      and raises(lambda: T.trg_apply_periodic(t, empty, "trigger_on", 0.005, 0.001), "row spacing")
      and raises(lambda: T.trg_apply_periodic(t, empty, "trigger_on", 1.0, 0.004), "below the row resolution")
      and raises(lambda: T.trg_apply_periodic(t, empty, "trigger_on", 1.0, 0.0), "duration")
      and raises(lambda: T.trg_apply_periodic(t, empty, "trigger_on", 1.0, 0.5, 0.0, (5.0, 30.0)), "outside the plan")
      and raises(lambda: T.trg_apply_periodic(t, empty, "trigger_on", 1.0, 0.5, 0.0, (5.0, 5.0)), "after its start")
      and raises(lambda: T.trg_apply_periodic(t, empty, "trigger_on", 1.0, 0.5, 6.0, (5.0, 10.0)), "first event"),
      "validation: D > P, P <= 0, P below the row spacing, D below the resolution, D = 0, range outside / empty, offset")
base, _ = T.trg_switch_at(t, empty, 4.0, True)
base, _ = T.trg_switch_at(t, base, 9.0, False)          # window 4..9
pat = dict(action="trigger_on", period=2.0, duration=0.5, offset=0.0, rng=(0.0, 12.0))
add, _ = T.trg_apply_periodic(t, base, combine="add", **pat)
rep, _ = T.trg_apply_periodic(t, base, combine="replace", **pat)
both, _ = T.trg_apply_periodic(t, base, combine="intersect", **pat)
check(T.trg_windows(t, add) == [(0.0, 0.5), (2.0, 2.5), (4.0, 9.0), (10.0, 10.5)], f"Add: {T.trg_windows(t, add)}")
check(T.trg_windows(t, rep) == [(0.0, 0.5), (2.0, 2.5), (4.0, 4.5), (6.0, 6.5), (8.0, 8.5), (10.0, 10.5)],
      f"Replace in range: {T.trg_windows(t, rep)}")
check(T.trg_windows(t, both) == [(4.0, 4.5), (6.0, 6.5), (8.0, 8.5)], f"Only where both: {T.trg_windows(t, both)}")
rep2, _ = T.trg_apply_periodic(t, base, combine="replace", action="trigger_on", period=2.0, duration=0.5, rng=(5.0, 7.0))
check(T.trg_windows(t, rep2) == [(4.0, 5.5), (7.0, 9.0)],
      f"Replace in the subset 5..7 s: one pulse 5-5.5 s inside, the window parts outside stay: {T.trg_windows(t, rep2)}")
off, s = T.trg_apply_periodic(t, base, "beam_off", 2.0, 0.5, 0.0, (4.0, 9.0))
check(T.trg_windows(t, off) == [(4.5, 6.0), (6.5, 8.0), (8.5, 9.0)] and "trigger-off gaps" in s['text'],
      f"Beam off: existing AND NOT window within the range: {T.trg_windows(t, off)}")
off2, _ = T.trg_apply_periodic(t, base, "beam_off", 2.0, 0.5, 0.0, (6.0, 8.0))
check(T.trg_windows(t, off2) == [(4.0, 6.0), (6.5, 9.0)], "Beam off in a subset leaves the rest")
cwt = list(base)
cwt[400] = T.add_cell_command(cwt[400], RAD)
wp, s = T.trg_apply_periodic(t, cwt, "wait_rad", 4.0, 0.0, 0.0, (0.0, 12.0))
check([i for i, x in enumerate(wp) if "sensor_wait" in str(x)] == [0, 400, 800] and s['n_added'] == 2
      and s['n_present'] == 1 and wp[400] == f"{ON} ; {RAD}" and T.trg_windows(t, wp) == T.trg_windows(t, base),
      "Wait radiation every 4 s: added to the cells (trigger kept, no duplicate), windows unchanged")
wu, s = T.trg_apply_periodic(t, empty, "wait_user", 5.0, rng=(2.0, 20.0))
check([i for i, x in enumerate(wu) if x == USR] == [200, 700, 1200, 1700] and "4 Wait User pauses every 5 s" in s['text'],
      "Wait user every 5 s from 2 s")
pv = T.trg_periodic_preview(t, 2.0, 0.5, 0.0, (0.0, 12.0))
check(pv['windows'] == T.trg_windows(t, T.trg_apply_periodic(t, empty, "trigger_on", 2.0, 0.5, 0.0, (0.0, 12.0))[0]),
      "periodic preview = the windows Apply places")

print("\n=== position-gated trigger ===")
LAT = 15 + 10 * np.sin(2 * np.pi * t / 4.0)
AP = 7.5 + 5 * np.cos(2 * np.pi * t / 5.0)
SI = np.full(n, 3.0)
vals = {"LAT": LAT, "AP": AP, "SI": SI}
g1 = T.trg_gate_mask(vals, {"LAT": (10.0, 20.0)})
check(np.array_equal(g1, (LAT >= 10) & (LAT <= 20)), "one axis: on where LAT is inside [10, 20], the others ignored")
g2 = T.trg_gate_mask(vals, {"LAT": (10.0, 20.0), "AP": (5.0, 10.0)})
check(np.array_equal(g2, (LAT >= 10) & (LAT <= 20) & (AP >= 5) & (AP <= 10)) and g2.sum() < g1.sum(),
      "two axes: AND of the conditions")
g3 = T.trg_gate_mask(vals, {"LAT": (2.0, 9.0), "AP": (2.0, 9.0), "SI": (2.0, 9.0)})
check(np.array_equal(g3, (LAT >= 2) & (LAT <= 9) & (AP >= 2) & (AP <= 9)), "same margins for all axes")
g4 = T.trg_gate_mask(vals, {"LAT": (10.0, 20.0)}, flip=True)
check(np.array_equal(g4, ~g1), "flip inverts")
check(raises(lambda: T.trg_gate_mask(vals, {}), "at least one axis")
      and raises(lambda: T.trg_gate_mask(vals, {"LAT": (5.0, 1.0)}), "min")
      and raises(lambda: T.trg_gate_mask(vals, {"Q": (0.0, 1.0)}), "not in the plan"),
      "validation: no used axis, Min > Max, unknown axis")
ga, s = T.trg_apply_gate(t, empty, vals, {"LAT": (10.0, 20.0)}, rng=(4.0, 12.0))
wg = T.trg_windows(t, ga)
check(all(4.0 - 1e-9 <= a and b <= 12.0 + 1e-9 for a, b in wg) and len(wg) == 5 and wg[0][0] == 4.0
      and wg[-1][1] == 12.0 and "Result" in s['text'], f"range subset: windows only inside 4..12 s ({wg})")
gw = T.trg_gate_preview(t, vals, {"LAT": (10.0, 20.0)}, rng=(4.0, 12.0))
check(gw == wg, "gate preview = the windows Apply places (empty plan)")
k_out = 400 + int(np.flatnonzero(~g1[400:])[0])
check(abs(wg[0][1] - t[k_out]) < 1e-9, f"the first gate window ends at the first row where LAT leaves [10, 20] ({t[k_out]} s)")
gadd, _ = T.trg_apply_gate(t, base, vals, {"LAT": (10.0, 20.0)}, rng=(10.0, 20.0), combine="add")
grep_, _ = T.trg_apply_gate(t, base, vals, {"LAT": (10.0, 20.0)}, rng=(6.0, 20.0), combine="replace")
gand, _ = T.trg_apply_gate(t, base, vals, {"LAT": (10.0, 20.0)}, combine="intersect")
Sb = T.trg_states(base)
R1 = T.trg_range_mask(t, (10.0, 20.0))
R2 = T.trg_range_mask(t, (6.0, 20.0))
exp_add = (Sb | (g1 & R1))[:-1]
exp_rep = ((Sb & ~R2) | (g1 & R2))[:-1]
exp_and = (Sb & g1)[:-1]
check(np.array_equal(T.trg_states(gadd)[:-1], exp_add) and np.array_equal(T.trg_states(grep_)[:-1], exp_rep)
      and np.array_equal(T.trg_states(gand)[:-1], exp_and), "gate combine: Add / Replace in range / Only where both")
check(T.trg_windows(t, gand) and all(4.0 - 1e-9 <= a and b <= 9.0 + 1e-9 for a, b in T.trg_windows(t, gand)),
      "Only where both: the 4..9 s window cut by the LAT margins")
per, _ = T.trg_apply_periodic(t, empty, "trigger_on", 2.0, 0.5)
pg, _ = T.trg_apply_gate(t, per, vals, {"LAT": (10.0, 20.0), "AP": (5.0, 10.0)}, combine="intersect")
Sp, Sg = T.trg_states(per), T.trg_states(pg)
check(np.array_equal(Sg[:-1], (Sp & g2)[:-1]) and Sg.sum() < Sp.sum(),
      "pulses every 2 s, only inside the LAT/AP margins (intersection)")

print("\n=== G-code ===")
X = 10 + 5 * np.sin(2 * np.pi * t / 4.0)
cmds = list(empty)
cmds, _ = T.trg_switch_at(t, cmds, 2.0, True)
cmds, _ = T.trg_switch_at(t, cmds, 3.5, False)
cmds, _ = T.trg_switch_at(t, cmds, 6.0, True)
cmds, _ = T.trg_switch_at(t, cmds, 7.25, False)
cmds, _ = T.trg_switch_at(t, cmds, 15.0, True)            # on to the plan end
cmds[200] = T.add_cell_command(cmds[200], RAD)            # wait at the window start (S1 before it)
cmds[725] = T.add_cell_command(cmds[725], USR)            # wait at a window end (S0 after it)
plan_w = T.trg_windows(t, cmds)
cols = {"X": X, "Y": np.zeros(n), "Z": np.full(n, 2.0), "Command": cmds}
g, _ = G.generate_gcode_string("Lung Phantom", t, cols, (40, 40, 40), speed=50, acc=1000, jerk=600, min_speed=0.1,
                               step_overhead_ms=3.0)
L = g.splitlines()
first_move = next(k for k, l in enumerate(L) if l.startswith("G1 "))
check(L[first_move - 2:first_move] == ["; trigger safety off", "M42 P5 S0"] and L[first_move - 3].startswith("; --- Execution"),
      "start: 'M42 P5 S0' after the header settings, before the first move")
check(L[-2:] == ["; trigger safety off", "M42 P5 S0"] and L[-3].startswith(("G1", "G4", "; ---", "M42")),
      f"end: 'M42 P5 S0' after the last move / dwell ({L[-3]!r})")
m42 = [k for k, l in enumerate(L) if l.startswith("M42")]
check(len(m42) == 2 + 6, f"{len(m42)} M42 lines = 6 switches (the last window closed on the last row) + 2 safety")
check(L[-4:] == ["; trigger off", OFF, "; trigger safety off", OFF] and L[-5].startswith(("G1", "G4", "; ---")),
      f"end: the explicit S0 of the window open at the plan end comes after the last move, then the safety S0 ({L[-6:]})")
check(all(L[k - 1] in ("; trigger on", "; trigger off", "; trigger safety off") for k in m42),
      "every M42 has its comment line")
k_on = L.index("M42 P5 S1")
check(L[k_on + 1] == "; waiting for radiation" and L[k_on + 2] == RAD, "S1 before the wait in the same row")
k_usr = L.index("M226")
check(L[k_usr + 1] == "; trigger off" and L[k_usr + 2] == OFF, "S0 after the wait in the same row")
inner = [k for k in m42[1:-2]]    # without the safety lines and the end S0 (checked above: after the last move)
check(all(any(L[j].startswith(("G1", "G4")) for j in range(k - 6, k)) and any(L[j].startswith("G1") for j in range(k + 1, k + 6))
          for k in inner), "every switch lies between moves (G1/G4 before, G1 after)")
p = G.parse_gcode_timeline(L)
tt = np.array([r['time'] for r in p.rows])
cc = [r['Command'] for r in p.rows]
gw = T.trg_windows(tt, cc)
check(len(gw) == len(plan_w) and all(abs(a - c_) <= 0.0105 and abs(b - d) <= 0.0105 for (a, b), (c_, d) in zip(gw, plan_w)),
      f"round trip plan -> G-code -> parse: same windows within one row (plan {plan_w}, parsed {[(round(a, 4), round(b, 4)) for a, b in gw]})")
err = max(max(abs(a - c_), abs(b - d)) for (a, b), (c_, d) in zip(gw, plan_w))
check(err < 0.002, f"  ... max time error {err * 1000:.2f} ms")
check([lb for lb, _ in p.pause_times] == ["sensor_wait", "M226"], "M42 is not a pause (pause_times only has the waits)")
sw_rows = [(r['time'], r['Command']) for r in p.rows if "M42" in str(r['Command'])]
check(len(sw_rows) == 6 and sw_rows[0][1] == ON and sw_rows[-1][1] == OFF and abs(sw_rows[-1][0] - p.time) < 1e-9,
      "parser: the explicit S0 ends the last window at the plan end; the start / end safety S0 add no row")
L_old = L[:-4] + L[-2:]           # G-code written before the explicit end S0 existed: only the safety S0 at the end
p_old = G.parse_gcode_timeline(L_old)
sw_old = [(r['time'], r['Command']) for r in p_old.rows if "M42" in str(r['Command'])]
check(sw_old == sw_rows, "an older file without the explicit end S0: its end safety S0 closes the window (same rows)")
check(L[m42[0]] == OFF and L[m42[-1]] == OFF, "first and last M42 lines are the safety S0")
p_nt = G.parse_gcode_timeline(L[:m42[0] - 1] + L[m42[0] + 1:])
check(p_nt.rows == [r for r in p.rows], "dropping the start safety lines changes nothing in the parsed rows")
# bake: switches are G1 boundaries
slow = np.clip(t * 0.02, 0, None)  # 0.02 mm/s: stepped
cmdk = list(empty)
cmdk[1234] = ON
b0 = G.bake_stepped_plan("Lung Phantom", t, {"X": slow, "Y": np.zeros(n), "Z": np.zeros(n)}, (40, 40, 40))
b1 = G.bake_stepped_plan("Lung Phantom", t, {"X": slow, "Y": np.zeros(n), "Z": np.zeros(n), "Command": cmdk}, (40, 40, 40))
check(G.is_plan_command(ON) and G.is_plan_command(f"{RAD} ; {OFF}") and not G.is_plan_command("M42 P5 S0.5"),
      "is_plan_command accepts M42 P<port> S<0|1> (and cells holding one)")
check(not np.array_equal(b0["X"], b1["X"]), "bake: a switch row is a forced knot (the stepped plan changes around it)")
gk, _ = G.generate_gcode_string("Lung Phantom", t, {"X": b1["X"], "Y": np.zeros(n), "Z": np.zeros(n), "Command": cmdk},
                                (40, 40, 40), min_speed=0.1)
pk = G.parse_gcode_timeline(gk.splitlines())
tk = [r['time'] for r in pk.rows if r['Command'] == ON]
check(len(tk) == 1 and abs(tk[0] - t[1234]) < 0.002, f"switch inside stepped motion runs at its row time ({tk} vs {t[1234]})")
# a multi-command cell never becomes a comment
gm, _ = G.generate_gcode_string("Lung Phantom", t, {"X": X, "Y": np.zeros(n), "Z": np.zeros(n),
                                                     "Command": [f"M226 ; {RAD}" if i == 300 else "" for i in range(n)]},
                                (40, 40, 40))
Lm = gm.splitlines()
check("M226" in Lm and RAD in Lm and not any(";" in l and not l.startswith(";") for l in Lm),
      "a cell with two commands is written as two lines (no ';' turns a command into a comment)")
check("M42" not in gm, "a plan without trigger has no M42 line")
# parser details
pp = G.parse_gcode_timeline(["G90", "M42 P5 S0", "M42 P5 S1", "G1 X0 F600", "G1 X10", "M42 P5 S1", "G4 P500",
                             "M42 P5 S0", "M42 P5 S0", "G1 X0"])
rows_c = [(round(r['time'], 4), r['Command']) for r in pp.rows if r['Command']]
check(rows_c == [(0.0, "M42 P5 S1"), (1.0, "M42 P5 S1"), (1.5, "M42 P5 S0")] and pp.pause_times == [],
      f"parser: S1 before the first move joins the first row; a repeated S1 is a row (explicit window start, survives "
      f"an import); the safety / repeated S0 add no row ({rows_c})")

print("\n=== regressions (verifier round 1) ===")
# [HIGH] Crop / Trim must keep the trigger state of every kept row (CropTrimDialog row selection and time shift)


def cut(tt_, cmds_, a, b, mode):
    """CropTrimDialog.execute_action on (time, Command), with the trigger hook (trg_cut_commands)."""
    tt_ = np.asarray(tt_, float)
    new_c = T.trg_cut_commands(tt_, cmds_, a, b, mode)
    if mode == "crop":
        k = (tt_ >= a) & (tt_ <= b)
        return np.round(tt_[k] - tt_[k].min(), 3), new_c
    p1, p3 = tt_[tt_ < a], tt_[tt_ > b]
    dt_ = tt_[1] - tt_[0]
    return np.round(np.concatenate([p1, p3 - (p3.min() - (p1.max() + dt_))]), 3), new_c


def wins_of(tt_, cmds_):
    return [(round(a, 3), round(b, 3)) for a, b in T.trg_windows(tt_, cmds_)]


t60 = np.round(np.arange(0.0, 60.0 + 1e-9, 0.01), 6)
e60 = [""] * len(t60)
two, _ = T.trg_switch_at(t60, e60, 2.0, True)
two, _ = T.trg_switch_at(t60, two, 6.0, False)
two, _ = T.trg_switch_at(t60, two, 8.0, True)
two, _ = T.trg_switch_at(t60, two, 9.0, False)
two[300] = T.add_cell_command(two[300], RAD)               # a wait inside the first window, before the cut
two[650] = USR                                             # a wait inside the cut (removed with its row)
tt2, cc2 = cut(t60, two, 5.0, 7.0, "trim")
check(wins_of(tt2, cc2) == [(2.0, 5.0), (5.99, 6.99)],
      f"Trim [5, 7] with windows (2,6) and (8,9): the first ends at the joint, the second keeps its length ({wins_of(tt2, cc2)})")
S_exp = T.trg_states(two)[(t60 < 5.0) | (t60 > 7.0)]
check(np.array_equal(T.trg_states(cc2)[:-1], S_exp[:-1]), "Trim: every kept row has its original state")
check(cc2[300] == RAD and sum(USR in str(x) for x in cc2) == 0 and len(cc2) == len(tt2),
      "Trim: the kept wait stays, the wait inside the cut goes with its row")
one, _ = T.trg_switch_at(t60, e60, 2.0, True)
one, _ = T.trg_switch_at(t60, one, 6.0, False)
tt1, cc1 = cut(t60, one, 5.0, 7.0, "trim")
check(wins_of(tt1, cc1) == [(2.0, 5.0)], f"Trim [5, 7] of the window's end: it ends at the joint, not at the plan end ({wins_of(tt1, cc1)})")
ttc, ccc = cut(t60, one, 4.0, 10.0, "crop")
check(wins_of(ttc, ccc) == [(0.0, 2.0)] and ccc[0] == ON,
      f"Crop [4, 10] with window (2,6): the part 4-6 s stays as 0-2 s (S1 on row 0) ({wins_of(ttc, ccc)})")
ttc2, ccc2 = cut(t60, one, 3.0, 5.0, "crop")
check(wins_of(ttc2, ccc2) == [(0.0, 2.0)] and ccc2[-1] == OFF, "Crop inside a window: on over the whole cropped plan, S0 on its last row")
check(T.trg_cut_commands(t60, [RAD if i == 100 else "" for i in range(len(t60))], 0.5, 2.0, "crop")[50] == RAD,
      "Crop of a plan without trigger: cells unchanged")
# [MEDIUM] extending the plan with a new curve (create_curve appends rows with Command "") keeps a window's end
t10 = np.round(np.arange(0.0, 10.0 + 1e-9, 0.01), 6)
p10, _ = T.trg_apply_periodic(t10, [""] * len(t10), "trigger_on", 2.0, 0.5, 1.5)
t20 = np.round(np.arange(0.0, 20.0 + 1e-9, 0.01), 6)
ext = p10 + [""] * (len(t20) - len(t10))
check(T.trg_windows(t10, p10)[-1] == (9.5, 10.0) and p10[-1] == OFF and T.trg_windows(t20, ext)[-1] == (9.5, 10.0),
      f"periodic pulse clipped at the plan end: explicit S0 on the last row, still 0.5 s after extending to 20 s "
      f"({T.trg_windows(t20, ext)[-1]})")
m10, _ = T.trg_switch_at(t10, [""] * len(t10), 7.0, True)
m20 = m10 + [""] * (len(t20) - len(t10))
check(T.trg_windows(t20, m20) == [(7.0, 10.0)], "manual On without Off: the window keeps its end (old plan end) after extending")
_, i_end = T.trg_switch_at(t10, m10, 10.0, False)
check(not i_end['changed'] and "plan end" in i_end['message'], f"Off at the plan end: says the window already ends there ({i_end['message']})")
cont, i_on = T.trg_switch_at(t20, m20, 10.0, True)
check(i_on['changed'] and T.trg_windows(t20, cont) == [(7.0, 20.0)], "On at the old end continues the window into the new segment")
g10, _ = T.trg_apply_gate(t10, [""] * len(t10), {"X": np.linspace(0, 10, len(t10))}, {"X": (5.0, 20.0)})
check(g10[-1] == OFF and T.trg_windows(t20, g10 + [""] * (len(t20) - len(t10))) == [(5.0, 10.0)],
      "gate window reaching the plan end: also closed on the last row")
# [LOW] periodic: off gaps below the row resolution are reported (they merge pulses)
_, s1 = T.trg_apply_periodic(t10, [""] * len(t10), "trigger_on", 1.0, 0.996)
check(s1['n_merged'] == 9 and s1['warning'] and "9 off gaps of 0.004 s below the row resolution (0.01 s) merged" in s1['text'],
      f"P=1 D=0.996: 9 merged gaps reported ({s1['text']})")
_, s2 = T.trg_apply_periodic(t10, [""] * len(t10), "trigger_on", 0.333, 0.33)
w2 = T.trg_windows(t10, _)
check(s2['n_merged'] == s2['n_kept'] - len(w2) == 21 and s2['warning'], f"P=0.333 D=0.33: {s2['n_merged']} merged = requested - result")
_, s3 = T.trg_apply_periodic(t10, [""] * len(t10), "trigger_on", 2.0, 2.0)
_, s4 = T.trg_apply_periodic(t10, [""] * len(t10), "trigger_on", 2.0, 0.5)
check(s3['n_merged'] == 0 and not s3['warning'] and s4['n_merged'] == 0 and not s4['warning'] and "merged" not in s4['text'],
      "D == P (contiguous on purpose) and a normal pattern: no gap message")
full_on, _ = T.trg_switch_at(t10, [""] * len(t10), 0.0, True)
bo, s5 = T.trg_apply_periodic(t10, full_on, "beam_off", 1.0, 0.996)
check(s5['n_merged'] == 9 and "on gaps" in s5['text'] and "stays off" in s5['text'], f"Beam off: merged on-gaps reported ({s5['text']})")
# [LOW] export -> import -> export: the same switches (import normalises, the end S0 is explicit)


def import_like(gtxt):
    """fcn_create.import_gcode_action's command placement: parse, 10 ms grid, merge_cell, trg_normalise."""
    pr = G.parse_gcode_timeline(gtxt.splitlines())
    tg = np.arange(0.0, max(r['time'] for r in pr.rows) + 0.005, 0.01)
    cg = [""] * len(tg)
    for r in pr.rows:
        if r['Command']:
            k = int(round(r['time'] / 0.01))
            if 0 <= k < len(tg):
                cg[k] = T.merge_cell(cg[k], str(r['Command']).strip())
    if T.plan_has_trigger(cg):
        cg = T.trg_normalise(cg)
    return np.round(tg, 6), cg


X60 = 10 + 5 * np.sin(2 * np.pi * t60 / 4.0)
re_c, _ = T.trg_switch_at(t60, e60, 10.0, True)
re_c, _ = T.trg_switch_at(t60, re_c, 12.0, False)
re_c, _ = T.trg_switch_at(t60, re_c, 55.0, True)
ga, _ = G.generate_gcode_string("Lung Phantom", t60, {"X": X60, "Y": np.zeros(len(t60)), "Z": np.zeros(len(t60)), "Command": re_c},
                                (40, 40, 40), speed=50)
ti, ci = import_like(ga)
gb, _ = G.generate_gcode_string("Lung Phantom", ti, {"X": np.interp(ti, t60, X60), "Y": np.zeros(len(ti)), "Z": np.zeros(len(ti)),
                                                      "Command": ci}, (40, 40, 40), speed=50)
ma = [l for l in ga.splitlines() if l.startswith("M42")]
mb = [l for l in gb.splitlines() if l.startswith("M42")]
check(ma == mb and len(ma) == 6 and ci[-1] == OFF and wins_of(ti, ci) == [(10.0, 12.0), (55.0, 60.0)],
      f"export -> import -> export: the same {len(ma)} M42 lines ({len(mb)} after the re-import)")
old_txt = "\n".join(ga.splitlines()[:-4] + ga.splitlines()[-2:])
to, co = import_like(old_txt)
check(co[-1] == OFF and wins_of(to, co) == wins_of(ti, ci), "importing an older file (only the safety S0 at the end): same windows, S0 on the last row")
td, cd = import_like("\n".join(["G90", "G1 X0 F600", "M42 P5 S1", "G1 X10", "M42 P5 S0", "M42 P5 S1", "G1 X0"]))
sw_cd = [(round(float(td[k]), 2), x) for k, x in enumerate(cd) if x]
check(sw_cd == [(0.0, ON), (1.0, ON), (2.0, OFF)] and wins_of(td, cd) == [(0.0, 2.0)],
      f"import normalises: an off/on pair landing on one row is a window start there (S1 kept inside the run), the "
      f"window open at the end gets its S0 ({sw_cd})")

print("\n=== regressions (verifier round 2): manual windows in any order (event semantics) ===")
# [MEDIUM] an On before a later window merged with it and the next Off deleted that window (Undo could not help)


def presses(cmds_, seq, tt_=t60):
    infos = []
    for tm, on in seq:
        cmds_, inf = T.trg_switch_at(tt_, cmds_, tm, on)
        infos.append(inf)
    return cmds_, infos


def gc60(cmds_, tt_=t60):
    return G.generate_gcode_string("Lung Phantom", tt_, {"X": np.interp(tt_, t60, X60), "Y": np.zeros(len(tt_)),
                                                         "Z": np.zeros(len(tt_)), "Command": cmds_}, (40, 40, 40), speed=50)[0]


def gc_windows(gtxt):
    pg = G.parse_gcode_timeline(gtxt.splitlines())
    return wins_of([r['time'] for r in pg.rows], [r['Command'] for r in pg.rows])


def m42_of(gtxt):
    return [l for l in gtxt.splitlines() if l.startswith("M42")]


ao, inf = presses(list(e60), [(15.0, True), (20.0, False), (3.0, True)])
check(wins_of(t60, ao) == [(3.0, 20.0)] and T.trg_inner_starts(t60, ao) == [15.0] and inf[2]['merged_into'] == 15.0
      and "on until the window at 15.000 s starts; press Trigger Off to end it earlier" in inf[2]['message'],
      f"On 3 alone before (15,20): shown on 3..20 (as the G-code runs it), the 15 s start kept ({inf[2]['message']})")
g_on3 = gc60(ao)
check(m42_of(g_on3) == [OFF, ON, ON, OFF, OFF] and gc_windows(g_on3) == [(3.0, 20.0)],
      f"  G-code: S1 at 3 s, the repeated S1 at 15 s (harmless), S0 at 20 s; parsed (3, 20) ({m42_of(g_on3)})")
L15 = g_on3.splitlines()
pk = G.GcodeTimelineParser()
t_s1 = []
for ln in L15:
    if ln == ON:
        t_s1.append(pk.time)
    pk.feed_line(ln)
check(len(t_s1) == 2 and abs(t_s1[0] - 3.0) < 0.002 and abs(t_s1[1] - 15.0) < 0.002,
      f"  each S1 runs at its row time (queued behind the moves before it): {[round(x, 4) for x in t_s1]}")
ao2, inf2 = presses(ao, [(4.0, False)])
check(wins_of(t60, ao2) == [(3.0, 4.0), (15.0, 20.0)] and T.trg_events(t60, ao2) == [(3.0, True), (4.0, False), (15.0, True), (20.0, False)]
      and inf2[0]['kept_window'] == (15.0, 20.0) and "the window 15.000-20.000 s is kept" in inf2[0]['message']
      and not T.trg_inner_starts(t60, ao2),
      f"On 15, Off 20, On 3, Off 4 -> [(3,4),(15,20)]: the Off ends the new part only ({inf2[0]['message']})")
g_ao = gc60(ao2)
check(gc_windows(g_ao) == [(3.0, 4.0), (15.0, 20.0)] and m42_of(g_ao) == [OFF, ON, OFF, ON, OFF, OFF],
      f"  G-code windows [(3,4),(15,20)] ({gc_windows(g_ao)})")
tord, _ = presses(list(e60), [(3.0, True), (4.0, False), (15.0, True), (20.0, False)])
check(tord == ao2 and g_ao == gc60(tord), "  same cells and byte-identical G-code as the same presses in time order")
ex, infx = presses(list(e60), [(2.0, True), (4.0, False), (10.0, True), (12.0, False), (4.0, True)])
check(wins_of(t60, ex) == [(2.0, 12.0)] and infx[4]['extended'] and infx[4]['merged_into'] == 10.0 and ex[400] == ""
      and T.trg_inner_starts(t60, ex) == [10.0] and "on until the window at 10.000 s starts" in infx[4]['message'],
      f"(2,4),(10,12) + On 4: the window ending at 4 goes on (its S0 removed, no extra S1) into (10,12) ({infx[4]['message']})")
ex2, infx2 = presses(ex, [(6.0, False)])
check(wins_of(t60, ex2) == [(2.0, 6.0), (10.0, 12.0)] and infx2[0]['kept_window'] == (10.0, 12.0)
      and gc_windows(gc60(ex2)) == [(2.0, 6.0), (10.0, 12.0)],
      f"  ... Off 6 -> [(2,6),(10,12)], also in the G-code ({wins_of(t60, ex2)})")
W4_ = [(3.0, 4.0), (15.0, 20.0), (25.5, 26.0), (40.0, 52.25)]
bad = []
for perm in itertools.permutations(W4_):
    cp_, _ = presses(list(e60), [x for a, b in perm for x in ((a, True), (b, False))])
    if wins_of(t60, cp_) != W4_ or T.trg_inner_starts(t60, cp_):
        bad.append((perm, wins_of(t60, cp_)))
check(not bad, f"windows entered in any of the 24 orders (each On then its Off) -> the same 4 windows ({bad[:2]})")
bad = []
for f1, f2 in itertools.permutations([(4.0, False), (20.0, False)]):
    cp_, _ = presses(list(e60), [(15.0, True), (3.0, True), f1, f2])
    if wins_of(t60, cp_) != [(3.0, 4.0), (15.0, 20.0)]:
        bad.append(([f1, f2], wins_of(t60, cp_)))
check(not bad, f"On 15, On 3, then Off 4 / Off 20 in either order -> [(3,4),(15,20)] ({bad})")
c_in3, inf_in = presses(presses(list(e60), [(3.0, True)])[0], [(15.0, True)])
check(inf_in[0]['changed'] and inf_in[0]['inner_start'] == 15.0 and wins_of(t60, c_in3) == [(3.0, 60.0)]
      and T.trg_inner_starts(t60, c_in3) == [15.0] and "window start placed inside the run 3.000-60.000 s" in inf_in[0]['message']
      and "A Trigger Off before 15.000 s ends only the earlier part" in inf_in[0]['message'],
      f"[round 3, was 'still changes nothing'] On 3, then On 15 inside that run: a window start at 15 s, the run shown "
      f"unchanged ({inf_in[0]['message']})")
rm, infr = presses(ao, [(3.0, False)])
check(wins_of(t60, rm) == [(15.0, 20.0)] and "window removed; the window 15.000-20.000 s is kept" in infr[0]['message'],
      f"Off at the start of the new part removes only that part ({infr[0]['message']})")
rs, infs = presses(ao, [(15.0, False)])
tord_j, _ = presses(list(e60), [(3.0, True), (15.0, False), (15.0, True), (20.0, False)])
check(rs == tord_j and infs[0]['changed'] and infs[0]['joined_at'] == 15.0 and wins_of(t60, rs) == [(3.0, 20.0)]
      and not T.trg_inner_starts(t60, rs)
      and "the window start at 15.000 s removed; the parts before and after it touch: one run 3.000-20.000 s" in infs[0]['message'],
      f"[round 3b, was 'nothing changed'] Off right on the later window's start: the part 3-15 ends where (15,20) "
      f"starts, one run (3,20) with the same cells as in time order (that start removed) ({infs[0]['message']})")
snap_ao = list(ao)
T.trg_switch_at(t60, ao, 4.0, False)
check(ao == snap_ao, "a press never changes the commands it was given (the Undo snapshot stays intact)")
# invariants under random presses
rnd = random.Random(11)
viol = []
for _trial in range(200):
    cr = list(e60)
    for _ in range(rnd.randint(1, 8)):
        tm, on = round(rnd.uniform(0, 60) * 4) / 4, rnd.random() < 0.55
        prev = cr
        Sb = T._normalised_states(T.trg_states(prev))
        cr, inf_ = T.trg_switch_at(t60, prev, tm, on)
        if T.trg_normalise(cr) != cr or cr[-1] not in ("", OFF):
            viol.append(("canonical / last row", tm, on))
        if not inf_['changed']:
            continue
        r_ = inf_['row']
        Sa = T._normalised_states(T.trg_states(cr))
        if not np.array_equal(Sa[:r_], Sb[:r_]):
            viol.append(("rows before the press changed", tm, on))
        if on and not {x for x, s in T.trg_events(t60, prev) if s} <= {x for x, s in T.trg_events(t60, cr) if s} | {float(t60[r_])}:
            viol.append(("On lost a window start", tm))
        if not on:
            j_ = next((k for k in range(r_ + 1, len(t60)) if T.cell_trigger_state(prev[k]) is True), None)
            stop = j_ if j_ is not None else len(t60)
            later_b = [ev for ev in T.trg_events(t60, prev) if j_ is not None and ev[0] >= t60[j_] - 1e-9]
            later_a = [ev for ev in T.trg_events(t60, cr) if j_ is not None and ev[0] >= t60[j_] - 1e-9]
            if Sa[r_:stop].any() or later_b != later_a:
                viol.append(("Off past the next window start", tm))
check(not viol, f"200 random press sequences: canonical cells, rows before a press unchanged, On keeps every window start, "
                f"Off only up to the next start and every switch after it unchanged ({viol[:3]})")
# export -> import -> export with an explicit start inside a run (the merged state of On 3 before (15,20))
ti2, ci2 = import_like(g_on3)
g_on3b = gc60(ci2, ti2)
ti3, ci3 = import_like(g_on3b)
check(m42_of(g_on3b) == m42_of(g_on3) and m42_of(gc60(ci3, ti3)) == m42_of(g_on3)
      and T.trg_events(ti2, ci2) == T.trg_events(t60, ao) and T.trg_inner_starts(ti2, ci2) == [15.0],
      f"export -> import -> export (twice) of 'On 3 before (15,20)': the same {len(m42_of(g_on3))} M42 lines, the "
      f"repeated S1 survives the import once (no duplicate)")
imp_off, _ = presses(ci2, [(4.0, False)], ti2)
check(wins_of(ti2, imp_off) == [(3.0, 4.0), (15.0, 20.0)], "  ... and an Off 4 on the imported plan still keeps (15,20)")
check(T.output_state_changes({}, ON) and T.output_state_changes({5: True}, ON) and not T.output_state_changes({}, OFF)
      and not T.output_state_changes({5: False}, OFF) and T.output_state_changes({5: True}, OFF),
      "parser rule: every S1 is a row (also while on); an S0 on an output already off (safety lines) is not")
# Crop / Trim / extension / periodic / gate keep the explicit start
tcr, ccr = cut(t60, ao, 10.0, 30.0, "crop")
check(T.trg_inner_starts(tcr, ccr) == [5.0] and wins_of(tcr, presses(ccr, [(1.0, False)], tcr)[0]) == [(0.0, 1.0), (5.0, 10.0)],
      "Crop [10, 30]: the 15 s start stays (5 s after the shift); Off 1 then -> (0,1),(5,10)")
ttr, ctr = cut(t60, ao, 14.0, 16.0, "trim")
check(len(T.trg_inner_starts(ttr, ctr)) == 1 and abs(T.trg_inner_starts(ttr, ctr)[0] - 14.0) < 1e-6
      and wins_of(ttr, presses(ctr, [(4.0, False)], ttr)[0]) == [(3.0, 4.0), (14.0, 17.99)],
      "Trim [14, 16] cuts the 15 s start: it moves to the joint, Off 4 then keeps the rest of (15,20)")
t70_ = np.round(np.arange(0.0, 70.0 + 1e-9, 0.01), 6)
ext70 = ao + [""] * (len(t70_) - len(t60))
check(wins_of(t70_, presses(ext70, [(4.0, False)], t70_)[0]) == [(3.0, 4.0), (15.0, 20.0)],
      "extending the plan keeps the 15 s start (Off 4 afterwards still keeps (15,20))")
pad, _ = T.trg_apply_periodic(t60, ao, "trigger_on", 2.0, 0.5, 0.0, (30.0, 40.0), "add")
prp, _ = T.trg_apply_periodic(t60, ao, "trigger_on", 2.0, 0.5, 0.0, None, "replace")
gre, _ = T.trg_apply_gate(t60, ao, {"X": X60}, {"X": (-100.0, 100.0)}, rng=(30.0, 40.0), combine="replace")
check(T.trg_inner_starts(t60, pad) == [15.0] and T.trg_inner_starts(t60, gre) == [15.0] and not T.trg_inner_starts(t60, prp),
      "Periodic Add / gate Replace elsewhere keep the 15 s start; Periodic Replace over the whole plan drops it")

print("\n=== regressions (verifier round 3): every On before the Offs, any interleaving, touching windows ===")
# [MEDIUM] an On while the trigger was already on was rejected, so entering every On before the Offs lost windows
# [LOW] an Off right at a later window's start inside a run deleted that window (touching windows depended on the order)


def time_order(ws):
    return [x for a, b in sorted(ws) for x in ((a, True), (b, False))]


def valid_orders(ws):
    """Every press order of the windows' On / Off events in which each window's On comes before its Off."""
    evs = [(a, True, k) for k, (a, b) in enumerate(ws)] + [(b, False, k) for k, (a, b) in enumerate(ws)]
    for p in itertools.permutations(evs):
        pos = {(e[1], e[2]): j for j, e in enumerate(p)}
        if all(pos[(True, k)] < pos[(False, k)] for k in range(len(ws))):
            yield [(e[0], e[1]) for e in p]


def joined(ws):
    """The windows the time-order presses give: touching windows form one run."""
    out = []
    for a, b in sorted(ws):
        if out and abs(out[-1][1] - a) < 1e-9:
            out[-1] = (out[-1][0], b)
        else:
            out.append((a, b))
    return [(round(a, 3), round(b, 3)) for a, b in out]


rnd3 = random.Random(5)


def rand_windows(k, touch_p=0.0, tmax=59.0):
    """k disjoint windows (>= 2 rows between all their ends); with touch_p a window may start where the one before ends."""
    while True:
        pts = sorted(rnd3.sample(range(1, int(tmax * 100)), 2 * k))
        if all(pts[q + 1] - pts[q] >= 2 for q in range(len(pts) - 1)):
            ws = [[pts[2 * q] / 100.0, pts[2 * q + 1] / 100.0] for q in range(k)]
            for q in range(1, k):
                if rnd3.random() < touch_p:
                    ws[q][0] = ws[q - 1][1]
            return [tuple(w_) for w_ in ws]


def rand_valid(ws):
    evs = [(a, True, k) for k, (a, b) in enumerate(ws)] + [(b, False, k) for k, (a, b) in enumerate(ws)]
    while True:
        rnd3.shuffle(evs)
        pos = {(e[1], e[2]): j for j, e in enumerate(evs)}
        if all(pos[(True, k)] < pos[(False, k)] for k in range(len(ws))):
            return [(e[0], e[1]) for e in evs]


def expected_cells(ws):
    """Independent oracle for disjoint windows: an S1 on each start row, an S0 on each end row, nothing else."""
    c_ = list(e60)
    for a, b in ws:
        c_[int(round(a * 100))] = ON
        c_[int(round(b * 100))] = OFF
    return c_


_GW = {}


def gcw(cmds_):
    """Parsed G-code windows of the 60 s plan (memoised on the cells: the G-code is a function of the plan)."""
    k = tuple(cmds_)
    if k not in _GW:
        _GW[k] = gc_windows(gc60(cmds_))
    return _GW[k]


W2_, W3_ = [(3.0, 4.0), (15.0, 20.0)], [(3.0, 4.0), (15.0, 20.0), (25.0, 30.0)]
aof, inf_aof = presses(list(e60), [(3.0, True), (15.0, True), (4.0, False), (20.0, False)])
g_aof = gc60(aof)
check(wins_of(t60, aof) == W2_ and inf_aof[1]['changed'] and inf_aof[1]['inner_start'] == 15.0
      and T.trg_inner_starts(t60, presses(list(e60), [(3.0, True), (15.0, True)])[0]) == [15.0]
      and inf_aof[2]['kept_window'] == (15.0, 60.0) and gc_windows(g_aof) == W2_
      and aof == presses(list(e60), time_order(W2_))[0] and g_aof == gc60(presses(list(e60), time_order(W2_))[0]),
      f"On 3, On 15, Off 4, Off 20 -> [(3,4),(15,20)] in the plan and the parsed G-code; the same cells and byte-identical "
      f"G-code as in time order ({inf_aof[1]['message']} | {inf_aof[2]['message']})")
aof3, _ = presses(list(e60), [(3.0, True), (15.0, True), (25.0, True), (4.0, False), (20.0, False), (30.0, False)])
check(wins_of(t60, aof3) == W3_ and gc_windows(gc60(aof3)) == W3_ and m42_of(gc60(aof3)) == [OFF, ON, OFF, ON, OFF, ON, OFF, OFF],
      "On 3, On 15, On 25, Off 4, Off 20, Off 30 -> 3 windows; G-code: one S1 / S0 per window and the two safety S0")
bad = []
for f1, f2, f3 in itertools.permutations([(4.0, False), (20.0, False), (30.0, False)]):
    for o1, o2, o3 in itertools.permutations([(3.0, True), (15.0, True), (25.0, True)]):
        cp_, _ = presses(list(e60), [o1, o2, o3, f1, f2, f3])
        if wins_of(t60, cp_) != W3_:
            bad.append(([o1, o2, o3, f1, f2, f3], wins_of(t60, cp_)))
check(not bad, f"every On first, in any of the 6 x 6 orders of the Ons and the Offs -> the 3 windows ({bad[:1]})")
for ws in (W2_, W3_):
    ref_c, _ = presses(list(e60), time_order(ws))
    bad, tot = [], 0
    for seq in valid_orders(ws):
        tot += 1
        cp_, _ = presses(list(e60), seq)
        if wins_of(t60, cp_) != joined(ws) or cp_ != ref_c or cp_ != expected_cells(ws) or gcw(cp_) != joined(ws):
            bad.append((seq, wins_of(t60, cp_)))
    check(not bad and tot == (6 if len(ws) == 2 else 90),
          f"all {tot} press orders of {ws} (each On before its Off): the time-order windows and the same cells (one S1 / "
          f"S0 per window), so byte-identical G-code, parsed to the same windows ({len(bad)} wrong {bad[:1]})")
for touch_p, label, trials in ((0.0, "disjoint", 500), (0.5, "some touching", 200)):
    bad, n_g = [], 0
    for _trial in range(trials):
        ws = rand_windows(rnd3.randint(2, 5), touch_p)
        cp_, _ = presses(list(e60), rand_valid(ws))
        if wins_of(t60, cp_) != joined(ws):
            bad.append((ws, wins_of(t60, cp_)))
        elif touch_p == 0.0 and cp_ != expected_cells(ws):
            bad.append((ws, "cells differ from one S1 / S0 per window"))
        elif _trial < 20:
            n_g += 1
            if gcw(cp_) != joined(ws):
                bad.append((ws, "G-code", gcw(cp_)))
    check(not bad, f"{trials} random interleavings of 2-5 windows ({label}): the time-order windows ({n_g} also through "
                   f"the G-code{'; the same cells as in time order' if touch_p == 0.0 else ''}) ({len(bad)} wrong {bad[:1]})")
# touching windows: an Off at a later window's start inside the run joins them, as in time order
iss2, inf_j = presses(list(e60), [(15.0, True), (20.0, False), (3.0, True), (15.0, False)])
tj, _ = presses(list(e60), [(3.0, True), (15.0, False), (15.0, True), (20.0, False)])
check(wins_of(t60, iss2) == wins_of(t60, tj) == [(3.0, 20.0)] and gc_windows(gc60(iss2)) == gc_windows(gc60(tj)) == [(3.0, 20.0)]
      and inf_j[3]['changed'] and inf_j[3]['joined_at'] == 15.0 and iss2 == tj and not T.trg_inner_starts(t60, iss2),
      f"On 15, Off 20, On 3, Off 15 -> [(3,20)] (the 15-20 s window is no longer deleted), the same cells as the time "
      f"order; parsed G-code too ({inf_j[3]['message']})")
iss2b, _ = presses(iss2, [(10.0, False)])
tj2, _ = presses(tj, [(10.0, False)])
check(wins_of(t60, iss2b) == wins_of(t60, tj2) == [(3.0, 10.0)],
      f"  ... an Off 10 afterwards ends the joined run at 10 s, as in time order ({wins_of(t60, iss2b)})")
for ws in ([(3.0, 15.0), (15.0, 20.0)], [(3.0, 10.0), (10.0, 15.0), (15.0, 20.0)], [(3.0, 10.0), (10.0, 15.0), (25.0, 30.0)],
           [(3.0, 3.01), (3.01, 3.02), (3.02, 3.03)]):
    bad, tot = [], 0
    for seq in valid_orders(ws):
        tot += 1
        cp_, _ = presses(list(e60), seq)
        if wins_of(t60, cp_) != joined(ws) or gcw(cp_) != joined(ws):
            bad.append((seq, wins_of(t60, cp_)))
    check(not bad, f"touching {ws}: all {tot} orders -> {joined(ws)} in the plan and the parsed G-code ({bad[:1]})")
# edges: Off at 0, On at the plan end, On / Off on the same row, a window to the plan end, waits on those rows
eA, ieA = presses(list(e60), [(0.0, True), (15.0, True), (0.0, False)])
check(wins_of(t60, eA) == [(15.0, 60.0)] and ieA[2]['kept_window'] == (15.0, 60.0),
      f"On 0, On 15, Off 0: the window from 0 removed up to the 15 s start, which is kept ({ieA[2]['message']})")
eB, ieB = presses(list(e60), [(3.0, True), (60.0, True), (15.0, True)])
check(not ieB[1]['changed'] and "plan end" in ieB[1]['message'] and ieB[2]['changed'] and T.trg_inner_starts(t60, eB) == [15.0],
      "On at the plan end inside a run: nothing changed (says so); the next On inside the run still places its start")
eC, ieC = presses(list(e60), [(3.0, True), (5.0, True), (5.0, False)])
check(wins_of(t60, eC) == [(3.0, 60.0)] and ieC[2]['changed'] and ieC[2]['joined_at'] == 5.0
      and not T.trg_inner_starts(t60, eC) and eC == presses(list(e60), [(3.0, True)])[0],
      "[round 3b] On / Off on the same row inside a run: the Off cancels that On (its start removed, the plan as before it)")
for seq in ([(3.0, True), (5.0, True), (5.0, False), (4.0, False)],
            [(3.0, True), (5.001, True), (5.004, False), (4.0, False)],
            [(3.0, True), (4.0, True), (4.0, False), (4.0, False)],
            [(3.0, True), (10.0, True), (15.0, True), (10.0, False), (4.0, False), (20.0, False)]):
    want = [(3.0, 4.0)] if len(seq) == 4 else [(3.0, 4.0), (15.0, 20.0)]
    eZ, _ = presses(list(e60), seq)
    check(wins_of(t60, eZ) == want and gc_windows(gc60(eZ)) == want,
          f"[round 3b] zero-length window / cancelled On inside an open run leaves no beam to the plan end: {seq} -> "
          f"{wins_of(t60, eZ)} (G-code {gc_windows(gc60(eZ))})")
eD, _ = presses(list(e60), [(5.0, True), (5.0, False)])
check(wins_of(t60, eD) == [] and not T.plan_has_trigger(eD), "On / Off on the same row alone: no window, no switch left")
eE, ieE = presses(list(e60), [(3.0, True), (50.0, True), (60.0, False), (4.0, False)])
check(wins_of(t60, eE) == [(3.0, 4.0), (50.0, 60.0)] and not ieE[2]['changed'] and eE[-1] == OFF
      and gc_windows(gc60(eE)) == [(3.0, 4.0), (50.0, 60.0)],
      "On 3, On 50, Off at the plan end (already ends there), Off 4 -> (3,4),(50,60), S0 on the last row, G-code too")
cwa = list(e60)
cwa[300], cwa[400], cwa[1500], cwa[2000] = USR, RAD, RAD, USR
cwa, _ = presses(cwa, [(3.0, True), (15.0, True), (4.0, False), (20.0, False)])
ga_l = [l for l in gc60(cwa).splitlines() if l.startswith("M42") or l == USR or l == RAD]
check(wins_of(t60, cwa) == W2_ and cwa[300] == f"{ON} ; {USR}" and cwa[400] == f"{RAD} ; {OFF}" and cwa[1500] == f"{ON} ; {RAD}"
      and cwa[2000] == f"{USR} ; {OFF}" and ga_l == [OFF, ON, USR, RAD, OFF, ON, RAD, USR, OFF, OFF],
      f"every On first with waits on the 3 / 4 / 15 / 20 s rows: S1 before the wait, S0 after it, in the G-code too ({ga_l})")
# export -> import -> export of the state with every On placed (two explicit starts inside the run), then the Offs
mid, _ = presses(list(e60), [(3.0, True), (15.0, True), (25.0, True)])
g_mid = gc60(mid)
ti4, ci4 = import_like(g_mid)
g_mid2 = gc60(ci4, ti4)
ti5, ci5 = import_like(g_mid2)
check(m42_of(g_mid) == [OFF, ON, ON, ON, OFF, OFF] and m42_of(g_mid2) == m42_of(g_mid) and m42_of(gc60(ci5, ti5)) == m42_of(g_mid)
      and T.trg_inner_starts(ti4, ci4) == [15.0, 25.0] and T.trg_events(ti4, ci4) == T.trg_events(t60, mid),
      f"export -> import -> export (twice) after On 3, On 15, On 25: the same M42 lines {m42_of(g_mid)}, the two starts "
      f"inside the run survive once (no multiplying switches)")
fin4, _ = presses(ci4, [(20.0, False), (4.0, False), (30.0, False)], ti4)
ti6, ci6 = import_like(gc60(fin4, ti4))
check(wins_of(ti4, fin4) == W3_ and wins_of(ti6, ci6) == W3_ and m42_of(gc60(ci6, ti6)) == m42_of(gc60(fin4, ti4)),
      "  ... the Offs on the imported plan give the 3 windows; their round trip keeps the same M42 lines")
# Crop / Trim / extension / periodic / gate with the explicit starts of every-On-first
tcm, ccm = cut(t60, mid, 10.0, 40.0, "crop")
fcm, _ = presses(ccm, [(2.0, False), (10.0, False)], tcm)
check(T.trg_inner_starts(tcm, ccm) == [5.0, 15.0] and wins_of(tcm, fcm) == [(0.0, 2.0), (5.0, 10.0), (15.0, 30.0)],
      f"Crop [10, 40] keeps both starts (5 and 15 s after the shift); Off 2, Off 10 -> {wins_of(tcm, fcm)}")
ttm, ctm = cut(t60, mid, 14.0, 16.0, "trim")
ftm, _ = presses(ctm, [(4.0, False), (20.0, False)], ttm)
check(len(T.trg_inner_starts(ttm, ctm)) == 2 and wins_of(ttm, ftm)[:2] == [(3.0, 4.0), (14.0, 20.0)],
      f"Trim [14, 16] across the 15 s start: it moves to the joint; Off 4, Off 20 -> {wins_of(ttm, ftm)}")
fx70, _ = presses(mid + [""] * (len(t70_) - len(t60)), [(4.0, False), (20.0, False), (30.0, False)], t70_)
check(wins_of(t70_, fx70) == W3_, "extending the plan after every On: the Offs still give the 3 windows")
pm, _ = presses(list(e60), [(15.0, True), (30.0, True)])
pm, _ = T.trg_apply_periodic(t60, pm, "trigger_on", 2.0, 0.5, 0.0, (3.0, 10.0), "add")
pm, _ = T.trg_apply_gate(t60, pm, {"X": X60}, {"X": (-100.0, 100.0)}, rng=(40.0, 50.0), combine="replace")
pm, _ = presses(pm, [(20.0, False), (35.0, False)])
check(wins_of(t60, pm) == [(3.0, 3.5), (5.0, 5.5), (7.0, 7.5), (9.0, 9.5), (15.0, 20.0), (30.0, 35.0)],
      f"On 15, On 30, Periodic Add in 3..10, gate Replace (full margins) in 40..50, Off 20, Off 35 -> {wins_of(t60, pm)}")

print("\n=== byte-identical G-code for plans without a trigger (against git HEAD's fcn_gcode.py) ===")
head_src = None
try:
    head_src = subprocess.run(["git", "-C", ROOT, "show", "HEAD:fcn_plan/fcn_gcode.py"], capture_output=True,
                              text=True, check=True, encoding="utf-8").stdout
except Exception as e:
    print("  (git show failed:", e, ")")
bak = os.environ.get("T1B_GCODE_BACKUP")
if head_src and "fcn_trigger" in head_src and bak and os.path.isfile(bak):
    head_src = open(bak, encoding="utf-8").read()
if head_src and "fcn_trigger" not in head_src:
    tmp = os.path.join(tempfile.mkdtemp(prefix="trg_head_"), "fcn_gcode_head.py")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(head_src)
    spec = importlib.util.spec_from_file_location("fcn_gcode_head", tmp)
    H = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(H)

    def both(device, tt_, cols_, lim, **kw):
        a = H.generate_gcode_string(device, tt_, dict(cols_), lim, **kw)[0]
        b = G.generate_gcode_string(device, tt_, dict(cols_), lim, **kw)[0]
        return a, b

    plans = {}
    cw_ = list(empty)
    cw_[0], cw_[500], cw_[-1] = USR, RAD, USR
    plans["sine (phantom) + waits"] = ("Lung Phantom", t, {"X": X, "Y": np.zeros(n), "Z": np.zeros(n), "Command": cw_},
                                       (40, 40, 40), dict(speed=50, acc=1000, jerk=600, min_speed=0.1))
    bk = H.bake_stepped_plan("Lung Phantom", t, {"X": slow, "Y": np.zeros(n), "Z": np.zeros(n), "Command": cw_}, (40, 40, 40))
    bk2 = G.bake_stepped_plan("Lung Phantom", t, {"X": slow, "Y": np.zeros(n), "Z": np.zeros(n), "Command": cw_}, (40, 40, 40))
    check(all(np.array_equal(bk[c_], bk2[c_]) for c_ in bk), "stepped bake identical")
    plans["stepped (phantom)"] = ("Lung Phantom", t, {"X": bk["X"], "Y": bk["Y"], "Z": bk["Z"], "Command": cw_},
                                  (40, 40, 40), dict(min_speed=0.1, step_overhead_ms=2.0))
    SIv = 15 + 10 * np.sin(2 * np.pi * t / 4.0)
    plans["sine (platform) + waits"] = ("Motion Platform", t, {"LAT": np.full(n, 20.0), "SI": SIv, "AP": np.full(n, 10.0),
                                        "Roll": np.zeros(n), "Pitch": 2 * np.sin(t), "Yaw": np.zeros(n), "Command": cw_},
                                        (40,) * 6, dict(lat_dim=300, si_dim=500, speed=20, min_speed=0.1))
    c2g = os.path.join(ROOT, "curve2.gcode")
    if os.path.isfile(c2g):
        pr = G.parse_gcode_timeline(open(c2g).read().splitlines())
        tr = np.array([r['time'] for r in pr.rows])
        o = np.argsort(tr, kind="stable")
        tg = np.round(np.arange(0.0, tr.max() + 0.005, 0.01), 6)
        imp = {k_: np.interp(tg, tr[o], np.array([r.get(k_, np.nan) for r in pr.rows])[o])
               for k_ in ("A", "B", "C", "D", "'e", "'f", "'a", "'c")}
        ci = [""] * len(tg)
        for r in pr.rows:
            if r['Command']:
                ci[int(round(r['time'] / 0.01))] = r['Command']
        plans["imported curve2.gcode (Other axes)"] = ("Other", tg, dict(imp, Command=ci), [60.0], dict(min_speed=0.1))
    for name, (dev, tt_, cols_, lim, kw) in plans.items():
        a, b = both(dev, tt_, cols_, lim, **kw)
        check(a == b and len(a) > 200, f"{name}: {len(b)} bytes, identical to HEAD")
        pa, pb = H.parse_gcode_timeline(a.splitlines()), G.parse_gcode_timeline(b.splitlines())
        check(pa.rows == pb.rows and pa.pause_times == pb.pause_times and pa.time == pb.time,
              f"{name}: parser rows / pauses identical to HEAD")
else:
    print("  SKIP: HEAD's fcn_gcode.py already has the trigger hooks (set T1B_GCODE_BACKUP to a pre-trigger copy)")

print("\n=== window edits (right-click menu in the Planning plot): trg_runs / trg_run_at / trg_delete_window / "
      "trg_set_window / trg_remove_inner_start ===")
we, _ = presses(list(e60), [(5.0, True), (8.0, False), (20.0, True), (25.0, False), (40.0, True), (45.0, False)])
we[700] = T.add_cell_command(we[700], RAD)                 # a pause inside the first window (7.00 s)
we[2000] = T.add_cell_command(we[2000], USR)               # a pause in the cell of the 20 s switch
r_ = T.trg_runs(we)
check(r_ == [(500, 800), (2000, 2500), (4000, 4500)], f"trg_runs: rows of the 3 runs ({r_})")
check(T.trg_run_at(t60, we, 6.0) == (500, 800) and T.trg_run_at(t60, we, 8.0) == (500, 800)
      and T.trg_run_at(t60, we, 8.03, tol=0.05) == (500, 800) and T.trg_run_at(t60, we, 12.0, tol=0.05) is None,
      "trg_run_at: inside, on the end edge, near the edge within tol; None away from every window")
dw, inf = T.trg_delete_window(t60, we, 500, 800)
check(wins_of(t60, dw) == [(20.0, 25.0), (40.0, 45.0)] and RAD in T.split_cell(dw[700])
      and not T.cell_has_trigger(dw[500]) and not T.cell_has_trigger(dw[800]) and USR in T.split_cell(dw[2000])
      and inf['removed'] == (5.0, 8.0), f"delete window 5-8: the others stay, the pause inside it kept ({inf['message']})")
check(all(dw[k] == we[k] for k in range(len(we)) if k not in (500, 800)), "delete window: no other cell touched")
g_dw = gc60(dw)
check(gc_windows(g_dw) == [(20.0, 25.0), (40.0, 45.0)] and m42_of(g_dw)[0] == OFF and m42_of(g_dw)[-1] == OFF,
      "delete window: parsed G-code windows agree, safety S0 at start and end")
mw, inf = T.trg_set_window(t60, we, 500, 800, 10.004, 12.0)
check(wins_of(t60, mw) == [(10.0, 12.0), (20.0, 25.0), (40.0, 45.0)] and not inf['joined']
      and RAD in T.split_cell(mw[700]), f"adjust 5-8 -> 10-12 (snapped to rows), pause kept ({inf['message']})")
jw, inf = T.trg_set_window(t60, we, 500, 800, 18.0, 22.0)
check(wins_of(t60, jw) == [(18.0, 25.0), (40.0, 45.0)] and inf['joined'] == [(20.0, 25.0)]
      and "joined with 20.000-25.000 s" in inf['message'] and T.trg_inner_starts(t60, jw) == []
      and USR in T.split_cell(jw[2000]), f"adjust into an overlap: the windows join (one run, no inner start; "
                                         f"pause kept) ({inf['message']})")
tw_, inf = T.trg_set_window(t60, we, 500, 800, 15.0, 20.0)
check(wins_of(t60, tw_) == [(15.0, 25.0), (40.0, 45.0)] and inf['joined'] == [(20.0, 25.0)]
      and T.trg_inner_starts(t60, tw_) == [], "adjust to touch the next window: joined")
lw, inf = T.trg_set_window(t60, we, 4000, 4500, 50.0, 60.0)
check(wins_of(t60, lw) == [(5.0, 8.0), (20.0, 25.0), (50.0, 60.0)] and lw[-1] == OFF,
      "adjust to the plan end: closed by an explicit S0 on the last row")
check(raises(lambda: T.trg_set_window(t60, we, 500, 800, 9.0, 9.003), "shorter than one plan row")
      and raises(lambda: T.trg_set_window(t60, we, 500, 800, 9.0, 8.0), "after the start")
      and raises(lambda: T.trg_set_window(t60, we, 500, 800, -1.0, 8.0), "inside the plan")
      and raises(lambda: T.trg_set_window(t60, we, 500, 801, 1.0, 2.0), "no trigger window")
      and raises(lambda: T.trg_delete_window(t60, we, 900, 1000), "no trigger window"),
      "trg_set_window / trg_delete_window reject: shorter than a row, end before start, outside the plan, no run")
check(T.trg_normalise(mw) == mw and T.trg_normalise(jw) == jw and T.trg_normalise(dw) == dw,
      "edited plans are normalised (export -> import -> export keeps the same M42 lines)")
ia, _ = presses(list(e60), [(30.0, True), (35.0, False), (10.0, True)])      # run 10..35 with an inner start at 30
check(T.trg_inner_starts(t60, ia) == [30.0], "setup: inner start at 30 s")
ir, inf = T.trg_remove_inner_start(t60, ia, 30.0)
check(T.trg_inner_starts(t60, ir) == [] and wins_of(t60, ir) == [(10.0, 35.0)] and inf['changed'],
      "remove inner start: the mark goes, the run stays")
nr, inf = T.trg_remove_inner_start(t60, ia, 20.0)
check(nr == ia and not inf['changed'], "remove inner start where there is none: nothing changed")
dr, _ = T.trg_delete_window(t60, ia, *T.trg_run_at(t60, ia, 20.0))
check(wins_of(t60, dr) == [] and not any(T.cell_has_trigger(c) for c in dr),
      "delete a run with an inner start: every switch of it removed (no window left over)")
g_mw = gc60(mw)
check(gc_windows(g_mw) == wins_of(t60, mw) and gc_windows(gc60(jw)) == wins_of(t60, jw),
      "adjusted plans: parsed G-code windows agree with the plan")

print(f"\n{'ALL PASSED' if not FAILS else f'{len(FAILS)} FAILED'} ({N[0]} checks)")
sys.exit(1 if FAILS else 0)
