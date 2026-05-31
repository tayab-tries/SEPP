from __future__ import annotations

from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget

from .styles import PRIMARY_BUTTON, SECONDARY_BUTTON


class NavigationButtonsWidget(QWidget):
    prev_requested = Signal()
    next_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 14, 0, 0)
        root.setSpacing(12)

        self.prev_button = QPushButton("Previous Question")
        self.prev_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.prev_button.setFixedHeight(42)
        self.prev_button.setStyleSheet(SECONDARY_BUTTON)
        self.prev_button.clicked.connect(self.prev_requested.emit)

        self.next_button = QPushButton("Next Question")
        self.next_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.next_button.setFixedHeight(42)
        self.next_button.setStyleSheet(PRIMARY_BUTTON)
        self.next_button.clicked.connect(self.next_requested.emit)

        root.addWidget(self.prev_button)
        root.addStretch()
        root.addWidget(self.next_button)

    def set_enabled_state(self, prev_enabled: bool, next_enabled: bool) -> None:
        self.prev_button.setEnabled(prev_enabled)
        self.next_button.setEnabled(next_enabled)
