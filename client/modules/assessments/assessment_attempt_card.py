from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSizePolicy,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCursor

# ─────────────────────────────────────────────────────────────────────────────
#  AssessmentAttemptCardWidget
#  Card displaying an individual student's attempt for an exam.
# ─────────────────────────────────────────────────────────────────────────────

CARD_BG        = "#ffffff"
BORDER_COLOR   = "#e5e7eb"
CARD_RADIUS    = 10
ACCENT_BLUE    = "#3b82f6"
ACCENT_BLUE_H  = "#2563eb"
ACCENT_YELLOW  = "#f0a500"
ACCENT_YELLOW_H = "#d99400"
TEXT_PRIMARY   = "#0d1b2e"
TEXT_SECONDARY = "#6b7280"

class AssessmentAttemptCardWidget(QWidget):
    view_logs_requested = Signal(str)    # session_id
    grade_attempt_requested = Signal(str) # session_id

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._session_id: str = ""
        self._setup_ui()
        self._set_blank()

    def _setup_ui(self) -> None:
        self.setStyleSheet(f"""
            AssessmentAttemptCardWidget {{
                background: {CARD_BG};
                border: 1px solid {BORDER_COLOR};
                border-radius: {CARD_RADIUS}px;
            }}
        """)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 14, 18, 14)
        outer.setSpacing(8)

        # ── Row 1: Student Name + Status Tag ──────────────────────────────────
        top_row = QHBoxLayout()
        top_row.setSpacing(10)

        self._student_lbl = QLabel()
        self._student_lbl.setStyleSheet(
            f"color:{TEXT_PRIMARY}; font-size:15px; font-weight:700; background:transparent;"
        )
        self._student_lbl.setWordWrap(True)

        self._status_tag = QLabel()
        self._status_tag.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        self._status_tag.hide()

        top_row.addWidget(self._student_lbl, stretch=1)
        top_row.addWidget(self._status_tag, alignment=Qt.AlignmentFlag.AlignVCenter)
        outer.addLayout(top_row)

        # ── Row 2: Scores and Meta ────────────────────────────────────────────
        meta_row = QHBoxLayout()
        meta_row.setSpacing(18)

        self._score_lbl = QLabel()
        self._score_lbl.setStyleSheet(
            f"color:{TEXT_SECONDARY}; font-size:12px; background:transparent;"
        )

        self._integrity_lbl = QLabel()
        self._integrity_lbl.setStyleSheet(
            f"color:{TEXT_SECONDARY}; font-size:12px; background:transparent;"
        )

        self._time_lbl = QLabel()
        self._time_lbl.setStyleSheet(
            f"color:{TEXT_SECONDARY}; font-size:12px; background:transparent;"
        )

        meta_row.addWidget(self._score_lbl)
        meta_row.addWidget(self._integrity_lbl)
        meta_row.addWidget(self._time_lbl)
        meta_row.addStretch()
        outer.addLayout(meta_row)

        # ── Row 3: Action Buttons ─────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.addStretch()

        self._view_logs_btn = QPushButton("View Logs")
        self._view_logs_btn.setFixedHeight(34)
        self._view_logs_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._view_logs_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {TEXT_PRIMARY};
                border: 1px solid {BORDER_COLOR};
                border-radius: 6px;
                padding: 0 14px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{ background: #f9fafb; }}
        """)
        self._view_logs_btn.clicked.connect(
            lambda: self.view_logs_requested.emit(self._session_id)
        )

        self._grade_btn = QPushButton("Grade Attempt")
        self._grade_btn.setFixedHeight(34)
        self._grade_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._grade_btn.setStyleSheet(f"""
            QPushButton {{
                background: {ACCENT_BLUE};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 0 16px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{ background: {ACCENT_BLUE_H}; }}
        """)
        self._grade_btn.clicked.connect(
            lambda: self.grade_attempt_requested.emit(self._session_id)
        )

        btn_row.addWidget(self._view_logs_btn)
        btn_row.addWidget(self._grade_btn)
        outer.addLayout(btn_row)

    def _set_blank(self) -> None:
        self._student_lbl.setText("—")
        self._score_lbl.setText("")
        self._integrity_lbl.setText("")
        self._time_lbl.setText("")
        self._status_tag.hide()
        self._view_logs_btn.hide()
        self._grade_btn.hide()

    def set_loading(self) -> None:
        self._session_id = ""
        self._student_lbl.setText("Loading…")
        self._score_lbl.setText("")
        self._integrity_lbl.setText("")
        self._time_lbl.setText("")
        self._status_tag.hide()
        self._view_logs_btn.hide()
        self._grade_btn.hide()

    def set_attempt(self, data: dict) -> None:
        from client.modules.assessments.examinergradingview.grading_cache import has_drafts
        self._session_id = str(data.get("session_id", ""))
        self._student_lbl.setText(data.get("student_name") or "Unknown Student")

        status = str(data.get("status") or "pending").lower()
        is_graded = data.get("is_graded", False) or status == "graded"
        has_local_drafts = has_drafts(self._session_id)
        
        if is_graded and not has_local_drafts:
            self._status_tag.setText("GRADED")
            self._status_tag.setStyleSheet(f"""
                color: #047857;
                background: #d1fae5;
                border: 1px solid #a7f3d0;
                border-radius: 4px;
                padding: 2px 8px;
                font-size: 11px;
                font-weight: 600;
            """)
        elif has_local_drafts:
            self._status_tag.setText("PENDING")
            self._status_tag.setStyleSheet(f"""
                color: #b45309;
                background: #fef3c7;
                border: 1px solid #fde68a;
                border-radius: 4px;
                padding: 2px 8px;
                font-size: 11px;
                font-weight: 600;
            """)
        elif status == "submitted":
            self._status_tag.setText("SUBMITTED")
            self._status_tag.setStyleSheet(f"""
                color: #22c55e;
                background: #f0fdf4;
                border: 1px solid #bbf7d0;
                border-radius: 4px;
                padding: 2px 8px;
                font-size: 11px;
                font-weight: 600;
            """)
        elif status == "terminated":
            self._status_tag.setText("TERMINATED")
            self._status_tag.setStyleSheet(f"""
                color: #ef4444;
                background: #fef2f2;
                border: 1px solid #fecaca;
                border-radius: 4px;
                padding: 2px 8px;
                font-size: 11px;
                font-weight: 600;
            """)
        elif status in ("active", "locked"):
            self._status_tag.setText("● LIVE")
            self._status_tag.setStyleSheet(f"""
                color: #f59e0b;
                background: transparent;
                font-size: 11px;
                font-weight: 600;
            """)
        else:
            self._status_tag.setText(status.upper())
            self._status_tag.setStyleSheet(f"""
                color: #6b7280;
                background: #f3f4f6;
                border-radius: 4px;
                padding: 2px 8px;
                font-size: 11px;
                font-weight: 600;
            """)
        self._status_tag.setVisible(True)

        mcq_score = data.get("mcq_score")
        essay_score = data.get("essay_score")
        mcq_val = float(mcq_score) if mcq_score is not None else 0.0
        essay_val = float(essay_score) if essay_score is not None else 0.0
        total_score = round(mcq_val + essay_val, 2)
        
        self._score_lbl.setText(f"📝 Score: {total_score}")

        integrity_score = data.get("integrity_score")
        if integrity_score is not None:
            self._integrity_lbl.setText(f"🛡️ Integrity: {integrity_score}%")
        else:
            self._integrity_lbl.setText("🛡️ Integrity: N/A")

        submitted_at = data.get("submitted_at") or data.get("terminated_at")
        if submitted_at:
            if isinstance(submitted_at, str) and "T" in submitted_at:
                submitted_at = submitted_at.replace("T", " ")[:16]
            self._time_lbl.setText(f"🕒 Completed: {submitted_at}")
        else:
            self._time_lbl.setText("")

        self._view_logs_btn.setVisible(True)
        self._grade_btn.setVisible(True)

        # Dynamic grading button text
        from client.modules.assessments.examinergradingview.grading_cache import has_drafts
        is_graded = data.get("is_graded", False) or status == "graded"
        
        if has_drafts(self._session_id):
            self._grade_btn.setText("Continue")
        elif is_graded:
            self._grade_btn.setText("Review Grade")
        else:
            self._grade_btn.setText("Grade Attempt")
