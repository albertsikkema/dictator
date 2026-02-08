"""Tests for transcriber module."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _mock_pywhispercpp():
    """Mock pywhispercpp for all tests in this module."""
    mock = MagicMock()
    mock_model_module = MagicMock()
    with patch.dict(
        sys.modules,
        {
            "pywhispercpp": mock,
            "pywhispercpp.model": mock_model_module,
        },
    ):
        if "transcriber" in sys.modules:
            del sys.modules["transcriber"]
        yield mock_model_module
    if "transcriber" in sys.modules:
        del sys.modules["transcriber"]


def _import_transcriber():
    """Import transcriber module with mocked pywhispercpp."""
    import transcriber

    return transcriber


@pytest.fixture
def reset_transcriber_globals():
    """Reset transcriber module globals before each test."""
    transcriber = _import_transcriber()
    transcriber._model = None
    transcriber._current_model_file = None
    yield transcriber
    transcriber._model = None
    transcriber._current_model_file = None


# --- get_model_path tests ---


def test_get_model_path_project_models(tmp_path, reset_transcriber_globals):
    """Verify model found in project models directory."""
    transcriber = reset_transcriber_globals
    model_dir = tmp_path / "models"
    model_dir.mkdir()
    model_file = model_dir / transcriber.ENGLISH_MODEL
    model_file.write_text("fake model")

    with patch.object(Path, "parent", new=tmp_path):
        # Patch __file__ location
        with patch.object(transcriber, "__file__", str(tmp_path / "transcriber.py")):
            result = transcriber.get_model_path(transcriber.ENGLISH_MODEL)
            assert result == model_file


def test_get_model_path_local_share(tmp_path, reset_transcriber_globals):
    """Verify model found in ~/.local/share fallback."""
    transcriber = reset_transcriber_globals
    local_dir = tmp_path / ".local" / "share" / "whisper-dictation"
    local_dir.mkdir(parents=True)
    model_file = local_dir / transcriber.ENGLISH_MODEL
    model_file.write_text("fake model")

    with (
        patch.object(transcriber, "__file__", str(tmp_path / "nonexistent" / "transcriber.py")),
        patch.object(Path, "home", return_value=tmp_path),
    ):
        result = transcriber.get_model_path(transcriber.ENGLISH_MODEL)
        assert result == model_file


def test_get_model_path_not_found(tmp_path, reset_transcriber_globals):
    """Verify FileNotFoundError when model not found anywhere."""
    transcriber = reset_transcriber_globals
    with (
        patch.object(transcriber, "__file__", str(tmp_path / "nonexistent" / "transcriber.py")),
        patch.object(Path, "home", return_value=tmp_path),
    ):
        with pytest.raises(FileNotFoundError, match="Model not found"):
            transcriber.get_model_path(transcriber.ENGLISH_MODEL)


def test_get_model_path_frozen(tmp_path, reset_transcriber_globals):
    """Verify model found when running as PyInstaller bundle."""
    transcriber = reset_transcriber_globals
    bundle_dir = tmp_path / "bundle"
    model_dir = bundle_dir / "models"
    model_dir.mkdir(parents=True)
    model_file = model_dir / transcriber.ENGLISH_MODEL
    model_file.write_text("fake model")

    with (
        patch.object(sys, "frozen", True, create=True),
        patch.object(sys, "_MEIPASS", str(bundle_dir), create=True),
    ):
        result = transcriber.get_model_path(transcriber.ENGLISH_MODEL)
        assert result == model_file


# --- get_model tests ---


def test_get_model_english(reset_transcriber_globals, _mock_pywhispercpp):
    """Verify English model loaded for language='en'."""
    transcriber = reset_transcriber_globals
    mock_model = MagicMock()
    _mock_pywhispercpp.Model.return_value = mock_model

    with patch.object(
        transcriber, "get_model_path", return_value=Path("/fake/model.bin")
    ) as mock_gmp:
        result = transcriber.get_model(language="en")
        mock_gmp.assert_called_with(transcriber.ENGLISH_MODEL)

    assert result == mock_model


def test_get_model_multilingual(reset_transcriber_globals, _mock_pywhispercpp):
    """Verify multilingual model loaded for non-English languages."""
    transcriber = reset_transcriber_globals
    mock_model = MagicMock()
    _mock_pywhispercpp.Model.return_value = mock_model

    with patch.object(
        transcriber, "get_model_path", return_value=Path("/fake/model.bin")
    ) as mock_gmp:
        result = transcriber.get_model(language="nl")
        mock_gmp.assert_called_with(transcriber.MULTILINGUAL_MODEL)

    assert result == mock_model


def test_get_model_caching(reset_transcriber_globals, _mock_pywhispercpp):
    """Verify Model() is only called once for same language."""
    transcriber = reset_transcriber_globals
    mock_model = MagicMock()
    _mock_pywhispercpp.Model.return_value = mock_model

    with patch.object(transcriber, "get_model_path", return_value=Path("/fake/model.bin")):
        result1 = transcriber.get_model(language="en")
        result2 = transcriber.get_model(language="en")

    assert result1 is result2
    assert _mock_pywhispercpp.Model.call_count == 1


def test_get_model_switches_on_language_change(reset_transcriber_globals, _mock_pywhispercpp):
    """Verify model reloaded when switching languages."""
    transcriber = reset_transcriber_globals
    _mock_pywhispercpp.Model.side_effect = [MagicMock(), MagicMock()]

    with patch.object(transcriber, "get_model_path", return_value=Path("/fake/model.bin")):
        result1 = transcriber.get_model(language="en")
        result2 = transcriber.get_model(language="nl")

    assert result1 is not result2
    assert _mock_pywhispercpp.Model.call_count == 2


# --- _detect_language tests ---


def test_detect_language_picks_highest(reset_transcriber_globals):
    """Verify highest-probability supported language is chosen."""
    transcriber = reset_transcriber_globals
    mock_model = MagicMock()
    mock_model.auto_detect_language.return_value = (
        ("en", 0.8),
        {"en": 0.8, "nl": 0.2},
    )
    result = transcriber._detect_language(mock_model, Path("/fake/audio.wav"))
    assert result == "en"


def test_detect_language_filters_unsupported(reset_transcriber_globals):
    """Verify unsupported languages are filtered out."""
    transcriber = reset_transcriber_globals
    mock_model = MagicMock()
    mock_model.auto_detect_language.return_value = (
        ("da", 0.9),
        {"da": 0.9, "en": 0.05, "nl": 0.05},
    )
    result = transcriber._detect_language(mock_model, Path("/fake/audio.wav"))
    assert result in ("en", "nl")


def test_detect_language_empty_filtered(reset_transcriber_globals):
    """Verify defaults to 'en' when all languages are unsupported."""
    transcriber = reset_transcriber_globals
    mock_model = MagicMock()
    mock_model.auto_detect_language.return_value = (
        ("da", 0.9),
        {"da": 0.9, "sv": 0.05, "fi": 0.05},
    )
    result = transcriber._detect_language(mock_model, Path("/fake/audio.wav"))
    assert result == "en"


# --- transcribe tests ---


def test_transcribe_success(tmp_path, reset_transcriber_globals):
    """Verify transcription returns joined segment text."""
    transcriber = reset_transcriber_globals
    audio_file = tmp_path / "test.wav"
    audio_file.write_text("fake audio")

    mock_model = MagicMock()
    seg1, seg2 = MagicMock(), MagicMock()
    seg1.text = "Hello"
    seg2.text = "world"
    mock_model.transcribe.return_value = [seg1, seg2]

    with patch.object(transcriber, "get_model", return_value=mock_model):
        result = transcriber.transcribe(audio_file, language="en")

    assert result == "Hello world"


def test_transcribe_auto_detect(tmp_path, reset_transcriber_globals):
    """Verify _detect_language is called for language='auto'."""
    transcriber = reset_transcriber_globals
    audio_file = tmp_path / "test.wav"
    audio_file.write_text("fake audio")

    mock_model = MagicMock()
    mock_model.transcribe.return_value = []

    with (
        patch.object(transcriber, "get_model", return_value=mock_model),
        patch.object(transcriber, "_detect_language", return_value="en") as mock_detect,
    ):
        transcriber.transcribe(audio_file, language="auto")

    mock_detect.assert_called_once_with(mock_model, audio_file)


@pytest.mark.parametrize(
    "blank_marker",
    ["[BLANK_AUDIO]", "[BLANK AUDIO]", "(BLANK_AUDIO)", "(BLANK AUDIO)"],
)
def test_transcribe_blank_audio_markers(tmp_path, reset_transcriber_globals, blank_marker):
    """Verify blank audio markers return empty string."""
    transcriber = reset_transcriber_globals
    audio_file = tmp_path / "test.wav"
    audio_file.write_text("fake audio")

    mock_model = MagicMock()
    seg = MagicMock()
    seg.text = blank_marker
    mock_model.transcribe.return_value = [seg]

    with patch.object(transcriber, "get_model", return_value=mock_model):
        result = transcriber.transcribe(audio_file, language="en")

    assert result == ""


def test_transcribe_file_not_found(reset_transcriber_globals):
    """Verify FileNotFoundError for non-existent path."""
    transcriber = reset_transcriber_globals
    with pytest.raises(FileNotFoundError, match="Audio file not found"):
        transcriber.transcribe(Path("/nonexistent/audio.wav"), language="en")


def test_transcribe_cleans_up_audio_file(tmp_path, reset_transcriber_globals):
    """Verify audio file is deleted after transcription."""
    transcriber = reset_transcriber_globals
    audio_file = tmp_path / "test.wav"
    audio_file.write_text("fake audio")

    mock_model = MagicMock()
    mock_model.transcribe.return_value = []

    with patch.object(transcriber, "get_model", return_value=mock_model):
        transcriber.transcribe(audio_file, language="en")

    assert not audio_file.exists()


def test_transcribe_cleanup_on_error(tmp_path, reset_transcriber_globals):
    """Verify cleanup happens even when transcription raises."""
    transcriber = reset_transcriber_globals
    audio_file = tmp_path / "test.wav"
    audio_file.write_text("fake audio")

    mock_model = MagicMock()
    mock_model.transcribe.side_effect = RuntimeError("boom")

    with (
        patch.object(transcriber, "get_model", return_value=mock_model),
        pytest.raises(RuntimeError, match="boom"),
    ):
        transcriber.transcribe(audio_file, language="en")

    assert not audio_file.exists()
