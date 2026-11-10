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
# rumps.MenuItem must be a callable that returns a new MagicMock per item.
# Using MagicMock (the class) directly would pass the first arg as `spec`,
# constraining the mock's attributes to those of a string.
_mock_rumps.MenuItem = MagicMock(side_effect=lambda *args, **kwargs: MagicMock())
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

import macos  # noqa: E402
import main  # noqa: E402

# Restore references for the test module
_original_config_dir = main.CONFIG_DIR
_original_config_file = main.CONFIG_FILE
_original_icons_dir = main.ICONS_DIR
_original_launch_agent_file = main.LAUNCH_AGENT_FILE
_original_key = main.Key
_original_hotkey_options = main.HOTKEY_OPTIONS


# ---------------------------------------------------------------------------
# DictatorApp fixture
# ---------------------------------------------------------------------------


class _ImmediateExecutor:
    """Stands in for the audio worker: runs submitted work right away."""

    def submit(self, fn, *args):
        fn(*args)


def _mock_macos():
    """A macos module mock with every permission granted."""
    mock = MagicMock()
    mock.ACCESSIBILITY = macos.ACCESSIBILITY
    mock.INPUT_MONITORING = macos.INPUT_MONITORING
    mock.MICROPHONE = macos.MICROPHONE
    mock.PERMISSIONS = macos.PERMISSIONS
    mock.permission_status.side_effect = lambda: {name: True for name in macos.PERMISSIONS}
    mock.accessibility_granted.return_value = True
    mock.login_item_enabled.return_value = False
    return mock


