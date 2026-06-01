"""
client/modules/dashboard/examiner_overview.py

Composes the examiner overview page from smaller section modules.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from client.modules.examiner_dashboard.views.components.examiner_alert_feed_section import AlertFeedCard
from client.modules.examiner_dashboard.views.components.examiner_exam_management_section import ExamManagementCard
from client.modules.examiner_dashboard.views.components.examiner_metric_section import ExaminerMetricsSection
from client.modules.examiner_dashboard.scripts.examiner_overview_models import AlertSpec, ExamRowSpec, MetricSpec
from client.modules.examiner_dashboard.scripts.examiner_overview_theme import BG_PAGE


class ExaminerOverviewPage(QWidget):
    new_schedule_clicked = Signal()
    delete_draft_requested = Signal(str)
    status_change_requested = Signal(str, str)
    dismiss_alert_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet(f"background-color: {BG_PAGE};")

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(18)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(18)

        metrics = [
            MetricSpec("blue", "Loading...", False, "-", "Total Active Students", "👥"),
            MetricSpec("red", "Loading...", False, "-", "Flagged Sessions", "⚑"),
            MetricSpec("amber", "Loading...", False, "-", "Proctors Online", "🛡"),
        ]
        self._metrics_section = ExaminerMetricsSection(metrics)
        left_layout.addWidget(self._metrics_section)

        self._exam_card = ExamManagementCard()
        self._exam_card.new_schedule_clicked.connect(self.new_schedule_clicked)
        self._exam_card.delete_draft_requested.connect(self.delete_draft_requested)
        self._exam_card.status_change_requested.connect(self.status_change_requested)
        left_layout.addWidget(self._exam_card, 1)

        root.addWidget(left, 1)
        self._alert_feed = AlertFeedCard()
        self._alert_feed.dismiss_requested.connect(self.dismiss_alert_requested)
        root.addWidget(self._alert_feed)

    def set_overview_data(
        self,
        metrics: list[MetricSpec],
        exams: list[ExamRowSpec],
        alerts: list[AlertSpec],
        latency_ms: int = 24,
    ) -> None:
        self._metrics_section.set_metrics(metrics)
        self._exam_card.set_rows(exams)
        self._alert_feed.set_alerts(alerts)
        self._alert_feed.set_latency(latency_ms)


__all__ = [
    "AlertSpec",
    "ExamRowSpec",
    "ExaminerOverviewPage",
    "MetricSpec",
]
