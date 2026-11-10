"""
Toolkit for the TRACE user-guide demo videos (recorded by the user with the Windows screen recorder).

* Overlay: a click-through, always-on-top transparent window over the whole screen that draws
  - a soft yellow circle following the mouse pointer,
  - an expanding red ring at every click (blue for a right click),
  - a short outline around the control about to be used,
  - a caption strip ("Step 3 - Add a sine curve on X") and the start countdown.
* Director: runs a demo as a Python generator inside the Qt event loop, so modal menus / dialogs opened by a click
  keep the demo going (their nested event loop runs the director's timers).  A step yields a delay in ms.
* The real OS mouse pointer is moved smoothly (QCursor.setPos), clicks are delivered with QTest at that point, so
  hover effects and the recording show what a user would see.
* Narration: one clip per step with the offline Windows voices (System.Speech), timed to the step start times measured
  during the run; written as one WAV per video plus an .srt subtitle file, ready to drop into Clipchamp.

Nothing here talks to the Duet.
"""
import math
import os
import subprocess
import time
import wave

from PySide6.QtCore import Qt, QPoint, QPointF, QRect, QRectF, QTimer
from PySide6.QtGui import QColor, QCursor, QFont, QGuiApplication, QPainter, QPen
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

POINTER_COLOR = QColor(255, 214, 0, 110)        # soft yellow halo
POINTER_EDGE = QColor(255, 179, 0, 200)
CLICK_COLOR = QColor(229, 57, 53)               # left click ring
RCLICK_COLOR = QColor(75, 97, 67)              # right click ring (KINETIQ olive)
OUTLINE_COLOR = QColor(229, 57, 53, 230)
CAPTION_BG = QColor(31, 39, 28, 220)           # dark olive (KINETIQ)


class Overlay(QWidget):
    def __init__(self):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
                         | Qt.WindowTransparentForInput | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        scr = QGuiApplication.primaryScreen()
        self.setGeometry(scr.geometry())
        self.ripples = []            # (global QPoint, t0, color)
        self.outline = None          # (global QRect, t_end)
        self.caption = ""
        self.caption_sub = ""
        self.big_text = ""
        self.big_sub = ""
        self.show_pointer = True
        self.caption_y = 118         # logical px from the screen top: just below the main tab bar, over the plot
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.update)
        self._timer.start(16)

    def click_ripple(self, gpos, right=False):
        self.ripples.append((QPoint(gpos), time.perf_counter(), RCLICK_COLOR if right else CLICK_COLOR))

    def flash_outline(self, grect, seconds=1.2):
        self.outline = (QRect(grect), time.perf_counter() + seconds)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        now = time.perf_counter()
        off = self.geometry().topLeft()
        if self.outline is not None:
            r, t_end = self.outline
            if now < t_end:
                pen = QPen(OUTLINE_COLOR, 4)
                p.setPen(pen)
                p.setBrush(Qt.NoBrush)
                p.drawRoundedRect(QRectF(r.translated(-off)).adjusted(-5, -5, 5, 5), 8, 8)
            else:
                self.outline = None
        keep = []
        for gpos, t0, color in self.ripples:
            age = now - t0
            if age < 0.7:
                keep.append((gpos, t0, color))
                c = QColor(color)
                c.setAlphaF(max(0.0, 0.9 * (1 - age / 0.7)))
                p.setPen(QPen(c, 4))
                p.setBrush(Qt.NoBrush)
                rad = 10 + 38 * (age / 0.7)
                p.drawEllipse(QPointF(gpos - off), rad, rad)
        self.ripples = keep
        if self.show_pointer:
            cp = QCursor.pos() - off
            p.setPen(QPen(POINTER_EDGE, 2))
            p.setBrush(POINTER_COLOR)
            p.drawEllipse(QPointF(cp), 28, 28)
        if self.caption:
            self._draw_caption(p)
        if self.big_text:
            self._draw_big(p)
        p.end()

    def _draw_caption(self, p):
        f1 = QFont("Segoe UI", 22, QFont.Bold)
        f2 = QFont("Segoe UI", 15)
        p.setFont(f1)
        w1 = p.fontMetrics().horizontalAdvance(self.caption)
        h1 = p.fontMetrics().height()
        w2 = h2 = 0
        if self.caption_sub:
            p.setFont(f2)
            w2 = p.fontMetrics().horizontalAdvance(self.caption_sub)
            h2 = p.fontMetrics().height()
        w = max(w1, w2) + 48
        h = h1 + (h2 + 4 if h2 else 0) + 22
        x = (self.width() - w) / 2
        y = self.caption_y
        p.setPen(Qt.NoPen)
        p.setBrush(CAPTION_BG)
        p.drawRoundedRect(QRectF(x, y, w, h), 14, 14)
        p.setPen(QColor("white"))
        p.setFont(f1)
        p.drawText(QRectF(x, y + 10, w, h1), Qt.AlignHCenter | Qt.AlignVCenter, self.caption)
        if h2:
            p.setFont(f2)
            p.setPen(QColor("#ffe082"))
            p.drawText(QRectF(x, y + 14 + h1, w, h2), Qt.AlignHCenter | Qt.AlignVCenter, self.caption_sub)

    def _draw_big(self, p):
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 150))
        p.drawRect(self.rect())
        p.setPen(QColor("white"))
        p.setFont(QFont("Segoe UI", 64, QFont.Bold))
        p.drawText(self.rect().adjusted(0, -80, 0, -80), Qt.AlignCenter, self.big_text)
        if self.big_sub:
            p.setFont(QFont("Segoe UI", 20))
            p.drawText(self.rect().adjusted(0, 80, 0, 80), Qt.AlignCenter, self.big_sub)


