from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from client.modules.dashboard.dashboard_shell import DashboardCard, SHELL_BORDER


_NAVY = "#0F2454"
_TXT = "#111827"
_TXT_MUTED = "#6B7280"
_CHIP_NAVY = "#0F2454"
_CHIP_GREY = "#E5E7EB"
_CHIP_FG_W = "#FFFFFF"
_CHIP_FG_D = "#374151"
_BORDER = SHELL_BORDER


@dataclass(frozen=True)
class _SliderSpec:
    key: str
    label: str
    left_label: str
    mid_label: str
    right_label: str
    default: int
    chip_text: str
    chip_dark: bool


_SLIDERS: list[_SliderSpec] = [
    _SliderSpec(
        key="gaze",
        label="Gaze Deviation",
        left_label="Relaxed",
        mid_label="Standard",
        right_label="Aggressive",
        default=75,
        chip_text="75% High",
        chip_dark=True,
    ),
    _SliderSpec(
        key="audio",
        label="Audio Anomaly Detection",
        left_label="Low Noise",
        mid_label="Balanced",
        right_label="High Fidelity",
        default=40,
        chip_text="40% Balanced",
        chip_dark=False,
    ),
    _SliderSpec(
        key="object",
        label="Prohibited Object Detection",
        left_label="Basic",
        mid_label="Intermediate",
        right_label="Strict",
        default=90,
        chip_text="90% Strict",
        chip_dark=True,
    ),
]


def _pct_label(value: int, spec: _SliderSpec) -> str:
    if value < 35:
        tier = spec.left_label
    elif value < 65:
        tier = spec.mid_label
    else:
        tier = spec.right_label
    return f"{value}% {tier}"


class _SliderRow(QWidget):
    value_changed = Signal(str, int)

    def __init__(self, spec: _SliderSpec, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._spec = spec
        self.setStyleSheet("background: transparent;")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        top = QHBoxLayout()
        top.setSpacing(8)

        lbl = QLabel(spec.label)
        lbl.setStyleSheet(
            f"font-size: 16px; font-weight: 800; color: {_TXT}; background: transparent;"
        )
        top.addWidget(lbl)

        info = QLabel("ⓘ")
        info.setStyleSheet(f"color: {_TXT_MUTED}; font-size: 14px; background: transparent;")
        top.addWidget(info)
        top.addStretch(1)

        self._chip = QLabel(spec.chip_text)
        self._apply_chip_style(spec.chip_dark)
        top.addWidget(self._chip)

        root.addLayout(top)

        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(0, 100)
        self._slider.setValue(spec.default)
        self._slider.setStyleSheet(self._slider_qss())
        self._slider.valueChanged.connect(self._on_change)
        root.addWidget(self._slider)

        axis = QHBoxLayout()
        for txt, align in (
            (spec.left_label, Qt.AlignmentFlag.AlignLeft),
            (spec.mid_label, Qt.AlignmentFlag.AlignCenter),
            (spec.right_label, Qt.AlignmentFlag.AlignRight),
        ):
            a = QLabel(txt)
            a.setAlignment(align)
            a.setStyleSheet(f"font-size: 12px; color: {_TXT_MUTED}; background: transparent;")
            axis.addWidget(a, 1)
        root.addLayout(axis)

    def _apply_chip_style(self, dark: bool) -> None:
        bg = _CHIP_NAVY if dark else _CHIP_GREY
        fg = _CHIP_FG_W if dark else _CHIP_FG_D
        self._chip.setStyleSheet(
            f"background-color: {bg}; color: {fg};"
            f"border-radius: 10px; padding: 4px 14px;"
            f"font-size: 13px; font-weight: 800;"
        )

    @staticmethod
    def _slider_qss() -> str:
        return f"""
            QSlider::groove:horizontal {{
                height: 4px;
                background: #D1D5DB;
                border-radius: 2px;
            }}
            QSlider::sub-page:horizontal {{
                background: {_NAVY};
                border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                width: 20px;
                height: 20px;
                margin: -8px 0;
                background: {_NAVY};
                border-radius: 10px;
                border: 3px solid white;
            }}
        """

    def _on_change(self, value: int) -> None:
        dark = value >= 65
        self._chip.setText(_pct_label(value, self._spec))
        self._apply_chip_style(dark)
        self.value_changed.emit(self._spec.key, value)

    def get_value(self) -> int:
        return self._slider.value()

    def set_value(self, value: int) -> None:
        self._slider.setValue(value)


class AIMonitoringCard(DashboardCard):
    value_changed = Signal(str, int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent=parent)
        root = self.content_layout
        root.setSpacing(0)
        root.setContentsMargins(28, 24, 28, 28)

        hdr = QHBoxLayout()
        icon = QLabel("◎")
        icon.setStyleSheet(f"font-size: 20px; color: {_TXT}; background: transparent;")
        title = QLabel("AI Monitoring Sensitivity")
        title.setStyleSheet(
            f"font-size: 20px; font-weight: 900; color: {_TXT}; background: transparent;"
        )
        hdr.addWidget(icon)
        hdr.addSpacing(8)
        hdr.addWidget(title)
        hdr.addStretch(1)
        root.addLayout(hdr)
        root.addSpacing(8)

        desc = QLabel(
            "Adjust the algorithmic threshold for behavioral anomalies. "
            "Higher sensitivity increases flag frequency but may result in more false positives."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet(
            f"font-size: 13px; color: {_TXT_MUTED}; background: transparent;"
        )
        root.addWidget(desc)
        root.addSpacing(24)

        self._rows: dict[str, _SliderRow] = {}
        for i, spec in enumerate(_SLIDERS):
            row = _SliderRow(spec)
            row.value_changed.connect(self.value_changed)
            self._rows[spec.key] = row
            root.addWidget(row)
            if i < len(_SLIDERS) - 1:
                div = QFrame()
                div.setFixedHeight(1)
                div.setStyleSheet(f"background: {_BORDER};")
                root.addSpacing(20)
                root.addWidget(div)
                root.addSpacing(20)

    def get_values(self) -> dict[str, int]:
        return {k: r.get_value() for k, r in self._rows.items()}

    def set_values(self, values: dict[str, int]) -> None:
        for k, v in values.items():
            if k in self._rows:
                self._rows[k].set_value(v)

