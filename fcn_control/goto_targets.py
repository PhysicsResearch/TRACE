"""
Control tab "Go to" buttons: move only the axes whose Target differs from the Current position; 0 is a valid target.

* Typed targets are kept.  The status poll copies Current into every Target field that has no keyboard focus, so a
  value typed in one field was lost as soon as another field (or the touch keypad) took the focus, and Go then moved
  nothing or the wrong set of axes.  A Target that differs from Current is now marked pending (amber border) and the
  poll leaves it alone (hook in fcn_control.update_duet_status_ui) until Go / Return sends it, or until Current
  reaches it.
* Lung phantom "Go to": only X / Y / Z whose Target differs from Current are moved (and only those must be homed).
* Motion platform "Go to ...": LAT moves 'e 'f, SI moves 'a 'c/'b, and A B C D are recomputed only when AP, Roll or
  Pitch changed; motors whose new position equals the current one are left out.  The lower limit is the board's
  M208 minimum (0 on KINETIQ) instead of the fixed 0.2 mm, so 0 can be reached; the actuator maximum stays capped at
  70 mm as before.  A target within 0.001 mm of a limit (rounding of the shown angles) is set to the limit.
"""
import math

from PySide6.QtWidgets import QMessageBox

TOL = 0.0005                 # fields show 3 decimals: smaller differences are "the same position"
LIMIT_SNAP = 0.001           # mm: a computed target this close outside a limit is put on the limit

LUNG_AXES = [('XAXIS_LUNG', 'X'), ('YAXIS_LUNG', 'Y'), ('ZAXIS_LUNG', 'Z')]
PLATFORM_DOFS = ['LATAXIS', 'SIAXIS', 'APAXIS', 'ROLL', 'PITCH', 'YAW']
PENDING_STYLE = "QLineEdit[pendingTarget=\"true\"] { border: 2px solid #ff9800; }"


def _num(text):
    try:
        return float(str(text).strip())
    except (TypeError, ValueError):
        return None


def _field(self, prefix, ax):
    return getattr(self, f"{prefix}_{ax}", None)


def _same(a, b):
    a, b = _num(a), _num(b)
    return a is not None and b is not None and abs(a - b) <= TOL


# ---------------------------------------------------------------------------------------------- pending targets
def _set_pending(des, on):
    if bool(des.property('pendingTarget')) == bool(on):
        return
    des.setProperty('pendingTarget', bool(on))
    des.style().unpolish(des)
    des.style().polish(des)


def clear_pending(self, axes=None):
    for ax in (axes if axes is not None else [a for a, _ in LUNG_AXES] + PLATFORM_DOFS):
        des = _field(self, 'POS_DES', ax)
        if des is not None:
            _set_pending(des, False)


def install_goto_targets(self):
    """Idempotent: pending-target marking on every Target field of the Control tab."""
    if getattr(self, '_goto_targets_installed', False):
        return
    for ax in [a for a, _ in LUNG_AXES] + PLATFORM_DOFS:
        des, cur = _field(self, 'POS_DES', ax), _field(self, 'POS_CURR', ax)
        if des is None or cur is None:
            continue
        if PENDING_STYLE not in (des.styleSheet() or ""):
            des.setStyleSheet((des.styleSheet() or "") + "\n" + PENDING_STYLE)

        def target_changed(_t=None, d=des, c=cur):
            # typed / keypad / Go to center: pending when it differs; the poll's own copy (Current -> Target) is
            # "the same" and never marks a field pending
            _set_pending(d, not _same(d.text(), c.text()))

        def current_changed(_t=None, d=des, c=cur):
            if d.property('pendingTarget') and _same(d.text(), c.text()):
                _set_pending(d, False)                   # the axis has arrived: the field tracks again
        des.textChanged.connect(target_changed)
        cur.textChanged.connect(current_changed)
    self._goto_targets_installed = True


# ---------------------------------------------------------------------------------------------- helpers
def _not_connected(self):
    from fcn_control.fcn_control import log_to_duet_console
    if getattr(self, 'duet_connected', False):
        return False
    log_to_duet_console(self, "Error: Not connected to Duet.", color="#ff3333")
    QMessageBox.warning(self, "Not Connected", "Please connect to Duet before moving axes.")
    return True


