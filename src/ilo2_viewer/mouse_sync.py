"""Mouse synchronization state machine for iLO2 remote console.

Ported from MouseSync.java - calibrates mouse movement between client and server
using predefined deltas to detect acceleration curves.
"""

from __future__ import annotations

import threading
import time
from enum import IntEnum, auto
from typing import Protocol


MOUSE_BUTTON_LEFT = 4
MOUSE_BUTTON_CENTER = 2
MOUSE_BUTTON_RIGHT = 1

TIMEOUT_DELAY = 0.005  # 5ms
TIMEOUT_MOVE = 0.200   # 200ms
TIMEOUT_SYNC = 2.0     # 2s

SYNC_SUCCESS_COUNT = 2
SYNC_FAIL_COUNT = 4


class MouseSyncListener(Protocol):
    def server_move(self, dx: int, dy: int, client_x: int, client_y: int): ...
    def server_press(self, button: int): ...
    def server_release(self, button: int): ...
    def server_click(self, button: int, count: int): ...


class _Cmd(IntEnum):
    START = 0
    STOP = auto()
    SYNC = auto()
    SERVER_MOVE = auto()
    SERVER_SCREEN = auto()
    SERVER_DISABLE = auto()
    TIMEOUT = auto()
    CLICK = auto()
    ENTER = auto()
    EXIT = auto()
    PRESS = auto()
    RELEASE = auto()
    DRAG = auto()
    MOVE = auto()
    ALIGN = auto()


class _State(IntEnum):
    INIT = 0
    SYNC = auto()
    ENABLE = auto()
    DISABLE = auto()


class _Timer:
    """Simple timer that fires a callback after a timeout (runs in a thread)."""

    def __init__(self, timeout: float, callback, mutex: threading.RLock):
        self._timeout = timeout
        self._callback = callback
        self._mutex = mutex
        self._running = False
        self._paused = False
        self._elapsed = 0.0
        self._thread: threading.Thread | None = None

    def start(self):
        self._elapsed = 0.0
        self._paused = False
        if not self._running:
            self._running = True
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()

    def stop(self):
        self._running = False

    def pause(self):
        self._paused = True

    def _run(self):
        poll = 0.05
        while self._running:
            time.sleep(poll)
            if not self._running:
                break
            if not self._paused:
                continue
            self._elapsed += poll
            if self._elapsed >= self._timeout:
                with self._mutex:
                    if self._callback:
                        self._callback()
                self._elapsed = 0.0


