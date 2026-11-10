"""
Compact G1 lines: every axis whose value does not change is left out of the line.

Why (measured on KINETIQ, RRF 3.6, 2026-11-10, scratch/timing_step_after.py): LogIQ wrote every axis on every G1
line, also linear axes that do not move (e.g. 'e0 'f0 'a0 'c0 on an AP-only move).  After a move of a linear axis
(SI or LAT) the controller treats such a line as a move of linear and rotary axes with a near-zero linear part, so
the feed rate applies to that near-zero distance and the AP part (rotary A-D) runs far too fast: a slow 0.46 s AP
step took 0.03 s, and the last breathing cycle of a cos^6 plan ran 0.38 s early.  With the unchanged axes left out
the same step takes its planned time.  G-code readers keep the previous value of an axis a line leaves out (RRF and
fcn_plan.fcn_gcode.GcodeTimelineParser), so the planned timeline is unchanged.

Rules: only absolute moves (G90) are compacted (G91 resets the known positions and leaves lines as they are); F and
every other word stays; a G1 line in which no axis changes is dropped (it moves nothing and takes no time); the first
G1 keeps every axis (positions not known yet).  Comments after ';' stay on the line.

    from fcn_plan.gcode_compact import compact_gcode_lines
    lines = compact_gcode_lines(lines)
"""
import re

_AXIS_WORD = re.compile(r"^('?[A-Za-z])([-+]?(?:\d+\.?\d*|\.\d+))$")
_NOT_AXES = set("FGMPSTHRIJKNE")        # parameter letters on a G0/G1 line that are not axes (E: extruder)


def _is_move(code):
    c = code.upper()
    return c in ("G0", "G1", "G00", "G01")


def compact_gcode_lines(lines):
    """List of G-code lines -> the same list with the unchanged axes left out of G0/G1 lines."""
    pos = {}
    absolute = True
    out = []
    for line in lines:
        text, sep, comment = line.partition(';')
        words = text.split()
        if not words:
            out.append(line)
            continue
        head = words[0].upper()
        if head == "G90":
            absolute = True
        elif head == "G91":
            absolute = False
            pos = {}
        elif head == "G92":
            pos = {}
        if not _is_move(head) or not absolute:
            out.append(line)
            continue
        keep = [words[0]]
        axes_given = axes_left = 0
        for w in words[1:]:
            m = _AXIS_WORD.match(w)
            if not m or (len(m.group(1)) == 1 and m.group(1).upper() in _NOT_AXES):
                keep.append(w)
                continue
            axis, v = m.group(1), float(m.group(2))
            axes_given += 1
            if axis in pos and pos[axis] == v:
                continue
            pos[axis] = v
            keep.append(w)
            axes_left += 1
        if axes_given and not axes_left:
            continue                                   # nothing moves: the line takes no time
        new = " ".join(keep)
        out.append(new + (f" {sep}{comment}" if sep else ""))
    return out


def compact_gcode(text):
    return "\n".join(compact_gcode_lines(text.splitlines()))
