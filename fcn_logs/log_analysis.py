"""
Analysis core of the TRACE "Log files" tab (pure Python: numpy / pandas / scipy, no Qt).

Reads TRACE position logs (every format written so far: v2 with ';' columns and a decimal comma,
v1 with ',' columns, and the tab's own exports in both styles) and reference G-code files into
``Curve`` objects, and provides the numerical tools the tab is built on: resampling, time
shift estimation (cross-correlation), log-vs-reference comparison, ensemble error bands,
peak / period detection, movement detection (start, stop, time until it stops) and the numbers
of a movement set by hand (movement_stats), value crossings (nearest_crossing), the logged
sensor waits of a log (meta['waits'], read from its notes and its Probe -1000 rows; never
estimated): their removal from the time axis (remove_waits / CutMap) and their pairing with the
G-code pauses (pair_pause_waits), and CSV export helpers (v2 style: ';' and a decimal comma).

Conventions
-----------
* Every curve has its own time base ``t`` (s, strictly increasing).  A curve can be moved in
  time with ``time_offset`` and per axis in value with ``value_offsets``; ``times()`` and
  ``values(axis)`` return the data with those offsets applied, and every analysis function
  works on that offset ("displayed") time base, ROIs included.
* Positions in logs are a staircase: the Duet refreshes machinePosition at most every ~200 ms,
  so consecutive rows often repeat.  Between samples a curve is linear (``np.interp``).
* Axis names: platform DOF 'LAT','SI','AP' (mm), 'Roll','Pitch','Yaw' (deg); raw platform
  actuators 'A','B','C','D',"'e","'f","'a","'c" (mm); lung phantom 'X','Y','Z' (mm).
  Requested positions from the ``Cmd_*`` columns of the 5/6 Nov logs are 'Cmd <axis>'.
* Logged sensor waits (sensor_wait.g): the log marks the rows of a wait with Probe -1000 and
  notes its timing ('# Wait start: ... received at T s (Duet sent it between A and T s)',
  '# Wait end: <what> at T s (<how>)').  A log without them is shown exactly as recorded.
"""

from __future__ import annotations

from fcn_logs.product_names import canonical_device  # DYNAMIQ / KINETIQ in the log header
import csv
import io
import math
import os
import re
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy import signal

PLATFORM_DOF = ['LAT', 'SI', 'AP', 'Roll', 'Pitch', 'Yaw']
PLATFORM_RAW = ['A', 'B', 'C', 'D', "'e", "'f", "'a", "'c"]
PHANTOM_AXES = ['X', 'Y', 'Z']
AXIS_ORDER = PLATFORM_DOF + PLATFORM_RAW + PHANTOM_AXES

CMD_PREFIX = 'Cmd '
PROBE_RELEASE_MIN = 1500          # Probe >= this value marks the Release button (logged as 2000)
PROBE_WAIT = -1000                # Probe value of the rows logged while sensor_wait.g waits
SENSOR_WAIT_THRESHOLD = 500       # sensor_wait.g waits while the detector is at or below this value
SENSOR_WAIT_LABEL = 'sensor_wait'  # pause label of fcn_plan.fcn_gcode for a sensor_wait.g call
_DEG_AXES = ('Roll', 'Pitch', 'Yaw')
_MAX_GRID = 2_000_000             # uniform grids are coarsened beyond this many points
_EPS_T = 1e-9                     # s, time tolerance
_NOTE_ROUND = 0.0005              # s, rounding of the 3-decimal times in the notes (rows have 4 decimals)

# aligned export of the Log files tab: 'time [s]' and one '<axis>: <curve> [<unit>]' column per curve
_EXPORT_TIME_COL = 'time [s]'
_EXPORT_COL_RE = re.compile(r'^(?P<axis>[^:]+?)\s*:\s*(?P<curve>.*?)\s*\[(?P<unit>[^\[\]]*)\]$')

# RRF axis letters accepted from a G-code timeline (quoted lowercase letters are also axes)
_GCODE_AXIS_LETTERS = set('XYZUVWABCD')

_META_DEFAULTS = {
    'computer_time': None,
    'gcode': None,
    'device': None,
    'axes': None,
    'end': None,
    'gaps': [],
    'pauses': [],
    'format': None,
    'all_zero_axes': [],
    'n': None,
    'median_dt': None,
    'units': {},
    'waits': [],
    'waits_not_marked': [],
    'message_read_failures': [],
}


def _copy_default(v):
    return list(v) if isinstance(v, list) else (dict(v) if isinstance(v, dict) else v)


def axis_unit(axis, curve=None):
    """Unit of an axis.  With curve (a Curve, or its meta dict): the unit its reader recorded for
    that axis (meta['units'], e.g. 'deg' for a 'Roll ...' column of an aligned export read back),
    when there is one.  Otherwise by name: 'deg' for Roll/Pitch/Yaw (also 'Cmd Roll' ...), 'mm'
    for every other axis."""
    if curve is not None:
        meta = curve if isinstance(curve, dict) else getattr(curve, 'meta', None)
        units = meta.get('units') if isinstance(meta, dict) else None
        if isinstance(units, dict):
            try:
                u = units.get(axis)
            except TypeError:                   # unhashable axis argument
                u = None
            if u is None:
                u = units.get(str(axis))
            if u is not None and str(u).strip():
                return str(u).strip()
    a = str(axis).strip()
    if a.startswith(CMD_PREFIX):
        a = a[len(CMD_PREFIX):].strip()
    return 'deg' if a in _DEG_AXES else 'mm'


def _new_meta(**values):
    meta = {k: _copy_default(v) for k, v in _META_DEFAULTS.items()}
    meta.update(values)
    return meta


def _zero_axes(data):
    return [k for k, v in data.items() if len(v) and bool(np.all(v == 0.0))]


# ----------------------------------------------------------------------------
# Curve
# ----------------------------------------------------------------------------
@dataclass
class Curve:
    """
    One time series set: a log file (kind 'log') or a reference G-code (kind 'reference').

    t      : sample times in s (strictly increasing, float)
    data   : axis -> values (same length as t); requested positions are 'Cmd <axis>'
    probe  : probe column of a log (0 none, 1..1499 detector, >= 1500 Release button, -1000
             waiting for sensor) or None
    meta   : 'computer_time', 'gcode', 'device', 'axes' (Duet axis letters of the header),
             'end' ((reason, t) of the '# End:' line), 'gaps' [(t_lost, t_back or None)],
             'pauses' [(label, t)], 'format', 'all_zero_axes', 'n', 'median_dt', 'units'
             ({axis: unit} the reader found in the file, e.g. an aligned export; see axis_unit),
             'waits', 'waits_not_marked', 'message_read_failures' (logged sensor waits, see
             read_trace_log) (always present, None / [] / {} when unknown) plus reader-specific
             extras.
    time_offset   : s added to t by times()
    value_offsets : axis -> value added by values(axis)
    """
    name: str
    kind: str
    path: str
    t: np.ndarray
    data: dict
    probe: np.ndarray | None
    meta: dict = field(default_factory=dict)
    time_offset: float = 0.0
    value_offsets: dict = field(default_factory=dict)

    def __post_init__(self):
        self.t = np.asarray(self.t, dtype=float).ravel()
        self.data = {str(k): np.asarray(v, dtype=float).ravel() for k, v in self.data.items()}
        if self.probe is not None:
            self.probe = np.asarray(self.probe, dtype=float).ravel()
        for k, v in self.data.items():
            if v.shape != self.t.shape:
                raise ValueError(f"{self.name}: axis {k} has {v.size} values for {self.t.size} times")
        if self.t.size > 1 and not np.all(np.diff(self.t) > 0.0):
            raise ValueError(f"{self.name}: times must be strictly increasing")
        if self.meta is None:
            self.meta = {}
        if self.meta.get('all_zero_axes') is None:
            self.meta['all_zero_axes'] = _zero_axes(self.data)
        for k, v in _META_DEFAULTS.items():
            if k not in self.meta:
                self.meta[k] = _copy_default(v)
        if self.meta.get('n') is None:
            self.meta['n'] = int(self.t.size)
        if self.meta.get('median_dt') is None and self.t.size > 1:
            self.meta['median_dt'] = float(np.median(np.diff(self.t)))
        self.time_offset = float(self.time_offset or 0.0)
        self.value_offsets = dict(self.value_offsets or {})

    def axes(self):
        """Axes in canonical order (DOF, raw actuators, X/Y/Z, then 'Cmd <axis>'), then others."""
        out = [a for a in AXIS_ORDER if a in self.data]
        out += [CMD_PREFIX + a for a in AXIS_ORDER if CMD_PREFIX + a in self.data]
        out += [k for k in self.data if k not in out]
        return out

    def has(self, axis):
        return axis in self.data

    def times(self):
        """Sample times with time_offset applied."""
        return self.t + self.time_offset

    def values(self, axis):
        """Values of an axis with its value offset applied."""
        if axis not in self.data:
            raise ValueError(f"{self.name} has no axis {axis!r} (available: {', '.join(self.axes())})")
        return self.data[axis] + float(self.value_offsets.get(axis, 0.0) or 0.0)


# ----------------------------------------------------------------------------
# Reading log files
# ----------------------------------------------------------------------------
_KV_RE = re.compile(r'^#\s*([^:]+?)\s*:\s*(.*?)\s*$')
# numbers in '#' lines: '.' or ',' as the decimal mark (v1 '10.110', v2 '10,110')
_NUM_TXT = r'[-+]?(?:\d+(?:[.,]\d+)?|[.,]\d+)'
_AT_TIME_RE = re.compile(r'\bat\s+(' + _NUM_TXT + r')\s*s\b', re.IGNORECASE)
_NUM_RE = re.compile(_NUM_TXT)
_RECEIVED_RE = re.compile(r'\breceived\s+at\s+(' + _NUM_TXT + r')\s*s\b', re.IGNORECASE)
_BETWEEN_RE = re.compile(r'\bbetween\s+(' + _NUM_TXT + r')\s+and\s+(' + _NUM_TXT + r')\s*s\b', re.IGNORECASE)
_BEFORE_RE = re.compile(r'\bbefore\s+(' + _NUM_TXT + r')\s*s\b', re.IGNORECASE)
_DEC_COMMA_RE = re.compile(r'^-?\d+,\d+$')
_DEC_CELL_RE = re.compile(r'^-?\d+,\d+(?:[eE][-+]?\d+)?$')
_NOTE_KINDS = (                     # (kind, line prefix) of the logger's run notes
    ('wait_start', re.compile(r'^#\s*wait\s+start\s*:', re.IGNORECASE)),
    ('wait_end', re.compile(r'^#\s*wait\s+end\s*:', re.IGNORECASE)),
    ('wait_not_marked', re.compile(r'^#\s*wait\s+not\s+marked\s*:', re.IGNORECASE)),
    ('read_failed', re.compile(r'^#\s*message\s+read\s+failed\b', re.IGNORECASE)),
)
_ROWS_END_BY = 'unknown (no notes at the end of the file)'
_COL_RE = re.compile(r'^(pos|cmd)_?(.+?)(?:_(mm|deg|rad))?$', re.IGNORECASE)
_NAME_MAP = {
    'x': 'X', 'y': 'Y', 'z': 'Z',
    'lat': 'LAT', 'si': 'SI', 'ap': 'AP',
    'roll': 'Roll', 'pitch': 'Pitch', 'yaw': 'Yaw',
    'w': 'Yaw', 'v': 'Pitch',               # TRACE log readers map W / V to Yaw / Pitch
    'a': 'A', 'b': 'B', 'c': 'C', 'd': 'D',
    "'e": "'e", "'f": "'f", "'a": "'a", "'c": "'c", "'b": "'b",
}


def _read_text(path):
    with open(path, 'rb') as f:
        raw = f.read()
    for enc in ('utf-8-sig', 'cp1252'):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode('latin-1')


def _column_axis(col):
    """'time', 'probe', an axis name ('SI', "'e", 'Cmd LAT' ...) or the stripped column name."""
    c = str(col).strip().strip('"')
    cl = c.lower()
    if cl in ('time_s', 'time', 't', 'time [s]', 'time(s)', 'time_sec'):
        return 'time'
    if cl.startswith('probe') or cl == 'sensor':
        return 'probe'
    m = _COL_RE.match(c)
    if m:
        prefix, name = m.group(1).lower(), m.group(2)
        key = _NAME_MAP.get(name.lower())
        if key is None:
            key = name
        return CMD_PREFIX + key if prefix == 'cmd' else key
    return c


def _export_columns(cols, t_idx):
    """{column index: (axis, curve, unit, header)} of the '<axis>: <curve> [<unit>]' columns of an
    aligned export of the Log files tab (time column 'time [s]')."""
    out = {}
    for k, c in enumerate(cols):
        if k == t_idx:
            continue
        h = str(c).strip().strip('"').strip()
        m = _EXPORT_COL_RE.match(h)
        if m and m.group('axis').strip():
            out[k] = (m.group('axis').strip(), m.group('curve').strip(), m.group('unit').strip(), h)
    return out


def _export_names(data, parsed):
    """data (axis -> values) with the aligned-export columns (keys = their header; parsed: header ->
    (axis, curve, unit, header)) renamed to '<axis>' when no other column with data has that axis,
    else '<axis> <curve>' (then ' (2)' ... on a clash).  Returns (data, {name: (axis, curve, unit,
    header)}); other columns and the column order are kept."""
    count = {}
    for key in data:
        if key in parsed:
            count[parsed[key][0]] = count.get(parsed[key][0], 0) + 1
    taken = {key for key in data if key not in parsed}
    out, info = {}, {}
    for key, v in data.items():
        if key not in parsed:
            out[key] = v
            continue
        axis, curve, unit, h = parsed[key]
        name = axis if count[axis] == 1 else f"{axis} {curve}".strip()
        if _column_axis(name) in ('time', 'probe', ''):
            name = f"{axis}: {curve}".strip()
        base, j = name, 2
        while name in taken:
            name = f"{base} ({j})"
            j += 1
        taken.add(name)
        out[name] = v
        info[name] = parsed[key]
    return out, info


