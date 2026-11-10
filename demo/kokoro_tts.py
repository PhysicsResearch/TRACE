"""
Kokoro text-to-speech for the demo narration.  Runs in the separate 'kokoro' conda environment (not TRACE's):

    <anaconda>/envs/kokoro/python.exe kokoro_tts.py job.json

job.json: {"texts": [...], "out_dir": "...", "voice": "bf_emma", "speed": 1.0}
Writes clip_00.wav, clip_01.wav ... (24 kHz, 16-bit mono).  Voices starting with 'b' are British English, 'a' American.
"""
import json
import re
import os
import sys

import numpy as np
import soundfile as sf
from kokoro import KPipeline

SR = 24000
# names Kokoro would spell out or misread: Kokoro's inline phoneme override, [word](/phonemes/)
PRONUNCIATIONS = {"KINETIQ": "/kɪnˈɛtɪk/", "DYNAMIQ": "/dInˈamɪk/", "LogIQ": "/lˈɒʤɪk/"}


def _pronounce(text):
    for word, ph in PRONUNCIATIONS.items():
        text = re.sub(rf"(?<![\w\[]){re.escape(word)}(?![\w\]])", f"[{word}]({ph})", text)
    return text


def main(job_path):
    with open(job_path, encoding="utf-8") as f:
        job = json.load(f)
    voice = job.get("voice", "bf_emma")
    speed = float(job.get("speed", 1.0))
    out_dir = job["out_dir"]
    os.makedirs(out_dir, exist_ok=True)
    pipe = KPipeline(lang_code=voice[0], repo_id="hexgrad/Kokoro-82M")
    for i, text in enumerate(job["texts"]):
        parts = [np.asarray(a, dtype=np.float32) for _gs, _ps, a in pipe(_pronounce(text), voice=voice, speed=speed)]
        audio = np.concatenate(parts) if parts else np.zeros(SR // 2, dtype=np.float32)
        sf.write(os.path.join(out_dir, f"clip_{i:02d}.wav"), audio, SR, subtype="PCM_16")
    print("ok", len(job["texts"]), flush=True)


if __name__ == "__main__":
    main(sys.argv[1])
