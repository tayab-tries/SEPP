from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from client.modules.examiner_dashboard.views.dashboard_shell import DashboardCard
from client.modules.examiner_dashboard.settings.settings_comms import CommunicationPermissionsCard
from client.modules.examiner_dashboard.settings.settings_right_panel import (
    LockdownRulesCard,
    SecurityAdvisoryCard,
)
from client.modules.examiner_dashboard.settings.settings_sliders import AIMonitoringCard


class ExaminerSettingsView(QWidget):
    def __init__(
        self,
        apply_shadow: Callable[[QWidget], None] | None = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._apply_shadow = apply_shadow or (lambda _widget: None)

        self._status_label = QLabel("Static preview only. Changes are stored locally until backend wiring is added.")
        self._ai_card = AIMonitoringCard()
        self._comms_card = CommunicationPermissionsCard()
        self._lockdown_card = LockdownRulesCard()
        self._advisory_card = SecurityAdvisoryCard()

        self._build()
        self._wire()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("background: transparent;")

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        content_lay = QVBoxLayout(content)
        content_lay.setContentsMargins(0, 0, 8, 20)
        content_lay.setSpacing(18)

        intro_card = DashboardCard()
        intro = intro_card.content_layout
        intro.setContentsMargins(24, 22, 24, 22)
        intro.setSpacing(8)

        eyebrow = QLabel("Exam Security Profile")
        eyebrow.setStyleSheet(
            "font-size: 12px; font-weight: 800; letter-spacing: 1px; color: #6E7B91;"
        )
        title = QLabel("Configure static invigilation defaults")
        title.setStyleSheet("font-size: 24px; font-weight: 900; color: #0F2454;")
        subtitle = QLabel(
            "Tune sensitivity, communication permissions, and lockdown behavior for the current examiner theme. "
            "This screen is static for now, so changes are visual only."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("font-size: 13px; color: #6E7B91;")
        self._status_label.setWordWrap(True)
        self._status_label.setStyleSheet(
            "font-size: 13px; font-weight: 700; color: #163564; background: #E9F1FF; border-radius: 10px; padding: 10px 12px;"
        )

        intro.addWidget(eyebrow)
        intro.addWidget(title)
        intro.addWidget(subtitle)
        intro.addSpacing(6)
        intro.addWidget(self._status_label)
        self._apply_shadow(intro_card)
        content_lay.addWidget(intro_card)

        body = QHBoxLayout()
        body.setSpacing(18)

        left_col = QVBoxLayout()
        left_col.setSpacing(18)
        self._apply_shadow(self._ai_card)
        self._apply_shadow(self._comms_card)
        left_col.addWidget(self._ai_card)
        left_col.addWidget(self._comms_card)
        left_col.addStretch(1)

        right_col = QVBoxLayout()
        right_col.setSpacing(18)
        self._apply_shadow(self._lockdown_card)
        self._apply_shadow(self._advisory_card)
        right_col.addWidget(self._lockdown_card)
        right_col.addWidget(self._advisory_card)
        right_col.addStretch(1)

        body.addLayout(left_col, 7)
        body.addLayout(right_col, 4)
        content_lay.addLayout(body)
        content_lay.addStretch(1)

        scroll.setWidget(content)
        root.addWidget(scroll)

    def _wire(self) -> None:
        self._ai_card.value_changed.connect(self._on_slider_changed)
        self._comms_card.permission_changed.connect(self._on_permission_changed)
        self._lockdown_card.rule_changed.connect(self._on_rule_changed)

    def _on_slider_changed(self, key: str, value: int) -> None:
        label = {
            "gaze": "Gaze deviation",
            "audio": "Audio anomaly detection",
            "object": "Prohibited object detection",
        }.get(key, key)
        self._status_label.setText(
            f"{label} updated to {value}%. Static preview only; no server persistence yet."
        )

    def _on_permission_changed(self, key: str, enabled: bool) -> None:
        label = {
            "direct_chat": "Direct proctor chat",
            "global_announce": "Global announcements",
            "peer_interact": "Peer interaction",
        }.get(key, key)
        state = "enabled" if enabled else "disabled"
        self._status_label.setText(
            f"{label} {state}. Static preview only; this does not affect live sessions yet."
        )

    def _on_rule_changed(self, key: str, enabled: bool) -> None:
        label = {
            "browser_lockdown": "Browser lockdown",
            "clipboard_block": "Clipboard block",
            "external_display": "External display blocking",
        }.get(key, key)
        state = "enabled" if enabled else "disabled"
        self._status_label.setText(
            f"{label} {state}. Static preview only; backend policy wiring comes later."
        )
