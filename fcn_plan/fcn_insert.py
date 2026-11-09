"""
Insert an interval into a plan (the 'Insert' mode of Add Curve in the Planning tab, tab_planning_insert.py).

``insert_interval(df, t_at, length)`` opens a gap of ``length`` seconds at ``t_at``:

- every row with t >= t_at (the snapped row: the first plan row at / after t_at) moves right by the inserted length,
  with its axis values and its Command cell (pauses, trigger switches, other commands) unchanged;
- the gap rows (same row spacing as the plan) hold every axis at its position at t_at (the value of that row: the
  motion stops there, as the plan extension of Add Curve holds the last position) and have empty Command cells, so
  no switch edge is added: the trigger state in the gap is the state before the moved row, i.e. a window that spans
  t_at simply gets longer, a window that starts at t_at moves right with its row; a window that ENDS exactly at t_at
  (its S0 on the moved row: the trigger is off at t_at) keeps its end - its S0 goes to the first gap row, so the
  gap is off (no window grows over the inserted interval);
- rows before t_at are untouched; the explicit S0 on the last row moves with it (it stays the last row).

The inserted length is a whole number of plan rows (``length`` rounded to the row spacing).  The function is pure:
it returns a new dataframe (Vel. / Acc. columns dropped as Add Curve does) and never touches the input.  Inserting
at or after the plan end returns an unchanged copy (Add Curve then extends the plan as before).
"""

import numpy as np
import pandas as pd

from fcn_plan.fcn_duration import plan_step, axis_columns
from fcn_plan.fcn_trigger import (add_cell_command, output_command, plan_has_trigger, strip_trigger,
                                  trg_states)

TIME_TOL = 1e-6


def insert_row_index(df, t_at):
    """Index of the first row with time >= t_at (tolerance 1e-6 s); len(df) when t_at is past the plan end."""
    t = pd.to_numeric(df['time'], errors='coerce').to_numpy(float)
    idx = np.flatnonzero(t >= float(t_at) - TIME_TOL)
    return int(idx[0]) if len(idx) else len(t)


def insert_rows(df, length):
    """Number of plan rows an inserted interval of ``length`` seconds takes (>= 0)."""
    step = plan_step(df)
    return max(0, int(round(float(length) / step)))


def insert_interval(df, t_at, length):
    """New plan with a gap of ``length`` s (whole rows) at ``t_at``: rows at / after t_at shifted right, the gap holding
    every axis at its value at t_at, empty commands.  Returns (new_df, inserted_seconds); (copy, 0.0) when nothing is
    inserted (length < one row, or t_at at / past the plan end)."""
    out = df.copy()
    drop = [c for c in out.columns if str(c).startswith(('Vel.', 'Acc.'))]
    if drop:
        out = out.drop(columns=drop)
    if 'Command' not in out.columns:
        out['Command'] = ""
    n = len(out)
    if n == 0:
        return out, 0.0
    step = plan_step(out)
    k = insert_rows(out, length)
    i0 = insert_row_index(out, t_at)
    if k == 0 or i0 >= n:
        return out.reset_index(drop=True), 0.0
    ins = k * step
    t = pd.to_numeric(out['time'], errors='coerce').to_numpy(float)
    t0 = t[i0]
    head = out.iloc[:i0]
    tail = out.iloc[i0:].copy()
    gap_t = t0 + step * np.arange(k)
    gap = pd.DataFrame({c: [None] * k for c in out.columns})
    row = out.iloc[i0]
    for c in out.columns:
        if c == 'time':
            gap[c] = np.round(gap_t, 9)
        elif c == 'timestamp':
            gap[c] = np.round(gap_t, 9) * 1000.0
        elif c == 'Command':
            gap[c] = [""] * k
        elif c in axis_columns(out):
            v = pd.to_numeric(pd.Series([row[c]]), errors='coerce').iloc[0]
            gap[c] = 0.0 if pd.isna(v) else float(v)
        else:
            gap[c] = [row[c]] * k
    new_tail_t = np.round(pd.to_numeric(tail['time'], errors='coerce').to_numpy(float) + ins, 9)
    tail['time'] = new_tail_t
    if 'timestamp' in tail.columns:
        tail['timestamp'] = new_tail_t * 1000.0
    for c in out.columns:                      # keep the column dtypes of the plan (float axes, object commands)
        try:
            gap[c] = gap[c].astype(out[c].dtype)
        except (TypeError, ValueError):
            pass
    res = pd.concat([head, gap, tail], ignore_index=True)
    res = res[list(out.columns)]
    if window_closes_at(out, i0):
        # the S0 on the row at t_at closes a window there: the trigger is OFF at t_at, so the gap is OFF too - the
        # window keeps its end (the S0 goes to the first gap row; the moved row needs no switch any more)
        res.at[i0, 'Command'] = add_cell_command(res.at[i0, 'Command'], output_command(False))
        res.at[i0 + k, 'Command'] = strip_trigger(res.at[i0 + k, 'Command'])
    return res, float(ins)


def window_closes_at(df, i0):
    """True when the trigger is on before row i0 and row i0 switches it off (a window ends exactly at that row)."""
    if 'Command' not in df.columns or not (0 < i0 < len(df)):
        return False
    cmds = list(df['Command'])
    if not plan_has_trigger(cmds):
        return False
    st = trg_states(cmds)
    return bool(st[i0 - 1]) and not bool(st[i0])
