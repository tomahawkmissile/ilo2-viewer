"""Telnet/socket connection layer for iLO2 remote console.

Ported from telnet.java + cim.java connection parts.
Handles the raw socket, DVC mode detection, RC4 encryption, and the receiver thread.
"""

from __future__ import annotations

import socket
import threading
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Signal

from .rc4 import RC4
from .dvc import DVCDecoder
from .input_handler import InputHandler
from .mouse_sync import MouseSync

if TYPE_CHECKING:
    from .display import DisplayWidget

TELNET_IAC = 0xFF
TELNET_ENCRYPT = 0xC0
TELNET_CHG_ENCRYPT_KEYS = 0xC1
CMD_TS_AVAIL = 0xC2
CMD_TS_NOT_AVAIL = 0xC3
CMD_TS_STARTED = 0xC4
CMD_TS_STOPPED = 0xC5


class Connection(QObject):
    """Manages the telnet socket connection to iLO2."""

    status_changed = Signal(int, str)  # (field_index, message)
    seized = Signal()
    disconnected_signal = Signal()

    def __init__(self, screen: DisplayWidget, parent=None):
        super().__init__(parent)
        self._screen = screen
        self._socket: socket.socket | None = None
        self._receiver_thread: threading.Thread | None = None
        self._connected = False
        self._host = ""
        self._port = 23
        self._login = ""

        # Encryption
        self._rc4_decrypter: RC4 | None = None
        self._rc4_encrypter: RC4 | None = None
        self._encryption_enabled = False
        self._encryption_active = False
        self._sending_encrypt_command = False
        self._key_index = 0

        # DVC
        self._dvc_mode = False
        self._dvc_encryption = False
        self._dvc = DVCDecoder(screen)

        # Input handling
        self.input_handler = InputHandler()
        self.mouse_sync = MouseSync()
        self.mouse_sync.set_listener(self)

        # Wire DVC callbacks
        self._dvc.on_change_key = self._change_key
        self._dvc.on_seize = self._on_seize
        self._dvc.on_refresh_screen = self.refresh_screen
        self._dvc.on_set_status = lambda f, m: self.status_changed.emit(f, m)
        self._dvc.on_start_rdp = lambda ts: None  # RDP not ported
        self._dvc.on_stop_rdp = lambda: None

        self._lock = threading.Lock()

    def setup_encryption(self, encrypt_key: bytes, key_index: int):
        self._rc4_encrypter = RC4(encrypt_key)
        self._key_index = key_index

    def setup_decryption(self, decrypt_key: bytes):
        self._rc4_decrypter = RC4(decrypt_key)
        self._encryption_enabled = True

    def connect(self, host: str, login: str, port: int = 23,
                ts_param: int = 0, ts_port: int = 3389):
        if self._connected:
            return

        self._host = host
        self._port = port

        # Prepend encryption start command if enabled
        if self._encryption_enabled:
            login = f"\xff\xc0    {login}"
            self._encryption_active = True
            self._sending_encrypt_command = True

        self._login = login
        self._screen.start_updates()
        self._connected = True

        self.status_changed.emit(1, "Connecting")

        try:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER,
                                     bytes([1, 0, 0, 0, 0, 0, 0, 0]))
            self._socket.connect((self._host, self._port))
            self.status_changed.emit(1, "Online")

            self._receiver_thread = threading.Thread(
                target=self._receiver_loop, daemon=True, name="telnet_rcvr"
            )
            self._receiver_thread.start()

            self.transmit_str(self._login)
        except Exception as e:
            print(f"Connection error: {e}")
            self.status_changed.emit(1, str(e))
            self._cleanup()

    def disconnect(self):
        if not self._connected:
            return
        self._screen.stop_updates()
        self._connected = False

        if self._socket:
            try:
                self._socket.close()
            except Exception as e:
                print(f"Disconnect error: {e}")
        self._socket = None
        self._dvc_mode = False
        self.status_changed.emit(1, "Offline")
        self.status_changed.emit(2, "")
        self.status_changed.emit(3, "")
        self.disconnected_signal.emit()

    def transmit_str(self, data: str):
        """Transmit a string, applying RC4 encryption if active."""
        if not self._socket or not data:
            return

        raw = bytearray(len(data))

        with self._lock:
            if self._encryption_active and self._rc4_encrypter:
                if self._sending_encrypt_command:
                    raw[0] = ord(data[0]) & 0xFF
                    raw[1] = ord(data[1]) & 0xFF
                    raw[2] = (self._key_index >> 24) & 0xFF
                    raw[3] = (self._key_index >> 16) & 0xFF
                    raw[4] = (self._key_index >> 8) & 0xFF
                    raw[5] = self._key_index & 0xFF
                    for i in range(6, len(data)):
                        raw[i] = (ord(data[i]) ^ self._rc4_encrypter.random_value()) & 0xFF
                    self._sending_encrypt_command = False
                else:
                    for i in range(len(data)):
                        raw[i] = (ord(data[i]) ^ self._rc4_encrypter.random_value()) & 0xFF
            else:
                for i in range(len(data)):
                    raw[i] = ord(data[i]) & 0xFF

        self._send_raw(bytes(raw))

    def transmit_bytes(self, data: bytes):
        """Transmit raw bytes, applying RC4 encryption if active."""
        if not self._socket or not data:
            return

        out = bytearray(len(data))

        with self._lock:
            if self._encryption_active and self._rc4_encrypter:
                if self._sending_encrypt_command:
                    out[0] = data[0]
                    out[1] = data[1]
                    out[2] = (self._key_index >> 24) & 0xFF
                    out[3] = (self._key_index >> 16) & 0xFF
                    out[4] = (self._key_index >> 8) & 0xFF
                    out[5] = self._key_index & 0xFF
                    for i in range(6, len(data)):
                        out[i] = (data[i] ^ self._rc4_encrypter.random_value()) & 0xFF
                    self._sending_encrypt_command = False
                else:
                    for i in range(len(data)):
                        out[i] = (data[i] ^ self._rc4_encrypter.random_value()) & 0xFF
            else:
                out[:] = data

        self._send_raw(bytes(out))

    def _send_raw(self, data: bytes):
        if self._socket:
            try:
                self._socket.sendall(data)
            except Exception as e:
                print(f"Transmit error: {e}")

    def refresh_screen(self):
        self.transmit_str("\033[~")

    def send_keep_alive(self):
        self.transmit_str("\033[(")

    def send_auto_alive(self):
        self.transmit_str("\033[&")

    # MouseSyncListener interface
    def server_move(self, dx: int, dy: int, client_x: int, client_y: int):
        data = self.input_handler.build_mouse_move(dx, dy, client_x, client_y)
        self.transmit_bytes(data)

    def server_press(self, button: int):
        self.transmit_bytes(InputHandler.build_mouse_press(button))

    def server_release(self, button: int):
        self.transmit_bytes(InputHandler.build_mouse_release(button))

    def server_click(self, button: int, count: int):
        self.transmit_bytes(InputHandler.build_mouse_click(button, count))

    def _change_key(self):
        """Called by DVC firmware command 9 - rotate encryption keys."""
        with self._lock:
            if self._rc4_encrypter:
                self._rc4_encrypter.update_key()
            if self._rc4_decrypter:
                self._rc4_decrypter.update_key()

    def _on_seize(self):
        """Called by DVC firmware command 10 - session seized."""
        self._screen.show_text("Session Acquired by another user.")
        self.status_changed.emit(1, "Offline")
        self.disconnect()
        self.seized.emit()

    def _receiver_loop(self):
        """Main receiver thread - reads data from socket and processes DVC."""
        self._screen.show_text("Connecting")
        esc_state = 0  # 0=none, 1=got ESC, 2=got ESC[

        try:
            while self._connected:
                if not self._socket:
                    break

                self._socket.settimeout(1.0)
                try:
                    data = self._socket.recv(1024)
                except socket.timeout:
                    continue
                except Exception as e:
                    print(f"Receiver error: {e}")
                    break

                if not data:
                    break

                for byte in data:
                    c = byte & 0xFF

                    if self._dvc_mode:
                        # Decrypt if needed
                        if self._dvc_encryption and self._rc4_decrypter:
                            c ^= self._rc4_decrypter.random_value()
                            c &= 0xFF

                        self._dvc_mode = self._dvc.process_dvc(c)
                        if not self._dvc_mode:
                            print("DVC mode turned off")
                            self.status_changed.emit(1, "DVC Mode off")

                        # Update input handler screen size from DVC
                        self.input_handler.set_screen_size(
                            self._dvc.screen_x, self._dvc.screen_y
                        )
                    else:
                        # Detect DVC mode via ESC[R or ESC[r
                        if c == 0x1B:  # ESC
                            esc_state = 1
                        elif esc_state == 1 and c == 0x5B:  # [
                            esc_state = 2
                        elif esc_state == 2 and c == ord("R"):
                            self._dvc_mode = True
                            self._dvc_encryption = True
                            self.status_changed.emit(1, "DVC Mode (RC4-128 bit)")
                            esc_state = 0
                        elif esc_state == 2 and c == ord("r"):
                            self._dvc_mode = True
                            self._dvc_encryption = False
                            self.status_changed.emit(1, "DVC Mode (no encryption)")
                            esc_state = 0
                        else:
                            esc_state = 0

        except Exception as e:
            print(f"Receiver exception: {e}")
        finally:
            if self._connected:
                self._screen.show_text("Offline")
                self.status_changed.emit(1, "Offline")
                self.disconnect()

    def _cleanup(self):
        self._socket = None
        self._connected = False
        self._dvc_mode = False