@pytest.fixture
def app(tmp_path):
    """Create a DictatorApp with all dependencies mocked.

    Calls dispatched to the main thread run immediately.
    """
    # Reset rumps mock call state
    _mock_rumps.reset_mock()
    _mock_pynput_keyboard.reset_mock()

    # Redirect config to tmp_path
    main.CONFIG_DIR = tmp_path / "config"
    main.CONFIG_FILE = main.CONFIG_DIR / "config.json"
    main.LAUNCH_AGENT_FILE = tmp_path / "LaunchAgents" / "com.dictator.app.plist"

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

    mock_app_helper = MagicMock()
    mock_app_helper.callAfter.side_effect = lambda func, *args: func(*args)

    with (
        patch.object(main, "macos", _mock_macos()) as mock_macos,
        patch.object(main, "AppHelper", mock_app_helper),
        patch.object(main, "is_model_installed", return_value=False),
    ):
        with (
            patch.object(main, "_generate_icons"),
            patch.object(main, "AudioRecorder", return_value=mock_recorder),
            patch.object(main.threading, "Thread", return_value=MagicMock()),
        ):
            main.keyboard = _mock_pynput_keyboard
            main.KeyboardController = MagicMock
            app_instance = main.DictatorApp()

        app_instance._audio_worker = _ImmediateExecutor()
        app_instance._mock_rumps = _mock_rumps
        app_instance._mock_recorder = mock_recorder
        app_instance._mock_listener = mock_listener
        app_instance._mock_pynput_keyboard = _mock_pynput_keyboard
        app_instance._mock_macos = mock_macos

        yield app_instance

    # Restore module-level state
    main.CONFIG_DIR = _original_config_dir
    main.CONFIG_FILE = _original_config_file
    main.ICONS_DIR = _original_icons_dir
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
        assert result == {"hotkey": "Right Option", "language": "Auto-detect"}

    def test_load_config_existing(self, tmp_path, monkeypatch):
        """Config file exists — returns its contents."""
        config_file = tmp_path / "config.json"
        config = {"hotkey": "Left Option", "language": "Dutch"}
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
        assert result == {"hotkey": "Right Option", "language": "Auto-detect"}

    def test_load_config_fills_missing_keys(self, tmp_path, monkeypatch):
        """A config from an older version gets defaults for keys it lacks."""
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({"hotkey": "Left Option", "auto_start": False}))
        monkeypatch.setattr(main, "CONFIG_FILE", config_file)
        result = main.load_config()
        assert result["hotkey"] == "Left Option"
        assert result["language"] == "Auto-detect"

    def test_load_config_not_a_dict(self, tmp_path, monkeypatch):
        """Valid JSON that is not an object — returns defaults."""
        config_file = tmp_path / "config.json"
        config_file.write_text("[1, 2]")
        monkeypatch.setattr(main, "CONFIG_FILE", config_file)
        assert main.load_config() == main.DEFAULT_CONFIG


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
    @pytest.fixture(autouse=True)
    def _recording(self, app):
        app.is_recording = True

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

    def test_update_icon_level_ignored_after_recording(self, app):
        """A late level update must not overwrite the transcribing icon."""
        app.update_status("transcribing")
        app.is_recording = False
        app.update_icon_level(1.0)
        assert "transcribing.png" in str(app.icon)


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
    @pytest.fixture(autouse=True)
    def _no_sleep(self):
        with patch.object(main.time, "sleep"):
            yield

    def test_paste_text_copies_to_clipboard(self, app):
        """Text is put on the clipboard and remembered."""
        app.paste_text("test text")
        app._mock_macos.write_clipboard_text.assert_called_once_with("test text")
        assert app.last_transcription == "test text"

    def test_paste_text_simulates_cmd_v(self, app):
        """Verify keyboard controller presses Cmd+V."""
        app.paste_text("test")
        app.keyboard_controller.press.assert_any_call(main.Key.cmd)
        app.keyboard_controller.press.assert_any_call("v")

    def test_paste_text_restores_clipboard(self, app):
        """The previous clipboard comes back after the paste."""
        app._mock_macos.read_clipboard.return_value = ["previous"]
        app._mock_macos.write_clipboard_text.return_value = 5
        app._mock_macos.clipboard_change_count.return_value = 5
        app.paste_text("test")
        app._mock_macos.restore_clipboard.assert_called_once_with(["previous"])

    def test_paste_text_keeps_newer_clipboard(self, app):
        """If something else changed the clipboard meanwhile, it is left alone."""
        app._mock_macos.write_clipboard_text.return_value = 5
        app._mock_macos.clipboard_change_count.return_value = 6
        app.paste_text("test")
        app._mock_macos.restore_clipboard.assert_not_called()

    def test_paste_text_without_accessibility(self, app):
        """No Accessibility: no Cmd+V, text stays on the clipboard, error shown."""
        app._mock_macos.accessibility_granted.return_value = False
        app.paste_text("test")
        app.keyboard_controller.press.assert_not_called()
        app._mock_macos.restore_clipboard.assert_not_called()
        assert "Accessibility" in app.status_item.title

    def test_paste_text_failure_shows_error(self, app):
        """A clipboard error is reported in the menu."""
        app._mock_macos.write_clipboard_text.side_effect = RuntimeError("boom")
        app.paste_text("test")
        assert "Paste failed" in app.status_item.title

    def test_copy_last_transcription(self, app):
        """The menu item puts the last transcription back on the clipboard."""
        app.paste_text("remember me")
        app._mock_macos.write_clipboard_text.reset_mock()
        app.copy_last_transcription()
        app._mock_macos.write_clipboard_text.assert_called_once_with("remember me")

    def test_copy_last_transcription_nothing_yet(self, app):
        """Without a transcription the clipboard is untouched."""
        app.copy_last_transcription()
        app._mock_macos.write_clipboard_text.assert_not_called()


# ---------------------------------------------------------------------------
# Recording on the audio worker
# ---------------------------------------------------------------------------


class TestRecording:
    def test_key_press_does_not_touch_microphone(self, app):
        """The key callback only queues work; the microphone starts on the worker."""
        _, key_enums, _ = main.HOTKEY_OPTIONS[app.config["hotkey"]]
        app._audio_worker = MagicMock()
        app.on_key_press(next(iter(key_enums)))
        app._mock_recorder.start.assert_not_called()
        app._audio_worker.submit.assert_called_once_with(app._start_recording)

    def test_start_recording_failure_shows_error(self, app):
        """A microphone error resets state and is shown in the menu."""
        app.is_recording = True
        app._mock_recorder.start.side_effect = OSError("no device")
        app._start_recording()
        assert app.is_recording is False
        assert "Microphone" in app.status_item.title

    def test_start_recording_clears_error(self, app):
        """A new recording clears the previous error."""
        app.error = "old error"
        with patch.object(main.threading, "Thread", return_value=MagicMock()):
            app._start_recording()
        assert app.error is None
        assert "Listening" in app.status_item.title

    def test_stop_recording_failure_resets_status(self, app):
        """An error stopping the microphone returns to ready."""
        app._mock_recorder.stop.side_effect = OSError("stream gone")
        app._stop_recording()
        assert "Ready" in app.status_item.title

    def test_level_monitor_stops_with_recording(self, app):
        """The monitor updates the icon until recording ends."""
        app._mock_recorder.level = 1.0
        app.is_recording = True

        def stop(_):
            app.is_recording = False

        with patch.object(main.time, "sleep", side_effect=stop):
            app.level_monitor()
        assert "recording_5.png" in str(app.icon)

    def test_language_shortcut_runs_on_main_thread(self, app):
        """Ctrl+Shift+L is dispatched to the main thread once."""
        app._pressed_keys.update({main.Key.ctrl_l, main.Key.shift_l})
        key = MagicMock()
        key.char = "l"
        with patch.object(main, "on_main_thread") as mock_main:
            app.on_key_press(key)
        mock_main.assert_called_once_with(app.cycle_language)