def _check_homed(self, keys_names):
    from fcn_control.fcn_control import is_axis_homed, log_to_duet_console
    for key, name in keys_names:
        if not is_axis_homed(self, key):
            log_to_duet_console(self, f"Error: Cannot move {name}. Please home the axis first!", color="#ff3333")
            QMessageBox.warning(self, "Axis Not Homed", f"Cannot move {name}.\nPlease home the axis first!")
            return False
    return True


def _changed(self, axes):
    """{axis: (target, current)} for the axes whose Target differs from Current; None if a Target is not a number."""
    from fcn_control.fcn_control import log_to_duet_console
    out = {}
    for ax in axes:
        des, cur = _field(self, 'POS_DES', ax), _field(self, 'POS_CURR', ax)
        if des is None or cur is None:
            continue
        t, c = _num(des.text()), _num(cur.text())
        if t is None:
            log_to_duet_console(self, f"Error: Invalid target value '{des.text()}' for {ax}.", color="#ff3333")
            QMessageBox.warning(self, "Invalid Target", f"The target for {ax} is not a number: '{des.text()}'")
            return None
        if c is None or abs(t - c) > TOL:
            out[ax] = (t, c)
    return out


def _limits(self, motor, default_min, default_max, cap_max=None):
    mn = (getattr(self, 'axis_min_limits', None) or {}).get(motor, default_min)
    mx = (getattr(self, 'axis_max_limits', None) or {}).get(motor, default_max)
    if cap_max is not None:
        mx = min(mx, cap_max)
    return float(mn), float(mx)


def _fit(value, mn, mx):
    """value inside [mn, mx] (snapped onto a limit when within LIMIT_SNAP), or None when outside."""
    if mn - LIMIT_SNAP <= value < mn:
        return mn
    if mx < value <= mx + LIMIT_SNAP:
        return mx
    return value if mn <= value <= mx else None


def _curr_motor(self, names):
    for n in names:
        f = getattr(self, f"POS_CURR_{n}", None)
        if f is not None and _num(f.text()) is not None:
            return _num(f.text())
    return None


def _platform_value(self, name, default):
    f = getattr(self, name, None)
    v = _num(f.text()) if f is not None else None
    return v if v is not None else default


# ---------------------------------------------------------------------------------------------- lung phantom
def go_lung_changed(self):
    from fcn_control.fcn_control import log_to_duet_console, move
    if _not_connected(self):
        return
    changed = _changed(self, [a for a, _ in LUNG_AXES])
    if changed is None:
        return
    if not changed:
        log_to_duet_console(self, "Go to: all lung phantom targets equal the current positions, nothing to move.")
        return
    names = dict(LUNG_AXES)
    if not _check_homed(self, [(ax, names[ax]) for ax in changed]):
        return
    log_to_duet_console(self, "Go to: moving " + ", ".join(f"{names[ax]} -> {t:.3f}" for ax, (t, _c) in changed.items()))
    for ax in changed:
        move(self, ax)
    clear_pending(self, [a for a, _ in LUNG_AXES])


# ---------------------------------------------------------------------------------------------- motion platform
def actuator_heights(self, ap, roll, pitch, yaw):
    """A B C D heights for AP / Roll / Pitch / Yaw (same kinematics as fcn_control.go_to_desired_positions)."""
    lat_dim = _platform_value(self, 'input_plat_lat', 100.0)
    si_dim = _platform_value(self, 'input_plat_si', 100.0)
    lat_dim = lat_dim if lat_dim > 0 else 100.0
    si_dim = si_dim if si_dim > 0 else 100.0
    zc = _platform_value(self, 'input_offset_ap', 0.0)
    r, p, y = math.radians(roll), -math.radians(pitch), math.radians(yaw)
    pts = {'A': (-lat_dim / 2, -si_dim / 2), 'B': (lat_dim / 2, -si_dim / 2),
           'C': (lat_dim / 2, si_dim / 2), 'D': (-lat_dim / 2, si_dim / 2)}
    out = {}
    for name, (x1, y1) in pts.items():
        z1 = -zc
        x2, y2 = math.cos(y) * x1 - math.sin(y) * y1, math.sin(y) * x1 + math.cos(y) * y1
        x3, z3 = x2 * math.cos(r) + z1 * math.sin(r), -x2 * math.sin(r) + z1 * math.cos(r)
        z4 = y2 * math.sin(p) + z3 * math.cos(p)
        out[name] = z4 + zc + ap
    return out


