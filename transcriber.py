"""Transcription module using pywhispercpp."""

import logging
import subprocess
import sys
from pathlib import Path

from pywhispercpp.model import Model

log = logging.getLogger(__name__)

ENGLISH_MODEL = "ggml-small.en.bin"
MULTILINGUAL_MODEL = "ggml-medium-q5_0.bin"  # 539 MB quantized; see model-choice doc

MODEL_DIR = Path.home() / ".local" / "share" / "whisper-dictation"
MODEL_URL = "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/{}"

# Auto-detect is constrained to these languages to avoid
# misdetection (e.g. Danish, Romanian for Dutch speakers).
AUTO_DETECT_LANGUAGES = ["en", "nl"]

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
    local_models = MODEL_DIR / model_file
    if local_models.exists():
        return local_models

    raise FileNotFoundError(
        f"Model not found: {model_file}. Download it from the Models menu, or run "
        f"'make install-model' (English) or 'make install-model-multilingual' (Dutch/Auto)."
    )


def model_for_language(language: str) -> str:
    """The English-only model for 'en', the multilingual model otherwise."""
    return ENGLISH_MODEL if language == "en" else MULTILINGUAL_MODEL


def is_model_installed(model_file: str) -> bool:
    """Whether the model file exists in any of the locations get_model_path checks."""
    try:
        get_model_path(model_file)
    except FileNotFoundError:
        return False
    return True


def download_model(model_file: str) -> Path:
    """Download a model into MODEL_DIR and return its path.

    Uses curl, which trusts the macOS system certificates; a bundled Python
    may not. The file only appears under its final name once complete.
    """
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    target = MODEL_DIR / model_file
    partial = target.with_name(model_file + ".part")
    try:
        subprocess.run(
            ["curl", "-fsSL", "--retry", "2", "-o", str(partial), MODEL_URL.format(model_file)],
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        partial.unlink(missing_ok=True)
        raise
    partial.replace(target)
    return target


def get_model(language: str = "en") -> Model:
    """Get or create the whisper model instance.

    Loads the English-only model for 'en', or the multilingual model
    for any other language (including 'auto' for auto-detect).
    """
    global _model, _current_model_file
    needed = model_for_language(language)
    if _model is None or _current_model_file != needed:
        model_path = get_model_path(needed)
        _model = Model(str(model_path), print_realtime=False, print_progress=False)
        _current_model_file = needed
    return _model


def _detect_language(model: Model, audio_path: Path) -> str:
    """Detect language from audio, constrained to AUTO_DETECT_LANGUAGES."""
    (_lang, _prob), all_probs = model.auto_detect_language(str(audio_path))
    filtered = {lang: prob for lang, prob in all_probs.items() if lang in AUTO_DETECT_LANGUAGES}
    chosen = max(filtered, key=filtered.get) if filtered else "en"
    log.debug(
        f"Language detection: whisper picked {_lang} ({_prob:.2f}), "
        f"filtered to {chosen} (en={filtered.get('en', 0):.2f}, nl={filtered.get('nl', 0):.2f})"
    )
    return chosen


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

        # When auto-detecting, first detect language constrained to
        # allowed languages, then transcribe with that language forced.
        if language == "auto":
            language = _detect_language(model, audio_path)

        kwargs = {"translate": False, "language": language}
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