# ---------------------------------------------------------------------------
# Status and errors
# ---------------------------------------------------------------------------


class TestStatusMessages:
    def test_missing_permission_shown_when_idle(self, app):
        """A missing permission replaces "Ready" in the status."""
        app.permissions[macos.MICROPHONE] = False
        app.update_status("ready")
        assert app.status_item.title == "Missing permission: Microphone"

    def test_error_shown_until_cleared(self, app):
        """show_error keeps the message in the status and notifies."""
        _mock_rumps.notification.reset_mock()
        app.show_error("Something broke")
        assert app.status_item.title == "Something broke"
        _mock_rumps.notification.assert_called_once()

    def test_transcription_error_shown(self, app):
        """A failed transcription is visible in the status."""
        with patch.object(main, "transcribe", side_effect=RuntimeError("boom")):
            app._transcribe_and_paste(Path("/tmp/test.wav"))
        assert "Transcription failed" in app.status_item.title


# ---------------------------------------------------------------------------
# Permissions
# ---------------------------------------------------------------------------


class TestPermissions:
    def test_startup_requests_permissions(self, app):
        """Missing permissions are requested once at startup."""
        app._mock_macos.request_permissions.assert_called_once()

    def test_check_permissions_updates_menu(self, app):
        """Each permission's menu item shows its state."""
        app._mock_macos.permission_status.side_effect = None
        app._mock_macos.permission_status.return_value = {
            macos.ACCESSIBILITY: True,
            macos.INPUT_MONITORING: False,
            macos.MICROPHONE: True,
        }
        app.check_permissions()
        assert app.permission_items[macos.ACCESSIBILITY].title == "Accessibility: granted"
        assert "missing" in app.permission_items[macos.INPUT_MONITORING].title
        assert "Input Monitoring" in app.status_item.title

    def test_input_monitoring_granted_restarts_listener(self, app):
        """Gaining Input Monitoring restarts the listener, which was deaf without it."""
        app.permissions[macos.INPUT_MONITORING] = False
        with patch.object(app, "start_hotkey_listener") as mock_start:
            app.check_permissions()
        mock_start.assert_called_once()

    def test_unchanged_permissions_leave_listener(self, app):
        """No change, no restart."""
        with patch.object(app, "start_hotkey_listener") as mock_start:
            app.check_permissions()
        mock_start.assert_not_called()


# ---------------------------------------------------------------------------
# Listener watchdog
# ---------------------------------------------------------------------------


