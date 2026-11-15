"""
Planning import of KINETIQ files written for the old frame (0 at home).

KINETIQ G-code is centred (fcn_control/work_zero_frame.py): every KINETIQ G-code made by Planning has the header line
KINETIQ_FRAME_MARKER, and a run log recorded with a work-zero offset names it in its '# Positions:' line
(fcn_control/work_zero.positions_header).  A KINETIQ G-code without that line, or a KINETIQ log without the offset
text, was probably written with 0 at home: its values are machine positions.  Imported as they are and exported
again, the file would get the line and run displaced by the centre (Start would no longer ask).  So the Planning
import asks first:
    [Convert]      the centre is subtracted per motor ('e 'f 50, 'a 'c 'b 25, A-D 45 mm; a log's LAT 50, SI 25,
                   AP 45) before the reverse kinematics / clipping
    [Keep values]  imported as before
    [Cancel]       no import
Files with the line (and logs that name the work-zero offset) import without a question; DYNAMIQ is unchanged.

    df, go_on = check_gcode_import(parent, df, axis_cols, head_lines)     # fcn_create G-code imports
    plan_df, go_on = check_log_import(parent, plan_df, log_path)          # fcn_import LogIQ log import
"""
from fcn_control.work_zero_frame import (ACTUATORS, KINETIQ_CENTRE, KINETIQ_CENTRE_DOF,
                                         has_kinetiq_frame_marker)

CONVERT, KEEP, CANCEL = "convert", "keep", "cancel"
TITLE = "KINETIQ work zero"
HEAD_LINES = 200                       # header lines read (the work-zero line / the log's '# Positions:' line)
LOG_OFFSET_TEXT = "work-zero offset"   # in the '# Positions:' line of a log recorded with an offset

# centre subtracted per column: G-code motor columns and the DOF columns of a log
COLUMN_CENTRE = dict(KINETIQ_CENTRE)
COLUMN_CENTRE.update({"LAT": KINETIQ_CENTRE_DOF["LAT"], "SI": KINETIQ_CENTRE_DOF["SI"], "AP": KINETIQ_CENTRE_DOF["AP"]})


def question_text(kind="file"):
    c = KINETIQ_CENTRE_DOF
    if kind == "log":
        return (f"This KINETIQ log has no work-zero offset in its header, so it was probably recorded with 0 at home. "
                f"Convert it to the centred frame (LAT -{c['LAT']:g}, SI -{c['SI']:g}, AP and A-D -{c['AP']:g} mm)?")
    return (f"This KINETIQ file has no work-zero line, so it was probably written with 0 at home. "
            f"Convert it to the centred frame (LAT -{c['LAT']:g}, SI -{c['SI']:g}, A-D -{c['AP']:g} mm)?")


def ask_old_frame(parent, kind="file"):
    """[Convert] [Keep values] [Cancel] -> CONVERT / KEEP / CANCEL (Escape or closing the box: CANCEL).
    kind: 'file' (G-code) or 'log'."""
    from PySide6.QtWidgets import QMessageBox, QWidget
    box = QMessageBox(parent if isinstance(parent, QWidget) else None)
    box.setIcon(QMessageBox.Question)
    box.setWindowTitle(TITLE)
    box.setText(question_text(kind))
    b_convert = box.addButton("Convert", QMessageBox.YesRole)
    b_keep = box.addButton("Keep values", QMessageBox.NoRole)
    b_cancel = box.addButton(QMessageBox.Cancel)
    box.setDefaultButton(b_convert)
    box.setEscapeButton(b_cancel)
    box.exec()
    clicked = box.clickedButton()
    return CONVERT if clicked is b_convert else KEEP if clicked is b_keep else CANCEL


def to_centred(df):
    """A copy of df with the centre subtracted from every KINETIQ position column ('e 'f 50, 'a 'c 'b 25, A-D 45;
    LAT 50, SI 25, AP 45); time, Roll / Pitch / Yaw, X Y Z, velocities and the other columns are unchanged."""
    out = df.copy()
    for col in out.columns:
        c = COLUMN_CENTRE.get(col)
        if c:
            out[col] = out[col].astype(float) - c
    return out


def file_head(path, n=HEAD_LINES):
    """The first n lines of a text file ([] when it cannot be read)."""
    lines = []
    try:
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            for i, line in enumerate(f):
                if i >= n:
                    break
                lines.append(line)
    except OSError:
        pass
    return lines


def _answer(parent, df, kind):
    ans = ask_old_frame(parent, kind)
    if ans == CANCEL:
        return df, False
    return (to_centred(df) if ans == CONVERT else df), True


def check_gcode_import(parent, df, axis_cols, head_lines):
    """(df, go_on) for a Planning G-code import: a KINETIQ file (A B C D, the import's Motion Platform test) without
    the work-zero line -> question (Convert: df centred; Keep values: df; Cancel: go_on False).  Other files and
    files with the line: (df, True) without a question."""
    cols = set(axis_cols or ())
    if not all(a in cols for a in ACTUATORS) or has_kinetiq_frame_marker(head_lines):
        return df, True
    return _answer(parent, df, "file")


def log_names_work_zero(path):
    """True when the '#' header of a LogIQ log names the work-zero offset (it was recorded in the G-code frame of a
    work zero, work_zero.positions_header)."""
    for line in file_head(path):
        s = line.strip().lstrip('﻿').lstrip('"')
        if s.startswith('#') and LOG_OFFSET_TEXT in s.lower():
            return True
    return False


def check_log_import(parent, plan_df, path):
    """(plan_df, go_on) for the Planning import of a KINETIQ (Motion Platform) LogIQ log: a header without the
    work-zero offset text -> question (Convert / Keep values / Cancel, as check_gcode_import)."""
    if log_names_work_zero(path):
        return plan_df, True
    return _answer(parent, plan_df, "log")
