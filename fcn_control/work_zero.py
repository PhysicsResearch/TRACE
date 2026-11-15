"""
Work zero of DYNAMIQ (lung phantom) and KINETIQ (motion platform): the Duet's G54 workplace offset.

The work zero (checked in the RRF 3.6.3 source)
* G-code coordinates = machine position - offset (the Duet's userPosition).  Every absolute move, so every G-code
  job, drives a motor to machine position = G-code value + offset.  The M208 limits stay machine positions, so they
  keep protecting the hardware; a move past them is clamped by the Duet without an error.
* Standard zero (fcn_control/work_zero_frame.py):
    KINETIQ = platform centre: LAT 'e 'f 50, SI 'a 'c ('b) 25, A-D 45 mm machine read 0, so at home LAT reads +50,
              SI +35 and A-D -45;
    DYNAMIQ = home: offset 0 on every axis.
  LogIQ sets it before every homing it sends (before_homing: the Home buttons, and a G28 or home macro typed in the
  console) with one G10 L2 P<n> for every axis letter of the board, and only when the Duet's offsets differ.  The
  Duet keeps the offset through G28, job start and job end; a reset (power, M112, M999) sets it to 0, which on
  KINETIQ means "home, not centre" until LogIQ homes it again.
* Custom zero: "Set current position as zero" (set_zero) sends G10 L20 P<n> (offset = machine position - value):
  nothing moves, only the numbers change; never G92.  "Back to centre" / "Back to home zero" (set_standard_zero)
  restores the standard zero with G10 L2.
* The Duet's offsets (move.axes[].workplaceOffsets) are read on every status poll (sync_from_status), so LogIQ's
  record follows the Duet, also after a reset or an offset set from DWC.

LogIQ works in G-code coordinates, so a run stays comparable with its plan:
* Control tab positions are the Duet's userPosition.  LogIQ's limit checks get the M208 limits minus the offset
  (sync_from_status rewrites the polled limits).  LogIQ's own actuator range for A-D (0.2-70 mm) is physical:
  0.2 - offset .. 70 - offset in G-code coordinates (actuator_bounds, actuator_envelope).
* Live samples, the run log, the Status plot and Start's pre-position wait use machinePosition minus the offset
  (to_gcode_frame); the log header names the offset (positions_header); a first move that the Duet clamps at a limit
  is waited for at the limit (preposition_targets).
* Start (confirm_start) asks only when the zero is not the device's standard one or cannot be read, when an axis of
  the file goes past its limits (with its offset, 0 where none) or its moves cannot be followed (also G92, G10,
  G54-G59.3, G53 moves and arcs in the file), when a KINETIQ file sends A-D outside 0.2-70 mm, or when a KINETIQ
  file lacks Planning's work-zero line (it may be written for the old frame, 0 at home).
* Homing a group the connected board does not have is refused (home_refused): RRF homes every axis on a G28 without
  a known axis letter.  A typed G54-G59.3 is followed (before_typed_command: read_board shortly after it).
* SI's second motor is 'c on some KINETIQ boards and 'b on others (row_motors, board_si_motors).  Where no board is
  at hand (Planning G-code) kinetiq_si_motors gives the connected KINETIQ board's letters, else those of the last
  KINETIQ board seen (remembered in configuration.json, 'kinetiq_si_motors'), else 'a 'c.  Start asks when a file
  moves an axis the connected board does not have (e.g. 'c on a 'b board, A-D on DYNAMIQ): it would not move.
"""
import json
import math
import re
import time

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QMessageBox

from fcn_control.work_zero_frame import (ACTUATORS, ACTUATOR_ENVELOPE, KINETIQ_CENTRE_DOF, LAT_MOTORS, SI_MOTORS,
                                         SI_SECOND, actuator_limits, default_offsets, has_kinetiq_frame_marker)

EPS = 0.0005                      # the Duet reports positions and offsets with 3 decimals
TOL = 1e-6
VERIFY_TOL = 0.005                # mm: an offset read back this close to the expected one is right
HOMING_GRACE_S = 2.0              # right after a Home press the Duet may still report idle
JOB_STATES = ('P', 'S', 'D', 'R', 'M')        # running, paused, pausing, resuming, simulating
DYNAMIQ, KINETIQ = "DYNAMIQ", "KINETIQ"
ROWS = {
    KINETIQ: [("LAT", ("'e", "'f")), ("SI", ("'a", "'c")), ("AP", ("A", "B", "C", "D")),
              ("A", ("A",)), ("B", ("B",)), ("C", ("C",)), ("D", ("D",))],
    DYNAMIQ: [("X", ("X",)), ("Y", ("Y",)), ("Z", ("Z",))],
}
KINETIQ_MOTORS = frozenset(LAT_MOTORS + SI_MOTORS + ACTUATORS)
LETTER_ORDER = ("X", "Y", "Z", "'e", "'f", "'a", "'b", "'c", "A", "B", "C", "D")
MOTOR_NAMES = {"'e": "LAT 'e", "'f": "LAT 'f", "'a": "SI 'a", "'b": "SI 'b", "'c": "SI 'c",
               "A": "actuator A", "B": "actuator B", "C": "actuator C", "D": "actuator D"}
STANDARD_NAME = {KINETIQ: "centre", DYNAMIQ: "home"}
WARN, NOTE = "#ff3333", "#ff9800"


class WorkZeroState:
    def __init__(self):
        self.board = None             # Duet IP these values belong to
        self.axes = {}                # motor -> {'user', 'min', 'max' (machine positions), 'homed'}
        self.offsets = {}             # motor -> offset of the active workplace (G54) in mm
        self.from_board = False       # offsets read from the Duet (else unknown)
        self.wpn = 0                  # active workplace, 0 = G54
        self.status = None            # one-letter Duet status of the last poll
        self.homing_t = None          # time.monotonic() of LogIQ's last homing command
        self.read_error = None        # last read_board failure: 'connection' (not reachable: requests.ConnectionError)
        #                               / 'reply' (read timeout, reply not JSON) / 'http' / None


def state(self):
    st = getattr(self, '_work_zero_state', None)
    if st is None:
        st = self._work_zero_state = WorkZeroState()
    return st


# ---------------------------------------------------------------------------------------------------------- helpers
def _num(v):
    try:
        return None if v is None or isinstance(v, bool) else float(v)
    except (TypeError, ValueError):
        return None


def _value(v):
    """A typed value (number or text, decimal comma allowed) as a finite float, else None."""
    if isinstance(v, str):
        v = v.strip().replace(",", ".").replace("−", "-")
    x = _num(v)
    return x if x is not None and math.isfinite(x) else None


def _mm(v):
    """G-code number without trailing zeros: 50 -> '50', 25.5 -> '25.5', -0.0 -> '0'."""
    s = f"{round(float(v), 4) + 0.0:.4f}".rstrip("0").rstrip(".")
    return s if s not in ("", "-0") else "0"


def norm_letter(let):
    """Object-model axis letter -> LogIQ motor name ('e' or "'e" -> "'e", 'A' -> 'A')."""
    s = str(let or "").strip()
    if s.startswith("'"):
        return "'" + s[1:].lower() if len(s) > 1 else ""
    if len(s) == 1 and s.islower():
        return "'" + s
    return s


def aliases(m):
    """Keys a live sample uses for motor m ('A', "'A" / "'e", 'e')."""
    plain = m.strip("'")
    return list(dict.fromkeys((m, plain, "'" + plain)))


def _order(m):
    return (LETTER_ORDER.index(m) if m in LETTER_ORDER else len(LETTER_ORDER), m)


def mean(values):
    vals = [v for v in values if v is not None]
    return sum(vals) / len(vals) if vals and len(vals) == len(values) else None


