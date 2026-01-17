# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Run Commands

```bash
make run       # Run from source
make build     # Build app and install to /Applications/Dictator.app
make install-model  # Download whisper model (~466MB) to ~/.local/share/whisper-dictation/
make lint      # Run ruff linter
make format    # Format code with ruff
make clean     # Remove build artifacts
```

Package management uses `uv`. Run `uv sync` to install dependencies.

## Architecture

This is a macOS menu bar push-to-talk speech-to-text app. The flow is:

1. **main.py** - `DictatorApp` (rumps.App subclass) runs the menu bar UI and hotkey listener
2. **audio.py** - `AudioRecorder` captures audio via sounddevice while hotkey is held, exposes real-time `level` property for UI feedback
3. **transcriber.py** - `transcribe()` uses pywhispercpp to run whisper.cpp inference, returns text
4. Result is copied to clipboard and pasted via simulated Cmd+V

Key architectural decisions:
- Hotkey listener runs in daemon thread via pynput, with watchdog thread to auto-restart if it dies
- Transcription runs in background thread to not block the hotkey listener
- Model is lazy-loaded on first transcription to speed up app startup
- Menu bar icon swaps between pre-generated PNGs (in `icons/`) to show audio level animation
- Config stored in `~/.config/dictator/config.json`
- Debug logs written to `~/.config/dictator/dictator.log`

## PyInstaller Bundling

`Dictator.spec` configures the macOS app bundle. Key points:
- Model files from `models/` are bundled into the app
- pywhispercpp's native `.dylib` files must be explicitly collected
- `LSUIElement: True` hides the app from the Dock (menu bar only)
- The bundled app needs separate Accessibility permissions from the dev version

## Common Pitfalls

### Logging vs Print Statements
Always use the configured logger (`log`) instead of `print()` statements for error output:
- ✅ `log.error(f"Failed to paste: {e}")`
- ✅ `log.warning("Listener died, restarting...")`
- ❌ `print(f"Failed to paste: {e}")`

Print statements won't be visible to users and won't be captured in the log file (`~/.config/dictator/dictator.log`).

### Exception Handling in Config Loading
When loading configuration files, always log exceptions so users can diagnose issues:
- ✅ `except Exception as e: log.warning(f"Failed to load config, using defaults: {e}")`
- ❌ `except Exception: pass`  # Silent failure hides corruption/permission errors

See main.py:50-51 for the correct pattern.
