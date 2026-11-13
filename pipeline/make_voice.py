"""Voice the demo script and write its soundtrack.

By default the voice is Kokoro, an open-weights model that runs on this computer. Point it at a folder of your
own recordings and those are used instead, one file per take, named 01, 02 and so on.

Kokoro needs its own environment, with `pip install kokoro-onnx imageio-ffmpeg`, and the two model files from
https://github.com/thewh1teagle/kokoro-onnx/releases/tag/model-files-v1.0 in one folder.

    python pipeline/make_voice.py --model-dir path/to/models
    python pipeline/make_voice.py --recordings path/to/your/folder

Writes data/local/demo/voice.wav, music.wav and timeline.json, which pipeline/make_demo.py reads.
"""
from __future__ import annotations

import argparse
import functools
import hashlib
import itertools
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys

import numpy as np

from common import ROOT
from demo_script import MOODS, load

OUT = ROOT / "data" / "local" / "demo"
VOICE = "af_heart"
RATE = 24_000
MUSIC_RATE = 48_000
GAP_WEIGHT = 6.0  # how much a long pause counts as the break between two lines
LIMIT_SECONDS = 140  # X's limit for a standard account
AUDIO_TYPES = (".m4a", ".mp3", ".wav", ".ogg", ".opus", ".aac", ".flac", ".webm", ".mp4", ".mov", ".3gp", ".amr")


def ffmpeg() -> str:
    found = os.environ.get("FFMPEG") or shutil.which("ffmpeg")
    if found:
        return found
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def to_wav_bytes(samples: np.ndarray, rate: int) -> bytes:
    """Little-endian 16-bit WAV, mono or (n, 2) stereo."""
    data = np.clip(samples, -1, 1)
    pcm = (data * 32767).astype("<i2")
    channels = 1 if pcm.ndim == 1 else pcm.shape[1]
    raw = pcm.tobytes()
    header = b"RIFF" + (36 + len(raw)).to_bytes(4, "little") + b"WAVEfmt " + (16).to_bytes(4, "little")
    header += (1).to_bytes(2, "little") + channels.to_bytes(2, "little") + rate.to_bytes(4, "little")
    header += (rate * channels * 2).to_bytes(4, "little") + (channels * 2).to_bytes(2, "little") + (16).to_bytes(2, "little")
    return header + b"data" + len(raw).to_bytes(4, "little") + raw