class TestListenerWatchdog:
    def test_dead_listener_restarted(self, app):
        """A dead listener is replaced."""
        app.listener.is_alive.return_value = False
        with patch.object(app, "start_hotkey_listener") as mock_start:
            app.check_listener()
        mock_start.assert_called_once()

    def test_dead_listener_not_restarted_without_input_monitoring(self, app):
        """Without Input Monitoring a restart would die too."""
        app.listener.is_alive.return_value = False
        app.permissions[macos.INPUT_MONITORING] = False
        with patch.object(app, "start_hotkey_listener") as mock_start:
            app.check_listener()
        mock_start.assert_not_called()

    def test_disabled_event_tap_reenabled(self, app):
        """A tap macOS switched off is switched back on."""
        app.listener.is_alive.return_value = True
        app._event_tap = "tap"
        app._mock_macos.event_tap_enabled.return_value = False
        app.check_listener()
        app._mock_macos.enable_event_tap.assert_called_once_with("tap")

    def test_enabled_event_tap_left_alone(self, app):
        app.listener.is_alive.return_value = True
        app._event_tap = "tap"
        app._mock_macos.event_tap_enabled.return_value = True
        app.check_listener()
        app._mock_macos.enable_event_tap.assert_not_called()

    def test_listener_event_tap_is_kept(self, app):
        """The tap pynput creates is remembered for the watchdog."""
        listener = MagicMock()
        listener._create_event_tap.return_value = "new tap"
        app._keep_event_tap(listener)
        assert listener._create_event_tap() == "new tap"
        assert app._event_tap == "new tap"

    def test_watchdog_survives_errors(self, app):
        """An exception in one check does not end the watchdog."""
        calls = []

        def check():
            calls.append(1)
            if len(calls) == 1:
                raise RuntimeError("boom")
            raise SystemExit

        with (
            patch.object(main.time, "sleep"),
            patch.object(app, "check_listener", side_effect=check),
            pytest.raises(SystemExit),
        ):
            app._listener_watchdog()
        assert len(calls) == 2

    def test_restart_stops_old_listener(self, app):
        """Starting a listener stops the previous one, even if stop fails."""
        old = app.listener
        old.stop.side_effect = RuntimeError("already stopped")
        app.start_hotkey_listener()
        old.stop.assert_called_once()


# ---------------------------------------------------------------------------
# Models menu
# ---------------------------------------------------------------------------


class TestModels:
    def _sender(self, model_file):
        sender = MagicMock()
        sender.title = next(k for k, v in main.MODEL_OPTIONS.items() if v == model_file)
        return sender

    def test_click_missing_model_starts_download(self, app):
        sender = self._sender(main.ENGLISH_MODEL)
        with (
            patch.object(main, "is_model_installed", return_value=False),
            patch.object(main.threading, "Thread") as mock_thread,
        ):
            app.on_model_clicked(sender)
        mock_thread.return_value.start.assert_called_once()
        assert "Downloading" in app.status_item.title

    def test_click_installed_model_does_nothing(self, app):
        sender = self._sender(main.ENGLISH_MODEL)
        with (
            patch.object(main, "is_model_installed", return_value=True),
            patch.object(main.threading, "Thread") as mock_thread,
        ):
            app.on_model_clicked(sender)
        mock_thread.assert_not_called()

    def test_download_success_marks_installed(self, app):
        with patch.object(main, "download_model"):
            app._download_model(main.ENGLISH_MODEL)
        assert app.model_items[main.ENGLISH_MODEL].state == 1
        assert main.ENGLISH_MODEL not in app._downloading

    def test_download_failure_shows_error(self, app):
        with patch.object(main, "download_model", side_effect=OSError("offline")):
            app._download_model(main.ENGLISH_MODEL)
        assert "download failed" in app.status_item.title
        assert main.ENGLISH_MODEL not in app._downloading


# ---------------------------------------------------------------------------
# Start at Login
# ---------------------------------------------------------------------------


class TestLoginItem:
    def test_toggle_registers_login_item(self, app):
        sender = MagicMock()
        sender.state = 0
        app._mock_macos.login_item_enabled.return_value = True
        app.toggle_auto_start(sender)
        app._mock_macos.set_login_item.assert_called_once_with(True)
        assert sender.state == 1

    def test_toggle_failure_shows_error(self, app):
        sender = MagicMock()
        sender.state = 0
        app._mock_macos.set_login_item.side_effect = OSError("not a bundle")
        app.toggle_auto_start(sender)
        assert sender.state == 0
        assert "Start at Login" in app.status_item.title

    def test_login_item_status_error_reads_as_off(self, app):
        app._mock_macos.login_item_enabled.side_effect = RuntimeError("unavailable")
        assert app.login_item_enabled() is False

    def test_old_launch_agent_migrated(self, app):
        """The Launch Agent of earlier versions is replaced by a login item."""
        main.LAUNCH_AGENT_FILE.parent.mkdir(parents=True)
        main.LAUNCH_AGENT_FILE.write_text("plist")
        with patch.object(main.subprocess, "run"):
            app.migrate_launch_agent()
        assert not main.LAUNCH_AGENT_FILE.exists()
        app._mock_macos.set_login_item.assert_called_once_with(True)


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
