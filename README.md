# Dictator

[![License](https://img.shields.io/badge/License-MIT%20with%20Commons%20Clause-blue.svg)](LICENSE)

A lightweight, open-source macOS menu bar app for push-to-talk speech-to-text. Runs entirely on your Mac—no internet connection required, no data leaves your device.

## Features

- **100% Local**: All processing happens on-device using [whisper.cpp](https://github.com/ggerganov/whisper.cpp)—your audio never leaves your Mac
- **No Internet Required**: Works completely offline once installed
- **Fast**: Metal GPU acceleration for near-instant transcription on Apple Silicon
- **Lightweight**: Minimal resource usage, stays out of your way
- **Non-obtrusive**: Lives quietly in your menu bar, not the dock
- **Easy to Use**: Just hold a hotkey to record, release to transcribe and paste
- **Push-to-talk**: Natural workflow—hold to speak, release to transcribe
- **Visual Feedback**: Icon animates (red → orange → yellow) based on audio level
- **Configurable**: Choose your preferred hotkey (Right Option, Right Command, Left Option, or Left Command)
- **Auto-start**: Option to launch at login
- **Self-contained**: Model bundled in the app (no external dependencies)
- **Open Source**: MIT licensed with Commons Clause

## Requirements

- macOS (tested on Apple Silicon)

For building from source:
- Python 3.11+
- [uv](https://github.com/astral-sh/uv) for package management

## Installation

### Download (Recommended)

1. Download the DMG from [Releases](https://github.com/albertsikkema/dictator/releases)
2. Open the DMG and drag `Dictator.app` to `/Applications`
3. **First launch** (required for unsigned apps):
   - Right-click `Dictator.app` → select **Open**
   - Click **Open** in the security dialog
4. Grant permissions when prompted (see [Permissions](#permissions))

### From Source

1. Clone the repository:
   ```bash
   git clone https://github.com/albertsikkema/dictator.git
   cd dictator
   ```

2. Install dependencies:
   ```bash
   uv sync
   ```

3. Download the whisper model (~466MB):
   ```bash
   make install-model
   ```

4. Run the app:
   ```bash
   make run
   ```

### Build Standalone App

To build a standalone macOS app:

```bash
make build
```

This will:
- Build the app with PyInstaller
- Bundle the whisper model inside the app
- Install to `/Applications/Dictator.app`

## Usage

1. Launch the app (from Applications or `make run`)
2. Look for the gray circle icon in your menu bar
3. Hold the hotkey (default: **Right Option**) to record
4. Speak clearly
5. Release the hotkey - text will be transcribed and pasted into the active app

### Menu Bar Icon States

| Icon | State |
|------|-------|
| Gray circle | Ready |
| Red/orange/yellow (animated) | Recording - color indicates volume |
| Blue circle | Transcribing |

### Configuration

Click the menu bar icon to access:

- **Hotkey**: Change the push-to-talk key
- **Start at Login**: Enable/disable auto-start

Settings are saved to `~/.config/dictator/config.json`.

## Permissions

Dictator needs two permissions to function:

### Microphone
- macOS will prompt automatically on first recording
- Click **Allow** when asked

### Accessibility (required for hotkey + paste)
This must be enabled manually:
1. Open **System Settings → Privacy & Security → Accessibility**
2. Click the **+** button
3. Navigate to `/Applications/Dictator.app` and add it
4. Ensure the toggle is **ON**

### Troubleshooting Permissions

If the hotkey doesn't work:
1. Go to **System Settings → Privacy & Security → Accessibility**
2. Remove Dictator.app (select it and click **−**)
3. Re-add it using the steps above
4. Restart the app

## Project Structure

```
dictator/
├── main.py           # Menu bar app and hotkey handling
├── audio.py          # Audio recording with sounddevice
├── transcriber.py    # Whisper transcription
├── icons/            # Menu bar icons (generated)
├── models/           # Whisper model (downloaded)
├── Dictator.spec     # PyInstaller configuration
├── Dictator.icns     # App icon
├── Makefile          # Build commands
├── pyproject.toml    # Dependencies
└── CHANGELOG.md      # Version history
```

## Development

```bash
# Run from source
make run

# Lint code
make lint

# Format code
make format

# Build app
make build

# Clean build artifacts
make clean
```

## Tech Stack

- **[whisper.cpp](https://github.com/ggerganov/whisper.cpp)** via [pywhispercpp](https://github.com/absadiki/pywhispercpp) - Speech recognition
- **[rumps](https://github.com/jaredks/rumps)** - macOS menu bar framework
- **[pynput](https://github.com/moses-palmer/pynput)** - Global hotkey detection
- **[sounddevice](https://python-sounddevice.readthedocs.io/)** - Audio capture
- **[PyInstaller](https://pyinstaller.org/)** - App bundling

## Model

The app uses the `ggml-small.en.bin` model (~466MB):
- English-only, optimized for accuracy
- Good for non-native English speakers
- Uses Metal GPU acceleration on Apple Silicon

## Troubleshooting

### Hotkey not working
- See [Troubleshooting Permissions](#troubleshooting-permissions) above
- Try a different hotkey from the menu

### "[BLANK_AUDIO]" or no transcription
- Speak louder/closer to the microphone
- Hold the hotkey longer (at least 0.5 seconds)
- Check that the menu bar icon animates when you speak

### App not starting
- Check Console.app for crash logs
- Run from terminal to see errors: `/Applications/Dictator.app/Contents/MacOS/Dictator`

## License

This project is licensed under the [MIT License with Commons Clause](LICENSE).

You are free to use, modify, and distribute this software. However, you may not sell it or offer it as a paid service.
