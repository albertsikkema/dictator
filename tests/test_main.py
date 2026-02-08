"""Tests for main module (DictatorApp, load_config, save_config)."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Module-level mocking: mock macOS modules ONCE before importing main
# ---------------------------------------------------------------------------

_mock_rumps = MagicMock()
_mock_rumps.App = type(
    "MockApp",
    (),
    {
        "__init__": lambda self, *a, **kw: None,
        "menu": MagicMock(),
        "icon": None,
    },
)
# rumps.MenuItem must be a callable that returns MagicMock instances.
# Using MagicMock (the class) directly would pass the first arg as `spec`,
# constraining the mock's attributes to those of a string.
_mock_rumps.MenuItem = MagicMock()
_mock_rumps.separator = MagicMock()

_mock_pynput = MagicMock()
_mock_pynput_keyboard = MagicMock()

# Install mocks before importing main (must also mock transitive deps)
sys.modules["rumps"] = _mock_rumps
sys.modules["pynput"] = _mock_pynput
sys.modules["pynput.keyboard"] = _mock_pynput_keyboard
sys.modules.setdefault("sounddevice", MagicMock())
sys.modules.setdefault("pywhispercpp", MagicMock())
sys.modules.setdefault("pywhispercpp.model", MagicMock())

import main  # noqa: E402

# Restore references for the test module
_original_config_dir = main.CONFIG_DIR
_original_config_file = main.CONFIG_FILE
_original_icons_dir = main.ICONS_DIR
_original_launch_agent_dir = main.LAUNCH_AGENT_DIR
_original_launch_agent_file = main.LAUNCH_AGENT_FILE
_original_key = main.Key
_original_hotkey_options = main.HOTKEY_OPTIONS


# ---------------------------------------------------------------------------
# DictatorApp fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def app(tmp_path):
    """Create a DictatorApp with all dependencies mocked."""
    # Reset rumps mock call state
    _mock_rumps.reset_mock()
    _mock_pynput_keyboard.reset_mock()

    # Redirect config to tmp_path
    main.CONFIG_DIR = tmp_path / "config"
    main.CONFIG_FILE = main.CONFIG_DIR / "config.json"
    main.LAUNCH_AGENT_DIR = tmp_path / "LaunchAgents"
    main.LAUNCH_AGENT_FILE = main.LAUNCH_AGENT_DIR / "com.dictator.app.plist"

    # Redirect icons to tmp_path and create dummy icons
    icons_dir = tmp_path / "icons"
    icons_dir.mkdir()
    for name in ["ready.png", "transcribing.png"] + [f"recording_{i}.png" for i in range(6)]:
        (icons_dir / name).write_bytes(b"fake png")
    main.ICONS_DIR = icons_dir

    # Set up Key mock attributes
    main.Key = MagicMock()
    main.Key.alt_r = "alt_r"
    main.Key.alt_gr = "alt_gr"
    main.Key.cmd_r = "cmd_r"
    main.Key.alt_l = "alt_l"
    main.Key.cmd_l = "cmd_l"
    main.Key.ctrl_l = "ctrl_l"
    main.Key.ctrl_r = "ctrl_r"
    main.Key.shift_l = "shift_l"
    main.Key.shift_r = "shift_r"
    main.Key.cmd = "cmd"

    # Rebuild HOTKEY_OPTIONS with mock keys
    main.HOTKEY_OPTIONS = {
        "Right Option": (main.Key.alt_r, {main.Key.alt_r, main.Key.alt_gr}, 61),
        "Right Command": (main.Key.cmd_r, {main.Key.cmd_r}, 54),
        "Left Option": (main.Key.alt_l, {main.Key.alt_l}, 58),
        "Left Command": (main.Key.cmd_l, {main.Key.cmd_l}, 55),
    }

    # Patch generate_icons to no-op
    mock_recorder = MagicMock()
    mock_recorder.level = 0.0

    mock_listener = MagicMock()
    _mock_pynput_keyboard.Listener.return_value = mock_listener

    with (
        patch.object(main, "_generate_icons"),
        patch.object(main, "AudioRecorder", return_value=mock_recorder),
        patch.object(main.threading, "Thread", return_value=MagicMock()),
    ):
        main.keyboard = _mock_pynput_keyboard
        main.KeyboardController = MagicMock
        app_instance = main.DictatorApp()

    app_instance._mock_rumps = _mock_rumps
    app_instance._mock_recorder = mock_recorder
    app_instance._mock_listener = mock_listener
    app_instance._mock_pynput_keyboard = _mock_pynput_keyboard

    yield app_instance

    # Restore module-level state
    main.CONFIG_DIR = _original_config_dir
    main.CONFIG_FILE = _original_config_file
    main.ICONS_DIR = _original_icons_dir
    main.LAUNCH_AGENT_DIR = _original_launch_agent_dir
    main.LAUNCH_AGENT_FILE = _original_launch_agent_file
    main.Key = _original_key
    main.HOTKEY_OPTIONS = _original_hotkey_options


# ---------------------------------------------------------------------------
# load_config / save_config tests
# ---------------------------------------------------------------------------


class TestLoadConfig:
    def test_load_config_default(self, tmp_path, monkeypatch):
        """No config file exists — returns default dict."""
        monkeypatch.setattr(main, "CONFIG_FILE", tmp_path / "nonexistent" / "config.json")
        result = main.load_config()
        assert result == {"hotkey": "Right Option", "auto_start": False, "language": "Auto-detect"}

    def test_load_config_existing(self, tmp_path, monkeypatch):
        """Config file exists — returns its contents."""
        config_file = tmp_path / "config.json"
        config = {"hotkey": "Left Option", "auto_start": True, "language": "Dutch"}
        config_file.write_text(json.dumps(config))
        monkeypatch.setattr(main, "CONFIG_FILE", config_file)
        result = main.load_config()
        assert result == config

    def test_load_config_corrupt_json(self, tmp_path, monkeypatch):
        """Corrupt JSON — returns defaults and logs warning."""
        config_file = tmp_path / "config.json"
        config_file.write_text("{invalid json")
        monkeypatch.setattr(main, "CONFIG_FILE", config_file)
        result = main.load_config()
        assert result == {"hotkey": "Right Option", "auto_start": False, "language": "Auto-detect"}


class TestSaveConfig:
    def test_save_config(self, tmp_path, monkeypatch):
        """Verify config is written correctly."""
        config_dir = tmp_path / "config"
        config_file = config_dir / "config.json"
        monkeypatch.setattr(main, "CONFIG_DIR", config_dir)
        monkeypatch.setattr(main, "CONFIG_FILE", config_file)
        config = {"hotkey": "Right Option", "auto_start": False}
        main.save_config(config)
        assert json.loads(config_file.read_text()) == config

    def test_save_config_creates_directory(self, tmp_path, monkeypatch):
        """Verify CONFIG_DIR is created."""
        config_dir = tmp_path / "newdir"
        config_file = config_dir / "config.json"
        monkeypatch.setattr(main, "CONFIG_DIR", config_dir)
        monkeypatch.setattr(main, "CONFIG_FILE", config_file)
        main.save_config({"test": True})
        assert config_dir.exists()


# ---------------------------------------------------------------------------
# DictatorApp.__init__ tests
# ---------------------------------------------------------------------------


class TestDictatorAppInit:
    def test_init_loads_config(self, app):
        """Verify config is loaded."""
        assert isinstance(app.config, dict)
        assert "hotkey" in app.config

    def test_init_creates_recorder(self, app):
        """Verify AudioRecorder is created."""
        assert app.recorder is app._mock_recorder

    def test_init_starts_listener(self, app):
        """Verify hotkey listener is started."""
        assert app.listener is not None


# ---------------------------------------------------------------------------
# is_hotkey tests
# ---------------------------------------------------------------------------


class TestIsHotkey:
    def test_is_hotkey_matching_key(self, app):
        """Matching key returns True."""
        _, key_enums, _ = main.HOTKEY_OPTIONS[app.config["hotkey"]]
        matching_key = next(iter(key_enums))
        assert app.is_hotkey(matching_key) is True

    def test_is_hotkey_non_matching(self, app):
        """Non-matching key returns False."""
        fake_key = MagicMock(spec=[])  # No vk attribute
        assert app.is_hotkey(fake_key) is False

    def test_is_hotkey_vk_fallback(self, app):
        """Key with matching vk attribute returns True."""
        _, _, vk_code = main.HOTKEY_OPTIONS[app.config["hotkey"]]
        fake_key = MagicMock()
        fake_key.vk = vk_code
        assert app.is_hotkey(fake_key) is True


# ---------------------------------------------------------------------------
# update_status tests
# ---------------------------------------------------------------------------


class TestUpdateStatus:
    def test_update_status_ready(self, app):
        """Verify status text and icon for ready."""
        app.update_status("ready")
        assert "Ready" in app.status_item.title
        assert "ready.png" in str(app.icon)

    def test_update_status_listening(self, app):
        """Verify status text for listening."""
        app.update_status("listening")
        assert "Listening" in app.status_item.title

    def test_update_status_transcribing(self, app):
        """Verify status text and icon for transcribing."""
        app.update_status("transcribing")
        assert "Transcribing" in app.status_item.title
        assert "transcribing.png" in str(app.icon)


# ---------------------------------------------------------------------------
# update_icon_level tests
# ---------------------------------------------------------------------------


class TestUpdateIconLevel:
    def test_update_icon_level_zero(self, app):
        """Level 0 maps to recording_0.png."""
        app.update_icon_level(0)
        assert "recording_0.png" in str(app.icon)

    def test_update_icon_level_max(self, app):
        """Level 1.0 maps to recording_5.png."""
        app.update_icon_level(1.0)
        assert "recording_5.png" in str(app.icon)

    def test_update_icon_level_mid(self, app):
        """Level 0.5 maps to recording_3.png."""
        app.update_icon_level(0.5)
        assert "recording_3.png" in str(app.icon)


# ---------------------------------------------------------------------------
# cycle_language tests
# ---------------------------------------------------------------------------


class TestCycleLanguage:
    def test_cycle_language_advances(self, app):
        """English → Dutch → Auto-detect → English."""
        names = list(main.LANGUAGE_OPTIONS.keys())

        app.config["language"] = names[0]  # English
        app.cycle_language()
        assert app.config["language"] == names[1]  # Dutch

        app.cycle_language()
        assert app.config["language"] == names[2]  # Auto-detect

        app.cycle_language()
        assert app.config["language"] == names[0]  # English

    def test_cycle_language_saves_config(self, app):
        """Verify config is saved after cycling."""
        with patch.object(main, "save_config") as mock_save:
            app.cycle_language()
        mock_save.assert_called_once()

    def test_cycle_language_sends_notification(self, app):
        """Verify rumps.notification is called."""
        _mock_rumps.notification.reset_mock()
        app.cycle_language()
        _mock_rumps.notification.assert_called()


# ---------------------------------------------------------------------------
# change_hotkey tests
# ---------------------------------------------------------------------------


class TestChangeHotkey:
    def test_change_hotkey_updates_config(self, app):
        """Verify config is updated and saved."""
        sender = MagicMock()
        sender.title = "Left Option"

        with patch.object(main, "save_config"):
            app.change_hotkey(sender)

        assert app.config["hotkey"] == "Left Option"

    def test_change_hotkey_restarts_listener(self, app):
        """Verify start_hotkey_listener is called."""
        sender = MagicMock()
        sender.title = "Left Option"

        with (
            patch.object(main, "save_config"),
            patch.object(app, "start_hotkey_listener") as mock_start,
        ):
            app.change_hotkey(sender)

        mock_start.assert_called_once()


# ---------------------------------------------------------------------------
# change_language tests
# ---------------------------------------------------------------------------


class TestChangeLanguage:
    def test_change_language_updates_config(self, app):
        """Verify config is updated and saved."""
        sender = MagicMock()
        sender.title = "Dutch"

        with patch.object(main, "save_config"):
            app.change_language(sender)

        assert app.config["language"] == "Dutch"

    def test_change_language_updates_status(self, app):
        """Verify update_status('ready') is called."""
        sender = MagicMock()
        sender.title = "Dutch"

        with (
            patch.object(main, "save_config"),
            patch.object(app, "update_status") as mock_status,
        ):
            app.change_language(sender)

        mock_status.assert_called_with("ready")


# ---------------------------------------------------------------------------
# on_key_press tests
# ---------------------------------------------------------------------------


class TestOnKeyPress:
    def test_on_key_press_hotkey_starts_recording(self, app):
        """Simulate hotkey press — recording starts."""
        _, key_enums, _ = main.HOTKEY_OPTIONS[app.config["hotkey"]]
        hotkey = next(iter(key_enums))

        with patch.object(main.threading, "Thread", return_value=MagicMock()):
            app.on_key_press(hotkey)

        assert app.is_recording is True
        assert app.hotkey_pressed is True
        app._mock_recorder.start.assert_called_once()

    def test_on_key_press_non_hotkey_ignored(self, app):
        """Non-hotkey key — no recording."""
        fake_key = MagicMock(spec=[])  # No vk attribute
        app.on_key_press(fake_key)
        assert app.is_recording is False
        app._mock_recorder.start.assert_not_called()

    def test_on_key_press_double_press_ignored(self, app):
        """Second press while already pressed — ignored."""
        _, key_enums, _ = main.HOTKEY_OPTIONS[app.config["hotkey"]]
        hotkey = next(iter(key_enums))

        with patch.object(main.threading, "Thread", return_value=MagicMock()):
            app.on_key_press(hotkey)
            app._mock_recorder.start.reset_mock()
            app.on_key_press(hotkey)

        app._mock_recorder.start.assert_not_called()

    def test_on_key_press_clears_pressed_keys_overflow(self, app):
        """More than 10 keys in _pressed_keys causes clear."""
        for i in range(11):
            app._pressed_keys.add(f"fake_key_{i}")

        fake_key = MagicMock(spec=[])
        app.on_key_press(fake_key)
        assert len(app._pressed_keys) == 1


# ---------------------------------------------------------------------------
# on_key_release tests
# ---------------------------------------------------------------------------


class TestOnKeyRelease:
    def test_on_key_release_hotkey_stops_recording(self, app):
        """Simulate release — recording stops."""
        _, key_enums, _ = main.HOTKEY_OPTIONS[app.config["hotkey"]]
        hotkey = next(iter(key_enums))

        app.is_recording = True
        app.hotkey_pressed = True
        app._pressed_keys.add(hotkey)
        app._mock_recorder.stop.return_value = None

        app.on_key_release(hotkey)

        assert app.is_recording is False
        assert app.hotkey_pressed is False
        app._mock_recorder.stop.assert_called_once()

    def test_on_key_release_with_audio_starts_transcription(self, app):
        """Audio path returned — transcription thread started."""
        _, key_enums, _ = main.HOTKEY_OPTIONS[app.config["hotkey"]]
        hotkey = next(iter(key_enums))

        app.is_recording = True
        app.hotkey_pressed = True
        app._pressed_keys.add(hotkey)
        app._mock_recorder.stop.return_value = Path("/tmp/test.wav")

        with patch.object(main.threading, "Thread", return_value=MagicMock()) as mock_thread:
            app.on_key_release(hotkey)

        mock_thread.assert_called_once()
        mock_thread.return_value.start.assert_called_once()

    def test_on_key_release_no_audio_resets_status(self, app):
        """None returned — status reset to ready."""
        _, key_enums, _ = main.HOTKEY_OPTIONS[app.config["hotkey"]]
        hotkey = next(iter(key_enums))

        app.is_recording = True
        app.hotkey_pressed = True
        app._pressed_keys.add(hotkey)
        app._mock_recorder.stop.return_value = None

        with patch.object(app, "update_status") as mock_status:
            app.on_key_release(hotkey)

        mock_status.assert_called_with("ready")


# ---------------------------------------------------------------------------
# _transcribe_and_paste tests
# ---------------------------------------------------------------------------


class TestTranscribeAndPaste:
    def test_transcribe_and_paste_success(self, app):
        """Text returned — paste_text called."""
        with (
            patch.object(main, "transcribe", return_value="hello world"),
            patch.object(app, "paste_text") as mock_paste,
            patch.object(app, "update_status"),
        ):
            app._transcribe_and_paste(Path("/tmp/test.wav"))

        mock_paste.assert_called_once_with("hello world")

    def test_transcribe_and_paste_empty_text(self, app):
        """Empty string — paste_text NOT called."""
        with (
            patch.object(main, "transcribe", return_value=""),
            patch.object(app, "paste_text") as mock_paste,
            patch.object(app, "update_status"),
        ):
            app._transcribe_and_paste(Path("/tmp/test.wav"))

        mock_paste.assert_not_called()

    def test_transcribe_and_paste_model_not_found(self, app):
        """FileNotFoundError — notification shown."""
        _mock_rumps.notification.reset_mock()
        with (
            patch.object(main, "transcribe", side_effect=FileNotFoundError("model missing")),
            patch.object(app, "update_status"),
        ):
            app._transcribe_and_paste(Path("/tmp/test.wav"))

        _mock_rumps.notification.assert_called()

    def test_transcribe_and_paste_resets_status(self, app):
        """Status always reset to 'ready' in finally."""
        with (
            patch.object(main, "transcribe", side_effect=RuntimeError("boom")),
            patch.object(app, "update_status") as mock_status,
        ):
            app._transcribe_and_paste(Path("/tmp/test.wav"))

        mock_status.assert_called_with("ready")


# ---------------------------------------------------------------------------
# paste_text tests
# ---------------------------------------------------------------------------


class TestPasteText:
    def test_paste_text_copies_to_clipboard(self, app):
        """Verify subprocess receives text."""
        mock_proc = MagicMock()
        with patch.object(main.subprocess, "Popen", return_value=mock_proc) as mock_popen:
            app.paste_text("test text")

        mock_popen.assert_called_once()
        mock_proc.communicate.assert_called_once_with(b"test text")

    def test_paste_text_simulates_cmd_v(self, app):
        """Verify keyboard controller presses Cmd+V."""
        mock_proc = MagicMock()
        with patch.object(main.subprocess, "Popen", return_value=mock_proc):
            app.paste_text("test")

        app.keyboard_controller.press.assert_any_call(main.Key.cmd)
        app.keyboard_controller.press.assert_any_call("v")


# ---------------------------------------------------------------------------
# Auto-start tests
# ---------------------------------------------------------------------------


class TestAutoStart:
    def test_enable_auto_start_writes_plist(self, app):
        """Verify plist file created."""
        with patch.object(main.subprocess, "run"):
            app.enable_auto_start()

        assert main.LAUNCH_AGENT_FILE.exists()
        content = main.LAUNCH_AGENT_FILE.read_text()
        assert "com.dictator.app" in content

    def test_disable_auto_start_removes_plist(self, app):
        """Verify file deleted."""
        main.LAUNCH_AGENT_DIR.mkdir(parents=True, exist_ok=True)
        main.LAUNCH_AGENT_FILE.write_text("dummy")

        with patch.object(main.subprocess, "run"):
            app.disable_auto_start()

        assert not main.LAUNCH_AGENT_FILE.exists()

    def test_toggle_auto_start(self, app):
        """Verify toggling works and saves config."""
        sender = MagicMock()
        app.config["auto_start"] = False

        with (
            patch.object(main, "save_config"),
            patch.object(app, "enable_auto_start"),
            patch.object(app, "disable_auto_start"),
        ):
            app.toggle_auto_start(sender)

        assert app.config["auto_start"] is True


# ---------------------------------------------------------------------------
# quit_app tests
# ---------------------------------------------------------------------------


class TestQuitApp:
    def test_quit_app_stops_listener(self, app):
        """Verify listener stopped."""
        app.listener = app._mock_listener
        app.quit_app(None)
        app._mock_listener.stop.assert_called_once()

    def test_quit_app_calls_rumps_quit(self, app):
        """Verify rumps.quit_application() called."""
        _mock_rumps.quit_application.reset_mock()
        app.quit_app(None)
        _mock_rumps.quit_application.assert_called_once()
