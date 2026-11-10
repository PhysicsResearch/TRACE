"""
Insert an interval into a plan (fcn_plan/fcn_insert.py, the 'Insert' mode of Add Curve), no Qt.
Covers: rows before Start untouched; every row from Start on (axes, Command cells with pauses and trigger switches)
moved right by the inserted length; the gap holding every axis at its value at Start with empty commands; trigger
windows before / spanning / starting at / after Start and the window closed by the explicit S0 on the last row;
explicit window starts inside a run kept; the G-code: the same M42 / M226 / M98 lines in the same order, pauses and
trigger windows shifted by the inserted length; edge cases (Start 0, Start at the plan end, past the end, a length
below one row, rounding to whole rows, Vel. / Acc. dropped, the input dataframe not changed).
Run:  C:\\Users\\gabri\\anaconda3\\envs\\TRACE\\python.exe scratch\\test_insert_core.py
"""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)
import numpy as np
import pandas as pd

from fcn_plan import fcn_trigger as T
from fcn_plan import fcn_gcode as G
from fcn_plan.fcn_insert import insert_interval, insert_row_index, insert_rows

FAILS = []
N = [0]


def check(cond, msg):
    N[0] += 1
    print(("PASS  " if cond else "FAIL  ") + msg)
    if not cond:
        FAILS.append(msg)


ON, OFF = T.output_command(True), T.output_command(False)
RAD, USR = T.WAIT_RAD_CMD, T.WAIT_USER_CMD


def make_plan(t_end=20.0, step=0.01):
    n = int(round(t_end / step)) + 1
    t = np.round(np.arange(n) * step, 9)
    df = pd.DataFrame({'timestamp': t * 1000.0, 'time': t,
                       'X': 10.0 + 8.0 * np.sin(2 * np.pi * t / 4.0),
                       'Y': 2.0 + t,
                       'Z': np.full(n, 5.0)})
    df['Command'] = [""] * n
    return df


def at(df, x):
    return int(np.argmin(np.abs(df['time'].to_numpy(float) - x)))


def put(df, x, cmd):
    i = at(df, x)
    df.at[i, 'Command'] = T.add_cell_command(df.at[i, 'Command'], cmd)


def windows(df):
    return [(round(a, 3), round(b, 3)) for a, b in T.trg_windows(df['time'].to_numpy(float), list(df['Command']))]


def pauses(df):
    out = []
    for tm, c in zip(df['time'], df['Command']):
        for piece in T.split_cell(c):
            if piece in (RAD, USR):
                out.append(('rad' if piece == RAD else 'usr', round(float(tm), 3)))
    return out


def gcode(df):
    g, _ = G.generate_gcode_string("Lung Phantom", df['time'].to_numpy(float),
                                   {"X": df['X'].to_numpy(float), "Y": df['Y'].to_numpy(float),
                                    "Z": df['Z'].to_numpy(float), "Command": list(df['Command'])},
                                   (40, 40, 40), speed=50)
    return g


def cmd_lines(g):
    return [l for l in g.splitlines() if l.startswith(("M42", "M226", "M98"))]


def gc_pauses(g):
    pg = G.parse_gcode_timeline(g.splitlines())
    return [(k, round(tm, 2)) for k, tm in pg.pause_times]


def gc_windows(g):
    pg = G.parse_gcode_timeline(g.splitlines())
    return [(round(a, 2), round(b, 2)) for a, b in T.trg_windows([r['time'] for r in pg.rows],
                                                                 [r['Command'] for r in pg.rows])]


# ---------------------------------------------------------------- main case
base = make_plan()
put(base, 3.0, RAD)            # pause before Start
put(base, 10.0, USR)           # pause after Start
put(base, 6.0, ON)             # window spanning Start (6 - 9)
put(base, 7.0, ON)             # explicit window start inside that run
put(base, 9.0, OFF)
put(base, 12.0, ON)            # window after Start (12 - 14)
put(base, 14.0, OFF)
put(base, 18.0, ON)            # window open at the plan end ...
base['Command'] = T.trg_normalise(list(base['Command']))     # ... closed by the explicit S0 on the last row
check(base['Command'].iat[-1] == OFF, "setup: the window open at the plan end has the explicit S0 on the last row")
w0 = windows(base)
check(w0 == [(6.0, 9.0), (12.0, 14.0), (18.0, 20.0)], f"setup windows {w0}")
orig = base.copy(deep=True)