def _split_header(line):
    """(separator, column names) of the column-names line: ';' when it holds one (v2 logs, the
    tab's v2 exports), else ',' (v1), else a tab, else whitespace."""
    for sep in (';', ',', '\t'):
        if sep in line:
            return sep, [c.strip() for c in line.split(sep)]
    return r'\s+', line.split()


def _decimal_mark(data_lines, sep):
    """',' when the separator is ';' and the data tokens are written with a decimal comma
    (-?\\d+,\\d+, e.g. '10,1666'), else '.'."""
    if sep != ';':
        return '.'
    for s in data_lines[:200]:
        for tok in s.split(';'):
            if _DEC_COMMA_RE.match(tok.strip().strip('"')):
                return ','
    return '.'


def _num(text):
    """A number of a '#' line ('.' or ',' as the decimal mark), or None."""
    try:
        x = float(str(text).replace(',', '.'))
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _parse_at_time(text):
    m = _AT_TIME_RE.search(text)
    if m:
        return _num(m.group(1))
    return None


def _line_time(line, sep, t_idx, dec='.'):
    """Time field of one data text line (float) or None when it is missing / not a finite number."""
    parts = line.split() if sep == r'\s+' else line.split(sep)
    if t_idx >= len(parts):
        return None
    tok = parts[t_idx].strip().strip('"')
    if dec == ',':
        tok = tok.replace(',', '.')
    try:
        x = float(tok)
    except ValueError:
        return None
    return x if math.isfinite(x) else None


def _to_numeric(col, dec):
    """A parsed column as floats (NaN where not a number); decimal-comma text columns included (a
    column with one text cell is not numeric: object dtype, or StringDtype with pandas >= 3, so its
    other cells still have their decimal comma)."""
    if dec == ',' and not pd.api.types.is_numeric_dtype(col):
        col = col.astype(str).str.replace(',', '.', regex=False)
    return pd.to_numeric(col, errors='coerce').to_numpy(dtype=float)


def _has_text(col):
    """True when a parsed column holds at least one non-empty cell (text or number)."""
    try:
        s = col.dropna()
        if s.empty:
            return False
        if pd.api.types.is_numeric_dtype(s):
            return True
        return bool((s.astype(str).str.strip() != '').any())
    except Exception:
        return False


def _excel_comment(line):
    """A '#' line as Excel writes it back when a CSV is opened and saved again: a cell holding '"'
    is quoted with its quotes doubled ('"# Wait start: ""Waiting ..."" received at ..."'), and a row
    may get trailing separators (';;;').  Returns the comment line, or None when it is not one."""
    s = line.strip()
    if s.startswith('"#'):
        out, i, n = [], 1, len(s)
        while i < n:
            ch = s[i]
            if ch == '"':
                if i + 1 < n and s[i + 1] == '"':
                    out.append('"')
                    i += 2
                    continue
                break                           # the closing quote: anything after it (';;;') is dropped
            out.append(ch)
            i += 1
        return ''.join(out).strip()
    if s.startswith('#'):
        return s.rstrip(';').rstrip()
    return None


def _unquoted_spans(text):
    """[(start, end)] of the parts of text outside double quotes."""
    out, pos, inside = [], 0, False
    for i, ch in enumerate(text):
        if ch == '"':
            if not inside:
                out.append((pos, i))
            pos, inside = i + 1, not inside
    if not inside:
        out.append((pos, len(text)))
    return out


def _at_time_outside_quotes(text):
    """First 'at <t> s' of text outside a quoted Duet message: (t, match start, match end) or None."""
    for a, b in _unquoted_spans(text):
        m = _AT_TIME_RE.search(text, a, b)
        if m and m.end() <= b:
            t = _num(m.group(1))
            if t is not None:
                return t, m.start(), m.end()
    return None


def _sent_window(text):
    """(sent_from, sent_to) of 'between A and B s' / 'before B s': A is None for 'before'."""
    m = _BETWEEN_RE.search(text)
    if m:
        return _num(m.group(1)), _num(m.group(2))
    m = _BEFORE_RE.search(text)
    if m:
        return None, _num(m.group(1))
    return None, None


def _quoted(text):
    m = re.search(r'"([^"]*)"', text)
    return m.group(1) if m else None


def _parse_note(kind, s):
    """One run note of the logger (s = the stripped '#' line) as a dict; None when it is malformed
    (no usable time).  Times are run times in s."""
    body = s.lstrip('#').strip()
    rest = body.split(':', 1)[1].strip() if ':' in body else ''
    if kind in ('wait_start', 'wait_not_marked'):
        m = _RECEIVED_RE.search(rest)
        t = _num(m.group(1)) if m else None
        if t is None:
            hit = _at_time_outside_quotes(rest)
            t = hit[0] if hit else None
        if t is None:
            return None
        sent_from, _ = _sent_window(rest)
        out = {'received': t, 'sent_from': sent_from, 'message': _quoted(rest), 'line': body}
        if kind == 'wait_not_marked':
            why = ''
            k = rest.lower().find('may already have ended')
            if k >= 0:
                why = rest[k + len('may already have ended'):].lstrip(' :').strip()
            elif ')' in rest:
                why = rest.rsplit(')', 1)[1].lstrip(' ,:').strip()
            out['reason'] = why
        return out
    if kind == 'wait_end':
        hit = _at_time_outside_quotes(rest)
        if hit is None:
            return None
        t, a, b = hit
        what = rest[:a].strip()
        after = rest[b:].strip()
        how = after[1:-1].strip() if after.startswith('(') and after.endswith(')') else after.strip(' ()')
        return {'end': t, 'end_by': what or 'unknown', 'end_note': how,
                'end_exact': 'exact to one sample' in how.lower(), 'line': body}
    if kind == 'read_failed':
        head, _, tail = body.partition(':')
        t = _parse_at_time(head)
        if t is None:
            return None
        sent_from, sent_to = _sent_window(tail)
        return {'t': t, 'sent_from': sent_from, 'sent_to': sent_to, 'line': body}
    return None


def _wait_rows(t, probe, a, b):
    """Number of Probe -1000 rows with a <= t < b."""
    if probe is None:
        return 0
    i0 = int(np.searchsorted(t, a, side='left'))
    i1 = int(np.searchsorted(t, b, side='left'))
    return int(np.count_nonzero(probe[i0:i1] == PROBE_WAIT))


def _wait_cut(t, probe, received, end):
    """Interval [start, stop) of the rows of one noted wait: start = received, earlier by up to the
    0.5 ms rounding of the note when a -1000 row lies there; stop = the row at 'end' (the first row
    at or after end - 0.5 ms: the trigger row stays, it is not part of the wait), or end itself when
    no row is that close (e.g. a Duet message end between rows).  A Probe -1000 row within that
    rounding is a row of the wait (the logger marked it before the end): the stop is never snapped
    onto it, it stays inside [start, stop)."""
    start = float(received)
    if probe is not None and t.size:
        i = int(np.searchsorted(t, start - _NOTE_ROUND - _EPS_T, side='left'))
        if i < t.size and t[i] < start and probe[i] == PROBE_WAIT:
            start = float(t[i])
    stop = float(end)
    if t.size:
        j = int(np.searchsorted(t, stop - _NOTE_ROUND - _EPS_T, side='left'))
        hi = stop + _NOTE_ROUND + _EPS_T
        while j < t.size and float(t[j]) <= hi:
            if probe is not None and probe[j] == PROBE_WAIT:
                stop = max(stop, float(np.nextafter(t[j], np.inf)))     # this wait row stays inside
                j += 1
                continue
            stop = float(t[j])                  # the row that ended the wait (trigger row): kept
            break
    return start, max(start, stop)


def _row_groups(t, probe, covered):
    """Waits seen only in the rows (no note covers them): runs of rows with Probe -1000, 1..500 or
    2000 that lie between -1000 rows, -1000 rows covered by a noted wait left out.  [(i_first,
    i_last)] of the first / last -1000 row of each group."""
    if probe is None or not t.size:
        return []
    is_w = (probe == PROBE_WAIT) & ~covered
    if not is_w.any():
        return []
    cand = (is_w | ((probe >= 1) & (probe <= SENSOR_WAIT_THRESHOLD)) | (probe == 2000)) & ~covered
    out = []
    n = t.size
    w_idx = np.flatnonzero(is_w)
    breaks = np.flatnonzero(~cand)                  # rows that end a run
    k = 0
    while k < w_idx.size:
        first = int(w_idx[k])
        q = int(np.searchsorted(breaks, first, side='right'))
        run_end = int(breaks[q]) if q < breaks.size else n          # first row after the run
        k2 = int(np.searchsorted(w_idx, run_end, side='left'))      # -1000 rows of the run: w_idx[k:k2]
        last = int(w_idx[k2 - 1])
        out.append((first, last))
        k = k2
    return out


def _build_waits(t, probe, events, warnings):
    """meta['waits'], meta['waits_not_marked'], meta['message_read_failures'] from the run notes
    (events: (kind, dict) in file order) and the Probe -1000 rows."""
    waits, not_marked, failures = [], [], []
    open_w = None

    def close_from_rows(w, why):
        # a wait start without its end note: the end is the first row after its -1000 rows
        i = int(np.searchsorted(t, w['received'] - _NOTE_ROUND - _EPS_T, side='left'))
        grp = _row_groups(t[i:], None if probe is None else probe[i:], np.zeros(t.size - i, bool))
        if grp and t[i + grp[0][0]] <= w['received'] + 2.0:      # its rows start right after the message
            last = i + grp[0][1]
            end = float(t[last + 1]) if last + 1 < t.size else float(t[last]) + _median_dt(t)
        else:
            end = float(w['received'])
        w.update(end=end, end_by=_ROWS_END_BY, end_note=why, end_exact=False)
        warnings.append(f"Wait received at {w['received']:.3f} s: {why}; its end is taken from the -1000 rows")
        return w

    for kind, d in events:
        if kind == 'wait_start':
            if open_w is not None:
                waits.append(close_from_rows(open_w, "no '# Wait end' note before the next wait start"))
            open_w = dict(d, source='notes')
        elif kind == 'wait_end':
            if open_w is None:
                warnings.append(f"'# Wait end' note at {d['end']:.3f} s without a '# Wait start' note: ignored")
                continue
            w = open_w
            open_w = None
            w.update(end=d['end'], end_by=d['end_by'], end_note=d['end_note'], end_exact=d['end_exact'],
                     end_line=d.get('line'))
            if w['end'] < w['received']:
                warnings.append(f"Wait received at {w['received']:.3f} s ends before it starts ({w['end']:.3f} s): "
                                f"taken as 0 s long")
                w['end'] = w['received']
            waits.append(w)
        elif kind == 'wait_not_marked':
            not_marked.append({'received': d['received'], 'sent_from': d['sent_from'], 'reason': d.get('reason', ''),
                               'message': d.get('message'), 'line': d.get('line')})
        elif kind == 'read_failed':
            failures.append({'t': d['t'], 'sent_from': d['sent_from'], 'sent_to': d['sent_to'], 'line': d.get('line')})
    if open_w is not None:
        waits.append(close_from_rows(open_w, "no '# Wait end' note"))

    for w in waits:
        w['cut'] = _wait_cut(t, probe, w['received'], w['end'])
        w['rows'] = _wait_rows(t, probe, *w['cut'])
        w['length'] = float(w['cut'][1] - w['cut'][0])

    # rows-only fallback (TRACE stopped before writing the notes): -1000 rows outside every noted wait
    if probe is not None and t.size and np.any(probe == PROBE_WAIT):
        covered = np.zeros(t.size, dtype=bool)
        for w in waits:
            a, b = w['cut']
            covered |= (t >= a) & (t < b)
        groups = _row_groups(t, probe, covered)
        for first, last in groups:
            a = float(t[first])
            if last + 1 < t.size:
                b, note = float(t[last + 1]), 'from the Probe -1000 rows: end = first row after them'
            else:
                b, note = float(t[last]) + _median_dt(t), 'from the Probe -1000 rows: the data ends during the wait'
            w = {'received': a, 'sent_from': None, 'message': None, 'end': b, 'end_by': _ROWS_END_BY,
                 'end_note': note, 'end_exact': False, 'source': 'rows', 'cut': (a, b)}
            w['rows'] = _wait_rows(t, probe, a, b)
            w['length'] = b - a
            waits.append(w)
        if groups:
            warnings.append(f"{len(groups)} sensor wait(s) seen only in the Probe -1000 rows (no '# Wait start' / "
                            f"'# Wait end' notes for them, e.g. LogIQ stopped before closing the log): start = "
                            f"first -1000 row, end = first row after them, the Duet's send time is unknown")
    waits.sort(key=lambda w: w['received'])
    not_marked.sort(key=lambda w: w['received'])
    failures.sort(key=lambda w: w['t'])
    for k, w in enumerate(waits):
        w['index'] = k
    return waits, not_marked, failures


def _median_dt(t):
    return float(np.median(np.diff(t))) if t.size > 1 else 0.05


def _device_from_axes(axes):
    base = {a[len(CMD_PREFIX):] if a.startswith(CMD_PREFIX) else a for a in axes}
    if base & set(PLATFORM_DOF + PLATFORM_RAW):
        return 'Motion Platform'
    if base & set(PHANTOM_AXES):
        return 'Lung Phantom'
    return None


