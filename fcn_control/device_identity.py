"""
Which device is connected: DYNAMIQ (lung phantom) or KINETIQ (motion platform).

Called after a successful connection (fcn_control.setDuetIP).  The board's name (M550 P"..." in config.g) decides:
    KINETIQ, TRACE (the platform's old name), platform   -> KINETIQ
    DYNAMIQ, lung, phantom                               -> DYNAMIQ
If the name says neither, the number of axes the board reports decides (DYNAMIQ: X Y Z; KINETIQ: more).

The result is kept in ``window.connected_device`` ('KINETIQ' / 'DYNAMIQ' / None), the Control tab opens that device's
sub-tab (as before), and the top bar fills the device's button (logiq_shell.show_connected_device).
"""
KINETIQ, DYNAMIQ = "KINETIQ", "DYNAMIQ"
_NAMES = ((KINETIQ, ("kinetiq", "trace", "platform")), (DYNAMIQ, ("dynamiq", "lung", "phan")))


def device_from_name(name):
    n = str(name or "").strip().lower()
    for device, keys in _NAMES:
        if any(k in n for k in keys):
            return device
    return None


def axis_count(ip, timeout=2.0):
    """Number of axes the board reports (rr_model move.axes, fast flags), or None."""
    try:
        from fcn_monitor.fcn_duet import duet_request
        r = duet_request(f"http://{ip}/rr_model?key=move.axes&flags=f", timeout=timeout, retry=False)
        if r.status_code != 200:
            return None
        arr = r.json().get("result")
        return len(arr) if isinstance(arr, list) else None
    except Exception:
        return None


def identify_device(name=None, ip=None):
    """(device, how) - device 'KINETIQ' / 'DYNAMIQ' / None."""
    d = device_from_name(name)
    if d is not None:
        return d, f"name '{name}'"
    if ip:
        n = axis_count(ip)
        if n:
            return (KINETIQ if n > 3 else DYNAMIQ), f"{n} axes"
    return None, "unknown"


def apply_connected_device(window, ip, machine_name=None):
    """After connecting: identify the device, open its Control sub-tab, fill its button in the top bar."""
    device, how = identify_device(machine_name, ip)
    window.connected_device = device
    try:
        from fcn_control.fcn_control import log_to_duet_console
        if machine_name:
            log_to_duet_console(window, f"Machine name: {machine_name}")
        log_to_duet_console(window, f"Device: {device} ({how})" if device else
                            "Device: not recognised (name and axes say neither DYNAMIQ nor KINETIQ)")
    except Exception:
        pass
    tw = getattr(window, 'tabWidget', None)                       # Control tab: DYNAMIQ / KINETIQ / IND. MOTORS
    page = {KINETIQ: getattr(window, 'tab_platform', None), DYNAMIQ: getattr(window, 'tab', None)}.get(device)
    if tw is not None and page is not None:
        try:
            tw.setCurrentWidget(page)
        except RuntimeError:
            pass
    try:
        from fcn_create_gui.logiq_shell import show_connected_device
        show_connected_device(window)
    except Exception:
        pass
    return device
