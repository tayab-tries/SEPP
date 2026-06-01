from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from client.modules.examiner_dashboard.views.dashboard_shell import DashboardCard, SHELL_BORDER


_NAVY = "#0F2454"
_TXT = "#111827"
_TXT_MUTED = "#6B7280"
_TXT_DIM = "#9CA3AF"
_BORDER = SHELL_BORDER
_BG_CHECKED = "#FFFFFF"
_BG_DISABLED = "#F7F9FC"
_CHECK_ON = "#0F2454"
_CHECK_OFF = "#D1D5DB"


@dataclass(frozen=True)
class _PermSpec:
    key: str
    title: str
    desc: str
    default: bool
    locked: bool


_PERMS: list[_PermSpec] = [
    _PermSpec(
        key="direct_chat",
        title="Direct Proctor Chat",
        desc="Allow students to initiate 1-to-1 chat for technical assistance.",
        default=True,
        locked=False,
    ),
    _PermSpec(
        key="global_announce",
        title="Global Announcements",
        desc="Enable broadcast messages to all active candidates simultaneously.",
        default=True,
        locked=False,
    ),
    _PermSpec(
        key="peer_interact",
        title="Peer Interaction",
        desc="Allow candidate-to-candidate messaging (Institutional Disable).",
        default=False,
        locked=True,
    ),
]


class _CheckTile(QFrame):
    toggled = Signal(str, bool)

    def __init__(self, spec: _PermSpec, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._spec = spec
        self._checked = spec.default
        self._locked = spec.locked

        self._apply_frame_style()
        self.setCursor(
            Qt.CursorShape.ArrowCursor if spec.locked else Qt.CursorShape.PointingHandCursor
        )

        lay = QHBoxLayout(self)
        lay.setContentsMargins(18, 18, 18, 18)
        lay.setSpacing(14)

        self._box = QLabel()
        self._box.setFixedSize(22, 22)
        self._apply_box_style()

        text_w = QWidget()
        text_w.setStyleSheet("background: transparent;")
        text_lay = QVBoxLayout(text_w)
        text_lay.setContentsMargins(0, 0, 0, 0)
        text_lay.setSpacing(3)

        title_color = _TXT_DIM if spec.locked else _TXT
        self._title_lbl = QLabel(spec.title)
        self._title_lbl.setStyleSheet(
            f"font-size: 14px; font-weight: 800; color: {title_color}; background: transparent; border: none;"
        )
        self._desc_lbl = QLabel(spec.desc)
        self._desc_lbl.setWordWrap(True)
        self._desc_lbl.setStyleSheet(
            f"font-size: 12px; color: {_TXT_DIM if spec.locked else _TXT_MUTED}; background: transparent; border: none;"
        )
        text_lay.addWidget(self._title_lbl)
        text_lay.addWidget(self._desc_lbl)

        lay.addWidget(self._box, 0, Qt.AlignmentFlag.AlignTop)
        lay.addWidget(text_w, 1)

    def mousePressEvent(self, event) -> None:
        if not self._locked:
            self._checked = not self._checked
            self._apply_box_style()
            self._apply_frame_style()
            self.toggled.emit(self._spec.key, self._checked)
        super().mousePressEvent(event)

    def _apply_frame_style(self) -> None:
        if self._locked:
            self.setStyleSheet(
                f"QFrame {{ background-color: {_BG_DISABLED};"
                f"border: 1.5px solid {_BORDER}; border-radius: 12px; }}"
            )
        elif self._checked:
            self.setStyleSheet(
                f"QFrame {{ background-color: {_BG_CHECKED};"
                f"border: 1.5px solid {_NAVY}; border-radius: 12px; }}"
            )
        else:
            self.setStyleSheet(
                f"QFrame {{ background-color: {_BG_CHECKED};"
                f"border: 1.5px solid {_BORDER}; border-radius: 12px; }}"
            )

    def _apply_box_style(self) -> None:
        if self._locked:
            self._box.setText("")
            self._box.setStyleSheet(
                f"background-color: {_CHECK_OFF}; border-radius: 5px;"
            )
        elif self._checked:
            self._box.setText("✓")
            self._box.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._box.setStyleSheet(
                f"background-color: {_CHECK_ON}; color: white;"
                f"border-radius: 5px; font-size: 14px; font-weight: 900;"
            )
        else:
            self._box.setText("")
            self._box.setStyleSheet(
                f"background-color: white; border: 2px solid {_CHECK_OFF}; border-radius: 5px;"
            )

    def is_checked(self) -> bool:
        return self._checked

    def set_checked(self, value: bool) -> None:
        if not self._locked:
            self._checked = value
            self._apply_box_style()
            self._apply_frame_style()


class CommunicationPermissionsCard(DashboardCard):
    permission_changed = Signal(str, bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent=parent)
        root = self.content_layout
        root.setSpacing(0)
        root.setContentsMargins(28, 24, 28, 28)

        hdr = QHBoxLayout()
        icon = QLabel("▣")
        icon.setStyleSheet(f"font-size: 18px; color: {_TXT}; background: transparent;")
        title = QLabel("Communication Permissions")
        title.setStyleSheet(
            f"font-size: 20px; font-weight: 900; color: {_TXT}; background: transparent;"
        )
        hdr.addWidget(icon)
        hdr.addSpacing(8)
        hdr.addWidget(title)
        hdr.addStretch(1)
        root.addLayout(hdr)
        root.addSpacing(20)

        tiles_row = QHBoxLayout()
        tiles_row.setSpacing(14)

        self._tiles: dict[str, _CheckTile] = {}
        for spec in _PERMS:
            tile = _CheckTile(spec)
            tile.toggled.connect(self.permission_changed)
            tile.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            self._tiles[spec.key] = tile
            tiles_row.addWidget(tile)

        root.addLayout(tiles_row)

    def get_permissions(self) -> dict[str, bool]:
        return {k: t.is_checked() for k, t in self._tiles.items()}

    def set_permissions(self, values: dict[str, bool]) -> None:
        for k, v in values.items():
            if k in self._tiles:
                self._tiles[k].set_checked(v)

