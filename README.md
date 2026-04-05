# iLO2 Viewer

A modern Python/Qt remote console client for HP Integrated Lights-Out 2 (iLO2) devices.

This is a port of [ILO2-Standalone-Remote-Console](https://github.com/perjg/ILO2-Standalone-Remote-Console) from Java Swing to Python using PySide6.

## Features

- Remote video console via HP's proprietary DVC protocol
- Keyboard and mouse input with locale translation (18 layouts)
- RC4-128 session encryption
- High-performance mouse mode (USB absolute)
- Cookie-based session persistence
- Custom cursor styles

## Requirements

- Python 3.10+
- PySide6
- requests
- numpy

## Installation

```bash
python -m venv venv
source venv/bin/activate
pip install PySide6 requests numpy
```

## Usage

```bash
# Direct credentials
PYTHONPATH=src python -m ilo2_viewer <hostname> <username> <password>

# Config file
PYTHONPATH=src python -m ilo2_viewer -c config.ini

# Default config (reads ./config.ini)
PYTHONPATH=src python -m ilo2_viewer
```

### Config file format

```ini
[ilo2]
hostname = 192.168.1.100
username = Administrator
password = secret
```

See `config_template.ini` for a template.

## Architecture

```
src/ilo2_viewer/
  __main__.py          CLI entry point and auth flow
  auth.py              3-stage HTTPS authentication
  ssl_config.py        TLS bypass for legacy iLO2 firmware
  connection.py        Telnet socket, receiver thread, RC4 encrypt/decrypt
  dvc.py               DVC video decoder (48-state Huffman-like state machine)
  display.py           Qt video widget with numpy framebuffer
  input_handler.py     Keyboard/mouse event translation to iLO2 escape sequences
  mouse_sync.py        Mouse synchronization and calibration state machine
  locale_translator.py Keyboard layout mappings for 18 locales
  rc4.py               RC4 stream cipher with MD5 key derivation
  main_window.py       Main window, toolbar, and session lifecycle
```

## Notes

- iLO2 firmware uses outdated TLS ciphers and self-signed certificates. Certificate verification is intentionally disabled.
- Tested against iLO2 firmware v2.33. Later iLO generations (iLO3+) use different protocols and are not supported.
- The original Java version hangs on Java 15+; this Python port has no such limitation.
