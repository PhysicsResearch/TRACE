"""
Total duration of a plan (the 'Total duration (s)' field of the Planning tab, tab_planning_curve_controls.py).

The plan length is the last 'time' of the plan dataframe (the default plans are 0 - 60 s).  Two operations, both
built from the existing code paths so that the plan invariants hold:

- ``extend_plan``: rows appended up to the new end exactly as Create Curve extends a plan (fcn_create.create_curve:
  same step, every axis held at its last value, empty Command), Vel. / Acc. columns dropped as there.  A trigger
  window that runs to the plan end keeps its old end (its S0 stays on the old last row), as Create Curve's extension
  and Insert at the plan end do: the trigger is never left on during the added hold the user did not ask for.
- ``crop_plan_end``: the plan kept from 0 to the new end exactly as the Crop dialog does (CropTrimDialog, mode
  'crop': rows t_start <= t <= t_end, time re-indexed and rounded, timestamp from time), with the Command column
  from fcn_trigger.trg_cut_commands when the plan holds a trigger (every kept row keeps its trigger state).

``cut_report`` says what a shorter plan would lose (motion, pauses / other commands, trigger windows), so the GUI
asks before cutting them.  The functions are pure: they return a new dataframe and never touch the input.
"""

import numpy as np
import pandas as pd

from fcn_plan.fcn_trigger import (plan_has_trigger, trg_cut_commands, trg_windows, strip_trigger,
                                  cell_has_trigger, trg_states, trg_normalise)

EXCLUDE_COLS = {'timestamp', 'time', 'Command'}
TIME_TOL = 1e-6


def plan_end(df):
    """Last time of the plan (s), 0.0 for an empty / missing plan."""
    if df is None or len(df) == 0 or 'time' not in df.columns:
        return 0.0
    v = pd.to_numeric(df['time'], errors='coerce').max()
    return 0.0 if pd.isna(v) else float(v)


def plan_step(df):
    """Row spacing as Create Curve reads it (time[1] - time[0], 0.001 when not usable)."""
    step = 0.001
    if df is not None and len(df) > 1:
        step = float(df['time'].iat[1] - df['time'].iat[0])
        if not step > 0:
            step = 0.001
    return step


def axis_columns(df):
    return [c for c in df.columns if c not in EXCLUDE_COLS and not str(c).startswith(('Vel.', 'Acc.'))]


def extend_plan(df, new_end):
    """Plan extended up to ``new_end`` (the same rows Create Curve appends when End Time is past the plan end).
    Returns a copy; unchanged (copy) when ``new_end`` is not past the plan end."""
    out = df.copy()
    t_max = plan_end(df)
    if new_end <= t_max:
        return out
    step = plan_step(df)
    new_t = np.arange(t_max + step, new_end + step / 2.0, step)
    # A trigger window that runs to the plan end keeps its old end: the explicit S0 stays on the old last row (as in
    # Create Curve's extension and Insert at the plan end), so the trigger is off during the added hold
    move_s0 = False
    if len(new_t) > 0:
        new_rows = pd.DataFrame({'timestamp': new_t * 1000.0, 'time': new_t})
        last_row = out.loc[out['time'].idxmax()]
        for col in axis_columns(out):
            last_val = pd.to_numeric(pd.Series([last_row[col]]), errors='coerce').iloc[0]
            new_rows[col] = 0.0 if pd.isna(last_val) else float(last_val)
        new_rows['Command'] = ""
        out = pd.concat([out, new_rows], ignore_index=True)
    if 'Command' not in out.columns:
        out['Command'] = ""
    if move_s0:
        out['Command'] = trg_normalise(list(out['Command']))
    drop =[c for c in out.columns if str(c).startswith(('Vel.', 'Acc.'))]
    if drop:
        out = out.drop(columns=drop)
    return out


def _cut_mask(df, new_end):
    t = pd.to_numeric(df['time'], errors='coerce').to_numpy(float)
    return t > new_end + TIME_TOL


def cut_report(df, new_end):
    """What cropping the plan to [0, new_end] would remove:
    {'motion': [axes that move after new_end], 'pauses': n commands other than trigger switches after new_end,
     'trigger': n trigger windows that end after new_end}.  All empty / 0 when only an idle tail is cut."""
    rep = {'motion': [], 'pauses': 0, 'trigger': 0}
    if df is None or len(df) == 0:
        return rep
    cut = _cut_mask(df, new_end)
    if not cut.any():
        return rep
    keep_idx = np.flatnonzero(~cut)
    ref = int(keep_idx[-1]) if len(keep_idx) else None
    for col in axis_columns(df):
        v = pd.to_numeric(df[col], errors='coerce').to_numpy(float)
        tail = v[cut]
        base = v[ref] if ref is not None else (tail[0] if len(tail) else 0.0)
        if len(tail) and np.nanmax(np.abs(tail - base)) > 1e-9:
            rep['motion'].append(col)
    if 'Command' in df.columns:
        cmds = df['Command'].tolist()
        n = 0
        for c, k in zip(cmds, cut):
            if k and isinstance(c, str) and c.strip():
                rest = strip_trigger(c) if cell_has_trigger(c) else c
                if isinstance(rest, str) and rest.strip():
                    n += 1
        rep['pauses'] = n
        if plan_has_trigger(cmds):
            t = pd.to_numeric(df['time'], errors='coerce').to_numpy(float)
            rep['trigger'] = sum(1 for _a, b in trg_windows(t, cmds) if b > new_end + TIME_TOL)
    return rep


def cut_report_text(rep):
    """Human-readable list of what would be lost ('' when nothing)."""
    parts = []
    if rep.get('motion'):
        parts.append("the motion of " + ", ".join(rep['motion']))
    if rep.get('pauses'):
        n = rep['pauses']
        parts.append(f"{n} pause{'s' if n != 1 else ''} / command{'s' if n != 1 else ''}")
    if rep.get('trigger'):
        n = rep['trigger']
        parts.append(f"{n} trigger window{'s' if n != 1 else ''} (cut or shortened)")
    return "; ".join(parts)


def crop_plan_end(df, new_end):
    """Plan cropped to [0, new_end] as the Crop dialog does (None when no row would be left)."""
    t_start = 0.0
    t_end = round(float(new_end), 3)
    out = df[(df['time'] >= t_start) & (df['time'] <= t_end)].copy()
    if len(out) == 0:
        return None
    min_t = out['time'].min()
    out['time'] = (out['time'] - min_t).round(3)
    out['timestamp'] = (out['time'] * 1000.0).round(1)
    out.reset_index(drop=True, inplace=True)
    if 'Command' in df.columns and plan_has_trigger(df['Command']):
        out['Command'] = trg_cut_commands(df['time'].to_numpy(float), df['Command'].tolist(), t_start, t_end, "crop")
    return out