def device_of(self):
    """'KINETIQ' / 'DYNAMIQ' / None: the connected device (fcn_control/device_identity.py), else from the axis
    letters the board reports (KINETIQ motors -> KINETIQ; only X Y Z -> DYNAMIQ)."""
    d = getattr(self, 'connected_device', None)
    if d in ROWS:
        return d
    letters = set(state(self).axes)
    if letters & KINETIQ_MOTORS:
        return KINETIQ
    if letters and letters <= {"X", "Y", "Z"}:
        return DYNAMIQ
    return None


def row_motors(self, device, row):
    motors = dict(ROWS.get(device, [])).get(row, ())
    st = state(self)
    if "'c" in motors and "'b" in st.axes and "'c" not in st.axes:      # SI's lower motor is 'b on some builds
        motors = tuple("'b" if m == "'c" else m for m in motors)
    return motors


def device_motors(self, device):
    out = []
    for row, _m in ROWS.get(device, []):
        for m in row_motors(self, device, row):
            if m not in out:
                out.append(m)
    return out


# ---------------------------------------------------------------------------------------------------------- SI motors
CONFIG_SI_KEY = "kinetiq_si_motors"   # configuration.json: SI motors of the last KINETIQ board seen, e.g. ["'a", "'b"]
DEFAULT_SI_MOTORS = ("'a", "'c")


def board_si_motors(self):
    """('a, 'c) or ('a, 'b): the SI motors of the connected KINETIQ board (work_zero's record of it, refreshed on every
    poll; 'c when a board has both, as row_motors), None when no KINETIQ board is connected or its axes are unknown."""
    if not getattr(self, 'duet_connected', False) or device_of(self) != KINETIQ:
        return None
    axes = state(self).axes
    second = next((m for m in SI_SECOND if m in axes), None)
    return ("'a", second) if second else None


def _valid_si(value):
    """("'a", "'c" | "'b") from a stored value (list, tuple or "'a 'b"), else None."""
    if isinstance(value, str):
        value = value.split()
    if isinstance(value, (list, tuple)) and len(value) == 2 and value[0] == "'a" and value[1] in SI_SECOND:
        return "'a", str(value[1])
    return None


def remembered_si_motors(self):
    """SI motors of the last KINETIQ board seen (configuration.json 'kinetiq_si_motors', read once per window), None
    when none is stored."""
    if not hasattr(self, '_kinetiq_si_remembered'):
        value = None
        try:
            from fcn_init.app_config import get_config_path
            with open(get_config_path('configuration.json', for_writing=False), 'r') as f:
                data = json.load(f)
            value = _valid_si(data.get(CONFIG_SI_KEY)) if isinstance(data, dict) else None
        except Exception:
            value = None
        self._kinetiq_si_remembered = value
    return self._kinetiq_si_remembered


def remember_kinetiq_si_motors(self, motors):
    """Stores the SI motors of a KINETIQ board ('a 'c / 'a 'b) in configuration.json ('kinetiq_si_motors', the other
    settings kept) when they differ from the stored ones.  The file is only written when it can be read (or does not
    exist).  True when they are stored (or were already)."""
    motors = _valid_si(motors)
    if motors is None:
        return False
    if remembered_si_motors(self) == motors:
        return True
    self._kinetiq_si_remembered = motors           # used from now on, also when the file cannot be written
    try:
        import os
        from fcn_init.app_config import get_config_path
        data = {}
        path = get_config_path('configuration.json', for_writing=False)
        if os.path.exists(path):
            with open(path, 'r') as f:
                data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError("configuration.json does not hold settings")
        data[CONFIG_SI_KEY] = list(motors)
        with open(get_config_path('configuration.json', for_writing=True), 'w') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"Work zero: the KINETIQ SI motors ({' '.join(motors)}) were not saved to configuration.json: {e}")
        return False
    return True


def kinetiq_si_motors(self):
    """SI motors of KINETIQ where no board is at hand (Planning G-code, labels): the connected KINETIQ board's ('a 'c,
    or 'a 'b on boards that use it), else those of the last KINETIQ board seen (configuration.json), else 'a 'c."""
    return board_si_motors(self) or remembered_si_motors(self) or DEFAULT_SI_MOTORS


def row_value(self, device, row):
    """Current G-code value of a row (mean of its motors' userPosition), None when one of them is unknown."""
    st = state(self)
    vals = [st.axes.get(m, {}).get('user') for m in row_motors(self, device, row)]
    return mean(vals) if vals else None


def nonzero_offsets(self):
    st = state(self)
    return {m: st.offsets[m] for m in sorted(st.offsets, key=_order) if abs(st.offsets[m]) >= EPS}


def offsets_text(nz, sep=", "):
    return sep.join(f"{m} {w:+.3f}" for m, w in nz.items())


def _all_letters(st):
    return sorted(st.axes, key=_order) if st.axes else list(LETTER_ORDER)


def standard_offsets(self, device=None):
    """{motor: offset} of the device's standard zero for the board's axis letters (KINETIQ: platform centre, other
    letters 0; DYNAMIQ: all 0).  device None -> the connected device."""
    dev = device if device in ROWS else device_of(self)
    return default_offsets(dev, _all_letters(state(self)))


def custom_offsets(self, device=None):
    """{motor: (offset, standard offset)} for the offsets read from the Duet that are not the standard ones."""
    st = state(self)
    std = standard_offsets(self, device)
    out = {}
    for m in sorted(st.offsets, key=_order):
        w, s = st.offsets[m], std.get(m, 0.0)
        if abs(w - s) >= EPS:
            out[m] = (w, s)
    return out


def motor_offset(self, motor):
    """Offset (mm) of one motor ('A', "'e", ...) as last read from the Duet; 0 when unknown."""
    st = getattr(self, '_work_zero_state', None)
    if st is None:
        return 0.0
    m = str(motor or "").strip()
    w = st.offsets.get(m)
    if w is None:
        w = st.offsets.get(norm_letter(m))
    return float(w) if w is not None else 0.0


def actuator_bounds(self, motor):
    """LogIQ's actuator range (0.2-70 mm machine) of A-D in G-code coordinates: (0.2 - offset, 70 - offset)."""
    return actuator_limits(motor_offset(self, motor))


def actuator_envelope(self, motors=ACTUATORS):
    """({motor: min}, {motor: max}) in G-code coordinates: LogIQ's actuator range (actuator_bounds) combined with the
    Duet's M208 limits as polled (already minus the offset, see sync_from_status)."""
    amin = getattr(self, 'axis_min_limits', None) or {}
    amax = getattr(self, 'axis_max_limits', None) or {}
    mins, maxs = {}, {}
    for m in motors:
        lo, hi = actuator_bounds(self, m)
        mn, mx = _num(amin.get(m, lo)), _num(amax.get(m, hi))
        mins[m] = max(mn if mn is not None else lo, lo)
        maxs[m] = min(mx if mx is not None else hi, hi)
    return mins, maxs


def actuator_range_text():
    lo, hi = ACTUATOR_ENVELOPE
    return f"{lo:g}-{hi:g} mm machine"


def envelope_text(mins, maxs):
    """'-44.800 ... 25.000 mm' (same for every motor) or 'A -44.800 ... 25.000 / B ...' mm."""
    pairs = {m: (mins[m], maxs[m]) for m in mins if m in maxs}
    if not pairs:
        return "unknown"
    vals = list(pairs.values())
    if all(abs(a - vals[0][0]) < EPS and abs(b - vals[0][1]) < EPS for a, b in vals):
        return f"{vals[0][0]:.3f} ... {vals[0][1]:.3f} mm"
    return " / ".join(f"{m} {a:.3f} ... {b:.3f}" for m, (a, b) in pairs.items()) + " mm"


def _centre_text():
    c = KINETIQ_CENTRE_DOF
    return f"LAT {c['LAT']:g}, SI {c['SI']:g}, AP {c['AP']:g} mm machine"


