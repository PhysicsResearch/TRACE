"""
Planning limits: the range each planned axis may use, in G-code coordinates (new file, 2026-11-15).

* Planning > Settings shows "<axis> limits (mm): min to max": DYNAMIQ X Y Z; KINETIQ LAT SI AP (the actuators A-D use
  the AP limits, 'e 'f the LAT limits, 'a 'c|'b the SI limits).
* They come from the connected board: its M208 limits (move.axes[].min / max, machine mm, which work_zero records on
  every status poll) minus the device's standard zero (KINETIQ centre LAT 50, SI 25, A-D 45 mm; DYNAMIQ 0). They are
  taken once per connection (and again if the board's limits change), so values typed while connected stay.
  Offline: the last values (configuration.json, tab_planning persistence) or the config.g defaults below.
* Planning no longer cuts values off at these limits. Export and upload check every G-code axis against them and
  warn (confirm_plan_limits); Roll / Pitch / Yaw are checked against Settings "Max Lim." (deg).
"""

from fcn_control.work_zero_frame import ACTUATORS, KINETIQ_CENTRE_DOF, KINETIQ_TRAVEL, LAT_MOTORS

PHANTOM = "Lung Phantom"            # Planning device names (combo_device)
PLATFORM = "Motion Platform"

PLAN_DOFS = {PHANTOM: ("X", "Y", "Z"), PLATFORM: ("LAT", "SI", "AP")}

# Offline defaults = the boards' config.g M208 (DYNAMIQ_setup_files: X0:40 Y0:40 Z0:40; MP_setup_files: 'e 'f 0:100,
# 'a 'c 0:60, A-D 0:90) in G-code coordinates
DEFAULT_RANGES = {
    PHANTOM: {"X": (0.0, 40.0), "Y": (0.0, 40.0), "Z": (0.0, 40.0)},
    PLATFORM: {dof: (lo - KINETIQ_CENTRE_DOF[dof], hi - KINETIQ_CENTRE_DOF[dof])
               for dof, (lo, hi) in KINETIQ_TRAVEL.items()},
}

ROTATIONS = ("Roll", "Pitch", "Yaw")
LIMIT_TOL = 1e-3                    # mm / deg: closer than this outside a limit counts as inside (rounding)
SPIN_MIN, SPIN_MAX = -1000.0, 1000.0


def dof_of_letter(device, letter):
    """Plan degree of freedom whose limits apply to a G-code axis letter ('C' -> 'AP', "'e" -> 'LAT', 'X' -> 'X')."""
    if device == PLATFORM:
        if letter in ACTUATORS:
            return "AP"
        if letter in LAT_MOTORS:
            return "LAT"
        if letter in ("'a", "'c", "'b"):
            return "SI"
        return None
    if device == PHANTOM and letter in PLAN_DOFS[PHANTOM]:
        return letter
    return None


def axis_name(device, letter):
    """Name of a G-code axis in a message: 'actuator C', "LAT motor 'e", 'X'."""
    if device == PLATFORM:
        if letter in ACTUATORS:
            return f"actuator {letter}"
        dof = dof_of_letter(device, letter)
        return f"{dof} motor {letter}" if dof else letter
    return letter


# --------------------------------------------------------------------------------------------------------- settings UI
def add_limit_setting(self, layout, parent, device, dof, row, col):
    """Planning > Settings cell "<dof> limits (mm): [min] to [max]" at (row, col) of the settings grid, in the style of
    tab_planning.add_setting_spinbox. Returns (min_spin, max_spin), also kept in self._plan_limit_spins."""
    from PySide6.QtWidgets import QDoubleSpinBox, QHBoxLayout, QLabel, QVBoxLayout

    lo_def, hi_def = DEFAULT_RANGES[device][dof]
    lbl = QLabel(f"{dof} limits (mm):", parent)
    lbl.setStyleSheet("font-weight: bold; font-size: 13px;")
    spins = []
    for v in (lo_def, hi_def):
        sp = QDoubleSpinBox(parent)
        sp.setDecimals(1)
        sp.setRange(SPIN_MIN, SPIN_MAX)
        sp.setSingleStep(1.0)
        sp.setValue(v)
        sp.setMinimumHeight(38)
        sp.setMinimumWidth(70)
        spins.append(sp)
    to = QLabel("to", parent)
    row_l = QHBoxLayout()
    row_l.setSpacing(4)
    row_l.addWidget(spins[0], 1)
    row_l.addWidget(to)
    row_l.addWidget(spins[1], 1)
    sub_v = QVBoxLayout()
    sub_v.setSpacing(2)
    sub_v.addWidget(lbl)
    sub_v.addLayout(row_l)
    layout.addLayout(sub_v, row, col)

    store = getattr(self, '_plan_limit_spins', None)
    if store is None:
        store = self._plan_limit_spins = {}
    store[(device, dof)] = (spins[0], spins[1], lbl)
    _set_tooltip(self, device, dof, None)
    return spins[0], spins[1]


