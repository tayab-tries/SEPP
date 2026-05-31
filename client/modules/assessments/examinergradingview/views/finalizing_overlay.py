from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QFrame, QProgressBar, QVBoxLayout, QWidget

from .styles import CARD_BG, CARD_BORDER, TEXT_PRIMARY, TEXT_SECONDARY, TOPBAR_BG


class FinalizingOverlay(QWidget):
    """Blocking overlay shown while final answers are being synced/finalized."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("finalizingOverlay")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("""
            QWidget#finalizingOverlay {
                background: rgba(10, 20, 35, 180);
            }
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addStretch()

        self.card = QFrame()
        self.card.setObjectName("finalizingCard")
        self.card.setFixedWidth(460)
        self.card.setStyleSheet(f"""
            QFrame#finalizingCard {{
                background: {CARD_BG};
                border: 1px solid {CARD_BORDER};
                border-radius: 14px;
            }}
            QLabel {{ background: transparent; }}
        """)
        card_lay = QVBoxLayout(self.card)
        card_lay.setContentsMargins(28, 26, 28, 26)
        card_lay.setSpacing(14)

        self.title_label = QLabel("Finalizing exam")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setStyleSheet(f"color:{TEXT_PRIMARY}; font-size:18px; font-weight:800;")
        card_lay.addWidget(self.title_label)

        self.body_label = QLabel("Please wait while your answers are saved and submitted.")
        self.body_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.body_label.setWordWrap(True)
        self.body_label.setStyleSheet(f"color:{TEXT_SECONDARY}; font-size:13px; line-height:1.4;")
        card_lay.addWidget(self.body_label)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(8)
        self.progress.setStyleSheet(f"""
            QProgressBar {{
                border: none;
                border-radius: 4px;
                background: #edf2f7;
            }}
            QProgressBar::chunk {{
                border-radius: 4px;
                background: {TOPBAR_BG};
            }}
        """)
        card_lay.addWidget(self.progress)

        root.addWidget(self.card, alignment=Qt.AlignmentFlag.AlignCenter)
        root.addStretch()
        self.hide()

    def show_message(self, title: str, body: str) -> None:
        self.title_label.setText(title)
        self.body_label.setText(body)
        self.show()
        self.raise_()