def _standard_text(device):
    if device == KINETIQ:
        return f"the platform centre ({_centre_text()})"
    return "home (0)"


def job_running(self, st=None):
    st = st or state(self)
    return (getattr(self, 'run_active', False) is True or getattr(self, '_starting_gcode', False) is True
            or st.status in JOB_STATES)


def homing_now(self, st=None):
    """LogIQ's homing poll runs (fcn_control.home) and the Duet has not reported idle since the Home press.  The poll
    itself can run its full 30 s after a Home ALL (it waits for the axes of both devices), so idle ends it here."""
    st = st or state(self)
    t = getattr(self, '_homing_poll_timer', None)
    try:
        active = t is not None and t.isActive()
    except RuntimeError:
        active = False
    if not active:
        return False
    if st.homing_t is not None and time.monotonic() - st.homing_t < HOMING_GRACE_S:
        return True
    return st.status not in (None, 'I')


def _console(self, text, color=None):
    try:
        from fcn_control.fcn_control import log_to_duet_console
        log_to_duet_console(self, text, color=color)
    except Exception:
        print(text)


def _refuse(self, title, text):
    """Red console line and a warning box; returns False (for `return _refuse(...)`)."""
    _console(self, f"{title}: {text}", color=WARN)
    QMessageBox.warning(self, title, text)
    return False


def _poll(self):
    try:
        from fcn_control.fcn_control import update_duet_status_ui
        update_duet_status_ui(self)
    except Exception as e:
        print(f"Work zero: status refresh failed: {e}")


def _clear_pending(self):
    """Typed targets are G-code numbers: a new zero changes their physical meaning, so they are dropped."""
    try:
        from fcn_control.goto_targets import clear_pending
        clear_pending(self)
    except Exception as e:
        print(f"Work zero: pending targets not cleared: {e}")


def _send(self, gcode):
    """One rr_gcode request, shown in the console like send_cmd; True only when the Duet took it (no status poll)."""
    from fcn_control.fcn_control import update_connection_status_ui
    from fcn_monitor.fcn_duet import duet_request, get_clean_duet_ip
    if not getattr(self, 'duet_connected', False):
        QMessageBox.warning(self, "Not Connected", "Please connect to Duet first.")
        return False
    _console(self, "Sent: " + gcode.replace("\n", " | "))            # one console line per request
    try:
        r = duet_request(f"http://{get_clean_duet_ip(self)}/rr_gcode", params={'gcode': gcode}, timeout=4)
    except Exception as e:
        _console(self, f"Error: Failed to execute command '{gcode}': {e}", color=WARN)
        self.duet_connected = False
        update_connection_status_ui(self, connected=False)
        return False
    if r.status_code != 200:
        _console(self, f"Error: HTTP {r.status_code} - Command '{gcode}' failed", color=WARN)
        return False
    txt = r.text.strip()
    try:
        js = json.loads(txt) if txt.startswith("{") else None
    except ValueError:
        js = None
    if isinstance(js, dict) and js.get('err'):                    # RRF: 200 with {"err":1} = command not taken
        _console(self, f"Error: the Duet did not take the command (reply {txt}): its command buffer is full.",
                 color=WARN)
        return False
    try:
        from fcn_control.console_reply import after_command, is_buffer_ack
        if not is_buffer_ack(txt):
            _console(self, f"Recv: {txt if txt else 'OK (200)'}")
        after_command(self)
    except Exception:
        pass
    return True


# ---------------------------------------------------------------------------------------------------------- listeners
def add_listener(self, fn):
    """fn(self) runs at the end of every sync_from_status (every status poll and every fresh read of the Duet)."""
    lst = getattr(self, '_work_zero_listeners', None)
    if lst is None:
        lst = self._work_zero_listeners = []
    if fn not in lst:
        lst.append(fn)


def _notify(self):
    for fn in list(getattr(self, '_work_zero_listeners', None) or ()):
        try:
            fn(self)
        except Exception as e:
            failed = getattr(self, '_work_zero_listener_failed', None)
            if failed is None:
                failed = self._work_zero_listener_failed = set()
            if id(fn) not in failed:                    # printed once per listener (it runs on every poll)
                failed.add(id(fn))
                print(f"Work zero listener {getattr(fn, '__name__', fn)} failed: {e}")


# ---------------------------------------------------------------------------------------------------------- Duet side
def _board_key(self):
    try:
        from fcn_monitor.fcn_duet import get_clean_duet_ip
        return get_clean_duet_ip(self)
    except Exception:
        return None


def sync_from_status(self, data):
    """update_duet_status_ui hook (every status poll): axes, limits, offsets and status into the record.  The limits
    in ``data`` become G-code coordinates (M208 limit - offset) for LogIQ's own limit checks, which compare them with
    userPosition values (idempotent: the machine limits are kept in the axis dicts).  Offsets are merged per axis, so
    a poll that lost a page of move.axes keeps the offsets of the axes it did not get.  The listeners run last."""
    try:
        _sync(self, data)
    finally:
        _notify(self)


def _forget_board(self):
    """Another Duet answers: LogIQ's per-board limits and homed flags of the earlier board must not apply to it (a
    stale 'b of a board that uses 'b for SI would make Home SI / Go to zero / the SI jog move 'b on a 'c board; stale
    homed flags would enable the buttons of the other device).  The two limit dicts are emptied and every homed flag
    is set to False; fcn_control.update_duet_status_ui refills them from the same poll right after this sync."""
    for name in ('axis_min_limits', 'axis_max_limits'):
        d = getattr(self, name, None)
        if isinstance(d, dict):
            d.clear()
    homed = getattr(self, 'ext_axes_homed', None)
    if isinstance(homed, dict):
        for k in homed:
            homed[k] = False


def _sync(self, data):
    st = state(self)
    key = _board_key(self)
    if st.board != key:                                  # another Duet: nothing of the old record applies
        st.__init__()
        st.board = key
        _forget_board(self)
    if not isinstance(data, dict):
        return
    status = data.get('status')
    if isinstance(status, str) and status:
        st.status = status
    move = data.get('move')
    axes = move.get('axes') if isinstance(move, dict) else None
    if not isinstance(axes, list) or not axes:
        return
    offsets = {}
    for ax in axes:
        if not isinstance(ax, dict) or 'letter' not in ax:
            continue
        m = norm_letter(ax['letter'])
        if not m:
            continue
        mn = ax.get('_wz_machine_min', ax.get('min'))
        mx = ax.get('_wz_machine_max', ax.get('max'))
        ax['_wz_machine_min'], ax['_wz_machine_max'] = mn, mx
        homed = ax.get('homed', ax.get('userHomed', False))
        st.axes[m] = {'user': _num(ax.get('userPosition')), 'min': _num(mn), 'max': _num(mx),
                      'homed': homed == 1 or homed is True}
        wo = ax.get('workplaceOffsets')
        if isinstance(wo, (list, tuple)) and len(wo) > st.wpn:
            w = _num(wo[st.wpn])
            if w is not None:
                offsets[m] = w
    if offsets:
        st.offsets.update(offsets)
        st.from_board = True
    for ax in axes:
        if not isinstance(ax, dict) or 'letter' not in ax:
            continue
        w = st.offsets.get(norm_letter(ax['letter']), 0.0)
        for k in ('min', 'max'):
            v = _num(ax.get(f'_wz_machine_{k}'))
            if v is not None and k in ax:
                ax[k] = v - w
    motors = board_si_motors(self)                   # a KINETIQ board: its SI letters are remembered for Planning
    if motors:
        remember_kinetiq_si_motors(self, motors)


