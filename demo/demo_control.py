"""
LogIQ user-guide video: the Control tab with KINETIQ connected (real platform: it connects, homes and moves).

    python demo/demo_control.py            record  -> demo/output/control_kinetiq.mp4 (+ _silent, .srt, _narration)
    python demo/demo_control.py --check    no narration / recording: runs the steps fast (the platform still moves)

Environment: DEMO_IP (default 172.18.38.129), TRACE_DEMO_FFMPEG (recorder).  The platform must be switched on and
NOT homed (power-cycled), with the base plate disconnected.  configuration.json is restored afterwards.
"""
import os
import shutil
import sys
import tempfile
import time

sys.path.insert(0, r"C:\TRACE")
sys.path.insert(0, r"C:\TRACE\demo")
os.chdir(r"C:\TRACE")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QPushButton

import demo_kit as K

OUT = os.path.join(r"C:\TRACE\demo", "output")
TAG = "control_kinetiq"
IP = os.environ.get("DEMO_IP", "172.18.38.129")
CHECK = "--check" in sys.argv

# (caption, sub-caption, narration)
STEPS = [
    ("Control tab - KINETIQ", "LogIQ user guide - manual control",
     "This video shows the Control tab of LogIQ, with KINETIQ, the motion platform, connected. The Control tab is "
     "for manual adjustments and single moves. In normal use the motion is automated: you plan it in the Planning "
     "tab and run it as G-code. Other videos show how."),
    ("Step 1 - The address of the device", "DYNAMIQ and KINETIQ fill in a preset address",
     "At the top, clicking DYNAMIQ or KINETIQ fills in a predefined IP address and connects. The address depends on "
     "your network, so you can also type it yourself. Here we type the address of the platform."),
    ("Step 2 - Red: not homed", "an axis must be homed before it can move",
     "Before connecting, look at the motion buttons of KINETIQ: they are red. Red means the axis is not homed, and "
     "LogIQ will not move it."),
    ("Step 3 - Connect", "the button with the link icon",
     "Now press the connect button, the one with the link icon. LogIQ connects, reads the name of the controller and "
     "recognises the platform: the KINETIQ button is filled, and the status shows connected."),
    ("Step 4 - Home all", "first setup: base plate disconnected",
     "The platform is not homed yet, so the axes are still red. Press Home ALL. During the first setup, the base "
     "plate should be disconnected when you home. After the first setup, the plate can stay connected, and you can "
     "press Home ALL with the plate in place."),
    ("Step 5 - Homing: 8 switches", "A, B, C, D, then LAT, then SI",
     "While it homes: each of the eight motors moves to its own switch. First the four vertical axes, A, B, C and D, "
     "then the two lateral axes, then the two superior inferior axes. When the switches are found, homing was "
     "successful, and the buttons turn green."),
    ("Step 6 - Homed stays homed", "home again only after switching the platform off and on",
     "The platform is homed. If LogIQ disconnects and connects again, there is no need to home again. You only home "
     "again after the platform was switched off and on."),
    ("Step 7 - Send a command", "the console shows the reply",
     "You can also send a single command to the controller. Type M one one five and press Send. The reply, with the "
     "firmware name and version, appears in the console."),
    ("Step 8 - Light or dark console", "the sun and moon button",
     "The sun and moon button switches the console between light and dark mode."),
    ("Step 9 - Step size", "how far one click moves",
     "Back to the motion. The step buttons on the right set how far one click moves: from a tenth of a millimetre "
     "up to ten millimetres, or degrees for Roll and Pitch."),
    ("Step 10 - Incremental moves", "minus and plus per direction",
     "Each minus or plus button moves the platform one step in that direction. Here AP goes up by one millimetre, and "
     "with a step of five, by five more. The current position follows the platform."),
    ("Step 11 - Limits", "defined in the configuration, never exceeded",
     "The limits of every axis are defined in the configuration, and LogIQ checks every move against them. LAT is at "
     "its maximum after homing, so one more step is refused, with a message. A limit can only be exceeded after an "
     "improper homing."),
    ("Step 12 - Go to center", "Roll and Pitch at zero, mid range",
     "Go to center moves the platform to its central position, with Roll and Pitch at zero."),
    ("Step 13 - KINETIQ dimensions", "depend on the build plate",
     "The KINETIQ dimensions, LAT and SI, depend on the build plate, and LogIQ uses them to calculate the angles. "
     "They are provided with your hardware. Changing them changes every Roll and Pitch."),
    ("Step 14 - Offset of the rotation point", "rotate about another point",
     "The rotation offset sets the point the platform rotates about, relative to other positions, in AP, LAT and SI. "
     "For a rotation that is not about the isocentre, the platform then corrects the lateral shift by itself. "
     "Separate videos explain this in more detail."),
    ("Done", "LogIQ user guide - Control tab",
     "That is the Control tab: connect, home, move step by step, and send commands. For automated motion, use the "
     "Planning tab."),
]


