from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QSizePolicy,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCursor

from client.dashboard.services.api_client import ApiClient

# ─────────────────────────────────────────────────────────
#  SEPP Dashboard — Design Tokens
#  Match these to the reference screenshot.
# ─────────────────────────────────────────────────────────

# Sidebar
SIDEBAR_BG       = "#0b1a2e"
SIDEBAR_HOVER    = "#152644"
SIDEBAR_ACTIVE   = "#1e3a62"
SIDEBAR_TEXT     = "#7a92ad"
SIDEBAR_TEXT_ACT = "#ffffff"

# Exam hero card
EXAM_CARD_BG     = "#1a2d4e"
TIMER_BOX_BG     = "#253d5e"
EXAM_TITLE_CLR   = "#7eb8f7"
EXAM_BODY_CLR    = "#b0c8e0"

# App chrome
TOP_BAR_BG       = "#ffffff"
MAIN_BG          = "#f0f2f5"
CARD_BG          = "#ffffff"

# Accents
ACCENT_YELLOW    = "#f0a500"
ACCENT_YELLOW_H  = "#d99400"
ACCENT_GREEN     = "#22c55e"
ACCENT_RED       = "#ef4444"

# Text
TEXT_PRIMARY     = "#0d1b2e"
TEXT_SECONDARY   = "#6b7280"
TEXT_MUTED       = "#9ca3af"

# Misc
BORDER_COLOR     = "#e5e7eb"
PROGRESS_BG      = "#e8eaed"
PROGRESS_FILL    = "#1a2d4e"

# Sizes
SIDEBAR_WIDTH    = 232
TOP_BAR_HEIGHT   = 56
CARD_RADIUS      = 10


# ──────────────────────────────────────────────────────────────────────────────
class _AssessmentItem(QWidget):
    """Single row in the upcoming-assessments list."""

    def __init__(self, data: dict) -> None:
        super().__init__()
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedHeight(78)
        self.setStyleSheet(f"""
            _AssessmentItem {{
                background: {CARD_BG};
                border: 1px solid {BORDER_COLOR};
                border-radius: 8px;
            }}
        """)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(18, 0, 18, 0)
        lay.setSpacing(16)

        # ── Date block ────────────────────────────────────────────────────
        date_w = QWidget()
        date_w.setFixedWidth(42)
        date_w.setStyleSheet("background: transparent;")
        date_lay = QVBoxLayout(date_w)
        date_lay.setContentsMargins(0, 0, 0, 0)
        date_lay.setSpacing(0)
        date_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

        month_lbl = QLabel(data.get("month", ""))
        month_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        month_lbl.setStyleSheet(
            f"color:{TEXT_SECONDARY}; font-size:10px; font-weight:600; background:transparent;"
        )

        day_lbl = QLabel(data.get("day", ""))
        day_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        day_lbl.setStyleSheet(
            f"color:{TEXT_PRIMARY}; font-size:22px; font-weight:800; background:transparent;"
        )

        date_lay.addWidget(month_lbl)
        date_lay.addWidget(day_lbl)

        # Vertical divider
        vline = QFrame()
        vline.setFrameShape(QFrame.Shape.VLine)
        vline.setFixedWidth(1)
        vline.setStyleSheet(f"color: {BORDER_COLOR};")

        # ── Middle: title + time ──────────────────────────────────────────
        mid = QVBoxLayout()
        mid.setSpacing(4)

        title_lbl = QLabel(data.get("title", ""))
        title_lbl.setStyleSheet(
            f"color:{TEXT_PRIMARY}; font-size:13px; font-weight:600; background:transparent;"
        )

        time_str = f"{data.get('time', '')}  •  {data.get('duration_minutes', '')} Minutes"
        time_lbl = QLabel(time_str)
        time_lbl.setStyleSheet(
            f"color:{TEXT_SECONDARY}; font-size:12px; background:transparent;"
        )

        mid.addWidget(title_lbl)
        mid.addWidget(time_lbl)

        # ── Badge ─────────────────────────────────────────────────────────
        exam_type = data.get("exam_type", "")
        badge = QLabel(f"● {exam_type}")
        badge.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        badge.setFixedHeight(26)

        if exam_type == "Proctored":
            badge.setStyleSheet(f"""
                color: {TEXT_PRIMARY};
                background: #e4e8ed;
                border-radius: 13px;
                padding: 2px 12px;
                font-size: 12px;
                font-weight: 500;
            """)
        else:
            badge.setStyleSheet(f"""
                color: {TEXT_SECONDARY};
                background: #f3f4f6;
                border-radius: 13px;
                padding: 2px 12px;
                font-size: 12px;
                font-weight: 500;
            """)

        lay.addWidget(date_w)
        lay.addWidget(vline)
        lay.addLayout(mid, stretch=1)
        lay.addWidget(badge)


# ──────────────────────────────────────────────────────────────────────────────
class UpcomingAssessments(QWidget):
    view_schedule_clicked = Signal()
    def __init__(self, api: ApiClient) -> None:
        super().__init__()
        self._api = api
        self.setStyleSheet("background: transparent;")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        # ── Header row ────────────────────────────────────────────────────
        hdr = QHBoxLayout()

        title_lbl = QLabel("Upcoming Assessments")
        title_lbl.setStyleSheet(
            f"color:{TEXT_PRIMARY}; font-size:17px; font-weight:700;"
        )

        sched_btn = QPushButton("View Full Schedule")
        sched_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        sched_btn.setStyleSheet(f"""
            QPushButton {{
                color: {TEXT_SECONDARY};
                background: transparent;
                border: none;
                font-size: 12px;
            }}
            QPushButton:hover {{ color: {TEXT_PRIMARY}; text-decoration: underline; }}
        """)
        sched_btn.clicked.connect(self.view_schedule_clicked)

        hdr.addWidget(title_lbl)
        hdr.addStretch()
        hdr.addWidget(sched_btn)
        root.addLayout(hdr)

        # ── List ──────────────────────────────────────────────────────────
        self._list_lay = QVBoxLayout()
        self._list_lay.setSpacing(8)
        root.addLayout(self._list_lay)

        self.set_loading()

    def _clear(self) -> None:
        while self._list_lay.count():
            item = self._list_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()


    def set_loading(self) -> None:
        self._clear()
        lbl = QLabel("Loading upcoming assessments…")
        lbl.setStyleSheet(
            f"color:{TEXT_SECONDARY}; font-size:12px; background:transparent;"
        )
        self._list_lay.addWidget(lbl)


    def set_assessments(self, assessments: list[dict]) -> None:
        self._clear()

        if not assessments:
            self.set_empty()
            return

        for a in assessments:
            self._list_lay.addWidget(_AssessmentItem(a))

        self._list_lay.addStretch()


    def set_empty(self) -> None:
        self._clear()
        lbl = QLabel("No upcoming assessments.")
        lbl.setStyleSheet(
            f"color:{TEXT_SECONDARY}; font-size:12px; background:transparent;"
        )
        self._list_lay.addWidget(lbl)
        self._list_lay.addStretch()


    def set_error(self, message: str = "Could not load upcoming assessments.") -> None:
        self._clear()
        lbl = QLabel(message)
        lbl.setStyleSheet(
            f"color:{ACCENT_RED}; font-size:12px; background:transparent;"
        )
        self._list_lay.addWidget(lbl)
        self._list_lay.addStretch()
