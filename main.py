"""Main entry point for push-to-talk whisper dictation - Menu bar app."""

import json
import logging
import subprocess
import threading
import time
from pathlib import Path

import rumps
from pynput import keyboard
from pynput.keyboard import Controller as KeyboardController
from pynput.keyboard import Key

from audio import AudioRecorder
from transcriber import transcribe

# Setup logging to file for debugging
LOG_FILE = Path.home() / ".config" / "dictator" / "dictator.log"
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    filename=str(LOG_FILE),
    level=logging.DEBUG,
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

CONFIG_DIR = Path.home() / ".config" / "dictator"
CONFIG_FILE = CONFIG_DIR / "config.json"
LAUNCH_AGENT_DIR = Path.home() / "Library" / "LaunchAgents"
LAUNCH_AGENT_FILE = LAUNCH_AGENT_DIR / "com.dictator.app.plist"

# Icons directory
ICONS_DIR = Path(__file__).parent / "icons"


def load_config() -> dict:
    """Load configuration from file."""
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text())
        except Exception as e:
            log.warning(f"Failed to load config, using defaults: {e}")
    return {"hotkey": "Right Option", "auto_start": False}


def save_config(config: dict) -> None:
    """Save configuration to file."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(config, indent=2))


class DictatorApp(rumps.App):
    """Menu bar dictation app."""

    def __init__(self):
        super().__init__("Dictator", quit_button=None)

        self.config = load_config()
        self.recorder = AudioRecorder()
        self.keyboard_controller = KeyboardController()
        self.is_recording = False
        self.hotkey_pressed = False
        self.listener = None

        # Load icons
        self.load_icons()

        # Set initial icon
        self.icon = str(ICONS_DIR / "ready.png")

        # Build menu
        self.build_menu()

        # Start hotkey listener
        self.start_hotkey_listener()

    def load_icons(self) -> None:
        """Ensure icons directory exists and generate icons if needed."""
        if not ICONS_DIR.exists() or not (ICONS_DIR / "ready.png").exists():
            self.generate_icons()

    def generate_icons(self) -> None:
        """Generate menu bar icons."""
        from PIL import Image, ImageDraw

        ICONS_DIR.mkdir(exist_ok=True)
        size = 22  # Standard menu bar icon size

        # Ready icon (gray circle)
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        padding = 4
        draw.ellipse([padding, padding, size - padding, size - padding], fill=(100, 100, 100, 255))
        img.save(ICONS_DIR / "ready.png")

        # Transcribing icon (blue circle)
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.ellipse([padding, padding, size - padding, size - padding], fill=(30, 136, 229, 255))
        img.save(ICONS_DIR / "transcribing.png")

        # Recording icons at different levels (red -> orange -> yellow)
        for i in range(6):
            level = i / 5.0
            img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)

            # Color: red -> orange -> yellow
            r = 229
            g = int(57 + level * 198)
            b = int(53 - level * 53)

            # Size based on level
            level_padding = int(padding - level * 2)
            draw.ellipse(
                [level_padding, level_padding, size - level_padding, size - level_padding],
                fill=(r, g, b, 255),
            )
            img.save(ICONS_DIR / f"recording_{i}.png")

    def build_menu(self) -> None:
        """Build the menu."""
        self.menu.clear()

        # Status item (non-clickable)
        self.status_item = rumps.MenuItem("Ready", callback=None)
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

        # Auto-start toggle
        self.auto_start_item = rumps.MenuItem("Start at Login", callback=self.toggle_auto_start)
        self.auto_start_item.state = 1 if self.config.get("auto_start", False) else 0
        self.menu.add(self.auto_start_item)

        self.menu.add(rumps.separator)
        self.menu.add(rumps.MenuItem("Quit", callback=self.quit_app))

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

    def toggle_auto_start(self, sender: rumps.MenuItem) -> None:
        """Toggle auto-start at login."""
        self.config["auto_start"] = not self.config.get("auto_start", False)
        save_config(self.config)
        sender.state = 1 if self.config["auto_start"] else 0

        if self.config["auto_start"]:
            self.enable_auto_start()
        else:
            self.disable_auto_start()

    def enable_auto_start(self) -> None:
        """Enable auto-start via Launch Agent."""
        LAUNCH_AGENT_DIR.mkdir(parents=True, exist_ok=True)

        # Get app path
        app_path = "/Applications/Dictator.app"

        plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.dictator.app</string>
    <key>ProgramArguments</key>
    <array>
        <string>open</string>
        <string>-a</string>
        <string>{app_path}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>
"""
        LAUNCH_AGENT_FILE.write_text(plist_content)
        subprocess.run(["launchctl", "load", str(LAUNCH_AGENT_FILE)], capture_output=True)

    def disable_auto_start(self) -> None:
        """Disable auto-start."""
        if LAUNCH_AGENT_FILE.exists():
            subprocess.run(["launchctl", "unload", str(LAUNCH_AGENT_FILE)], capture_output=True)
            LAUNCH_AGENT_FILE.unlink()

    def quit_app(self, _) -> None:
        """Quit the application."""
        if self.listener:
            self.listener.stop()
        rumps.quit_application()

    def get_current_hotkey(self) -> tuple:
        """Get current hotkey configuration."""
        hotkey_name = self.config.get("hotkey", "Right Option")
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
        """Update the status display."""
        status_text = {
            "ready": "Ready",
            "listening": "Listening...",
            "transcribing": "Transcribing...",
        }
        self.status_item.title = status_text.get(status, "Ready")

        if status == "ready":
            self.icon = str(ICONS_DIR / "ready.png")
        elif status == "transcribing":
            self.icon = str(ICONS_DIR / "transcribing.png")

    def update_icon_level(self, level: float) -> None:
        """Update icon based on audio level."""
        # Map level (0-1) to icon index (0-5)
        idx = min(5, int(level * 6))
        self.icon = str(ICONS_DIR / f"recording_{idx}.png")

    def level_monitor(self) -> None:
        """Monitor and update icon based on audio level."""
        while self.is_recording:
            self.update_icon_level(self.recorder.level)
            time.sleep(0.05)
        self.update_icon_level(0)

    def paste_text(self, text: str) -> None:
        """Paste text into the active application."""
        try:
            process = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE)
            process.communicate(text.encode("utf-8"))
            time.sleep(0.05)

            self.keyboard_controller.press(Key.cmd)
            self.keyboard_controller.press("v")
            self.keyboard_controller.release("v")
            self.keyboard_controller.release(Key.cmd)
        except Exception as e:
            log.error(f"Failed to paste: {e}")

    def on_key_press(self, key) -> None:
        """Handle key press events."""
        try:
            log.debug(f"Key press: {key}")
            if self.is_hotkey(key):
                log.info("Hotkey pressed!")
                if self.hotkey_pressed:
                    return
                self.hotkey_pressed = True
                if not self.is_recording:
                    self.is_recording = True
                    self.update_status("listening")
                    self.recorder.start()
                    threading.Thread(target=self.level_monitor, daemon=True).start()
        except Exception as e:
            log.error(f"Key press error: {e}")
            self.is_recording = False
            self.hotkey_pressed = False

    def on_key_release(self, key) -> None:
        """Handle key release events."""
        try:
            if self.is_hotkey(key):
                self.hotkey_pressed = False
                if not self.is_recording:
                    return
                self.is_recording = False
                audio_path = self.recorder.stop()

                if audio_path is not None:
                    self.update_status("transcribing")
                    # Run transcription in background to not block listener
                    threading.Thread(
                        target=self._transcribe_and_paste, args=(audio_path,), daemon=True
                    ).start()
                else:
                    self.update_status("ready")
        except Exception as e:
            log.error(f"Key release error: {e}")
            self.is_recording = False
            self.hotkey_pressed = False
            self.update_status("ready")

    def _transcribe_and_paste(self, audio_path) -> None:
        """Transcribe audio and paste result (runs in background thread)."""
        try:
            text = transcribe(audio_path)
            if text:
                self.paste_text(text)
        except Exception as e:
            log.error(f"Transcription failed: {e}")
        finally:
            self.update_status("ready")

    def start_hotkey_listener(self) -> None:
        """Start the global hotkey listener."""
        log.info("Starting hotkey listener...")
        if self.listener:
            try:
                self.listener.stop()
            except Exception:
                pass

        self.listener = keyboard.Listener(
            on_press=self.on_key_press, on_release=self.on_key_release
        )
        self.listener.daemon = True
        self.listener.start()
        log.info(f"Listener started, is_alive: {self.listener.is_alive()}")

        # Start watchdog to restart listener if it dies
        threading.Thread(target=self._listener_watchdog, daemon=True).start()

    def _listener_watchdog(self) -> None:
        """Monitor listener and restart if it dies."""
        while True:
            time.sleep(5)
            if self.listener is None or not self.listener.is_alive():
                log.warning("Listener died, restarting...")
                self.start_hotkey_listener()
                break  # New watchdog will be started by start_hotkey_listener


def main() -> None:
    """Main entry point."""
    app = DictatorApp()
    app.run()


if __name__ == "__main__":
    main()
