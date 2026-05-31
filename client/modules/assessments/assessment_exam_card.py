from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSizePolicy,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCursor

# ─────────────────────────────────────────────────────────────────────────────
#  AssessmentExamCardWidget
#  Card displaying an exam, specialized for the assessments view.
# ─────────────────────────────────────────────────────────────────────────────

CARD_BG        = "#ffffff"
BORDER_COLOR   = "#e5e7eb"
CARD_RADIUS    = 10
ACCENT_BLUE    = "#3b82f6"
ACCENT_BLUE_H  = "#2563eb"
TEXT_PRIMARY   = "#0d1b2e"
TEXT_SECONDARY = "#6b7280"

class AssessmentExamCardWidget(QWidget):
    view_assessments_requested = Signal(str)  # exam_id

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._exam_id: str = ""
        self._setup_ui()
        self._set_blank()

    def _setup_ui(self) -> None:
        self.setStyleSheet(f"""
            AssessmentExamCardWidget {{
                background: {CARD_BG};
                border: 1px solid {BORDER_COLOR};
                border-radius: {CARD_RADIUS}px;
            }}
        """)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 14, 18, 14)
        outer.setSpacing(8)

        # ── Row 1: title + status tag ─────────────────────────────────────────
        top_row = QHBoxLayout()
        top_row.setSpacing(10)

        self._title_lbl = QLabel()
        self._title_lbl.setStyleSheet(
            f"color:{TEXT_PRIMARY}; font-size:15px; font-weight:700; background:transparent;"
        )
        self._title_lbl.setWordWrap(True)

        self._status_tag = QLabel()
        self._status_tag.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        self._status_tag.hide()

        top_row.addWidget(self._title_lbl, stretch=1)
        top_row.addWidget(self._status_tag, alignment=Qt.AlignmentFlag.AlignVCenter)
        outer.addLayout(top_row)

        # ── Row 2: date + duration ────────────────────────────────────────────
        meta_row = QHBoxLayout()
        meta_row.setSpacing(18)

        self._date_lbl = QLabel()
        self._date_lbl.setStyleSheet(
            f"color:{TEXT_SECONDARY}; font-size:12px; background:transparent;"
        )

        self._duration_lbl = QLabel()
        self._duration_lbl.setStyleSheet(
            f"color:{TEXT_SECONDARY}; font-size:12px; background:transparent;"
        )

        meta_row.addWidget(self._date_lbl)
        meta_row.addWidget(self._duration_lbl)
        meta_row.addStretch()
        outer.addLayout(meta_row)

        # ── Row 3: action buttons ─────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.addStretch()

        self._view_btn = QPushButton("View Assessments")
        self._view_btn.setFixedHeight(34)
        self._view_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._view_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {ACCENT_BLUE};
                border: 1px solid {ACCENT_BLUE};
                border-radius: 6px;
                padding: 0 16px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{ background: #eff6ff; }}
        """)
        self._view_btn.clicked.connect(
            lambda: self.view_assessments_requested.emit(self._exam_id)
        )

        btn_row.addWidget(self._view_btn)
        outer.addLayout(btn_row)

    def _set_blank(self) -> None:
        self._title_lbl.setText("—")
        self._date_lbl.setText("")
        self._duration_lbl.setText("")
        self._status_tag.hide()
        self._view_btn.hide()

    def set_loading(self) -> None:
        self._exam_id = ""
        self._title_lbl.setText("Loading…")
        self._date_lbl.setText("")
        self._duration_lbl.setText("")
        self._status_tag.hide()
        self._view_btn.hide()

    def set_exam(self, data: dict) -> None:
        self._exam_id = str(data.get("exam_id", ""))
        self._title_lbl.setText(data.get("title") or "Untitled Exam")

        date_str = data.get("start_time") or data.get("date") or "—"
        if isinstance(date_str, str) and "T" in date_str:
            date_str = date_str.split("T")[0]
        self._date_lbl.setText(f"📅  {date_str}")

        duration = data.get("duration_minutes") or data.get("duration_mins") or 0
        self._duration_lbl.setText(f"🕐  {duration} Mins")

        status = str(data.get("status") or "draft").lower()
        if status == "live":
            self._status_tag.setText("● LIVE")
            self._status_tag.setStyleSheet(f"""
                color: #22c55e;
                background: transparent;
                font-size: 11px;
                font-weight: 600;
            """)
        elif status == "closed":
            self._status_tag.setText("CLOSED")
            self._status_tag.setStyleSheet(f"""
                color: #6b7280;
                background: #f3f4f6;
                border-radius: 4px;
                padding: 2px 8px;
                font-size: 11px;
                font-weight: 600;
            """)
        else:
            self._status_tag.setText(status.upper())
            self._status_tag.setStyleSheet(f"""
                color: #f59e0b;
                background: transparent;
                font-size: 11px;
                font-weight: 600;
            """)
        self._status_tag.setVisible(True)
        self._view_btn.setVisible(True)