class MouseSync:
    SYNC_DELTAS = [1, 4, 6, 8, 12, 16, 32, 64]

    def __init__(self):
        self._mutex = threading.RLock()
        self._state = _State.INIT
        self._listener: MouseSyncListener | None = None
        self._debug = False

        self._server_w = 640
        self._server_h = 480
        self._server_x = 0
        self._server_y = 0
        self._client_x = 0
        self._client_y = 0
        self._client_dx = 0
        self._client_dy = 0

        self._send_dx: list[int] = []
        self._send_dy: list[int] = []
        self._recv_dx: list[int] = []
        self._recv_dy: list[int] = []
        self._send_dx_index = 0
        self._send_dy_index = 0
        self._send_dx_count = 0
        self._send_dy_count = 0
        self._send_dx_success = 0
        self._send_dy_success = 0
        self._sync_successful = False

        self._timer: _Timer | None = None
        self._pressed_button = 0
        self._dragging = False

        self._state_machine(_Cmd.START, 0, 0)

    def set_listener(self, listener: MouseSyncListener):
        self._listener = listener

    def enable_debug(self):
        self._debug = True

    def disable_debug(self):
        self._debug = False

    def restart(self):
        self._go_state(_State.INIT)

    def align(self):
        self._state_machine(_Cmd.ALIGN, 0, 0)

    def sync(self):
        self._state_machine(_Cmd.SYNC, 0, 0)

    def server_moved(self, x: int, y: int):
        self._state_machine(_Cmd.SERVER_MOVE, x, y)

    def server_screen(self, w: int, h: int):
        self._state_machine(_Cmd.SERVER_SCREEN, w, h)

    def server_disabled(self):
        self._state_machine(_Cmd.SERVER_DISABLE, 0, 0)

    def on_timeout(self):
        self._state_machine(_Cmd.TIMEOUT, 0, 0)

    # Mouse event handlers (called from Qt events via input_handler)
    def mouse_clicked(self, x: int, y: int, button: int, modifiers: int):
        self._state_machine(_Cmd.CLICK, x, y, button=button, modifiers=modifiers)

    def mouse_entered(self, x: int, y: int, modifiers: int):
        pass  # commented out in original

    def mouse_exited(self, x: int, y: int, modifiers: int):
        self._state_machine(_Cmd.EXIT, x, y, modifiers=modifiers)

    def mouse_pressed(self, x: int, y: int, button: int, modifiers: int):
        self._state_machine(_Cmd.PRESS, x, y, button=button, modifiers=modifiers)

    def mouse_released(self, x: int, y: int, button: int, modifiers: int):
        self._state_machine(_Cmd.RELEASE, x, y, button=button, modifiers=modifiers)

    def mouse_dragged(self, x: int, y: int, button: int, modifiers: int):
        self._state_machine(_Cmd.DRAG, x, y, button=button, modifiers=modifiers)
        time.sleep(TIMEOUT_DELAY)

    def mouse_moved(self, x: int, y: int, modifiers: int):
        self._state_machine(_Cmd.MOVE, x, y, modifiers=modifiers)
        time.sleep(TIMEOUT_DELAY)

    # Internal
    def _sync_default(self):
        n = len(self.SYNC_DELTAS)
        self._send_dx = list(self.SYNC_DELTAS)
        self._send_dy = list(self.SYNC_DELTAS)
        self._recv_dx = list(self.SYNC_DELTAS)
        self._recv_dy = list(self.SYNC_DELTAS)
        self._send_dx_index = 0
        self._send_dy_index = 0
        self._send_dx_count = 0
        self._send_dy_count = 0
        self._send_dx_success = 0
        self._send_dy_success = 0
        self._sync_successful = False

    def _sync_continue(self):
        dx_sign = -1 if self._server_x > self._server_w // 2 else 1
        dy_sign = -1 if self._server_y < self._server_h // 2 else 1
        k = dx_sign * self._send_dx[self._send_dx_index] if self._send_dx_index >= 0 else 0
        m = dy_sign * self._send_dy[self._send_dy_index] if self._send_dy_index >= 0 else 0
        if self._listener:
            self._listener.server_move(k, m, self._client_x, self._client_y)
        if self._timer:
            self._timer.start()

    def _sync_update(self, px: int, py: int):
        if self._timer:
            self._timer.pause()

        dx = abs(px - self._server_x)
        dy = abs(self._server_y - py)
        self._server_x = px
        self._server_y = py

        if self._send_dx_index >= 0:
            if self._recv_dx[self._send_dx_index] == dx:
                self._send_dx_success += 1
            self._recv_dx[self._send_dx_index] = dx
            self._send_dx_count += 1
            if self._send_dx_success >= SYNC_SUCCESS_COUNT:
                self._send_dx_index -= 1
                self._send_dx_success = 0
                self._send_dx_count = 0
            elif self._send_dx_count >= SYNC_FAIL_COUNT:
                self._go_state(_State.ENABLE)
                return

        if self._send_dy_index >= 0:
            if self._recv_dy[self._send_dy_index] == dy:
                self._send_dy_success += 1
            self._recv_dy[self._send_dy_index] = dy
            self._send_dy_count += 1
            if self._send_dy_success >= SYNC_SUCCESS_COUNT:
                self._send_dy_index -= 1
                self._send_dy_success = 0
                self._send_dy_count = 0
            elif self._send_dy_count >= SYNC_FAIL_COUNT:
                self._go_state(_State.ENABLE)
                return

        if self._send_dx_index < 0 and self._send_dy_index < 0:
            for k in range(len(self._send_dx) - 1, -1, -1):
                if self._recv_dx[k] == 0 or self._recv_dy[k] == 0:
                    self._go_state(_State.ENABLE)
                    return
                if k != 0 and (self._recv_dx[k] < self._recv_dx[k - 1] or self._recv_dy[k] < self._recv_dy[k - 1]):
                    self._go_state(_State.ENABLE)
                    return

            self._sync_successful = True
            self._send_dx_index = 0
            self._send_dy_index = 0
            self._go_state(_State.ENABLE)
        else:
            self._sync_continue()

    def _init_vars(self):
        self._server_w = 640
        self._server_h = 480
        self._server_x = 0
        self._server_y = 0
        self._client_x = 0
        self._client_y = 0
        self._client_dx = 0
        self._client_dy = 0
        self._pressed_button = 0
        self._dragging = False
        self._sync_default()

    def _move_server(self, synced: bool):
        if self._timer:
            self._timer.pause()

        dx_abs = abs(self._client_dx)
        dy_abs = abs(self._client_dy)
        sign_dx = -1 if self._client_dx < 0 else 1
        sign_dy = -1 if self._client_dy < 0 else 1

        total_dx = 0
        total_dy = 0

        while dx_abs != 0 or dy_abs != 0:
            step_dx = 0
            step_dy = 0

            if dx_abs != 0:
                found = False
                for i in range(len(self._send_dx) - 1, self._send_dx_index - 1, -1):
                    if self._recv_dx[i] <= dx_abs:
                        step_dx = sign_dx * self._send_dx[i]
                        total_dx += self._recv_dx[i]
                        dx_abs -= self._recv_dx[i]
                        found = True
                        break
                if not found:
                    total_dx += dx_abs
                    dx_abs = 0

            if dy_abs != 0:
                found = False
                for i in range(len(self._send_dy) - 1, self._send_dy_index - 1, -1):
                    if self._recv_dy[i] <= dy_abs:
                        step_dy = sign_dy * self._send_dy[i]
                        total_dy += self._recv_dy[i]
                        dy_abs -= self._recv_dy[i]
                        found = True
                        break
                if not found:
                    total_dy += dy_abs
                    dy_abs = 0

            if (step_dx != 0 or step_dy != 0) and self._listener:
                self._listener.server_move(step_dx, step_dy, self._client_x, self._client_y)

        self._client_dx -= sign_dx * total_dx
        self._client_dy -= sign_dy * total_dy

        if not synced:
            self._server_x += sign_dx * total_dx
            self._server_y -= sign_dy * total_dy

        if (self._client_dx != 0 or self._client_dy != 0) and self._timer:
            self._timer.start()

    def _go_state(self, new_state: _State):
        with self._mutex:
            self._state_machine_inner(_Cmd.STOP, 0, 0)
            self._state = new_state
            self._state_machine_inner(_Cmd.START, 0, 0)

    def _state_machine(self, cmd: _Cmd, px: int, py: int, **kwargs):
        with self._mutex:
            self._state_machine_inner(cmd, px, py, **kwargs)

    def _state_machine_inner(self, cmd: _Cmd, px: int, py: int, **kwargs):
        if self._state == _State.INIT:
            self._state_init(cmd)
        elif self._state == _State.SYNC:
            self._state_sync(cmd, px, py, **kwargs)
        elif self._state == _State.ENABLE:
            self._state_enable(cmd, px, py, **kwargs)
        elif self._state == _State.DISABLE:
            self._state_disable(cmd, px, py, **kwargs)

    def _state_init(self, cmd: _Cmd):
        if cmd == _Cmd.START:
            self._init_vars()
            self._go_state(_State.DISABLE)

    def _state_sync(self, cmd: _Cmd, px: int, py: int, **kwargs):
        if cmd == _Cmd.START:
            self._timer = _Timer(TIMEOUT_SYNC, self.on_timeout, self._mutex)
            self._sync_default()
            self._send_dx_index = len(self._send_dx) - 1
            self._send_dy_index = len(self._send_dy) - 1
            self._sync_continue()
        elif cmd == _Cmd.STOP:
            if self._timer:
                self._timer.stop()
                self._timer = None
            if not self._sync_successful:
                self._sync_default()
        elif cmd == _Cmd.SYNC:
            self._go_state(_State.SYNC)
        elif cmd == _Cmd.SERVER_MOVE:
            if px > 2000 or py > 2000:
                self._go_state(_State.DISABLE)
            else:
                self._sync_update(px, py)
        elif cmd == _Cmd.SERVER_SCREEN:
            self._server_h = px
            self._server_w = py
        elif cmd == _Cmd.SERVER_DISABLE:
            self._go_state(_State.DISABLE)
        elif cmd == _Cmd.TIMEOUT:
            self._go_state(_State.ENABLE)
        elif cmd in (_Cmd.ENTER, _Cmd.EXIT, _Cmd.DRAG, _Cmd.MOVE):
            self._client_x = px
            self._client_y = py

    def _state_enable(self, cmd: _Cmd, px: int, py: int, **kwargs):
        button = kwargs.get("button", 0)
        modifiers = kwargs.get("modifiers", 0)

        if cmd == _Cmd.START:
            self._timer = _Timer(TIMEOUT_MOVE, self.on_timeout, self._mutex)
        elif cmd == _Cmd.STOP:
            if self._timer:
                self._timer.stop()
                self._timer = None
        elif cmd == _Cmd.SYNC:
            self._go_state(_State.SYNC)
        elif cmd == _Cmd.SERVER_MOVE:
            if px > 2000 or py > 2000:
                self._go_state(_State.DISABLE)
            else:
                self._server_x = px
                self._server_y = py
        elif cmd == _Cmd.SERVER_SCREEN:
            self._server_h = px
            self._server_w = py
        elif cmd == _Cmd.SERVER_DISABLE:
            self._go_state(_State.DISABLE)
        elif cmd == _Cmd.ALIGN:
            self._client_dx = self._client_x - self._server_x
            self._client_dy = self._server_y - self._client_y
            self._move_server(True)
        elif cmd == _Cmd.TIMEOUT:
            self._move_server(True)
        elif cmd in (_Cmd.ENTER, _Cmd.EXIT):
            self._client_x = max(0, min(px, self._server_w))
            self._client_y = max(0, min(py, self._server_h))
            if self._pressed_button != MOUSE_BUTTON_RIGHT and not (modifiers & 0x2):
                self.align()
        elif cmd == _Cmd.DRAG:
            if self._pressed_button != MOUSE_BUTTON_RIGHT:
                if self._pressed_button > 0:
                    self._pressed_button = -self._pressed_button
                    if self._listener:
                        self._listener.server_press(self._pressed_button)
                self._client_dx += px - self._client_x
                self._client_dy += self._client_y - py
                self._move_server(True)
            self._client_x = px
            self._client_y = py
            self._dragging = True
        elif cmd == _Cmd.MOVE:
            if not (modifiers & 0x2):  # Ctrl not pressed
                self._client_dx += px - self._client_x
                self._client_dy += self._client_y - py
                self._move_server(True)
            self._client_x = px
            self._client_y = py
        elif cmd == _Cmd.PRESS:
            self._handle_press(button, modifiers)
        elif cmd == _Cmd.RELEASE:
            self._handle_release()
            self._pressed_button = 0
        elif cmd == _Cmd.CLICK:
            self._handle_click(button, modifiers)

    def _state_disable(self, cmd: _Cmd, px: int, py: int, **kwargs):
        button = kwargs.get("button", 0)
        modifiers = kwargs.get("modifiers", 0)

        if cmd == _Cmd.START:
            self._timer = _Timer(TIMEOUT_MOVE, self.on_timeout, self._mutex)
        elif cmd == _Cmd.STOP:
            if self._timer:
                self._timer.stop()
                self._timer = None
        elif cmd == _Cmd.SYNC:
            self._sync_default()
        elif cmd == _Cmd.SERVER_MOVE:
            if px < 2000 and py < 2000:
                self._server_x = px
                self._server_y = py
                self._go_state(_State.ENABLE)
        elif cmd == _Cmd.SERVER_SCREEN:
            self._server_h = px
            self._server_w = py
        elif cmd == _Cmd.ALIGN:
            self._client_dx = self._client_x - self._server_x
            self._client_dy = self._server_y - self._client_y
            self._move_server(False)
        elif cmd == _Cmd.TIMEOUT:
            self._move_server(False)
        elif cmd in (_Cmd.ENTER, _Cmd.EXIT):
            self._client_x = max(0, min(px, self._server_w))
            self._client_y = max(0, min(py, self._server_h))
            if self._pressed_button != MOUSE_BUTTON_RIGHT and not (modifiers & 0x2):
                self.align()
        elif cmd == _Cmd.DRAG:
            if self._pressed_button != MOUSE_BUTTON_RIGHT:
                if self._pressed_button > 0:
                    self._pressed_button = -self._pressed_button
                    if self._listener:
                        self._listener.server_press(self._pressed_button)
                self._client_dx += px - self._client_x
                self._client_dy += self._client_y - py
                self._move_server(False)
            else:
                self._server_x = px
                self._server_y = py
            self._client_x = px
            self._client_y = py
            self._dragging = True
        elif cmd == _Cmd.MOVE:
            if not (modifiers & 0x2):
                self._client_dx += px - self._client_x
                self._client_dy += self._client_y - py
                self._move_server(False)
            else:
                self._server_x = px
                self._server_y = py
            self._client_x = px
            self._client_y = py
        elif cmd == _Cmd.PRESS:
            self._handle_press(button, modifiers)
        elif cmd == _Cmd.RELEASE:
            self._handle_release()
            self._pressed_button = 0
        elif cmd == _Cmd.CLICK:
            self._handle_click(button, modifiers)

    def _handle_press(self, button: int, modifiers: int):
        """button: 0=left, 1=middle, 2=right (matching JS MouseEvent.button)"""
        if self._pressed_button == 0:
            if button == 2:
                self._pressed_button = MOUSE_BUTTON_RIGHT
            elif button == 1:
                self._pressed_button = MOUSE_BUTTON_CENTER
            else:
                self._pressed_button = MOUSE_BUTTON_LEFT
            self._dragging = False

    def _handle_release(self):
        if self._pressed_button == -MOUSE_BUTTON_LEFT:
            if self._listener:
                self._listener.server_release(MOUSE_BUTTON_LEFT)
        elif self._pressed_button == -MOUSE_BUTTON_CENTER:
            if self._listener:
                self._listener.server_release(MOUSE_BUTTON_CENTER)
        elif self._pressed_button == -MOUSE_BUTTON_RIGHT:
            if self._listener:
                self._listener.server_release(MOUSE_BUTTON_RIGHT)

    def _handle_click(self, button: int, modifiers: int):
        """button: 0=left, 1=middle, 2=right (matching JS MouseEvent.button)"""
        if not self._dragging and self._listener:
            if button == 0:
                self._listener.server_click(MOUSE_BUTTON_LEFT, 1)
            elif button == 1:
                self._listener.server_click(MOUSE_BUTTON_CENTER, 1)
            elif button == 2:
                self._listener.server_click(MOUSE_BUTTON_RIGHT, 1)