def plan_platform(self):
    """(commands, description, errors) for the changed platform targets; ([], [], []) when nothing changed."""
    changed = _changed(self, PLATFORM_DOFS)
    if changed is None:
        return None
    errors, cmds, desc = [], [], []
    if 'YAW' in changed:
        errors.append("Yaw motion is not implemented yet (Yaw target ignored).")
        changed.pop('YAW')
    y_lo = "'b" if ("b" in (getattr(self, 'axis_max_limits', None) or {}) or
                    "'b" in (getattr(self, 'axis_max_limits', None) or {})) else "'c"

    horiz = []
    for dof, motors in (('LATAXIS', ["'e", "'f"]), ('SIAXIS', ["'a", y_lo])):
        if dof not in changed:
            continue
        t = changed[dof][0]
        for m in motors:
            mn, mx = _limits(self, m, 0.0, 200.0)
            v = _fit(t, mn, mx)
            if v is None:
                errors.append(f"{dof[:-4]} target {t:.3f} mm is outside the {m} limits [{mn:.1f}, {mx:.1f}] mm.")
            else:
                cur = _curr_motor(self, [m.strip("'"), m])
                if cur is None or abs(v - cur) > TOL:
                    horiz.append(f"{m}{v:.4f}")
        desc.append(f"{dof[:-4]} -> {t:.3f}")

    vert = []
    if any(d in changed for d in ('APAXIS', 'ROLL', 'PITCH')):
        def val(d):
            f = _field(self, 'POS_DES', d)
            return _num(f.text()) if f is not None and _num(f.text()) is not None else 0.0
        yaw_cur = _num(getattr(self, 'POS_CURR_YAW').text()) if getattr(self, 'POS_CURR_YAW', None) is not None else 0.0
        heights = actuator_heights(self, val('APAXIS'), val('ROLL'), val('PITCH'), yaw_cur or 0.0)
        for m in ['A', 'B', 'C', 'D']:
            mn, mx = _limits(self, m, 0.0, 70.0, cap_max=70.0)
            v = _fit(heights[m], mn, mx)
            if v is None:
                errors.append(f"Actuator {m} target {heights[m]:.3f} mm is out of bounds [{mn:.1f}, {mx:.1f}] mm.")
            else:
                cur = _curr_motor(self, [m])
                if cur is None or abs(v - cur) > TOL:
                    vert.append(f"{m}{v:.4f}")
        desc += [f"{n} -> {changed[d][0]:.3f}" for d, n in (('APAXIS', 'AP'), ('ROLL', 'Roll'), ('PITCH', 'Pitch'))
                 if d in changed]

    blocking = [e for e in errors if not e.startswith("Yaw")]
    if blocking:
        return [], desc, errors
    if horiz:
        cmds.append("G1 " + " ".join(horiz) + " F600")
    if vert:
        cmds.append("G1 " + " ".join(vert) + " F600")
    return cmds, desc, errors


def go_platform_changed(self):
    from fcn_control.fcn_control import log_to_duet_console, send_cmd
    if _not_connected(self):
        return
    plan = plan_platform(self)
    if plan is None:
        return
    cmds, desc, errors = plan
    for e in errors:
        log_to_duet_console(self, f"Error: {e}" if not e.startswith("Yaw") else f"Warning: {e}",
                            color="#ff3333" if not e.startswith("Yaw") else "#ff9800")
    if any(not e.startswith("Yaw") for e in errors):
        log_to_duet_console(self, "Error: Move command blocked.", color="#ff3333")
        QMessageBox.warning(self, "Limit Exceeded", "Cannot complete move.\n" +
                            "\n".join(e for e in errors if not e.startswith("Yaw")))
        return
    if not cmds:
        clear_pending(self, PLATFORM_DOFS)
        log_to_duet_console(self, "Go to: all platform targets equal the current positions, nothing to move.")
        return
    moved = {d.split(" ")[0] for d in desc}
    need = [(k, n) for k, n in (('LATAXIS', 'LAT'), ('SIAXIS', 'SI')) if n in moved]
    if moved & {'AP', 'Roll', 'Pitch'}:
        need += [('APAXIS', 'AP'), ('ROLL', 'Roll'), ('PITCH', 'Pitch')]
    if not _check_homed(self, need):
        return
    send_cmd(self, "G90")
    for c in cmds:
        send_cmd(self, c)
    log_to_duet_console(self, "Go to: " + ", ".join(desc))
    clear_pending(self, PLATFORM_DOFS)
