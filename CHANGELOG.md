# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Permissions menu showing Accessibility, Input Monitoring and Microphone, with links to System Settings; missing permissions are requested at startup
- Models menu to download missing whisper models
- The app downloads the model the selected language needs when it is missing
- `make build` downloads both models if missing; `make install-models`
- Copy Last Transcription menu item
- `make reset-permissions`

### Changed

- Builds are signed with a stable self-signed certificate when available, so permissions survive rebuilds
- The clipboard is restored after pasting
- Start at Login uses a macOS login item instead of a Launch Agent; the old Launch Agent is migrated
- Errors and missing permissions are shown in the menu status line

### Fixed

- Key presses are no longer written to the log file
- The hotkey stopped working when macOS disabled a slow key listener
- Ctrl+Shift+L kept cycling the language
- Menu bar updates from background threads
- Duplicate listener watchdogs after changing the hotkey
- Bundle version in Info.plist
- Configs from before the language setting keep using English

## [1.0.3] - 2026-01-17

### Fixed

- Added macOS entitlements file for proper Accessibility and Microphone permissions
- Enabled ad-hoc code signing in PyInstaller build for reliable permission handling
- Fixed app bundle copying to preserve symlinks and code signatures (using `ditto` instead of `cp`)

## [1.0.2] - 2026-01-17

### Changed

- Simplified release process to create DMG only (removed ZIP from releases)

### Fixed

- Updated permissions section in README for clarity and troubleshooting

## [1.0.1] - 2026-01-17

### Fixed

- Updated version number in pyproject.toml

## [1.0.0] - 2026-01-17

### Added

- macOS menu bar push-to-talk speech-to-text application
- Audio recording via sounddevice with real-time level monitoring
- Whisper.cpp integration for local speech recognition via pywhispercpp
- Configurable global hotkey (default: Right Option key)
- Automatic clipboard copy and paste of transcribed text
- Menu bar icon with audio level animation feedback
- Lazy model loading for fast app startup
- Hotkey listener with auto-restart watchdog
- PyInstaller bundling for standalone macOS app
- Configuration stored in `~/.config/dictator/config.json`
- Debug logging to `~/.config/dictator/dictator.log`
- GitHub release workflow for automated releases
- Community files (LICENSE, CODE_OF_CONDUCT, SECURITY, CONTRIBUTING)

[Unreleased]: https://github.com/albertsikkema/dictator/compare/v1.0.3...HEAD
[1.0.3]: https://github.com/albertsikkema/dictator/compare/v1.0.2...v1.0.3
[1.0.2]: https://github.com/albertsikkema/dictator/compare/v1.0.1...v1.0.2
[1.0.1]: https://github.com/albertsikkema/dictator/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/albertsikkema/dictator/releases/tag/v1.0.0
