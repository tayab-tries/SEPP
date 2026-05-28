from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from client.modules.dashboard.examiner_overview_models import AlertSpec
from client.modules.dashboard.examiner_overview_theme import (
    BG_CARD,
    BORDER_CARD,
    SEVERITY_CRITICAL,
    SEVERITY_INFO,
    SEVERITY_MODERATE,
    TXT_MUTED,
    TXT_PRIMARY,
    TXT_SECONDARY,
)


class _AlertItem(QFrame):
    def __init__(self, spec: AlertSpec, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("alertItem")

        accent, badge_bg, action_bg = {
            "critical": (SEVERITY_CRITICAL, "#FFE8E8", "#FFF0F0"),
            "moderate": (SEVERITY_MODERATE, "#FFF2D9", "#FFF6E3"),
            "info": (SEVERITY_INFO, "#F3F6F9", "#F6F8FB"),
        }[spec.severity]

        self.setStyleSheet(
            f"""
            QFrame#alertItem {{
                background-color: {BG_CARD};
                border-left: 4px solid {accent};
                border-top: 1px solid #F2F5F8;
                border-right: 1px solid #F2F5F8;
                border-bottom: 1px solid #F2F5F8;
                border-radius: 14px;
            }}
            """
        )
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(8)

        top = QHBoxLayout()
        sev_lbl = QLabel(spec.severity.upper())
        sev_lbl.setStyleSheet(
            f"font-size: 11px; font-weight: 900; color: {accent}; background: transparent;"
        )
        age_lbl = QLabel(spec.age)
        age_lbl.setStyleSheet(
            f"font-size: 11px; color: {TXT_MUTED}; background: transparent;"
        )
        top.addWidget(sev_lbl)
        top.addStretch(1)
        top.addWidget(age_lbl)
        root.addLayout(top)

        title_lbl = QLabel(spec.title)
        title_lbl.setWordWrap(True)
        title_lbl.setStyleSheet(
            "font-size: 15px; font-weight: 800; color: #161F2C; background: transparent;"
        )
        root.addWidget(title_lbl)

        body_lbl = QLabel(spec.body)
        body_lbl.setWordWrap(True)
        body_lbl.setStyleSheet(
            "font-size: 12px; color: #4A5566; background: transparent;"
        )
        root.addWidget(body_lbl)

        act_row = QHBoxLayout()
        act_row.setSpacing(8)
        act_row.addWidget(self._action_btn(spec.action_primary, accent, action_bg))
        if spec.action_secondary:
            act_row.addWidget(self._ghost_btn(spec.action_secondary, badge_bg))
        act_row.addStretch(1)
        root.addLayout(act_row)

    def _action_btn(self, text: str, fg: str, bg: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setEnabled(False)
        btn.setFixedHeight(30)
        btn.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {bg};
                color: {fg};
                border: none;
                border-radius: 8px;
                padding: 0 12px;
                font-size: 12px;
                font-weight: 800;
            }}
            """
        )
        return btn

    def _ghost_btn(self, text: str, bg: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setEnabled(False)
        btn.setFixedHeight(30)
        btn.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {bg};
                color: #525F72;
                border: none;
                border-radius: 8px;
                padding: 0 12px;
                font-size: 12px;
                font-weight: 700;
            }}
            """
        )
        return btn


class AlertFeedCard(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("alertFeedCard")
        self.setFixedWidth(360)
        self.setStyleSheet(
            f"""
            QFrame#alertFeedCard {{
                background-color: {BG_CARD};
                border: 1px solid {BORDER_CARD};
                border-radius: 18px;
            }}
            """
        )

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        header_w = QWidget()
        header_w.setStyleSheet("background: transparent;")
        header_lay = QHBoxLayout(header_w)
        header_lay.setContentsMargins(20, 18, 20, 14)

        title = QLabel("Alert Feed")
        title.setStyleSheet(
            f"font-size: 18px; font-weight: 800; color: {TXT_PRIMARY}; background: transparent;"
        )
        controls = QLabel("≡  ↻")
        controls.setStyleSheet(
            f"font-size: 16px; color: {TXT_PRIMARY}; background: transparent;"
        )
        controls.setCursor(Qt.CursorShape.PointingHandCursor)
        header_lay.addWidget(title)
        header_lay.addStretch(1)
        header_lay.addWidget(controls)
        outer.addWidget(header_w)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            """
            QScrollArea {
                background: transparent;
            }
            QScrollArea > QWidget > QWidget {
                background: transparent;
            }
            """
        )

        content_w = QWidget()
        content_w.setStyleSheet("background: transparent;")
        self._alerts_layout = QVBoxLayout(content_w)
        self._alerts_layout.setContentsMargins(14, 6, 14, 14)
        self._alerts_layout.setSpacing(12)
        self.set_alerts([])
        scroll.setWidget(content_w)
        outer.addWidget(scroll, 1)

        footer_w = QWidget()
        footer_w.setStyleSheet("background: transparent;")
        footer_lay = QVBoxLayout(footer_w)
        footer_lay.setContentsMargins(20, 10, 20, 16)
        footer_lay.setSpacing(6)

        latency_row = QHBoxLayout()
        lat_lbl = QLabel("System Latency")
        lat_lbl.setStyleSheet(
            f"font-size: 13px; color: {TXT_SECONDARY}; background: transparent;"
        )
        self._lat_val = QLabel("24ms")
        self._lat_val.setStyleSheet(
            "font-size: 13px; font-weight: 800; color: #5AB680; background: transparent;"
        )
        latency_row.addWidget(lat_lbl)
        latency_row.addStretch(1)
        latency_row.addWidget(self._lat_val)
        footer_lay.addLayout(latency_row)

        bar_bg = QFrame()
        bar_bg.setObjectName("latencyBarBg")
        bar_bg.setFixedHeight(8)
        bar_bg.setStyleSheet(
            """
            QFrame#latencyBarBg {
                background-color: #DCE6EF;
                border: none;
                border-radius: 4px;
            }
            """
        )
        bar_fill = QFrame(bar_bg)
        bar_fill.setObjectName("latencyBarFill")
        bar_fill.setGeometry(0, 0, 260, 8)
        bar_fill.setStyleSheet(
            """
            QFrame#latencyBarFill {
                background-color: #7AD39E;
                border: none;
                border-radius: 4px;
            }
            """
        )
        footer_lay.addWidget(bar_bg)

        outer.addWidget(footer_w)

    def set_alerts(self, alerts: list[AlertSpec]) -> None:
        while self._alerts_layout.count():
            item = self._alerts_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        if not alerts:
            empty = QLabel("No recent alerts.")
            empty.setStyleSheet(
                f"padding: 12px 4px; font-size: 13px; color: {TXT_SECONDARY}; background: transparent;"
            )
            self._alerts_layout.addWidget(empty)
            self._alerts_layout.addStretch(1)
            return
        for spec in alerts:
            self._alerts_layout.addWidget(_AlertItem(spec))
        self._alerts_layout.addStretch(1)

    def set_latency(self, latency_ms: int) -> None:
        self._lat_val.setText(f"{latency_ms}ms")
