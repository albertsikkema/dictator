# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/albertsikkema/dictator/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/albertsikkema/dictator/releases/tag/v1.0.0