def persistence_map(self):
    """{config key: spin box} of the limit fields, for tab_planning.setup_settings_persistence."""
    out = {}
    for (device, dof), (lo, hi, _lbl) in (getattr(self, '_plan_limit_spins', None) or {}).items():
        out[f"plan_lim_{dof.lower()}_min"] = lo
        out[f"plan_lim_{dof.lower()}_max"] = hi
    return out


def _set_tooltip(self, device, dof, source):
    entry = (getattr(self, '_plan_limit_spins', None) or {}).get((device, dof))
    if entry is None:
        return
    lo, hi, lbl = entry
    if device == PLATFORM:
        motors = {"LAT": "the LAT motors 'e and 'f", "SI": "the SI motors 'a and 'c ('b)",
                  "AP": "AP and every actuator A, B, C, D"}[dof]
        frame = "around the KINETIQ centre (0)"
    else:
        motors = dof
        frame = "from home (0)"
    origin = source or ("the board's limits (M208) when LogIQ connects; offline the last values, else the "
                        "standard config.g")
    tip = (f"Range {frame} that {motors} may use in a plan, in G-code coordinates.\n"
           f"Taken from {origin}.\n"
           f"Planning does not cut values off at these limits: exporting or uploading G-code that leaves them asks "
           f"you to confirm.")
    for w in (lo, hi, lbl):
        w.setToolTip(tip)


def plan_ranges(self, device):
    """{dof: (lo, hi)} of the limit fields (G-code coordinates), else the defaults; lo <= hi."""
    store = getattr(self, '_plan_limit_spins', None) or {}
    out = {}
    for dof in PLAN_DOFS.get(device, ()):
        entry = store.get((device, dof))
        if entry is not None:
            a, b = float(entry[0].value()), float(entry[1].value())
        else:
            a, b = DEFAULT_RANGES[device][dof]
        out[dof] = (min(a, b), max(a, b))
    return out


def rotation_limits(self):
    """{'Roll' | 'Pitch' | 'Yaw': deg} from Settings "Max Lim." (40 when the field is missing)."""
    out = {}
    for r in ROTATIONS:
        w = getattr(self, f'settings_max_lim_{r.lower()}', None)
        try:
            out[r] = abs(float(w.value())) if w is not None else 40.0
        except Exception:
            out[r] = 40.0
    return out


def other_limit(self):
    """Planning device 'Other': the symmetric limit it always used, now the larger end of the LAT limits."""
    lo, hi = plan_ranges(self, PLATFORM)["LAT"]
    return max(abs(lo), abs(hi))


# ------------------------------------------------------------------------------------------------- from the board
def board_ranges(self):
    """(planning device, {dof: (lo, hi)}) of the connected board in G-code coordinates, or None (not connected,
    device or limits unknown). A degree of freedom with several motors gets the range all of them can reach."""
    if not getattr(self, 'duet_connected', False):
        return None
    try:
        from fcn_control import work_zero as wz
    except Exception:
        return None
    device = wz.device_of(self)
    if device == 'KINETIQ':
        plan_dev = PLATFORM
        motors = {"LAT": LAT_MOTORS, "SI": wz.board_si_motors(self) or ("'a", "'c"), "AP": ACTUATORS}
        centre = KINETIQ_CENTRE_DOF
    elif device == 'DYNAMIQ':
        plan_dev = PHANTOM
        motors = {d: (d,) for d in PLAN_DOFS[PHANTOM]}
        centre = {d: 0.0 for d in PLAN_DOFS[PHANTOM]}
    else:
        return None
    axes = getattr(wz.state(self), 'axes', None) or {}
    ranges = {}
    for dof, ms in motors.items():
        los, his = [], []
        for m in ms:
            a = axes.get(m)
            if not isinstance(a, dict) or a.get('min') is None or a.get('max') is None:
                los = None
                break
            los.append(float(a['min']))
            his.append(float(a['max']))
        if los:
            ranges[dof] = (round(max(los) - centre[dof], 3), round(min(his) - centre[dof], 3))
    return (plan_dev, ranges) if ranges else None


