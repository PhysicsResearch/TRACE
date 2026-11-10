"""
Videos for the LogIQ website: copies the recordings as fast-start MP4s, a poster frame each, WebVTT subtitles of the
narration (timed by the recorded steps) and a chapters JSON (step titles + start times).

    python demo/site_videos.py [site_dir]          default site_dir: C:\\LogIQ_site
"""
import json
import os
import re
import subprocess
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, r"C:\TRACE")
sys.path.insert(0, r"C:\TRACE\demo")
SITE = sys.argv[1] if len(sys.argv) > 1 else r"C:\LogIQ_site"
SRC = r"C:\TRACE\demo\output"
FF = os.environ.get("TRACE_DEMO_FFMPEG", "ffmpeg")
VID = os.path.join(SITE, "public", "videos")
DATA = os.path.join(SITE, "src", "data")
os.makedirs(VID, exist_ok=True)
os.makedirs(DATA, exist_ok=True)

import demo_planning as DP
import demo_control as DC
import demo_intro as DI
import demo_logs as DL

DL_STEPS = [(c, sub, DL.narration(i)) for i, (c, sub, _n) in enumerate(DL.STEPS)]     # numbers filled in

VIDEOS = [
    # id, source tag, steps, title, poster time (s)
    ("planning-dynamiq", "planning_1_dynamiq", DP.STEPS_1, "Planning part 1 - DYNAMIQ: a smooth motion plan", 150.0),
    ("planning-kinetiq", "planning_1_kinetiq", DP.STEPS_3, "Planning part 1 - KINETIQ: Roll around a central position", 185.0),
    ("planning-events", "planning_2", DP.STEPS_2, "Planning part 2 - Pauses and triggers", 75.0),
    ("intro-workflow", "intro_workflow", DI.STEPS, "Overview - The workflow, end to end with KINETIQ", 222.0),
    ("control-kinetiq", "control_kinetiq", DC.STEPS, "Control tab - KINETIQ: connect, home and move", 168.0),
    ("logs-analysis", "logs_analysis", DL_STEPS, "Log files tab - three runs compared with the plan", 236.0),
]


def srt_times(path):
    """[(start, end)] of the step captions."""
    txt = open(path, encoding="utf-8").read()
    out = []
    for m in re.finditer(r"(\d+):(\d+):(\d+),(\d+) --> (\d+):(\d+):(\d+),(\d+)", txt):
        g = [int(x) for x in m.groups()]
        out.append((g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000, g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000))
    return out


def duration(path):
    r = subprocess.run([FF, "-hide_banner", "-i", path], capture_output=True, text=True)
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", r.stderr)
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else 0.0


def ts(x):
    ms = int(round(x * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d}.{ms % 1000:03d}"


def sentences(text):
    parts = re.split(r"(?<=[.!?:])\s+", text.strip())
    out, cur = [], ""
    for p in parts:                       # cues of about 60 to 110 characters
        cur = (cur + " " + p).strip() if cur else p
        if len(cur) >= 60:
            out.append(cur)
            cur = ""
    if cur:
        out.append(cur)
    return out


catalog = []
for vid, tag, steps, title, poster_t in VIDEOS:
    src = os.path.join(SRC, tag + ".mp4")
    dst = os.path.join(VID, vid + ".mp4")
    subprocess.run([FF, "-loglevel", "error", "-y", "-i", src, "-c", "copy", "-movflags", "+faststart", dst], check=True)
    subprocess.run([FF, "-loglevel", "error", "-y", "-ss", str(poster_t), "-i", src, "-frames:v", "1", "-q:v", "3",
                    os.path.join(VID, vid + ".jpg")], check=True)
    total = duration(dst)
    times = srt_times(os.path.join(SRC, tag + ".srt"))
    assert len(times) == len(steps), (vid, len(times), len(steps))
    # narration cues: each step's text spread over the time until the next step (by length)
    lines = ["WEBVTT", ""]
    n = 1
    chapters = []
    for i, ((cap, sub, narration), (t0, _t1)) in enumerate(zip(steps, times)):
        t_next = times[i + 1][0] if i + 1 < len(times) else total
        chapters.append({"t": round(t0, 1), "title": cap, "sub": sub})
        cues = sentences(narration)
        span = max(0.5, t_next - t0 - 0.2)
        total_chars = sum(len(c) for c in cues) or 1
        t = t0
        for c in cues:
            dt = span * len(c) / total_chars
            lines += [str(n), f"{ts(t)} --> {ts(t + dt - 0.05)}", c, ""]
            n += 1
            t += dt
    with open(os.path.join(VID, vid + ".vtt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    catalog.append({"id": vid, "title": title, "src": f"/videos/{vid}.mp4", "poster": f"/videos/{vid}.jpg",
                    "captions": f"/videos/{vid}.vtt", "duration": round(total, 1), "chapters": chapters,
                    "size_mb": round(os.path.getsize(dst) / 1e6, 1)})
    print(vid, round(total, 1), "s", len(chapters), "chapters", catalog[-1]["size_mb"], "MB", flush=True)

with open(os.path.join(DATA, "videos.generated.json"), "w", encoding="utf-8") as f:
    json.dump(catalog, f, indent=2, ensure_ascii=False)
print("wrote", os.path.join(DATA, "videos.generated.json"))
