from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QWidget,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCursor

CARD       = "#FFFFFF"
BORDER     = "#DDE0E8"
T_PRIMARY  = "#111827"
T_SECONDARY = "#6B7280"
ACCENT_BLUE = "#3b82f6"
ACCENT_GRAY = "#9ca3af"


class AttemptReviewDialog(QDialog):
    review_requested = Signal()
    report_requested = Signal()

    def __init__(
        self,
        exam_title: str,
        is_graded: bool,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(True)
        self.setFixedWidth(420)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── Card container ──
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

        # ── Title bar ──
        tb = QWidget()
        tb.setStyleSheet("background: transparent;")
        tb_lay = QHBoxLayout(tb)
        tb_lay.setContentsMargins(20, 12, 16, 12)
        tb_lay.setSpacing(0)

        title_lbl = QLabel("Exam Attempt")
        title_lbl.setStyleSheet(
            f"font-size:16px; font-weight:800; color:{T_PRIMARY}; background:transparent;"
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

        # ── Divider ──
        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet(f"background: {BORDER};")
        card_lay.addWidget(divider)

        # ── Body ──
        body_w = QWidget()
        body_w.setStyleSheet("background: transparent;")
        body_lay = QVBoxLayout(body_w)
        body_lay.setContentsMargins(20, 16, 20, 20)
        body_lay.setSpacing(14)

        status_text = "Exam Graded" if is_graded else "Exam Not Graded"
        
        body_lbl = QLabel(f"<b>{exam_title}</b><br><br>Status: {status_text}")
        body_lbl.setWordWrap(True)
        body_lbl.setStyleSheet(
            f"color:{T_PRIMARY}; font-size:14px; background:transparent; line-height: 1.4;"
        )
        body_lay.addWidget(body_lbl)

        # ── Buttons ──
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)
        btn_row.addStretch()

        review_btn = QPushButton("Review")
        review_btn.setFixedHeight(36)
        review_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        review_btn.setStyleSheet(f"""
            QPushButton {{
                background: {ACCENT_BLUE};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 0 20px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{ background: #2563eb; }}
        """)
        review_btn.clicked.connect(self._on_review)

        report_btn = QPushButton("Check Report")
        report_btn.setFixedHeight(36)
        
        if is_graded:
            report_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            report_btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: {T_PRIMARY};
                    border: 1px solid {BORDER};
                    border-radius: 6px;
                    padding: 0 20px;
                    font-size: 13px;
                    font-weight: 600;
                }}
                QPushButton:hover {{ background: #F3F4F6; }}
            """)
            report_btn.clicked.connect(self._on_report)
        else:
            report_btn.setCursor(QCursor(Qt.CursorShape.ForbiddenCursor))
            report_btn.setStyleSheet(f"""
                QPushButton {{
                    background: #F3F4F6;
                    color: {ACCENT_GRAY};
                    border: 1px solid {BORDER};
                    border-radius: 6px;
                    padding: 0 20px;
                    font-size: 13px;
                    font-weight: 600;
                }}
            """)
            report_btn.setEnabled(False)

        btn_row.addWidget(report_btn)
        btn_row.addWidget(review_btn)
        body_lay.addLayout(btn_row)

        card_lay.addWidget(body_w)
        outer.addWidget(card)

    def _on_review(self) -> None:
        self.review_requested.emit()
        self.accept()
        
    def _on_report(self) -> None:
        self.report_requested.emit()
        self.accept()
