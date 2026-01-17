# Contributing to Dictator

Thank you for your interest in contributing to Dictator! This document provides guidelines for contributions.

## How to Contribute

### Reporting Bugs

1. Check the [existing issues](https://github.com/albertsikkema/dictator/issues) to avoid duplicates
2. Use the bug report template when creating a new issue
3. Include:
   - macOS version
   - Apple Silicon or Intel Mac
   - Steps to reproduce
   - Expected vs actual behavior
   - Relevant log output from `~/.config/dictator/dictator.log`

### Suggesting Features

1. Open an issue using the feature request template
2. Describe the use case and expected behavior
3. Consider if the feature fits the app's minimal, focused design

### Submitting Changes

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature-name`
3. Make your changes
4. Run linting: `make lint`
5. Run formatting: `make format`
6. Test your changes: `make run`
7. Commit with a clear message
8. Open a pull request

## Development Setup

```bash
# Clone your fork
git clone https://github.com/YOUR_USERNAME/dictator.git
cd dictator

# Install dependencies
uv sync

# Download whisper model
make install-model

# Run from source
make run
```

## Code Style

- Follow existing code patterns
- Run `make lint` and `make format` before committing
- Keep changes focused and minimal

## License

By contributing, you agree that your contributions will be licensed under the MIT License with Commons Clause.
