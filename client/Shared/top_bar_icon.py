from PySide6.QtWidgets import QLabel
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QPainterPath, QCursor

def get_initials(name: str) -> str:
    """Extracts initials (first letter of first and last word, or first letter)."""
    if not name:
        return "S"
    parts = name.strip().split()
    if not parts:
        return "S"
    if len(parts) >= 2:
        return (parts[0][0] + parts[-1][0]).upper()
    return parts[0][0].upper()

class TopBarIcon(QLabel):
    """Custom vector-painted icons for the top bar (camera, signal, bell)."""

    def __init__(self, kind: str, parent=None) -> None:
        super().__init__(parent)
        self.kind = kind.lower().strip()
        self.setFixedSize(36, 36)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._hovered = False
        self._color = "#4B5563"       # Cool gray
        self._hover_color = "#111827" # Darker gray/black

    def enterEvent(self, event) -> None:
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw a subtle hover background circle
        if self._hovered:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor("#F3F4F6")))
            painter.drawEllipse(2, 2, 32, 32)

        color = self._hover_color if self._hovered else self._color
        pen = QPen(QColor(color), 1.75, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        # 18x18 icon content centered inside the 36x36 widget
        # offset X=9, Y=9
        s = 18
        ox = 9
        oy = 9

        if self.kind == "camera":
            # Photo camera style
            # Shutter button / flash bump on top
            painter.drawRoundedRect(ox + 5, oy, 5, 2, 0.5, 0.5)
            # Camera body
            painter.drawRoundedRect(ox, oy + 2, s, s - 3, 2, 2)
            # Outer lens circle
            painter.drawEllipse(ox + s // 2 - 3.5, oy + s // 2 - 2, 7, 7)
            # Inner lens dot
            painter.setBrush(QBrush(QColor(color)))
            painter.drawEllipse(ox + s // 2 - 1, oy + s // 2 - 0.5, 2, 2)

        elif self.kind == "signal" or self.kind == "network":
            # 4 vertical signal bars
            bar_w = 2.5
            spacing = 1.5
            start_x = ox + 2.5
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(color)))
            for i in range(4):
                x = start_x + i * (bar_w + spacing)
                h = 3.5 + i * 4.5
                y = oy + s - h - 1
                painter.drawRoundedRect(QRectF(x, y, bar_w, h), 0.75, 0.75)

        elif self.kind == "bell":
            # Notification Bell
            # Bell top loop
            painter.drawEllipse(ox + s // 2 - 2, oy, 4, 3)
            # Bell dome body
            path = QPainterPath()
            path.moveTo(ox + s // 2, oy + 3)
            # curve/line to left shoulder
            path.lineTo(ox + s // 2 - 5, oy + 6)
            path.lineTo(ox + s // 2 - 5, oy + s - 5)
            # flare out to bottom left
            path.lineTo(ox + 1, oy + s - 3)
            # bottom line to bottom right
            path.lineTo(ox + s - 1, oy + s - 3)
            # flare back in to right side
            path.lineTo(ox + s // 2 + 5, oy + s - 5)
            path.lineTo(ox + s // 2 + 5, oy + 6)
            path.closeSubpath()
            painter.drawPath(path)
            # Bell clapper at the bottom
            painter.setBrush(QBrush(QColor(color)))
            painter.drawEllipse(QRectF(ox + s // 2 - 2.5, oy + s - 3, 5, 3.5))

        painter.end()