def _read_status(self, st, timeout=1.5):
    from fcn_monitor.fcn_duet import RRF_STATUS_CODES, duet_request, get_clean_duet_ip
    try:
        r = duet_request(f"http://{get_clean_duet_ip(self)}/rr_model?key=state.status", timeout=timeout)
        txt = str(r.json().get('result') or "").lower() if r.status_code == 200 else ""
        if txt:
            st.status = RRF_STATUS_CODES.get(txt, 'B')
    except Exception:
        pass
    return st.status


def read_board(self, timeout=2.5):
    """Fresh read of move.workplaceNumber, move.axes (every page; with workplaceOffsets) and state.status into the
    record.  True when all axes were read."""
    import requests
    from fcn_monitor.fcn_duet import duet_request, get_clean_duet_ip
    st = state(self)
    st.read_error = None
    base = f"http://{get_clean_duet_ip(self)}/rr_model"
    axes, nxt = [], 0
    try:
        for _page in range(10):
            r = duet_request(f"{base}?key=move.axes&flags=d99" + (f"a{nxt}" if nxt else ""), timeout=timeout)
            if r.status_code != 200:
                st.read_error = 'http'
                return False
            js = r.json()
            res = js.get('result') if isinstance(js, dict) else None
            if not isinstance(res, list):
                st.read_error = 'http'
                return False
            axes.extend(res)
            nxt = js.get('next', 0) or 0
            if not nxt:
                break
    except requests.ConnectionError:
        st.read_error = 'connection'                  # not reachable (refused, unreachable, connect timeout)
        return False
    except requests.RequestException:
        st.read_error = 'reply'                       # the Duet is there, but its reply came too late or is not JSON
        return False
    except Exception:
        st.read_error = 'http'
        return False
    try:
        r = duet_request(f"{base}?key=move.workplaceNumber", timeout=timeout)
        wpn = r.json().get('result') if r.status_code == 200 else None
        if isinstance(wpn, int) and not isinstance(wpn, bool) and 0 <= wpn < 9:
            st.wpn = wpn
    except Exception:
        pass
    _read_status(self, st, timeout)                  # keeps the polled status if this read fails
    sync_from_status(self, {'status': st.status, 'move': {'axes': axes}})
    return True


def to_gcode_frame(self, positions):
    """Live-sample hook (handle_position_sample): machinePosition -> G-code coordinates, in place."""
    st = getattr(self, '_work_zero_state', None)
    if st is None or not st.offsets or not isinstance(positions, dict):
        return positions
    if getattr(self, '_machine_pos_missing_noted', False):
        return positions                  # the samples hold userPosition (no machinePosition): G-code values already
    for m, w in st.offsets.items():
        if not w:
            continue
        for k in aliases(m):
            v = positions.get(k)
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                positions[k] = v - w
    return positions


def positions_header(self, default):
    """Run log '# Positions:' line; names the offset while one is set (the header keeps its 10 lines; no ';')."""
    try:
        nz = nonzero_offsets(self)
    except Exception:
        nz = {}
    if not nz:
        return default
    try:
        kind = zero_summary(self).get("kind")
    except Exception:
        kind = None
    label = {"centre": "platform centre", "home": "home"}.get(kind, "custom")
    txt = offsets_text(nz, " / ").replace('.', ',')
    return ("# Positions: actual in G-code coordinates = Duet machinePosition minus the work-zero offset "
            f"({txt} mm, {label}, machine position = value + offset), refreshed at most every 200 ms, "
            "CAN expansion-board axes about every 100 ms")


def _target_motor(key):
    s = str(key).strip()
    return s[1] if len(s) == 2 and s[0] == "'" and s[1].isupper() else norm_letter(s)   # "'A" is an alias of A


def preposition_targets(self, targets):
    """Start hook: the pre-position wait's targets.  Axes the connected board does not have are left out (they never
    get there; Start asked first, confirm_start).  With an offset set, a first move that the offset pushes past a
    limit is clamped there by the Duet, so the wait expects the limit (else it times out after 30 s)."""
    if not isinstance(targets, dict):
        return targets
    st = state(self)
    if st.axes and any(_target_motor(k) not in st.axes for k in targets):
        targets = {k: v for k, v in targets.items() if _target_motor(k) in st.axes}
    nz = nonzero_offsets(self)
    if not nz:
        return targets
    out = dict(targets)
    for k, v in targets.items():
        m = _target_motor(k)
        t = _num(v)
        if m not in nz or t is None:
            continue
        info = st.axes.get(m) or {}
        lo, hi, w = info.get('min'), info.get('max'), nz[m]
        if lo is not None and t + w < lo:
            out[k] = lo - w
        elif hi is not None and t + w > hi:
            out[k] = hi - w
    return out


# ---------------------------------------------------------------------------------------------------------- summary
def _summary(kind, text, detail, device, standard):
    return {"kind": kind, "text": text, "detail": detail, "device": device, "standard": standard}


def _zero_lines(self, device, custom=None):
    """'LAT: 0 at machine 52.000 mm (centre 50.000)' per row, plus other axis letters with a custom zero."""
    st = state(self)
    std = standard_offsets(self, device)
    name = STANDARD_NAME.get(device, "standard")
    lines, shown = [], set()
    for row, _m in ROWS.get(device, []):
        ms = [m for m in row_motors(self, device, row) if m in st.offsets]
        if not ms:
            continue
        offs = [st.offsets[m] for m in ms]
        if row == "AP" or max(offs) - min(offs) < EPS:
            where = f"{sum(offs) / len(offs):.3f}"
        else:
            where = " / ".join(f"{m} {st.offsets[m]:.3f}" for m in ms)
        s = sum(std.get(m, 0.0) for m in ms) / len(ms)
        lines.append(f"{row}: 0 at machine {where} mm ({name} {s:.3f})")
        shown.update(ms)
    for m, (w, s) in (custom or {}).items():
        if m not in shown:
            lines.append(f"{m}: 0 at machine {w:.3f} mm ({name} {s:.3f})")
    return lines


def _kinetiq_at_home(self):
    """KINETIQ offsets all 0 (a Duet reset, or homed outside LogIQ): the zero is at home, not at the centre."""
    st = state(self)
    motors = [m for m in device_motors(self, KINETIQ) if m in st.offsets]
    return bool(motors) and all(abs(st.offsets[m]) < EPS for m in motors)


_HOME_NOT_CENTRE = ("The zero is at home, not at the platform centre: the Duet was reset or homed outside LogIQ. "
                    "Home KINETIQ in LogIQ, or use Back to centre, to restore the standard zero.")


def zero_summary(self, device=None):
    """{'kind', 'text', 'detail', 'device', 'standard'} of the work zero for a status line.

    kind: 'centre' (KINETIQ standard), 'home' (DYNAMIQ standard), 'custom' (not the standard one, also KINETIQ at home
    after a reset: text 'Zero: home, not centre'), 'unknown' (not read), 'disconnected', 'other' (``device`` is not
    the connected one).  text: at most 24 characters.  detail: one line per row, where its 0 is in machine mm.
    device None -> the connected device."""
    st = state(self)
    conn = device_of(self)
    dev = device if device in ROWS else conn
    if not getattr(self, 'duet_connected', False):
        return _summary("disconnected", "Not connected", "Connect to the Duet to read its zero.", dev, False)
    if device in ROWS and conn is not None and device != conn:
        return _summary("other", f"{conn} connected", f"{conn} is connected: the zero of {device} is read when "
                                                      f"{device} is connected.", device, False)
    if dev is None or not st.from_board:
        return _summary("unknown", "Zero: not read", "The zero (G54 workplace offset) has not been read from the "
                                                     "Duet yet.", dev, False)
    custom = custom_offsets(self, dev)
    detail = "\n".join(_zero_lines(self, dev, custom))
    if not custom:
        if dev == KINETIQ:
            return _summary("centre", "Zero: platform centre", detail, dev, True)
        return _summary("home", "Zero: home (0)", detail, dev, True)
    if dev == KINETIQ and _kinetiq_at_home(self):
        return _summary("custom", "Zero: home, not centre", detail + "\n" + _HOME_NOT_CENTRE, dev, False)
    return _summary("custom", "Zero: custom", detail, dev, False)