def decode(path: pathlib.Path) -> np.ndarray:
    """Any audio file as mono float samples at RATE."""
    raw = subprocess.run([ffmpeg(), "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(RATE), "-f", "s16le", "-"],
                         check=True, capture_output=True).stdout
    return np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768


def rms_db(samples: np.ndarray) -> float:
    return 20 * np.log10(np.sqrt(np.mean(np.square(samples))) + 1e-9)


def level(samples: np.ndarray, target_db: float) -> np.ndarray:
    """Bring speech to a target level, counting only the parts that are speech."""
    window = RATE // 50
    frames = samples[: len(samples) // window * window].reshape(-1, window)
    energy = np.sqrt(np.mean(np.square(frames), axis=1))
    voiced = frames[energy > max(energy.max() * 0.12, 1e-4)]
    current = rms_db(voiced) if len(voiced) else rms_db(samples)
    return samples * 10 ** ((target_db - current) / 20)


def fade_edges(samples: np.ndarray, ms: float = 12) -> np.ndarray:
    n = min(int(RATE * ms / 1000), len(samples) // 2)
    if n:
        ramp = np.linspace(0, 1, n)
        samples = samples.copy()
        samples[:n] *= ramp
        samples[-n:] *= ramp[::-1]
    return samples


def perform(engine, entry: dict) -> np.ndarray:
    """One line in its mood: speed from the model, pitch by resampling, then level. Kept, so only changed lines are redone."""
    mood = MOODS[entry["mood"]]
    key = hashlib.sha256(json.dumps([VOICE, entry["say"], mood["speed"], mood["pitch"], mood["gain"]]).encode()).hexdigest()[:20]
    cached = OUT / "lines" / f"{key}.npy"
    if cached.exists():
        return np.load(cached)
    lift = 1 + mood["pitch"]
    samples, rate = engine().create(entry["say"], voice=VOICE, speed=float(mood["speed"] / lift), lang="en-us")
    assert rate == RATE
    samples = np.asarray(samples, dtype=np.float32)
    if abs(lift - 1) > 1e-6:  # playing the samples faster raises the pitch, and the speed above made up for it
        positions = np.arange(0, len(samples) - 1, lift)
        samples = np.interp(positions, np.arange(len(samples)), samples).astype(np.float32)
    samples = fade_edges(level(samples, -20 + mood["gain"]))
    cached.parent.mkdir(parents=True, exist_ok=True)
    np.save(cached, samples)
    return samples


def ai_voice(script: list[dict], model_dir: pathlib.Path) -> tuple[list[np.ndarray], list[list[tuple[float, float]]]]:
    """Each take as audio, and the (start, end) of each line within it."""
    @functools.cache
    def engine():
        from kokoro_onnx import Kokoro
        return Kokoro(str(model_dir / "kokoro-v1.0.onnx"), str(model_dir / "voices-v1.0.bin"))
    audio, spans = [], []
    for take in script:
        parts, take_spans, at = [], [], 0.0
        for entry in take["lines"]:
            speech = perform(engine, entry)
            take_spans.append((at, at + len(speech) / RATE))
            at += len(speech) / RATE + entry["pause"]
            parts += [speech, np.zeros(int(entry["pause"] * RATE), dtype=np.float32)]
        audio.append(np.concatenate(parts))
        spans.append(take_spans)
        print(take["name"], f"{at:.1f}s", flush=True)
    return audio, spans


def pauses_in(samples: np.ndarray, min_gap: float = 0.16) -> list[tuple[float, float]]:
    """The stretches of near-silence in a recording, as (start, end) in seconds."""
    window = RATE // 100
    energy = np.sqrt(np.mean(np.square(samples[: len(samples) // window * window].reshape(-1, window)), axis=1))
    quiet = energy < max(np.percentile(energy, 95) * 0.08, 1e-4)
    gaps, begin = [], None
    for i, flag in enumerate(np.append(quiet, False)):
        if flag and begin is None:
            begin = i
        elif not flag and begin is not None:
            if (i - begin) / 100 >= min_gap:
                gaps.append((begin / 100, i / 100))
            begin = None
    return gaps


def place_lines(entries: list[dict], duration: float, gaps: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Where each line falls in a recording: the set of pauses that best fits how long each line should take."""
    lead = gaps[0][1] if gaps and gaps[0][0] <= 0.02 else 0.0
    tail = gaps[-1][0] if gaps and gaps[-1][1] >= duration - 0.02 else duration
    inner = [g for g in gaps if g[0] > lead and g[1] < tail]
    sizes = np.array([len(e["say"]) + 8 for e in entries], dtype=float)  # the spoken words, since a figure takes longer to say than to write
    shares = sizes / sizes.sum()
    need = len(entries) - 1
    if len(inner) < need:  # hardly any pauses, so go by length alone
        edges = lead + np.cumsum(shares)[:-1] * (tail - lead)
        cuts = [(float(x), float(x)) for x in edges]
    else:
        def cost(chosen: tuple) -> float:
            lengths = np.array([b for b, _ in chosen] + [tail]) - np.array([lead] + [a for _, a in chosen])
            speech = tail - lead - sum(a - b for b, a in chosen)
            return float(np.square(lengths - shares * speech).sum() - GAP_WEIGHT * sum((a - b) ** 2 for b, a in chosen))
        cuts = list(min(itertools.combinations(inner, need), key=cost))
    return list(zip([lead] + [a for _, a in cuts], [b for b, _ in cuts] + [tail]))


def trim_silence(samples: np.ndarray, keep: float = 0.15) -> np.ndarray:
    """Cut the dead air a recording has at each end."""
    gaps, length = pauses_in(samples), len(samples) / RATE
    begin = max(gaps[0][1] - keep, 0.0) if gaps and gaps[0][0] <= 0.02 else 0.0
    end = min(gaps[-1][0] + keep, length) if gaps and gaps[-1][1] >= length - 0.02 else length
    return samples[int(begin * RATE): int(end * RATE)]


def human_voice(script: list[dict], folder: pathlib.Path) -> tuple[list[np.ndarray], list[list[tuple[float, float]]]]:
    audio, spans = [], []
    for i, take in enumerate(script, 1):
        found = [p for p in sorted(folder.iterdir()) if re.fullmatch(rf"0*{i}", p.stem) and p.suffix.lower() in AUDIO_TYPES]
        if not found:
            sys.exit(f"No recording for take {i:02d} in {folder}. Name it {i:02d}.m4a, or use another common audio type.")
        samples = trim_silence(decode(found[0]))
        audio.append(np.concatenate([fade_edges(level(samples, -20)), np.zeros(int(0.45 * RATE), dtype=np.float32)]))
        spans.append(place_lines(take["lines"], len(samples) / RATE, pauses_in(samples)))
        print(take["name"], found[0].name, f"{len(samples) / RATE:.1f}s", flush=True)
    return audio, spans


# ---- the music, written here so it belongs to the project -------------------------------------------------
NOTE = {"A2": 110.0, "B2": 123.47, "C3": 130.81, "D3": 146.83, "E3": 164.81, "F3": 174.61, "G3": 196.0, "A3": 220.0,
        "B3": 246.94, "C4": 261.63, "D4": 293.66, "E4": 329.63, "F4": 349.23, "G4": 392.0, "A4": 440.0, "B4": 493.88,
        "C5": 523.25, "D5": 587.33, "E5": 659.25, "G5": 783.99}
F2, G2, C2, D2, E2 = 87.31, 98.0, 65.41, 73.42, 82.41
CHORDS = {
    "Am": (NOTE["A2"], NOTE["E3"], NOTE["C4"], NOTE["E4"]), "F": (F2, NOTE["C3"], NOTE["A3"], NOTE["C4"]),
    "C": (C2 * 2, NOTE["G3"], NOTE["C4"], NOTE["E4"]), "G": (G2, NOTE["D3"], NOTE["B3"], NOTE["D4"]),
    "Dm": (D2 * 2, NOTE["A3"], NOTE["D4"], NOTE["F4"]), "Em": (E2 * 2, NOTE["G3"], NOTE["B3"], NOTE["E4"]),
    "Asus": (NOTE["A2"], NOTE["E3"], NOTE["B3"], NOTE["E4"]), "Cadd": (C2 * 2, NOTE["G3"], NOTE["D4"], NOTE["E4"]),
    "drone": (NOTE["A2"], NOTE["A3"], NOTE["E4"]),
}
# for each take: chords in order, how full the pad is, and whether a soft line of notes runs over it
SCORE = {
    "problem": (["Am", "F", "Am", "Dm"], 0.75, None),
    "solution": (["F", "C", "G"], 0.9, ["C4", "G4", "C5", "G4"]),
    "weigh": (["Asus", "Cadd"], 0.8, ["E4", "B4", "E5", "B4"]),
    "benefit": (["C", "G", "Am", "F"], 0.9, None),
    "honest": (["Dm", "Am"], 0.7, None),
    "maths": (["Am", "F", "C", "G"], 0.85, None),
    "you": (["C", "G", "Am", "F", "C"], 1.0, ["E4", "G4", "C5", "G4"]),
}


def pad(freqs: tuple, seconds: float, rng: np.random.Generator) -> np.ndarray:
    """A soft sustained chord, stereo."""
    n = int(seconds * MUSIC_RATE)
    t = np.arange(n) / MUSIC_RATE
    out = np.zeros((n, 2))
    for f in freqs:
        for side, detune in ((0, 0.998), (1, 1.002)):
            for partial, weight in ((1, 1.0), (2, 0.28), (3, 0.08)):
                out[:, side] += weight * np.sin(2 * np.pi * f * detune * partial * t + rng.uniform(0, 6.28))
    attack = np.minimum(t / 1.4, 1.0) ** 2
    release = np.minimum((seconds - t) / 1.6, 1.0) ** 2
    return out * (attack * release)[:, None] / (len(freqs) * 2.2)


def bell(freq: float, seconds: float = 1.8) -> np.ndarray:
    """A soft struck note, mono."""
    t = np.arange(int(seconds * MUSIC_RATE)) / MUSIC_RATE
    tone = np.sin(2 * np.pi * freq * t) + 0.3 * np.sin(4 * np.pi * freq * t) * np.exp(-t * 3)
    return tone * np.exp(-t * 2.6) * np.minimum(t / 0.008, 1.0)


def add(track: np.ndarray, clip: np.ndarray, at: float, gain: float = 1.0, pan: float = 0.0) -> None:
    start = int(at * MUSIC_RATE)
    if start < 0:
        clip, start = clip[-start:], 0
    if start >= len(track):
        return
    clip = clip[: len(track) - start]
    if clip.ndim == 1:
        clip = np.column_stack([clip * (1 - max(pan, 0)), clip * (1 + min(pan, 0))])
    track[start: start + len(clip)] += clip * gain


def speech_envelope(voice: np.ndarray) -> np.ndarray:
    """1 while someone is speaking, 0 in the gaps, moving smoothly, at the music's sample rate."""
    window = RATE // 100
    energy = np.sqrt(np.mean(np.square(voice[: len(voice) // window * window].reshape(-1, window)), axis=1))
    active = (energy > 0.01).astype(float)
    smooth, value = np.zeros_like(active), 0.0
    for i, flag in enumerate(active):
        value += (flag - value) * (0.28 if flag > value else 0.05)
        smooth[i] = value
    return np.interp(np.arange(int(len(voice) * 2)) / MUSIC_RATE, np.arange(len(smooth)) / 100, smooth)


def find_line(layout: list[dict], mark: str) -> dict:
    return next(entry for slot in layout for entry in slot["lines"] if entry["mark"] == mark)


def compose(script: list[dict], layout: list[dict], voice: np.ndarray) -> np.ndarray:
    total = len(voice) / RATE
    track = np.zeros((int(total * MUSIC_RATE), 2))
    rng = np.random.default_rng(7)
    for take, slot in zip(script, layout):
        chords, fullness, run = SCORE[take["name"]]
        length = slot["end"] - slot["start"]
        step = length / len(chords)
        for i, name in enumerate(chords):
            add(track, pad(CHORDS[name], step + 2.2, rng), slot["start"] + i * step - 0.8, gain=fullness)
        if run:
            beat, at, k = 0.62, slot["start"] + 0.2, 0
            while at < slot["end"] - 0.4:
                add(track, bell(NOTE[run[k % len(run)]]), at, gain=0.13 * fullness, pan=0.35 if k % 2 else -0.35)
                at += beat
                k += 1
    # moments the music has to serve
    automation = [(0.0, 1.0), (total, 1.0)]
    verdict = find_line(layout, "verdict")
    automation += [(verdict["start"] - 1.6, 1.0), (verdict["start"] - 0.5, 0.05), (verdict["end"] + 0.6, 0.05), (verdict["end"] + 2.4, 0.9)]
    result = find_line(layout, "result")
    for f, g in ((NOTE["C4"], 0.3), (NOTE["G4"], 0.24), (NOTE["E5"], 0.2), (NOTE["G5"], 0.14)):
        add(track, bell(f, 3.2), result["start"] - 0.05, gain=g)
    add(track, bell(NOTE["A2"], 3.0), verdict["end"] + 0.15, gain=0.5)
    points = sorted(automation)
    gain = np.interp(np.arange(len(track)) / MUSIC_RATE, [p[0] for p in points], [p[1] for p in points])
    fade = np.minimum((total - np.arange(len(track)) / MUSIC_RATE) / 2.5, 1.0).clip(0, 1) * np.minimum(np.arange(len(track)) / MUSIC_RATE / 1.2, 1.0)
    envelope = speech_envelope(voice)[: len(track)]
    envelope = np.pad(envelope, (0, len(track) - len(envelope)))
    duck = 10 ** (-(envelope * 9) / 20)  # 9 dB lower under speech
    track = track * (gain * fade * duck)[:, None]
    peak = np.abs(track).max() + 1e-9
    return track / peak * 10 ** (-10.5 / 20)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model-dir", type=pathlib.Path, help="folder holding the two Kokoro model files")
    parser.add_argument("--recordings", type=pathlib.Path, help="folder of your own recordings, one per take")
    parser.add_argument("--no-music", action="store_true")
    args = parser.parse_args()
    if bool(args.model_dir) == bool(args.recordings):
        parser.error("give either --model-dir or --recordings")
    script = load()
    audio, spans = human_voice(script, args.recordings) if args.recordings else ai_voice(script, args.model_dir)

    gap = int(0.25 * RATE)
    lead = int(0.5 * RATE)
    pieces, layout, at = [np.zeros(lead, dtype=np.float32)], [], lead / RATE
    for take, samples, take_spans in zip(script, audio, spans):
        lines = [{"mark": e["mark"], "show": e["show"], "start": at + a, "end": at + b} for e, (a, b) in zip(take["lines"], take_spans)]
        layout.append({"name": take["name"], "label": take["label"], "start": at, "end": at + len(samples) / RATE, "lines": lines})
        pieces += [samples, np.zeros(gap, dtype=np.float32)]
        at += (len(samples) + gap) / RATE
    voice = np.concatenate(pieces)

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "voice.wav").write_bytes(to_wav_bytes(voice, RATE))
    music = np.zeros((len(voice) * 2, 2)) if args.no_music else compose(script, layout, voice)
    (OUT / "music.wav").write_bytes(to_wav_bytes(music, MUSIC_RATE))
    timeline = {"duration": len(voice) / RATE, "voice": "human" if args.recordings else f"kokoro:{VOICE}", "takes": layout}
    (OUT / "timeline.json").write_text(json.dumps(timeline, indent=1), encoding="utf-8")
    print(f"{timeline['duration']:.1f} seconds, voice peak {np.abs(voice).max():.2f}")
    if timeline["duration"] > LIMIT_SECONDS:
        print(f"Too long for a standard X account, which allows {LIMIT_SECONDS} seconds. Record the takes a little faster.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
