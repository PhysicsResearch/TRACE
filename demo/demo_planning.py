"""
LogIQ user-guide videos for the Planning tab (recorded by demo_kit: only the LogIQ window, pointer highlight, captions,
narration with the offline Windows voice).

    python demo_planning.py 1          video 1 for DYNAMIQ, the lung phantom (planning_1_dynamiq)
    python demo_planning.py 2          video 2: pauses and triggers
    python demo_planning.py 3          video 1 for KINETIQ, the motion platform (planning_1_kinetiq)
    python demo_planning.py 1 --dry    fast run without recording / narration (to check the steps)

Outputs (demo/output): planning_<n>.mp4 (with narration), planning_<n>_silent.mp4, planning_<n>.srt,
planning_<n>_narration.wav.  Nothing is sent to a Duet; configuration.json is restored afterwards.
"""
import os
import shutil
import sys
import tempfile
import time

sys.path.insert(0, r"C:\TRACE")
os.chdir(r"C:\TRACE")
from PySide6.QtCore import Qt, QPoint
from PySide6.QtWidgets import (QApplication, QDialog, QDialogButtonBox, QDoubleSpinBox, QFileDialog, QMenu,
                               QMessageBox, QPushButton)

import demo_kit as K

OUT = os.path.join(r"C:\TRACE\demo", "output")
VIDEO = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 1
DRY = "--dry" in sys.argv

# (caption, sub-caption, narration)
STEPS_1 = [
    ("Planning tab - making a motion plan", "LogIQ user guide, part 1 - DYNAMIQ",
     "In this video we build a smooth motion plan for DYNAMIQ, the lung phantom, in the Planning tab of LogIQ. It is a general illustration of "
     "how to use the tool: define the curves according to your own application."),
    ("Step 1 - Open the Planning tab", "",
     "Open the Planning tab, in the column on the left. The plot shows the plan, the controls are below it."),
    ("Step 2 - Choose the device", "DYNAMIQ: 3 axes, one for each lung and one for the surrogate",
     "First choose the device. One click switches between KINETIQ, the motion platform, and DYNAMIQ, the lung "
     "phantom. We use DYNAMIQ. It has three axes, X, Y and Z: one for each lung, and one for the surrogate."),
    ("Step 3 - Choose the function", "sin, cos, cos squared ... constant, linear",
     "Pick the shape of the motion. Here, a sine."),
    ("Step 4 - Amplitude and period", "type the values",
     "Type the amplitude, ten millimetres, and the period, four seconds."),
    ("Step 5 - Start and end time", "drag the slider or type in the boxes",
     "Set when the motion runs, here from two to eighteen seconds. Drag the slider handles, or type the times. "
     "Slider and boxes stay in sync."),
    ("Step 6 - Choose the axis and add the curve", "the part below zero is cut off",
     "Select the axis, X, and press Add Curve. Notice that only the upper half of the sine is there: "
     "the part below zero is cut off."),
    ("Step 7 - Negative values need an offset", "DYNAMIQ cannot move below zero",
     "DYNAMIQ cannot move to negative positions, so values below zero are not accepted. "
     "Undo the curve with the circular arrow, set an amplitude offset of ten millimetres, and add it again. "
     "Now the full sine runs from zero to twenty millimetres."),
    ("Step 8 - Avoid abrupt changes", "jumps can displace the device or move it on the build plate",
     "But look at the start and the end of the sine: the position jumps between zero and ten millimetres. "
     "Abrupt changes like these are undesired. They can displace the device, or make DYNAMIQ move on the "
     "build plate. So we undo the sine, and build the motion from segments that connect."),
    ("Step 9 - Segment 1: a linear ramp up", "linear: amplitude = start value, offset = end value, period = duration",
     "A linear segment goes from one value to another. The amplitude is its start value, the offset its end "
     "value, and the period its duration. This ramp goes from zero to ten millimetres in the first two seconds."),
    ("Step 10 - Segment 2: the sine", "it starts where the ramp ends: 10 mm at 2 s",
     "Then the sine, from two to eighteen seconds, with its ten millimetre offset. It starts at ten millimetres, "
     "exactly where the ramp ends."),
    ("Step 11 - Segment 3: a linear ramp down", "from 10 mm back to 0 mm",
     "And a ramp from ten millimetres back to zero after the sine. Pay attention to the gaps: each segment "
     "should start where the previous one ends. The final curve has no abrupt changes."),
    ("Step 12 - The limits in Settings", "they depend on the hardware",
     "The allowed range is set in the Settings tab: here the maximum X, Y and Z positions of DYNAMIQ. "
     "These limits depend on the hardware. Values below zero or above the maximum are not accepted, "
     "they are cut off in the plan."),
    ("Step 13 - A second axis", "cos squared with a 180 degree phase: starts and ends at 0",
     "A second axis: a cosine squared on Y with a starting phase of one hundred and eighty degrees. "
     "It starts and ends at zero, so it needs no ramps."),
    ("Step 14 - Insert instead of Replace", "Replace overwrites, Insert makes room",
     "Replace overwrites the selected time. Insert makes room instead: everything after the start time moves to "
     "the right, and during the inserted time every axis holds its position. We insert a three second hold on X "
     "at ten seconds, at ten millimetres, where X is at that moment, so the curve stays connected."),
    ("Step 15 - Total duration", "longer: every axis holds its position; shorter: crop",
     "The total duration sets the length of the plan. Longer adds time where every axis holds its position; "
     "shorter crops the plan."),
    ("Step 16 - What the plot shows", "velocity and the curve buttons on the right",
     "Below the plot you can also show velocity and acceleration. On the right, the coloured buttons show or hide "
     "each curve; a group title selects or clears the whole group."),
    ("Step 17 - Export the G-code", "to the hard drive, or upload it to the Duet directly",
     "Finally, the plan is turned into G-code. Export G-code saves it as a file on the hard drive, and Upload "
     "to Duet sends it to the Duet directly."),
    ("Done", "Part 2: pauses and triggers",
     "That is a complete, smooth motion plan. Part two shows pauses and triggers."),
]

