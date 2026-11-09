"""
Beam trigger for the Planning tab (Qt-free core).

The trigger is a 5 V output of the Duet, switched with ``M42 P<port> S1`` (on) and ``M42 P<port> S0`` (off) on
port TRIGGER_PORT.  It lives in the plan's Command column, next to the pauses (wait radiation / wait user).

Data model
----------
* State machine over the plan rows: off at the start; a cell's S1 switches it on, S0 off.  The state of row i
  holds from t[i] to t[i+1]; the last row holds no interval, so the state there is always OFF: a window that is
  still on at the second-to-last row is drawn to the plan end and CLOSED BY AN EXPLICIT S0 ON THE LAST ROW.  The
  window end is then part of the data: extending the plan with a new curve, Trim or Crop keep it (a pulse that ends
  at the plan end stays a pulse).  The G-code also switches the output off after the last move (``trg_safety_lines``).
* Every trigger operation reads the state per row (``trg_states``), changes it and writes it back as M42 commands
  at the transitions (``trg_write_states``: no redundant off).  The old M42 commands of the port are removed; other
  commands in the cells are never touched.
* Explicit window starts: an S1 in a cell where the trigger is already on is KEPT (``trg_write_states`` /
  ``trg_normalise``).  It is the start of a window the user set that an earlier Trigger On now runs into, or a Trigger
  On pressed while the trigger was already on (all Ons entered before the Offs): the state (plot, G-code) is on
  through it, but a later Trigger Off before it ends the earlier part only and that window keeps its start and end.
  In the G-code it is a repeated 'M42 P5 S1' (harmless: RRF queues it with the moves and the output is already on);
  the parser keeps it as a row (``output_state_changes``) so it survives an import.
* Manual buttons (``trg_switch_at``) place switch EVENTS, so windows can be entered in any order, also every On before
  the Offs: On puts an S1 at the row, also where the trigger is already on (an explicit window start), or, at the row
  where a window ends, removes that S0 (the window goes on); Off puts an S0 at the row and removes the S0 events up to
  the next S1, so it never deletes a window that starts later.  An Off right at a window start inside a run keeps it:
  the part before ends where that window starts (touching windows: one run, as in time order).
* Removing rows (Crop / Trim) must not change the state of the rows that stay: ``trg_keep_rows`` /
  ``trg_cut_commands`` rewrite the switches of the kept rows from their original states (an explicit start inside a
  removed block moves to the first kept row after it).
* A cell may hold several commands separated by ' ; ' (CMD_SEP, the G-code parser's join).
  Order inside a cell (``order_cell``): a trigger-ON runs BEFORE the waits, so the beam is on while waiting for
  radiation, and a trigger-OFF runs AFTER them.  A cell holds at most one switch per port (the last one wins).
* Times snap to the nearest plan row, like the waits: the resolution is the row spacing (``row_spacing``).

G-code
------
RRF queues M42 behind the moves scheduled before it (GCodeQueue::ShouldQueueMCode, case 42), so a switch written
between two G1 lines runs when the first move has completed, i.e. at its row time; after a G4 nothing is pending
and it runs at once.  fcn_gcode uses ``cell_has_output_command`` (plan commands), ``cell_gcode_lines`` (one line per
command), ``trg_safety_lines`` ('M42 P5 S0' at the start and the end) and ``output_state_changes`` (the parser drops
an S0 on an output that is already off, so the safety lines never create windows or rows; every S1 is kept).
"""
import re

import numpy as np

TRIGGER_PORT = 5
CMD_SEP = " ; "
WAIT_RAD_CMD = 'M98 P"0:macros/sensor_wait.g"'
WAIT_USER_CMD = "M226"

TRIGGER_COLOR = "#a5d6a7"       # light green cover of the trigger-on windows on the plot
TRIGGER_ALPHA = 0.3
TRIGGER_ROW_COLOR = "#c8e6c9"   # table rows holding a trigger switch
TRIGGER_LABEL = f"Trigger on (M42 P{TRIGGER_PORT})"

COMBINE_MODES = ("add", "replace", "intersect")
COMBINE_LABELS = {"add": "Add (union)", "replace": "Replace in range", "intersect": "Only where both"}
PERIODIC_ACTIONS = ("trigger_on", "beam_off", "wait_rad", "wait_user")
PERIODIC_LABELS = {"trigger_on": "Trigger on", "beam_off": "Trigger off", "wait_rad": "Wait radiation",
                   "wait_user": "Wait user"}

_EPS = 1e-9
MAX_PERIODIC_EVENTS = 100000


# ----------------------------------------------------------------------------
# M42 commands
# ----------------------------------------------------------------------------
_M42 = re.compile(r"^M0*42(?![\d.])(.*)$", re.IGNORECASE)
_PARAM = re.compile(r"([A-Za-z])\s*([-+]?(?:\d+\.\d*|\.\d+|\d+))")


def output_command(on, port=TRIGGER_PORT):
    """'M42 P<port> S1' (on) / 'M42 P<port> S0' (off)."""
    return f"M42 P{int(port)} S{1 if on else 0}"


TRIGGER_ON_CMD = output_command(True)
TRIGGER_OFF_CMD = output_command(False)


def parse_output_command(cmd):
    """(port, on) for one 'M42 P<port> S<0|1>' command (any parameter order, compact form, S1.0 accepted);
    None for anything else (other commands, PWM values, several commands)."""
    if not isinstance(cmd, str):
        return None
    m = _M42.match(cmd.strip())
    if not m:
        return None
    rest = m.group(1)
    if _PARAM.sub("", rest).strip():
        return None
    params = {}
    for key, val in _PARAM.findall(rest):
        key = key.upper()
        if key in params:
            return None
        params[key] = float(val)
    if set(params) != {"P", "S"}:
        return None
    port, s = params["P"], params["S"]
    if port < 0 or port != int(port) or s not in (0.0, 1.0):
        return None
    return int(port), s == 1.0


