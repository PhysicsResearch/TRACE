# Narrated user-guide videos: how they are made (LogIQ / TRACE pipeline)

A recipe to build the same kind of videos for another PySide6 desktop app (e.g. AMIGO). It covers the tools, how
the script drives the real app, the voice and the website export, plus what went wrong before and how it was fixed.
All paths are on this PC.

## 1. What a video is

- The **real app window** is driven by a Python script: the actual OS mouse pointer moves smoothly and clicks the
  real widgets. Nothing is mocked; when a device is connected, it really moves.
- A transparent, click-through **overlay** draws on top of the app:
  - a yellow halo around the pointer;
  - a red ring at every click;
  - a short outline around the control about to be used;
  - a dark caption box ("Step 3 - Connect", with a sub-caption).
- **ffmpeg** records only the app window's screen rectangle (gdigrab), never the second screen or the whole desktop.
- A **neural voice** (Kokoro) reads one narration text per step. Each clip is placed at the time its step really
  started during the run, then muxed into the video.
- Outputs per video, in `demo/output/<tag>`:
  - `<tag>.mp4` (with voice)
  - `_silent.mp4`
  - `.srt` (step captions)
  - `_narration.wav`
  - `_clips/` (one wav per step)

## 2. Files to copy (from `C:\TRACE\demo\`)

| File | What it is | Reuse |
| :--- | :--- | :--- |
| `demo_kit.py` | Overlay, Director / PacedDirector, TTS, narration assembly, Recorder (ffmpeg), mux, window checks | Copy as is; change the colours at the top and the `TRACE_DEMO_*` env names if you like |
| `kokoro_tts.py` | Runs Kokoro in its own conda env; `PRONUNCIATIONS` for product names | Copy; replace the names in `PRONUNCIATIONS` |
| `demo_control.py`, `demo_intro.py` | Complete example scripts (steps list, demo class, `main()`) | Templates for new videos |
| `demo_planning.py` | Planning videos; `build_window()`; helpers to type into spin boxes and answer modal dialogs | Pattern for `build_window()` and helpers |
| `site_videos.py` | Copies videos to the website: fast-start MP4, poster JPG, WebVTT subtitles, chapters JSON | Adapt the list and the site path |
| `site_shots.py`, `site_shots_control.py` | Website screenshots with `widget.grab()` (only the app, real fonts), cropped and saved as WebP | Adapt the widget names |

## 3. Environments and tools

- **App Python:** the app's own conda env, e.g. `C:\Users\gabri\anaconda3\envs\TRACE\python.exe`. For AMIGO, its own
  env, probably `envs\amigo`.
- **Voice:** a separate conda env, `C:\Users\gabri\anaconda3\envs\kokoro` (package `kokoro`, model
  `hexgrad/Kokoro-82M`).
  - Voice `bf_emma` (British English), `speed=0.95`.
  - `demo_kit.tts_clips()` calls it through `kokoro_tts.py`; `TRACE_DEMO_KOKORO_PY` / `TRACE_DEMO_VOICE` override it.
  - If the env is missing, it falls back to the Windows voice (Zira). That sounds worse, so avoid it.
- **ffmpeg:** set `TRACE_DEMO_FFMPEG` to an ffmpeg.exe, or `pip install imageio-ffmpeg` in the app env (`find_ffmpeg()`
  uses it).
  - The TRACE recordings used
    `C:\Users\gabri\AppData\Local\Temp\claude\...\scratchpad\rec_venv\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v9.0.2.exe`.
    That folder is temporary, so install imageio-ffmpeg properly.
  - **A missing ffmpeg fails with `FileNotFoundError: [WinError 2]` right after "recording".**

## 4. Structure of a video script

```python
STEPS = [  # (caption, sub-caption, narration)
    ("Control tab - KINETIQ", "LogIQ user guide - manual control", "This video shows ..."),
    ("Step 1 - Connect", "the button with the link icon", "Now press the connect button ..."),
    ...
]

class Demo:
    def run(self):                       # a generator: every `yield ms` waits inside the Qt event loop
        yield from d.step(*STEPS[0])     # caption on + step start time recorded (narration placed there)
        yield from d.click(w.some_button)            # pointer glides there, outline, click ripple, real click
        yield from d.point_at(w.some_field, ms=700)  # point without clicking
        yield from d.until_left(3.0)     # wait until 3 s of this step's narration remain (sync an action to a sentence)
        yield from self.wait_for(lambda: w.connected, 25)   # poll real state; ABORT cleanly on timeout
```