STEPS_2 = [
    ("Planning tab - pauses and triggers", "LogIQ user guide, part 2",
     "In this video we add pauses and trigger windows to a motion plan in the Planning tab of LogIQ. It is a general illustration of how to "
     "use the tool: define the pauses and triggers according to your own application."),
    ("Step 1 - The pauses and trigger panel", "right of the curve settings",
     "The panel on the right adds pauses and trigger switches. Choose a kind, set the time, and press Add."),
    ("Step 2 - Wait for radiation", "at 5 s",
     "A wait for radiation at five seconds: the motion stops there until the detector sees the beam. "
     "It is shown as a dashed line."),
    ("Step 3 - Wait for the user", "at 12 s",
     "A wait for the user at twelve seconds: the motion waits until the user presses Release."),
    ("Step 4 - A trigger window", "Trigger On at 3 s, Trigger Off at 8 s",
     "Trigger On at three seconds and Trigger Off at eight seconds switch the five volt trigger output. "
     "The window is shaded green."),
    ("Step 5 - Repeat", "a periodic pattern, previewed in gray",
     "Repeat places a pattern: here the trigger is on for one second every four seconds, from twenty to forty "
     "seconds. The gray preview shows it before you press Add."),
    ("Step 6 - Right-click a pause", "move it to another time",
     "Right-click a dashed pause line to delete it or move it. We move the user pause to fifteen seconds."),
    ("Step 7 - Delete a pause", "",
     "Right-click again to delete a pause."),
    ("Step 8 - Right-click a trigger window", "adjust its start and end",
     "Right-click a green trigger window to adjust it. We let the first window end at ten seconds."),
    ("Step 9 - Delete a trigger window", "",
     "Or delete a window completely."),
    ("Step 10 - Clear one kind", "Clear removes every pause or switch of the selected kind",
     "Clear removes everything of the selected kind, here all waits for radiation. Undo brings it back."),
    ("Done", "", "That is how pauses and triggers are added and edited in the Planning tab."),
]

