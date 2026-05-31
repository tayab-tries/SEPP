from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from client.modules.examiner_dashboard.views.dashboard_shell import DashboardCard
from client.modules.examiner_dashboard.scripts.examiner_overview_models import MetricSpec
from client.modules.examiner_dashboard.scripts.examiner_overview_theme import (
    ACCENT_AMB_BG,
    ACCENT_BLUE,
    ACCENT_RED_BG,
    NAVY,
    SEVERITY_CRITICAL,
    TXT_SECONDARY,
)


_METRIC_STYLES: dict[str, tuple[str, str, str]] = {
    "blue": (ACCENT_BLUE, NAVY, "#82B0FF"),
    "red": (ACCENT_RED_BG, SEVERITY_CRITICAL, "#F2B0B0"),
    "amber": (ACCENT_AMB_BG, "#7A5800", "#FFCB66"),
}


def _build_chip(text: str, live: bool, fg: str, bg: str) -> QWidget:
    chip = QWidget()
    chip.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    chip.setStyleSheet(f"background-color: {bg}; border-radius: 8px;")

    layout = QHBoxLayout(chip)
    layout.setContentsMargins(8, 4, 8, 4)
    layout.setSpacing(5)

    if live:
        dot = QLabel("●")
        dot.setStyleSheet("color: #E53E3E; font-size: 9px; background: transparent;")
        layout.addWidget(dot)

    label = QLabel(text)
    label.setStyleSheet(
        f"color: {fg}; font-size: 12px; font-weight: 700; background: transparent;"
    )
    layout.addWidget(label)
    return chip


class MetricCard(DashboardCard):
    def __init__(self, spec: MetricSpec, parent: QWidget | None = None) -> None:
        super().__init__(parent=parent)
        root = self.content_layout
        root.setSpacing(6)

        top = QHBoxLayout()
        top.setSpacing(0)

        self._icon_lbl = QLabel()
        self._icon_lbl.setFixedSize(48, 48)
        self._icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        top.addWidget(self._icon_lbl)
        top.addStretch(1)

        self._chip_host = QWidget()
        self._chip_host.setStyleSheet("background: transparent;")
        self._chip_layout = QVBoxLayout(self._chip_host)
        self._chip_layout.setContentsMargins(0, 0, 0, 0)
        self._chip_layout.setSpacing(0)
        top.addWidget(self._chip_host)
        root.addLayout(top)

        self._value_lbl = QLabel()
        root.addWidget(self._value_lbl)

        self._title_lbl = QLabel()
        self._title_lbl.setStyleSheet(
            f"font-size: 14px; color: {TXT_SECONDARY}; background: transparent;"
        )
        root.addWidget(self._title_lbl)
        self.set_spec(spec)

    def set_spec(self, spec: MetricSpec) -> None:
        icon_bg, value_color, chip_color = _METRIC_STYLES.get(spec.tone, _METRIC_STYLES["blue"])
        self._icon_lbl.setText(spec.icon)
        self._icon_lbl.setStyleSheet(
            f"background-color: {icon_bg}; color: {value_color};"
            f"border-radius: 12px; font-size: 20px;"
        )
        while self._chip_layout.count():
            item = self._chip_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._chip_layout.addWidget(
            _build_chip(spec.chip_text, spec.chip_is_live, chip_color, icon_bg)
        )
        self._value_lbl.setText(spec.value)
        self._value_lbl.setStyleSheet(
            f"font-size: 44px; font-weight: 900; color: {value_color};"
            f"background: transparent; letter-spacing: -1px;"
        )
        self._title_lbl.setText(spec.title)


class ExaminerMetricsSection(QWidget):
    def __init__(self, metrics: list[MetricSpec], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._cards: list[MetricCard] = []

        grid = QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(0)

        for col, spec in enumerate(metrics):
            card = MetricCard(spec)
            self._cards.append(card)
            grid.addWidget(card, 0, col)

    def set_metrics(self, metrics: list[MetricSpec]) -> None:
        for card, spec in zip(self._cards, metrics):
            card.set_spec(spec)