def output_comment(port, on):
    """Comment line written above an M42 in the G-code."""
    if int(port) == TRIGGER_PORT:
        return "; trigger on" if on else "; trigger off"
    return f"; output P{int(port)} {'on' if on else 'off'}"


# ----------------------------------------------------------------------------
# Multi-command cells
# ----------------------------------------------------------------------------
def split_cell(cell):
    """Commands of a Command cell: split at ';' outside double quotes, stripped, empty parts dropped."""
    if not isinstance(cell, str):
        return []
    if ";" not in cell:
        c = cell.strip()
        return [c] if c else []
    parts, buf, quoted = [], [], False
    for ch in cell:
        if ch == '"':
            quoted = not quoted
        if ch == ";" and not quoted:
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    parts.append("".join(buf))
    return [p.strip() for p in parts if p.strip()]


def join_cell(pieces):
    return CMD_SEP.join(p for p in pieces if p)


def order_cell(pieces):
    """Canonical order of a cell's commands: output switches ON first, then the other commands in their order,
    then the switches OFF (so the beam is on while a wait at that row runs).  One switch per port: the last."""
    parsed = [parse_output_command(p) for p in pieces]
    last = {}
    for i, o in enumerate(parsed):
        if o is not None:
            last[o[0]] = i
    ons, others, offs = [], [], []
    for i, (p, o) in enumerate(zip(pieces, parsed)):
        if o is None:
            others.append(p)
        elif last[o[0]] == i:
            (ons if o[1] else offs).append(output_command(o[1], o[0]))
    return ons + others + offs


def merge_cell(existing, cmd):
    """Appends the command(s) of ``cmd`` to a cell, keeping the order (used when importing G-code rows that land
    on the same plan row)."""
    pieces = split_cell(existing) + split_cell(cmd)
    return join_cell(pieces)


def add_cell_command(cell, cmd):
    """Adds ``cmd`` to a cell without touching the other commands (no duplicate), in the canonical order."""
    cmd = str(cmd).strip()
    pieces = split_cell(cell)
    if cmd and cmd not in pieces:
        pieces.append(cmd)
    return join_cell(order_cell(pieces))


def remove_cell_commands(cell, match):
    """Removes only the commands that contain the substring ``match`` (or satisfy the predicate ``match``);
    the other commands of the cell stay as they are.  Non-string cells are returned unchanged."""
    if not isinstance(cell, str):
        return cell
    pred = match if callable(match) else (lambda p: match in p)
    return join_cell([p for p in split_cell(cell) if not pred(p)])


def cell_has_output_command(cell):
    """True when the cell holds an 'M42 P<port> S<0|1>' (any port)."""
    if not isinstance(cell, str) or "42" not in cell:
        return False
    return any(parse_output_command(p) is not None for p in split_cell(cell))


def _is_port_switch(piece, port):
    o = parse_output_command(piece)
    return o is not None and o[0] == int(port)


def cell_has_trigger(cell, port=TRIGGER_PORT):
    """True when the cell holds a switch of the trigger port."""
    if not isinstance(cell, str) or "42" not in cell:
        return False
    return any(_is_port_switch(p, port) for p in split_cell(cell))


def cell_trigger_state(cell, port=TRIGGER_PORT):
    """State the cell leaves the trigger port in (True / False), None when it holds no switch of that port."""
    if not isinstance(cell, str) or "42" not in cell:
        return None
    state = None
    for p in split_cell(cell):
        o = parse_output_command(p)
        if o is not None and o[0] == int(port):
            state = o[1]
    return state


def strip_trigger(cell, port=TRIGGER_PORT):
    return remove_cell_commands(cell, lambda p: _is_port_switch(p, port))


# ----------------------------------------------------------------------------
# G-code helpers (used by fcn_gcode)
# ----------------------------------------------------------------------------
def cell_gcode_lines(cell, format_single, is_command):
    """G-code lines for a cell with several commands or an output switch: one line per command (canonical order),
    '; trigger on' / '; trigger off' above an M42, ``format_single`` for the other plan commands (non-commands are
    dropped, as before).  None for a cell with a single other command: the caller formats it as before."""
    pieces = split_cell(cell)
    if len(pieces) <= 1 and not any(parse_output_command(p) is not None for p in pieces):
        return None
    lines = []
    for p in order_cell(pieces):
        o = parse_output_command(p)
        if o is not None:
            lines.append(output_comment(o[0], o[1]))
            lines.append(output_command(o[1], o[0]))
        elif is_command(p):
            lines.extend(format_single(p))
    return lines


def plan_has_trigger(commands, port=TRIGGER_PORT):
    if commands is None:
        return False
    return any(cell_has_trigger(c, port) for c in commands)


def trg_safety_lines(commands, port=TRIGGER_PORT):
    """['; trigger safety off', 'M42 P5 S0'] when the plan holds any trigger switch, else [] (so G-code of plans
    without a trigger stays byte-identical).  Written after the header and after the last move / dwell."""
    if not plan_has_trigger(commands, port):
        return []
    return ["; trigger safety off", output_command(False, port)]


def output_state_changes(states, code):
    """For the G-code parser: False for an M42 S0 on an output that is already off (the start / end safety lines, a
    repeated S0); True otherwise (the new state is recorded in ``states``).  Every S1 counts, also one while the output
    is already on: that is an explicit window start (see the module notes) and must survive an import, so that a
    later Trigger Off before it still keeps that window."""
    o = parse_output_command(code)
    if o is None:
        return True
    port, on = o
    if not on and not states.get(port, False):
        return False
    states[port] = on
    return True


