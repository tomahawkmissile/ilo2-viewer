"""Keyboard and mouse input handling for iLO2 remote console.

Ported from cim.java - translates Qt key/mouse events into iLO2 escape sequences
and telnet commands.
"""

from __future__ import annotations

from PySide6.QtCore import Qt

from .locale_translator import LocaleTranslator

ESC = "\033"

# F-key mappings: (normal, shift, ctrl, alt) for F1-F12
_FKEY_MAP = {
    Qt.Key.Key_F1:  (f"{ESC}[M", f"{ESC}[Y", f"{ESC}[k", f"{ESC}[w"),
    Qt.Key.Key_F2:  (f"{ESC}[N", f"{ESC}[Z", f"{ESC}[l", f"{ESC}[x"),
    Qt.Key.Key_F3:  (f"{ESC}[O", f"{ESC}[a", f"{ESC}[m", f"{ESC}[y"),
    Qt.Key.Key_F4:  (f"{ESC}[P", f"{ESC}[b", f"{ESC}[n", f"{ESC}[z"),
    Qt.Key.Key_F5:  (f"{ESC}[Q", f"{ESC}[c", f"{ESC}[o", f"{ESC}[@"),
    Qt.Key.Key_F6:  (f"{ESC}[R", f"{ESC}[d", f"{ESC}[p", f"{ESC}[["),
    Qt.Key.Key_F7:  (f"{ESC}[S", f"{ESC}[e", f"{ESC}[q", f"{ESC}[\\"),
    Qt.Key.Key_F8:  (f"{ESC}[T", f"{ESC}[f", f"{ESC}[r", f"{ESC}[]"),
    Qt.Key.Key_F9:  (f"{ESC}[U", f"{ESC}[g", f"{ESC}[s", f"{ESC}[^"),
    Qt.Key.Key_F10: (f"{ESC}[V", f"{ESC}[h", f"{ESC}[t", f"{ESC}[_"),
    Qt.Key.Key_F11: (f"{ESC}[W", f"{ESC}[i", f"{ESC}[u", f"{ESC}[`"),
    Qt.Key.Key_F12: (f"{ESC}[X", f"{ESC}[j", f"{ESC}[v", f"{ESC}['"),
}

# Navigation key mappings
_NAV_MAP = {
    Qt.Key.Key_Home:     f"{ESC}[H",
    Qt.Key.Key_End:      f"{ESC}[F",
    Qt.Key.Key_PageUp:   f"{ESC}[I",
    Qt.Key.Key_PageDown: f"{ESC}[G",
    Qt.Key.Key_Insert:   f"{ESC}[L",
    Qt.Key.Key_Up:       f"{ESC}[A",
    Qt.Key.Key_Down:     f"{ESC}[B",
    Qt.Key.Key_Left:     f"{ESC}[D",
    Qt.Key.Key_Right:    f"{ESC}[C",
}

# Telnet IAC commands
TELNET_IAC = 0xFF
CMD_MOUSE_MOVE = 0xD0
CMD_BUTTON_PRESS = 0xD1
CMD_BUTTON_RELEASE = 0xD2
CMD_BUTTON_CLICK = 0xD3
CMD_BYTE = 0xD4
CMD_SET_MODE = 0xD5
MOUSE_USBABS = 1
MOUSE_USBREL = 2


def _modifier_index(modifiers) -> int:
    """Return modifier index: 0=none, 1=shift, 2=ctrl, 3=alt."""
    if modifiers & Qt.KeyboardModifier.ShiftModifier:
        return 1
    elif modifiers & Qt.KeyboardModifier.ControlModifier:
        return 2
    elif modifiers & Qt.KeyboardModifier.AltModifier:
        return 3
    return 0