`main()`, following `demo_control.py`, does this:

1. Back up the app's config file, and restore it in `finish()` whatever happens.
2. `clips = K.tts_clips([narrations], out/<tag>_clips, rate=-1, speed=0.95)` gives the step durations.
3. Build the window (`build_window()`: the same theme / layout calls as the app's launcher), `showMaximized()`, create
   `K.Overlay()`, then `K.PacedDirector(ov, durations)`. A paced step lasts at least as long as its narration.
4. Keep the overlay on top (see pitfalls).
5. `K.bring_to_front(w, ov)`, then `K.window_on_screen(w)`, so nothing is covering the app before recording starts.
   Then `rec.rect = K.physical_rect(w); rec.start()`.
6. Run the demo.
7. Then:
   - `rec.stop()`;
   - `d.write_srt(...)`;
   - `K.assemble_narration(clips, step_starts, wav, total)`;
   - `K.mux_audio(silent, wav, mp4)`;
   - `K.black_segments(silent)`, which should print "none".
8. Run modes:
   - `--check` / `--dry`: runs the steps fast without voice or recording, to test the flow first;
   - `--plan`: an offline check of a generated result before involving hardware.

## 5. Narration style the user liked

- **Order:** a short intro saying what the video shows and where it fits (other videos show details), then
  "Step N - ..." captions with a sub-caption (one line, the key fact), then a "Done" step with a one-sentence summary.
- **Each narration:** 1–3 short sentences, describing what is on screen as it happens. Plain words; no internal
  names, file paths or code. Numbers are written out where the voice would misread them ("M one one five", "zero
  point four seconds"); IP addresses are not read aloud.
- **Product names** say the display name, with a phoneme override in `kokoro_tts.PRONUNCIATIONS` (e.g.
  `"LogIQ": "/lˈɒʤɪk/"`). Check every new product name once by ear.
- **Not public:** the company name.
- **Length:** detail videos 2–5 min; the end-to-end overview about 4–5 min, saying that each step has its own detailed
  video.

## 6. Pitfalls already solved

- **Overlay hidden after a dialog.** A modal dialog (e.g. "Connecting...") puts the always-on-top app window above the
  overlay, and captions and the pointer halo vanished for the rest of the video. Fix: a 250 ms QTimer that re-raises
  the overlay with `ov.raise_()` and `SetWindowPos(HWND_TOPMOST)` (see `overlay_on_top` in `demo_control.py`).
- **Another window on top during recording** (a notification popup): the user had to stop it. Ask the user to keep
  the screen clear; the start check only covers the start.
- **Modal dialogs and message boxes:** clicks are delivered with `QTimer.singleShot(0, QTest.mouseClick)`, so the demo
  keeps running inside the dialog's event loop. Find the dialog with `d.wait_popup()` and click its OK button (see
  `close_message`, and `answer_modal` in `demo_planning.py`).
- **Typing:** select all, type characters, check the widget value, and set it directly if the app reformatted it.
  Decimal comma or point depends on the widget.
- **Offscreen Qt (`QT_QPA_PLATFORM=offscreen`) has no fonts** (squares in screenshots). Use the real platform for
  screenshots and recordings.
- **Hardware state:** check it read-only before recording (connected, homed, etc.) and make the script ABORT if the
  state is wrong, rather than recording a broken video. Never change device configuration without asking the user.
- **Time:** poll real state instead of fixed sleeps (connect, homing, job running / finished). Narration that runs
  while the device works keeps people from waiting.

## 7. Website export (`site_videos.py`)

- ffmpeg `-c copy -movflags +faststart` to `public/videos/<id>.mp4`.
- A poster JPG at a chosen second.
- WebVTT subtitles: each step's narration split into ~60–110 character cues, spread over the step by length.
- `videos.generated.json`: id, title (`"<Group> - <Title>"`), src, poster, captions, duration, chapters (step start
  times and captions), size.

The site (Next.js) reads that JSON for the video player with clickable chapters, and the guide pages link a video
with `video: <id>` in their front matter.

## 8. Checking a finished video

```
ffmpeg -ss <t> -i video.mp4 -frames:v 1 frame.png      # a few frames at key moments, tiled into one image
```

Check:
- the captions are present all through;
- the pointer halo is there;
- dialogs and messages are readable;
- the end state is right;
- `black stretches: none`;
- the total length;
- a few narration lines played back in sync with their step.