# ----------------------------------------------------------------------------
# Rows and time
# ----------------------------------------------------------------------------
def row_spacing(t):
    """Resolution of the plan: the median spacing of its rows (s)."""
    t = np.asarray(t, dtype=float)
    if len(t) < 2:
        return 0.0
    d = np.diff(t)
    d = d[d > 0]
    return float(np.median(d)) if len(d) else 0.0


def nearest_row(t, x):
    """Index of the row nearest to time x (ties: the earlier row, like np.argmin)."""
    t = np.asarray(t, dtype=float)
    n = len(t)
    if n == 0:
        raise ValueError("The plan is empty")
    i = int(np.searchsorted(t, x))
    if i <= 0:
        return 0
    if i >= n:
        return n - 1
    return i - 1 if abs(t[i - 1] - x) <= abs(t[i] - x) else i


def fmt_s(x):
    """Compact seconds for messages: 0.5, 2, 12.25."""
    s = f"{float(x):.3f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


# ----------------------------------------------------------------------------
# State machine
# ----------------------------------------------------------------------------
def _commands_list(commands):
    return list(commands) if commands is not None else []


def trg_states(commands, port=TRIGGER_PORT):
    """Boolean trigger state per row (state after the row's commands ran)."""
    cmds = _commands_list(commands)
    st = np.zeros(len(cmds), dtype=bool)
    cur = False
    for i, c in enumerate(cmds):
        if isinstance(c, str) and "42" in c:
            s = cell_trigger_state(c, port)
            if s is not None:
                cur = s
        st[i] = cur
    return st


def _normalised_states(states):
    """The last row holds no interval: its state is always off, so a window still on at the row before it gets an
    explicit S0 on the last row (its end stays put when rows are appended / removed later)."""
    st = np.array(states, dtype=bool, copy=True)
    if len(st):
        st[-1] = False
    return st


def _cell_on(cell, port=TRIGGER_PORT):
    """True when the cell switches the port on (an S1 event)."""
    return isinstance(cell, str) and "42" in cell and cell_trigger_state(cell, port) is True


def _explicit_starts(commands, port=TRIGGER_PORT):
    """Rows whose cell holds an S1 of the port (window starts, also those inside an on-run)."""
    return np.array([_cell_on(c, port) for c in _commands_list(commands)], dtype=bool)


def _set_port_switch(cell, on, port=TRIGGER_PORT):
    """The cell with its switch of the port set to S1 (True) / S0 (False) or removed (None); other commands kept."""
    pieces = [p for p in split_cell(cell) if not _is_port_switch(p, port)]
    if on is not None:
        pieces.append(output_command(on, port))
    return join_cell(order_cell(pieces))


def _write_states(commands, states, starts, port=TRIGGER_PORT):
    """Switches at the transitions of ``states``, plus an S1 at every row of ``starts`` (bool mask or None) where the
    trigger stays on (explicit window start).  Old switches of the port are replaced; other cells untouched."""
    out = _commands_list(commands)
    st = _normalised_states(states)
    if len(st) != len(out):
        raise ValueError("states and commands differ in length")
    prev = False
    for i in range(len(out)):
        c = out[i]
        cur = bool(st[i])
        if cur != prev:
            want = cur
        elif cur and starts is not None and starts[i]:
            want = True        # explicit start of a window inside an on-run: kept (see the module notes)
        else:
            want = None
        prev = cur
        if want is None and not cell_has_trigger(c, port):
            continue
        out[i] = _set_port_switch(c, want, port)
    return out


def trg_write_states(commands, states, port=TRIGGER_PORT, keep_starts=True):
    """Writes the states back as switches at the transitions (a window open at the plan end is closed by an S0 on the
    last row) and removes the other old switches of the port, except the explicit window starts: an S1 already in a
    cell where the trigger stays on is kept (``keep_starts``: True everywhere, False nowhere, or a row mask).
    Redundant S0 are dropped; cells without a switch and without a transition are returned untouched."""
    cmds = _commands_list(commands)
    if keep_starts is True:
        starts = _explicit_starts(cmds, port)
    elif keep_starts is False or keep_starts is None:
        starts = None
    else:
        keep_starts = np.asarray(keep_starts, dtype=bool)
        if len(keep_starts) != len(cmds):
            raise ValueError("keep_starts mask and commands differ in length")
        starts = _explicit_starts(cmds, port) & keep_starts
    return _write_states(cmds, states, starts, port)


def trg_normalise(commands, port=TRIGGER_PORT):
    """Canonical switches of the plan: the transitions plus the explicit window starts (the windows do not change;
    an S1 already present is never duplicated, so export -> import -> export keeps the same M42 lines)."""
    return trg_write_states(commands, trg_states(commands, port), port)


def trg_keep_rows(commands, keep, port=TRIGGER_PORT):
    """Commands of the rows where ``keep`` is True, rewritten so that every kept row keeps the trigger state it had
    in the full plan (removing a row that held a switch must not change the rows after it).  A window open where a
    cut starts / ends gets a switch at the new boundary; an explicit window start (S1) inside a removed block moves
    to the first kept row after it (kept when the trigger is on there); other commands are kept as they are."""
    cmds = _commands_list(commands)
    keep = np.asarray(keep, dtype=bool)
    if len(keep) != len(cmds):
        raise ValueError("keep mask and commands differ in length")
    S = trg_states(cmds, port)
    E = _explicit_starts(cmds, port)
    kept, starts, pending = [], [], False
    for c, k, e in zip(cmds, keep, E):
        if k:
            kept.append(c)
            starts.append(bool(e) or pending)
            pending = False
        else:
            pending = pending or bool(e)
    return _write_states(kept, S[keep], np.asarray(starts, dtype=bool), port)