def zero_ready(self, device):
    """(ok, reason): the zero of ``device`` can be changed now (connected to it, positions read, no job, no homing)."""
    st = state(self)
    if not getattr(self, 'duet_connected', False):
        return False, "Not connected: connect to the Duet first."
    if device not in ROWS:
        return False, f"Unknown device {device}."
    conn = device_of(self)
    if conn is not None and conn != device:
        return False, f"The connected board is {conn}, not {device}."
    missing = [m for m in device_motors(self, device) if st.axes.get(m, {}).get('user') is None]
    if missing:
        return False, (f"No position of {' '.join(missing)} from the Duet yet: wait for the position readout, or "
                       f"connect to {device}.")
    if job_running(self, st):
        return False, "A G-code job is running or starting: wait until it has ended."
    if homing_now(self, st):
        return False, "Homing is in progress: wait until it has ended."
    return True, ""


# ---------------------------------------------------------------------------------------------------------- set zero
def _row_zero_text(self, device, row, value, offsets):
    ms = row_motors(self, device, row)
    offs = [offsets[m] for m in ms]
    if row == "AP" or max(offs) - min(offs) < EPS:
        where = f"{sum(offs) / len(offs):.3f}"
    else:
        where = " / ".join(f"{m} {offsets[m]:.3f}" for m in ms)
    return f"{row} {value:.3f} (its 0 is at machine {where} mm)"


def _fresh_idle(self, device, title, what):
    """zero_ready, a fresh read of the Duet and an idle Duet; False after telling the user why."""
    st = state(self)
    ok, reason = zero_ready(self, device)
    if not ok:
        return _refuse(self, title, reason)
    if not read_board(self):
        return _refuse(self, title, f"Could not read the positions and the zero from the Duet: {what}.")
    if not st.from_board:
        return _refuse(self, title, f"The Duet does not report its workplace offsets: {what}.")
    if st.status not in (None, 'I'):
        return _refuse(self, title, f"The Duet is busy (status {st.status}): try again when it is idle.")
    ok, reason = zero_ready(self, device)                  # again with the values just read
    if not ok:
        return _refuse(self, title, reason)
    return True


def set_zero(self, device, values):
    """Set current position as zero: the rows in ``values`` ({row: value}, rows of ROWS[device]) read that value from
    now on.  One G10 L20 P<n> (offset = machine position - value); nothing moves.  'AP' shifts the zero of A-D
    equally, so that their mean reads the value and Roll / Pitch read as before; 'AP' cannot be combined with
    A-D.  Verified by reading the Duet back.  True when the Duet took it and reports the expected zero."""
    title = "Set zero"
    st = state(self)
    if not _fresh_idle(self, device, title, "nothing was changed"):
        return False
    vals = dict(values or {})
    if not vals:
        return _refuse(self, title, "No axis ticked: nothing was changed.")
    rows = [r for r, _m in ROWS[device]]
    unknown = [str(r) for r in vals if r not in rows]
    if unknown:
        return _refuse(self, title, f"{device} has no axis {', '.join(unknown)}: nothing was changed.")
    if "AP" in vals and any(r in vals for r in ACTUATORS):
        return _refuse(self, title, "AP and A, B, C, D cannot be set together (AP sets the zero of all four "
                                    "actuators): tick either AP or single actuators.")
    nums = {}
    for r in rows:
        if r in vals:
            x = _value(vals[r])
            if x is None:
                return _refuse(self, title, f"{r}: '{vals[r]}' is not a number: nothing was changed.")
            nums[r] = x
    motors = {r: row_motors(self, device, r) for r in nums}
    not_homed = list(dict.fromkeys(m for r in nums for m in motors[r] if not st.axes.get(m, {}).get('homed')))
    if not_homed:
        return _refuse(self, title, f"Not homed: {' '.join(not_homed)}. Home {device} first, then set the zero.")
    target = {}
    for r, v in nums.items():
        if r == "AP":
            users = [st.axes[m]['user'] for m in motors[r]]
            shift = sum(users) / len(users) - v
            for m in motors[r]:
                target[m] = st.axes[m]['user'] - shift
        else:
            for m in motors[r]:
                target[m] = v
    expect = {m: st.axes[m]['user'] + st.offsets.get(m, 0.0) - target[m] for m in target}  # machine - value
    order = sorted(target, key=_order)
    if not _send(self, f"G10 L20 P{st.wpn + 1} " + " ".join(f"{m}{target[m]:.4f}" for m in order)):
        return _refuse(self, title, "The zero was not set: the Duet did not take the command.")
    st.offsets.update(expect)
    verified = read_board(self) and st.from_board
    wrong = [m for m in order if verified and abs(st.offsets.get(m, 0.0) - expect[m]) > VERIFY_TOL]
    _clear_pending(self)
    if wrong:
        _refuse(self, title, "The Duet reports a different zero than expected: " +
                ", ".join(f"{m} {st.offsets.get(m, 0.0):.3f} mm (expected {expect[m]:.3f})" for m in wrong) +
                ". Check the zero before a run.")
        _poll(self)
        return False
    if not verified:
        _console(self, "Set zero: the zero could not be read back from the Duet; check it before a run.", color=WARN)
    _console(self, f"Zero set on {device}: " +
             ", ".join(_row_zero_text(self, device, r, v, expect) for r, v in nums.items()), color=NOTE)
    _poll(self)
    return True


def set_standard_zero(self, device):
    """Back to centre (KINETIQ) / Back to home zero (DYNAMIQ): one G10 L2 P<n> with the standard offsets for every
    axis letter of the board; nothing moves.  Verified by reading the Duet back."""
    title = "Set zero"
    st = state(self)
    if not _fresh_idle(self, device, title, "nothing was changed"):
        return False
    std = standard_offsets(self, device)
    what = _standard_text(device)
    if not custom_offsets(self, device):
        _console(self, f"The zero of {device} is already the standard one: {what}.")
        return True
    if not _send(self, f"G10 L2 P{st.wpn + 1} " + " ".join(f"{m}{_mm(v)}" for m, v in std.items())):
        return _refuse(self, title, "The zero was not changed: the Duet did not take the command.")
    st.offsets.update(std)
    verified = read_board(self) and st.from_board
    wrong = [m for m in std if verified and abs(st.offsets.get(m, 0.0) - std[m]) > VERIFY_TOL]
    _clear_pending(self)
    if wrong:
        _refuse(self, title, "The Duet reports a different zero than expected: " +
                ", ".join(f"{m} {st.offsets.get(m, 0.0):.3f} mm (expected {std[m]:.3f})" for m in wrong) +
                ". Check the zero before a run.")
        _poll(self)
        return False
    if not verified:
        _console(self, "Set zero: the zero could not be read back from the Duet; check it before a run.", color=WARN)
    _console(self, f"Zero back at the standard of {device}: {what}.", color=NOTE)
    _poll(self)
    return True


# ---------------------------------------------------------------------------------------------------------- homing
HOME_GROUPS = {"LAT": (("'e",), ("'f",)), "SI": (("'a",), ("'c", "'b")), "AP": (("A",), ("B",), ("C",), ("D",))}


