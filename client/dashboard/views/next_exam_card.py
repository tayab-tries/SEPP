from __future__ import annotations

from datetime import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSizePolicy,
)
from PySide6.QtCore import Qt, QTimer, Signal, Slot
from PySide6.QtGui import QCursor

from client.dashboard.services.api_client import ApiClient
from client.dashboard.dashboard_utils import parse_iso_datetime

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


class NextExamCard(QWidget):
    """
    Dark-navy hero card showing the next immediate exam.
    Contains a live countdown timer that ticks every second.
    """

    check_in_clicked    = Signal()
    instructions_clicked = Signal()

    def __init__(self, api: ApiClient) -> None:
        super().__init__()
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._api       = api
        self._target_dt: datetime | None = None

        self.setStyleSheet(f"""
            NextExamCard {{
                background: {EXAM_CARD_BG};
                border-radius: {CARD_RADIUS}px;
            }}
        """)
        self.setMinimumHeight(210)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        root = QHBoxLayout(self)
        root.setContentsMargins(28, 26, 28, 26)
        root.setSpacing(24)

        # ── Left: badge, title, description, buttons ──────────────────────
        left = QVBoxLayout()
        left.setSpacing(10)

        badge = QLabel("NEXT IMMEDIATE EXAM")
        badge.setFixedHeight(24)
        badge.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        badge.setStyleSheet(f"""
            color: {EXAM_TITLE_CLR};
            background: rgba(30, 77, 140, 0.55);
            border-radius: 4px;
            padding: 2px 10px;
            font-size: 10px;
            font-weight: 700;
            letter-spacing: 1px;
        """)

        self._title_lbl = QLabel("Loading…")
        self._title_lbl.setStyleSheet(f"""
            color: {EXAM_TITLE_CLR};
            font-size: 21px;
            font-weight: 700;
            background: transparent;
        """)
        self._title_lbl.setWordWrap(True)

        self._desc_lbl = QLabel("")
        self._desc_lbl.setStyleSheet(f"""
            color: {EXAM_BODY_CLR};
            font-size: 13px;
            background: transparent;
        """)
        self._desc_lbl.setWordWrap(True)

        # Button row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        self._checkin_btn = QPushButton("  ➜  Check In")
        self._checkin_btn.setFixedHeight(46)
        self._checkin_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._checkin_btn.setStyleSheet(f"""
            QPushButton {{
                background: {ACCENT_YELLOW};
                color: #0d1b2e;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 700;
                padding: 0 22px;
            }}
            QPushButton:hover  {{ background: {ACCENT_YELLOW_H}; }}
            QPushButton:pressed {{ background: #c07800; }}
        """)
        self._checkin_btn.clicked.connect(self.check_in_clicked)

        self._instr_btn = QPushButton("View Instructions")
        self._instr_btn.setFixedHeight(46)
        self._instr_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._instr_btn.setStyleSheet("""
            QPushButton {
                background: #2d4a6e;
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 600;
                padding: 0 22px;
            }
            QPushButton:hover  { background: #3a5f8a; }
            QPushButton:pressed { background: #1e3a58; }
        """)
        self._instr_btn.clicked.connect(self.instructions_clicked)

        btn_row.addWidget(self._checkin_btn)
        btn_row.addWidget(self._instr_btn)
        btn_row.addStretch()

        left.addWidget(badge)
        left.addWidget(self._title_lbl)
        left.addWidget(self._desc_lbl)
        left.addStretch()
        left.addLayout(btn_row)

        # ── Right: countdown box ──────────────────────────────────────────
        timer_box = QWidget()
        timer_box.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        timer_box.setFixedWidth(200)
        timer_box.setMinimumHeight(130)
        timer_box.setStyleSheet(f"""
            QWidget {{
                background: {TIMER_BOX_BG};
                border-radius: 8px;
            }}
        """)

        tb_lay = QVBoxLayout(timer_box)
        tb_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tb_lay.setSpacing(6)
        tb_lay.setContentsMargins(16, 20, 16, 20)

        starts_lbl = QLabel("STARTS IN")
        starts_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        starts_lbl.setStyleSheet(f"""
            color: {EXAM_BODY_CLR};
            font-size: 10px;
            font-weight: 700;
            letter-spacing: 2px;
            background: transparent;
        """)

        self._countdown_lbl = QLabel("--:--:--")
        self._countdown_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._countdown_lbl.setStyleSheet("""
            color: white;
            font-size: 34px;
            font-weight: 800;
            background: transparent;
            letter-spacing: 2px;
        """)

        # HH / MM / SS labels
        unit_row = QHBoxLayout()
        unit_row.setContentsMargins(0, 0, 0, 0)
        unit_row.setSpacing(0)
        for u in ["HOURS", "MINS", "SECS"]:
            u_lbl = QLabel(u)
            u_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            u_lbl.setStyleSheet(
                f"color:{EXAM_BODY_CLR}; font-size:9px; background:transparent;"
            )
            unit_row.addWidget(u_lbl, stretch=1)

        tb_lay.addWidget(starts_lbl)
        tb_lay.addWidget(self._countdown_lbl)
        tb_lay.addLayout(unit_row)

        root.addLayout(left, stretch=3)
        root.addWidget(timer_box, stretch=0)

        # ── Bootstrap ─────────────────────────────────────────────────────
        self.set_loading()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(1000)

    # ── Data ─────────────────────────────────────────────────────────────
    def set_loading(self) -> None:
        self._title_lbl.setText("Loading…")
        self._desc_lbl.setText("Fetching your next scheduled exam.")
        self._target_dt = None
        self._checkin_btn.setEnabled(False)
        self._instr_btn.setEnabled(False)
        self._tick()


    def set_exam(self, data: dict | None) -> None:
        if not data:
            self.set_empty()
            return

        self._checkin_btn.setEnabled(True)
        self._instr_btn.setEnabled(True)

        self._title_lbl.setText(data.get("title", "Untitled Exam"))

        meta = " • ".join(
            part for part in [
                data.get("course_code"),
                data.get("datetime_label"),
                data.get("duration_label"),
                data.get("exam_type"),
            ]
            if part
        )

        description = data.get("description") or ""
        if meta:
            description = f"{meta}\n\n{description}" if description else meta

        self._desc_lbl.setText(description)

        self._target_dt = parse_iso_datetime(data.get("start_time"))

        # Important: if the timer was stopped after a previous exam hit 00:00:00,
        # restart it when new exam data arrives.
        if not self._timer.isActive():
            self._timer.start(1000)

        self._tick()

    def set_empty(self) -> None:
        self._title_lbl.setText("No upcoming exam")
        self._desc_lbl.setText("You currently have no scheduled exams.")
        self._target_dt = None
        self._checkin_btn.setEnabled(False)
        self._instr_btn.setEnabled(False)
        self._tick()


    def set_error(self, message: str = "Could not load next exam.") -> None:
        self._title_lbl.setText("Unable to load exam")
        self._desc_lbl.setText(message)
        self._target_dt = None
        self._checkin_btn.setEnabled(False)
        self._instr_btn.setEnabled(False)
        self._tick()

    def refresh(self) -> None:
        """
        Put the card into loading state only.

        Actual API fetching should be handled by DashboardPage through ApiWorker,
        because this card should stay as a display component.
        """
        self.set_loading()

    # ── Timer ─────────────────────────────────────────────────────────────

    @Slot()
    def _tick(self) -> None:
        if self._target_dt is None:
            self._countdown_lbl.setText("--:--:--")
            return
        delta     = self._target_dt - datetime.now()
        total     = int(delta.total_seconds())
        if total <= 0:
            self._countdown_lbl.setText("00:00:00")
            self._timer.stop()
            return
        h, rem = divmod(total, 3600)
        m, s   = divmod(rem, 60)
        self._countdown_lbl.setText(f"{h:02d}:{m:02d}:{s:02d}")

    def hideEvent(self, event):
        super().hideEvent(event)
        self._timer.stop()

    def showEvent(self, event):
        super().showEvent(event)
        if self._target_dt is not None:
            self._timer.start(1000)
