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
from client.Shared.top_bar_icon import TopBarIcon, get_initials


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
    sign_out_requested = Signal()

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

        unicode_icons = {
            "Dashboard": "⊞",
            "Exams": "☰",
            "Assessments": "✎",
            "Monitoring": "◉",
            "Reports": "▦",
            "Settings": "⚙"
        }
        nav_items = [(unicode_icons.get(spec.label, "▪"), spec.label) for spec in items]

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._sidebar = SidebarWidget(title=title, subtitle=subtitle, nav_items=nav_items)
        self._sidebar.nav_clicked.connect(self._on_nav_clicked)
        self._sidebar.sign_out_clicked.connect(self.sign_out_requested.emit)
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
        self.setFixedHeight(56)
        self.setStyleSheet(f"""
            QFrame#dashboardTopBar {{
                background: {TOP_BAR_BG};
                border-bottom: 1px solid {BORDER_COLOR};
            }}
        """)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(22, 0, 22, 0)
        lay.setSpacing(16)

        logo = QLabel()
        logo.setTextFormat(Qt.TextFormat.RichText)
        logo.setText(
            f'<span style="color:#0d1b2e; font-size:17px; font-weight:900;">SEPP</span>'
            f'<span style="color:#4a90d9; font-size:17px; font-weight:700;"> SECURE</span>'
        )
        logo.setStyleSheet("background:transparent;")
        lay.addWidget(logo)
        lay.addStretch()

        # Icon row (camera, signal, bell)
        for icon_kind in ["camera", "signal", "bell"]:
            icon_btn = TopBarIcon(icon_kind)
            lay.addWidget(icon_btn)

        # Avatar circle showing initials
        self.avatar = QLabel(get_initials("Examiner"))
        self.avatar.setFixedSize(32, 32)
        self.avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.avatar.setStyleSheet("""
            background: #4a90d9;
            color: white;
            border-radius: 16px;
            font-size: 13px;
            font-weight: 800;
        """)
        lay.addWidget(self.avatar)

    def set_section_title(self, title: str) -> None:
        pass

    def update_user_info(self, name: str) -> None:
        self.avatar.setText(get_initials(name))


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