START, LEN = 8.0, 5.0
new, ins = insert_interval(base, START, LEN)
check(base.equals(orig), "the input dataframe is not changed")
check(abs(ins - LEN) < 1e-9, f"inserted length {ins}")
n0, k = len(base), insert_rows(base, LEN)
check(k == 500 and len(new) == n0 + k, f"rows: {n0} + {k} = {len(new)}")
check(abs(new['time'].iat[-1] - (20.0 + LEN)) < 1e-9, f"plan end 20 -> {new['time'].iat[-1]}")
i0 = insert_row_index(base, START)
check(abs(base['time'].iat[i0] - START) < 1e-9, "Start snaps to the plan row at 8.00 s")
check(new.iloc[:i0].reset_index(drop=True).equals(base.iloc[:i0].reset_index(drop=True)),
      "rows before Start untouched (times, axes, commands)")
gap = new.iloc[i0:i0 + k]
check(np.allclose(gap['time'].to_numpy(float), START + 0.01 * np.arange(k)), "gap rows on the plan's row spacing")
check(all(np.allclose(gap[c].to_numpy(float), base[c].iat[i0]) for c in ('X', 'Y', 'Z')),
      "gap: every axis holds its position at Start (X, Y, Z)")
check(all(c == "" for c in gap['Command']), "gap: empty Command cells (no new switch / pause)")
tail_new = new.iloc[i0 + k:].reset_index(drop=True)
tail_old = base.iloc[i0:].reset_index(drop=True)
check(np.allclose(tail_new['time'].to_numpy(float), tail_old['time'].to_numpy(float) + LEN)
      and np.allclose(tail_new['timestamp'].to_numpy(float), (tail_old['time'].to_numpy(float) + LEN) * 1000.0),
      "rows from Start on: time and timestamp + inserted length")
check(all(np.allclose(tail_new[c].to_numpy(float), tail_old[c].to_numpy(float)) for c in ('X', 'Y', 'Z'))
      and list(tail_new['Command']) == list(tail_old['Command']),
      "rows from Start on: axis values and Command cells unchanged")
w1 = windows(new)
check(w1 == [(6.0, 14.0), (17.0, 19.0), (23.0, 25.0)],
      f"windows: spanning Start gets longer, the later ones move right, the plan-end window moves with the end {w1}")
check(new['Command'].iat[-1] == OFF, "the explicit S0 stays on the (new) last row")
check(sum(1 for c in new['Command'] if T._cell_on(c)) == sum(1 for c in base['Command'] if T._cell_on(c)),
      "the explicit window start inside the run (S1 at 7 s) kept, no S1 added or lost")
check(pauses(new) == [('rad', 3.0), ('usr', 15.0)], f"pauses: before Start kept, after Start moved {pauses(new)}")
check(list(new['Command']) == list(T.trg_normalise(list(new['Command']))), "the Command column is canonical")
check(list(new.columns) == list(base.columns), "same columns, same order")

# G-code
g_old, g_new = gcode(base), gcode(new)
check(cmd_lines(g_old) == cmd_lines(g_new) and len(cmd_lines(g_new)) >= 9,
      f"G-code: the same M42 / M226 / M98 lines in the same order ({len(cmd_lines(g_new))})")
p_old, p_new = gc_pauses(g_old), gc_pauses(g_new)
check(len(p_old) == len(p_new) == 2 and p_new[0] == p_old[0] and abs(p_new[1][1] - (p_old[1][1] + LEN)) < 0.02,
      f"G-code pauses: the one before Start at the same time, the one after + {LEN} s ({p_old} -> {p_new})")