def read_trace_log(path):
    """
    Read a TRACE log file (any format written so far) into a Curve (kind 'log', name = file stem).

    Formats ('#' lines are comments / metadata, the first other line holds the column names):
      'trace-header'  : 5, 7, 8 or 10 '#' header lines (Computer Time, G-code, Device, Axes (Duet
                        order), Positions, Probe, Wait timing, Run notes, Recording from, Format),
                        DOF + raw actuator or X/Y/Z columns; '# Gap: ... at t s', '# Gap end: ... at
                        t s', '# End: <reason> at t s' and the sensor-wait notes ('# Wait start:',
                        '# Wait end:', '# Wait not marked:', '# Message read failed at ...') may
                        appear between the rows (v1) or after the last row (v2).
      'pos+cmd'       : 5/6 Nov logs, Pos_* plus Cmd_* (requested position) columns.
      'computer-time' : 3 Nov logs, a single '# Computer Time' line.
      'aligned-export': the Log files tab's aligned export, time column 'time [s]' and one
                        '<axis>: <curve> [<unit>]' column per curve.  Each such column becomes the
                        axis '<axis>' (e.g. 'Roll', so a single exported curve lines up with the
                        others) or, when several columns share that axis, '<axis> <curve>' (then
                        ' (2)' ... on a clash); meta['units'] = {axis: unit} keeps the unit
                        (axis_unit(axis, curve)), meta['export_axes'] = {axis: exported axis} and
                        meta['source_columns'] = {axis: column header}.
      'plain'         : no comment line (old text logs).
    Text style: the separator comes from the column-names line (';' when it holds one, else ',',
    else a tab, else whitespace); with ';' the numbers are read with a decimal comma when the data
    tokens look like -?\\d+,\\d+ (v2 logs and the tab's v2 exports: '10,1666;50,000;...').  Numbers
    in '#' lines may use '.' or ',' (e.g. '# Recording from: 0,000 s of the run').  A file opened
    and saved again by Excel is read too: a '#' line it wrote quoted ('"# Wait start: ""Waiting
    ..."" received at ..."', a cell holding '"') or with trailing separators is still a comment line.
    Rows with an invalid time are dropped, rows are sorted by time and duplicate times keep the
    first row, so t is strictly increasing; missing values are interpolated over time (a text
    cell costs only its own value; an axis column with text but no number at all is left out with a
    warning; in an aligned export a column stays empty (NaN) before its first and after its last
    value: that curve has no data there).  Fields
    beyond the header's columns (e.g. a trailing delimiter) are ignored; rows with fewer fields
    than the header read the missing ones as empty (a missing Probe value is 0, an axis column
    without any value is left out).
    The time base is the log's own (run time), so gap / end / wait times refer to it; a Gap / End
    line without 'at <t> s' takes the time of the nearest kept data row before it (Gap end: after it).
    Logged sensor waits (never estimated; the probe array keeps its -1000 values):
      meta['waits'] = [dict(received, sent_from, end, end_by, end_note, end_exact, rows, source,
        cut, length, index, message, line)] in time order: each '# Wait start' paired with the next
        '# Wait end'.  received = when TRACE got the Duet message (s); sent_from = start of the window
        in which the Duet sent it (None for 'before T s (no earlier read)'), so the real start lies in
        [sent_from, received]; end / end_by / end_note = the '# Wait end' line ('<what> at T s
        (<how>)'), end_exact when it says 'exact to one sample'; rows = Probe -1000 rows in the wait;
        cut = (start, stop) of the rows it covers ([received, end): stop is the row at 'end', the
        trigger row, within the 0.5 ms rounding of the note) and length = stop - start; source
        'notes', or 'rows' for -1000 rows outside every noted wait (TRACE stopped before writing the
        notes): grouped over runs of rows with -1000, 1..500 or 2000 between -1000 rows, start = the
        first -1000 row, end = the first row after the last one, sent_from None, end_by 'unknown (no
        notes at the end of the file)' (a warning says so).
      meta['waits_not_marked'] = [dict(received, sent_from, reason, message, line)] ('# Wait not
        marked': the wait may have ended before TRACE knew of it, no row marked);
      meta['message_read_failures'] = [dict(t, sent_from, sent_to, line)] ('# Message read failed':
        Duet messages sent in [sent_from, sent_to] may be lost, so a wait start / end may be missing).
    Extra meta keys: 'header' (comment lines before the columns), 'recording_from', 'device_source'
    ('header' | 'columns'), 'release_times' (Probe >= 1500 onsets), 'separator', 'decimal'
    ('.' | ','), 'warnings' (list of str).
    Raises ValueError with a clear message for files that cannot be used.
    """
    path = os.fspath(path)
    base = os.path.basename(path)
    if not os.path.isfile(path):
        raise ValueError(f"Log file not found: {path}")
    try:
        text = _read_text(path)
    except OSError as e:
        raise ValueError(f"Cannot read {base}: {e}") from None

    comments = []            # (stripped line, number of data text lines before it)
    header_line = None
    data_lines = []
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        cm = _excel_comment(s) if s[0] in '#"' else None
        if cm is not None:
            comments.append((cm, len(data_lines)))
        elif header_line is None:
            header_line = s
        else:
            data_lines.append(s)
    if header_line is None:
        raise ValueError(f"{base}: no column header line (empty file?)")

    sep, cols = _split_header(header_line)
    targets = [_column_axis(c) for c in cols]
    if 'time' not in targets:
        raise ValueError(f"{base}: no time column (Time_s) - this is not a LogIQ log file "
                         f"(first line: {header_line[:80]!r})")
    if not data_lines:
        raise ValueError(f"{base}: the file has a header but no data rows")
    dec = _decimal_mark(data_lines, sep)
    t_idx = targets.index('time')
    export_cols = {}
    if str(cols[t_idx]).strip().strip('"').strip().lower() == _EXPORT_TIME_COL:
        # aligned export: its columns are read under their header, renamed after the data
        export_cols = _export_columns(cols, t_idx)
        for k, info in export_cols.items():
            targets[k] = info[3]

    # As many column names as the widest row: extra trailing fields (a trailing delimiter) can
    # then neither shift every column into the index nor get a row skipped, and rows with fewer
    # fields than the header (no Probe value, a header with a trailing delimiter) read as NaN.
    if sep == r'\s+':
        maxf = max(len(s.split()) for s in data_lines)
    else:
        maxf = max(s.count(sep) + 1 for s in data_lines)
    ncol = max(len(cols), maxf)
    try:
        df = pd.read_csv(io.StringIO('\n'.join(data_lines)), sep=sep, header=None,
                         names=list(range(ncol)), index_col=False, on_bad_lines='skip', decimal=dec,
                         engine='python' if sep not in (',', ';', '\t', r'\s+') else 'c')
    except Exception as e:      # pandas parser errors have many types
        raise ValueError(f"{base}: cannot parse the data rows ({e})") from None
    df = df.iloc[:, :len(cols)]

    t_all = _to_numeric(df[t_idx], dec)
    valid = np.flatnonzero(np.isfinite(t_all))
    if valid.size < 2:
        raise ValueError(f"{base}: fewer than 2 rows with a valid time")
    t_valid = t_all[valid]
    order = np.argsort(t_valid, kind='stable')
    t_sorted = t_valid[order]
    keep = np.concatenate(([True], np.diff(t_sorted) > 0.0))
    rows = valid[order][keep]
    t = t_sorted[keep]
    if t.size < 2:
        raise ValueError(f"{base}: fewer than 2 distinct sample times")

    data, probe, warnings = {}, None, []
    for idx, target in enumerate(targets):
        if target in ('time', '') or idx >= df.shape[1]:          # '': unnamed (trailing delimiter)
            continue
        v = _to_numeric(df[idx], dec)[rows]
        fin = np.isfinite(v)
        if target == 'probe':
            if probe is None:
                probe = np.where(fin, v, 0.0)
            continue
        if target in data:
            continue
        if not fin.any():
            if _has_text(df[idx].iloc[rows]):
                warnings.append(f"Column {str(cols[idx]).strip()!r} has no numeric value: left out")
            continue
        if not fin.all():
            if idx in export_cols:
                # aligned export: a curve's column is empty where that curve has no data (e.g. a shorter
                # curve, or one shown without its waits): kept empty (NaN) outside its first / last value,
                # interpolated only between them (no value held beyond what the file holds)
                f = np.flatnonzero(fin)
                inner = np.interp(t, t[fin], v[fin])
                v = np.full(t.shape, np.nan)
                v[f[0]:f[-1] + 1] = inner[f[0]:f[-1] + 1]
            else:
                v = np.interp(t, t[fin], v[fin])
        data[target] = v
    if not data:
        raise ValueError(f"{base}: no position columns (Pos_*_mm / Pos_*_deg) found")
    export_info = {}
    if export_cols:
        data, export_info = _export_names(data, {info[3]: info for info in export_cols.values()})

    # ---- comment lines: header metadata, gaps, end, sensor-wait notes ----
    meta = _new_meta(format=None)
    meta['header'] = []
    meta['recording_from'] = None
    header_keys = set()
    gaps, end = [], None
    wait_events = []         # (kind, dict) of the sensor-wait notes, in file order

    def row_time(n_before, after=False):
        # Time of the nearest data text line before (after) the comment whose row was kept.  The
        # text is parsed directly: pandas row numbers differ from text line numbers as soon as a
        # line is dropped (invalid time, parser skip), so t_all cannot be indexed by line count.
        ks = range(n_before, len(data_lines)) if after else range(n_before - 1, -1, -1)
        for k in ks:
            x = _line_time(data_lines[k], sep, t_idx, dec)
            if x is None:
                continue
            q = int(np.searchsorted(t, x))
            for qq in (q - 1, q):
                if 0 <= qq < t.size and abs(t[qq] - x) <= 1e-9 * max(1.0, abs(x)):
                    return float(t[qq])
        return None

    for s, n_before in comments:
        low = s.lower()
        body = s.lstrip('#').strip()
        if re.match(r'^#\s*gap\s+end\s*:', low):
            tb = _parse_at_time(body)
            if tb is None:
                tb = row_time(n_before, after=True)
            for k in range(len(gaps) - 1, -1, -1):
                if gaps[k][1] is None:
                    gaps[k] = (gaps[k][0], tb)
                    break
            continue
        if re.match(r'^#\s*gap\s*:', low):
            tl = _parse_at_time(body)
            if tl is None:
                tl = row_time(n_before)
            if tl is not None:
                gaps.append((tl, None))
            continue
        if re.match(r'^#\s*end\s*:', low):
            reason = body.split(':', 1)[1].strip()
            te = _parse_at_time(reason)
            reason = _AT_TIME_RE.split(reason)[0].strip() if te is not None else reason
            if te is None:
                te = row_time(n_before)
            end = (reason, te)
            continue
        kind = next((k for k, rx in _NOTE_KINDS if rx.match(s)), None)
        if kind is not None:
            d = _parse_note(kind, s)
            if d is None:
                warnings.append(f"Malformed note ignored (no time): {body[:80]}")
            else:
                wait_events.append((kind, d))
            continue
        if n_before == 0:
            meta['header'].append(body)
        m = _KV_RE.match(s)
        if not m:
            continue
        key, val = m.group(1).strip().lower(), m.group(2).strip()
        header_keys.add(key)
        if key == 'computer time':
            meta['computer_time'] = val or None
        elif key in ('g-code', 'gcode'):
            meta['gcode'] = None if val.lower() in ('', 'none') else val
        elif key == 'device':
            meta['device'] = canonical_device(val)      # 'KINETIQ' / 'Motion Platform' (old logs) -> code word
        elif key.startswith('axes'):
            letters = [a.strip() for a in val.split(',') if a.strip()]
            meta['axes'] = None if not letters or val.lower() == 'unknown' else letters
        elif key == 'recording from':
            mm = _NUM_RE.search(val)
            meta['recording_from'] = _num(mm.group(0)) if mm else None

    if meta['device']:
        meta['device_source'] = 'header'
    else:
        meta['device'] = _device_from_axes([export_info[k][0] if k in export_info else k for k in data])
        meta['device_source'] = 'columns'

    if 'device' in header_keys:
        fmt = 'trace-header'
    elif export_info:
        fmt = 'aligned-export'
    elif any(k.startswith(CMD_PREFIX) for k in data):
        fmt = 'pos+cmd'
    elif comments:
        fmt = 'computer-time'
    else:
        fmt = 'plain'

    zero = _zero_axes(data)
    pos_axes = [k for k in data if not k.startswith(CMD_PREFIX)]
    if pos_axes and all(k in zero for k in pos_axes):
        warnings.append(f"All values of {', '.join(pos_axes)} are 0: nothing was recorded for these "
                        f"axes (log written with the wrong columns for the device?)")

    release = []
    if probe is not None:
        on = probe >= PROBE_RELEASE_MIN
        starts = np.flatnonzero(on & ~np.concatenate(([False], on[:-1])))
        release = [float(t[i]) for i in starts]

    waits, not_marked, failures = _build_waits(t, probe, wait_events, warnings)

    meta.update({
        'end': end, 'gaps': gaps, 'pauses': [], 'format': fmt, 'all_zero_axes': zero,
        'n': int(t.size), 'median_dt': float(np.median(np.diff(t))),
        'release_times': release, 'warnings': warnings,
        'units': {k: u for k, (_, _, u, _) in export_info.items() if u},
        'waits': waits, 'waits_not_marked': not_marked, 'message_read_failures': failures,
        'separator': sep, 'decimal': dec,
    })
    if export_info:
        meta['export_axes'] = {k: v[0] for k, v in export_info.items()}
        meta['source_columns'] = {k: v[3] for k, v in export_info.items()}
    name = os.path.splitext(base)[0]
    return Curve(name=name, kind='log', path=path, t=t, data=data, probe=probe, meta=meta)