def trg_cut_commands(t, commands, t_start, t_end, mode, port=TRIGGER_PORT):
    """Command column after Crop (mode 'crop': keeps t_start <= t <= t_end) or Trim (otherwise: removes that interval),
    with the same row selection as CropTrimDialog, the trigger state of each kept row preserved (``trg_keep_rows``)."""
    t = np.asarray(t, dtype=float)
    if mode == "crop":
        keep = (t >= t_start) & (t <= t_end)
    else:
        keep = (t < t_start) | (t > t_end)
    return trg_keep_rows(commands, keep, port)


def trg_windows_from_states(t, states):
    """[(t_on, t_off)] of the runs where the state is on (row i covers t[i]..t[i+1])."""
    t = np.asarray(t, dtype=float)
    st = np.asarray(states, dtype=bool)
    n = len(t)
    if n < 2 or len(st) != n:
        return []
    on = st[:-1].astype(np.int8)
    d = np.diff(np.concatenate(([0], on, [0])))
    starts = np.flatnonzero(d == 1)
    ends = np.flatnonzero(d == -1)
    return [(float(t[a]), float(t[b])) for a, b in zip(starts, ends) if t[b] > t[a]]


def trg_windows(t, commands, port=TRIGGER_PORT):
    """Trigger-on windows [(t_on, t_off)] of a plan (or of parsed G-code rows)."""
    return trg_windows_from_states(t, trg_states(commands, port))


def trg_events(t, commands, port=TRIGGER_PORT):
    """[(time, on)] of the trigger switches in the cells, in row order (as written to the G-code)."""
    t = np.asarray(t, dtype=float)
    out = []
    for i, c in enumerate(_commands_list(commands)):
        if isinstance(c, str) and "42" in c:
            s = cell_trigger_state(c, port)
            if s is not None:
                out.append((float(t[i]), bool(s)))
    return out


def trg_inner_starts(t, commands, port=TRIGGER_PORT):
    """Times of the explicit window starts inside an on-run (an S1 while the trigger is already on: a window the user
    set that an earlier Trigger On runs into, or a Trigger On pressed inside a run).  The plot marks them; the G-code
    holds them as a repeated S1."""
    t = np.asarray(t, dtype=float)
    cmds = _commands_list(commands)
    if len(cmds) != len(t):
        return []
    S = _normalised_states(trg_states(cmds, port))
    return [float(t[i]) for i in range(1, len(cmds)) if S[i - 1] and S[i] and _cell_on(cmds[i], port)]


def trg_on_time(windows):
    return float(sum(b - a for a, b in windows))


def trg_describe(windows):
    if not windows:
        return "no trigger window"
    n = len(windows)
    return f"{n} window{'s' if n != 1 else ''}, {trg_on_time(windows):.2f} s on in total"


def trg_resolve_range(t, rng=None):
    """(r0, r1) of the range: the whole plan for None, else validated to lie inside the plan."""
    t = np.asarray(t, dtype=float)
    if len(t) < 2:
        raise ValueError("The plan has fewer than 2 rows")
    t0, t1 = float(t[0]), float(t[-1])
    if rng is None:
        return t0, t1
    r0, r1 = float(rng[0]), float(rng[1])
    if r1 <= r0 + _EPS:
        raise ValueError(f"Range end ({fmt_s(r1)} s) must be after its start ({fmt_s(r0)} s)")
    tol = max(1e-6, 0.5 * row_spacing(t))
    if r0 < t0 - tol or r1 > t1 + tol:
        raise ValueError(f"Range {fmt_s(r0)}-{fmt_s(r1)} s is outside the plan ({fmt_s(t0)}-{fmt_s(t1)} s)")
    return max(r0, t0), min(r1, t1)


def trg_range_mask(t, rng=None):
    """Rows whose interval lies in the range (snapped to the nearest rows)."""
    t = np.asarray(t, dtype=float)
    n = len(t)
    R = np.zeros(n, dtype=bool)
    if n < 2:
        return R
    r0, r1 = trg_resolve_range(t, rng)
    a, b = nearest_row(t, r0), nearest_row(t, r1)
    R[a:b] = True
    return R


def trg_window_mask(t, windows):
    """(mask, n_dropped): rows covered by the windows, each snapped to the nearest rows; windows shorter than half a
    row spacing vanish and are counted in n_dropped."""
    t = np.asarray(t, dtype=float)
    M = np.zeros(len(t), dtype=bool)
    dropped = 0
    for s, e in windows:
        a, b = nearest_row(t, s), nearest_row(t, e)
        if b > a:
            M[a:b] = True
        else:
            dropped += 1
    return M, dropped


def trg_combine(S, M, R, mode):
    """New states from the existing S, the new pattern M and the range R:
    add = S or M; replace = M inside the range, S outside; intersect = S and M inside the range, S outside;
    subtract = S and not M (beam off)."""
    S = np.asarray(S, dtype=bool)
    MR = np.asarray(M, dtype=bool) & np.asarray(R, dtype=bool)
    R = np.asarray(R, dtype=bool)
    if mode == "add":
        return S | MR
    if mode == "replace":
        return (S & ~R) | MR
    if mode == "intersect":
        return (S & ~R) | (S & MR)
    if mode == "subtract":
        return S & ~MR
    raise ValueError(f"Unknown combine mode {mode!r}")


def _starts_kept(R, mode):
    """Rows whose explicit window starts survive a combine: 'replace' drops them inside its range (the windows there
    are the new pattern only); add / intersect / subtract keep them (the on-rows left are parts of those windows)."""
    return ~np.asarray(R, dtype=bool) if mode == "replace" else True


# ----------------------------------------------------------------------------
# Manual switches
# ----------------------------------------------------------------------------
def _window_at(windows, x):
    for a, b in windows:
        if a - _EPS <= x <= b + _EPS:
            return a, b
    return None