def _ease(u):
    return 0.5 - 0.5 * math.cos(math.pi * u)


class Director:
    """Runs a demo generator: each ``yield ms`` waits that long (inside the Qt event loop)."""

    def __init__(self, overlay, speed=1.0):
        self.ov = overlay
        self.speed = speed
        self.gen = None
        self.steps = []                 # (start_s, caption, narration) measured during the run
        self.t0 = None
        self.done = False
        self.on_finish = None

    # --- driving -------------------------------------------------------------------------------------------------
    def run(self, gen, on_finish=None):
        self.gen = gen
        self.on_finish = on_finish
        QTimer.singleShot(0, self._next)

    def _next(self):
        try:
            ms = next(self.gen)
        except StopIteration:
            self.done = True
            if self.on_finish:
                self.on_finish()
            return
        except Exception:
            import traceback
            traceback.print_exc()
            self.done = True
            if self.on_finish:
                self.on_finish()
            return
        QTimer.singleShot(max(0, int((ms or 0) / self.speed)), self._next)

    # --- building blocks (generators: use with ``yield from``) --------------------------------------------------
    def start_clock(self):
        self.t0 = time.perf_counter()

    def step(self, caption, sub="", narration=None, hold_ms=0):
        """Shows the caption and records its start time (for subtitles / narration)."""
        self.ov.caption, self.ov.caption_sub = caption, sub
        t = 0.0 if self.t0 is None else time.perf_counter() - self.t0
        self.steps.append((t, caption, narration if narration is not None else caption))
        if hold_ms:
            yield hold_ms

    def countdown(self, seconds=10, title="", hint="Start the screen recording now (Win + Shift + R)"):
        self.ov.caption = ""
        for k in range(seconds, 0, -1):
            self.ov.big_text, self.ov.big_sub = str(k), hint
            yield 1000
        self.ov.big_text = title
        self.ov.big_sub = ""
        if title:
            yield 1800
        self.ov.big_text = ""

    def move_to(self, gpos, ms=650):
        a = QCursor.pos()
        b = QPoint(gpos)
        n = max(2, int(ms / 16))
        for i in range(1, n + 1):
            u = _ease(i / n)
            QCursor.setPos(int(a.x() + (b.x() - a.x()) * u), int(a.y() + (b.y() - a.y()) * u))
            yield 16

    def point_at(self, widget, local=None, ms=650, outline=True):
        if local is None:
            local = widget.rect().center()
        g = widget.mapToGlobal(local)
        if outline:
            self.ov.flash_outline(QRect(widget.mapToGlobal(QPoint(0, 0)), widget.size()))
        yield from self.move_to(g, ms)

    def click(self, widget, local=None, right=False, ms=650, pause_ms=350, outline=True):
        """Moves the real pointer onto the widget and clicks there (QTest), with a ripple."""
        if local is None:
            local = widget.rect().center()
        yield from self.point_at(widget, local, ms, outline)
        yield pause_ms
        self.ov.click_ripple(widget.mapToGlobal(local), right)
        btn = Qt.RightButton if right else Qt.LeftButton
        # deliver after this timer callback returns: a modal menu / dialog opened by the click must not block _next
        QTimer.singleShot(0, lambda: QTest.mouseClick(widget, btn, Qt.NoModifier, local))
        yield 450

    def type_into(self, widget, text, per_char_ms=90, select_all=True):
        yield from self.click(widget, pause_ms=200)
        if select_all:
            widget.setFocus()
            QTest.keyClick(widget, Qt.Key_A, Qt.ControlModifier)
            yield 120
        for ch in text:
            QTest.keyClicks(widget, ch)
            yield per_char_ms
        QTest.keyClick(widget, Qt.Key_Return)
        yield 300

    def drag(self, widget, a_local, b_local, ms=900, right=False):
        """Press at a, move to b, release (real pointer follows; events via QTest)."""
        btn = Qt.RightButton if right else Qt.LeftButton
        yield from self.point_at(widget, a_local, 600)
        yield 250
        self.ov.click_ripple(widget.mapToGlobal(a_local), right)
        QTest.mousePress(widget, btn, Qt.NoModifier, a_local)
        n = max(2, int(ms / 16))
        for i in range(1, n + 1):
            u = _ease(i / n)
            pt = QPoint(int(a_local.x() + (b_local.x() - a_local.x()) * u),
                        int(a_local.y() + (b_local.y() - a_local.y()) * u))
            QCursor.setPos(widget.mapToGlobal(pt))
            QTest.mouseMove(widget, pt)
            yield 16
        QTest.mouseRelease(widget, btn, Qt.NoModifier, b_local)
        yield 300

    def wait_popup(self, timeout_ms=3000):
        """Waits for a popup menu / dialog to appear; returns via self.popup (None on timeout)."""
        self.popup = None
        t_end = time.perf_counter() + timeout_ms / 1000.0
        while time.perf_counter() < t_end:
            w = QApplication.activePopupWidget() or QApplication.activeModalWidget()
            if w is not None and w.isVisible():
                self.popup = w
                return
            yield 50

    def choose_menu_item(self, menu, text_part, ms=600):
        """Moves to the menu action whose text contains text_part and triggers it."""
        act = next((a for a in menu.actions() if text_part.lower() in a.text().lower() and a.isEnabled()), None)
        if act is None:
            menu.close()
            yield 200
            return False
        r = menu.actionGeometry(act)
        yield from self.move_to(menu.mapToGlobal(r.center()), ms)
        menu.setActiveAction(act)
        yield 450
        self.ov.click_ripple(menu.mapToGlobal(r.center()))
        # select it the way a click does, so QMenu.exec() returns this action (callers read the return value)
        menu.setActiveAction(act)
        QTimer.singleShot(0, lambda: QTest.keyClick(menu, Qt.Key_Return))
        yield 400
        return True

    # --- outputs ---------------------------------------------------------------------------------------------------
    def write_srt(self, path, total_s):
        def ts(x):
            ms = int(round(x * 1000))
            return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"
        lines = []
        for i, (t, cap, _n) in enumerate(self.steps):
            t_end = self.steps[i + 1][0] if i + 1 < len(self.steps) else total_s
            lines += [str(i + 1), f"{ts(t)} --> {ts(max(t + 0.5, t_end - 0.05))}", cap, ""]
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))