class Demo:
    def __init__(self, w, d):
        self.w, self.d = w, d

    def type_text(self, widget, text, per_char_ms=110):
        """Click, select all, type (no Return)."""
        yield from self.d.click(widget, pause_ms=200)
        widget.setFocus()
        QTest.keyClick(widget, Qt.Key_A, Qt.ControlModifier)
        yield 150
        for ch in text:
            QTest.keyClicks(widget, ch)
            yield per_char_ms
        yield 300

    def wait_for(self, cond, timeout_s, poll_ms=250):
        t_end = time.perf_counter() + timeout_s
        while time.perf_counter() < t_end:
            try:
                if cond():
                    return True
            except Exception:
                pass
            yield poll_ms
        return False

    def homed(self):
        from fcn_control.fcn_control import is_axis_homed
        return all(is_axis_homed(self.w, k) for k in ("LAT", "SI", "AP"))

    def jog_buttons(self):
        return [getattr(self.w, f"{p}{a}") for a in ("LATAXIS", "SIAXIS", "APAXIS", "ROLL", "PITCH")
                for p in ("MIN_", "PLUS_")]

    def close_message(self):
        """Clicks OK on the message box that just opened."""
        yield from self.d.wait_popup(4000)
        box = self.d.popup
        if box is None:
            print("  (no message box appeared)", flush=True)
            return
        yield 2600                                          # let it be read
        btns = [b for b in box.findChildren(QPushButton) if b.isVisible()]
        if btns:
            yield from self.d.click(btns[0], pause_ms=250)
        else:
            box.close()
        yield 600

    def run(self):
        w, d = self.w, self.d
        self.ok = False
        # 0 - intro (Control tab, KINETIQ sub-tab shown)
        yield from d.step(*STEPS[0])
        yield from d.click(w.nav_buttons[0])
        yield 1200
        # 1 - presets / typing the address
        yield from d.step(*STEPS[1])
        yield from d.point_at(w.btn_ip_lungphan, ms=800)
        yield 900
        yield from d.point_at(w.btn_ip_trace, ms=600)
        yield 1400
        yield from d.until_left(3.5)
        yield from self.type_text(w.DuetIPAddress.lineEdit(), IP)
        # 2 - red before connecting
        yield from d.step(*STEPS[2])
        bar = w.tabWidget.tabBar()
        yield from d.click(bar, bar.tabRect(w.tabWidget.indexOf(w.tab_platform)).center())
        yield 600
        for b in (w.MIN_LATAXIS, w.PLUS_SIAXIS, w.MIN_APAXIS, w.PLUS_ROLL):
            yield from d.point_at(b, ms=550)
            yield 500
        # 3 - connect
        yield from d.step(*STEPS[3])
        yield from d.click(w.setDuetIP)
        if not (yield from self.wait_for(lambda: getattr(w, 'duet_connected', False)
                                         and not getattr(w, '_connecting_in_progress', False), 25)):
            print("ABORT: could not connect to", IP, flush=True)
            return
        yield 1500
        yield from d.point_at(w.btn_ip_trace, ms=700)
        yield 900
        yield from d.point_at(w.connect_status, ms=600)
        yield 800
        if self.homed():
            print("ABORT: the platform is already homed - switch it off and on, then record again", flush=True)
            return
        # 4 - home all
        yield from d.step(*STEPS[4])
        yield from d.point_at(w.MIN_APAXIS, ms=600)
        yield 800
        yield from d.until_left(6.0)
        yield from d.click(w.HOME_ALL_PLATFORM)
        # 5 - homing (narration while it runs), then green
        yield from d.step(*STEPS[5])
        t_home = time.perf_counter()
        if not (yield from self.wait_for(self.homed, 240)):
            print("ABORT: homing did not finish within 4 minutes", flush=True)
            return
        print(f"  homed after {time.perf_counter() - t_home:.1f} s", flush=True)
        yield 1500
        for b in (w.MIN_LATAXIS, w.PLUS_SIAXIS, w.MIN_APAXIS, w.PLUS_PITCH):
            yield from d.point_at(b, ms=500)
            yield 450
        # 6 - homed stays homed
        yield from d.step(*STEPS[6])
        yield from d.point_at(w.connect_status, ms=700)
        yield 1000
        # 7 - send a command
        yield from d.step(*STEPS[7])
        yield from self.type_text(w.duet_command, "M115")
        yield from d.click(w.sendCommandDUET)
        yield 2500
        yield from d.point_at(w.duet_log_console, ms=700)
        yield 1500
        # 8 - light / dark
        yield from d.step(*STEPS[8])
        tb = getattr(w, 'button_console_theme', None)
        if tb is not None:
            yield from d.click(tb)
            yield 2200
            yield from d.click(tb)
            yield 1200
        # 9 - step size
        yield from d.step(*STEPS[9])
        for key in ("0.1", "10", "1"):
            b = w.step_buttons.get(key)
            if b is not None:
                yield from d.click(b) if key == "1" else d.point_at(b, ms=600)
                yield 700
        # 10 - incremental moves: AP +1, then step 5, AP +5
        yield from d.step(*STEPS[10])
        yield from d.click(w.PLUS_APAXIS)
        yield 2500
        yield from d.click(w.step_buttons["5"])
        yield 600
        yield from d.click(w.PLUS_APAXIS)
        yield 3000
        yield from d.point_at(w.POS_CURR_APAXIS, ms=600)
        yield 1200
        # 11 - limits: LAT is at its maximum after homing
        yield from d.step(*STEPS[11])
        yield from d.point_at(w.POS_CURR_LATAXIS, ms=700)
        yield 1500
        yield from d.until_left(9.0)
        yield from d.click(w.PLUS_LATAXIS)
        yield from self.close_message()
        # 12 - go to center
        yield from d.step(*STEPS[12])
        yield from d.click(w.btn_go_to_center)
        yield 9000
        # 13 - dimensions
        yield from d.step(*STEPS[13])
        yield from d.point_at(w.input_plat_lat, ms=700)
        yield 1500
        yield from d.point_at(w.input_plat_si, ms=600)
        yield 1500
        # 14 - rotation offset
        yield from d.step(*STEPS[14])
        for f in (w.input_offset_ap, w.input_offset_lat, w.input_offset_si):
            yield from d.point_at(f, ms=600)
            yield 1100
        # 15 - done
        yield from d.step(*STEPS[15])
        self.ok = True