gw_old, gw_new = gc_windows(g_old), gc_windows(g_new)
check(len(gw_new) == 3 and abs(gw_new[0][0] - gw_old[0][0]) < 0.02 and abs(gw_new[0][1] - (gw_old[0][1] + LEN)) < 0.02
      and all(abs(a2 - (a1 + LEN)) < 0.02 and abs(b2 - (b1 + LEN)) < 0.02
              for (a1, b1), (a2, b2) in zip(gw_old[1:], gw_new[1:])),
      f"G-code trigger windows: spanning Start + {LEN} s longer, the later ones + {LEN} s ({gw_old} -> {gw_new})")
check(g_new.splitlines()[-4:] == g_old.splitlines()[-4:], "G-code end: explicit S0 then the safety S0 (unchanged)")

# ---------------------------------------------------------------- a window starting exactly at Start moves right
new2, ins2 = insert_interval(base, 12.0, 2.5)
check(windows(new2) == [(6.0, 9.0), (14.5, 16.5), (20.5, 22.5)] and all(c == "" for c in new2['Command'].iloc[
    at(base, 12.0):at(base, 12.0) + 250]), f"window starting at Start: moves right, gap off {windows(new2)}")

# ---------------------------------------------------------------- Start 0: everything moves
new3, ins3 = insert_interval(base, 0.0, 1.0)
check(abs(ins3 - 1.0) < 1e-9 and windows(new3) == [(7.0, 10.0), (13.0, 15.0), (19.0, 21.0)]
      and pauses(new3) == [('rad', 4.0), ('usr', 11.0)] and np.allclose(new3['X'].iloc[:100], base['X'].iat[0]),
      f"Start 0: everything + 1 s, the gap holds the first position {windows(new3)}")

# ---------------------------------------------------------------- Start at the plan end: the last row moves
new4, ins4 = insert_interval(base, 20.0, 2.0)
check(abs(ins4 - 2.0) < 1e-9 and abs(new4['time'].iat[-1] - 22.0) < 1e-9
      and windows(new4) == [(6.0, 9.0), (12.0, 14.0), (18.0, 20.0)],
      f"Start at the plan end: the last row moves to 22 s, the window open at the old end keeps its end 20 s (the "
      f"trigger is off at Start, like Replace) {windows(new4)}")
i4 = at(base, 20.0)
check(new4['Command'].iat[i4] == OFF and not T.cell_has_trigger(new4['Command'].iat[-1])
      and not T.trg_states(list(new4['Command']))[i4:].any(),
      "Start at the plan end: the S0 sits on the first gap row (20 s), the gap and the moved last row are off")

# ---------------------------------------------------------------- a window ending exactly at Start keeps its end
new9, ins9 = insert_interval(base, 9.0, 3.0)
i9 = at(base, 9.0)
check(abs(ins9 - 3.0) < 1e-9 and windows(new9) == [(6.0, 9.0), (15.0, 17.0), (21.0, 23.0)],
      f"window ending at Start: keeps its end 9 s, the later windows move right {windows(new9)}")
st9 = T.trg_states(list(new9['Command']))
check(not st9[i9:i9 + 300].any() and new9['Command'].iat[i9] == OFF
      and not T.cell_has_trigger(new9['Command'].iat[i9 + 300]),
      "window ending at Start: the gap is off (S0 on the first gap row, none left on the moved row)")
check(list(new9['Command']) == list(T.trg_normalise(list(new9['Command'])))
      and pauses(new9) == [('rad', 3.0), ('usr', 13.0)],
      f"window ending at Start: canonical Command column, pauses kept / moved {pauses(new9)}")