# --------------------------------------------------------------------------------------------------------------------
# Narration: Kokoro (natural offline voice, default 'bf_emma', in its own conda env) or the Windows voices
# --------------------------------------------------------------------------------------------------------------------
RATE = 22050
KOKORO_PY = os.environ.get("TRACE_DEMO_KOKORO_PY",
                           os.path.join(os.path.expanduser("~"), "anaconda3", "envs", "kokoro", "python.exe"))
KOKORO_VOICE = os.environ.get("TRACE_DEMO_VOICE", "bf_emma")


def tts_clips(texts, out_dir, voice=None, rate=0, speed=1.0):
    """One WAV per text.  Kokoro (voice KOKORO_VOICE) when its environment exists, else the Windows voice.
    Returns [(path, seconds)]."""
    if os.path.isfile(KOKORO_PY) and os.environ.get("TRACE_DEMO_TTS", "kokoro") == "kokoro":
        return tts_clips_kokoro(texts, out_dir, voice or KOKORO_VOICE, speed)
    return tts_clips_windows(texts, out_dir, voice or "Microsoft Zira Desktop", rate)


def tts_clips_kokoro(texts, out_dir, voice="bf_emma", speed=1.0):
    import json
    os.makedirs(out_dir, exist_ok=True)
    job = os.path.join(out_dir, "kokoro_job.json")
    with open(job, "w", encoding="utf-8") as f:
        json.dump({"texts": list(texts), "out_dir": out_dir, "voice": voice, "speed": speed}, f)
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kokoro_tts.py")
    r = subprocess.run([KOKORO_PY, script, job], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError("Kokoro failed: " + r.stderr[-1500:])
    out = []
    for i in range(len(texts)):
        path = os.path.join(out_dir, f"clip_{i:02d}.wav")
        with wave.open(path, "rb") as w:
            out.append((path, w.getnframes() / float(w.getframerate())))
    return out


def tts_clips_windows(texts, out_dir, voice="Microsoft Zira Desktop", rate=0):
    """One WAV per text (22.05 kHz, 16-bit mono).  Returns [(path, seconds)]."""
    os.makedirs(out_dir, exist_ok=True)
    jobs = []
    for i, text in enumerate(texts):
        path = os.path.join(out_dir, f"clip_{i:02d}.wav")
        jobs.append((path, text))
    ps = ["Add-Type -AssemblyName System.Speech",
          "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer",
          f"$s.SelectVoice('{voice}')",
          f"$s.Rate = {int(rate)}",
          "$fmt = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(22050, "
          "[System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono)"]
    for path, text in jobs:
        t = text.replace("'", "''")
        ps += [f"$s.SetOutputToWaveFile('{path}', $fmt)", f"$s.Speak('{t}')"]
    ps.append("$s.SetOutputToNull()")
    subprocess.run(["powershell", "-NoProfile", "-Command", "; ".join(ps)], check=True, capture_output=True)
    out = []
    for path, _ in jobs:
        with wave.open(path, "rb") as w:
            out.append((path, w.getnframes() / float(w.getframerate())))
    return out


def assemble_narration(clips, starts, out_path, total_s):
    """Places clip i at starts[i] seconds (silence elsewhere) in one WAV of total_s seconds, at the clips' rate
    (16-bit mono: 22.05 kHz Windows voice, 24 kHz Kokoro)."""
    rate_hz = RATE
    if clips:
        with wave.open(clips[0][0], "rb") as w:
            rate_hz = w.getframerate()
    n_total = int(round(total_s * rate_hz))
    buf = bytearray(n_total * 2)
    for (path, _dur), t in zip(clips, starts):
        with wave.open(path, "rb") as w:
            data = w.readframes(w.getnframes())
        i0 = int(round(t * rate_hz)) * 2
        end = min(len(buf), i0 + len(data))
        if i0 < len(buf):
            buf[i0:end] = data[:end - i0]
    with wave.open(out_path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate_hz)
        w.writeframes(bytes(buf))


# --------------------------------------------------------------------------------------------------------------------
# Screen recording (ffmpeg gdigrab: the whole desktop incl. the overlay and the mouse pointer) and audio muxing
# --------------------------------------------------------------------------------------------------------------------
def find_ffmpeg():
    exe = os.environ.get("TRACE_DEMO_FFMPEG")
    if exe and os.path.isfile(exe):
        return exe
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def physical_rect(widget):
    """The widget's frame rectangle in physical desktop pixels (what gdigrab uses), clipped to its screen."""
    scr = widget.screen()
    dpr = scr.devicePixelRatio()
    g = widget.geometry() if widget.isMaximized() else widget.frameGeometry()
    sg = scr.geometry()
    g = g.intersected(sg)
    # physical origin of this screen: Windows places screens in physical pixels; for the primary screen it is 0,0
    ox = int(round(sg.x() * dpr))
    oy = int(round(sg.y() * dpr))
    x = ox + int(round((g.x() - sg.x()) * dpr))
    y = oy + int(round((g.y() - sg.y()) * dpr))
    w = int(round(g.width() * dpr)) // 2 * 2
    h = int(round(g.height() * dpr)) // 2 * 2
    return x, y, w, h


class Recorder:
    """Records ONLY a rectangle of the desktop (the TRACE window), never the whole multi-screen desktop."""

    def __init__(self, out_path, rect, fps=25, width=1920):
        self.out_path = out_path
        self.rect = rect             # (x, y, w, h) physical pixels, e.g. physical_rect(window)
        self.fps = fps
        self.width = width
        self.proc = None
        self.t_start = None

    def start(self):
        x, y, w, h = self.rect
        cmd = [find_ffmpeg(), "-y", "-loglevel", "error", "-f", "gdigrab", "-framerate", str(self.fps),
               "-draw_mouse", "1", "-offset_x", str(x), "-offset_y", str(y), "-video_size", f"{w}x{h}",
               "-i", "desktop",
               "-vf", f"scale={self.width}:-2:flags=lanczos", "-c:v", "libx264", "-preset", "veryfast",
               "-crf", "20", "-pix_fmt", "yuv420p", self.out_path]
        keep_display_awake(True)        # synthetic pointer moves do not count as activity: no dimming / sleep
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        self.t_start = time.perf_counter()

    def stop(self):
        if self.proc is None:
            return
        keep_display_awake(False)
        try:
            self.proc.stdin.write(b"q")
            self.proc.stdin.flush()
            self.proc.wait(timeout=30)
        except Exception:
            self.proc.kill()
        err = self.proc.stderr.read().decode("utf-8", "replace") if self.proc.stderr else ""
        self.proc = None
        return err


def mux_audio(video, audio, out_path):
    cmd = [find_ffmpeg(), "-y", "-loglevel", "error", "-i", video, "-i", audio, "-map", "0:v", "-map", "1:a",
           "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-shortest", out_path]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode, r.stderr


def probe_duration(path):
    r = subprocess.run([find_ffmpeg(), "-i", path], capture_output=True, text=True)
    for line in r.stderr.splitlines():
        if "Duration:" in line:
            hh, mm, ss = line.split("Duration:")[1].split(",")[0].strip().split(":")
            return int(hh) * 3600 + int(mm) * 60 + float(ss)
    return None


def extract_frame(video, t, out_png):
    subprocess.run([find_ffmpeg(), "-y", "-loglevel", "error", "-ss", f"{t:.2f}", "-i", video, "-frames:v", "1",
                    out_png], capture_output=True)


class PacedDirector(Director):
    """Director whose steps last at least as long as their narration clip (+ a small gap)."""

    def __init__(self, overlay, durations=None, gap_s=0.5, speed=1.0):
        super().__init__(overlay, speed)
        self.durations = list(durations or [])
        self._cur_start = None

    def step(self, caption, sub="", narration=None, hold_ms=0):
        k = len(self.steps)
        if self._cur_start is not None and k - 1 < len(self.durations):
            need = self.durations[k - 1] + 0.5 - (time.perf_counter() - self._cur_start)
            if need > 0:
                yield int(need * 1000)
        self._cur_start = time.perf_counter()
        yield from super().step(caption, sub, narration, hold_ms)

    def until_left(self, seconds):
        """Waits until only `seconds` of the current step's narration remain (an action that matches its last
        sentence, e.g. an undo, then happens while that sentence is spoken)."""
        k = len(self.steps)
        if self._cur_start is not None and 0 < k <= len(self.durations):
            need = self.durations[k - 1] - seconds - (time.perf_counter() - self._cur_start)
            if need > 0:
                yield int(need * 1000)

    def finish(self):
        """Lets the last narration clip finish."""
        k = len(self.steps)
        if self._cur_start is not None and 0 < k <= len(self.durations):
            need = self.durations[k - 1] + 0.8 - (time.perf_counter() - self._cur_start)
            if need > 0:
                yield int(need * 1000)


# --------------------------------------------------------------------------------------------------------------------
# Keeping the recorded window in front (the recorder captures a screen area, not a window)
# --------------------------------------------------------------------------------------------------------------------
def bring_to_front(window, overlay=None):
    """Window always-on-top for the recording, raised and activated; the overlay stays above it."""
    if not (window.windowFlags() & Qt.WindowStaysOnTopHint):
        window.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        window.showMaximized()
    window.raise_()
    window.activateWindow()
    if overlay is not None:
        overlay.raise_()


def window_on_screen(window, min_match=0.85):
    """True when the screen really shows the window: a screen grab of its area is compared with the window's own
    image (small grid of pixels).  False when another program covers it."""
    try:
        scr = window.screen()
        sg = scr.geometry()
        g = window.geometry()
        shot = scr.grabWindow(0, g.x() - sg.x(), g.y() - sg.y(), g.width(), g.height()).toImage()
        own = window.grab().toImage()
        if shot.isNull() or own.isNull():
            return False
        cols, rows = 48, 30
        a = shot.scaled(cols, rows)
        b = own.scaled(cols, rows)
        ok = n = 0
        for yy in range(rows):
            for xx in range(cols):
                ca, cb = a.pixelColor(xx, yy), b.pixelColor(xx, yy)
                n += 1
                if abs(ca.red() - cb.red()) + abs(ca.green() - cb.green()) + abs(ca.blue() - cb.blue()) < 60:
                    ok += 1
        return ok / float(n) >= min_match
    except Exception:
        return False


def keep_display_awake(on):
    """Windows: keep the display and the system awake while recording (as video players do); off restores."""
    try:
        import ctypes
        ES_CONTINUOUS, ES_SYSTEM_REQUIRED, ES_DISPLAY_REQUIRED = 0x80000000, 0x00000001, 0x00000002
        flags = ES_CONTINUOUS | (ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED if on else 0)
        ctypes.windll.kernel32.SetThreadExecutionState(flags)
    except Exception:
        pass


def black_segments(video, min_s=0.1):
    """[(start, end)] of (nearly) black stretches in a video (ffmpeg blackdetect) - a recording check."""
    r = subprocess.run([find_ffmpeg(), "-hide_banner", "-i", video, "-vf", f"blackdetect=d={min_s}:pic_th=0.90",
                        "-an", "-f", "null", "-"], capture_output=True, text=True, errors="replace")
    out = []
    for line in r.stderr.splitlines():
        if "black_start:" in line:
            try:
                a = float(line.split("black_start:")[1].split()[0])
                b = float(line.split("black_end:")[1].split()[0])
                out.append((a, b))
            except Exception:
                pass
    return out
