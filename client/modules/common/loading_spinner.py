"""
client/modules/common/loading_spinner.py

Reusable animated loading spinner.
Shows a spinning arc in the app's blue color palette.

Usage:
    spinner = LoadingSpinner(parent=self, size=32, color="#FFFFFF")
    spinner.show()   # starts spinning
    spinner.hide()   # stops spinning

Or use the overlay version which dims the parent:
    overlay = SpinnerOverlay(parent=self)
    overlay.show()
    overlay.hide()
"""

import math
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QTimer, QRectF, Slot
from PySide6.QtGui import QPainter, QColor, QPen


class LoadingSpinner(QWidget):
    """
    Animated spinning arc widget.
    Transparent background — place anywhere over existing UI.

    Args:
        parent: Parent widget
        size:   Diameter in pixels (default 32)
        color:  Arc color as hex string (default white)
        speed:  Rotation speed in degrees per tick (default 8)
    """

    def __init__(
        self,
        parent=None,
        size:  int = 32,
        color: str = "#FFFFFF",
        speed: int = 8,
    ):
        super().__init__(parent)
        self._size   = size
        self._color  = QColor(color)
        self._angle  = 0
        self._speed  = speed
        self._active = False

        self.setFixedSize(size, size)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        self._timer = QTimer(self)
        self._timer.setInterval(16)  # ~60fps
        self._timer.timeout.connect(self._tick)

    def show(self):
        self._active = True
        self._timer.start()
        super().show()

    def hide(self):
        self._active = False
        self._timer.stop()
        super().hide()

    @Slot()
    def _tick(self):
        self._angle = (self._angle + self._speed) % 360
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        if not painter.isActive():
            return

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.translate(self._size / 2, self._size / 2)
        painter.rotate(self._angle)

        pen = QPen()
        pen.setWidth(3)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)

        # Draw arc with gradient opacity — full at top, fading at tail
        arc_length = 270  # degrees of arc
        steps      = 20
        for i in range(steps):
            opacity = (i / steps) ** 1.5
            c = QColor(self._color)
            c.setAlphaF(opacity)
            pen.setColor(c)
            painter.setPen(pen)

            start_angle = int((i / steps) * arc_length * 16)
            span_angle  = int((1 / steps) * arc_length * 16)
            r = self._size / 2 - 3
            painter.drawArc(
                QRectF(-r, -r, r * 2, r * 2),
                start_angle,
                span_angle,
            )

        painter.end()


class SpinnerOverlay(QWidget):
    """
    Full-parent-size semi-transparent overlay with centered spinner.
    Use this to block interaction while loading.

    Usage:
        self._overlay = SpinnerOverlay(parent=self)
        # show/hide as needed
        self._overlay.show()
        self._overlay.hide()
    """

    def __init__(self, parent=None, color: str = "#FFFFFF"):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._spinner = LoadingSpinner(self, size=40, color=color)
        self.hide()

    def show(self):
        if self.parent():
            self.setGeometry(self.parent().rect())  # type: ignore[union-attr]
        self._spinner.move(
            (self.width()  - self._spinner.width())  // 2,
            (self.height() - self._spinner.height()) // 2,
        )
        self._spinner.show()
        super().show()
        self.raise_()

    def hide(self):
        self._spinner.hide()
        super().hide()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._spinner.move(
            (self.width()  - self._spinner.width())  // 2,
            (self.height() - self._spinner.height()) // 2,
        )

    def paintEvent(self, event):
        painter = QPainter(self)
        if not painter.isActive():
            return
        painter.fillRect(self.rect(), QColor(0, 0, 0, 80))
        painter.end()