# ----------------------------------------------------------------------------
# Reference G-code
# ----------------------------------------------------------------------------
def _gcode_lines(src):
    """(lines, path, file name) from a path, a G-code text or a list of lines."""
    if isinstance(src, (list, tuple)):
        return [str(x) for x in src], '', None
    s = os.fspath(src)
    if isinstance(s, bytes):
        s = s.decode('utf-8', errors='replace')
    if '\n' not in s and len(s) < 1024 and os.path.isfile(s):
        try:
            return _read_text(s).splitlines(), s, os.path.basename(s)
        except OSError as e:
            raise ValueError(f"Cannot read {os.path.basename(s)}: {e}") from None
    if '\n' in s or re.search(r'^\s*[GgMm]\d', s, re.MULTILINE):
        return s.splitlines(), '', None
    raise ValueError(f"G-code file not found: {s}")


def _platform_dof_arrays(L, lat_dim, si_dim):
    """Platform DOF from actuator arrays, same formulas as the logger (fcn_duet._platform_dof)."""
    n = len(next(iter(L.values())))
    z = np.zeros(n)
    out = {}
    if all(k in L for k in ('A', 'B', 'C', 'D')):
        a, b, c, d = L['A'], L['B'], L['C'], L['D']
        out['Roll'] = np.degrees(np.arctan2((a + d) / 2.0 - (b + c) / 2.0, lat_dim))
        out['Pitch'] = np.degrees(np.arctan2((a + b) / 2.0 - (c + d) / 2.0, si_dim))
        out['AP'] = (a + b + c + d) / 4.0
    if "'e" in L or "'f" in L:
        out['LAT'] = (L.get("'e", z) + L.get("'f", z)) / 2.0
    y_lo = "'c" if "'c" in L else ("'b" if "'b" in L else None)
    if "'a" in L or y_lo is not None:
        out['SI'] = (L.get("'a", z) + (L[y_lo] if y_lo else z)) / 2.0
    out['Yaw'] = np.array(L['W'], dtype=float) if 'W' in L else z.copy()
    return out


def _build_reference(name, path, src, pause_durations):
    """Reference Curve from its parsed source, holding each pause for its duration."""
    pauses = list(src['pauses'])
    d = [float(x) if x is not None and np.isfinite(float(x)) else 0.0
         for x in list(pause_durations or [])[:len(pauses)]]
    d = [max(0.0, x) for x in d] + [0.0] * (len(pauses) - len(d))
    t0 = src['t']
    data0 = src['data']
    starts = []
    acc = 0.0
    for (label, tp), dur in zip(pauses, d):
        starts.append((label, float(tp) + acc))
        acc += dur
    if any(x > 0.0 for x in d):
        tp = np.array([p[1] for p in pauses], dtype=float)
        cum = np.concatenate(([0.0], np.cumsum(d)))
        k = np.searchsorted(tp, t0 - _EPS_T, side='left')      # pauses strictly before each row
        t_rows = t0 + cum[k]
        hold_t, hold_idx = [], []
        for i, ((_, tpi), dur) in enumerate(zip(pauses, d)):
            if dur <= 0.0:
                continue
            hold_t += [starts[i][1], starts[i][1] + dur]
            hold_idx.append(float(tpi))
        hold_t = np.array(hold_t, dtype=float)
        tp_hold = np.repeat(np.array(hold_idx, dtype=float), 2)
        all_t = np.concatenate((t_rows, hold_t))
        order = np.argsort(all_t, kind='stable')
        all_t = all_t[order]
        keep = np.concatenate((np.diff(all_t) > _EPS_T, [True]))       # keep last of equal times
        t_new = all_t[keep]
        data = {}
        for ax, v in data0.items():
            vh = np.interp(tp_hold, t0, v) if t0.size > 1 else np.full(tp_hold.shape, v[0])
            data[ax] = np.concatenate((v, vh))[order][keep]
    else:
        t_new = t0.copy()
        data = {ax: v.copy() for ax, v in data0.items()}
    meta = _new_meta(gcode=src['gcode'], device=src['device'], axes=list(src['letters']),
                     pauses=starts, format='gcode', all_zero_axes=_zero_axes(data))
    meta.update({
        'pause_durations': d,
        'pauses_gcode': pauses,
        'total_time': float(src['total']) + float(sum(d)),
        'lat_dim': src['lat_dim'], 'si_dim': src['si_dim'],
        'n_rows': src['n_rows'],
        '_source': src,
    })
    return Curve(name=name, kind='reference', path=path, t=t_new, data=data, probe=None, meta=meta)


def read_reference_gcode(path_or_text, name=None, lat_dim=100.0, si_dim=100.0, pause_durations=None):
    """
    Reference Curve (kind 'reference') from a G-code file path, a G-code text or a list of lines.

    The timeline comes from fcn_plan.fcn_gcode.parse_gcode_timeline (same RRF time model as the
    planner); positions are piecewise linear between its rows.  data holds the axis letters present
    (A, B, C, D, 'e, 'f, 'a, 'c, X, Y, Z ...) and, for the platform, the DOF LAT/SI/AP/Roll/Pitch/Yaw
    computed with the logger formulas (lat_dim / si_dim = platform dimensions in mm).
    meta['pauses'] = [(label, start time)] of the pauses (sensor_wait / M226 ...), meta['gcode'] =
    file name.  pause_durations: one duration in s per pause (in order); the curve holds its value
    for that long at each pause and every later time shifts (default: pauses take 0 s).
    Extra meta keys: 'pause_durations', 'pauses_gcode' (parser times), 'total_time', 'lat_dim',
    'si_dim', 'n_rows', '_source' (used by with_pause_durations).
    """
    from fcn_plan.fcn_gcode import parse_gcode_timeline

    lines, path, fname = _gcode_lines(path_or_text)
    parser = parse_gcode_timeline(lines)
    rows = parser.rows
    if not rows:
        raise ValueError(f"{fname or 'G-code'}: no moves found")
    letters = []
    for r in rows:
        for k in r:
            if k in ('time', 'timestamp', 'Command') or k in letters:
                continue
            if (k.startswith("'") and len(k) == 2) or k in _GCODE_AXIS_LETTERS:
                letters.append(k)
    if not letters:
        raise ValueError(f"{fname or 'G-code'}: no axis positions found")

    t_raw = np.array([float(r['time']) for r in rows], dtype=float)
    raw = {}
    for ax in letters:
        v = np.array([float(r[ax]) if ax in r else np.nan for r in rows], dtype=float)
        fin = np.isfinite(v)
        first = int(np.argmax(fin))
        v[:first] = v[first]                       # before an axis' first move: its first position
        if not fin.all():
            v = pd.Series(v).ffill().to_numpy(dtype=float)
        raw[ax] = v
    order = np.argsort(t_raw, kind='stable')
    t_s = t_raw[order]
    keep = np.concatenate((np.diff(t_s) > _EPS_T, [True]))           # same time: last row wins
    t = t_s[keep]
    raw = {ax: v[order][keep] for ax, v in raw.items()}
    total = float(parser.time)
    if total > t[-1] + _EPS_T:                    # trailing dwell without a row: hold the end
        t = np.append(t, total)
        raw = {ax: np.append(v, v[-1]) for ax, v in raw.items()}

    platform = any(a in raw for a in ('A', 'B', 'C', 'D')) or any(a.startswith("'") for a in raw)
    data = dict(raw)
    if platform:
        data.update(_platform_dof_arrays(raw, float(lat_dim), float(si_dim)))
        device = 'Motion Platform'
    else:
        device = 'Lung Phantom' if any(a in raw for a in PHANTOM_AXES) else None

    src = {
        't': t, 'data': data, 'pauses': [(str(lb), float(tp)) for lb, tp in parser.pause_times],
        'total': max(total, float(t[-1])), 'lat_dim': float(lat_dim), 'si_dim': float(si_dim),
        'device': device, 'letters': letters, 'gcode': fname, 'n_rows': len(rows),
    }
    if name is None:
        name = os.path.splitext(fname)[0] if fname else 'reference'
    return _build_reference(name, path, src, pause_durations)


def with_pause_durations(ref_curve, pause_durations):
    """New reference Curve rebuilt from ref_curve's source with the given pause durations (s, one
    per pause in order); time_offset and value_offsets are kept."""
    src = ref_curve.meta.get('_source') if isinstance(ref_curve.meta, dict) else None
    if src is None:
        raise ValueError(f"{ref_curve.name} is not a reference G-code curve (no source to rebuild from)")
    c = _build_reference(ref_curve.name, ref_curve.path, src, pause_durations)
    c.time_offset = float(ref_curve.time_offset)
    c.value_offsets = dict(ref_curve.value_offsets)
    return c


# ----------------------------------------------------------------------------
# Sampling helpers
# ----------------------------------------------------------------------------
def _roi_bounds(roi):
    if roi is None:
        return -np.inf, np.inf
    a = -np.inf if roi[0] is None else float(roi[0])
    b = np.inf if roi[1] is None else float(roi[1])
    return (a, b) if a <= b else (b, a)


def roi_mask(t, roi):
    """Boolean mask of t inside roi = (t0, t1) (inclusive, either order; None = everything)."""
    t = np.asarray(t, dtype=float)
    if roi is None:
        return np.ones(t.shape, dtype=bool)
    a, b = _roi_bounds(roi)
    return (t >= a) & (t <= b)


def _span(curve):
    tt = curve.times()
    if tt.size == 0:
        return np.nan, np.nan
    return float(tt[0]), float(tt[-1])


def _grid_dt(t0, t1, dt):
    dt = float(dt)
    if not dt > 0.0:
        raise ValueError("dt must be > 0")
    span = t1 - t0
    if span / dt > _MAX_GRID:
        dt = span / _MAX_GRID
    return dt


def _grid(t0, t1, dt):
    """Uniform grid of multiples of dt inside [t0, t1] (returns grid, dt actually used, k0)."""
    if not (np.isfinite(t0) and np.isfinite(t1)) or t1 < t0:
        return np.empty(0), float(dt), 0
    dt = _grid_dt(t0, t1, dt)
    k0 = int(math.ceil(t0 / dt - 1e-6))
    k1 = int(math.floor(t1 / dt + 1e-6))
    if k1 < k0:
        return np.empty(0), dt, k0
    g = np.arange(k0, k1 + 1, dtype=float) * dt
    return np.clip(g, t0, t1), dt, k0


def gap_spans(curve):
    """
    Connection gaps of a log as [(a_eff, b_eff)] in the offset time base: a_eff = last sample at or
    before the loss, b_eff = first sample at or after the reconnection (open gap: first sample after
    the loss; inf when the data ends).  The data is unknown strictly between a_eff and b_eff.
    """
    gaps = curve.meta.get('gaps') if isinstance(curve.meta, dict) else None
    tt = curve.times()
    out = []
    if not gaps or tt.size == 0:
        return out
    off = curve.time_offset
    for gap in gaps:
        if not gap or gap[0] is None:
            continue
        a = float(gap[0]) + off
        b = gap[1] if len(gap) > 1 else None
        i = int(np.searchsorted(tt, a, side='right')) - 1          # last sample at/before the loss
        a_eff = float(tt[i]) if i >= 0 else a
        if b is None:
            j = int(np.searchsorted(tt, a, side='right'))
        else:
            j = int(np.searchsorted(tt, float(b) + off, side='left'))
        b_eff = float(tt[j]) if j < tt.size else np.inf
        out.append((a_eff, b_eff))
    return out


def sample(curve, axis, t_grid, gaps_as_nan=True):
    """
    Values of curve[axis] (offsets applied) at t_grid (offset time base), linear between samples.
    NaN outside the curve's time span and, with gaps_as_nan, between the last sample before and
    the first sample after each connection gap of a log (see gap_spans).
    """
    tg = np.asarray(t_grid, dtype=float)
    tt = curve.times()
    vv = curve.values(axis)
    if tt.size == 0:
        return np.full(tg.shape, np.nan)
    out = np.interp(tg, tt, vv, left=np.nan, right=np.nan)
    if gaps_as_nan:
        for a_eff, b_eff in gap_spans(curve):
            out[(tg > a_eff) & (tg < b_eff)] = np.nan
    return out


# ----------------------------------------------------------------------------
# Shift / comparison / ensemble
# ----------------------------------------------------------------------------
def _xcorr_valid(b, a):
    """out[q] = sum_i a[i] * b[i + q], q = 0 .. len(b) - len(a)."""
    if a.size * (b.size - a.size + 1) < 2_000_000:
        return np.correlate(b, a, mode='valid')
    return signal.fftconvolve(b, a[::-1], mode='valid')


