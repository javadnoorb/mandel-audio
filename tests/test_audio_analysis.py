import numpy as np

from mandel_audio.audio_analysis import analyze


def _tone(freq, sr, duration, amplitude=1.0):
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    return amplitude * np.sin(2 * np.pi * freq * t)


def test_analyze_shapes_and_ranges():
    sr = 22050
    y = np.random.default_rng(0).uniform(-0.5, 0.5, size=sr * 2).astype(np.float32)
    feats = analyze(y, sr, fps=10)

    n = feats.num_frames
    assert n > 0
    for arr in [feats.bass, feats.mid, feats.treble, feats.loudness, feats.beat]:
        assert len(arr) == n
        assert np.all(arr >= 0.0) and np.all(arr <= 1.0 + 1e-6)
    assert abs(feats.duration - 2.0) < 0.05
    assert feats.tempo >= 0


def test_bass_dominant_tone_has_higher_bass_energy():
    sr = 44100
    y = _tone(60.0, sr, 2.0)  # deep bass tone
    feats = analyze(y, sr, fps=10)
    assert feats.bass.mean() > feats.mid.mean()
    assert feats.bass.mean() > feats.treble.mean()


def test_treble_dominant_tone_has_higher_treble_energy():
    sr = 44100
    y = _tone(8000.0, sr, 2.0)  # bright high tone
    feats = analyze(y, sr, fps=10)
    assert feats.treble.mean() > feats.bass.mean()
    assert feats.treble.mean() > feats.mid.mean()


def test_silence_gives_zero_everywhere():
    sr = 22050
    y = np.zeros(sr * 1, dtype=np.float32)
    feats = analyze(y, sr, fps=10)
    assert np.allclose(feats.bass, 0.0)
    assert np.allclose(feats.mid, 0.0)
    assert np.allclose(feats.treble, 0.0)
    assert np.allclose(feats.loudness, 0.0)


def test_rhythmic_clicks_produce_beat_activity():
    # A train of short bursts every 0.5s (~120 BPM) at 4s duration.
    sr = 22050
    duration = 4.0
    y = np.zeros(int(sr * duration), dtype=np.float32)
    click_len = int(sr * 0.03)
    for click_time in np.arange(0, duration, 0.5):
        start = int(click_time * sr)
        y[start : start + click_len] += _tone(150.0, sr, 0.03, amplitude=1.0)
    feats = analyze(y, sr, fps=20)
    assert feats.tempo > 0
    assert feats.beat.max() > 0
