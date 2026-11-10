"""Main entry point for push-to-talk whisper dictation - Menu bar app."""

import json
import logging
import os
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import rumps
from pynput import keyboard
from pynput.keyboard import Controller as KeyboardController
from pynput.keyboard import Key
from PyObjCTools import AppHelper

import macos
from audio import AudioRecorder
from generate_icons import generate_icons as _generate_icons
from transcriber import (
    ENGLISH_MODEL,
    MULTILINGUAL_MODEL,
    download_model,
    is_model_installed,
    transcribe,
)

# Setup logging to file for debugging. Key events are never logged: the
# log would otherwise record everything typed, passwords included.
LOG_FILE = Path.home() / ".config" / "dictator" / "dictator.log"
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    filename=str(LOG_FILE),
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
log = logging.getLogger(__name__)

# Hotkey options: (display name, Key enum, virtual keycode)
HOTKEY_OPTIONS = {
    "Right Option": (Key.alt_r, {Key.alt_r, Key.alt_gr}, 61),
    "Right Command": (Key.cmd_r, {Key.cmd_r}, 54),
    "Left Option": (Key.alt_l, {Key.alt_l}, 58),
    "Left Command": (Key.cmd_l, {Key.cmd_l}, 55),
}

LANGUAGE_OPTIONS = {
    "English": "en",
    "Dutch": "nl",
    "Auto-detect": "auto",
}

LANGUAGE_SHORT = {
    "English": "EN",
    "Dutch": "NL",
    "Auto-detect": "Auto",
}

MODEL_OPTIONS = {
    "English (466 MB)": ENGLISH_MODEL,
    "Dutch / Auto-detect (539 MB)": MULTILINGUAL_MODEL,
}

DEFAULT_CONFIG = {"hotkey": "Right Option", "language": "Auto-detect"}

CONFIG_DIR = Path.home() / ".config" / "dictator"
CONFIG_FILE = CONFIG_DIR / "config.json"
# Written by earlier versions for "Start at Login"; replaced by a login item
LAUNCH_AGENT_FILE = Path.home() / "Library" / "LaunchAgents" / "com.dictator.app.plist"

# Icons directory
ICONS_DIR = Path(__file__).parent / "icons"

# How long the target app gets to read the clipboard before it is restored
CLIPBOARD_RESTORE_DELAY = 0.5
PERMISSION_CHECK_INTERVAL = 5
WATCHDOG_INTERVAL = 5


def load_config() -> dict:
    """Load configuration from file, filling in defaults for missing keys."""
    if CONFIG_FILE.exists():
        try:
            return {**DEFAULT_CONFIG, **json.loads(CONFIG_FILE.read_text())}
        except Exception as e:
            log.warning(f"Failed to load config, using defaults: {e}")
    return dict(DEFAULT_CONFIG)


