"""
Work-zero frame of the devices (pure values and helpers: no Qt, no network).

KINETIQ (motion platform) G-code coordinates are centred (user decision 2026-11-14):
whenever LogIQ homes KINETIQ it sets the Duet's G54 workplace offset (G10 L2) to the
platform centre, so G-code 0 is the centre of the platform:
    LAT  motors 'e 'f   machine 50 mm  ->  G-code 0
    SI   motors 'a 'c   machine 25 mm  ->  G-code 0   ('b on boards that use it instead of 'c)
    AP   actuators A-D  machine 45 mm  ->  G-code 0
G-code = machine - offset. With the Duet ranges of MP_setup_files/config.g (M208 'e/'f 0:100,
'a/'c 0:60, A-D 0:90) the travel in G-code coordinates is LAT -50..+50, SI -25..+35 and
A-D -45..+45. LAT and SI home at their maximum switch, so at home LAT reads +50, SI +35
and A-D -45.

DYNAMIQ (lung phantom) keeps 0 at home: its default offset is 0 on every axis.

LogIQ's own actuator envelope for A-D (0.2-70 mm, from the original code) is a physical
range: in G-code coordinates it is 0.2 - offset .. 70 - offset.
"""

LAT_MOTORS = ("'e", "'f")
SI_MOTORS = ("'a", "'c", "'b")
SI_SECOND = ("'c", "'b")          # the second SI motor: 'c, or 'b on the boards that use it
ACTUATORS = ("A", "B", "C", "D")

# Machine position (mm) that becomes G-code 0 on KINETIQ, per degree of freedom.
KINETIQ_CENTRE_DOF = {"LAT": 50.0, "SI": 25.0, "AP": 45.0}

KINETIQ_CENTRE = {}
KINETIQ_CENTRE.update({m: KINETIQ_CENTRE_DOF["LAT"] for m in LAT_MOTORS})
KINETIQ_CENTRE.update({m: KINETIQ_CENTRE_DOF["SI"] for m in SI_MOTORS})
KINETIQ_CENTRE.update({m: KINETIQ_CENTRE_DOF["AP"] for m in ACTUATORS})

# Machine travel (mm) of KINETIQ per degree of freedom, as in MP_setup_files/config.g (M208).
# Used where the board is not available (Planning works offline).
KINETIQ_TRAVEL = {"LAT": (0.0, 100.0), "SI": (0.0, 60.0), "AP": (0.0, 90.0)}

# LogIQ's own range for the actuators A-D in machine mm (kept from the original code).
ACTUATOR_ENVELOPE = (0.2, 70.0)

# Start of the comment line Planning writes into every KINETIQ G-code header. Start asks for a
# confirmation when a KINETIQ file lacks it: such a file may be written for the old frame
# (0 at home) and would run displaced by the centre.
KINETIQ_FRAME_MARKER = "; Work zero: KINETIQ platform centre = 0"


def kinetiq_frame_comment(si_second="'c"):
    """The full header comment line, e.g. '; Work zero: KINETIQ platform centre = 0
    (LAT 50, SI 25, A-D 45 mm machine); motors LAT 'e 'f, SI 'a 'c, actuators A B C D'.
    `si_second`: the second SI motor the G-code moves ('c, or 'b on boards that use it)."""
    c = KINETIQ_CENTRE_DOF
    return (f"{KINETIQ_FRAME_MARKER} (LAT {c['LAT']:g}, SI {c['SI']:g}, "
            f"A-D {c['AP']:g} mm machine); motors LAT {' '.join(LAT_MOTORS)}, SI 'a {si_second}, "
            f"actuators {' '.join(ACTUATORS)}")


def has_kinetiq_frame_marker(lines, max_lines=200):
    """True when one of the first `max_lines` lines starts with KINETIQ_FRAME_MARKER
    (leading spaces and letter case ignored)."""
    marker = KINETIQ_FRAME_MARKER.lower()
    for i, line in enumerate(lines or ()):
        if i >= max_lines:
            break
        if str(line).strip().lower().startswith(marker):
            return True
    return False


def default_offsets(device, letters=None):
    """Workplace offsets LogIQ sets when it homes `device` ('KINETIQ' / 'DYNAMIQ').

    `letters` (board axis letters such as "'e", 'A', 'X') limits the result to the axes the
    board has; letters without a centre get 0. DYNAMIQ (and anything else) -> all 0."""
    if device == "KINETIQ":
        if letters is None:
            return dict(KINETIQ_CENTRE)
        return {m: KINETIQ_CENTRE.get(m, 0.0) for m in letters}
    if letters is None:
        return {}
    return {m: 0.0 for m in letters}


def actuator_limits(offset=0.0):
    """LogIQ's actuator envelope (A-D) in G-code coordinates for a workplace offset."""
    lo, hi = ACTUATOR_ENVELOPE
    off = float(offset or 0.0)
    return lo - off, hi - off


def kinetiq_plan_range(dof, lim=None):
    """Allowed G-code range of a KINETIQ degree of freedom in a plan ('LAT', 'SI', 'AP';
    'A'-'D' use the AP range), centred frame.

    LAT / SI: the machine travel minus the centre; AP and the actuators: LogIQ's actuator
    envelope minus the AP centre. `lim` (the Planning setting "Max Lim.", a maximum excursion
    either side of 0) narrows it to [-lim, +lim] when given."""
    key = "AP" if dof in ACTUATORS else dof
    centre = KINETIQ_CENTRE_DOF[key]
    if key == "AP":
        lo, hi = ACTUATOR_ENVELOPE
    else:
        lo, hi = KINETIQ_TRAVEL[key]
    lo, hi = lo - centre, hi - centre
    if lim is not None:
        lim = abs(float(lim))
        lo, hi = max(lo, -lim), min(hi, lim)
        if lo > hi:                      # a limit that excludes 0 cannot happen with lim >= 0
            lo = hi = 0.0
    return lo, hi
