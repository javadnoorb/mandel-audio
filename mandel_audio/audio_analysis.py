"""Analyze a music track into per-video-frame features for driving visuals.

This is the reverse of ``mandel_audio.audio`` (which turns a fractal
orbit *into* sound). Here, an existing song is decomposed into signals
that ``mandel_audio.reactive`` uses to drive the fractal's zoom and
color:

- **band energy** (bass/mid/treble) — drives color mix, frame by frame.
- **loudness** (RMS) — drives overall brightness.
- **beat pulses** — short decaying spikes at detected beat times, used
  for zoom accents.

All per-frame arrays are aligned to a target video ``fps`` (via
``hop_length = sr // fps``), so they can be indexed directly by video
frame number.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class AudioFeatures:
    bass: np.ndarray  # normalized [0, 1] low-frequency energy, per frame
    mid: np.ndarray  # normalized [0, 1] mid-frequency energy, per frame
    treble: np.ndarray  # normalized [0, 1] high-frequency energy, per frame
    loudness: np.ndarray  # normalized [0, 1] RMS, per frame
    beat: np.ndarray  # [0, 1] decaying pulse at each detected beat, per frame
    tempo: float  # estimated BPM
    fps: int
    sr: int
    duration: float  # seconds

    @property
    def num_frames(self) -> int:
        return len(self.bass)


def load_audio(path: str, sr: int = 44100) -> tuple[np.ndarray, int]:
    """Load an audio file (wav/mp3/etc.) as mono float32 at ``sr``."""
    import librosa

    y, sr = librosa.load(path, sr=sr, mono=True)
    return y, sr


def _normalize(x: np.ndarray) -> np.ndarray:
    x = x - x.min()
    peak = x.max()
    return x / peak if peak > 0 else x


def analyze(
    y: np.ndarray,
    sr: int,
    fps: int = 24,
    beat_decay_frames: int = 6,
) -> AudioFeatures:
    """Decompose ``y`` into per-video-frame features aligned to ``fps``."""
    import librosa

    hop_length = max(1, sr // fps)

    stft = np.abs(librosa.stft(y, hop_length=hop_length))
    freqs = librosa.fft_frequencies(sr=sr)

    def band_energy(lo: float, hi: float) -> np.ndarray:
        mask = (freqs >= lo) & (freqs < hi)
        if not mask.any():
            return np.zeros(stft.shape[1])
        return stft[mask].mean(axis=0)

    bass_raw = band_energy(20, 250)
    mid_raw = band_energy(250, 4000)
    treble_raw = band_energy(4000, sr / 2)

    # Normalize the three bands *together* (shared scale), not each to
    # its own peak -- otherwise a treble-only signal would still show
    # bass swinging across its full [0, 1] range on pure noise floor,
    # which defeats the point of comparing band energies for coloring.
    shared_peak = max(bass_raw.max(), mid_raw.max(), treble_raw.max())
    if shared_peak > 0:
        bass, mid, treble = bass_raw / shared_peak, mid_raw / shared_peak, treble_raw / shared_peak
    else:
        bass, mid, treble = bass_raw, mid_raw, treble_raw

    rms = librosa.feature.rms(y=y, hop_length=hop_length)[0]
    loudness = _normalize(rms)

    tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr, hop_length=hop_length)
    num_frames = bass.shape[0]
    beat = np.zeros(num_frames)
    for bf in np.atleast_1d(beat_frames):
        bf = int(bf)
        for k in range(beat_decay_frames):
            idx = bf + k
            if idx < num_frames:
                beat[idx] = max(beat[idx], float(np.exp(-k / 2.0)))

    n = min(len(bass), len(mid), len(treble), len(loudness), len(beat))
    return AudioFeatures(
        bass=bass[:n],
        mid=mid[:n],
        treble=treble[:n],
        loudness=loudness[:n],
        beat=beat[:n],
        tempo=float(np.atleast_1d(tempo)[0]),
        fps=fps,
        sr=sr,
        duration=len(y) / sr,
    )


def analyze_file(path: str, fps: int = 24, sr: int = 44100) -> AudioFeatures:
    """Convenience: ``load_audio`` + ``analyze`` in one call."""
    y, sr = load_audio(path, sr=sr)
    return analyze(y, sr, fps=fps)
