"""Transcription module using pywhispercpp."""

import sys
from pathlib import Path

from pywhispercpp.model import Model

ENGLISH_MODEL = "ggml-small.en.bin"
MULTILINGUAL_MODEL = "ggml-medium-q5_0.bin"  # 539 MB quantized; see model-choice doc

# Lazy-loaded model instance with tracking
_model: Model | None = None
_current_model_file: str | None = None


def get_model_path(model_file: str = ENGLISH_MODEL) -> Path:
    """Find the model file in various locations."""
    # When running as a PyInstaller bundle
    if getattr(sys, "frozen", False):
        bundle_dir = Path(sys._MEIPASS)
        model_path = bundle_dir / "models" / model_file
        if model_path.exists():
            return model_path

    # When running from source - look in project models folder
    project_models = Path(__file__).parent / "models" / model_file
    if project_models.exists():
        return project_models

    # Fallback to user's local share folder
    local_models = Path.home() / ".local" / "share" / "whisper-dictation" / model_file
    if local_models.exists():
        return local_models

    raise FileNotFoundError(
        f"Model not found: {model_file}. Please run 'make install-model' "
        f"(English) or 'make install-model-multilingual' (Dutch/Auto) "
        f"to download it."
    )


def get_model(language: str = "en") -> Model:
    """Get or create the whisper model instance.

    Loads the English-only model for 'en', or the multilingual model
    for any other language (including 'auto' for auto-detect).
    """
    global _model, _current_model_file
    needed = ENGLISH_MODEL if language == "en" else MULTILINGUAL_MODEL
    if _model is None or _current_model_file != needed:
        model_path = get_model_path(needed)
        _model = Model(str(model_path), print_realtime=False, print_progress=False)
        _current_model_file = needed
    return _model


def transcribe(audio_path: Path, language: str = "en") -> str:
    """Transcribe audio file using whisper.cpp.

    Args:
        audio_path: Path to the WAV file to transcribe
        language: Language code ('en', 'nl', 'auto')

    Returns:
        Transcribed text, stripped of whitespace
    """
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    try:
        model = get_model(language)

        # Build transcription kwargs
        kwargs = {}
        if language and language != "auto":
            kwargs["language"] = language

        segments = model.transcribe(str(audio_path), **kwargs)

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
