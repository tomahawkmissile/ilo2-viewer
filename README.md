# iLO2 Viewer

A modern Python remote console client for HP Integrated Lights-Out 2 (iLO2) devices, served as a web application.

This is a port of ILO2-Standalone-Remote-Console from Java Swing to Python. The video console is streamed to your browser over WebSocket.

## Features

- Remote video console via HP's proprietary DVC protocol
- Web-based UI — works in any browser, no display server needed
- Keyboard and mouse input with locale translation (18 layouts)
- RC4-128 session encryption
- IPMI power control (on, off, reset, graceful shutdown)
- TLSv1.0 support via pyOpenSSL (required for legacy iLO2 firmware)
- Cookie-based session persistence
- Clean disconnect on Ctrl-C (frees iLO2 session slot)

## Requirements

- Python 3.10+
- A browser

## Installation

```bash
python -m venv venv
source venv/bin/activate
pip install aiohttp requests pyOpenSSL numpy Pillow pyghmi
```

## Usage

```bash
# Direct credentials
PYTHONPATH=src python -m ilo2_viewer <hostname> <username> <password>

# Config file
PYTHONPATH=src python -m ilo2_viewer -c config.ini

# Custom port (default: 8080)
PYTHONPATH=src python -m ilo2_viewer -p 9000 <hostname> <username> <password>
```

Then open `http://localhost:8080` in your browser. Press `Ctrl-C` to disconnect cleanly.

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
  ssl_config.py        TLS 1.0 via pyOpenSSL for legacy iLO2 firmware
  web_server.py        aiohttp web server + WebSocket video/input relay
  connection.py        Telnet socket, receiver thread, RC4 encrypt/decrypt
  dvc.py               DVC video decoder (48-state Huffman-like state machine)
  display.py           Headless framebuffer with JPEG encoding
  input_handler.py     Keyboard/mouse event translation to iLO2 escape sequences
  mouse_sync.py        Mouse synchronization and calibration state machine
  locale_translator.py Keyboard layout mappings for 18 locales
  rc4.py               RC4 stream cipher with MD5 key derivation
  power.py             IPMI power control via pyghmi
  static/index.html    Browser client (canvas + WebSocket)
```

## Notes

- iLO2 firmware uses TLSv1.0 with legacy renegotiation and self-signed certificates. pyOpenSSL is used to bypass OpenSSL 3.0+ restrictions.
- Tested against iLO2 firmware v2.33. Later iLO generations (iLO3+) use different protocols and are not supported.
- Works on WSL2 without a display server since the UI is browser-based.
