"""
Shared auth-style diagonal split background.
"""

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QBrush, QColor, QLinearGradient, QPainter, QPolygon
from PySide6.QtWidgets import QWidget


class DiagonalBackground(QWidget):
    def paintEvent(self, event):
        painter = QPainter(self)
        if not painter.isActive():
            return

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        width = self.width()
        height = self.height()

        left = QPolygon([
            QPoint(0, 0),
            QPoint(int(width * 0.50), 0),
            QPoint(int(width * 0.38), height),
            QPoint(0, height),
        ])
        painter.setBrush(QBrush(QColor("#F4F7FF")))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPolygon(left)

        right = QPolygon([
            QPoint(int(width * 0.50), 0),
            QPoint(width, 0),
            QPoint(width, height),
            QPoint(int(width * 0.38), height),
        ])
        gradient = QLinearGradient(int(width * 0.44), 0, width, height)
        gradient.setColorAt(0.0, QColor("#2C62D9"))
        gradient.setColorAt(1.0, QColor("#1A3FA0"))
        painter.setBrush(QBrush(gradient))
        painter.drawPolygon(right)
        painter.end()