STEPS_3 = [
    ("Planning tab - KINETIQ", "LogIQ user guide, part 1 - KINETIQ",
     "In this video we build a motion plan for KINETIQ, the motion platform, in the Planning tab of LogIQ. It is a general "
     "illustration of how to use the tool: define the curves according to your own application."),
    ("Step 1 - Choose KINETIQ", "plan length: 30 s",
     "Open the Planning tab and switch the device to KINETIQ. We set the total duration of the plan "
     "to thirty seconds."),
    ("Step 2 - The KINETIQ position", "LAT, SI, AP, Roll, Pitch: set by the user",
     "The KINETIQ position is what you define: the translations LAT, SI and AP, and the rotations Roll, Pitch "
     "and Yaw. These are the axes you select for a curve."),
    ("Step 3 - Yaw", "not available yet: it depends on the KINETIQ version",
     "Yaw is currently not available. It will be included depending on the version of KINETIQ."),
    ("Step 4 - The individual axes", "A, B, C, D, 'a, 'c, 'e, 'f: computed in the background",
     "A, B, C and D, and the primed axes a, c, e and f, are the individual axes of KINETIQ. They are usually "
     "not set up manually: LogIQ computes them in the background from the KINETIQ position. The buttons on the "
     "right show them in the plot."),
    ("Step 5 - The rotation centre", "the reference point for Roll and Pitch",
     "The rotation centre is the point KINETIQ turns about for Roll and Pitch. We keep it at zero."),
    ("Step 6 - A Roll at the zero position", "Roll: sine, 3 degrees, period 4 s, 2 to 18 s",
     "Let us try a Roll with KINETIQ at its zero position: a sine of three degrees, with a period of four "
     "seconds, from two to eighteen seconds. We show only Roll and the individual axes A and B."),
    ("Step 7 - Roll cannot be done at zero", "one side goes down, the other goes up",
     "A roll lifts one side of KINETIQ and lowers the other. At the zero position the lower side cannot go "
     "below zero, so it is cut off: only half of the roll is reached, and KINETIQ is pushed up. Roll must be "
     "defined around a central position that keeps every individual axis above zero. So we undo the roll."),
    ("Step 8 - A central position with AP", "linear: amplitude = start value, offset = end value, period = duration",
     "First we raise KINETIQ with AP. As for DYNAMIQ, avoid abrupt changes and build the motion from "
     "segments that connect. A linear segment goes from its amplitude, the start value, to its offset, the end "
     "value, over its period: here from zero to fifteen millimetres in the first three seconds."),
    ("Step 9 - Hold, then ramp down", "constant 15 mm from 3 to 27 s, then 15 mm back to 0",
     "Then a constant fifteen millimetres from three to twenty-seven seconds, and a ramp back to zero from "
     "twenty-seven to thirty seconds. Each segment starts where the previous one ends."),
    ("Step 10 - Roll around the central position", "every individual axis stays above zero",
     "Now the same roll, from five to twenty-five seconds, while KINETIQ is held at fifteen millimetres. "
     "The full three degrees are reached, and A, B, C and D stay above zero. A whole number of periods starts and "
     "ends at zero, so the roll connects smoothly."),
    ("Step 11 - A curve on SI", "cos squared with a 180 degree phase: starts and ends at 0",
     "We add a motion on SI as well: a cosine squared of ten millimetres, with a period of six seconds and a "
     "starting phase of one hundred and eighty degrees, from six to twenty-four seconds. SI cannot go below zero "
     "either; this curve stays between zero and ten millimetres, and starts and ends at zero. The individual axes "
     "a and c follow it in the background."),
    ("Step 12 - The limits in Settings", "they depend on the hardware",
     "The Settings tab holds the KINETIQ limits: the maximum LAT, SI and AP positions, and the maximum Roll, "
     "Pitch and Yaw angles. These limits depend on the hardware. Values outside them are not accepted."),
    ("Step 13 - What the plot shows", "the buttons on the right show or hide each curve",
     "On the right, the buttons show or hide each curve; a group title, like Individual axes, selects or clears "
     "the whole group."),
    ("Step 14 - Export the G-code", "to the hard drive, or upload it to the Duet directly",
     "Finally, the plan is turned into G-code, which drives the individual axes. Export G-code saves it as a file "
     "on the hard drive, and Upload to Duet sends it to the Duet directly."),
    ("Done", "Part 2: pauses and triggers",
     "That is a smooth motion plan for KINETIQ. Part two shows pauses and triggers."),
]


# ------------------------------------------------------------------------------------------------------------------
def build_window():
    import Launch_ImGUI as L
    from fcn_create_gui.window_fit import fit_tabs_to_current_page
    from fcn_create_gui.top_bar_style import style_top_bar
    from fcn_create_gui.console_theme import add_console_theme_button
    from fcn_create_gui.logiq_theme import prepare_logiq_theme, apply_logiq_theme
    prepare_logiq_theme()
    w = L.MyApp(None)
    QApplication.instance().setStyle('Fusion')
    fit_tabs_to_current_page(w)
    style_top_bar(w)
    add_console_theme_button(w)
    apply_logiq_theme(w)
    from fcn_create_gui.logiq_shell import apply_logiq_shell
    apply_logiq_shell(w)              # connection bar on top, tabs as icons on the left
    return w


def canvas_point(w, t, frac=0.5):
    """Widget point of the planning canvas at plot time t (frac: height in the axes, 0 bottom .. 1 top)."""
    canvas, ax = w.create_plot_canvas, w.create_plot_ax
    xpx, _ = ax.transData.transform((t, 0.0))
    bb = ax.get_window_extent()
    ypx = bb.y0 + frac * bb.height
    dpr = float(getattr(canvas, 'device_pixel_ratio', 1.0)) or 1.0
    return QPoint(int(round(xpx / dpr)), int(round(canvas.height() - ypx / dpr)))


