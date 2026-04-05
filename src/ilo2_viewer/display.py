"""Video display widget for the iLO2 DVC video stream.

Ported from dvcwin.java - renders 16x16 pixel blocks into a QImage framebuffer.
"""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt, QTimer, QSize
from PySide6.QtGui import QImage, QPainter, QFont, QColor
from PySide6.QtWidgets import QWidget


class DisplayWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._screen_x = 640
        self._screen_y = 480
        self._pixel_buffer = np.zeros((self._screen_y, self._screen_x), dtype=np.uint32)
        self._image = self._create_image()
        self._overlay_text: str | None = None
        self._frametime = 1000 // 15  # default 15 fps

        self._update_timer = QTimer(self)
        self._update_timer.timeout.connect(self._on_timer)

        self._dirty = False

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumSize(640, 100)

    def _create_image(self) -> QImage:
        return QImage(
            self._pixel_buffer.data,
            self._screen_x,
            self._screen_y,
            self._screen_x * 4,
            QImage.Format.Format_RGB32,
        )

    def paste_block(self, x: int, y: int, block: list[int], width: int = 16):
        """Paste a 16x16 pixel block at (x, y) into the framebuffer."""
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
            self._screen_x = width
            self._screen_y = height
            self._pixel_buffer = np.zeros((self._screen_y, self._screen_x), dtype=np.uint32)
            self._image = self._create_image()
            self._overlay_text = None
            self.setMinimumSize(width, height)
            self.updateGeometry()
            self.update()

    def show_text(self, text: str):
        """Display overlay text (e.g. 'Connecting', 'No Video')."""
        if self._screen_x != 640 or self._screen_y != 100:
            self.set_dimensions(640, 100)
        self._overlay_text = text
        self.update()

    def set_framerate(self, rate: int):
        if rate > 0:
            self._frametime = 1000 // rate
        else:
            self._frametime = 1000 // 15

        if self._update_timer.isActive():
            self._update_timer.setInterval(self._frametime)

    def mark_dirty(self):
        self._dirty = True

    def start_updates(self):
        self._update_timer.start(self._frametime)

    def stop_updates(self):
        self._update_timer.stop()
        self._screen_x = 0
        self._screen_y = 0

    def _on_timer(self):
        if self._dirty:
            self._dirty = False
            self.update()

    def sizeHint(self) -> QSize:
        return QSize(self._screen_x, self._screen_y)

    def paintEvent(self, event):
        painter = QPainter(self)
        if self._overlay_text:
            painter.fillRect(self.rect(), QColor(0, 0, 0))
            painter.setPen(QColor(255, 255, 255))
            painter.setFont(QFont("Courier", 16))
            painter.drawText(10, 20, self._overlay_text)
        else:
            # Recreate QImage from current buffer data each paint
            img = QImage(
                self._pixel_buffer.data,
                self._screen_x,
                self._screen_y,
                self._screen_x * 4,
                QImage.Format.Format_RGB32,
            )
            painter.drawImage(0, 0, img)
        painter.end()
