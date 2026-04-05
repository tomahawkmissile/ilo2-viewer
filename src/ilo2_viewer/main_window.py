"""Main application window for iLO2 Remote Console.

Ported from remcons.java - provides the toolbar, display widget, and manages
the connection lifecycle with keep-alive timers.
"""

from __future__ import annotations

import math

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QKeyEvent, QMouseEvent, QCursor, QPixmap
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QCheckBox, QComboBox, QLabel, QStatusBar, QMessageBox,
)

from .connection import Connection
from .display import DisplayWidget
from .input_handler import InputHandler

SESSION_TIMEOUT_DEFAULT = 900
KEEP_ALIVE_INTERVAL = 30


class MainWindow(QMainWindow):
    def __init__(self, hostname: str, params: dict[str, str]):
        super().__init__()
        self._hostname = hostname
        self._params = params

        self.setWindowTitle(f"{hostname} - iLO2")
        self.resize(1070, 880)

        # Display widget
        self._display = DisplayWidget()

        # Connection
        self._connection = Connection(self._display)
        self._connection.status_changed.connect(self._on_status_changed)
        self._connection.seized.connect(self._on_seized)

        # Parse parameters
        self._parse_params()

        # Status fields
        self._status_fields = ["", "Offline", "", "", ""]

        # Toolbar
        toolbar_widget = QWidget()
        toolbar_layout = QHBoxLayout(toolbar_widget)
        toolbar_layout.setContentsMargins(2, 2, 2, 2)

        self._btn_refresh = QPushButton("Refresh")
        self._btn_refresh.clicked.connect(self._on_refresh)
        toolbar_layout.addWidget(self._btn_refresh)

        self._btn_ctrl_alt_del = QPushButton("Ctrl-Alt-Del")
        self._btn_ctrl_alt_del.clicked.connect(self._on_ctrl_alt_del)
        toolbar_layout.addWidget(self._btn_ctrl_alt_del)

        self._chk_alt_lock = QCheckBox("Alt Lock")
        self._chk_alt_lock.stateChanged.connect(self._on_alt_lock)
        toolbar_layout.addWidget(self._chk_alt_lock)

        self._chk_hp_mouse = QCheckBox("High Performance Mouse")
        self._chk_hp_mouse.setChecked(self._hp_mouse_state)
        self._chk_hp_mouse.stateChanged.connect(self._on_hp_mouse)
        toolbar_layout.addWidget(self._chk_hp_mouse)

        toolbar_layout.addWidget(QLabel("Cursor:"))
        self._cmb_cursor = QComboBox()
        self._cmb_cursor.addItems(["Default", "Crosshairs", "Hidden", "Dot", "Outline"])
        self._cmb_cursor.currentTextChanged.connect(self._on_cursor_changed)
        toolbar_layout.addWidget(self._cmb_cursor)

        toolbar_layout.addWidget(QLabel("Locale:"))
        self._cmb_locale = QComboBox()
        locales = self._connection.input_handler.translator.get_locales()
        self._cmb_locale.addItems(locales)
        selected = self._connection.input_handler.translator.get_selected()
        if selected:
            idx = self._cmb_locale.findText(selected)
            if idx >= 0:
                self._cmb_locale.setCurrentIndex(idx)
        self._cmb_locale.currentTextChanged.connect(self._on_locale_changed)
        toolbar_layout.addWidget(self._cmb_locale)

        toolbar_layout.addStretch()

        # Main layout
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(toolbar_widget)
        layout.addWidget(self._display, 1)
        self.setCentralWidget(central)

        # Status bar
        self._statusbar = QStatusBar()
        self.setStatusBar(self._statusbar)
        self._statusbar.showMessage("Offline")

        # Keep-alive timer (30 seconds)
        self._keep_alive_timer = QTimer(self)
        self._keep_alive_timer.setInterval(KEEP_ALIVE_INTERVAL * 1000)
        self._keep_alive_timer.timeout.connect(self._on_keep_alive)

        # Session timeout
        self._session_timeout = self._timeout_seconds
        self._timeout_countdown = self._session_timeout

        # Install event filter on display for keyboard/mouse
        self._display.installEventFilter(self)

        # HP mouse warning shown once
        self._hp_mouse_warned = False

        # Cursor state
        self._current_cursor = Qt.CursorShape.ArrowCursor

    def start_session(self):
        """Connect to the iLO2 device and start the session."""
        login = self._build_login()
        self._connection.connect(
            self._hostname, login, self._port,
            self._ts_param, self._terminal_services_port,
        )
        self._keep_alive_timer.start()
        self._timeout_countdown = self._session_timeout

    def stop_session(self):
        self._keep_alive_timer.stop()
        self._connection.disconnect()

    def closeEvent(self, event):
        self.stop_session()
        super().closeEvent(event)

    # --- Parameter parsing ---
    def _parse_params(self):
        p = self._params

        self._port = int(p.get("INFO6", "23") or "23")
        self._mouse_mode = int(p.get("INFOM", "0") or "0")
        self._hp_mouse_state = int(p.get("INFOMM", "0") or "0") == 1

        timeout_min = int(p.get("INFO7", "15") or "15")
        self._timeout_seconds = timeout_min * 60

        # Encryption
        enc_enabled = int(p.get("INFOA", "0") or "0") == 1
        if enc_enabled:
            decrypt_key_hex = p.get("INFOB", "")
            encrypt_key_hex = p.get("INFOC", "")
            key_index = int(p.get("INFOD", "0") or "0")

            if decrypt_key_hex:
                dk = bytes(int(decrypt_key_hex[i:i+2], 16) for i in range(0, 32, 2))
                self._connection.setup_decryption(dk)
            if encrypt_key_hex:
                ek = bytes(int(encrypt_key_hex[i:i+2], 16) for i in range(0, 32, 2))
                self._connection.setup_encryption(ek, key_index)

        self._connection.input_handler.set_mouse_protocol(self._mouse_mode)

        # Terminal services
        infon = int(p.get("INFON", "0") or "0")
        self._ts_param = infon & 0xFF00
        ts_low = infon & 0xFF
        self._launch_ts = ts_low >= 2
        if ts_low == 0:
            self._ts_param |= 1
        self._terminal_services_port = int(p.get("INFOO", "3389") or "3389")

    def _build_login(self) -> str:
        """Build the login escape sequence from INFO0/INFO1 parameters."""
        info0 = self._params.get("INFO0", "")
        login = self._parse_login(info0)

        if login:
            info1 = self._params.get("INFO1")
            if info1 is not None:
                login = f"\033[4{login}"
            login = f"\033[7\033[9{login}"

        return login

    def _parse_login(self, info0: str) -> str:
        """Parse the login credential string."""
        if info0.startswith("Compaq-RIB-Login="):
            result = "\033[!"
            try:
                result += info0[17:73]
                result += "\r"
                result += info0[74:106]
                result += "\r"
            except IndexError:
                return ""
            return result
        return self._base64_decode(info0)

    @staticmethod
    def _base64_decode(s: str) -> str:
        """Custom base64 decode matching the Java implementation."""
        BASE64 = (
            [0]*43 + [62] + [0]*3 + [63]
            + list(range(52, 62)) + [0]*4
            + list(range(0, 26)) + [0]*6
            + list(range(26, 52)) + [0]*5
        )

        result = []
        n = 0
        done = False

        while n + 3 < len(s) and not done:
            i = BASE64[ord(s[n]) & 0x7F]
            j = BASE64[ord(s[n+1]) & 0x7F]
            k = BASE64[ord(s[n+2]) & 0x7F]
            m_val = BASE64[ord(s[n+3]) & 0x7F]

            c1 = ((i << 2) + (j >> 4)) & 0xFF
            c2 = ((j << 4) + (k >> 2)) & 0xFF
            c3 = ((k << 6) + m_val) & 0xFF

            if c1 == ord(":"):
                c1 = ord("\r")
            if c2 == ord(":"):
                c2 = ord("\r")
            if c3 == ord(":"):
                c3 = ord("\r")

            result.append(chr(c1))

            if s[n+2] == "=":
                done = True
            else:
                result.append(chr(c2))

            if s[n+3] == "=":
                done = True
            else:
                result.append(chr(c3))

            n += 4

        if result:
            result.append("\r")
        return "".join(result)

    # --- Event filter for keyboard/mouse on display widget ---
    def eventFilter(self, obj, event):
        if obj is not self._display:
            return super().eventFilter(obj, event)

        if isinstance(event, QKeyEvent):
            if event.type() == QKeyEvent.Type.KeyPress:
                seq = self._connection.input_handler.translate_special_key(
                    event.key(), event.modifiers()
                )
                if not seq:
                    text = event.text()
                    if text:
                        seq = self._connection.input_handler.translate_key(
                            event.key(), text, event.modifiers()
                        )
                if seq:
                    self._connection.transmit_str(seq)
                return True

            elif event.type() == QKeyEvent.Type.KeyRelease:
                seq = self._connection.input_handler.translate_key_release(
                    event.key(), event.modifiers()
                )
                if seq:
                    self._connection.transmit_str(seq)
                return True

        elif isinstance(event, QMouseEvent):
            x = int(event.position().x())
            y = int(event.position().y())
            btn = event.button()
            mods = int(event.modifiers())

            if event.type() == QMouseEvent.Type.MouseButtonPress:
                self._connection.mouse_sync.mouse_pressed(x, y, btn, mods)
                return True
            elif event.type() == QMouseEvent.Type.MouseButtonRelease:
                self._connection.mouse_sync.mouse_released(x, y, btn, mods)
                # Handle click
                self._connection.mouse_sync.mouse_clicked(x, y, btn, mods)
                return True
            elif event.type() == QMouseEvent.Type.MouseMove:
                if event.buttons():
                    self._connection.mouse_sync.mouse_dragged(x, y, btn, mods)
                else:
                    self._connection.mouse_sync.mouse_moved(x, y, mods)
                return True

        return super().eventFilter(obj, event)

    # --- Toolbar callbacks ---
    def _on_refresh(self):
        self._connection.refresh_screen()
        self._display.setFocus()

    def _on_ctrl_alt_del(self):
        self._connection.transmit_str(InputHandler.build_ctrl_alt_del())
        self._display.setFocus()

    def _on_alt_lock(self, state):
        if state:
            self._connection.input_handler.enable_altlock()
        else:
            self._connection.input_handler.disable_altlock()
        self._display.setFocus()

    def _on_hp_mouse(self, state):
        if not self._hp_mouse_warned:
            self._hp_mouse_warned = True
            reply = QMessageBox.question(
                self, "High Performance Mouse",
                "The High Performance Mouse is supported natively on "
                "Microsoft Windows Server 2000 SP3 or later and Windows 2003 or later. "
                "Linux users should enable the High-Performance Mouse option once the "
                "HP iLO2 High-Performance Mouse for Linux driver is installed.\n\n"
                "Continue?",
                QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
            )
            if reply != QMessageBox.StandardButton.Ok:
                self._chk_hp_mouse.setChecked(self._hp_mouse_state)
                return

        self._hp_mouse_state = bool(state)
        self._connection.transmit_bytes(
            InputHandler.build_mouse_mode_change(self._hp_mouse_state)
        )

    def _on_cursor_changed(self, text: str):
        cursor_map = {
            "Default": Qt.CursorShape.ArrowCursor,
            "Crosshairs": Qt.CursorShape.CrossCursor,
            "Hidden": Qt.CursorShape.BlankCursor,
            "Dot": Qt.CursorShape.CrossCursor,
            "Outline": Qt.CursorShape.ArrowCursor,
        }
        self._current_cursor = cursor_map.get(text, Qt.CursorShape.ArrowCursor)
        self._display.setCursor(QCursor(self._current_cursor))

    def _on_locale_changed(self, text: str):
        self._connection.input_handler.set_locale(text)

    # --- Keep-alive ---
    def _on_keep_alive(self):
        self._timeout_countdown -= KEEP_ALIVE_INTERVAL
        self._connection.send_auto_alive()

        if self._timeout_countdown <= 0:
            print("Session timeout reached")

    # --- Status ---
    def _on_status_changed(self, field: int, message: str):
        if 0 <= field < len(self._status_fields):
            self._status_fields[field] = message
        status = " ".join(self._status_fields[:4])
        self._statusbar.showMessage(status)

    def _on_seized(self):
        QMessageBox.warning(self, "Session Seized",
                           "Session has been acquired by another user.")