def _next_start(cmds, i, port=TRIGGER_PORT):
    """First row after i whose cell holds an S1 of the port (the next explicit window start), or None."""
    for j in range(i + 1, len(cmds)):
        if _cell_on(cmds[j], port):
            return j
    return None


def trg_switch_at(t, commands, time, on, port=TRIGGER_PORT):
    """Trigger On / Off at the row nearest to ``time``.  The buttons place switch EVENTS, so the windows can be entered
    in any order, also every On before the Offs: for windows that do not overlap (each at least one row long; touching
    is allowed), every press order in which each window's On comes before its Off gives the windows of the same presses
    in time order.

    * On, trigger off at the row: an S1 there; at the row where a window ends (its S0) that S0 is removed instead and
      the window goes on (info['extended']).  The trigger then stays on up to the next S0.  A window that starts before
      that keeps its own S1 (an explicit start inside the run, a repeated S1 in the G-code): the plot shows one run, as
      the G-code runs it, and info['merged_into'] is that window's start time (the message says so) until an Off ends it.
    * On, trigger already on at the row (inside a run, e.g. an earlier On whose Off is still to come): an explicit window
      start (S1) is placed there (info['inner_start']).  The run does not change, but a Trigger Off before that row now
      ends only the earlier part and one after it ends this window.  Nothing changes when the row already holds an S1.
    * Off, trigger on at the row: an S0 there, and the S0 events up to the next S1 removed: the trigger is off from the
      row up to the next window start, never past it, so windows that start later keep their start and end
      (info['kept_window']).  An Off at the start of a run removes that window (up to the next start).
    * Off right at an explicit window start inside a run (the row holds an S1, the trigger is on before it): the earlier
      part ends exactly where that later window starts, so they touch and the trigger stays on: one joined run, as the
      same presses in time order give (info['joined_at']; that S1 is removed, so the cells equal the time-order presses
      and an Off on the row of a mistaken On cancels it).

    Returns (new_commands, info); info['changed'] is False (and info['message'] says why) for On where a window already
    starts, Off outside a window, or a switch at the plan end."""
    t = np.asarray(t, dtype=float)
    n = len(t)
    cmds = _commands_list(commands)
    if n < 2:
        return cmds, {"changed": False, "message": "The plan has fewer than 2 rows."}
    if len(cmds) != n:
        raise ValueError("time and commands differ in length")
    i = nearest_row(t, time)
    ti = float(t[i])
    S = _normalised_states(trg_states(cmds, port))
    before = trg_windows_from_states(t, S)
    info = {"changed": False, "row": i, "time": ti, "windows_before": before, "merged_into": None,
            "extended": False, "inner_start": None, "joined_at": None, "kept_window": None}
    new = list(cmds)
    kept_row = None
    if on:
        if i >= n - 1:
            info["message"] = f"Trigger On at {ti:.3f} s is the plan end: nothing left to switch on."
            return cmds, info
        if S[i]:
            if _cell_on(cmds[i], port):
                w = _window_at(before, ti)
                info["message"] = (f"A window already starts at {ti:.3f} s"
                                   + (f" (on {w[0]:.3f}-{w[1]:.3f} s)" if w else "") + ": nothing changed.")
                return cmds, info
            new[i] = _set_port_switch(new[i], True, port)   # explicit window start inside the run (an event)
            info["inner_start"] = ti
        elif i > 0 and S[i - 1]:        # the row where a window ends: its S0 goes, the window goes on
            new[i] = _set_port_switch(new[i], None, port)
            info["extended"] = True
        else:
            new[i] = _set_port_switch(new[i], True, port)
    else:
        if i >= n - 1 and S[n - 2]:
            info["message"] = f"The window already ends at the plan end ({ti:.3f} s): nothing changed."
            return cmds, info
        if not S[i]:
            info["message"] = f"Trigger is not on at {ti:.3f} s (outside every window): nothing changed."
            return cmds, info
        if i > 0 and S[i - 1] and _cell_on(cmds[i], port):
            # an explicit window start right here inside the run: the earlier part ends where it starts (they touch).
            # That S1 is removed: the trigger stays on (one run, the same cells as these presses in time order), and an
            # Off on the row of a mistaken On (or a zero-length window inside a run) cancels it instead of leaving the
            # trigger on to the next S0
            w = _window_at(before, ti)
            info["joined_at"] = ti
            new[i] = _set_port_switch(new[i], None, port)
            new = trg_normalise(new, port)
            after = trg_windows_from_states(t, _normalised_states(trg_states(new, port)))
            info.update(changed=True, windows=after)
            info["message"] = (f"Trigger off at {ti:.3f} s: the window start at {ti:.3f} s removed; the parts before and "
                               f"after it touch: one run" + (f" {w[0]:.3f}-{w[1]:.3f} s" if w else "")
                               + f" ({trg_describe(after)}).")
            return new, info
        j = _next_start(new, i, port)
        for k in range(i + 1, j if j is not None else n):
            if cell_has_trigger(new[k], port):
                new[k] = _set_port_switch(new[k], None, port)     # the S0 ending this run: replaced by the Off at i
        new[i] = _set_port_switch(new[i], False, port)
        if j is not None and S[j - 1]:
            kept_row = j                # the run went on into a later window: that window starts there again
    new = trg_normalise(new, port)
    S2 = _normalised_states(trg_states(new, port))
    after = trg_windows_from_states(t, S2)
    desc = trg_describe(after)
    info.update(changed=True, windows=after)
    if on:
        w = _window_at(after, ti)
        e = i
        while e < n and S2[e]:
            e += 1
        m = next((k for k in range(i + 1, e) if _cell_on(new[k], port)), None)
        tm = float(t[m]) if m is not None else None
        info["merged_into"] = tm
        if info["inner_start"] is not None:
            until = f", on until the window at {tm:.3f} s starts" if m is not None else ""
            info["message"] = (f"Trigger on at {ti:.3f} s: window start placed inside the run {w[0]:.3f}-{w[1]:.3f} s "
                               f"(the trigger is already on there; dotted mark{until}). A Trigger Off before "
                               f"{ti:.3f} s ends only the earlier part ({desc}).")
        elif m is not None:
            what = f"window from {w[0]:.3f} s extended, " if info["extended"] else ""
            info["message"] = (f"Trigger on at {ti:.3f} s: {what}on until the window at {tm:.3f} s starts; press "
                               f"Trigger Off to end it earlier (shown: {w[0]:.3f}-{w[1]:.3f} s; {desc}).")
        else:
            info["message"] = (f"Trigger on at {ti:.3f} s: window {w[0]:.3f}-{w[1]:.3f} s ("
                               + ("extended; " if info["extended"] else "") + f"{desc}).")
    else:
        kept = ""
        if kept_row is not None:
            wk = _window_at(after, float(t[kept_row]))
            if wk is not None:
                info["kept_window"] = wk
                kept = f"; the window {wk[0]:.3f}-{wk[1]:.3f} s is kept"
        w = [ab for ab in after if abs(ab[1] - ti) <= _EPS]
        if w:
            info["message"] = f"Trigger off at {ti:.3f} s: window {w[0][0]:.3f}-{w[0][1]:.3f} s{kept} ({desc})."
        else:
            info["message"] = f"Trigger off at {ti:.3f} s: window removed{kept} ({desc})."
    return new, info