def estimate_shift(ref, cur, axis, roi=None, max_lag=5.0, dt=0.01):
    """
    Time shift between two curves by normalised cross-correlation of the mean-removed curves on a
    uniform grid (Pearson correlation over the overlapping samples at every lag, lags limited to
    +-max_lag), refined to sub-sample precision with a parabola through the peak.
    roi = (t0, t1) restricts the reference to that window (reference time base); the current curve
    may extend max_lag beyond it.  Among correlation peaks within 0.005 of the best one, the
    smallest |shift| wins (periodic signals).  Lags with less than half of the largest overlap are
    ignored.
    SIGN: 'shift' is the value to ADD to cur.time_offset so that cur lines up with ref
    (if cur(t) = ref(t - 2) then shift = -2).
    Returns dict(shift, corr, n, at_limit, lags, ncc); shift / corr are NaN when not computable.
    """
    nan_res = {'shift': float('nan'), 'corr': float('nan'), 'n': 0, 'at_limit': False,
               'lags': np.empty(0), 'ncc': np.empty(0)}
    lo, hi = _roi_bounds(roi)
    r0, r1 = _span(ref)
    t0, t1 = max(lo, r0), min(hi, r1)
    if not (np.isfinite(t0) and np.isfinite(t1)) or t1 <= t0:
        return nan_res
    dt = _grid_dt(t0 - max_lag, t1 + max_lag, dt)
    tg, dt, k0 = _grid(t0, t1, dt)
    N = tg.size
    if N < 10:
        return nan_res
    m = max(1, int(math.ceil(abs(float(max_lag)) / dt)))
    tc = (k0 - m + np.arange(N + 2 * m, dtype=float)) * dt
    r = sample(ref, axis, tg)
    c = sample(cur, axis, tc)
    mr, mc = np.isfinite(r), np.isfinite(c)
    if mr.sum() < 10 or mc.sum() < 10:
        return nan_res
    rz = np.where(mr, r - np.mean(r[mr]), 0.0)
    cz = np.where(mc, c - np.mean(c[mc]), 0.0)
    fr, fc = mr.astype(float), mc.astype(float)
    n = np.rint(_xcorr_valid(fc, fr))
    s_r = _xcorr_valid(fc, rz)
    s_c = _xcorr_valid(cz, fr)
    s_rr = _xcorr_valid(fc, rz * rz)
    s_cc = _xcorr_valid(cz * cz, fr)
    s_rc = _xcorr_valid(cz, rz)
    with np.errstate(invalid='ignore', divide='ignore'):
        nn = np.where(n > 0, n, np.nan)
        cov = s_rc - s_r * s_c / nn
        vr = s_rr - s_r * s_r / nn
        vc = s_cc - s_c * s_c / nn
        scale_r = np.nanmax(s_rr) if np.any(np.isfinite(s_rr)) else 0.0
        scale_c = np.nanmax(s_cc) if np.any(np.isfinite(s_cc)) else 0.0
        ok = (n >= max(10.0, 0.5 * float(np.max(n)))) & (vr > 1e-12 * max(scale_r, 1e-300)) \
            & (vc > 1e-12 * max(scale_c, 1e-300))
        ncc = np.where(ok, cov / np.sqrt(np.abs(vr * vc)), np.nan)
    lags = (m - np.arange(2 * m + 1, dtype=float)) * dt          # shift of each q
    if not np.any(np.isfinite(ncc)):
        return nan_res
    y = np.where(np.isfinite(ncc), ncc, -np.inf)
    left = np.concatenate(([-np.inf], y[:-1]))
    right = np.concatenate((y[1:], [-np.inf]))
    cand = np.flatnonzero(np.isfinite(y) & (y >= left) & (y >= right))
    best = float(np.max(y))
    near = cand[y[cand] >= best - 0.005]
    q = int(near[np.argmin(np.abs(lags[near]))]) if near.size else int(np.argmax(y))
    delta, peak = 0.0, float(y[q])
    at_limit = q == 0 or q == y.size - 1 or not (np.isfinite(y[q - 1]) and np.isfinite(y[q + 1]))
    if not at_limit:
        ym, y0, yp = y[q - 1], y[q], y[q + 1]
        den = ym - 2.0 * y0 + yp
        if den < 0.0:
            delta = float(np.clip(0.5 * (ym - yp) / den, -0.5, 0.5))
            peak = float(y0 - 0.25 * (ym - yp) * delta)
    shift = (m - (q + delta)) * dt
    return {'shift': float(shift), 'corr': float(min(peak, 1.0)), 'n': int(n[q]),
            'at_limit': bool(at_limit), 'lags': lags, 'ncc': ncc}


def _stats(x):
    n = int(x.size)
    if n == 0:
        nan = float('nan')
        return {'n': 0, 'mean': nan, 'std': nan, 'rms': nan, 'max_abs': nan, 'p95_abs': nan}
    ax = np.abs(x)
    return {
        'n': n,
        'mean': float(np.mean(x)),
        'std': float(np.std(x, ddof=1)) if n >= 2 else 0.0,
        'rms': float(np.sqrt(np.mean(x * x))),
        'max_abs': float(np.max(ax)),
        'p95_abs': float(np.percentile(ax, 95)),
    }


def compare(ref, cur, axis, roi=None, dt=0.01):
    """
    Difference cur - ref (offsets applied) on a uniform grid over the overlap of both curves (and
    the ROI).  Returns dict(n, mean, std (ddof=1), rms, max_abs, p95_abs, corr, t, diff, ref_v,
    cur_v); t / diff / ref_v / cur_v cover the whole overlap grid with NaN where either curve has
    no data (connection gaps), n and the statistics use the valid points only.
    """
    lo, hi = _roi_bounds(roi)
    a0, a1 = _span(ref)
    b0, b1 = _span(cur)
    t0, t1 = max(lo, a0, b0), min(hi, a1, b1)
    tg, _, _ = _grid(t0, t1, dt)
    r = sample(ref, axis, tg)
    c = sample(cur, axis, tg)
    ok = np.isfinite(r) & np.isfinite(c)
    diff = np.where(ok, c - r, np.nan)
    res = _stats(diff[ok])
    corr = float('nan')
    if ok.sum() >= 2:
        rv, cv = r[ok], c[ok]
        if np.std(rv) > 0.0 and np.std(cv) > 0.0:
            corr = float(np.corrcoef(rv, cv)[0, 1])
    res.update({'corr': corr, 't': tg, 'diff': diff, 'ref_v': r, 'cur_v': c})
    return res


def ensemble(curves, axis, roi=None, dt=0.01, k=2.0):
    """
    Point-wise statistics of several curves on a common grid (union of their spans, ROI applied),
    NaN-aware: each time uses the curves that cover it.  Returns dict(t, mean, std (ddof=1, NaN
    where fewer than 2 curves), lo = mean - k*std, hi = mean + k*std, vmin, vmax (envelope), n
    (curves per time), std_mean, std_max (over the grid), names (curves used)).  Curves without
    the axis are skipped.
    """
    used = [c for c in curves if c.has(axis)]
    nan = float('nan')
    empty = np.empty(0)
    if not used:
        return {'t': empty, 'mean': empty, 'std': empty, 'lo': empty, 'hi': empty, 'vmin': empty,
                'vmax': empty, 'n': np.empty(0, dtype=int), 'std_mean': nan, 'std_max': nan,
                'names': []}
    lo, hi = _roi_bounds(roi)
    spans = [_span(c) for c in used]
    t0 = max(lo, min(s[0] for s in spans))
    t1 = min(hi, max(s[1] for s in spans))
    tg, _, _ = _grid(t0, t1, dt)
    V = np.vstack([sample(c, axis, tg) for c in used]) if tg.size else np.empty((len(used), 0))
    fin = np.isfinite(V)
    n = fin.sum(axis=0)
    with np.errstate(invalid='ignore', divide='ignore'):
        mean = np.where(n > 0, np.where(fin, V, 0.0).sum(axis=0) / np.maximum(n, 1), np.nan)
        dev = np.where(fin, V - mean, 0.0)
        std = np.where(n >= 2, np.sqrt((dev * dev).sum(axis=0) / np.maximum(n - 1, 1)), np.nan)
    vmin = np.where(n > 0, np.where(fin, V, np.inf).min(axis=0), np.nan) if tg.size else empty
    vmax = np.where(n > 0, np.where(fin, V, -np.inf).max(axis=0), np.nan) if tg.size else empty
    sf = std[np.isfinite(std)]
    return {
        't': tg, 'mean': mean, 'std': std, 'lo': mean - k * std, 'hi': mean + k * std,
        'vmin': vmin, 'vmax': vmax, 'n': n.astype(int),
        'std_mean': float(np.mean(sf)) if sf.size else nan,
        'std_max': float(np.max(sf)) if sf.size else nan,
        'names': [c.name for c in used],
    }


# ----------------------------------------------------------------------------
# Peaks and periods
# ----------------------------------------------------------------------------
def _uniform(curve, axis, roi, dt):
    """Uniform grid over the curve span inside the ROI and the curve sampled on it (no gap NaN)."""
    lo, hi = _roi_bounds(roi)
    a, b = _span(curve)
    tg, dt, _ = _grid(max(lo, a), min(hi, b), dt)
    return tg, sample(curve, axis, tg, gaps_as_nan=False), dt


def find_peaks_curve(curve, axis, roi=None, prominence=None, min_distance_s=0.5, kind='max'):
    """
    Peaks of curve[axis] (offsets applied) inside the ROI: kind 'max' | 'min' | 'both'.
    The curve is resampled linearly on a 10 ms grid, so staircase plateaus become flat tops and the
    peak is reported at the middle of the plateau.  prominence None -> 10 % of the value range in
    the ROI; peaks closer than min_distance_s keep the larger one.  Returns dict(t, v, kind) with
    times in the curve's offset time base, sorted by time (kind is a list of 'max' / 'min').
    """
    if kind not in ('max', 'min', 'both'):
        raise ValueError("kind must be 'max', 'min' or 'both'")
    tg, y, dt = _uniform(curve, axis, roi, 0.01)
    out = {'t': np.empty(0), 'v': np.empty(0), 'kind': []}
    fin = np.isfinite(y)
    if fin.sum() < 3:
        return out
    tg, y = tg[fin], y[fin]
    rng = float(np.max(y) - np.min(y))
    if rng <= 0.0:
        return out
    prom = 0.1 * rng if prominence is None else float(prominence)
    dist = max(1, int(round(float(min_distance_s or 0.0) / dt)))
    found = []
    if kind in ('max', 'both'):
        idx, _ = signal.find_peaks(y, prominence=prom, distance=dist)
        found += [(i, 'max') for i in idx]
    if kind in ('min', 'both'):
        idx, _ = signal.find_peaks(-y, prominence=prom, distance=dist)
        found += [(i, 'min') for i in idx]
    found.sort(key=lambda p: p[0])
    if not found:
        return out
    ii = np.array([p[0] for p in found], dtype=int)
    return {'t': tg[ii], 'v': y[ii], 'kind': [p[1] for p in found]}


def period_stats(peak_times):
    """Period statistics from consecutive peak time differences: dict(n = number of periods, mean,
    std (ddof=1, 0 for one period), min, max, freq = 1/mean, periods); NaN when < 2 peaks."""
    p = np.asarray(peak_times, dtype=float).ravel()
    p = np.sort(p[np.isfinite(p)])
    nan = float('nan')
    if p.size < 2:
        return {'n': 0, 'mean': nan, 'std': nan, 'min': nan, 'max': nan, 'freq': nan,
                'periods': np.empty(0)}
    d = np.diff(p)
    mean = float(np.mean(d))
    return {
        'n': int(d.size), 'mean': mean,
        'std': float(np.std(d, ddof=1)) if d.size >= 2 else 0.0,
        'min': float(np.min(d)), 'max': float(np.max(d)),
        'freq': 1.0 / mean if mean > 0.0 else nan,
        'periods': d,
    }


def dominant_period(curve, axis, roi=None, dt=0.01, min_period=0.2, max_period=None):
    """
    Dominant period of curve[axis] in the ROI from the autocorrelation of the linearly detrended
    signal on a uniform grid: at every lag the Pearson correlation of the signal with itself shifted
    by that lag (overlapping part only, so short windows and trends do not bias the peak).  The
    period is the first autocorrelation peak between min_period and max_period (default half the
    ROI length) with a prominence of at least 0.05 that reaches 80 % of the highest such peak,
    refined with a parabola.  Returns dict(period, freq, strength = autocorrelation at the peak,
    -1..1); NaN when there is no peak.
    """
    nan = float('nan')
    res = {'period': nan, 'freq': nan, 'strength': nan}
    tg, y, dt = _uniform(curve, axis, roi, dt)
    fin = np.isfinite(y)
    if fin.sum() < 8:
        return res
    tg, y = tg[fin], y[fin]
    x = signal.detrend(y, type='linear')
    x = x - np.mean(x)
    N = x.size
    if not np.any(np.abs(x) > 1e-12 * max(1.0, float(np.max(np.abs(y))))):
        return res
    nfft = 1 << int(2 * N - 1).bit_length()
    F = np.fft.rfft(x, nfft)
    s_ab = np.fft.irfft(F * np.conj(F), nfft)[:N]                # sum x[i] x[i+k]
    cs = np.concatenate(([0.0], np.cumsum(x)))
    cs2 = np.concatenate(([0.0], np.cumsum(x * x)))
    k_all = np.arange(N)
    nk = (N - k_all).astype(float)
    s_a, s_b = cs[N - k_all], cs[N] - cs[k_all]
    s_aa, s_bb = cs2[N - k_all], cs2[N] - cs2[k_all]
    with np.errstate(invalid='ignore', divide='ignore'):
        var = (s_aa - s_a * s_a / nk) * (s_bb - s_b * s_b / nk)
        acf = np.where(var > 0.0, (s_ab - s_a * s_b / nk) / np.sqrt(np.abs(var)), np.nan)
    span = float(tg[-1] - tg[0])
    kmax = int(math.floor((max_period if max_period is not None else span / 2.0) / dt))
    kmin = max(1, int(math.ceil(float(min_period or 0.0) / dt)))
    kmax = min(kmax, N - 5)
    if kmax <= kmin + 1:
        return res
    seg = np.nan_to_num(acf[:kmax + 2], nan=-1.0)
    acf = np.nan_to_num(acf, nan=-1.0)
    idx, _ = signal.find_peaks(seg, prominence=0.05)
    idx = idx[(idx >= kmin) & (idx <= kmax)]
    if idx.size == 0:
        return res
    h = seg[idx]
    best = float(np.max(h))
    if best <= 0.0:
        return res
    k = int(idx[np.flatnonzero(h >= 0.8 * best)[0]])
    ym, y0, yp = acf[k - 1], acf[k], acf[k + 1]
    den = ym - 2.0 * y0 + yp
    delta = float(np.clip(0.5 * (ym - yp) / den, -0.5, 0.5)) if den < 0.0 else 0.0
    period = (k + delta) * dt
    return {'period': float(period), 'freq': 1.0 / period, 'strength': float(min(y0, 1.0))}


