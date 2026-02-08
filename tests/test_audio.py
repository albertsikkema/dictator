"""Tests for audio module."""

import sys
import wave
from unittest.mock import MagicMock, patch

import numpy as np
import pytest


@pytest.fixture(autouse=True)
def _mock_sounddevice():
    """Mock sounddevice for all tests in this module."""
    mock_sd = MagicMock()
    with patch.dict(sys.modules, {"sounddevice": mock_sd}):
        # Force reimport to pick up mock
        if "audio" in sys.modules:
            del sys.modules["audio"]
        yield mock_sd
    # Clean up
    if "audio" in sys.modules:
        del sys.modules["audio"]


def _import_audio():
    """Import audio module with mocked sounddevice."""
    import audio

    return audio


def test_init_state():
    """Verify initial state of AudioRecorder."""
    audio = _import_audio()
    recorder = audio.AudioRecorder()
    assert recorder._frames == []
    assert recorder._stream is None
    assert recorder._level == 0.0


def test_level_property():
    """Verify level property returns _level."""
    audio = _import_audio()
    recorder = audio.AudioRecorder()
    recorder._level = 0.75
    assert recorder.level == 0.75


def test_start_creates_stream(_mock_sounddevice):
    """Verify start() creates and starts a stream."""
    audio = _import_audio()
    recorder = audio.AudioRecorder()
    recorder.start()

    _mock_sounddevice.InputStream.assert_called_once_with(
        samplerate=audio.SAMPLE_RATE,
        channels=audio.CHANNELS,
        dtype=audio.DTYPE,
        callback=recorder._audio_callback,
    )
    _mock_sounddevice.InputStream.return_value.start.assert_called_once()


def test_audio_callback_stores_frame():
    """Verify _audio_callback appends frame data."""
    audio = _import_audio()
    recorder = audio.AudioRecorder()
    data = np.array([[100], [200], [300]], dtype=np.int16)
    recorder._audio_callback(data, 3, {}, MagicMock())
    assert len(recorder._frames) == 1
    np.testing.assert_array_equal(recorder._frames[0], data)


def test_audio_callback_calculates_level():
    """Verify _audio_callback calculates RMS level correctly."""
    audio = _import_audio()
    recorder = audio.AudioRecorder()
    data = np.array([[500], [500], [500]], dtype=np.int16)
    recorder._audio_callback(data, 3, {}, MagicMock())
    expected_rms = np.sqrt(np.mean(data.astype(np.float32) ** 2))
    expected_level = min(1.0, expected_rms / audio.RMS_NORMALIZATION_FACTOR)
    assert abs(recorder._level - expected_level) < 1e-6


def test_audio_callback_level_capped_at_1():
    """Verify level is capped at 1.0 for very loud audio."""
    audio = _import_audio()
    recorder = audio.AudioRecorder()
    # Very large values to exceed RMS_NORMALIZATION_FACTOR
    data = np.array([[30000], [30000], [30000]], dtype=np.int16)
    recorder._audio_callback(data, 3, {}, MagicMock())
    assert recorder._level <= 1.0


def test_stop_no_frames_returns_none():
    """Verify stop() returns None with no frames recorded."""
    audio = _import_audio()
    recorder = audio.AudioRecorder()
    result = recorder.stop()
    assert result is None


def test_stop_short_audio_returns_none():
    """Verify stop() returns None for audio shorter than 0.5s."""
    audio = _import_audio()
    recorder = audio.AudioRecorder()
    # Add frames totaling less than 0.5 seconds (SAMPLE_RATE * 0.5 = 8000 samples)
    short_data = np.zeros((100, 1), dtype=np.int16)
    recorder._frames.append(short_data)
    result = recorder.stop()
    assert result is None


def test_stop_returns_wav_path():
    """Verify stop() returns a Path to a WAV file for sufficient audio."""
    audio = _import_audio()
    recorder = audio.AudioRecorder()
    # Add enough frames (>= 0.5s = 8000 samples at 16kHz)
    long_data = np.zeros((16000, 1), dtype=np.int16)
    recorder._frames.append(long_data)
    result = recorder.stop()
    assert result is not None
    assert result.suffix == ".wav"
    assert result.exists()
    # Clean up
    result.unlink()


def test_stop_wav_file_properties():
    """Verify the WAV file has correct properties."""
    audio = _import_audio()
    recorder = audio.AudioRecorder()
    long_data = np.zeros((16000, 1), dtype=np.int16)
    recorder._frames.append(long_data)
    result = recorder.stop()

    with wave.open(str(result), "rb") as wf:
        assert wf.getnchannels() == audio.CHANNELS
        assert wf.getsampwidth() == 2  # 16-bit
        assert wf.getframerate() == audio.SAMPLE_RATE

    result.unlink()


def test_stop_closes_stream():
    """Verify stop() stops and closes the stream."""
    audio = _import_audio()
    recorder = audio.AudioRecorder()
    mock_stream = MagicMock()
    recorder._stream = mock_stream
    recorder.stop()
    mock_stream.stop.assert_called_once()
    mock_stream.close.assert_called_once()


def test_stop_resets_stream_to_none():
    """Verify _stream is None after stop()."""
    audio = _import_audio()
    recorder = audio.AudioRecorder()
    recorder._stream = MagicMock()
    recorder.stop()
    assert recorder._stream is None