def trg_clear(commands, port=TRIGGER_PORT):
    """Removes every switch of the trigger port; returns (new_commands, n_switches_removed)."""
    out = _commands_list(commands)
    removed = 0
    for i, c in enumerate(out):
        if cell_has_trigger(c, port):
            removed += sum(1 for p in split_cell(c) if _is_port_switch(p, port))
            out[i] = strip_trigger(c, port)
    return out, removed


# ----------------------------------------------------------------------------
# Periodic patterns
# ----------------------------------------------------------------------------
def trg_periodic_starts(r0, r1, period, offset=0.0):
    """Event times r0 + offset + k * period that lie before the range end r1."""
    period = float(period)
    offset = float(offset)
    if not period > 0.0:
        raise ValueError("Period must be greater than 0 s")
    if offset < 0.0:
        raise ValueError("First-event offset must not be negative")
    span = float(r1) - float(r0) - offset
    if span <= _EPS:
        raise ValueError(f"The first event ({fmt_s(r0 + offset)} s) is not before the range end ({fmt_s(r1)} s)")
    count = int(np.ceil(span / period - 1e-9))
    if count > MAX_PERIODIC_EVENTS:
        raise ValueError(f"{count} events: too many (period too short for the range)")
    return [float(r0) + offset + k * period for k in range(max(count, 1))]


def trg_periodic_windows(r0, r1, period, duration, offset=0.0):
    """[(start, end)] of the periodic windows, the last one clipped to the range end."""
    duration = float(duration)
    if not duration > 0.0:
        raise ValueError("Duration must be greater than 0 s")
    if duration > float(period) + _EPS:
        raise ValueError(f"Duration ({fmt_s(duration)} s) must not exceed the period ({fmt_s(period)} s)")
    return [(s, min(s + duration, float(r1))) for s in trg_periodic_starts(r0, r1, period, offset)]


def _check_resolution(t, period):
    dt = row_spacing(t)
    if dt > 0 and float(period) < dt - _EPS:
        raise ValueError(f"Period {fmt_s(period)} s is below the row spacing ({fmt_s(dt)} s)")
    return dt


def trg_periodic_preview(t, period, duration=0.0, offset=0.0, rng=None, action="trigger_on"):
    """What a periodic Apply would place, for the plot preview: {'windows': [...]} for trigger_on / beam_off (snapped),
    {'events': [row times]} for the waits.  Raises ValueError for invalid parameters."""
    t = np.asarray(t, dtype=float)
    r0, r1 = trg_resolve_range(t, rng)
    _check_resolution(t, period)
    if action in ("trigger_on", "beam_off"):
        M, _ = trg_window_mask(t, trg_periodic_windows(r0, r1, period, duration, offset))
        return {"windows": trg_windows_from_states(t, M)}
    starts = trg_periodic_starts(r0, r1, period, offset)
    rows = sorted({nearest_row(t, s) for s in starts})
    return {"events": [float(t[i]) for i in rows]}


