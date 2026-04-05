"""Keyboard and mouse input handling for iLO2 remote console.

Translates web keyboard/mouse events (JavaScript key codes) into
iLO2 escape sequences and telnet commands.
"""

from __future__ import annotations

from .locale_translator import LocaleTranslator

ESC = "\033"

# F-key mappings: (normal, shift, ctrl, alt) for F1-F12
_FKEY_MAP = {
    "F1":  (f"{ESC}[M", f"{ESC}[Y", f"{ESC}[k", f"{ESC}[w"),
    "F2":  (f"{ESC}[N", f"{ESC}[Z", f"{ESC}[l", f"{ESC}[x"),
    "F3":  (f"{ESC}[O", f"{ESC}[a", f"{ESC}[m", f"{ESC}[y"),
    "F4":  (f"{ESC}[P", f"{ESC}[b", f"{ESC}[n", f"{ESC}[z"),
    "F5":  (f"{ESC}[Q", f"{ESC}[c", f"{ESC}[o", f"{ESC}[@"),
    "F6":  (f"{ESC}[R", f"{ESC}[d", f"{ESC}[p", f"{ESC}[["),
    "F7":  (f"{ESC}[S", f"{ESC}[e", f"{ESC}[q", f"{ESC}[\\"),
    "F8":  (f"{ESC}[T", f"{ESC}[f", f"{ESC}[r", f"{ESC}[]"),
    "F9":  (f"{ESC}[U", f"{ESC}[g", f"{ESC}[s", f"{ESC}[^"),
    "F10": (f"{ESC}[V", f"{ESC}[h", f"{ESC}[t", f"{ESC}[_"),
    "F11": (f"{ESC}[W", f"{ESC}[i", f"{ESC}[u", f"{ESC}[`"),
    "F12": (f"{ESC}[X", f"{ESC}[j", f"{ESC}[v", f"{ESC}['"),
}

# Navigation key mappings (JavaScript event.key values)
_NAV_MAP = {
    "Home":      f"{ESC}[H",
    "End":       f"{ESC}[F",
    "PageUp":    f"{ESC}[I",
    "PageDown":  f"{ESC}[G",
    "Insert":    f"{ESC}[L",
    "ArrowUp":   f"{ESC}[A",
    "ArrowDown": f"{ESC}[B",
    "ArrowLeft": f"{ESC}[D",
    "ArrowRight":f"{ESC}[C",
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


def _modifier_index(shift: bool, ctrl: bool, alt: bool) -> int:
    if shift:
        return 1
    elif ctrl:
        return 2
    elif alt:
        return 3
    return 0


class InputHandler:
    def __init__(self):
        self._translator = LocaleTranslator()
        self._kbd_disabled = False
        self._altlock = False
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

    def translate_key_event(self, key: str, char: str,
                            shift: bool, ctrl: bool, alt: bool) -> str:
        """Translate a JavaScript keyboard event to an iLO2 escape sequence.

        Args:
            key: JavaScript event.key value (e.g. "a", "Enter", "F1")
            char: The typed character (empty for non-printable keys)
            shift/ctrl/alt: Modifier states
        """
        if self._kbd_disabled:
            return ""

        use_alt = alt or self._altlock
        mod_idx = _modifier_index(shift, ctrl, use_alt)

        # Special keys first
        if key == "Escape":
            return f"{ESC}"

        if key == "Tab":
            return "\t"

        if key == "Delete":
            if ctrl and use_alt:
                return self.build_ctrl_alt_del()
            return ""

        # F-keys
        if key in _FKEY_MAP:
            return _FKEY_MAP[key][mod_idx]

        # Navigation keys
        if key in _NAV_MAP:
            result = _NAV_MAP[key]
            if mod_idx == 1:
                result = f"{ESC}[3{result}"
            elif mod_idx == 2:
                result = f"{ESC}[2{result}"
            elif mod_idx == 3:
                result = f"{ESC}[1{result}"
            return result

        # Enter
        if key == "Enter":
            if mod_idx == 0:
                return "\r"
            elif mod_idx == 1:
                return f"{ESC}[3\r"
            elif mod_idx == 2:
                return "\n"
            elif mod_idx == 3:
                return f"{ESC}[1\r"

        # Backspace
        if key == "Backspace":
            if mod_idx == 0:
                return "\b"
            elif mod_idx == 1:
                return f"{ESC}[3\b"
            elif mod_idx == 2:
                return ""
            elif mod_idx == 3:
                return f"{ESC}[1\b"

        # Regular character
        if char and len(char) == 1:
            result = self._translator.translate(char)
            if result and mod_idx == 3:
                result = f"{ESC}[1{result}"
            return result

        return ""

    def build_mouse_move(self, dx: int, dy: int, client_x: int, client_y: int) -> bytes:
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
