from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QWidget, QFrame,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QCursor

# ─────────────────────────────────────────────────────────────────────────────
#  ViewDetailsDialog
#  Shown when the user clicks "View Details" on an ExamCardWidget.
#  Data is passed in from the page's exam cache (no additional API call).
#
#  Layout: dark header card + white body with label-value pairs.
#  Only a ✕ close button — no action buttons in the body.
#
#  Expected exam_data dict
#  -----------------------
#  {
#      "title":          str,
#      "start_time":     str,   e.g. "Oct 24, 2023 at 10:00 AM"
#      "examiner_name":  str,
#      "duration_mins":  int | str,
#  }
# ─────────────────────────────────────────────────────────────────────────────

EXAM_CARD_BG   = "#1a2d4e"
CARD_BG        = "#ffffff"
BORDER_COLOR   = "#e5e7eb"
TEXT_PRIMARY   = "#0d1b2e"
TEXT_SECONDARY = "#6b7280"


class ViewDetailsDialog(QDialog):
    def __init__(
        self,
        exam_data: dict,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(True)
        self.setFixedWidth(440)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── Outer card ────────────────────────────────────────────────────────
        card = QWidget()
        card.setObjectName("detailCard")
        card.setStyleSheet(f"""
            QWidget#detailCard {{
                background: {CARD_BG};
                border-radius: 10px;
                border: 1px solid {BORDER_COLOR};
            }}
        """)

        card_lay = QVBoxLayout(card)
        card_lay.setContentsMargins(0, 0, 0, 0)
        card_lay.setSpacing(0)

        # ── Dark header ───────────────────────────────────────────────────────
        header = QWidget()
        header.setObjectName("dialogHeader")
        header.setStyleSheet(f"""
            QWidget#dialogHeader {{
                background: {EXAM_CARD_BG};
                border-top-left-radius: 10px;
                border-top-right-radius: 10px;
            }}
        """)
        header_lay = QHBoxLayout(header)
        header_lay.setContentsMargins(20, 14, 16, 14)
        header_lay.setSpacing(0)

        title_lbl = QLabel(exam_data.get("title", "Exam Details"))
        title_lbl.setStyleSheet(
            "color: white; font-size: 14px; font-weight: 700; background: transparent;"
        )
        header_lay.addWidget(title_lbl, stretch=1)

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(28, 28)
        close_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        close_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: rgba(255, 255, 255, 0.65);
                border: none;
                font-size: 13px;
                font-weight: 600;
                border-radius: 6px;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.15);
                color: white;
            }
        """)
        close_btn.clicked.connect(self.accept)
        header_lay.addWidget(close_btn)
        card_lay.addWidget(header)

        # ── Body ──────────────────────────────────────────────────────────────
        body = QWidget()
        body.setStyleSheet("background: transparent;")
        body_lay = QVBoxLayout(body)
        body_lay.setContentsMargins(24, 20, 24, 24)
        body_lay.setSpacing(0)

        duration_raw = exam_data.get("duration_mins", "—")
        duration_str = (
            f"{duration_raw} Minutes" if isinstance(duration_raw, int) else str(duration_raw)
        )

        fields = [
            ("Exam Start Time", exam_data.get("start_time",    "—")),
            ("Examiner Name",   exam_data.get("examiner_name", "—")),
            ("Exam Duration",   duration_str),
        ]

        for i, (label, value) in enumerate(fields):
            row = QHBoxLayout()
            row.setContentsMargins(0, 14, 0, 14)
            row.setSpacing(12)

            lbl = QLabel(label)
            lbl.setFixedWidth(140)
            lbl.setStyleSheet(
                f"color:{TEXT_SECONDARY}; font-size:13px; font-weight:600; background:transparent;"
            )

            val = QLabel(value)
            val.setWordWrap(True)
            val.setStyleSheet(
                f"color:{TEXT_PRIMARY}; font-size:13px; background:transparent;"
            )

            row.addWidget(lbl)
            row.addWidget(val, stretch=1)
            body_lay.addLayout(row)

            # Divider between rows — not after the last one
            if i < len(fields) - 1:
                div = QFrame()
                div.setFixedHeight(1)
                div.setStyleSheet(f"background: {BORDER_COLOR};")
                body_lay.addWidget(div)

        card_lay.addWidget(body)
        outer.addWidget(card)