g9 = gcode(new9)
gw9 = gc_windows(g9)
check(cmd_lines(g9) == cmd_lines(g_old) and len(gw9) == 3 and abs(gw9[0][1] - gw_old[0][1]) < 0.02
      and all(abs(a2 - (a1 + 3.0)) < 0.02 and abs(b2 - (b1 + 3.0)) < 0.02
              for (a1, b1), (a2, b2) in zip(gw_old[1:], gw9[1:])),
      f"window ending at Start, G-code: same M42 / M226 / M98 order, the S0 at the old time, later windows + 3 s "
      f"({gw_old} -> {gw9})")

# ---------------------------------------------------------------- a Repeat (periodic) pattern
per = make_plan()
per['Command'] = T.trg_apply_periodic(per['time'].to_numpy(float), list(per['Command']), "trigger_on", 2.0, 0.5)[0]
wp = windows(per)
check(len(wp) >= 9 and (10.0, 10.5) in wp, f"periodic setup: every 2 s, on 0.5 s {wp[:4]} ... ({len(wp)})")
newp, insp = insert_interval(per, 10.5, 3.0)
exp = [w for w in wp if w[1] <= 10.5] + [(round(a + 3.0, 3), round(b + 3.0, 3)) for a, b in wp if a >= 10.5]
check(windows(newp) == exp, f"periodic, Insert at a window end (10.5 s): that window keeps its end, the later ones "
      f"+ 3 s {[w for w in windows(newp) if 8 <= w[0] <= 16]}")
check(cmd_lines(gcode(newp)) == cmd_lines(gcode(per)), "periodic, Insert at a window end: same G-code M42 order")
newq, insq = insert_interval(per, 10.25, 3.0)
expq = ([w for w in wp if w[1] <= 10.0] + [(10.0, 13.5)] +
        [(round(a + 3.0, 3), round(b + 3.0, 3)) for a, b in wp if a > 10.25])
check(windows(newq) == expq, f"periodic, Insert inside a window (10.25 s): that window 3 s longer, the later ones "
      f"+ 3 s {[w for w in windows(newq) if 8 <= w[0] <= 16]}")
newr, insr = insert_interval(per, 12.0, 3.0)
expr = [w for w in wp if w[1] <= 12.0] + [(round(a + 3.0, 3), round(b + 3.0, 3)) for a, b in wp if a >= 12.0]
check(windows(newr) == expr, f"periodic, Insert at a window start (12 s): it moves right, gap off "
      f"{[w for w in windows(newr) if 8 <= w[0] <= 18]}")

# ---------------------------------------------------------------- nothing inserted
new5, ins5 = insert_interval(base, 25.0, 3.0)
check(ins5 == 0.0 and new5.equals(base), "Start past the plan end: unchanged copy, 0 s inserted")
new6, ins6 = insert_interval(base, 5.0, 0.004)
check(ins6 == 0.0 and new6.equals(base), "length below half a row: unchanged copy, 0 s inserted")

# ---------------------------------------------------------------- whole rows, Vel. / Acc. dropped, 1 ms plans
fine = make_plan(t_end=2.0, step=0.001)
fine['Vel. X'] = 0.0
fine['Acc. X'] = 0.0
new7, ins7 = insert_interval(fine, 0.5, 0.2504)
check(abs(ins7 - 0.250) < 1e-9 and len(new7) == len(fine) + 250 and not any(c.startswith(('Vel.', 'Acc.'))
                                                                            for c in new7.columns),
      f"1 ms plan: 0.2504 s -> 250 rows (0.250 s), Vel. / Acc. dropped ({ins7})")
d = np.diff(new7['time'].to_numpy(float))
check(np.allclose(d, 0.001), "1 ms plan: uniform row spacing after the insert")
new8, ins8 = insert_interval(base, 8.004, 1.0)
check(abs(new8['time'].iat[insert_row_index(base, 8.004)] - 8.01) < 1e-9 and abs(ins8 - 1.0) < 1e-9,
      "Start between two rows: the first row at / after Start is the first moved row")

print(f"\n{N[0] - len(FAILS)}/{N[0]} passed" + ("" if not FAILS else "\nFAILED:\n  " + "\n  ".join(FAILS)))
sys.exit(1 if FAILS else 0)
