"""Trial recording of the demo toolkit on the Control tab (nothing is sent to a Duet)."""
import os
import shutil
import sys
import time

sys.path.insert(0, r"C:\TRACE")
os.chdir(r"C:\TRACE")
from PySide6.QtWidgets import QApplication

import demo_kit as K

OUT = os.environ.get("DEMO_OUT", os.path.join(r"C:\TRACE\demo", "output"))
os.makedirs(OUT, exist_ok=True)

STEPS = [
    ("TRACE - trial recording", "This is a short trial of the demo recording."),
    ("Step 1 - The command console", "On the Control tab, the console shows commands and replies from the Duet."),
    ("Step 2 - Light or dark console", "The sun and moon button switches the console between light and dark mode."),
    ("Step 3 - Typing a command", "Type a G-code command in the box. Here we only type it, nothing is sent."),
]


def main():
    cfg = os.path.join(r"C:\TRACE", "configuration.json")
    cfg_bak = cfg + ".demo_bak"
    if os.path.isfile(cfg):
        shutil.copy2(cfg, cfg_bak)
    clips = K.tts_clips([n for _c, n in STEPS], os.path.join(OUT, "trial_clips"))
    durs = [d for _p, d in clips]

    app = QApplication.instance() or QApplication(sys.argv)
    import Launch_ImGUI as L
    from fcn_create_gui.window_fit import fit_tabs_to_current_page
    from fcn_create_gui.top_bar_style import style_top_bar
    from fcn_create_gui.console_theme import add_console_theme_button
    w = L.MyApp(None)
    app.setStyle('Fusion')
    fit_tabs_to_current_page(w)
    style_top_bar(w)
    add_console_theme_button(w)
    w.showMaximized()
    ov = K.Overlay()
    ov.show()
    d = K.PacedDirector(ov, durs)
    rec = K.Recorder(os.path.join(OUT, "trial_video.mp4"), None)

    def demo():
        yield 1500
        rec.rect = K.physical_rect(w)
        print("recording rect (physical px):", rec.rect, flush=True)
        rec.start()
        yield 1200                       # ffmpeg start-up
        d.start_clock()
        d.t0 = rec.t_start               # narration / subtitles relative to the recording start
        ov.big_text = "TRACE"
        ov.big_sub = "Trial recording"
        yield from d.step(*STEPS[0])
        yield 1500
        ov.big_text = ""
        yield from d.step(*STEPS[1])
        yield from d.point_at(w.duet_log_console)
        yield 800
        yield from d.step(*STEPS[2])
        yield from d.click(w.button_console_theme)
        yield 1200
        yield from d.click(w.button_console_theme)
        yield from d.step(*STEPS[3])
        yield from d.type_into(w.duet_command, "M115", select_all=False)
        yield from d.finish()
        ov.caption = ""
        yield 800

    def finish():
        total = time.perf_counter() - rec.t_start
        err = rec.stop()
        starts = [t for t, _c, _n in d.steps]
        d.write_srt(os.path.join(OUT, "trial_video.srt"), total)
        K.assemble_narration(clips, starts, os.path.join(OUT, "trial_narration.wav"), total)
        rc, merr = K.mux_audio(os.path.join(OUT, "trial_video.mp4"), os.path.join(OUT, "trial_narration.wav"),
                               os.path.join(OUT, "trial_with_audio.mp4"))
        print("recorder:", err.strip() or "ok", "| mux:", rc, merr.strip()[:300], "| total", round(total, 1), flush=True)
        w.duet_command.clear()
        ov.close()
        w.close()
        if os.path.isfile(cfg_bak):
            shutil.copy2(cfg_bak, cfg)
            os.remove(cfg_bak)
        app.quit()

    d.run(demo(), on_finish=finish)
    app.exec()


if __name__ == "__main__":
    main()