# ----------------------------------------------------------------------------
# Movement detection
# ----------------------------------------------------------------------------
def _range_minmax(v, lo, hi):
    """Max and min of v[lo[i]:hi[i] + 1] for every i (sparse table, vectorised)."""
    L = hi - lo + 1
    levels = int(np.max(L)).bit_length()
    mx, mn = [v], [v]
    for kk in range(1, levels):
        h = 1 << (kk - 1)
        mx.append(np.maximum(mx[-1][:-h], mx[-1][h:]))
        mn.append(np.minimum(mn[-1][:-h], mn[-1][h:]))
    lev = np.frexp(L.astype(float))[1] - 1                 # floor(log2(L))
    rmax = np.empty(v.size)
    rmin = np.empty(v.size)
    for kk in np.unique(lev):
        sel = lev == kk
        a = lo[sel]
        b = hi[sel] - (1 << int(kk)) + 1
        rmax[sel] = np.maximum(mx[kk][a], mx[kk][b])
        rmin[sel] = np.minimum(mn[kk][a], mn[kk][b])
    return rmax, rmin


def _tolerance(thr):
    """Threshold with a float tolerance (values exactly 'threshold' apart count as within it)."""
    return thr * (1.0 + 1e-9) + 1e-12


_REST_TOL_MAX = 0.003     # units; cap of the 'still at the rest value' noise tolerance (logs round to 0.001)
_DRIFT_FRAC = 0.25        # a settled window changes by at most this fraction of the threshold ...
_DRIFT_MAX = 0.005        # units; ... and by at most this much (0.01 units/s over a 0.5 s settle_time)
_APPROACH_HOLD = 0.8      # fraction of settle_time a value must be held after a last approach step
_HOLD_FLOOR_MAX = 0.5     # s; cap of the staircase hold floor (_hold_floor) ...
_FLOOR_MIN_SETTLE = 0.75  # ... used from a settle_time of this fraction of the refresh interval
_DTC_MOVING_MAX = 1.0     # s; value-change intervals at least this long are rests, not refreshes
_NOISE_MAD_K = 3.0        # noisy logs: the rest tolerance is at least this many MAD of the rest steps ...
_NOISE_REST_FRAC = 0.5    # ... but at most this fraction of the threshold
_NOISE_MIN_STEPS = 20     # steps between rest samples needed for that noise estimate


def _rest_tol(thr):
    """Noise tolerance of 'at the rest value' (movement start / stop sample): min(thr / 4, 0.003)."""
    return _tolerance(min(0.25 * thr, _REST_TOL_MAX))


def _drift_tol(thr):
    """Largest net change of a settled window: min(thr / 4, 0.005), with the float tolerance.  The
    cap keeps it independent of a large threshold, so slow ramps stay one movement for any band."""
    return _tolerance(min(_DRIFT_FRAC * thr, _DRIFT_MAX))


def _hold_floor(t, dtc, settle):
    """Longest time a staircase log can show one value while it moves: the position refresh
    interval (dtc, the median interval between value changes while moving, i.e. intervals under
    _DTC_MOVING_MAX = 1 s, so rests in sparse logs do not inflate it; ~0.2 s for the Duet) plus the row
    spacing (99th percentile), at most _HOLD_FLOOR_MAX (0.5 s); ~0.34 s for 50-140 ms rows.
    0 when settle is shorter than _FLOOR_MIN_SETTLE * dtc: a settle_time below the refresh
    interval asks for the staircase steps themselves (every hold is then a stop)."""
    if t.size < 3 or not np.isfinite(dtc) or dtc <= 0.0 or settle < _FLOOR_MIN_SETTLE * dtc:
        return 0.0
    return float(min(dtc + float(np.percentile(np.diff(t), 99)), _HOLD_FLOOR_MAX))


def _noise_rest_tol(v, settled, e, thr):
    """Rest tolerance of noisy data: _NOISE_MAD_K (3) * the noise of the sample-to-sample steps
    inside the settled windows (rest samples), at most _NOISE_REST_FRAC * thr (thr / 2); 0 when
    there are fewer than _NOISE_MIN_STEPS (20) such steps.  The step noise is the MAD of the second
    differences / sqrt(3) (= the MAD of the steps for white noise), so a slow ramp or a smooth
    curve inside the window does not count as noise.  A firmware log (noise-free staircase: most
    steps are 0) gives 0, so it keeps _rest_tol."""
    js = np.flatnonzero(settled)
    n = v.size
    if js.size == 0 or n < 3:
        return 0.0
    mark = np.zeros(n + 1, dtype=np.int64)
    np.add.at(mark, js, 1)
    np.add.at(mark, np.minimum(e[js], n - 1) + 1, -1)
    inside = np.cumsum(mark[:n]) > 0
    d2 = np.diff(v, 2)[inside[:-2] & inside[1:-1] & inside[2:]]
    if d2.size < _NOISE_MIN_STEPS:
        return 0.0
    mad = float(np.median(np.abs(d2 - np.median(d2)))) / math.sqrt(3.0)
    return float(min(_NOISE_MAD_K * mad, _NOISE_REST_FRAC * thr))


def _windows(t, v, settle):
    """For every sample j: e[j] = last sample index inside [t[j], t[j] + settle] (>= j) and
    v_end[j] = curve value at t[j] + settle (linear between samples, clamped to the data)."""
    n = t.size
    te = t + settle
    e = np.searchsorted(t, te, side='right') - 1
    e = np.maximum(e, np.arange(n))
    nx = np.minimum(e + 1, n - 1)
    dt_next = t[nx] - t[e]
    with np.errstate(invalid='ignore', divide='ignore'):
        frac = np.where((nx > e) & (dt_next > 0.0), (te - t[e]) / dt_next, 0.0)
    v_end = v[e] + np.clip(frac, 0.0, 1.0) * (v[nx] - v[e])
    return te, e, v_end


def _settled_mask(t, v, thr, settle, win=None, floor=0.0):
    """settled[j]: over [t[j], t[j] + settle] (a window inside the data) the curve, linear between
    samples, stays within thr of v[j] AND its net change is small: the last sample inside the
    window differs from v[j] by at most dl = min(thr / 4, 0.005) (_drift_tol), or the window
    holds one last approach step: the first value change after j (inside the window) leads to a
    value that the rest of the window keeps within dl and that is held within the rest tolerance
    (_rest_tol) for at least _APPROACH_HOLD * settle (80 %), or max(that, floor) when settle < floor.
    The net-change rule keeps slow ramps (e.g. 0.05 mm/s logged as a 200 ms staircase of 0.01 mm
    steps, a new value at least every ~0.34 s) from looking settled on every hold, while a real
    stop passes.  It is measured on a sample, not on the value interpolated at the window end, so
    the start of the next movement right after a short stop only has to stay inside the
    threshold band; the approach-step case lets the last staircase sample before the final value
    start the stop window, as without the rule.
    floor (s, staircase logs: _hold_floor, ~0.34 s): the longest a value can be held mid-ramp.  When
    settle is shorter, the window could hold a single staircase value, so the net change is also
    measured at t[j] + floor (interpolated), and an approach step must be followed by a value held
    for at least floor; settle >= floor is unaffected.  Limit: with settle < floor, a real stop
    not much longer than the floor (up to about floor + one refresh, ~0.35-0.55 s) cannot be told
    apart from a staircase hold and is missed about half the time; use settle >= 0.4 s to
    resolve such short stops."""
    n = t.size
    idx = np.arange(n)
    te, e, v_end = win if win is not None else _windows(t, v, settle)
    wmax, wmin = _range_minmax(v, idx, e)
    wmax = np.maximum(wmax, v_end)
    wmin = np.minimum(wmin, v_end)
    tol = _tolerance(thr)
    dl = _drift_tol(thr)
    floor = max(0.0, float(floor or 0.0))
    inside = te <= t[-1] + 1e-12
    band = inside & (wmax - v <= tol) & (v - wmin <= tol)
    drift_ok = np.abs(v[e] - v) <= dl
    if floor > settle:
        drift_ok &= np.abs(_windows(t, v, floor)[2] - v) <= dl
    cps = np.flatnonzero(np.diff(v) != 0.0) + 1          # samples where the value changes
    if cps.size:
        q = np.searchsorted(cps, idx, side='right')
        k1 = cps[np.minimum(q, cps.size - 1)]           # first change after each sample
        hold = _APPROACH_HOLD * settle if settle >= floor else max(_APPROACH_HOLD * settle, floor)
        te8, e8, v_end8 = _windows(t, v, hold)
        hmax, hmin = _range_minmax(v, idx, e8)
        hmax = np.maximum(hmax, v_end8)
        hmin = np.minimum(hmin, v_end8)
        rt = _rest_tol(thr)
        held = (te8 <= t[-1] + 1e-12) & (hmax - v <= rt) & (v - hmin <= rt)
        drift_ok |= (q < cps.size) & (k1 <= e) & held[k1] & (np.abs(v[e] - v[k1]) <= dl)
    return band & drift_ok


def _last_within(v, lo, hi, level, tol):
    """Largest k in [lo, hi] with |v[k] - level| <= tol, or None."""
    if hi < lo:
        return None
    idx = np.flatnonzero(np.abs(v[lo:hi + 1] - level) <= tol)
    return lo + int(idx[-1]) if idx.size else None


def _first_at_final(v, lo, j, hi, level, tol):
    """Stop sample: when v[j] (first settled sample) is within tol of level, the first sample of
    the run of samples within tol that ends at j (searching back to lo); otherwise the first
    sample after j, up to hi (end of the settled window), that is within tol (j when none is)."""
    if abs(v[j] - level) <= tol:
        if j <= lo:
            return j
        bad = np.flatnonzero(np.abs(v[lo:j + 1] - level) > tol)
        return lo if bad.size == 0 else min(j, lo + int(bad[-1]) + 1)
    ok = np.flatnonzero(np.abs(v[j + 1:hi + 1] - level) <= tol)
    return j + 1 + int(ok[0]) if ok.size else j


def _first_exceed(v, start, ref, thr):
    """First index >= start with |v - ref| > thr (chunked search), or None."""
    n = v.size
    pos, step = start, 256
    while pos < n:
        end = min(n, pos + step)
        seg = np.abs(v[pos:end] - ref) > thr
        k = int(np.argmax(seg))
        if seg[k]:
            return pos + k
        pos, step = end, step * 2
    return None


def _peak_speed(t, v, s, j, cps, dtc, staircase):
    """Peak |speed| between samples s and j.  Staircase (log) data: from the first sample of each
    new value (de-staircased), the first step taking at least one refresh interval dtc."""
    if j <= s:
        return 0.0
    if not staircase:
        dv = np.abs(np.diff(v[s:j + 1]))
        dtt = np.diff(t[s:j + 1])
        return float(np.max(dv / dtt)) if dv.size else 0.0
    a = int(np.searchsorted(cps, s, side='right'))
    b = int(np.searchsorted(cps, j, side='right'))
    inside = cps[a:b]
    if inside.size == 0:
        return 0.0
    prev_cp = cps[a - 1] if a > 0 else 0
    t1 = t[inside[0]]
    dt0 = min(t1 - t[prev_cp], max(t1 - t[s], dtc))
    speeds = [abs(v[inside[0]] - v[s]) / dt0 if dt0 > 0 else 0.0]
    if inside.size > 1:
        speeds.extend(np.abs(np.diff(v[inside])) / np.diff(t[inside]))
    return float(np.max(speeds))


def _value_changes(t, v):
    """(cps, dtc) of a sampled curve: cps = sample 0 and every sample whose value differs from the
    previous one; dtc = the position refresh interval, the median interval between those samples
    while moving (intervals under _DTC_MOVING_MAX; all of them when there are none; the median row
    spacing when the value never changes).  Used by detect_movements and movement_stats (peak speed
    of staircase logs, staircase hold floor)."""
    cps = np.concatenate(([0], np.flatnonzero(np.diff(v) != 0.0) + 1))
    dcp = np.diff(t[cps])
    dcp_moving = dcp[dcp < _DTC_MOVING_MAX]    # value-change intervals while moving (rests excluded)
    if dcp_moving.size:
        dtc = float(np.median(dcp_moving))
    else:
        dtc = float(np.median(dcp)) if dcp.size else float(np.median(np.diff(t)))
    return cps, dtc


def _movement_gap_flags(t_start, t_stop, spans, settled=True, t_last=None):
    """(in_gap, start_in_gap, stop_in_gap) of a movement [t_start, t_stop] against the connection
    gaps spans = gap_spans(curve): in_gap when it overlaps or touches a gap, start_in_gap /
    stop_in_gap when that time lies in a gap (a sample bounding it included).  A movement whose stop
    is not settled (the data ends while it moves) with a gap starting between t_stop and t_last, the
    last sample, is in_gap and stop_in_gap too (the connection was lost for good while moving)."""
    in_gap = any(t_start <= b + _EPS_T and t_stop >= a - _EPS_T for a, b in spans)
    start_in = any(a - _EPS_T <= t_start <= b + _EPS_T for a, b in spans)
    stop_in = any(a - _EPS_T <= t_stop <= b + _EPS_T for a, b in spans)
    if not settled and t_last is not None and any(t_stop - _EPS_T <= a <= t_last + _EPS_T for a, _ in spans):
        # not settled before the data ends, and a gap starts between t_stop and the last sample
        # (e.g. the connection was lost for good during the movement): the stop may be in it
        in_gap = stop_in = True
    return bool(in_gap), bool(start_in), bool(stop_in)


def _nearest_index(tt, t):
    """Index of the sample of the (increasing) times tt nearest to t; a tie goes to the earlier one."""
    i = int(np.searchsorted(tt, float(t)))
    if i >= tt.size:
        return int(tt.size - 1)
    if i > 0 and abs(float(t) - tt[i - 1]) <= abs(tt[i] - float(t)):
        return i - 1
    return i


