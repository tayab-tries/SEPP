from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from client.dashboard.views.sidebar import SidebarWidget, MAIN_BG, TOP_BAR_BG, BORDER_COLOR


SHELL_BG = "#EEF3F8"
SHELL_CARD = "#FFFFFF"
SHELL_BORDER = "#D6DEE8"
SHELL_TEXT = "#0F2454"
SHELL_TEXT_MUTED = "#6E7B91"
SHELL_NAV_BG = "#F7FAFD"
SHELL_NAV_ACTIVE = "#163564"
SHELL_NAV_ACTIVE_TEXT = "#F4F7FB"
SHELL_NAV_HOVER = "#E6EDF6"
SHELL_ACTION = "#0F2E5F"
SHELL_ACTION_HOVER = "#163C79"
SHELL_INPUT = "#F1F4F8"


def load_svg_icon(icon_name: str, size: int = 18) -> QIcon | None:
    try:
        project_root = Path(__file__).resolve().parents[3]
        icon_path = project_root / "assets" / "Icon" / f"{icon_name}.svg"
        if not icon_path.exists():
            return None
        renderer = QSvgRenderer(str(icon_path))
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        return QIcon(pixmap)
    except Exception:
        return None


@dataclass(frozen=True)
class DashboardNavSpec:
    key: str
    label: str
    icon_name: str = ""


class DashboardSidebar(QWidget):
    nav_selected = Signal(str)

    def __init__(
        self,
        title: str,
        subtitle: str,
        items: Iterable[DashboardNavSpec],
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._label_to_key = {spec.label: spec.key for spec in items}
        self._key_to_label = {spec.key: spec.label for spec in items}

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._sidebar = SidebarWidget()
        self._sidebar.nav_clicked.connect(self._on_nav_clicked)
        root.addWidget(self._sidebar)

    def set_active(self, key: str) -> None:
        label = self._key_to_label.get(key)
        if label:
            self._sidebar.set_active_label(label)

    def _on_nav_clicked(self, label: str) -> None:
        key = self._label_to_key.get(label)
        if key:
            self.nav_selected.emit(key)


class DashboardTopBar(QFrame):
    def __init__(self, section_title: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("dashboardTopBar")
        self._section_title = QLabel(section_title)

        root = QHBoxLayout(self)
        root.setContentsMargins(22, 16, 22, 16)
        root.setSpacing(18)

        left = QHBoxLayout()
        brand = QLabel("SEPP")
        brand.setStyleSheet(f"font-size: 24px; font-weight: 900; color: {SHELL_TEXT};")
        divider = QLabel("|")
        divider.setStyleSheet(f"font-size: 24px; color: {SHELL_BORDER};")
        self._section_title.setStyleSheet("font-size: 16px; color: #202939;")
        left.addWidget(brand)
        left.addWidget(divider)
        left.addWidget(self._section_title)
        left.addStretch(1)

        right = QHBoxLayout()
        right.setSpacing(10)

        search = QLineEdit()
        search.setPlaceholderText("Search sessions...")
        search.setFixedWidth(390)
        search.setMinimumHeight(40)
        search.setStyleSheet(
            f"""
            QLineEdit {{
                background-color: {SHELL_INPUT};
                border: 1px solid {SHELL_BORDER};
                border-radius: 12px;
                padding: 0 16px;
                color: #1B2433;
                font-size: 14px;
            }}
            """
        )
        right.addWidget(search)

        for label in ("▣", "◔", "◉", "◔"):
            right.addWidget(self._icon_chip(label))

        avatar = QLabel("D")
        avatar.setFixedSize(38, 38)
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar.setStyleSheet(
            "background-color: #0F2E5F; color: white; border-radius: 19px; font-size: 14px; font-weight: 800;"
        )
        right.addWidget(avatar)

        root.addLayout(left, 1)
        root.addLayout(right)

        self.setStyleSheet(
            f"""
            QFrame#dashboardTopBar {{
                background-color: {TOP_BAR_BG};
                border-bottom: 1px solid {BORDER_COLOR};
            }}
            """
        )

    def _icon_chip(self, label: str) -> QLabel:
        chip = QLabel(label)
        chip.setFixedSize(30, 30)
        chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        chip.setStyleSheet(
            "background-color: transparent; color: #202939; font-size: 16px; font-weight: 700;"
        )
        return chip

    def set_section_title(self, title: str) -> None:
        self._section_title.setText(title)


class DashboardHeader(QWidget):
    def __init__(self, title: str, subtitle: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        self._title = QLabel(title)
        self._subtitle = QLabel(subtitle)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(2)

        self._title.setStyleSheet(f"font-size: 26px; font-weight: 800; color: {SHELL_TEXT};")
        self._subtitle.setStyleSheet(f"font-size: 13px; color: {SHELL_TEXT_MUTED};")
        self._subtitle.setWordWrap(True)
        root.addWidget(self._title)
        root.addWidget(self._subtitle)

    def set_text(self, title: str, subtitle: str = "") -> None:
        self._title.setText(title)
        self._subtitle.setText(subtitle)
        self._subtitle.setVisible(bool(subtitle))


class DashboardCard(QFrame):
    def __init__(self, title: str = "", subtitle: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("dashboardCard")
        self._content_layout = QVBoxLayout(self)
        self._content_layout.setContentsMargins(18, 18, 18, 18)
        self._content_layout.setSpacing(10)

        if title:
            title_label = QLabel(title)
            title_label.setStyleSheet(f"font-size: 18px; font-weight: 700; color: {SHELL_TEXT};")
            self._content_layout.addWidget(title_label)

        if subtitle:
            subtitle_label = QLabel(subtitle)
            subtitle_label.setWordWrap(True)
            subtitle_label.setStyleSheet(f"font-size: 12px; color: {SHELL_TEXT_MUTED};")
            self._content_layout.addWidget(subtitle_label)

        self.setStyleSheet(
            f"""
            QFrame#dashboardCard {{
                background-color: {SHELL_CARD};
                border: 1px solid {SHELL_BORDER};
                border-radius: 18px;
            }}
            """
        )

    @property
    def content_layout(self) -> QVBoxLayout:
        return self._content_layout


class DashboardScaffold(QWidget):
    def __init__(
        self,
        sidebar: DashboardSidebar,
        top_bar: DashboardTopBar,
        header: DashboardHeader,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.sidebar = sidebar
        self.top_bar = top_bar
        self.header = header

        self._body_host = QWidget()
        self._body_layout = QVBoxLayout(self._body_host)
        self._body_layout.setContentsMargins(0, 0, 0, 0)
        self._body_layout.setSpacing(0)

        right_col = QVBoxLayout()
        right_col.setContentsMargins(28, 20, 28, 20)
        right_col.setSpacing(16)
        right_col.addWidget(self.header)
        right_col.addWidget(self._body_host, 1)

        split = QHBoxLayout()
        split.setContentsMargins(0, 0, 0, 0)
        split.setSpacing(0)
        split.addWidget(self.sidebar)

        right = QWidget()
        right.setLayout(right_col)
        split.addWidget(right, 1)

        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)
        main.addWidget(self.top_bar)

        content = QWidget()
        content.setLayout(split)
        main.addWidget(content, 1)

        self.setStyleSheet(f"background-color: {MAIN_BG};")

    def set_body(self, widget: QWidget) -> None:
        while self._body_layout.count():
            item = self._body_layout.takeAt(0)
            child = item.widget()
            if child is not None:
                child.setParent(None)
        self._body_layout.addWidget(widget)

    def set_header_visible(self, visible: bool) -> None:
        self.header.setVisible(visible)
