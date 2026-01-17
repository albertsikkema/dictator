# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability in Dictator, please report it responsibly:

1. **Do not** open a public GitHub issue
2. Use [GitHub's private vulnerability reporting](https://github.com/albertsikkema/dictator/security/advisories/new)
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

You will receive a response acknowledging your report. We will work with you to understand and address the issue.

## Security Considerations

Dictator is a local-only application that:
- Records audio only when the hotkey is held
- Processes all audio locally using whisper.cpp
- Does not transmit any data over the network
- Stores settings locally in `~/.config/dictator/`

### Permissions Required

- **Microphone**: For audio recording
- **Accessibility**: For global hotkey detection and clipboard paste

These permissions are necessary for core functionality and are used only for their stated purposes.
