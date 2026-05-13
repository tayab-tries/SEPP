"""
Shared PySide6 visual effects helpers.
"""

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QGraphicsDropShadowEffect, QWidget


def apply_card_shadow(widget: QWidget, blur_radius: int = 20, y_offset: int = 2) -> None:
    """
    Apply a subtle airy SaaS card shadow:
    - blur: 20
    - color: rgba(0, 0, 0, 0.05)
    """
    shadow = QGraphicsDropShadowEffect(widget)
    shadow.setBlurRadius(blur_radius)
    shadow.setOffset(0, y_offset)
    shadow.setColor(QColor(0, 0, 0, 13))
    widget.setGraphicsEffect(shadow)
