"""
Timing Warning before G-code is written (Export / Upload): only for moves that the Max Speed setting slows down.

Before (until 18 Nov 2026) the warning compared the G-code's total time with the plan (the writer's residual) and
always blamed Max Speed.  On recorded breathing curves the residual is something else: holds of one sample (~40 ms)
are shorter than the Step overhead (KINETIQ 90 ms, the cost of a G4), so the writer carries that time to the next
dwell; what is left at the end (0.04-0.08 s measured on the three VXP files) made the G-code end that much EARLY.
The message then said "Some moves need more than the Max Speed setting (20 mm/s)" for curves that never go above
13 mm/s, and raising Max Speed did not remove it.  That leftover is always below the Step overhead (< 0.2 s), so it
no longer warns.

The writer (fcn_plan/fcn_gcode.generate_gcode_string) now adds up, per move, only the time the Max Speed cap adds
(info['speed_late_s']); this warns when it is more than WARN_MS.  The writer shortens the following dwells by that
time (its carry), so the motion falls behind at those moves and catches up at the next holds where it can: the old
end-of-file residual could hide it (1.vxp, deep breath at 26 mm/s with Max Speed 20: 83 ms of capped moves, net end
residual below 10 ms because the leftover above ran the other way).

    from fcn_plan.speed_warning import speed_warning_text
    text = speed_warning_text(gcode_info, max_speed)          # None: nothing to warn about
"""
WARN_MS = 10.0          # as before: below this the difference does not matter


def speed_warning_text(info, max_speed):
    """The question to ask before writing the G-code, or None."""
    late_s = float((info or {}).get('speed_late_s', 0.0) or 0.0)
    if late_s * 1000.0 <= WARN_MS:
        return None
    return (f"Some moves are faster than the Max Speed setting ({float(max_speed):g} mm/s). The controller runs them "
            f"at Max Speed, so they take {late_s:.2f} s longer than planned: the motion falls behind the plan there "
            f"(the following holds are shortened to catch up where possible).\n\n"
            f"Check the Velocity view of the plot, or raise Max Speed in Settings if the device allows it.\n\n"
            f"Do you still want to proceed?")