def save_config(config: dict) -> None:
    """Save configuration to file."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(config, indent=2))


def on_main_thread(func, *args) -> None:
    """Run func on the main thread; AppKit (and so rumps) is not thread-safe."""
    AppHelper.callAfter(func, *args)


class DictatorApp(rumps.App):
    """Menu bar dictation app."""

    def __init__(self):
        super().__init__("Dictator", quit_button=None)

        self.config = load_config()
        self.recorder = AudioRecorder()
        self.keyboard_controller = KeyboardController()
        self.is_recording = False
        self.hotkey_pressed = False
        self._pressed_keys = set()
        self.listener = None
        self._event_tap = None
        self._listener_lock = threading.Lock()
        # Starting and stopping the microphone can be slow; doing it in the
        # key callback makes macOS disable the event tap. One worker keeps
        # start and stop in order.
        self._audio_worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix="audio")
        self.permissions = {name: True for name in macos.PERMISSIONS}
        self.error = None
        self.last_transcription = None
        self._downloading = set()

        # Load icons
        self.load_icons()

        # Set initial icon
        self.icon = str(ICONS_DIR / "ready.png")

        # Build menu
        self.build_menu()

        self.migrate_launch_agent()

        self.check_permissions()
        macos.request_permissions(self.permissions)
        self._permission_timer = rumps.Timer(self.check_permissions, PERMISSION_CHECK_INTERVAL)
        self._permission_timer.start()

        # Start hotkey listener, and a watchdog that keeps it working
        self.start_hotkey_listener()
        threading.Thread(target=self._listener_watchdog, daemon=True).start()

    def load_icons(self) -> None:
        """Ensure icons directory exists and generate icons if needed."""
        if not ICONS_DIR.exists() or not (ICONS_DIR / "ready.png").exists():
            _generate_icons()

    def build_menu(self) -> None:
        """Build the menu."""
        self.menu.clear()

        # Status item (non-clickable)
        self.status_item = rumps.MenuItem("", callback=None)
        self.status_item.set_callback(None)
        self.menu.add(self.status_item)
        self.menu.add(rumps.separator)

        # Hotkey submenu
        hotkey_menu = rumps.MenuItem("Hotkey")
        for name in HOTKEY_OPTIONS:
            item = rumps.MenuItem(name, callback=self.change_hotkey)
            item.state = 1 if name == self.config["hotkey"] else 0
            hotkey_menu.add(item)
        self.menu.add(hotkey_menu)

        # Language submenu
        language_menu = rumps.MenuItem("Language")
        for name in LANGUAGE_OPTIONS:
            item = rumps.MenuItem(name, callback=self.change_language)
            item.state = 1 if name == self.config["language"] else 0
            language_menu.add(item)
        self.menu.add(language_menu)

        # Models submenu: a check means installed, clicking a missing one downloads it
        models_menu = rumps.MenuItem("Models")
        self.model_items = {}
        for label, model_file in MODEL_OPTIONS.items():
            item = rumps.MenuItem(label, callback=self.on_model_clicked)
            item.state = 1 if is_model_installed(model_file) else 0
            self.model_items[model_file] = item
            models_menu.add(item)
        self.menu.add(models_menu)

        # Permissions submenu: clicking an item opens its System Settings pane
        permissions_menu = rumps.MenuItem("Permissions")
        self.permission_items = {}
        for name in macos.PERMISSIONS:
            item = rumps.MenuItem(name, callback=lambda _, n=name: macos.open_settings(n))
            self.permission_items[name] = item
            permissions_menu.add(item)
        self.menu.add(permissions_menu)

        self.copy_last_item = rumps.MenuItem("Copy Last Transcription", callback=None)
        self.menu.add(self.copy_last_item)

        # Auto-start toggle
        self.auto_start_item = rumps.MenuItem("Start at Login", callback=self.toggle_auto_start)
        self.auto_start_item.state = 1 if self.login_item_enabled() else 0
        self.menu.add(self.auto_start_item)

        self.menu.add(rumps.separator)
        self.menu.add(rumps.MenuItem("Quit", callback=self.quit_app))

        self.update_status("ready")

    def change_hotkey(self, sender: rumps.MenuItem) -> None:
        """Change the hotkey."""
        self.config["hotkey"] = sender.title
        save_config(self.config)

        # Update menu checkmarks
        for item in self.menu["Hotkey"].values():
            if isinstance(item, rumps.MenuItem):
                item.state = 1 if item.title == sender.title else 0

        # Restart listener with new hotkey
        self.start_hotkey_listener()

    def _update_language_checkmarks(self, active_name: str) -> None:
        """Update Language menu checkmarks to reflect the active language."""
        for item in self.menu["Language"].values():
            if isinstance(item, rumps.MenuItem):
                item.state = 1 if item.title == active_name else 0

    def change_language(self, sender: rumps.MenuItem) -> None:
        """Change the transcription language."""
        self.config["language"] = sender.title
        save_config(self.config)

        self._update_language_checkmarks(sender.title)

        # Update status to reflect new language
        self.update_status("ready")

        log.info(f"Language changed to: {sender.title}")

    def cycle_language(self) -> None:
        """Cycle to the next language option."""
        names = list(LANGUAGE_OPTIONS.keys())
        current = self.config["language"]
        try:
            idx = names.index(current)
        except ValueError:
            idx = 0
        next_name = names[(idx + 1) % len(names)]

        self.config["language"] = next_name
        save_config(self.config)

        self._update_language_checkmarks(next_name)

        self.update_status("ready")

        lang_short = LANGUAGE_SHORT.get(next_name, "EN")
        rumps.notification(
            title="Dictator",
            subtitle="Language Changed",
            message=f"Now using: {next_name} ({lang_short})",
        )
        log.info(f"Language cycled to: {next_name}")

    def on_model_clicked(self, sender: rumps.MenuItem) -> None:
        """Download a missing model in the background."""
        model_file = MODEL_OPTIONS[sender.title]
        if is_model_installed(model_file) or model_file in self._downloading:
            return
        self._downloading.add(model_file)
        self.status_item.title = f"Downloading {sender.title}..."
        threading.Thread(target=self._download_model, args=(model_file,), daemon=True).start()

    def _download_model(self, model_file: str) -> None:
        """Download a model (runs in background thread)."""
        try:
            log.info(f"Downloading model {model_file}")
            download_model(model_file)
            log.info(f"Downloaded model {model_file}")
            on_main_thread(self._model_downloaded, model_file)
        except Exception as e:
            log.error(f"Failed to download model {model_file}: {e}")
            on_main_thread(self.show_error, "Model download failed")
        finally:
            self._downloading.discard(model_file)

    def _model_downloaded(self, model_file: str) -> None:
        """Mark a model as installed in the menu."""
        self.model_items[model_file].state = 1
        self.error = None
        self.update_status("ready")

    def check_permissions(self, _=None) -> None:
        """Refresh the Permissions menu and status from what macOS reports."""
        previous = self.permissions
        self.permissions = macos.permission_status()
        for name, granted in self.permissions.items():
            item = self.permission_items[name]
            item.title = f"{name}: granted" if granted else f"{name}: missing (open Settings)"
            item.state = 1 if granted else 0
        if self.permissions != previous:
            log.info(f"Permissions: {self.permissions}")
            if self.permissions[macos.INPUT_MONITORING] and not previous[macos.INPUT_MONITORING]:
                # A listener started without the permission receives nothing
                self.start_hotkey_listener()
            self.update_status("ready")

    def migrate_launch_agent(self) -> None:
        """Replace the Launch Agent of earlier versions with a login item."""
        if not LAUNCH_AGENT_FILE.exists():
            return
        subprocess.run(
            ["launchctl", "bootout", f"gui/{os.getuid()}", str(LAUNCH_AGENT_FILE)],
            capture_output=True,
        )
        LAUNCH_AGENT_FILE.unlink()
        log.info("Removed Launch Agent, registering login item instead")
        self.set_login_item(True)

    def login_item_enabled(self) -> bool:
        """Whether Dictator starts at login; False if macOS cannot tell."""
        try:
            return macos.login_item_enabled()
        except Exception as e:
            log.warning(f"Failed to read login item status: {e}")
            return False

    def set_login_item(self, enabled: bool) -> None:
        """Register or unregister the login item, reporting failure in the menu."""
        try:
            macos.set_login_item(enabled)
        except Exception as e:
            log.error(f"Failed to change login item: {e}")
            self.show_error("Could not change Start at Login")

    def toggle_auto_start(self, sender: rumps.MenuItem) -> None:
        """Toggle auto-start at login."""
        self.set_login_item(not sender.state)
        sender.state = 1 if self.login_item_enabled() else 0

    def quit_app(self, _) -> None:
        """Quit the application."""
        if self.listener:
            self.listener.stop()
        rumps.quit_application()

    def get_current_hotkey(self) -> tuple:
        """Get current hotkey configuration."""
        hotkey_name = self.config["hotkey"]
        return HOTKEY_OPTIONS.get(hotkey_name, HOTKEY_OPTIONS["Right Option"])

    def is_hotkey(self, key) -> bool:
        """Check if the pressed key is our hotkey."""
        _, key_enums, vk_code = self.get_current_hotkey()
        if key in key_enums:
            return True
        if hasattr(key, "vk") and key.vk == vk_code:
            return True
        return False

    def update_status(self, status: str) -> None:
        """Update the status display (main thread only).

        While idle, a missing permission or the last error takes the place
        of "Ready", so a failure is visible in the menu.
        """
        lang_name = self.config["language"]
        lang_short = LANGUAGE_SHORT.get(lang_name, "EN")
        missing = [name for name, granted in self.permissions.items() if not granted]
        if missing:
            ready_text = f"Missing permission: {', '.join(missing)}"
        elif self.error:
            ready_text = self.error
        else:
            ready_text = f"Ready ({lang_short})"
        status_text = {
            "ready": ready_text,
            "listening": f"Listening ({lang_short})...",
            "transcribing": "Transcribing...",
        }
        self.status_item.title = status_text.get(status, ready_text)

        if status == "ready":
            self.icon = str(ICONS_DIR / "ready.png")
        elif status == "transcribing":
            self.icon = str(ICONS_DIR / "transcribing.png")

    def show_error(self, message: str) -> None:
        """Show an error in the menu until the next recording (main thread only)."""
        self.error = message
        self.update_status("ready")
        rumps.notification(title="Dictator", subtitle="Error", message=message)

    def update_icon_level(self, level: float) -> None:
        """Update icon based on audio level (main thread only)."""
        if not self.is_recording:
            return
        # Map level (0-1) to icon index (0-5)
        idx = min(5, int(level * 6))
        self.icon = str(ICONS_DIR / f"recording_{idx}.png")

    def level_monitor(self) -> None:
        """Monitor and update icon based on audio level."""
        while self.is_recording:
            on_main_thread(self.update_icon_level, self.recorder.level)
            time.sleep(0.05)

    def paste_text(self, text: str) -> None:
        """Paste text into the active application, then restore the clipboard."""
        self.last_transcription = text
        on_main_thread(self.copy_last_item.set_callback, self.copy_last_transcription)
        try:
            snapshot = macos.read_clipboard()
            change_count = macos.write_clipboard_text(text)

            if not macos.accessibility_granted():
                # macOS would silently drop the Cmd+V; leave the text on the clipboard
                on_main_thread(self.show_error, "Not pasted (no Accessibility) - press Cmd+V")
                return

            time.sleep(0.05)
            self.keyboard_controller.press(Key.cmd)
            self.keyboard_controller.press("v")
            self.keyboard_controller.release("v")
            self.keyboard_controller.release(Key.cmd)

            time.sleep(CLIPBOARD_RESTORE_DELAY)
            # Skip the restore if anything else changed the clipboard meanwhile
            if macos.clipboard_change_count() == change_count:
                macos.restore_clipboard(snapshot)
        except Exception as e:
            log.error(f"Failed to paste: {e}")
            on_main_thread(self.show_error, "Paste failed - use Copy Last Transcription")

    def copy_last_transcription(self, _=None) -> None:
        """Put the last transcription on the clipboard."""
        if self.last_transcription:
            macos.write_clipboard_text(self.last_transcription)

    def on_key_press(self, key) -> None:
        """Handle key press events (listener thread; must return quickly)."""
        try:
            # Guard against unbounded growth if key releases are missed
            if len(self._pressed_keys) > 10:
                self._pressed_keys.clear()
            self._pressed_keys.add(key)

            # Check for language cycle shortcut: Ctrl+Shift+L
            has_ctrl = Key.ctrl_l in self._pressed_keys or Key.ctrl_r in self._pressed_keys
            has_shift = Key.shift_l in self._pressed_keys or Key.shift_r in self._pressed_keys
            # key.char may be None when Ctrl is held; fall back to vk code 37 (the L key)
            is_l = getattr(key, "char", None) in ("l", "\x0c")
            if not is_l:
                is_l = getattr(key, "vk", None) == 37
            if has_ctrl and has_shift and is_l:
                on_main_thread(self.cycle_language)
                return

            if self.is_hotkey(key):
                if self.hotkey_pressed:
                    return
                log.info("Hotkey pressed")
                self.hotkey_pressed = True
                if not self.is_recording:
                    self.is_recording = True
                    self._audio_worker.submit(self._start_recording)
        except Exception as e:
            log.error(f"Key press error: {e}")
            self.is_recording = False
            self.hotkey_pressed = False

    def on_key_release(self, key) -> None:
        """Handle key release events (listener thread; must return quickly)."""
        try:
            self._pressed_keys.discard(key)

            if self.is_hotkey(key):
                self.hotkey_pressed = False
                if not self.is_recording:
                    return
                self.is_recording = False
                self._audio_worker.submit(self._stop_recording)
        except Exception as e:
            log.error(f"Key release error: {e}")
            self.is_recording = False
            self.hotkey_pressed = False
            on_main_thread(self.update_status, "ready")

    def _start_recording(self) -> None:
        """Start the microphone (audio worker thread)."""
        try:
            self.recorder.start()
        except Exception as e:
            log.error(f"Failed to start recording: {e}")
            self.is_recording = False
            on_main_thread(self.show_error, "Microphone unavailable")
            return
        self.error = None
        on_main_thread(self.update_status, "listening")
        threading.Thread(target=self.level_monitor, daemon=True).start()

    def _stop_recording(self) -> None:
        """Stop the microphone and hand the audio to transcription (audio worker thread)."""
        try:
            audio_path = self.recorder.stop()
        except Exception as e:
            log.error(f"Failed to stop recording: {e}")
            audio_path = None

        if audio_path is None:
            on_main_thread(self.update_status, "ready")
            return
        on_main_thread(self.update_status, "transcribing")
        # Run transcription in its own thread so the next recording can start
        threading.Thread(target=self._transcribe_and_paste, args=(audio_path,), daemon=True).start()

    def _transcribe_and_paste(self, audio_path) -> None:
        """Transcribe audio and paste result (runs in background thread)."""
        try:
            lang_code = LANGUAGE_OPTIONS.get(self.config["language"], "en")
            text = transcribe(audio_path, language=lang_code)
            if text:
                self.paste_text(text)
        except FileNotFoundError as e:
            log.error(f"Model not found: {e}")
            on_main_thread(self.show_error, "Model missing - download it from the Models menu")
        except Exception as e:
            log.error(f"Transcription failed: {e}")
            on_main_thread(self.show_error, "Transcription failed - see log")
        finally:
            on_main_thread(self.update_status, "ready")

    def start_hotkey_listener(self) -> None:
        """Start the global hotkey listener, replacing any running one."""
        with self._listener_lock:
            log.info("Starting hotkey listener...")
            if self.listener:
                try:
                    self.listener.stop()
                except Exception as e:
                    log.warning(f"Failed to stop listener: {e}")

            self._event_tap = None
            listener = keyboard.Listener(on_press=self.on_key_press, on_release=self.on_key_release)
            self._keep_event_tap(listener)
            listener.daemon = True
            listener.start()
            self.listener = listener
            log.info(f"Listener started, is_alive: {listener.is_alive()}")

    def _keep_event_tap(self, listener) -> None:
        """Remember the listener's macOS event tap so the watchdog can check it.

        pynput does not expose the tap, so this wraps its private
        _create_event_tap (pynput is pinned in pyproject.toml for this).
        """
        create_event_tap = listener._create_event_tap

        def create_and_keep():
            tap = create_event_tap()
            self._event_tap = tap
            return tap

        listener._create_event_tap = create_and_keep

    def check_listener(self) -> None:
        """Restart a dead listener and re-enable an event tap macOS turned off."""
        listener = self.listener
        if listener is None or not listener.is_alive():
            # Without Input Monitoring a new listener would die the same way
            if self.permissions[macos.INPUT_MONITORING]:
                log.warning("Listener died, restarting...")
                self.start_hotkey_listener()
        elif self._event_tap is not None and not macos.event_tap_enabled(self._event_tap):
            log.warning("macOS disabled the key event tap, re-enabling")
            macos.enable_event_tap(self._event_tap)

    def _listener_watchdog(self) -> None:
        """Keep the hotkey listener working (runs in background thread)."""
        while True:
            time.sleep(WATCHDOG_INTERVAL)
            try:
                self.check_listener()
            except Exception as e:
                log.error(f"Listener watchdog error: {e}")


def main() -> None:
    """Main entry point."""
    app = DictatorApp()
    app.run()


if __name__ == "__main__":
    main()