def detect_movements(curve, axis, roi=None, threshold=0.02, settle_time=0.5, min_duration=0.0,
                     merge_gap=0.0):
    """
    Movements of curve[axis] inside the ROI (offset time base).

    A movement starts when the value leaves the rest value by more than threshold; t_start is the
    time of the last sample still AT the rest value (within a noise tolerance of
    min(threshold / 4, 0.003)).  The rest value is taken just before the movement: the median of
    the samples over settle_time up to the last settled sample before it (those within that
    tolerance of it), and t_start is not searched before that window, so a sub-threshold step
    earlier in a long rest does not pull t_start back to that step.  The movement stops when the
    value settles: for at least settle_time it stays within threshold of a new value AND its net
    change over the window is at most min(threshold / 4, 0.005) (see _settled_mask; one last
    approach step is allowed when the new value is then held; for the default settle_time 0.5 s
    the cap is a minimum speed of ~0.01 units/s whatever the threshold), so slow ramps (e.g.
    0.05 mm/s logged as a 200 ms staircase of 0.01 mm steps) are one movement.  t_stop is the
    first sample at the new rest value (same noise tolerance; after an approach step, the value
    held after it).  The curve is linear between samples; a reference is evaluated at its rows,
    which is exact for a piecewise-linear curve.
    Staircase holds shorter than settle_time do not split a movement.  Movements separated by less
    than merge_gap are merged first, then movements shorter than min_duration are dropped.
    Staircase logs: when settle_time is shorter than the longest a value can be held while the
    axis moves (refresh interval + row spacing, ~0.34 s for 50-140 ms rows, at most 0.5 s;
    _hold_floor), the net change is also checked over that hold floor, so a slow ramp is not
    split at every staircase hold (a stop shorter than the floor is then not seen as a stop).
    Noisy logs: the 'at the rest value' tolerance of t_start / t_stop (and of the rest value)
    becomes 3 x the sample-to-sample noise at rest (MAD of the second differences inside the
    settled windows; at most threshold / 2), so noise does not pull t_start early or push t_stop
    to the first settled window; the net-change cap of the settled test stays noise-free (at the
    noise level it would split noisy slow ramps).  Firmware logs are noise-free (MAD 0) and keep
    the tolerances above.
    Returns a list of dict(t_start, t_stop, duration, v_start, v_stop, delta, peak_speed,
    complete, in_gap, start_in_gap, stop_in_gap).  in_gap is True when [t_start, t_stop] overlaps
    or touches a connection gap of the log (gap_spans); start_in_gap / stop_in_gap when t_start /
    t_stop is a sample bounding a gap (the start / stop may have happened somewhere in it).  A
    movement that does not settle before the data ends, with a gap starting between t_stop and
    the last sample (connection lost for good while moving), is in_gap and stop_in_gap too.
    complete is False for in_gap movements, and when the data (or ROI) ends before the stop is
    confirmed.
    peak_speed (units/s) of a log is computed from the first sample of each new value, so the
    ~200 ms position refresh does not inflate it.
    """
    tt = curve.times()
    vv = curve.values(axis)
    m = roi_mask(tt, roi)
    fin = np.isfinite(vv)
    if not fin.all():                      # samples without a value (aligned export read back) are left out
        m &= fin
    t, v = tt[m], vv[m]
    n = t.size
    if n < 2:
        return []
    thr = abs(float(threshold))
    tol = _tolerance(thr)                  # same float tolerance for 'left the rest' and 'settled'
    rtol = _rest_tol(thr)                  # 'still / already at the rest value'
    dtol = _drift_tol(thr)
    settle = max(0.0, float(settle_time or 0.0))
    cps, dtc = _value_changes(t, v)
    staircase = curve.kind != 'reference'
    floor = _hold_floor(t, dtc, settle) if staircase else 0.0      # longest staircase hold while moving
    win = _windows(t, v, settle)
    e_win = win[1]
    settled = _settled_mask(t, v, thr, settle, win=win, floor=floor)
    if staircase:
        # noisy log: 'at the rest value' within the noise (the start / stop search would otherwise
        # stop at the first noisy sample: t_start early, t_stop late up to the first settled
        # sample); the settled test keeps its noise-free net-change cap, so noisy slow ramps are
        # still one movement
        noise = _noise_rest_tol(v, settled, e_win, thr)
        if noise > rtol:
            rtol = _tolerance(noise)
    settled_idx = np.flatnonzero(settled)
    smax = np.maximum.accumulate(v[::-1])[::-1]
    smin = np.minimum.accumulate(v[::-1])[::-1]
    tail_ok = (smax - v <= tol) & (v - smin <= tol) & (np.abs(v[-1] - v) <= dtol)

    segs = []
    a, v_rest, q_prev = 0, v[0], 0
    while True:
        i = _first_exceed(v, a + 1, v_rest, tol)
        if i is None:
            break
        # start: last sample still at the rest value (not merely inside the threshold band).  The
        # rest value is local: the median of the samples within the rest tolerance of v[ks] over
        # settle_time up to the last settled sample ks before i (a sub-threshold step earlier in a
        # long rest moves it; looking back from ks keeps the first sub-threshold steps of a slow
        # ramp out of it; sparse reference rows give v[ks]), and the search does not go back
        # beyond that window.
        k = int(np.searchsorted(settled_idx, i, side='left')) - 1
        if k >= 0 and settled_idx[k] >= a:
            ks = int(settled_idx[k])
            lo = max(a, int(np.searchsorted(t, t[ks] - settle, side='left')))
            near_rest = v[lo:ks + 1]
            level = float(np.median(near_rest[np.abs(near_rest - v[ks]) <= rtol]))
        else:
            lo, level = a, float(v[a])
        s = _last_within(v, lo, i - 1, level, rtol)
        if s is None:
            s = lo
        s = min(max(s, q_prev), i - 1)          # never before the previous stop
        k = int(np.searchsorted(settled_idx, i, side='left'))
        if k < settled_idx.size:
            j, complete = int(settled_idx[k]), True
            hi = int(e_win[j])
        else:
            j, complete = i + int(np.argmax(tail_ok[i:])), False
            hi = n - 1
        base = j
        if complete and abs(v[hi] - v[j]) > dtol:
            # settled through a last approach step (_settled_mask): the new rest value is the one
            # held after that step
            nz = np.flatnonzero(v[j + 1:hi + 1] != v[j])
            if nz.size:
                base = j + 1 + int(nz[0])
        final = float(np.median(v[base:hi + 1]))
        # stop: first sample at the new rest value (j = first settled sample, which can still be
        # up to threshold / 4 short of it at the end of a slow ramp)
        q = _first_at_final(v, s + 1, base, hi, final, rtol)
        segs.append({
            't_start': float(t[s]), 't_stop': float(t[q]),
            'v_start': float(v[s]), 'v_stop': float(v[q]),
            'peak_speed': _peak_speed(t, v, s, q, cps, dtc, staircase),
            'complete': complete,
        })
        if not complete:
            break
        a, v_rest, q_prev = base, v[base], q

    merged = []
    gap = max(0.0, float(merge_gap or 0.0))
    for sg in segs:
        if merged and gap > 0.0 and sg['t_start'] - merged[-1]['t_stop'] < gap:
            last = merged[-1]
            last['t_stop'] = sg['t_stop']
            last['v_stop'] = sg['v_stop']
            last['peak_speed'] = max(last['peak_speed'], sg['peak_speed'])
            last['complete'] = sg['complete']
        else:
            merged.append(dict(sg))
    out = []
    min_d = max(0.0, float(min_duration or 0.0))
    spans = gap_spans(curve)
    t_last = float(t[-1])
    for sg in merged:
        dur = sg['t_stop'] - sg['t_start']
        if dur < min_d:
            continue
        in_gap, start_in, stop_in = _movement_gap_flags(sg['t_start'], sg['t_stop'], spans,
                                                        settled=sg['complete'], t_last=t_last)
        out.append({
            't_start': sg['t_start'], 't_stop': sg['t_stop'], 'duration': float(dur),
            'v_start': sg['v_start'], 'v_stop': sg['v_stop'],
            'delta': float(sg['v_stop'] - sg['v_start']),
            'peak_speed': sg['peak_speed'], 'complete': bool(sg['complete'] and not in_gap),
            'in_gap': bool(in_gap), 'start_in_gap': bool(start_in), 'stop_in_gap': bool(stop_in),
        })
    return out


def movement_stats(curve, axis, t_start, t_stop, roi=None):
    """
    Numbers of a movement of curve[axis] given by its start and stop (offset time base, e.g. a
    movement edited by hand), with the keys of a detect_movements dict: t_start, t_stop (as given),
    duration, v_start / v_stop (value of the sample nearest to t_start / t_stop, offsets applied),
    delta, peak_speed, complete, in_gap, start_in_gap, stop_in_gap.
    peak_speed is computed as detect_movements does between those two samples (staircase logs:
    from the first sample of each new value, so the ~200 ms position refresh does not inflate it;
    a reference at its rows).  The gap flags follow the rules of detect_movements (gap_spans; the
    stop is taken as given, i.e. settled).  complete is False when a gap is involved or when
    t_start / t_stop lies outside the data (so it differs from detect_movements only for a movement
    that did not settle before the data or ROI ends, which detect_movements marks incomplete).
    roi: the region detect_movements was given (it evaluates the refresh interval of a staircase
    log and the end of the data inside it); with the same roi a detected movement gives exactly its
    detect_movements numbers (merge_gap 0: a merged movement keeps the largest peak speed of its
    parts there).  None: the whole curve.
    ValueError for non-finite times, t_stop < t_start or no samples (in the roi).
    """
    a, b = float(t_start), float(t_stop)
    if not (math.isfinite(a) and math.isfinite(b)):
        raise ValueError("t_start and t_stop must be finite numbers")
    if b < a:
        raise ValueError(f"t_stop ({b:.3f} s) is before t_start ({a:.3f} s)")
    tt = curve.times()
    vv = curve.values(axis)
    m = roi_mask(tt, roi)
    fin = np.isfinite(vv)
    if not fin.all():                      # samples without a value (aligned export read back) are left out
        m &= fin
    t, v = tt[m], vv[m]
    if t.size == 0:
        raise ValueError(f"{curve.name}: no samples" + (" in the ROI" if roi is not None else ""))
    s, q = _nearest_index(t, a), _nearest_index(t, b)
    staircase = curve.kind != 'reference'
    if t.size >= 2:
        cps, dtc = _value_changes(t, v)
        peak = _peak_speed(t, v, s, q, cps, dtc, staircase)
    else:
        peak = 0.0
    t_last = float(t[-1])
    in_gap, start_in, stop_in = _movement_gap_flags(a, b, gap_spans(curve), settled=True, t_last=t_last)
    outside = b > t_last + _EPS_T or a < float(t[0]) - _EPS_T
    v0, v1 = float(v[s]), float(v[q])
    return {
        't_start': a, 't_stop': b, 'duration': float(b - a),
        'v_start': v0, 'v_stop': v1, 'delta': float(v1 - v0),
        'peak_speed': float(peak), 'complete': bool(not (in_gap or outside)),
        'in_gap': in_gap, 'start_in_gap': start_in, 'stop_in_gap': stop_in,
    }


# ----------------------------------------------------------------------------
# Logged sensor waits: removal from the time axis, pairing with the G-code pauses
# ----------------------------------------------------------------------------
def wait_intervals(curve_or_waits):
    """Removed intervals [(start, stop, wait index)] of the logged waits of a log (a Curve, its
    meta, or a list of wait dicts): each wait's 'cut' ([received, end), see read_trace_log) in time
    order; overlapping ones are clipped to the end of the previous one, empty ones left out."""
    src = curve_or_waits
    if isinstance(src, Curve):
        src = src.meta
    waits = src.get('waits') if isinstance(src, dict) else src
    iv = []
    for i, w in enumerate(waits or []):
        cut = w.get('cut') if isinstance(w, dict) else None
        if cut is None and isinstance(w, dict):
            cut = (w.get('received'), w.get('end'))
        try:
            a, b = float(cut[0]), float(cut[1])
        except (TypeError, ValueError, IndexError):
            continue
        if not (math.isfinite(a) and math.isfinite(b)):
            continue
        iv.append((a, b, int(w.get('index', i)) if isinstance(w, dict) else i))
    iv.sort(key=lambda x: (x[0], x[1]))
    out, last = [], -np.inf
    for a, b, i in iv:
        a = max(a, last)
        if b > a:
            out.append((a, b, i))
            last = b
    return out


class CutMap:
    """Map between a log's recorded time and its time without the removed intervals ("cut time"):
    t -> t - (length removed before t); a time inside a removed interval [a, b) maps to that
    interval's cut point (a minus what was removed before it), the row at b (the trigger row) maps
    exactly onto the cut point.  inverse() is exact for times outside the removed intervals (the cut
    point itself maps back to b, the first kept time after the interval).  Vectorised: searchsorted
    only, so 100k rows cost well under a millisecond.  intervals: wait_intervals() (sorted, disjoint)."""

    def __init__(self, intervals):
        iv = [(float(a), float(b), int(i)) for a, b, i in intervals]
        self.intervals = iv
        self.a = np.array([x[0] for x in iv], dtype=float)
        self.b = np.array([x[1] for x in iv], dtype=float)
        self.index = [x[2] for x in iv]
        self.length = self.b - self.a
        self.cum = np.concatenate(([0.0], np.cumsum(self.length)))   # removed before interval k: cum[k]
        self.c = self.a - self.cum[:-1]                                  # cut points
        self.total = float(self.cum[-1])

    def __len__(self):
        return len(self.intervals)

    def __bool__(self):
        return bool(self.intervals)

    @staticmethod
    def _out(x, scalar):
        return float(x) if scalar else x

    def forward(self, t):
        """Recorded time(s) -> cut time(s)."""
        scalar = np.ndim(t) == 0
        t = np.asarray(t, dtype=float)
        if not self.intervals:
            return self._out(t.copy() if not scalar else t, scalar)
        k = np.searchsorted(self.a, t, side='right')           # intervals starting at or before t
        km = np.maximum(k - 1, 0)
        out = np.where(k > 0, self.c[km] + (t - self.b[km]), t)   # after interval k-1 (exact at b)
        inside = (k > 0) & (t < self.b[km])
        out = np.where(inside, self.c[km], out)
        return self._out(out, scalar)

    def inverse(self, x):
        """Cut time(s) -> recorded time(s) (the cut point -> the end of its interval)."""
        scalar = np.ndim(x) == 0
        x = np.asarray(x, dtype=float)
        if not self.intervals:
            return self._out(x.copy() if not scalar else x, scalar)
        j = np.searchsorted(self.c, x, side='right') - 1       # last cut point at or before x
        jm = np.maximum(j, 0)
        out = np.where(j >= 0, self.b[jm] + (x - self.c[jm]), x)
        return self._out(out, scalar)

    def inside(self, t):
        """True where a recorded time lies inside a removed interval [a, b)."""
        scalar = np.ndim(t) == 0
        t = np.asarray(t, dtype=float)
        if not self.intervals:
            out = np.zeros(t.shape, dtype=bool)
        else:
            k = np.searchsorted(self.a, t, side='right')
            out = (k > 0) & (t < self.b[np.maximum(k - 1, 0)])
        return bool(out) if scalar else out

    def cuts(self):
        """[(t_cut, length, wait index)] of the removed intervals."""
        return [(float(c), float(L), i) for c, L, i in zip(self.c, self.length, self.index)]