def home_refused(self, ax):
    """fcn_control.home guard, before anything is sent: True (red console line and a warning box, nothing sent) when
    the connected board lacks a motor of the homed group.  RRF treats a G28 without a known axis letter as "home
    every axis", so Home LAT ("G28 'e 'f") on DYNAMIQ would home DYNAMIQ.  'LAT' needs 'e and 'f, 'SI' 'a and 'c or
    'b, 'AP' A B C D, 'X' / 'Y' / 'Z' (or another motor letter) that axis; the board's letters are work_zero's record
    of it (refreshed on every poll, per board).  False (go on) for 'ALL' and Roll / Pitch / Yaw, when not connected,
    and when the board's axes are not known (no poll yet and a fresh read fails)."""
    if not getattr(self, 'duet_connected', False):
        return False
    key = str(ax if ax is not None else "").strip()
    need = HOME_GROUPS.get(key.upper())
    name = key.upper()
    if need is None:
        one = norm_letter(key)
        if one not in LETTER_ORDER:
            return False                                # 'ALL', 'ROLL' / 'PITCH' / 'YAW' (U V W)
        need, name = ((one,),), one
    st = state(self)
    if not st.axes:
        read_board(self, timeout=1.5)                   # nothing polled yet
    if not st.axes:
        return False
    missing = [" or ".join(alts) for alts in need if not any(m in st.axes for m in alts)]
    if not missing:
        return False
    dev = device_of(self) or "The connected board"
    _refuse(self, "Homing", f"Home {name}: {dev} has no axis {', '.join(missing)}, so nothing was sent (a G28 without "
                            "an axis letter of the board would home every axis).")
    return True


def before_homing(self, ax=None):
    """fcn_control.home hook (and typed G28 / home macros): before the homing command, the Duet gets the device's
    standard zero (KINETIQ: platform centre; DYNAMIQ: 0) for the axes that are homed, with one G10 L2 when their
    offsets differ.  ``ax`` picks them: 'LAT' -> 'e 'f, 'SI' -> 'a and 'c / 'b, 'AP' -> A B C D, 'X' / 'Y' / 'Z'
    (or another axis letter) -> that axis only, 'ALL' / None (Home ALL, a typed G28 or home macro) -> every axis
    letter of the board.  The other axes keep their zero.  The Duet keeps the offset through G28, and the homing
    files move relatively, so setting it before G28 equals setting it after.  True when the homed axes have the
    standard zero afterwards (as far as LogIQ can tell); the callers go on with homing anyway.
    Only a Duet that is not reachable (not connected, requests.ConnectionError) is skipped (with a red console line);
    a read timeout or an unreadable reply still sends the G10 with the last known axis letters and workplace, and a
    G10 the Duet does not take gives a red console line and the warning 'Work zero not set'."""
    st = state(self)
    st.homing_t = time.monotonic()
    if not getattr(self, 'duet_connected', False):
        return True
    fresh = read_board(self, timeout=1.5)              # the Duet's offsets and workplace now, not the last poll
    dev = device_of(self)
    key = str(ax).strip() if ax is not None else "ALL"
    groups = {"LAT": LAT_MOTORS, "SI": SI_MOTORS, "AP": ACTUATORS}
    if key.upper() == "ALL":                           # Home ALL, typed G28 / home macro: every letter
        letters, label = _all_letters(st), ""
    elif key.upper() in groups:                        # PLATFORM Home LAT / SI / AP: that group only
        letters, label = [m for m in _all_letters(st) if m in groups[key.upper()]], " " + key.upper()
    else:                                              # one axis: 'X', 'Y', 'Z' (or a motor letter such as "'e")
        one = norm_letter(key)
        letters, label = [m for m in _all_letters(st) if m == one], " " + one
    std = default_offsets(dev, letters)
    if not std:
        return True                                    # no axis of this board is homed by ax (e.g. 'ROLL')
    differ = {m: v for m, v in std.items() if m not in st.offsets or abs(st.offsets[m] - v) >= EPS}
    checked = fresh and st.from_board                  # the Duet's offsets were read just now
    if checked and not differ:
        return True                                    # the Duet has the standard zero already
    centre = dev == KINETIQ and any(abs(v) >= EPS for v in std.values())
    if not label:
        what = f"the KINETIQ platform centre ({_centre_text()})" if dev == KINETIQ else "home (0)"
    elif centre:
        c = KINETIQ_CENTRE_DOF
        part = {"LAT": f"LAT {c['LAT']:g}", "SI": f"SI {c['SI']:g}", "AP": f"A-D {c['AP']:g}"}.get(
            label.strip(), ", ".join(f"{m} {v:g}" for m, v in std.items()))
        what = f"the KINETIQ platform centre ({part} mm machine)"
    else:
        what = "home (0)"
    if not fresh and st.read_error == 'connection':    # not reachable (the only case that may skip): nothing can be
        _console(self, f"Homing{label}: the Duet does not answer, so the zero was not checked or set to {what}.",
                 color=WARN)                           # sent; the homing command reports the lost connection
        return not differ
    need = bool(differ) or not checked                 # a slow / unreadable reply: set it anyway, never skip silently
    if job_running(self, st):
        if need:
            _console(self, f"Homing{label}: a job is running, the zero is NOT set to {what} for this homing.",
                     color=WARN)
        return not need
    if not fresh:                                      # read timeout / reply not JSON: the last known letters and wpn
        why = {'reply': "slow or unreadable reply", 'http': "unexpected reply"}.get(st.read_error, "no reply")
        _console(self, f"Homing{label}: the zero could not be read just now ({why}); it is set from the last known "
                       "axes.", color=NOTE)
    if _send(self, f"G10 L2 P{st.wpn + 1} " + " ".join(f"{m}{_mm(v)}" for m, v in std.items())):
        st.offsets.update(std)
        _console(self, f"Homing{label}: zero set to {what}" if (centre or (not label and dev == KINETIQ))
                 else f"Homing{label}: zero back at home (0)", color=NOTE)
        _clear_pending(self)
        return True
    _refuse(self, "Work zero not set", f"The zero could not be set to {what} before homing, so G-code positions may "
                                       "not be the standard ones. Home again, or use Set zero > Back to "
                                       + ("centre." if dev == KINETIQ else "home zero."))
    return False


_G28 = re.compile(r"(?<![A-Za-z'])G0*28(?![0-9.])", re.IGNORECASE)
_M98_HOME = re.compile(r"(?<![A-Za-z'])M0*98(?![0-9.])[^;\n]*?P\s*\"[^\"]*home[^\"]*\"", re.IGNORECASE)


def typed_homing(cmd):
    """True when console text homes axes: a G28 (also 'G90G28' / 'N10G28') or M98 P"...home...g", but not a 'G28'
    inside quoted text, braces or a ';' comment."""
    text = str(cmd or "")
    if _M98_HOME.search(text):
        return True
    text = re.sub(r'"[^"]*"', " ", text)
    text = re.sub(r"\{[^}]*\}", " ", text)
    text = "\n".join(line.split(";", 1)[0] for line in text.split("\n"))
    return bool(_G28.search(text))


_WORKPLACE_CMD = re.compile(r"(?<![A-Za-z'])G0*5[4-9](?![0-9])", re.IGNORECASE)    # G54-G59, G59.1-G59.3
FOLLOW_WORKPLACE_MS = 300            # after the typed command: the Duet has switched the workplace by then


def typed_workplace(cmd):
    """True when console text selects a workplace (G54-G59, G59.1-G59.3), not inside quoted text, braces or a ';'
    comment."""
    text = re.sub(r'"[^"]*"', " ", str(cmd or ""))
    text = re.sub(r"\{[^}]*\}", " ", text)
    text = "\n".join(line.split(";", 1)[0] for line in text.split("\n"))
    return bool(_WORKPLACE_CMD.search(text))


def _follow_workplace(self):
    """The active workplace (move.workplaceNumber) is read only by read_board, and the polls take the offsets of
    that workplace: after a typed G54..G59.3 read it again, then refresh the status (limits of that workplace)."""
    if not getattr(self, 'duet_connected', False):
        return
    try:
        if read_board(self):
            _poll(self)
    except Exception as e:
        print(f"Work zero: workplace not read after the typed command: {e}")