def _on_status_poll(self):
    """work_zero listener (every status poll): the board's limits into the Planning fields, once per connection and
    whenever they change."""
    res = board_ranges(self)
    if res is None:
        return
    plan_dev, ranges = res
    try:
        from fcn_control.work_zero import device_of
        dev_name = device_of(self) or plan_dev
    except Exception:
        dev_name = plan_dev
    key = (plan_dev, tuple(sorted(ranges.items())))
    if getattr(self, '_plan_limits_applied', None) == key:
        return
    self._plan_limits_applied = key
    store = getattr(self, '_plan_limit_spins', None) or {}
    changed = []
    for dof, (lo, hi) in ranges.items():
        entry = store.get((plan_dev, dof))
        if entry is None:
            continue
        lo_sp, hi_sp, _lbl = entry
        if abs(lo_sp.value() - lo) > 1e-6 or abs(hi_sp.value() - hi) > 1e-6:
            changed.append(f"{dof} {lo:g} to {hi:g}")
        lo_sp.setValue(lo)                      # valueChanged: tab_planning persistence saves them
        hi_sp.setValue(hi)
        _set_tooltip(self, plan_dev, dof, f"the connected {dev_name} board (M208)")
    if changed:
        msg = f"Planning limits read from {dev_name}: " + ", ".join(changed) + " mm"
        print(msg)
        try:
            from fcn_control.fcn_control import log_to_duet_console
            log_to_duet_console(self, msg)
        except Exception:
            pass


def install(self):
    """Registers the board -> Planning limits update (idempotent)."""
    if getattr(self, '_plan_limits_installed', False):
        return
    try:
        from fcn_control.work_zero import add_listener
    except Exception as e:
        print(f"Planning limits: not read from the board ({e})")
        return
    add_listener(self, _on_status_poll)
    self._plan_limits_installed = True


def connection_changed(self, connected):
    """fcn_control.update_connection_status_ui hook: the next connection takes the board's limits again."""
    if not connected:
        self._plan_limits_applied = None


# ---------------------------------------------------------------------------------------------- export / upload check
def find_violations(device, axis_extent, ranges, rot_extent=None, rot_limits=None):
    """[(name, lowest, highest, lo, hi, unit)] for every G-code axis (axis_extent {letter: (min, max)}, from
    fcn_gcode.generate_gcode_string's info) and rotation (rot_extent {'Roll': (min, max)}) that leaves its limits."""
    out = []
    for letter, (vmin, vmax) in (axis_extent or {}).items():
        dof = dof_of_letter(device, letter)
        if dof is None or dof not in ranges:
            continue
        lo, hi = ranges[dof]
        if vmin < lo - LIMIT_TOL or vmax > hi + LIMIT_TOL:
            out.append((axis_name(device, letter), vmin, vmax, lo, hi, "mm"))
    for r, (vmin, vmax) in (rot_extent or {}).items():
        lim = (rot_limits or {}).get(r)
        if lim is None:
            continue
        if vmin < -lim - LIMIT_TOL or vmax > lim + LIMIT_TOL:
            out.append((r, vmin, vmax, -lim, lim, "deg"))
    return out


def violations_text(violations, max_lines=8):
    lines = []
    for name, vmin, vmax, lo, hi, unit in violations[:max_lines]:
        parts = []
        if vmin < lo - LIMIT_TOL:
            parts.append(f"down to {vmin:.2f}")
        if vmax > hi + LIMIT_TOL:
            parts.append(f"up to {vmax:.2f}")
        lines.append(f"• {name}: {' and '.join(parts)} {unit} (limits {lo:g} to {hi:g} {unit})")
    if len(violations) > max_lines:
        lines.append(f"• … and {len(violations) - max_lines} more")
    return "\n".join(lines)


def confirm_plan_limits(self, device, gcode_info, columns_data):
    """Export / upload: True to go on. When the G-code leaves the limits, a question lists where; the G-code is not
    changed (no cut-off): the controller itself stops every motor at its M208 limit."""
    if device not in PLAN_DOFS:
        return True
    rot_extent = {}
    if device == PLATFORM:
        import numpy as np
        for r in ROTATIONS:
            if r in columns_data:
                v = np.asarray(columns_data[r], dtype=float)
                v = v[np.isfinite(v)]
                if v.size:
                    rot_extent[r] = (float(v.min()), float(v.max()))
    violations = find_violations(device, (gcode_info or {}).get('axis_extent'), plan_ranges(self, device),
                                 rot_extent, rotation_limits(self))
    if not violations:
        return True
    from PySide6.QtWidgets import QMessageBox
    text = ("This plan goes beyond the limits in Planning > Settings:\n\n" + violations_text(violations) +
            "\n\nThe G-code keeps the planned values. The controller stops every motor at its own limit (M208), so "
            "the run would not follow the plan there.\n\nDo you still want to proceed?")
    self._last_limit_question = text                    # for tests
    res = QMessageBox.question(self, "Limits Exceeded", text, QMessageBox.Yes | QMessageBox.No)
    return res == QMessageBox.Yes