def build_window():
    from demo_planning import build_window as bw
    return bw()


def main():
    os.makedirs(OUT, exist_ok=True)
    cfg = os.path.join(r"C:\TRACE", "configuration.json")
    cfg_bak = os.path.join(tempfile.gettempdir(), "logiq_demo_control_cfg.json")
    shutil.copy2(cfg, cfg_bak)
    if CHECK:
        clips, durs = [], [0.3] * len(STEPS)
    else:
        clips = K.tts_clips([n for _c, _s, n in STEPS], os.path.join(OUT, f"{TAG}_clips"), rate=-1, speed=0.95)
        durs = [dd for _p, dd in clips]

    app = QApplication.instance() or QApplication(sys.argv)
    for eff in (Qt.UI_AnimateMenu, Qt.UI_FadeMenu, Qt.UI_AnimateCombo, Qt.UI_AnimateTooltip, Qt.UI_FadeTooltip):
        QApplication.setEffectEnabled(eff, False)
    w = build_window()
    w.showMaximized()
    ov = K.Overlay()
    ov.show()
    # dialogs (Connecting..., message boxes) put the always-on-top window above the overlay: captions and the
    # pointer highlight vanished after the connect dialog.  Keep raising the overlay.
    from PySide6.QtCore import QTimer
    def overlay_on_top():
        ov.raise_()
        if sys.platform == "win32":
            try:
                import ctypes
                # HWND_TOPMOST, SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE
                ctypes.windll.user32.SetWindowPos(int(ov.winId()), -1, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010)
            except Exception:
                pass

    keep_top = QTimer()
    keep_top.timeout.connect(overlay_on_top)
    keep_top.start(250)
    d = K.PacedDirector(ov, durs, speed=1.0)
    demo = Demo(w, d)
    rec = K.Recorder(os.path.join(OUT, f"{TAG}_silent.mp4"), None)

    def run():
        yield 1500
        if not CHECK:
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
        if not CHECK:
            d.t0 = rec.t_start
        yield from demo.run()
        if demo.ok:
            yield from d.finish()
        ov.caption = ""
        yield 1500

    def finish():
        total = time.perf_counter() - (rec.t_start or d.t0 or time.perf_counter())
        if not CHECK and rec.t_start is not None:
            err = rec.stop()
            if demo.ok:
                starts = [t for t, _c, _n in d.steps]
                d.write_srt(os.path.join(OUT, f"{TAG}.srt"), total)
                K.assemble_narration(clips, starts, os.path.join(OUT, f"{TAG}_narration.wav"), total)
                rc, merr = K.mux_audio(os.path.join(OUT, f"{TAG}_silent.mp4"),
                                       os.path.join(OUT, f"{TAG}_narration.wav"), os.path.join(OUT, f"{TAG}.mp4"))
                print("recorder:", (err or "").strip() or "ok", "| mux:", rc, (merr or "").strip()[:300], flush=True)
                bl = K.black_segments(os.path.join(OUT, f"{TAG}_silent.mp4"))
                print("black stretches:", bl if bl else "none", flush=True)
            else:
                print("recording stopped early (demo aborted): video not assembled", flush=True)
        print("completed:", demo.ok, "| steps:", [(round(tt, 1), c) for tt, c, _n in d.steps], "| total",
              round(total, 1), flush=True)
        try:
            from fcn_control.fcn_control import is_axis_homed
            print("homed LAT/SI/AP:", [is_axis_homed(w, k) for k in ("LAT", "SI", "AP")],
                  "| AP", w.POS_CURR_APAXIS.text(), "LAT", w.POS_CURR_LATAXIS.text(), "SI", w.POS_CURR_SIAXIS.text(),
                  flush=True)
        except Exception:
            pass
        ov.close()
        w.close()
        shutil.copy2(cfg_bak, cfg)
        app.quit()

    d.run(run(), on_finish=finish)
    app.exec()


if __name__ == "__main__":
    main()