class Demo:
    def __init__(self, w, d, ov):
        self.w, self.d, self.ov = w, d, ov

    @property
    def p(self):
        return self.w.planning_modern

    @property
    def cc(self):
        return self.p.curve_controls

    # ---- helpers (generators)
    def open_planning(self):
        nav = getattr(self.w, 'nav_buttons', None)       # LogIQ layout: the tabs are the icons on the left
        if nav:
            yield from self.d.click(nav[3])
        else:
            bar = self.w.tabModules.tabBar()
            yield from self.d.click(bar, bar.tabRect(3).center())
        yield 900

    def type_value(self, spin, value):
        """Types the value as one entry (char-by-char lets the app reformat the box between keys), then checks
        that the box holds it and sets it directly if not."""
        from PySide6.QtTest import QTest
        yield from self.d.click(spin, pause_ms=200)
        spin.setFocus()
        QTest.keyClick(spin, Qt.Key_A, Qt.ControlModifier)
        yield 250
        QTest.keyClicks(spin, f"{value:g}".replace('.', ','))
        yield 350
        QTest.keyClick(spin, Qt.Key_Return)
        yield 300
        try:
            if abs(float(spin.value()) - float(value)) > 1e-6:
                print(f"  (typed {value} into {spin.objectName() or type(spin).__name__}: got {spin.value()}; set "
                      f"directly)", flush=True)
                spin.setValue(float(value))
                spin.editingFinished.emit()
                yield 300
        except Exception:
            pass

    def set_axis(self, axis):
        for a, b in self.p.axis_pills.items():
            if b.isChecked() and a != axis:
                yield from self.d.click(b, ms=450, pause_ms=150)
        b = self.p.axis_pills[axis]
        if not b.isChecked():
            yield from self.d.click(b)

    def set_function(self, key):
        for b in self.cc.func_buttons:
            if b.property('func_key') == key:
                yield from self.d.click(b)
                return

    def drag_handle(self, which, t_target):
        s = self.cc.slider
        a = QPoint(*s.handle_pos(which))
        b = QPoint(int(round(s.x_of(t_target))), a.y())
        yield from self.d.drag(s, a, b, ms=1100)

    def answer_modal(self, prefer=("OK", "&OK", "Yes", "&Yes"), timeout_ms=4000):
        yield from self.d.wait_popup(timeout_ms)
        dlg = self.d.popup
        if dlg is None:
            return
        btn = None
        for b in dlg.findChildren(QPushButton):
            if b.isVisible() and b.text().replace('&', '') in [x.replace('&', '') for x in prefer]:
                btn = b
                break
        if btn is None:
            dlg.accept() if isinstance(dlg, QDialog) else dlg.close()
            yield 300
            return
        yield from self.d.click(btn, pause_ms=500)

    def right_click_plot(self, t, frac=0.5):
        canvas = self.w.create_plot_canvas
        yield from self.d.click(canvas, canvas_point(self.w, t, frac), right=True, outline=False, pause_ms=400)

    def pick_menu(self, text_part):
        yield from self.d.wait_popup(3000)
        menu = self.d.popup
        if os.environ.get("DEMO_DEBUG"):
            print("pick_menu", text_part, "->", type(menu).__name__ if menu is not None else None,
                  [a.text() for a in menu.actions()] if isinstance(menu, QMenu) else "", flush=True)
        if isinstance(menu, QMenu):
            yield 700
            yield from self.d.choose_menu_item(menu, text_part)

    def fill_dialog(self, values):
        """In the open dialog: type values into its spin boxes in order (None = keep), then OK."""
        yield from self.d.wait_popup(3000)
        dlg = self.d.popup
        if dlg is None:
            return
        yield 500
        spins = [s for s in dlg.findChildren(QDoubleSpinBox) if s.isVisible()]
        spins.sort(key=lambda s: (s.mapToGlobal(QPoint(0, 0)).y(), s.mapToGlobal(QPoint(0, 0)).x()))
        for s, v in zip(spins, values):
            if v is not None:
                yield from self.d.type_into(s, f"{v:g}".replace('.', ','), per_char_ms=110)
        bb = dlg.findChild(QDialogButtonBox)
        ok = bb.button(QDialogButtonBox.Ok) if bb is not None else None
        if ok is not None:
            yield from self.d.click(ok, pause_ms=400)
        else:
            dlg.accept()
            yield 300

    def event_add(self, key, t):
        yield from self.d.click(self.p.event_buttons[key])
        yield from self.type_value(self.w.input_wait_rad_time, t)
        yield from self.d.click(self.p.btn_event_add, pause_ms=450)
        yield 700

    # ---- video 1
    def sub_tab(self, name):
        tw = self.w.create_settings_tab_widget
        bar = tw.tabBar()
        i = next(k for k in range(tw.count()) if tw.tabText(k) == name)
        yield from self.d.click(bar, bar.tabRect(i).center())
        yield 700

    def point_plot(self, t, value, ms=900, hold=1200):
        """Moves the pointer to (t, value) in the plot."""
        w = self.w
        ax = w.create_plot_ax
        y0, y1 = ax.get_ylim()
        frac = 0.5 if y1 == y0 else (value - y0) / (y1 - y0)
        yield from self.d.move_to(w.create_plot_canvas.mapToGlobal(canvas_point(w, t, frac)), ms)
        yield hold

    def segment(self, func, amp, off, period, start=None, end=None, phase=None):
        """Function, values and times of one segment (start / end typed; a linear's end follows its period)."""
        w = self.w
        yield from self.set_function(func)
        yield from self.type_value(w.input_amplitude, amp)
        if off is not None:                               # rotations: the offset box is disabled
            yield from self.type_value(w.input_amp_offset, off)
        yield from self.type_value(w.input_period, period)
        if phase is not None:
            yield from self.type_value(w.input_phase, phase)
        if start is not None:
            yield from self.type_value(w.input_start_time, start)
        if end is not None and func != 'linear':
            yield from self.type_value(w.input_end_time, end)

    def video1(self):
        S, d, w, p = STEPS_1, self.d, self.w, None
        yield from d.step(*S[0])
        self.ov.caption = ""
        self.ov.big_text, self.ov.big_sub = "Planning tab", "Part 1 - DYNAMIQ"
        yield 2500
        self.ov.big_text = ""
        yield from d.step(*S[1])
        yield from self.open_planning()
        p = self.p
        yield from d.step(*S[2])
        yield from d.click(p.device_buttons[1])          # Motion Platform
        yield 1400
        yield from d.click(p.device_buttons[0])          # Lung Phantom
        yield 900
        yield from d.step(*S[3])
        yield from self.set_function('sin')
        yield from d.step(*S[4])
        yield from self.type_value(w.input_amplitude, 10)
        yield from self.type_value(w.input_period, 4)
        yield from d.step(*S[5])
        yield from self.drag_handle('lo', 2.0)
        yield from self.drag_handle('hi', 18.0)
        yield 400
        yield from self.type_value(w.input_start_time, 2)
        yield from self.type_value(w.input_end_time, 18)
        yield from d.step(*S[6])
        yield from self.set_axis('X')
        yield from d.click(w.button_create_curve, pause_ms=500)
        yield 1300
        yield from self.point_plot(5.0, 0.3)             # the cut-off half
        yield from d.step(*S[7])
        yield from d.click(p.btn_undo, pause_ms=500)
        yield 1000
        yield from self.type_value(w.input_amp_offset, 10)
        yield from d.click(w.button_create_curve, pause_ms=500)
        yield 1500
        yield from d.step(*S[8])
        yield from self.point_plot(2.1, 5.0, hold=1500)   # jump at the start
        yield from self.point_plot(18.1, 5.0, hold=1800)  # drop at the end
        yield from d.click(p.btn_undo, pause_ms=500)
        yield 1200
        yield from d.step(*S[9])
        yield from self.segment('linear', 0, 10, 2, start=0)
        yield from d.click(w.button_create_curve, pause_ms=500)
        yield 1500
        yield from d.step(*S[10])
        yield from self.segment('sin', 10, 10, 4, start=2, end=18)
        yield from d.click(w.button_create_curve, pause_ms=500)
        yield 1500
        yield from self.point_plot(2.0, 10.0, hold=1000)  # the joint
        yield from d.step(*S[11])
        yield from self.segment('linear', 10, 0, 2, start=18)
        yield from d.click(w.button_create_curve, pause_ms=500)
        yield 1500
        yield from self.point_plot(18.0, 10.0, hold=900)
        yield from self.point_plot(20.0, 0.0, hold=1200)
        yield from d.step(*S[12])
        yield from self.sub_tab("Settings")
        for attr in ('settings_max_lim_x', 'settings_max_lim_y', 'settings_max_lim_z'):
            box = getattr(w, attr, None)
            if box is not None and box.isVisible():
                yield from d.point_at(box, ms=700)
                yield 900
        yield 600
        yield from self.sub_tab("Curve")
        yield from d.step(*S[13])
        yield from self.set_axis('Y')
        yield from self.segment('cos^2', 8, 0, 4, phase=180, start=4, end=24)
        yield from d.click(w.button_create_curve, pause_ms=500)
        yield 1500
        yield from self.type_value(w.input_phase, 0)
        yield from d.step(*S[14])
        ir = p.insert_replace
        yield from d.click(ir.buttons['insert'])
        yield from self.set_axis('X')
        yield from self.segment('constant', 10, 0, 4, start=10, end=13)
        yield from d.click(w.button_create_curve, pause_ms=500)
        yield 1800
        yield from d.click(ir.buttons['replace'])
        yield from d.step(*S[15])
        yield from self.type_value(self.cc.total_spin, 80)
        yield 1500
        yield from self.type_value(self.cc.total_spin, 60)
        yield from self.answer_modal(timeout_ms=1500)
        yield 1000
        yield from d.step(*S[16])
        vel = p.kin_pills.get('check_show_vel')
        if vel is not None:
            yield from d.click(vel)
            yield 1500
            yield from d.click(vel)
        if 'Y' in p.pills:
            yield from d.click(p.pills['Y'])
            yield 1200
            yield from d.click(p.pills['Y'])
        sec = p.sections.get('phantom')
        if sec is not None:
            yield from d.click(sec[0])
            yield 1200
            yield from d.click(sec[0])
        yield 600
        yield from d.step(*S[17])
        yield from d.point_at(p.btn_export, ms=800)       # shown, not clicked
        yield 1800
        up = getattr(p, 'btn_upload', None)
        if up is not None:
            yield from d.point_at(up, ms=700)
            yield 1800
        yield from d.step(*S[18])
        self.ov.caption = ""
        self.ov.big_text, self.ov.big_sub = "Done", "Part 2: pauses and triggers"
        yield 600

    # ---- video 3: part 1 for the Motion Platform
    def show_only(self, keys):
        """Display pills: clear the Motion Platform group with its title, then turn on the given curves."""
        p, d = self.p, self.d
        title = p.sections['platform'][0]
        for _k in range(2):
            if not any(b.isChecked() for b in p.pills.values() if b.isVisible()):
                break
            yield from d.click(title, ms=600, pause_ms=300)
            yield 500
        for k in keys:
            yield from self.show_pill(k)

    def show_pill(self, key, on=True):
        b = self.p.pills.get(key)
        if b is not None and b.isChecked() != on:
            yield from self.d.click(b, ms=450, pause_ms=200)
            yield 300

    def video3(self):
        S, d, w, p = STEPS_3, self.d, self.w, None
        yield from d.step(*S[0])
        self.ov.caption = ""
        self.ov.big_text, self.ov.big_sub = "Planning tab", "Part 1 - KINETIQ"
        yield 2500
        self.ov.big_text = ""
        yield from d.step(*S[1])
        yield from self.open_planning()
        p = self.p
        yield from d.click(p.device_buttons[1])          # Motion Platform
        yield 1200
        yield from self.type_value(self.cc.total_spin, 30)
        yield from self.answer_modal(timeout_ms=1500)
        yield 800
        yield from d.step(*S[2])
        for k in ('LAT', 'SI', 'AP', 'Roll', 'Pitch'):
            yield from d.point_at(p.axis_pills[k], ms=450)
            yield 350
        yield from d.point_at(p.sections['position'][0], ms=700)
        yield 900
        yield from d.step(*S[3])
        yield from d.point_at(p.axis_pills['Yaw'], ms=700)
        yield 1800
        yield from d.step(*S[4])
        yield from d.point_at(p.sections['individual'][0], ms=800)
        yield 900
        for k in ('A', 'B', 'C', 'D', "'a", "'c", "'e", "'f"):
            if k in p.pills:
                yield from d.point_at(p.pills[k], ms=350)
                yield 250
        yield from d.step(*S[5])
        rc = getattr(p, 'rot_card', None)
        if rc is not None and rc.isVisible():
            yield from d.point_at(rc, ms=800)
            yield 1500
        yield from d.step(*S[6])
        yield from self.set_axis('Roll')
        yield from self.segment('sin', 3, None, 4, start=2, end=18)
        yield from d.click(w.button_create_curve, pause_ms=500)
        yield 1000
        yield from self.show_only(['Roll', 'A', 'B'])
        yield 800
        yield from d.step(*S[7])
        yield from self.point_plot(5.0, 0.3, hold=1800)   # the cut-off side at 0
        yield from self.point_plot(3.0, 1.5, hold=1500)   # only half of the roll
        yield from self.point_plot(3.0, 7.8, hold=1500)   # the other side pushed up
        yield from d.until_left(3.0)                      # undo on "So we undo the roll"
        yield from d.click(p.btn_undo, pause_ms=500)
        yield 1200
        yield from d.step(*S[8])
        yield from self.show_only(['AP', 'Roll', 'A', 'B', 'C', 'D'])
        yield from self.set_axis('AP')
        yield from self.segment('linear', 0, 15, 3, start=0)
        yield from d.click(w.button_create_curve, pause_ms=500)
        yield 1500
        yield from d.step(*S[9])
        yield from self.segment('constant', 15, 0, 4, start=3, end=27)
        yield from d.click(w.button_create_curve, pause_ms=500)
        yield 1200
        yield from self.segment('linear', 15, 0, 3, start=27)
        yield from d.click(w.button_create_curve, pause_ms=500)
        yield 1500
        yield from self.point_plot(3.0, 15.0, hold=900)
        yield from self.point_plot(27.0, 15.0, hold=1000)
        yield from d.step(*S[10])
        yield from self.set_axis('Roll')
        yield from self.segment('sin', 3, None, 4, start=5, end=25)
        yield from d.click(w.button_create_curve, pause_ms=500)
        yield 1500
        yield from self.point_plot(12.0, 7.5, hold=1500)  # lowest individual axis, above 0
        yield from self.point_plot(5.0, 15.0, hold=1000)  # the roll starts at the central position
        yield from d.step(*S[11])
        yield from self.set_axis('SI')
        yield from self.segment('cos^2', 10, 0, 6, phase=180, start=6, end=24)
        yield from d.click(w.button_create_curve, pause_ms=500)
        yield 1200
        yield from self.type_value(w.input_phase, 0)
        for k in ('SI', "'a", "'c"):
            yield from self.show_pill(k)
        yield 900
        yield from d.step(*S[12])
        yield from self.sub_tab("Settings")
        for attr in ('settings_max_lim_lat', 'settings_max_lim_si', 'settings_max_lim_ap', 'settings_max_lim_roll',
                     'settings_max_lim_pitch', 'settings_max_lim_yaw'):
            box = getattr(w, attr, None)
            if box is not None and box.isVisible():
                yield from d.point_at(box, ms=600)
                yield 600
        yield 500
        yield from self.sub_tab("Curve")
        yield from d.step(*S[13])
        ind = p.sections['individual'][0]
        yield from d.click(ind)
        yield 1500
        yield from d.click(ind)
        yield 1500
        if 'Roll' in p.pills:
            yield from d.click(p.pills['Roll'])
            yield 1200
            yield from d.click(p.pills['Roll'])
        yield 600
        yield from d.step(*S[14])
        yield from d.point_at(p.btn_export, ms=800)       # shown, not clicked
        yield 1800
        up = getattr(p, 'btn_upload', None)
        if up is not None:
            yield from d.point_at(up, ms=700)
            yield 1800
        yield from d.step(*S[15])
        self.ov.caption = ""
        self.ov.big_text, self.ov.big_sub = "Done", "Part 2: pauses and triggers"
        yield 600

    # ---- video 2
    def prepare2(self):
        """Before recording: the Planning tab with one smooth curve (X cos^2, phase 180 deg: 0 at 0 and 32 s)."""
        w = self.w
        w.tabModules.setCurrentIndex(3)
        QApplication.processEvents()
        p = self.p
        p.device_buttons[0].click()
        for a, b in p.axis_pills.items():
            if b.isChecked() != (a == 'X'):
                b.click()
        w.combo_func_type.setCurrentText('cos^2')
        w.input_amplitude.setValue(10.0)
        w.input_amp_offset.setValue(0.0)
        w.input_period.setValue(4.0)
        w.input_phase.setValue(180.0)
        w.input_start_time.setValue(0.0)
        w.input_end_time.setValue(32.0)
        w.button_create_curve.click()
        w.input_phase.setValue(0.0)
        w._curve_undo_stack = []
        QApplication.processEvents()

    def video2(self):
        S, d, w, p = STEPS_2, self.d, self.w, self.p
        yield from d.step(*S[0])
        self.ov.caption = ""
        self.ov.big_text, self.ov.big_sub = "Planning tab", "Part 2 - pauses and triggers"
        yield 2500
        self.ov.big_text = ""
        yield from d.step(*S[1])
        yield from d.point_at(p.event_card, ms=800)
        yield 800
        yield from d.step(*S[2])
        yield from self.event_add('rad', 5)
        yield from d.step(*S[3])
        yield from self.event_add('usr', 12)
        yield from d.step(*S[4])
        yield from self.event_add('on', 3)
        yield from self.event_add('off', 8)
        yield from d.step(*S[5])
        yield from d.click(p.mode_buttons['repeat'])
        yield from d.click(p.event_buttons['on'])
        rng = w.trg_per_range
        yield from self.type_value(w.trg_per_period, 4)
        yield from self.type_value(w.trg_per_duration, 1)
        yield from self.type_value(w.trg_per_offset, 0)
        yield from d.click(p.range_buttons['subset'])
        yield from self.type_value(rng['r0'], 20)
        yield from self.type_value(rng['r1'], 40)
        yield 1800                                       # the gray preview
        yield from d.click(p.btn_event_add, pause_ms=500)
        yield 1500
        yield from d.click(p.mode_buttons['once'])
        yield from d.step(*S[6])
        yield from self.right_click_plot(12.0, 0.75)
        yield from self.pick_menu("Adjust time")
        yield from self.fill_dialog([15])
        yield 1200
        yield from d.step(*S[7])
        yield from self.right_click_plot(5.0, 0.75)
        yield from self.pick_menu("Delete pause")
        yield 1200
        yield from d.step(*S[8])
        yield from self.right_click_plot(5.5, 0.3)
        yield from self.pick_menu("Adjust window")
        yield from self.fill_dialog([None, 10])
        yield 1200
        yield from d.step(*S[9])
        yield from self.right_click_plot(24.5, 0.3)
        yield from self.pick_menu("Delete window")
        yield 1200
        yield from d.step(*S[10])
        yield from self.event_add('rad', 25)
        yield from d.click(p.event_buttons['rad'])
        yield from d.click(p.btn_event_clear, pause_ms=500)
        yield from self.answer_modal(prefer=("Yes", "&Yes", "OK"), timeout_ms=1500)
        yield 1200
        yield from d.click(p.btn_undo, pause_ms=500)
        yield 1200
        yield from d.step(*S[11])
        self.ov.caption = ""
        self.ov.big_text, self.ov.big_sub = "Done", "LogIQ user guide - Planning tab"
        yield 600


