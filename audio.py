"""Audio capture module using sounddevice."""

import tempfile
import wave
from pathlib import Path

import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16000
CHANNELS = 1
DTYPE = np.int16
RMS_NORMALIZATION_FACTOR = 1000  # Audio level sensitivity for visual feedback


class AudioRecorder:
    """Records audio from the microphone."""

    def __init__(self):
        self._frames: list[np.ndarray] = []
        self._stream: sd.InputStream | None = None
        self._level: float = 0.0  # Current audio level (0.0 to 1.0)

    @property
    def level(self) -> float:
        """Current audio level (0.0 to 1.0)."""
        return self._level

    def start(self) -> None:
        """Start recording audio."""
        self._frames = []
        self._level = 0.0
        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype=DTYPE,
            callback=self._audio_callback,
        )
        self._stream.start()

    def _audio_callback(
        self, indata: np.ndarray, frames: int, time_info: dict, status: sd.CallbackFlags
    ) -> None:
        """Callback for audio stream."""
        self._frames.append(indata.copy())
        # Calculate RMS level normalized to 0.0-1.0
        rms = np.sqrt(np.mean(indata.astype(np.float32) ** 2))
        self._level = min(1.0, rms / RMS_NORMALIZATION_FACTOR)

    def stop(self) -> Path | None:
        """Stop recording and save to a temporary WAV file.

        Returns the path to the temporary file, or None if no audio was recorded.
        """
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

        if not self._frames:
            return None

        audio_data = np.concatenate(self._frames, axis=0)

        # Skip if too short (less than 0.5 seconds)
        if len(audio_data) < SAMPLE_RATE * 0.5:
            return None

        # Don't trim silence - let Whisper handle it
        # This avoids accidentally cutting off speech

        # Save to temporary WAV file
        tmp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        with wave.open(tmp_file.name, "wb") as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(audio_data.tobytes())

        return Path(tmp_file.name)
