from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QFrame, QVBoxLayout, QWidget

from .styles import CARD_BG, CARD_BORDER, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED, TOPBAR_BG


class SidebarWidget(QFrame):
    """Right-side proctoring sidebar. Camera is placeholder-only for now."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("examSidebar")
        self.setFixedWidth(320)
        self.setStyleSheet(f"""
            QFrame#examSidebar {{
                background: #EEF3F8;
                border-left: 1px solid #DDE5EF;
            }}
            QLabel {{ background: transparent; }}
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 22, 22, 22)
        root.setSpacing(16)

        heading = QLabel("Camera Feed")
        heading.setStyleSheet(f"color:{TEXT_PRIMARY}; font-size:15px; font-weight:800;")
        root.addWidget(heading)

        self.camera_box = QWidget()
        self.camera_box.setObjectName("cameraBox")
        self.camera_box.setFixedSize(276, 188)
        self.camera_box.setStyleSheet(f"""
            QWidget#cameraBox {{
                background: #FFFFFF;
                border-radius: 12px;
                border: 1px solid #DDE5EF;
            }}
        """)
        camera_lay = QVBoxLayout(self.camera_box)
        camera_lay.setContentsMargins(18, 18, 18, 18)
        camera_lay.setSpacing(8)

        icon = QLabel("●")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet("color: rgba(255,255,255,0.6); font-size: 30px;")
        camera_lay.addStretch()
        camera_lay.addWidget(icon)

        placeholder = QLabel("Camera Feed Placeholder")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setWordWrap(True)
        placeholder.setStyleSheet("color: white; font-size: 13px; font-weight: 800;")
        camera_lay.addWidget(placeholder)

        sub = QLabel("Live camera preview will be integrated here.")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setWordWrap(True)
        sub.setStyleSheet("color: rgba(255,255,255,0.62); font-size: 11px;")
        camera_lay.addWidget(sub)
        camera_lay.addStretch()

        root.addWidget(self.camera_box, alignment=Qt.AlignmentFlag.AlignHCenter)

        note = QLabel(
            "Monitoring runs separately in the exam engine. This panel is only a visual placeholder."
        )
        note.setWordWrap(True)
        note.setStyleSheet(f"color:{TEXT_MUTED}; font-size:12px; line-height: 1.3;")
        root.addWidget(note)
        root.addStretch()
