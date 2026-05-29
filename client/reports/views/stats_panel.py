from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QGridLayout, QSizePolicy
)
from PySide6.QtCore import Qt

# Tokens
CARD_BG          = "#ffffff"
BORDER_COLOR     = "#e5e7eb"
TEXT_PRIMARY     = "#0d1b2e"
TEXT_SECONDARY   = "#6b7280"
CARD_RADIUS      = 10

class StatsPanel(QWidget):
    """
    A single large card showing a 2x2 grid of performance statistics.
    """
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            StatsPanel {{
                background: {CARD_BG};
                border-radius: {CARD_RADIUS}px;
                border: 1px solid {BORDER_COLOR};
            }}
        """)
        self.setFixedHeight(160)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(16)

        # Title
        title = QLabel("Overall Performance")
        title.setStyleSheet(f"color:{TEXT_PRIMARY}; font-size:16px; font-weight:700; background:transparent;")
        root.addWidget(title)

        # 2x2 Grid
        grid_w = QWidget()
        grid_w.setStyleSheet("background: transparent;")
        grid = QGridLayout(grid_w)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(24)

        self._lbl_completed = self._build_stat_value("0")
        self._lbl_avg_score = self._build_stat_value("0%")
        self._lbl_avg_trust = self._build_stat_value("0%")
        self._lbl_flags     = self._build_stat_value("0")

        grid.addWidget(self._build_stat_box("Exams Completed", self._lbl_completed), 0, 0)
        grid.addWidget(self._build_stat_box("Average Score", self._lbl_avg_score), 0, 1)
        grid.addWidget(self._build_stat_box("Average Trust Score", self._lbl_avg_trust), 0, 2)
        grid.addWidget(self._build_stat_box("Proctoring Flags", self._lbl_flags), 0, 3)

        root.addWidget(grid_w)

    def _build_stat_value(self, default_text: str) -> QLabel:
        lbl = QLabel(default_text)
        lbl.setStyleSheet(f"color:{TEXT_PRIMARY}; font-size:24px; font-weight:800; background:transparent;")
        return lbl

    def _build_stat_box(self, label: str, value_lbl: QLabel) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        
        lbl = QLabel(label)
        lbl.setStyleSheet(f"color:{TEXT_SECONDARY}; font-size:13px; font-weight:600; background:transparent;")
        
        lay.addWidget(lbl)
        lay.addWidget(value_lbl)
        lay.addStretch()
        return w

    def update_stats(self, data: dict) -> None:
        """Update the UI with data from /sessions/my-performance"""
        completed = data.get("completed_sessions", 0)
        avg_score = data.get("average_mcq_score", 0.0)
        avg_trust = data.get("average_integrity_score", 0.0)
        flags = data.get("total_proctoring_events", 0)

        self._lbl_completed.setText(str(completed))
        self._lbl_avg_score.setText(f"{avg_score}%")
        self._lbl_avg_trust.setText(f"{avg_trust}%")
        self._lbl_flags.setText(str(flags))