def main():
    os.makedirs(OUT, exist_ok=True)
    cfg = os.path.join(r"C:\TRACE", "configuration.json")
    cfg_bak = os.path.join(tempfile.gettempdir(), "trace_demo_configuration.json")
    if os.path.isfile(cfg):
        shutil.copy2(cfg, cfg_bak)
    steps = {1: STEPS_1, 2: STEPS_2, 3: STEPS_3}[VIDEO]
    tag = {1: "planning_1_dynamiq", 2: "planning_2", 3: "planning_1_kinetiq"}[VIDEO]
    if DRY:
        clips, durs = [], [0.3] * len(steps)
    else:
        clips = K.tts_clips([n for _c, _s, n in steps], os.path.join(OUT, f"{tag}_clips"), rate=-1, speed=0.95)
        durs = [dd for _p, dd in clips]

    export_path = os.path.join(OUT, f"{tag}_export.gcode")
    QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: (export_path, "G-code Files (*.gcode)"))

    app = QApplication.instance() or QApplication(sys.argv)
    # menus / combo popups without fade or slide animation: an animating (layered) popup is recorded as a black box
    for eff in (Qt.UI_AnimateMenu, Qt.UI_FadeMenu, Qt.UI_AnimateCombo, Qt.UI_AnimateTooltip, Qt.UI_FadeTooltip):
        QApplication.setEffectEnabled(eff, False)
    w = build_window()
    w.showMaximized()
    ov = K.Overlay()
    ov.show()
    d = K.PacedDirector(ov, durs, speed=float(os.environ.get("DEMO_SPEED", 6.0 if DRY else 1.0)))
    demo = Demo(w, d, ov)
    rec = K.Recorder(os.path.join(OUT, f"{tag}_silent.mp4"), None)

    def run():
        yield 1500
        if VIDEO == 2:
            demo.prepare2()
            yield 1200
        if not DRY:
            # the recorder captures a screen area: never start while another program covers the app
            front = False
            for _k in range(30):
                K.bring_to_front(w, ov)
                yield 500
                if K.window_on_screen(w):
                    front = True
                    break
            if not front:
                print("ABORTED: the LogIQ window is covered by another program - nothing recorded", flush=True)
                return
            print("LogIQ window is in front - recording", flush=True)
            rec.rect = K.physical_rect(w)
            rec.start()
            yield 1200
        d.start_clock()
        if not DRY:
            d.t0 = rec.t_start
        yield from {1: demo.video1, 2: demo.video2, 3: demo.video3}[VIDEO]()
        yield from d.finish()
        ov.caption = ""
        yield 1500
        ov.big_text = ""

    def finish():
        total = time.perf_counter() - (rec.t_start or d.t0 or time.perf_counter())
        if not DRY and rec.t_start is not None:
            err = rec.stop()
            starts = [t for t, _c, _n in d.steps]
            d.write_srt(os.path.join(OUT, f"{tag}.srt"), total)
            K.assemble_narration(clips, starts, os.path.join(OUT, f"{tag}_narration.wav"), total)
            rc, merr = K.mux_audio(os.path.join(OUT, f"{tag}_silent.mp4"), os.path.join(OUT, f"{tag}_narration.wav"),
                                   os.path.join(OUT, f"{tag}.mp4"))
            print("recorder:", (err or "").strip() or "ok", "| mux:", rc, (merr or "").strip()[:300], flush=True)
            bl = K.black_segments(os.path.join(OUT, f"{tag}_silent.mp4"))
            print("black stretches:", bl if bl else "none", flush=True)
        from fcn_plan.fcn_trigger import trg_windows
        df = w.dfEdit
        if df is not None:
            t = df['time'].to_numpy(float)
            cmds = list(df['Command']) if 'Command' in df.columns else []
            waits = [(round(float(t[i]), 2), c) for i, c in enumerate(cmds) if c and 'M42' not in c]
            print("final plan: end", round(float(t[-1]), 2), "| windows", trg_windows(t, cmds) if cmds else [],
                  "| commands", waits[:12], flush=True)
        if df is not None:
            import numpy as np
            for col in [c for c in ('X', 'Y', 'Z', 'SI', 'LAT', 'AP', 'Roll', 'A', 'B', 'C', 'D', "'a", "'c")
                        if c in df.columns]:
                v = df[col].to_numpy(float)
                nz = np.nonzero(np.abs(v) > 1e-6)[0]
                print(f"  {col}: min {v.min():.2f} max {v.max():.2f} moving {t[nz[0]]:.2f}-{t[nz[-1]]:.2f} s"
                      if len(nz) else f"  {col}: all 0", flush=True)
                if len(v) > 1:
                    dv = np.abs(np.diff(v))
                    k = int(np.argmax(dv))
                    print(f"     largest step between rows: {dv[k]:.3f} mm at {t[k]:.2f} s", flush=True)
        print("export file:", os.path.isfile(export_path), "| undo stack", len(getattr(w, '_curve_undo_stack', [])),
              "| insert:", getattr(getattr(w.planning_modern, 'insert_replace', None), 'last_insert', None), flush=True)
        print("steps:", [(round(tt, 1), c) for tt, c, _n in d.steps], "| total", round(total, 1), flush=True)
        ov.close()
        w.close()
        if os.path.isfile(cfg_bak):
            shutil.copy2(cfg_bak, cfg)
        app.quit()

    d.run(run(), on_finish=finish)
    app.exec()


if __name__ == "__main__":
    main()
