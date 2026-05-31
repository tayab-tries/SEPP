from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
    QFrame,
)

from client.modules.examiner_dashboard.views.dashboard_shell import DashboardCard, SHELL_BORDER


_NAVY = "#0F2454"
_TXT = "#111827"
_TXT_MUTED = "#6B7280"
_BORDER = SHELL_BORDER
_ON_BG = _NAVY
_OFF_BG = "#D1D5DB"
_HANDLE = "#FFFFFF"


@dataclass(frozen=True)
class _ToggleSpec:
    key: str
    label: str
    sublabel: str
    default: bool


_RULES: list[_ToggleSpec] = [
    _ToggleSpec("browser_lockdown", "Browser Lockdown", "Prevent tab switching", True),
    _ToggleSpec("clipboard_block", "Clipboard Block", "Disable Copy/Paste", True),
    _ToggleSpec("external_display", "External Display", "Block second screen", False),
]


class _ToggleSwitch(QWidget):
    toggled = Signal(bool)

    _W, _H = 52, 28

    def __init__(self, checked: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._checked = checked
        self.setFixedSize(self._W, self._H)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._update_style()

    def _update_style(self) -> None:
        bg = _ON_BG if self._checked else _OFF_BG
        handle_left = self._W - self._H + 2 if self._checked else 2
        self.setStyleSheet(
            f"""
            QWidget {{
                background-color: {bg};
                border-radius: {self._H // 2}px;
            }}
            """
        )
        if not hasattr(self, "_handle"):
            self._handle = QLabel(self)
            self._handle.setFixedSize(self._H - 4, self._H - 4)
            self._handle.setStyleSheet(
                f"background-color: {_HANDLE}; border-radius: {(self._H - 4) // 2}px;"
            )
        self._handle.move(handle_left, 2)

    def mousePressEvent(self, event) -> None:
        self._checked = not self._checked
        self._update_style()
        self.toggled.emit(self._checked)
        super().mousePressEvent(event)

    def is_checked(self) -> bool:
        return self._checked

    def set_checked(self, value: bool) -> None:
        self._checked = value
        self._update_style()


class _ToggleRow(QWidget):
    rule_changed = Signal(str, bool)

    def __init__(self, spec: _ToggleSpec, last: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._spec = spec
        border = "" if last else f"border-bottom: 1px solid {_BORDER};"
        self.setStyleSheet(f"background: transparent; {border}")

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 14, 0, 14)
        lay.setSpacing(12)

        text_w = QWidget()
        text_w.setStyleSheet("background: transparent;")
        text_lay = QVBoxLayout(text_w)
        text_lay.setContentsMargins(0, 0, 0, 0)
        text_lay.setSpacing(2)

        lbl = QLabel(spec.label)
        lbl.setStyleSheet(
            f"font-size: 14px; font-weight: 800; color: {_TXT}; background: transparent;"
        )
        sub = QLabel(spec.sublabel)
        sub.setStyleSheet(
            f"font-size: 12px; color: {_TXT_MUTED}; background: transparent;"
        )
        text_lay.addWidget(lbl)
        text_lay.addWidget(sub)

        self._toggle = _ToggleSwitch(spec.default)
        self._toggle.toggled.connect(lambda v: self.rule_changed.emit(self._spec.key, v))

        lay.addWidget(text_w, 1)
        lay.addWidget(self._toggle, 0, Qt.AlignmentFlag.AlignVCenter)

    def is_checked(self) -> bool:
        return self._toggle.is_checked()

    def set_checked(self, value: bool) -> None:
        self._toggle.set_checked(value)


class LockdownRulesCard(DashboardCard):
    rule_changed = Signal(str, bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent=parent)
        root = self.content_layout
        root.setSpacing(0)
        root.setContentsMargins(22, 20, 22, 20)

        hdr = QHBoxLayout()
        lock_icon = QLabel("🔒")
        lock_icon.setStyleSheet("font-size: 16px; background: transparent;")
        title = QLabel("Lockdown Rules")
        title.setStyleSheet(
            f"font-size: 17px; font-weight: 900; color: {_TXT}; background: transparent;"
        )
        hdr.addWidget(lock_icon)
        hdr.addSpacing(6)
        hdr.addWidget(title)
        hdr.addStretch(1)
        root.addLayout(hdr)
        root.addSpacing(8)

        self._rows: dict[str, _ToggleRow] = {}
        for i, spec in enumerate(_RULES):
            row = _ToggleRow(spec, last=(i == len(_RULES) - 1))
            row.rule_changed.connect(self.rule_changed)
            self._rows[spec.key] = row
            root.addWidget(row)

    def get_rules(self) -> dict[str, bool]:
        return {k: r.is_checked() for k, r in self._rows.items()}

    def set_rules(self, values: dict[str, bool]) -> None:
        for k, v in values.items():
            if k in self._rows:
                self._rows[k].set_checked(v)


class SecurityAdvisoryCard(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet(
            f"QFrame {{ background-color: {_NAVY}; border-radius: 16px; }}"
        )

        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 20, 22, 20)
        lay.setSpacing(10)

        label = QLabel("SECURITY ADVISORY")
        label.setStyleSheet(
            "font-size: 11px; font-weight: 800; color: rgba(255,255,255,140);"
            "letter-spacing: 1.5px; background: transparent;"
        )
        lay.addWidget(label)

        body = QLabel(
            "Current settings meet <b>Tier 3 Secure Standard</b>. "
            "Any reduction in sensitivity may violate institutional policy."
        )
        body.setWordWrap(True)
        body.setStyleSheet(
            "font-size: 13px; color: rgba(255,255,255,210); background: transparent;"
        )
        body.setTextFormat(Qt.TextFormat.RichText)
        lay.addWidget(body)

        link = QLabel('<a href="#" style="color: #6EB5FF; font-weight: 800;">View Policy Guidelines →</a>')
        link.setTextFormat(Qt.TextFormat.RichText)
        link.setStyleSheet("background: transparent;")
        link.setOpenExternalLinks(False)
        lay.addWidget(link)

        shield = QLabel("🛡")
        shield.setStyleSheet(
            "font-size: 64px; color: rgba(255,255,255,18);"
            "background: transparent;"
        )
        shield.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom)
        lay.addWidget(shield)

