import numpy as np
import soundfile as sf

from mandel_audio.audio import compute_orbit, orbit_to_audio, save_wav


def test_orbit_at_origin_never_escapes():
    real, imag, escaped = compute_orbit(0.0, 0.0, 500)
    assert not escaped
    assert len(real) == 500
    np.testing.assert_array_equal(real, 0.0)
    np.testing.assert_array_equal(imag, 0.0)


def test_orbit_of_far_point_escapes_quickly():
    real, imag, escaped = compute_orbit(2.0, 2.0, 500)
    assert escaped
    assert len(real) < 500
    assert len(real) == len(imag)


def test_orbit_to_audio_shape_and_range():
    audio = orbit_to_audio(-0.5, 0.0, duration=0.1, sr=8000, maxiter=200)
    assert audio.shape == (800, 2)
    assert audio.dtype == np.float32
    assert np.all(audio >= -1.0) and np.all(audio <= 1.0)


def test_orbit_to_audio_silent_at_origin():
    # c=0 orbits at exactly 0 forever, so there's nothing to normalize
    # and the buffer should be silent, not NaN/inf from a divide-by-zero.
    audio = orbit_to_audio(0.0, 0.0, duration=0.05, sr=8000, maxiter=100)
    assert np.all(np.isfinite(audio))
    assert np.all(audio == 0.0)


def test_orbit_to_audio_escaping_point_is_not_silent():
    audio = orbit_to_audio(2.0, 2.0, duration=0.1, sr=8000, maxiter=100)
    assert np.max(np.abs(audio)) > 0


def test_save_wav_roundtrip(tmp_path):
    audio = orbit_to_audio(-0.74529, 0.113075, duration=0.2, sr=8000, maxiter=200)
    path = tmp_path / "orbit.wav"
    save_wav(str(path), audio, sr=8000)

    read_back, sr = sf.read(str(path))
    assert sr == 8000
    assert read_back.shape == audio.shape
    np.testing.assert_allclose(read_back, audio, atol=1e-4)
