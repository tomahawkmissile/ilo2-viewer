"""Headless video framebuffer for the iLO2 DVC video stream.

Maintains a numpy pixel buffer that the DVC decoder writes into.
The web server reads this buffer to encode and stream frames.
"""

from __future__ import annotations

import io
import threading

import numpy as np
from PIL import Image


class DisplayWidget:
    """Headless framebuffer — no GUI, just pixel storage."""

    def __init__(self):
        self._screen_x = 640
        self._screen_y = 480
        self._pixel_buffer = np.zeros((self._screen_y, self._screen_x), dtype=np.uint32)
        self._overlay_text: str | None = None
        self._dirty = False
        self._lock = threading.Lock()
        self._running = False

    @property
    def width(self) -> int:
        return self._screen_x

    @property
    def height(self) -> int:
        return self._screen_y

    @property
    def overlay_text(self) -> str | None:
        return self._overlay_text

    def paste_block(self, x: int, y: int, block: list[int], width: int = 16):
        """Paste a 16x16 pixel block at (x, y) into the framebuffer."""
        with self._lock:
            max_rows = min(16, self._screen_y - y)
            for row in range(max_rows):
                src_start = row * 16
                for col in range(width):
                    if x + col < self._screen_x:
                        self._pixel_buffer[y + row, x + col] = block[src_start + col]
            self._dirty = True

    def set_dimensions(self, width: int, height: int):
        """Resize the video canvas."""
        if width != self._screen_x or height != self._screen_y:
            with self._lock:
                self._screen_x = width
                self._screen_y = height
                self._pixel_buffer = np.zeros((self._screen_y, self._screen_x), dtype=np.uint32)
                self._overlay_text = None
                self._dirty = True

    def show_text(self, text: str):
        """Set overlay text (e.g. 'Connecting', 'No Video')."""
        with self._lock:
            if self._screen_x != 640 or self._screen_y != 100:
                self._screen_x = 640
                self._screen_y = 100
                self._pixel_buffer = np.zeros((self._screen_y, self._screen_x), dtype=np.uint32)
            self._overlay_text = text
            self._dirty = True

    def set_framerate(self, rate: int):
        pass  # Framerate is handled by the web server

    def mark_dirty(self):
        self._dirty = True

    def start_updates(self):
        self._running = True

    def stop_updates(self):
        self._running = False
        self._screen_x = 0
        self._screen_y = 0

    def encode_frame(self) -> bytes | None:
        """Encode the current framebuffer as JPEG. Returns None if not dirty."""
        with self._lock:
            if not self._dirty:
                return None
            self._dirty = False

            if self._screen_x <= 0 or self._screen_y <= 0:
                return None

            if self._overlay_text:
                img = Image.new("RGB", (self._screen_x, self._screen_y), (0, 0, 0))
                from PIL import ImageDraw
                draw = ImageDraw.Draw(img)
                draw.text((10, 10), self._overlay_text, fill=(255, 255, 255))
            else:
                buf = self._pixel_buffer.copy()
                r = ((buf >> 16) & 0xFF).astype(np.uint8)
                g = ((buf >> 8) & 0xFF).astype(np.uint8)
                b = (buf & 0xFF).astype(np.uint8)
                rgb = np.stack([r, g, b], axis=-1)
                img = Image.fromarray(rgb, "RGB")

        out = io.BytesIO()
        img.save(out, format="JPEG", quality=80)
        return out.getvalue()

    def get_dimensions(self) -> tuple[int, int]:
        return self._screen_x, self._screen_y