def trg_apply_periodic(t, commands, action, period, duration=0.0, offset=0.0, rng=None, combine="add",
                       port=TRIGGER_PORT):
    """Applies a periodic pattern.  action: 'trigger_on' (on for ``duration`` at every event, joined with the
    existing windows by ``combine``), 'beam_off' (off for ``duration`` at every event), 'wait_rad' / 'wait_user' (the
    pause command added to the cell of every event).  Returns (new_commands, summary) with summary['text'];
    raises ValueError with a clear message for invalid input."""
    t = np.asarray(t, dtype=float)
    cmds = _commands_list(commands)
    if len(cmds) != len(t):
        raise ValueError("time and commands differ in length")
    if action not in PERIODIC_ACTIONS:
        raise ValueError(f"Unknown action {action!r}")
    r0, r1 = trg_resolve_range(t, rng)
    dt = _check_resolution(t, period)
    rng_txt = f"every {fmt_s(period)} s from {fmt_s(r0)} to {fmt_s(r1)} s"
    summary = {"action": action, "period": float(period), "offset": float(offset), "range": (r0, r1),
               "row_spacing": dt}

    if action in ("trigger_on", "beam_off"):
        if combine not in COMBINE_MODES:
            raise ValueError(f"Unknown combine mode {combine!r}")
        wins = trg_periodic_windows(r0, r1, period, duration, offset)
        M, dropped = trg_window_mask(t, wins)
        kept = len(wins) - dropped
        if kept == 0:
            raise ValueError(f"Duration {fmt_s(duration)} s is below the row resolution ({fmt_s(dt)} s): "
                             f"no window would remain")
        # Gaps between consecutive windows that snap to the same row vanish: those windows join (D == P joins them
        # on purpose, no message).  Counted on the pattern alone: kept windows minus the runs they form.
        gap = float(period) - float(duration)
        merged = max(0, kept - len(trg_windows_from_states(t, M))) if gap > _EPS else 0
        R = trg_range_mask(t, (r0, r1))
        S = trg_states(cmds, port)
        mode = "subtract" if action == "beam_off" else combine
        S2 = trg_combine(S, M, R, mode)
        new = trg_write_states(cmds, S2, port, keep_starts=_starts_kept(R, mode))
        after = trg_windows_from_states(t, _normalised_states(S2))
        what = "windows" if action == "trigger_on" else "trigger-off gaps"
        text = f"{kept} {what} of {fmt_s(duration)} s {rng_txt}"
        if action == "trigger_on" and combine != "add":
            text += f" ({COMBINE_LABELS[combine].lower()})"
        if dropped:
            text += f"; {dropped} below the row resolution ({fmt_s(dt)} s) skipped"
        if merged:
            stays = "on" if action == "trigger_on" else "off"
            text += (f"; {merged} {'off' if action == 'trigger_on' else 'on'} gap{'s' if merged != 1 else ''} of "
                     f"{fmt_s(gap)} s below the row resolution ({fmt_s(dt)} s) merged (the trigger stays {stays} there)")
        text += f". Result: {trg_describe(after)}."
        summary.update(n_events=len(wins), n_kept=kept, n_dropped=dropped, n_merged=merged, duration=float(duration),
                       windows=after, text=text, warning=bool(dropped or merged))
        return new, summary

    cmd = WAIT_RAD_CMD if action == "wait_rad" else WAIT_USER_CMD
    present_test = (lambda p: "sensor_wait" in p.lower()) if action == "wait_rad" else (lambda p: "M226" in p.upper())
    starts = trg_periodic_starts(r0, r1, period, offset)
    rows = sorted({nearest_row(t, s) for s in starts})
    added = present = 0
    for i in rows:
        if any(present_test(p) for p in split_cell(cmds[i])):
            present += 1
            continue
        cmds[i] = add_cell_command(cmds[i], cmd)
        added += 1
    name = "Wait Radiation" if action == "wait_rad" else "Wait User"
    text = f"{added} {name} pause{'s' if added != 1 else ''} {rng_txt}"
    if present:
        text += f" ({present} already present)"
    summary.update(n_events=len(rows), n_added=added, n_present=present, events=[float(t[i]) for i in rows],
                   text=text + ".")
    return cmds, summary


# ----------------------------------------------------------------------------
# Position-gated trigger
# ----------------------------------------------------------------------------
def trg_gate_mask(values, limits, flip=False):
    """Rows where every used axis lies inside its [Min, Max] (AND), inverted with ``flip``.
    values: {axis: array}; limits: {axis: (min, max)} of the USED axes only (the others are ignored)."""
    if not limits:
        raise ValueError("Select at least one axis ('Use')")
    n = None
    mask = None
    for ax, (lo, hi) in limits.items():
        lo, hi = float(lo), float(hi)
        if lo > hi:
            raise ValueError(f"{ax}: Min ({lo:g}) must not be greater than Max ({hi:g})")
        if ax not in values:
            raise ValueError(f"Axis {ax} is not in the plan")
        v = np.asarray(values[ax], dtype=float)
        if n is None:
            n = len(v)
            mask = np.ones(n, dtype=bool)
        elif len(v) != n:
            raise ValueError("Axis arrays differ in length")
        tol = 1e-9 * max(1.0, abs(lo), abs(hi))
        mask &= (v >= lo - tol) & (v <= hi + tol)
    return ~mask if flip else mask


def trg_gate_preview(t, values, limits, flip=False, rng=None):
    """Windows where the gated condition (with flip, inside the range) would switch the trigger on."""
    G = trg_gate_mask(values, limits, flip) & trg_range_mask(t, rng)
    return trg_windows_from_states(t, G)


def trg_apply_gate(t, commands, values, limits, flip=False, rng=None, combine="add", port=TRIGGER_PORT):
    """Applies the position-gated condition (evaluated on the plan rows) inside the range, joined with the
    existing windows by ``combine``.  Returns (new_commands, summary) with summary['text']."""
    t = np.asarray(t, dtype=float)
    cmds = _commands_list(commands)
    if len(cmds) != len(t):
        raise ValueError("time and commands differ in length")
    if combine not in COMBINE_MODES:
        raise ValueError(f"Unknown combine mode {combine!r}")
    r0, r1 = trg_resolve_range(t, rng)
    R = trg_range_mask(t, (r0, r1))
    G = trg_gate_mask(values, limits, flip) & R
    S = trg_states(cmds, port)
    S2 = trg_combine(S, G, R, combine)
    new = trg_write_states(cmds, S2, port, keep_starts=_starts_kept(R, combine))
    gate_w = trg_windows_from_states(t, G)
    after = trg_windows_from_states(t, _normalised_states(S2))
    axes = ", ".join(f"{a} {lo:g}..{hi:g}" for a, (lo, hi) in limits.items())
    text = (f"Margins {axes}{' (flipped)' if flip else ''} from {fmt_s(r0)} to {fmt_s(r1)} s: "
            f"{trg_describe(gate_w)}")
    if combine != "add":
        text += f" ({COMBINE_LABELS[combine].lower()})"
    text += f". Result: {trg_describe(after)}."
    return new, {"gate_windows": gate_w, "windows": after, "range": (r0, r1), "text": text}


