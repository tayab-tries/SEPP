from typing import Callable
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QFrame, QSizePolicy
)
from PySide6.QtCore import Qt, Signal
from client.dashboard.views.sidebar import MAIN_BG

CARD_BG        = "#ffffff"
BORDER_COLOR   = "#e5e7eb"
TEXT_PRIMARY   = "#0d1b2e"
TEXT_SECONDARY = "#6b7280"

class _LogEventItem(QFrame):
    def __init__(self, data: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("logEventItem")
        
        severity = data.get("severity", "info").lower()
        accent, bg = {
            "critical": ("#ef4444", "#fef2f2"),
            "moderate": ("#f59e0b", "#fffbeb"),
            "warning":  ("#f59e0b", "#fffbeb"),
            "info":     ("#3b82f6", "#eff6ff"),
        }.get(severity, ("#6b7280", "#f3f4f6"))

        self.setStyleSheet(f"""
            QFrame#logEventItem {{
                background-color: {CARD_BG};
                border-left: 4px solid {accent};
                border-top: 1px solid {BORDER_COLOR};
                border-right: 1px solid {BORDER_COLOR};
                border-bottom: 1px solid {BORDER_COLOR};
                border-radius: 8px;
            }}
        """)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(6)

        top_row = QHBoxLayout()
        ev_type_lbl = QLabel(str(data.get("event_type", "UNKNOWN")).upper())
        ev_type_lbl.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {accent}; background: transparent;")
        
        timestamp = str(data.get("timestamp", ""))
        if "T" in timestamp:
            timestamp = timestamp.replace("T", " ")[:19]
            
        time_lbl = QLabel(timestamp)
        time_lbl.setStyleSheet(f"font-size: 12px; color: {TEXT_SECONDARY}; background: transparent;")
        
        top_row.addWidget(ev_type_lbl)
        top_row.addStretch()
        top_row.addWidget(time_lbl)
        root.addLayout(top_row)

        metadata = data.get("metadata")
        if metadata:
            meta_str = str(metadata)
            meta_lbl = QLabel(meta_str)
            meta_lbl.setWordWrap(True)
            meta_lbl.setStyleSheet(f"font-size: 13px; color: {TEXT_PRIMARY}; background: transparent;")
            root.addWidget(meta_lbl)

        examiner_note = data.get("examiner_note")
        if examiner_note:
            note_lbl = QLabel(f"Note: {examiner_note}")
            note_lbl.setWordWrap(True)
            note_lbl.setStyleSheet(f"font-size: 12px; font-style: italic; color: #4b5563; background: transparent;")
            root.addWidget(note_lbl)


class StudentLogsView(QWidget):
    back_requested = Signal()

    def __init__(self, apply_shadow: Callable[[QWidget], None], parent: QWidget | None = None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"background: {MAIN_BG};")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 20, 28, 20)
        layout.setSpacing(16)
        
        # Header
        header_row = QVBoxLayout()
        header_row.setSpacing(12)
        self._back_btn = QPushButton("← Back to Student Attempt")
        self._back_btn.setFixedWidth(200)
        self._back_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #3b82f6;
                border: 1px solid #3b82f6;
                border-radius: 6px;
                padding: 6px 12px;
                font-weight: bold;
            }
            QPushButton:hover { background: #eff6ff; }
        """)
        self._back_btn.clicked.connect(self.back_requested)
        header_row.addWidget(self._back_btn)
        
        title_row = QHBoxLayout()
        self._title_lbl = QLabel("Student Proctoring Logs")
        self._title_lbl.setStyleSheet("font-size: 24px; font-weight: bold; color: #0d1b2e;")
        
        self._count_badge = QLabel("0 EVENTS")
        self._count_badge.setStyleSheet(f"""
            color: {TEXT_SECONDARY};
            background: #f3f4f6;
            border: 1px solid {BORDER_COLOR};
            border-radius: 12px;
            padding: 4px 12px;
            font-size: 12px;
            font-weight: 600;
        """)

        title_row.addWidget(self._title_lbl)
        title_row.addStretch()
        title_row.addWidget(self._count_badge)
        header_row.addLayout(title_row)
        layout.addLayout(header_row)

        # Scroll area
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._scroll.setStyleSheet("""
            QScrollArea {
                background: transparent;
            }
            QScrollBar:vertical {
                width: 8px;
                background: transparent;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #cbd5e1;
                border-radius: 4px;
                min-height: 30px;
            }
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar::add-page:vertical,
            QScrollBar::sub-page:vertical {
                background: transparent;
            }
        """)

        self._inner = QWidget()
        self._inner.setStyleSheet("background: transparent;")
        
        self._inner_lay = QVBoxLayout(self._inner)
        self._inner_lay.setContentsMargins(0, 0, 8, 20)
        self._inner_lay.setSpacing(12)
        self._inner_lay.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        self._scroll.setWidget(self._inner)
        layout.addWidget(self._scroll, stretch=1)

    def _clear_logs(self) -> None:
        while self._inner_lay.count():
            item = self._inner_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def set_loading(self) -> None:
        self._clear_logs()
        self._count_badge.setText("— EVENTS")
        loading_lbl = QLabel("Fetching logs...")
        loading_lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 14px;")
        loading_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._inner_lay.addWidget(loading_lbl)

    def set_logs(self, events: list[dict], session_id: str) -> None:
        self._clear_logs()
        self._title_lbl.setText(f"Proctoring Logs")
        self._count_badge.setText(f"{len(events)} EVENTS")
        
        if not events:
            empty_lbl = QLabel("No proctoring events recorded for this session.")
            empty_lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 14px;")
            empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._inner_lay.addWidget(empty_lbl)
            return

        for data in events:
            self._inner_lay.addWidget(_LogEventItem(data))

    def set_error(self, message: str) -> None:
        self._clear_logs()
        self._count_badge.setText("— EVENTS")
        err_lbl = QLabel(f"Could not load logs: {message}")
        err_lbl.setStyleSheet("color: #ef4444; font-size:14px;")
        err_lbl.setWordWrap(True)
        self._inner_lay.addWidget(err_lbl)