def before_typed_command(self, cmd):
    """fcn_control.send_cmd hook for text typed in the console: a homing command sets the standard zero first, like
    the Home buttons; a workplace selection (G54-G59.3) is followed: read_board shortly after the command is sent."""
    if typed_homing(cmd):
        before_homing(self)
    if typed_workplace(cmd):
        QTimer.singleShot(FOLLOW_WORKPLACE_MS, lambda: _follow_workplace(self))


# ---------------------------------------------------------------------------------------------------------- Start
_WORD = re.compile(r"(?<!')(?=[GgMm]\d)")             # RRF ends a command at the next G / M word
_MOVE = re.compile(r"^G0*[01](?![0-9.])")
_MODE = re.compile(r"^G9([01])(?![0-9.])")
_SETPOS = re.compile(r"^G0*92(?![0-9.])")
_OFFSETS = re.compile(r"^G0*10(?![0-9.])")           # G10 (any L): offsets set by the file
_WORKPLACE = re.compile(r"^G0*5[4-9](?![0-9])")        # G54-G59, G59.1-G59.3: another workplace
_ARC = re.compile(r"^G0*[23](?![0-9.])")             # G2 / G3: arcs
_HOME = re.compile(r"^G0*28(?![0-9.])")
_MACHINE = re.compile(r"^G0*53(?![0-9.])")
_TOKEN = re.compile(r"('?[A-Za-z])\s*([-+]?(?:\d+\.?\d*|\.\d+))")


def gcode_ranges(lines, axes=None):
    """({motor: (min, max)}, incomplete, unchecked) of the G0/G1 targets of a G-code in workplace coordinates.
    Relative (G91) moves are followed from the last absolute position.  Moves that cannot be followed (G91 without a
    known start, expressions in braces, G1 H moves, G53 moves in machine coordinates, G2 / G3 arcs) are left out:
    their motors are in ``unchecked`` and ``incomplete`` is True.  A G92, G10 (any L) or G54-G59.3 in the file (the
    positions, the offsets or the workplace change while it runs) sets ``incomplete`` too, so Start asks
    (_frame_changes names them).  Planning-made files contain none of these.  Quoted texts are skipped."""
    known = set(axes or ()) | set(LETTER_ORDER) | {"U", "V", "W"}
    out, pos, absolute, incomplete, unchecked = {}, {}, True, False, set()
    for raw in lines or []:
        line = re.sub(r'"[^"]*"', '""', str(raw)).split(';', 1)[0]      # quoted texts can hold ';' or 'G1 X..'
        machine = False
        for part in _WORD.split(line):
            part = part.strip()
            up = part.upper()
            if not up:
                continue
            mode = _MODE.match(up)
            if mode:
                absolute = mode.group(1) == "0"
                continue
            if _MACHINE.match(up):
                machine = True                          # G53: the rest of the line is in machine coordinates
                continue
            if _SETPOS.match(up) or _OFFSETS.match(up) or _WORKPLACE.match(up):
                incomplete = True                       # positions / offsets / workplace changed by the file: the
                continue                                # ranges below are not exact
            if _HOME.match(up):
                pos.clear()                             # after homing the positions are not known from the file
                continue
            move = _MOVE.match(up)
            arc = None if move else _ARC.match(up)
            if machine or arc:                          # a G53 move (machine position: the offset is not known here)
                if move or arc:                         # or an arc (it leaves the line between its end points):
                    incomplete = True                   # its motors cannot be followed
                    for let, _val in _TOKEN.findall(re.sub(r"\{[^}]*\}", " ", part[(move or arc).end():])):
                        m = "'" + let[1:].lower() if let.startswith("'") else let.upper()
                        if m in known:
                            unchecked.add(m)
                            pos.pop(m, None)
                continue
            if not move:
                continue
            body = part[move.end():]
            special = "{" in body or re.search(r"(?:^|[\s\d])H\d", body, re.IGNORECASE) is not None
            body = re.sub(r"\{[^}]*\}", " ", body)
            for let, val in _TOKEN.findall(body):
                # in G-code an unquoted letter is upper case (e = E); 'e is the lower-case axis
                m = "'" + let[1:].lower() if let.startswith("'") else let.upper()
                if m not in known:
                    continue
                if special or (not absolute and m not in pos):
                    incomplete = True
                    unchecked.add(m)
                    pos.pop(m, None)
                    continue
                v = float(val) + (pos[m] if not absolute else 0.0)
                pos[m] = v
                lo, hi = out.get(m, (v, v))
                out[m] = (min(lo, v), max(hi, v))
            if special and "{" in part:
                for let in re.findall(r"('?[A-Za-z])\s*\{", part):
                    m = "'" + let[1:].lower() if let.startswith("'") else let.upper()
                    if m in known:
                        incomplete = True
                        unchecked.add(m)
                        pos.pop(m, None)
    return out, incomplete, unchecked


_FRAME_CODES = (("G92", _SETPOS), ("G10", _OFFSETS), ("G54-G59", _WORKPLACE))


def _frame_changes(lines):
    """What in the G-code changes its coordinates while it runs, or moves in a way that cannot be followed:
    'G92' (positions redefined), 'G10' (offsets), 'G53' (a move in machine coordinates), 'G54-G59' (another
    workplace), 'G2/G3' (arcs), in file order; [] when none (Planning-made files have none)."""
    found = []
    for raw in lines or []:
        line = re.sub(r'"[^"]*"', '""', str(raw)).split(';', 1)[0]
        machine = False
        for part in _WORD.split(line):
            up = part.strip().upper()
            if not up:
                continue
            if _MACHINE.match(up):
                machine = True
                continue
            hit = next((name for name, rx in _FRAME_CODES if rx.match(up)), None)
            if hit is None and machine and _MOVE.match(up):
                hit = "G53"
            if hit is None and _ARC.match(up):
                hit = "G2/G3"
            if hit and hit not in found:
                found.append(hit)
    return found


def _not_followed_text(frame):
    """Start dialog: why the moves of a file could not be followed (frame: _frame_changes)."""
    if frame:
        return ("Some moves of this file could not be followed: it changes positions, offsets or the workplace while "
                f"it runs, or moves in machine coordinates or on arcs ({', '.join(frame)})")
    return ("Some moves of this file could not be followed (relative moves without an absolute start, expressions or "
            "G1 H moves)")


def start_check_lines(self, nz, lines, ranges=None):
    """Lines for the Start confirmation: per offset axis, the G-code range on the machine and the limits.
    Returns (lines, exceeding axes, file read, incomplete, offset axes with moves that could not be checked).
    ``ranges``: gcode_ranges(lines) when already computed (a long file takes a while)."""
    st = state(self)
    rng, incomplete, unchecked = ranges if ranges is not None else gcode_ranges(lines, st.axes)
    out, exceed = [], 0
    for m, w in nz.items():
        if m in unchecked:
            out.append(f"    {m}: some moves could not be followed (relative moves, expressions, G1 H, G53 or "
                       "arcs): not checked")
        if m not in rng:
            continue
        lo, hi = rng[m]
        a, b = st.axes.get(m, {}).get('min'), st.axes.get(m, {}).get('max')
        bad = (a is not None and lo + w < a - TOL) or (b is not None and hi + w > b + TOL)
        exceed += bool(bad)
        lim = f"limits {a:g} ... {b:g} mm" if a is not None and b is not None else "limits unknown"
        out.append(f"    {m}: {lo:.3f} ... {hi:.3f} mm in the file -> {lo + w:.3f} ... {hi + w:.3f} mm "
                   f"({lim}){'  EXCEEDS THE LIMITS' if bad else ''}")
    return out, exceed, bool(rng) or bool(unchecked), incomplete, unchecked & set(nz)


def _status_text(self, text):
    lbl = getattr(self, 'statusDuetMessage', None)
    if lbl is not None and hasattr(lbl, 'setText'):
        lbl.setText(text)