class InputHandler:
    def __init__(self):
        self._translator = LocaleTranslator()
        self._kbd_disabled = False
        self._altlock = False
        self._ignore_next_key = False
        self._mouse_protocol = 0
        self._screen_x = 1
        self._screen_y = 1

    @property
    def translator(self) -> LocaleTranslator:
        return self._translator

    def set_locale(self, name: str):
        self._translator.select_locale(name)

    def set_mouse_protocol(self, protocol: int):
        self._mouse_protocol = protocol

    def set_screen_size(self, x: int, y: int):
        self._screen_x = x
        self._screen_y = y

    def enable_altlock(self):
        self._altlock = True

    def disable_altlock(self):
        self._altlock = False

    def enable_keyboard(self):
        self._kbd_disabled = False

    def disable_keyboard(self):
        self._kbd_disabled = True

    def translate_key(self, key: int, text: str, modifiers) -> str:
        """Translate a keyTyped event to an iLO2 escape sequence."""
        if self._kbd_disabled:
            return ""
        if self._ignore_next_key:
            self._ignore_next_key = False
            return ""

        mod_idx = _modifier_index(modifiers)
        if self._altlock and mod_idx == 0:
            mod_idx = 3

        char = text[0] if text else ""
        apply_alt_prefix = True

        # Escape
        if char == "\x1b":
            apply_alt_prefix = False
            return ""

        # Enter/Return
        if char in ("\n", "\r"):
            apply_alt_prefix = False
            if mod_idx == 0:
                return "\r"
            elif mod_idx == 1:
                return f"{ESC}[3\r"
            elif mod_idx == 2:
                return "\n"
            elif mod_idx == 3:
                return f"{ESC}[1\r"

        # Backspace
        if char == "\x08":
            apply_alt_prefix = False
            if mod_idx == 0:
                return "\b"
            elif mod_idx == 1:
                return f"{ESC}[3\b"
            elif mod_idx == 2:
                return ""
            elif mod_idx == 3:
                return f"{ESC}[1\b"

        # Default: use locale translator
        result = self._translator.translate(char) if char else ""

        if apply_alt_prefix and result and mod_idx == 3:
            result = f"{ESC}[1{result}"

        return result

    def translate_special_key(self, key: int, modifiers) -> str:
        """Translate a keyPressed event for special keys."""
        if self._kbd_disabled:
            return ""

        mod_idx = _modifier_index(modifiers)
        if self._altlock and not (modifiers & Qt.KeyboardModifier.AltModifier):
            if mod_idx == 0:
                mod_idx = 3

        result = ""
        needs_modifier_prefix = True

        # Escape
        if key == Qt.Key.Key_Escape:
            return f"{ESC}"

        # Tab
        if key == Qt.Key.Key_Tab:
            return "\t"

        # Delete
        if key == Qt.Key.Key_Delete:
            if (modifiers & Qt.KeyboardModifier.ControlModifier) and (
                self._altlock or (modifiers & Qt.KeyboardModifier.AltModifier)
            ):
                return f"{ESC}[2{ESC}["  # Ctrl-Alt-Del
            return ""

        # F-keys
        if key in _FKEY_MAP:
            return _FKEY_MAP[key][mod_idx]

        # Navigation keys
        if key in _NAV_MAP:
            result = _NAV_MAP[key]
        else:
            needs_modifier_prefix = False

        if result and needs_modifier_prefix:
            if mod_idx == 1:
                result = f"{ESC}[3{result}"
            elif mod_idx == 2:
                result = f"{ESC}[2{result}"
            elif mod_idx == 3:
                result = f"{ESC}[1{result}"

        return result

    def translate_key_release(self, key: int, modifiers) -> str:
        """Translate a keyReleased event (for IME/special key releases)."""
        i = 0
        if modifiers & Qt.KeyboardModifier.ShiftModifier:
            i = 1
        if self._altlock or (modifiers & Qt.KeyboardModifier.AltModifier):
            i += 2
        if modifiers & Qt.KeyboardModifier.ControlModifier:
            i += 4

        # Handle special key codes for IME
        if key in (243, 244, 263):
            i += 128
        elif key == 29:
            i += 136
        elif key in (28, 256, 257):
            i += 144
        elif key in (241, 242, 245):
            i += 152

        if i > 127:
            return chr(i)
        return ""

    def build_mouse_move(self, dx: int, dy: int, client_x: int, client_y: int) -> bytes:
        """Build a mouse move command."""
        dx = max(-128, min(127, dx))
        dy = max(-128, min(127, dy))

        if self._screen_x > 0 and self._screen_y > 0:
            abs_x = 3000 * client_x // self._screen_x
            abs_y = 3000 * client_y // self._screen_y
        else:
            abs_x = 3000 * client_x
            abs_y = 3000 * client_y

        if self._mouse_protocol == 0:
            return bytes([TELNET_IAC, CMD_MOUSE_MOVE, dx & 0xFF, dy & 0xFF])
        else:
            return bytes([
                TELNET_IAC, CMD_MOUSE_MOVE,
                dx & 0xFF, dy & 0xFF,
                (abs_x >> 8) & 0xFF, abs_x & 0xFF,
                (abs_y >> 8) & 0xFF, abs_y & 0xFF,
            ])

    @staticmethod
    def build_mouse_press(button: int) -> bytes:
        return bytes([TELNET_IAC, CMD_BUTTON_PRESS, button & 0xFF])

    @staticmethod
    def build_mouse_release(button: int) -> bytes:
        return bytes([TELNET_IAC, CMD_BUTTON_RELEASE, button & 0xFF])

    @staticmethod
    def build_mouse_click(button: int, count: int = 1) -> bytes:
        return bytes([TELNET_IAC, CMD_BUTTON_CLICK, button & 0xFF, count & 0xFF])

    @staticmethod
    def build_mouse_mode_change(absolute: bool) -> bytes:
        mode = MOUSE_USBABS if absolute else MOUSE_USBREL
        return bytes([TELNET_IAC, CMD_SET_MODE, mode])

    @staticmethod
    def build_ctrl_alt_del() -> str:
        return f"{ESC}[2{ESC}["

    @staticmethod
    def build_refresh_screen() -> str:
        return f"{ESC}[~"

    @staticmethod
    def build_keep_alive() -> str:
        return f"{ESC}[("

    @staticmethod
    def build_auto_alive() -> str:
        return f"{ESC}[&"
