from __future__ import annotations

from PySide6.QtCore import Qt, Slot, QPropertyAnimation, QEasingCurve, QRect
from PySide6.QtWidgets import QLabel, QFrame, QVBoxLayout, QTextEdit

from .styles import TEXT_PRIMARY, TEXT_MUTED


class SidebarWidget(QFrame):
    """Right-side sidebar showing examiner's comments during review."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("examSidebar")
        self.setMinimumWidth(0)
        self.setMaximumWidth(320)
        self.setStyleSheet("""
            QFrame#examSidebar {
                background: #EEF3F8;
                border-left: 1px solid #DDE5EF;
            }
            QLabel { background: transparent; }
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 22, 22, 22)
        root.setSpacing(16)

        heading = QLabel("Examiner's Remarks")
        heading.setStyleSheet(f"color:{TEXT_PRIMARY}; font-size:15px; font-weight:800;")
        root.addWidget(heading)

        # Text area for comments
        self.comment_box = QTextEdit()
        self.comment_box.setReadOnly(True)
        self.comment_box.setStyleSheet(f"""
            QTextEdit {{
                background: white;
                border: 1px solid #DDE5EF;
                border-radius: 8px;
                color: {TEXT_PRIMARY};
                font-size: 14px;
                padding: 8px;
            }}
        """)
        root.addWidget(self.comment_box, stretch=1)

        # We'll use width animation for sliding effect
        self._animation = QPropertyAnimation(self, b"maximumWidth")
        self._animation.setDuration(300)
        self._animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
        
        self._is_open = True
        self.setMaximumWidth(320)

    @Slot()
    def toggle_sidebar(self):
        if self._is_open:
            self._animation.setStartValue(320)
            self._animation.setEndValue(0)
            self._is_open = False
        else:
            self._animation.setStartValue(0)
            self._animation.setEndValue(320)
            self._is_open = True
        self._animation.start()

    @Slot(str)
    def set_comment(self, text: str) -> None:
        """Update the comment box with text. If empty, show default message."""
        if not text or not text.strip():
            self.comment_box.setStyleSheet(f"""
                QTextEdit {{
                    background: white;
                    border: 1px solid #DDE5EF;
                    border-radius: 8px;
                    color: {TEXT_MUTED};
                    font-size: 14px;
                    font-style: italic;
                    padding: 8px;
                }}
            """)
            self.comment_box.setText("No comments by the examiner")
        else:
            self.comment_box.setStyleSheet(f"""
                QTextEdit {{
                    background: white;
                    border: 1px solid #DDE5EF;
                    border-radius: 8px;
                    color: {TEXT_PRIMARY};
                    font-size: 14px;
                    padding: 8px;
                }}
            """)
            self.comment_box.setText(text)
