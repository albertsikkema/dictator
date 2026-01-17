"""Transcription module using pywhispercpp."""

import sys
from pathlib import Path

from pywhispercpp.model import Model

MODEL_FILE = "ggml-small.en.bin"

# Lazy-loaded model instance
_model: Model | None = None


def get_model_path() -> Path:
    """Find the model file in various locations."""
    # When running as a PyInstaller bundle
    if getattr(sys, "frozen", False):
        # Look in the app bundle's models folder
        bundle_dir = Path(sys._MEIPASS)
        model_path = bundle_dir / "models" / MODEL_FILE
        if model_path.exists():
            return model_path

    # When running from source - look in project models folder
    project_models = Path(__file__).parent / "models" / MODEL_FILE
    if project_models.exists():
        return project_models

    # Fallback to user's local share folder
    local_models = Path.home() / ".local" / "share" / "whisper-dictation" / MODEL_FILE
    if local_models.exists():
        return local_models

    raise FileNotFoundError(
        f"Model not found. Please run 'make install-model' or place "
        f"{MODEL_FILE} in the models folder."
    )


def get_model() -> Model:
    """Get or create the whisper model instance."""
    global _model
    if _model is None:
        model_path = get_model_path()
        _model = Model(str(model_path), print_realtime=False, print_progress=False)
    return _model


def transcribe(audio_path: Path) -> str:
    """Transcribe audio file using whisper.cpp.

    Args:
        audio_path: Path to the WAV file to transcribe

    Returns:
        Transcribed text, stripped of whitespace
    """
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    try:
        model = get_model()
        segments = model.transcribe(str(audio_path))

        # Combine all segment texts
        text_parts = [segment.text for segment in segments]
        result = " ".join(text_parts).strip()

        # Filter out Whisper's blank audio marker
        if result in ("[BLANK_AUDIO]", "[BLANK AUDIO]", "(BLANK_AUDIO)", "(BLANK AUDIO)"):
            return ""

        return result

    finally:
        # Clean up temporary audio file
        try:
            audio_path.unlink()
        except OSError:
            pass