# ----------------------------------------------------------------------------
# Window edits (right-click on a green window in the Planning plot; new functions, the ones above are unchanged)
# ----------------------------------------------------------------------------
def trg_runs(commands, port=TRIGGER_PORT):
    """[(a, b)] row indices of the on-runs (rows a..b-1 on, row b the first off row), the runs trg_windows reports."""
    S = _normalised_states(trg_states(commands, port))
    out, a = [], None
    for i, s in enumerate(S):
        if s and a is None:
            a = i
        elif not s and a is not None:
            out.append((a, i))
            a = None
    return out


def trg_run_at(t, commands, x, tol=0.0, port=TRIGGER_PORT):
    """(a, b) of the on-run whose span t[a]..t[b] contains time x (edges widened by ``tol`` seconds), or None.
    Inside a run wins over a neighbour's widened edge."""
    t = np.asarray(t, dtype=float)
    runs = trg_runs(commands, port)
    for a, b in runs:
        if t[a] - _EPS <= x <= t[b] + _EPS:
            return a, b
    best = None
    for a, b in runs:
        d = min(abs(x - t[a]), abs(x - t[b]))
        if d <= tol + _EPS and (best is None or d < best[0]):
            best = (d, (a, b))
    return best[1] if best else None


def _run_keep_mask(n, a, b):
    keep = np.ones(n, dtype=bool)
    keep[a:b + 1] = False
    return keep


def trg_delete_window(t, commands, a, b, port=TRIGGER_PORT):
    """The trigger off over the run a..b (rows a..b-1): its S1 / S0 and the explicit window starts inside it removed,
    the other windows and every other command (waits) kept.  Returns (new_commands, info)."""
    t = np.asarray(t, dtype=float)
    cmds = _commands_list(commands)
    n = len(cmds)
    if len(t) != n:
        raise ValueError("time and commands differ in length")
    S = _normalised_states(trg_states(cmds, port))
    if not (0 <= a < b < n) or not S[a:b].all():
        raise ValueError("no trigger window at these rows")
    S[a:b] = False
    new = trg_write_states(cmds, S, port, keep_starts=_run_keep_mask(n, a, b))
    after = trg_windows(t, new, port)
    return new, {"changed": True, "removed": (float(t[a]), float(t[b])), "windows": after,
                 "message": f"Trigger window {t[a]:.3f}-{t[b]:.3f} s deleted ({trg_describe(after)})."}


def trg_set_window(t, commands, a, b, start, end, port=TRIGGER_PORT):
    """Moves / resizes the run a..b to start..end (snapped to the nearest rows, as the Trigger On / Off buttons do):
    the old run is removed (with its inner window starts) and the trigger is on from the start row to the end row.
    A window it overlaps or touches joins it (one run; the window starts swallowed are removed, info['joined'] lists
    the windows it joined).  ValueError when start / end lie outside the plan or the window is shorter than a row.
    Returns (new_commands, info)."""
    t = np.asarray(t, dtype=float)
    cmds = _commands_list(commands)
    n = len(cmds)
    if len(t) != n or n < 2:
        raise ValueError("time and commands differ in length")
    start, end = float(start), float(end)
    if start < t[0] - _EPS or end > t[-1] + _EPS:
        raise ValueError(f"the window must lie inside the plan ({t[0]:.3f}-{t[-1]:.3f} s)")
    if not end > start:
        raise ValueError("the end must be after the start")
    i, j = nearest_row(t, start), nearest_row(t, end)
    if j <= i:
        raise ValueError(f"{start:.3f}-{end:.3f} s is shorter than one plan row ({row_spacing(t):.3f} s)")
    S = _normalised_states(trg_states(cmds, port))
    if not (0 <= a < b < n) or not S[a:b].all():
        raise ValueError("no trigger window at these rows")
    S[a:b] = False
    keep = _run_keep_mask(n, a, b)
    others = trg_windows_from_states(t, S)
    joined = [w for w in others if w[0] <= t[j] + _EPS and w[1] >= t[i] - _EPS]
    S[i:j] = True
    keep[i:j + 1] = False
    new = trg_write_states(cmds, S, port, keep_starts=keep)
    after = trg_windows(t, new, port)
    run = _window_at(after, float(t[i]))
    msg = f"Trigger window {t[a]:.3f}-{t[b]:.3f} s moved to {t[i]:.3f}-{t[j]:.3f} s"
    if joined:
        msg += (" and joined with " + ", ".join(f"{p:.3f}-{q:.3f} s" for p, q in joined)
                + (f": one window {run[0]:.3f}-{run[1]:.3f} s" if run else ""))
    msg += f" ({trg_describe(after)})."
    return new, {"changed": True, "window": (float(t[i]), float(t[j])), "run": run, "joined": joined,
                 "windows": after, "message": msg}


def trg_remove_inner_start(t, commands, x, port=TRIGGER_PORT):
    """Removes the explicit window start (dotted mark, an S1 inside an on-run) at the row nearest to x; the run does not
    change (a later Trigger Off then ends the whole run).  Returns (new_commands, info); info['changed'] False when that
    row holds no inner start."""
    t = np.asarray(t, dtype=float)
    cmds = _commands_list(commands)
    i = nearest_row(t, x)
    S = _normalised_states(trg_states(cmds, port))
    if not (0 < i < len(cmds) and S[i - 1] and S[i] and _cell_on(cmds[i], port)):
        return cmds, {"changed": False, "message": f"No window start mark at {t[i]:.3f} s: nothing changed."}
    keep = np.ones(len(cmds), dtype=bool)
    keep[i] = False
    new = trg_write_states(cmds, S, port, keep_starts=keep)
    return new, {"changed": True, "message": f"Window start mark at {t[i]:.3f} s removed; the run is unchanged."}
