from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QWidget,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCursor

# ─────────────────────────────────────────────────────────────────────────────
#  Shared InfoDialog
#  Extracted from dashboard_page.py and extended with an optional two-button
#  confirm mode (used by PendingRequestCard cancel confirmation).
#
#  Single-button mode  →  InfoDialog(title, body, parent)
#  Two-button mode     →  InfoDialog(title, body, parent,
#                                    confirm_label="Yes, Cancel",
#                                    cancel_label="Keep")
#
#  In two-button mode the `confirmed` signal is emitted when the user clicks
#  the confirm (destructive) button, then the dialog closes via accept().
#  The cancel / close buttons always call reject().
# ─────────────────────────────────────────────────────────────────────────────

CARD       = "#FFFFFF"
BORDER     = "#DDE0E8"
T_PRIMARY  = "#111827"
T_SECONDARY = "#6B7280"
ACCENT_RED = "#ef4444"


class InfoDialog(QDialog):
    confirmed = Signal()   # emitted only in two-button mode

    def __init__(
        self,
        title: str,
        body: str,
        parent: QWidget | None = None,
        confirm_label: str | None = None,
        cancel_label: str | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(True)
        self.setFixedWidth(400)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── Card container ────────────────────────────────────────────────────
        card = QWidget()
        card.setObjectName("dialogCard")
        card.setStyleSheet(f"""
            QWidget#dialogCard {{
                background: {CARD};
                border-radius: 10px;
                border: 1px solid {BORDER};
            }}
        """)

        card_lay = QVBoxLayout(card)
        card_lay.setContentsMargins(0, 0, 0, 0)
        card_lay.setSpacing(0)

        # ── Title bar ─────────────────────────────────────────────────────────
        tb = QWidget()
        tb.setStyleSheet("background: transparent;")
        tb_lay = QHBoxLayout(tb)
        tb_lay.setContentsMargins(20, 8, 16, 6)
        tb_lay.setSpacing(0)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(
            f"font-size:14px; font-weight:700; color:{T_PRIMARY}; background:transparent;"
        )
        tb_lay.addWidget(title_lbl)
        tb_lay.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(28, 28)
        close_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {T_SECONDARY};
                border: none;
                font-size: 13px;
                font-weight: 600;
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background: #F3F4F6;
                color: {T_PRIMARY};
            }}
        """)
        close_btn.clicked.connect(self.reject)
        tb_lay.addWidget(close_btn)
        card_lay.addWidget(tb)

        # ── Divider ───────────────────────────────────────────────────────────
        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet(f"background: {BORDER};")
        card_lay.addWidget(divider)

        # ── Body ──────────────────────────────────────────────────────────────
        body_w = QWidget()
        body_w.setStyleSheet("background: transparent;")
        self.body_lay = QVBoxLayout(body_w)
        self.body_lay.setContentsMargins(20, 16, 20, 20)
        self.body_lay.setSpacing(14)

        if body:
            body_lbl = QLabel(body)
        body_lbl.setWordWrap(True)
        body_lbl.setStyleSheet(
            f"color:{T_PRIMARY}; font-size:13px; background:transparent;"
        )
            self.body_lay.addWidget(body_lbl)

        # ── Two-button row (only when confirm_label is provided) ──────────────
        if confirm_label:
            btn_row = QHBoxLayout()
            btn_row.setSpacing(8)
            btn_row.addStretch()

            keep_btn = QPushButton(cancel_label or "Cancel")
            keep_btn.setFixedHeight(34)
            keep_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            keep_btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: {T_PRIMARY};
                    border: 1px solid {BORDER};
                    border-radius: 6px;
                    padding: 0 16px;
                    font-size: 13px;
                }}
                QPushButton:hover {{ background: #F3F4F6; }}
            """)
            keep_btn.clicked.connect(self.reject)

            confirm_btn = QPushButton(confirm_label)
            confirm_btn.setFixedHeight(34)
            confirm_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            confirm_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {ACCENT_RED};
                    color: white;
                    border: none;
                    border-radius: 6px;
                    padding: 0 16px;
                    font-size: 13px;
                    font-weight: 600;
                }}
                QPushButton:hover {{ background: #dc2626; }}
            """)
            confirm_btn.clicked.connect(self._on_confirm)

            btn_row.addWidget(keep_btn)
            btn_row.addWidget(confirm_btn)
            self.body_lay.addLayout(btn_row)

        card_lay.addWidget(body_w)
        outer.addWidget(card)

    # ── Private ───────────────────────────────────────────────────────────────

    def _on_confirm(self) -> None:
        self.confirmed.emit()
        self.accept()
