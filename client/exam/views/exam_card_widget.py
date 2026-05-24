from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSizePolicy,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCursor

# ─────────────────────────────────────────────────────────────────────────────
#  ExamCardWidget
#  One repeatable card per upcoming exam.
#  Starts blank; populate via set_exam(data).
#
#  Signals
#  -------
#  check_in_requested(exam_id: str)
#      Emitted when the user clicks "Check-In Now".
#      Only visible when data["check_in_open"] is True.
#
#  view_details_requested(exam_id: str)
#      Emitted when the user clicks "View Details".
#      Always visible.
#
#  Expected data dict (passed to set_exam)
#  ----------------------------------------
#  {
#      "exam_id":          str,
#      "title":            str,
#      "date":             str,   e.g. "Oct 24, 10:00 AM"
#      "duration_mins":    int,
#      "face_id_required": bool,
#      "check_in_open":    bool,
#  }
# ─────────────────────────────────────────────────────────────────────────────

CARD_BG        = "#ffffff"
BORDER_COLOR   = "#e5e7eb"
CARD_RADIUS    = 10
ACCENT_YELLOW  = "#f0a500"
ACCENT_YELLOW_H = "#d99400"
ACCENT_GREEN   = "#22c55e"
TEXT_PRIMARY   = "#0d1b2e"
TEXT_SECONDARY = "#6b7280"
TEXT_MUTED     = "#9ca3af"


class ExamCardWidget(QWidget):
    check_in_requested    = Signal(str)   # exam_id
    view_details_requested = Signal(str)  # exam_id

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._exam_id: str = ""
        self._setup_ui()
        self._set_blank()

    # ── UI construction ───────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        self.setStyleSheet(f"""
            ExamCardWidget {{
                background: {CARD_BG};
                border: 1px solid {BORDER_COLOR};
                border-radius: {CARD_RADIUS}px;
            }}
        """)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 14, 18, 14)
        outer.setSpacing(8)

        # ── Row 1: title + CHECK-IN OPEN tag ─────────────────────────────────
        top_row = QHBoxLayout()
        top_row.setSpacing(10)

        self._title_lbl = QLabel()
        self._title_lbl.setStyleSheet(
            f"color:{TEXT_PRIMARY}; font-size:15px; font-weight:700; background:transparent;"
        )
        self._title_lbl.setWordWrap(True)

        self._checkin_tag = QLabel("● CHECK-IN OPEN")
        self._checkin_tag.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        self._checkin_tag.setStyleSheet(
            f"color:{ACCENT_GREEN}; background:transparent; font-size:11px; font-weight:600;"
        )
        self._checkin_tag.hide()

        top_row.addWidget(self._title_lbl, stretch=1)
        top_row.addWidget(self._checkin_tag, alignment=Qt.AlignmentFlag.AlignVCenter)
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

        # ── Row 3: Face ID Required tag ───────────────────────────────────────
        self._face_id_tag = QLabel("Face ID Required")
        self._face_id_tag.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        self._face_id_tag.setStyleSheet(f"""
            color: {TEXT_SECONDARY};
            background: #f3f4f6;
            border: 1px solid {BORDER_COLOR};
            border-radius: 4px;
            padding: 2px 8px;
            font-size: 11px;
        """)
        self._face_id_tag.hide()
        outer.addWidget(self._face_id_tag)

        # ── Row 4: action buttons ─────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.addStretch()

        self._details_btn = QPushButton("View Details")
        self._details_btn.setFixedHeight(34)
        self._details_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._details_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {TEXT_PRIMARY};
                border: 1px solid {BORDER_COLOR};
                border-radius: 6px;
                padding: 0 14px;
                font-size: 13px;
            }}
            QPushButton:hover {{ background: #f9fafb; }}
        """)
        self._details_btn.clicked.connect(
            lambda: self.view_details_requested.emit(self._exam_id)
        )

        self._checkin_btn = QPushButton("Check-In Now  →")
        self._checkin_btn.setFixedHeight(34)
        self._checkin_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._checkin_btn.setStyleSheet(f"""
            QPushButton {{
                background: {ACCENT_YELLOW};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 0 16px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{ background: {ACCENT_YELLOW_H}; }}
        """)
        self._checkin_btn.clicked.connect(
            lambda: self.check_in_requested.emit(self._exam_id)
        )
        self._checkin_btn.hide()

        btn_row.addWidget(self._details_btn)
        btn_row.addWidget(self._checkin_btn)
        outer.addLayout(btn_row)

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _set_blank(self) -> None:
        self._title_lbl.setText("—")
        self._date_lbl.setText("")
        self._duration_lbl.setText("")
        self._checkin_tag.hide()
        self._face_id_tag.hide()
        self._checkin_btn.hide()

    # ── Public API ────────────────────────────────────────────────────────────

    def set_loading(self) -> None:
        """Show a loading placeholder state."""
        self._exam_id = ""
        self._title_lbl.setText("Loading…")
        self._date_lbl.setText("")
        self._duration_lbl.setText("")
        self._checkin_tag.hide()
        self._face_id_tag.hide()
        self._checkin_btn.hide()

    def set_exam(self, data: dict) -> None:
        """Populate the card with data pushed from the page layer."""
        self._exam_id = data.get("exam_id", "")

        self._title_lbl.setText(data.get("title", "Untitled Exam"))

        date_str = data.get("date", "—")
        self._date_lbl.setText(f"📅  {date_str}")

        duration = data.get("duration_mins", 0)
        self._duration_lbl.setText(f"🕐  {duration} Mins")

        check_in_open = data.get("check_in_open", False)
        self._checkin_tag.setVisible(check_in_open)
        self._checkin_btn.setVisible(check_in_open)

        face_id = data.get("face_id_required", False)
        self._face_id_tag.setVisible(face_id)