def confirm_start(self, fname, lines):
    """Start hook (fcn_duet._start_selected_gcode_execution_impl), before anything moves: True to go on.

    The user confirms first only when: the zero is not the device's standard one (custom, or KINETIQ offsets 0 after
    a reset), the zero cannot be read, an axis of the file goes past its M208 limits (with its offset, 0 where none;
    also with the standard zero), an offset is set and the file's moves on it cannot be followed, the file changes
    positions / offsets / the workplace or moves in machine coordinates or on arcs (G92, G10, G54-G59.3, G53, G2 /
    G3), a KINETIQ file sends A-D outside LogIQ's actuator range (0.2-70 mm machine), a KINETIQ file lacks
    Planning's work-zero line, or the file moves an axis the connected board does not have (it would not move: 'c on
    a board that uses 'b for SI, A-D on DYNAMIQ).  A centred KINETIQ file from Planning, inside the limits, with the
    standard zero starts without a question."""
    st = state(self)
    fresh = False
    if getattr(self, 'duet_connected', False):
        try:
            fresh = read_board(self)                  # the Duet's zero now
        except Exception:
            fresh = False
    unread = not (fresh and st.from_board)
    lines = list(lines or [])
    ranges = gcode_ranges(lines, st.axes)
    rng, _incomplete, unchecked_all = ranges
    file_motors = set(rng) | set(unchecked_all)
    dev = device_of(self)
    if dev not in ROWS:
        dev = (KINETIQ if file_motors & KINETIQ_MOTORS else
               DYNAMIQ if file_motors and file_motors <= {"X", "Y", "Z"} else None)
    dev_txt = dev or "the board"
    custom = custom_offsets(self, dev)
    nz = nonzero_offsets(self)
    reasons, parts = [], []

    # the zero
    if unread:
        reasons.append("zero not read")
        parts.append(f"The zero of {dev_txt} could not be read from the Duet just now"
                     + (" (the checks below use the last known values)" if nz else "") +
                     f". {fname} runs displaced if the zero is not the standard one, {_standard_text(dev)}.")
    elif custom:
        reasons.append("custom zero")
        text = (f"The zero of {dev_txt} is not the standard one, {_standard_text(dev)}:\n" +
                "\n".join(f"    {MOTOR_NAMES.get(m, m)}: 0 at machine {w:.3f} mm (standard {s:.3f})"
                          for m, (w, s) in custom.items()))
        if dev == KINETIQ and _kinetiq_at_home(self):
            text += "\n" + _HOME_NOT_CENTRE
        parts.append(text + f"\n{fname} runs displaced by this zero.")
    else:
        parts.append(f"Work zero of {dev_txt}: {_standard_text(dev)}, the standard one.")

    # axes the file moves that the connected board does not have (e.g. 'c on a board with 'b for SI, A-D on DYNAMIQ):
    # the Duet ignores such a letter, so that axis would not move
    missing = (sorted((m for m in file_motors if m not in st.axes), key=_order)
               if getattr(self, 'duet_connected', False) and st.axes else [])
    if missing:
        reasons.append("axes the board does not have")
        names = ", ".join(missing)
        text = (f"This file moves {names}: the connected board ({dev_txt}) does not have "
                f"{'this axis' if len(missing) == 1 else 'these axes'}, so {names} would not move.")
        own = [m for m in SI_SECOND if m in st.axes]
        if own and any(m in missing for m in SI_SECOND) and "'a" in file_motors and "'a" in st.axes:
            text += f" This board uses {own[0]} for SI, so only 'a of SI would move."
        parts.append(text)

    # the M208 limits (machine positions) with the offset, 0 where none: EVERY axis the file moves, also with the
    # standard zero; the dialog lists the axes with an offset and every axis that goes past its limits
    file_read = any(str(l).strip() for l in lines)
    incomplete = bool(_incomplete)
    frame = _frame_changes(lines) if incomplete else []        # G92 / G10 / G53 / G54-G59 / arcs: Start asks
    unchecked = set(unchecked_all) & set(nz)          # relative moves without a start etc. matter where an offset is
    axes_w = {m: st.offsets.get(m, 0.0) for m in sorted(set(rng) | set(nz), key=_order)}
    per_axis = {m: start_check_lines(self, {m: w}, lines, ranges) for m, w in axes_w.items()}
    exceeding = [m for m in axes_w if per_axis[m][1]]
    check = [ln for m in axes_w if m in nz or m in exceeding for ln in per_axis[m][0]]
    checked_txt = (", so it may still go past the limits. Checked:\n" + "\n".join(check) if check else
                   ", so it was not fully checked against the limits.")
    if not file_read:
        if nz:
            reasons.append("file not read")
            parts.append("The file could not be read, so it was not checked against the limits.")
    elif exceeding:
        reasons.append("past the limits")
        parts.append(("With the work zero, " if nz else "") + f"{len(exceeding)} axis/axes of this file go past the "
                     "limits:\n" + "\n".join(check) + "\nThe Duet stops those moves at the limit without an error (the "
                     "motion is cut off there)." +
                     ("\nSome moves could not be followed and were not checked." if incomplete else ""))
    elif unchecked or frame:
        reasons.append("moves not followed")
        parts.append(_not_followed_text(frame) + checked_txt)
    elif nz:
        if not (rng or unchecked_all):
            parts.append("This file does not move any axis (no G0 / G1 moves found).")
        elif incomplete:
            parts.append(_not_followed_text([]) + checked_txt)
        elif check:
            parts.append("With the work zero, this file stays inside the limits:\n" + "\n".join(check))
        else:
            parts.append("This file does not move the axes that have an offset.")

    # KINETIQ files: actuator range and Planning's work-zero line
    if dev != DYNAMIQ and file_motors & KINETIQ_MOTORS:
        act = []
        for m in ACTUATORS:
            if m not in rng:
                continue
            lo_f, hi_f = rng[m]
            lo, hi = actuator_bounds(self, m)
            if lo_f < lo - TOL or hi_f > hi + TOL:
                off = motor_offset(self, m)
                act.append(f"    {m}: {lo_f:.3f} ... {hi_f:.3f} mm in the file -> {lo_f + off:.3f} ... "
                           f"{hi_f + off:.3f} mm machine")
        if act:
            reasons.append("actuators outside their range")
            parts.append(f"Actuators of this file go outside LogIQ's actuator range of {actuator_range_text()}:\n"
                         + "\n".join(act))
        if not has_kinetiq_frame_marker(lines):
            reasons.append("no work-zero line")
            c = KINETIQ_CENTRE_DOF
            parts.append("This file has no 'Work zero: KINETIQ platform centre' line: if it was written for the old "
                         f"frame (0 at home) it runs displaced by LAT {c['LAT']:g} / SI {c['SI']:g} / AP "
                         f"{c['AP']:g} mm.")

    if not reasons:
        return True
    title = "Work zero" if ("zero not read" in reasons or "custom zero" in reasons) else "Confirm start"
    _status_text(self, "Waiting for the confirmation of the start (work zero)...")
    if QMessageBox.question(self, title, "\n\n".join(parts + [f"Start {fname} anyway?"]),
                            QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.Yes:
        _console(self, f"Work zero: start of {fname} confirmed ({', '.join(reasons)}).", color=NOTE)
        _status_text(self, f"Pre-positioning to starting coordinates of {fname}...")
        return True
    msg = f"Start cancelled: not confirmed (work zero: {', '.join(reasons)})."
    _console(self, msg, color=NOTE)
    _status_text(self, msg)
    # the fresh read above ran the listeners while Start was running (Set zero unavailable: job_running) and no poll
    # follows a cancelled Start: refresh them once Start has returned
    QTimer.singleShot(0, lambda: _notify(self))
    return False