def cut_map(curve):
    """CutMap of a log's logged waits (meta['waits'])."""
    return CutMap(wait_intervals(curve))


def remove_waits(curve):
    """
    The log without its logged sensor waits (Remove mode of the Log files tab): the rows inside the
    removed intervals [received, end) of meta['waits'] are dropped (so no Probe -1000 row of a wait
    remains; the row at 'end', which ended the wait, stays) and every later time moves earlier by
    the length removed before it (CutMap.forward).  Gaps, End, release times, waits not marked and
    failed message reads are mapped the same way (a time inside a removed interval goes to its cut
    point).  time_offset / value_offsets are copied (display = cut(t) + offset).
    Extra meta keys of the new Curve: 'cut_map' (CutMap), 'cut_index' (indices of the kept rows in
    the recorded curve), 'cuts' [(t_cut, length, wait index)], 'waits_removed' (the recorded waits,
    each with 'cut_at'); 'waits' is [] (nothing left to remove).  A log without waits gives a
    copy with an empty CutMap.
    """
    cm = cut_map(curve)
    t = curve.t
    keep = ~cm.inside(t) if cm else np.ones(t.shape, dtype=bool)
    idx = np.flatnonzero(keep)
    t_new = cm.forward(t[idx]) if cm else t[idx].copy()
    if t_new.size > 1:
        ok = np.concatenate(([True], np.diff(t_new) > 0.0))     # (float rounding at a cut point)
        if not ok.all():
            idx, t_new = idx[ok], t_new[ok]
    data = {k: v[idx] for k, v in curve.data.items()}
    probe = curve.probe[idx] if curve.probe is not None else None
    meta = dict(curve.meta)
    f = cm.forward

    def fm(x):
        return None if x is None else float(f(float(x)))
    meta['gaps'] = [(fm(g[0]), fm(g[1]) if len(g) > 1 else None) for g in (curve.meta.get('gaps') or []) if g]
    end = curve.meta.get('end')
    if end and isinstance(end, (tuple, list)) and len(end) > 1:
        meta['end'] = (end[0], fm(end[1]))
    meta['release_times'] = [fm(x) for x in (curve.meta.get('release_times') or [])]
    meta['waits_not_marked'] = [dict(w, received=fm(w.get('received')), sent_from=fm(w.get('sent_from')))
                                for w in (curve.meta.get('waits_not_marked') or [])]
    meta['message_read_failures'] = [dict(w, t=fm(w.get('t')), sent_from=fm(w.get('sent_from')),
                                          sent_to=fm(w.get('sent_to')))
                                     for w in (curve.meta.get('message_read_failures') or [])]
    removed = []
    for w in curve.meta.get('waits') or []:
        w2 = dict(w)
        a = w.get('cut', (w.get('received'), w.get('end')))[0]
        w2['cut_at'] = fm(a)
        w2['sent_from_cut'] = fm(w.get('sent_from'))
        removed.append(w2)
    meta.update({'waits': [], 'waits_removed': removed, 'cuts': cm.cuts(), 'cut_map': cm, 'cut_index': idx,
                 'n': None, 'median_dt': None, 'all_zero_axes': None})
    c = Curve(name=curve.name, kind=curve.kind, path=curve.path, t=t_new, data=data, probe=probe, meta=meta,
              time_offset=curve.time_offset, value_offsets=dict(curve.value_offsets))
    return c


def logged_wait_items(curve):
    """The sensor waits a log knows of, marked and not marked, sorted by received: [dict(kind
    'marked' | 'not_marked', received, wait)] (wait = the meta dict)."""
    meta = curve.meta if isinstance(curve, Curve) else (curve or {})
    items = [{'kind': 'marked', 'received': float(w['received']), 'wait': w} for w in meta.get('waits') or []]
    items += [{'kind': 'not_marked', 'received': float(w['received']), 'wait': w}
              for w in meta.get('waits_not_marked') or []]
    items.sort(key=lambda x: x['received'])
    return items


def pair_pause_waits(ref_curve, log_curve):
    """
    The pauses of a G-code reference paired with the logged sensor waits of a log (no estimate):
    one dict per pause (G-code order) with label, t_gcode (parser time), length (s), kind
    ('marked' | 'not_marked' | 'none'), wait (the log's wait dict or None), ended_by, note.
    The 'sensor_wait' pauses are paired in order with the log's waits, marked and not marked, sorted
    by received.  A pause paired with a marked wait gets length = its cut length (end - received:
    exactly what remove_waits cuts); with a wait not marked 0 and a note; other pause kinds (M226 /
    M25 / M0 ...) 0 and the note 'not logged'.  When the numbers of sensor_wait pauses and logged
    waits differ, nothing is paired (every length 0, a note says why): which wait belongs to which
    pause would be a guess.  log_curve None or without waits: every length 0 (the G-code as is).
    """
    src = ref_curve.meta.get('_source') if isinstance(ref_curve.meta, dict) else None
    pauses = list(ref_curve.meta.get('pauses_gcode') or (src or {}).get('pauses') or
                  ref_curve.meta.get('pauses') or [])
    out = []
    for label, tp in pauses:
        sensor = str(label) == SENSOR_WAIT_LABEL
        out.append({'label': str(label), 't_gcode': float(tp), 'length': 0.0, 'kind': 'none', 'wait': None,
                    'ended_by': '', 'note': 'no logged wait' if sensor else 'not logged'})
    sensor_idx = [i for i, p in enumerate(out) if p['label'] == SENSOR_WAIT_LABEL]
    if log_curve is None:
        return out
    items = logged_wait_items(log_curve)
    if not items:
        for i in sensor_idx:
            out[i]['note'] = f"no logged wait in {log_curve.name}"
        return out
    if len(items) != len(sensor_idx):
        why = (f"not paired: {log_curve.name} has {len(items)} logged sensor wait(s), the G-code "
               f"{len(sensor_idx)} sensor_wait pause(s)")
        for i in sensor_idx:
            out[i]['note'] = why
        return out
    for i, it in zip(sensor_idx, items):
        w = it['wait']
        if it['kind'] == 'marked':
            L = float(w.get('length', float(w['end']) - float(w['received'])))
            out[i].update(length=max(0.0, L), kind='marked', wait=w, ended_by=str(w.get('end_by') or ''),
                          note='logged' + (' (from the -1000 rows only)' if w.get('source') == 'rows' else ''))
        else:
            out[i].update(length=0.0, kind='not_marked', wait=w, ended_by='',
                          note=f"wait not marked: {w.get('reason') or 'it may have ended before LogIQ knew of it'}")
    return out


# ----------------------------------------------------------------------------
# Points, tables, CSV
# ----------------------------------------------------------------------------
def nearest_point(curve, axis, t):
    """(t_i, v_i) of the sample of curve[axis] nearest to t (offset time base, offsets applied)."""
    tt = curve.times()
    vv = curve.values(axis)
    if tt.size == 0:
        raise ValueError(f"{curve.name} has no samples")
    fin = np.isfinite(vv)
    if not fin.all() and fin.any():
        # an axis without values at some times (an aligned export read back: a shorter curve's column
        # is empty there): the nearest sample that has a value
        tt, vv = tt[fin], vv[fin]
    i = _nearest_index(tt, t)
    return float(tt[i]), float(vv[i])


def value_crossings(curve, axis, value, gaps=True):
    """Sorted times (offset time base) where curve[axis] (offsets applied, linear between samples)
    reaches value: every sample at the value, and the linear crossing between two consecutive
    samples on either side of it.  With gaps, the line between the two samples bounding a
    connection gap (gap_spans; the data is unknown there) does not count."""
    tt = curve.times()
    vv = curve.values(axis)
    x = float(value)
    if tt.size == 0 or not math.isfinite(x):
        return np.empty(0)
    d = vv - x
    ok = np.isfinite(d)
    exact = tt[ok & (d == 0.0)]
    if tt.size < 2:
        return np.sort(exact)
    sg = np.sign(d)
    pair = ok[:-1] & ok[1:] & (sg[:-1] * sg[1:] < 0.0)
    if gaps:
        for a_eff, b_eff in gap_spans(curve):
            i = int(np.searchsorted(tt, a_eff - _EPS_T, side='left'))
            if 0 <= i < tt.size - 1 and abs(tt[i] - a_eff) <= _EPS_T and tt[i + 1] <= b_eff + _EPS_T:
                pair[i] = False
    i = np.flatnonzero(pair)
    tc = tt[i] + (x - vv[i]) / (vv[i + 1] - vv[i]) * (tt[i + 1] - tt[i])
    return np.sort(np.concatenate([exact, tc]))


def nearest_crossing(curve, axis, value, t, gaps=True):
    """The time nearest to t (offset time base) where curve[axis] reaches value (value_crossings),
    or None when it never does."""
    tc = value_crossings(curve, axis, value, gaps=gaps)
    if tc.size == 0:
        return None
    return float(tc[int(np.argmin(np.abs(tc - float(t))))])


def aligned_table(curves, axis, roi=None, dt=0.01):
    """DataFrame with 'Time_s' (uniform grid over the union of the curves, ROI applied) and one
    column per curve name (offsets applied; duplicate names get ' (2)' ...), NaN where a curve has
    no data or lacks the axis."""
    lo, hi = _roi_bounds(roi)
    spans = [_span(c) for c in curves]
    spans = [s for s in spans if np.isfinite(s[0])]
    if not spans:
        return pd.DataFrame({'Time_s': np.empty(0)})
    tg, _, _ = _grid(max(lo, min(s[0] for s in spans)), min(hi, max(s[1] for s in spans)), dt)
    cols = {'Time_s': tg}
    for c in curves:
        name = str(c.name)
        base, k = name, 2
        while name in cols:
            name = f"{base} ({k})"
            k += 1
        cols[name] = sample(c, axis, tg) if c.has(axis) else np.full(tg.shape, np.nan)
    return pd.DataFrame(cols)


CSV_SEP = ';'                     # files written by the tab: v2 style (Excel with ';' lists, decimal comma)
CSV_DECIMAL = ','


def _fmt_cell(x, decimal=CSV_DECIMAL):
    if x is None:
        return ''
    if isinstance(x, (bool, np.bool_)):
        return str(bool(x))
    if isinstance(x, (int, np.integer)):
        return str(int(x))
    if isinstance(x, (float, np.floating)):
        if not np.isfinite(x):
            return ''
        s = f"{float(x):.9g}"
        return s.replace('.', decimal) if decimal != '.' else s
    return str(x)


def comment_line(text):
    """A '# ...' line for a file written by the tab: one line, no ';' (Excel would split it into
    cells), '"' as "'"."""
    s = " ".join(str(text).replace(';', ',').replace('"', "'").split())
    return s if s.startswith('#') else f"# {s}"


def write_rows_csv(path, headers, rows, notes=None):
    """Write a CSV file (UTF-8) in the v2 style of the TRACE logs: columns separated by ';', a
    decimal comma (floats with 9 significant digits), NaN / None as empty cells, text containing
    ';' quoted.  notes: lines written first as '# ...' comment lines (no ';' in them, see
    comment_line); then one header row and the rows (lists, or dicts keyed by header)."""
    path = os.fspath(path)
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    headers = [str(h) for h in headers]
    with open(path, 'w', newline='', encoding='utf-8') as f:
        for n in notes or []:
            f.write(comment_line(n) + '\r\n')
        w = csv.writer(f, delimiter=CSV_SEP)
        w.writerow(headers)
        for row in rows:
            if isinstance(row, dict):
                row = [row.get(h) for h in headers]
            w.writerow([_fmt_cell(x) for x in row])


def read_rows_csv(path):
    """(notes, headers, rows) of a CSV written by write_rows_csv (or an older ',' one): '#' lines
    are the notes; cells as text (numbers with the file's decimal mark turned into '.')."""
    text = _read_text(os.fspath(path))
    notes, body = [], []
    for line in text.splitlines():
        if line.startswith('#'):
            notes.append(line.lstrip('#').strip())
        elif line.strip():
            body.append(line)
    if not body:
        return notes, [], []
    sep = ';' if ';' in body[0] else ','
    rows = list(csv.reader(body, delimiter=sep))
    dec = ',' if sep == ';' else '.'

    def cell(x):
        return x.replace(',', '.') if dec == ',' and _DEC_CELL_RE.match(x.strip()) else x
    return notes, rows[0], [[cell(x) for x in r] for r in rows[1:]]
