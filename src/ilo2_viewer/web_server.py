"""Web server for iLO2 Remote Console.

Serves an HTML client and streams video frames over WebSocket.
Receives keyboard/mouse input from the browser.
"""

from __future__ import annotations

import asyncio
import json
import threading
import time
from pathlib import Path

from aiohttp import web

from .connection import Connection
from .display import DisplayWidget
from .input_handler import InputHandler

STATIC_DIR = Path(__file__).parent / "static"
FRAME_INTERVAL = 1 / 30  # 30 fps target


class WebConsole:
    def __init__(self, hostname: str, params: dict[str, str]):
        self._hostname = hostname
        self._params = params
        self._display = DisplayWidget()
        self._connection = Connection(self._display)
        self._status_fields = ["", "Offline", "", "", ""]
        self._websockets: list[web.WebSocketResponse] = []
        self._loop: asyncio.AbstractEventLoop | None = None

        self._connection.on_status_changed = self._on_status_changed
        self._parse_params()

    def _parse_params(self):
        p = self._params
        self._port = int(p.get("INFO6", "23") or "23")
        self._mouse_mode = int(p.get("INFOM", "0") or "0")

        enc_enabled = int(p.get("INFOA", "0") or "0") == 1
        if enc_enabled:
            dk_hex = p.get("INFOB", "")
            ek_hex = p.get("INFOC", "")
            key_index = int(p.get("INFOD", "0") or "0")
            if dk_hex:
                dk = bytes(int(dk_hex[i:i+2], 16) for i in range(0, 32, 2))
                self._connection.setup_decryption(dk)
            if ek_hex:
                ek = bytes(int(ek_hex[i:i+2], 16) for i in range(0, 32, 2))
                self._connection.setup_encryption(ek, key_index)

        self._connection.input_handler.set_mouse_protocol(self._mouse_mode)

        infon = int(p.get("INFON", "0") or "0")
        self._ts_param = infon & 0xFF00
        ts_low = infon & 0xFF
        if ts_low == 0:
            self._ts_param |= 1
        self._ts_port = int(p.get("INFOO", "3389") or "3389")

    def _build_login(self) -> str:
        info0 = self._params.get("INFO0", "")
        login = self._parse_login(info0)
        if login:
            if self._params.get("INFO1") is not None:
                login = f"\033[4{login}"
            login = f"\033[7\033[9{login}"
        return login

    def _parse_login(self, info0: str) -> str:
        if info0.startswith("Compaq-RIB-Login="):
            result = "\033[!"
            try:
                result += info0[17:73] + "\r" + info0[74:106] + "\r"
            except IndexError:
                return ""
            return result
        return self._base64_decode(info0)

    @staticmethod
    def _base64_decode(s: str) -> str:
        # Standard Base64 lookup table (indexed by ASCII code, value = 6-bit int)
        BASE64 = [0] * 128
        BASE64[43] = 62   # +
        BASE64[47] = 63   # /
        for _i in range(10): BASE64[48 + _i] = 52 + _i  # 0-9
        for _i in range(26): BASE64[65 + _i] = _i        # A-Z -> 0-25
        for _i in range(26): BASE64[97 + _i] = 26 + _i   # a-z -> 26-51
        result = []
        n = 0
        done = False
        while n + 3 < len(s) and not done:
            i = BASE64[ord(s[n]) & 0x7F]
            j = BASE64[ord(s[n+1]) & 0x7F]
            k = BASE64[ord(s[n+2]) & 0x7F]
            m = BASE64[ord(s[n+3]) & 0x7F]
            c1 = ((i << 2) + (j >> 4)) & 0xFF
            c2 = ((j << 4) + (k >> 2)) & 0xFF
            c3 = ((k << 6) + m) & 0xFF
            if c1 == ord(":"): c1 = ord("\r")
            if c2 == ord(":"): c2 = ord("\r")
            if c3 == ord(":"): c3 = ord("\r")
            result.append(chr(c1))
            if s[n+2] == "=": done = True
            else: result.append(chr(c2))
            if s[n+3] == "=": done = True
            else: result.append(chr(c3))
            n += 4
        if result:
            result.append("\r")
        return "".join(result)

    def _on_status_changed(self, field: int, message: str):
        if 0 <= field < len(self._status_fields):
            self._status_fields[field] = message
        # Broadcast status to all websockets
        status = " ".join(self._status_fields[:4])
        if self._loop:
            asyncio.run_coroutine_threadsafe(
                self._broadcast_json({"type": "status", "text": status}),
                self._loop,
            )

    async def _broadcast_json(self, msg: dict):
        data = json.dumps(msg)
        for ws in list(self._websockets):
            try:
                await ws.send_str(data)
            except Exception:
                pass

    async def _broadcast_binary(self, data: bytes):
        for ws in list(self._websockets):
            try:
                await ws.send_bytes(data)
            except Exception:
                pass

    # HTTP handlers
    async def handle_index(self, request: web.Request) -> web.Response:
        html = (STATIC_DIR / "index.html").read_text()
        return web.Response(text=html, content_type="text/html")

    async def handle_ws(self, request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        self._websockets.append(ws)

        # Send initial status and dimensions
        w, h = self._display.get_dimensions()
        await ws.send_str(json.dumps({
            "type": "init",
            "width": w, "height": h,
            "status": " ".join(self._status_fields[:4]),
            "hostname": self._hostname,
        }))

        try:
            async for msg in ws:
                if msg.type == web.WSMsgType.TEXT:
                    self._handle_input(json.loads(msg.data))
        finally:
            self._websockets.remove(ws)

        return ws

    def _handle_input(self, msg: dict):
        t = msg.get("type")

        if t == "key":
            seq = self._connection.input_handler.translate_key_event(
                msg["key"], msg.get("char", ""),
                msg.get("shift", False),
                msg.get("ctrl", False),
                msg.get("alt", False),
            )
            if seq:
                self._connection.transmit_str(seq)

        elif t == "mousemove":
            self._connection.mouse_sync.mouse_moved(
                msg["x"], msg["y"], 0
            )

        elif t == "mousedown":
            self._connection.mouse_sync.mouse_pressed(
                msg["x"], msg["y"], msg["button"], 0
            )

        elif t == "mouseup":
            self._connection.mouse_sync.mouse_released(
                msg["x"], msg["y"], msg["button"], 0
            )
            self._connection.mouse_sync.mouse_clicked(
                msg["x"], msg["y"], msg["button"], 0
            )

        elif t == "mousedrag":
            self._connection.mouse_sync.mouse_dragged(
                msg["x"], msg["y"], msg["button"], 0
            )

        elif t == "refresh":
            self._connection.refresh_screen()

        elif t == "ctrl_alt_del":
            self._connection.transmit_str(InputHandler.build_ctrl_alt_del())

        elif t == "altlock":
            if msg.get("enabled"):
                self._connection.input_handler.enable_altlock()
            else:
                self._connection.input_handler.disable_altlock()

    async def _frame_streamer(self):
        """Periodically encode and broadcast video frames."""
        last_w, last_h = 0, 0
        while True:
            await asyncio.sleep(FRAME_INTERVAL)
            if not self._websockets:
                continue

            frame = self._display.encode_frame()
            if frame:
                w, h = self._display.get_dimensions()
                if w != last_w or h != last_h:
                    last_w, last_h = w, h
                    await self._broadcast_json({"type": "resize", "width": w, "height": h})
                await self._broadcast_binary(frame)

    def start_session(self):
        login = self._build_login()
        self._connection.connect(
            self._hostname, login, self._port,
            self._ts_param, self._ts_port,
        )

        # Keep-alive thread
        def keep_alive():
            while True:
                time.sleep(30)
                self._connection.send_auto_alive()
        threading.Thread(target=keep_alive, daemon=True).start()

    async def run(self, host: str = "0.0.0.0", port: int = 8080):
        self._loop = asyncio.get_running_loop()

        app = web.Application()
        app.router.add_get("/", self.handle_index)
        app.router.add_get("/ws", self.handle_ws)

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, host, port)
        await site.start()

        print(f"iLO2 Console: http://localhost:{port}", flush=True)

        # Start iLO2 connection in a thread so it doesn't block the event loop
        self._loop.run_in_executor(None, self.start_session)

        # Stream frames until interrupted
        try:
            await self._frame_streamer()
        except asyncio.CancelledError:
            pass
        finally:
            self.shutdown()

    def shutdown(self):
        """Cleanly disconnect from iLO2."""
        print("Disconnecting from iLO2...", flush=True)
        self._connection.disconnect()
        # Invalidate the saved cookie so the session is freed on the iLO2
        from .auth import COOKIE_FILE
        COOKIE_FILE.unlink(missing_ok=True)
