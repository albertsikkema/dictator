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
- **Multilingual**: Supports English, Dutch, and auto-detection between the two
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
3. **First launch** - macOS is protective of unsigned apps (see note below):
   - Right-click `Dictator.app` → select **Open**
   - Click **Open** in the security dialog
4. Grant permissions when prompted (see [Permissions](#permissions))

> **Note: macOS Security**
>
> This app is not signed with an Apple Developer certificate, so macOS will show security warnings. This is normal for open-source apps distributed outside the App Store.
>
> **The app is safe** - you can [review the source code yourself](https://github.com/albertsikkema/dictator). All audio processing happens locally on your Mac.
>
> If right-click → Open doesn't work:
> 1. Go to **System Settings → Privacy & Security**
> 2. Scroll down to the **Security** section
> 3. You'll see a message about Dictator being blocked - click **Open Anyway**
> 4. Confirm by clicking **Open** in the dialog

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

3. Download the whisper models (optional: the app downloads the one it needs on first use):
   ```bash
   make install-models              # both, skips any already downloaded
   make install-model               # English-only (~466MB)
   make install-model-multilingual  # Multilingual (~539MB, required for Dutch / Auto-detect)
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

This builds the app with PyInstaller, downloads both whisper models to
`~/.local/share/whisper-dictation/` if they are missing (~1 GB the first
time), and installs the app to `/Applications/Dictator.app`.

#### Stable code signing

macOS ties privacy permissions to the app's code signature. Without a
signing certificate the app is signed ad hoc, which produces a new
signature on every build, so macOS silently drops Dictator's permissions
after each `make build`. To keep them, create a self-signed certificate
once:

1. Open **Keychain Access** and choose **Keychain Access > Certificate Assistant > Create a Certificate...**
2. Name: `Dictator Local Signing`, Identity Type: **Self Signed Root**, Certificate Type: **Code Signing**, then **Create**
3. Double-click the new certificate, open **Trust** and set **Code Signing** to **Always Trust**

`make build` uses it automatically when present (another name works with
`make build SIGN_IDENTITY="Your Name"`). Grant the permissions once more
after the first signed build; they then survive rebuilds. With an ad-hoc
build, run `make reset-permissions` and grant them again after every build.

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

- **Hotkey**: Change the push-to-talk key (Right Option, Right Command, Left Option, or Left Command)
- **Language**: Choose between English, Dutch, or Auto-detect (default). **Ctrl+Shift+L** cycles through them
- **Models**: A check means installed; click a missing model to download it
- **Permissions**: Shows whether each permission is granted; click one to open its System Settings pane
- **Copy Last Transcription**: Put the last transcription back on the clipboard, e.g. when a paste went to the wrong place
- **Start at Login**: Enable/disable auto-start

The first line of the menu shows the status. Instead of "Ready" it shows a
missing permission or the last error, until the next recording.

After pasting, Dictator restores what was on the clipboard before.

Settings are saved to `~/.config/dictator/config.json`.

## Permissions

Dictator needs three permissions. At startup it asks macOS to prompt for
any that are missing, and the **Permissions** menu shows their state.

| Permission | Needed for | System Settings > Privacy & Security |
|------------|------------|--------------------------------------|
| Input Monitoring | Noticing the hotkey | Input Monitoring |
| Accessibility | Pasting (simulated Cmd+V) | Accessibility |
| Microphone | Recording | Microphone |

To grant one by hand, open its pane (or click it in the **Permissions**
menu), add `/Applications/Dictator.app` with **+** and turn it on. Restart
Dictator after granting Input Monitoring.

When running from source (`make run`), macOS checks the permissions of the
terminal app instead.

### Troubleshooting Permissions

If a permission looks granted but Dictator says it is missing, the entry
belongs to an earlier build (see [Stable code signing](#stable-code-signing)):

1. Quit Dictator
2. Run `make reset-permissions`
3. Start Dictator and grant the permissions again

## Project Structure

```
dictator/
├── main.py           # Menu bar app and hotkey handling
├── macos.py          # macOS permissions, clipboard and login item
├── audio.py          # Audio recording with sounddevice
├── transcriber.py    # Whisper transcription and model download
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

# Run tests
make test

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

## Models

The app supports two whisper.cpp models:

| Model | File | Size | Languages | Install command |
|-------|------|------|-----------|-----------------|
| Small (English) | `ggml-small.en.bin` | ~466MB | English only | `make install-model` |
| Medium (Multilingual) | `ggml-medium-q5_0.bin` | ~539MB | English, Dutch, Auto-detect | `make install-model-multilingual` |

`make build` downloads both. Otherwise the app downloads the model the
selected language needs at startup or when the language changes; the
status line shows "Downloading model..." meanwhile. The **Models** menu
downloads either one by hand.

- The **English-only** model is loaded when the language is set to English
- The **multilingual** model is loaded for Dutch or Auto-detect
- Both models use Metal GPU acceleration on Apple Silicon
- Models are stored in `~/.local/share/whisper-dictation/`

### Auto-detect

Auto-detect uses a two-pass approach: it first detects whether the audio is English or Dutch, then transcribes with that language forced. This prevents misdetection as similar-sounding languages (e.g. Danish). The multilingual model is required for auto-detect.

## Troubleshooting

### Hotkey not working, or nothing is pasted
- Check the **Permissions** menu, and see [Troubleshooting Permissions](#troubleshooting-permissions)
- Check `~/.config/dictator/dictator.log`
- Password managers and secure text fields can block global hotkeys while they are focused
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
