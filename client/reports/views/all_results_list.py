from __future__ import annotations

from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QFrame, QSizePolicy, QScrollArea, QDialog
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCursor

# Tokens
CARD_BG          = "#ffffff"
BORDER_COLOR     = "#e5e7eb"
TEXT_PRIMARY     = "#0d1b2e"
TEXT_SECONDARY   = "#6b7280"
TEXT_MUTED       = "#9ca3af"
CARD_RADIUS      = 10
PROGRESS_BG      = "#e8eaed"
PROGRESS_FILL    = "#1a2d4e"
ACCENT_GREEN     = "#22c55e"
ACCENT_RED       = "#ef4444"

class ExamStatusDialog(QDialog):
    """
    Dialog shown when clicking an exam result.
    Shows whether the exam is graded and offers Review or Report actions.
    """
    review_requested = Signal(str, str) # session_id, exam_id
    
    def __init__(self, data: dict, parent=None):
        super().__init__(parent)
        self.data = data
        self.session_id = data.get("session_id")
        self.exam_id = data.get("exam_id")
        self.is_graded = data.get("is_graded", False)
        
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(True)
        self.setFixedWidth(380)

        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        
        card = QWidget()
        card.setObjectName("dialogCard")
        card.setStyleSheet(f"""
            QWidget#dialogCard {{
                background: {CARD_BG};
                border-radius: 12px;
                border: 1px solid {BORDER_COLOR};
            }}
        """)
        
        card_lay = QVBoxLayout(card)
        card_lay.setContentsMargins(24, 24, 24, 24)
        card_lay.setSpacing(16)
        
        # Header
        header_lay = QHBoxLayout()
        header_lay.setContentsMargins(0, 0, 0, 0)
        
        status_text = "Exam Graded" if self.is_graded else "Exam Not Graded"
        title = QLabel(status_text)
        title.setStyleSheet(f"color:{TEXT_PRIMARY}; font-size:18px; font-weight:800;")
        
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(28, 28)
        close_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {TEXT_SECONDARY}; border: none; font-size: 14px; font-weight: 800;
            }}
            QPushButton:hover {{ color: {TEXT_PRIMARY}; }}
        """)
        close_btn.clicked.connect(self.reject)
        
        header_lay.addWidget(title)
        header_lay.addStretch()
        header_lay.addWidget(close_btn)
        
        # Subtitle
        sub = QLabel(f"Result for: {self.data.get('exam_title', 'Unknown Exam')}")
        sub.setStyleSheet(f"color:{TEXT_SECONDARY}; font-size:13px;")
        sub.setWordWrap(True)
        
        # Buttons
        btn_lay = QHBoxLayout()
        btn_lay.setSpacing(12)
        
        self.review_btn = QPushButton("Review")
        self.review_btn.setFixedHeight(38)
        self.review_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.review_btn.setStyleSheet(f"""
            QPushButton {{
                background: #f3f4f6; color: {TEXT_PRIMARY}; font-weight: 600; font-size: 13px; border-radius: 6px; border: 1px solid {BORDER_COLOR};
            }}
            QPushButton:hover {{ background: #e5e7eb; }}
        """)
        self.review_btn.clicked.connect(self._on_review)
        
        self.report_btn = QPushButton("Check Report")
        self.report_btn.setFixedHeight(38)
        self.report_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        if self.is_graded:
            self.report_btn.setStyleSheet(f"""
                QPushButton {{
                    background: #1a2d4e; color: white; font-weight: 600; font-size: 13px; border-radius: 6px; border: none;
                }}
                QPushButton:hover {{ background: #253d5e; }}
            """)
        else:
            self.report_btn.setEnabled(False)
            self.report_btn.setStyleSheet(f"""
                QPushButton {{
                    background: #d1d5db; color: #9ca3af; font-weight: 600; font-size: 13px; border-radius: 6px; border: none;
                }}
            """)
        
        self.report_btn.clicked.connect(self._on_report)
        
        btn_lay.addWidget(self.review_btn)
        btn_lay.addWidget(self.report_btn)
        
        card_lay.addLayout(header_lay)
        card_lay.addWidget(sub)
        card_lay.addSpacing(8)
        card_lay.addLayout(btn_lay)
        
        outer.addWidget(card)

    def _on_review(self):
        self.review_requested.emit(self.session_id, self.exam_id)
        self.accept()

    def _on_report(self):
        from .report_card_dialog import ReportCardDialog
        dialog = ReportCardDialog(self.data, parent=self.window())
        dialog.exec()
        self.accept()

class _ResultItem(QWidget):
    """Single result entry for the list."""
    clicked = Signal(dict)

    def __init__(self, data: dict) -> None:
        super().__init__()
        self.data = data
        self.session_id = data.get("session_id")
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setMinimumHeight(72)
        self.setMaximumHeight(72)
        self.setStyleSheet("background: transparent;")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 6, 0, 4)
        root.setSpacing(4)

        # Date formatting
        date_str = data.get("started_at")
        date_formatted = date_str
        if date_str:
            try:
                dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                date_formatted = dt.strftime("%b %d, %Y • %I:%M %p")
            except ValueError:
                pass

        date_lbl = QLabel(date_formatted)
        date_lbl.setStyleSheet(f"color:{TEXT_MUTED}; font-size:10px; font-weight:600;")

        row = QHBoxLayout()
        row.setSpacing(8)

        title_lbl = QLabel(data.get("exam_title", "Untitled Exam"))
        title_lbl.setStyleSheet(f"color:{TEXT_PRIMARY}; font-size:13px; font-weight:700;")
        title_lbl.setWordWrap(False)
        title_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        score = data.get("total_score", 0.0) or 0.0
        score_lbl = QLabel(f"{score}%")
        score_lbl.setFixedSize(52, 18)
        score_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        score_lbl.setStyleSheet(
            f"color:{ACCENT_GREEN if score >= 50 else ACCENT_RED}; font-size:13px; font-weight:800;"
        )

        row.addWidget(title_lbl)
        row.addWidget(score_lbl)

        pbar = QProgressBar()
        pbar.setFixedHeight(6)
        pbar.setTextVisible(False)
        pbar.setRange(0, 100)
        pbar.setValue(int(score))
        pbar.setStyleSheet(f"""
            QProgressBar {{ background: {PROGRESS_BG}; border-radius: 3px; border: none; }}
            QProgressBar::chunk {{ background: {PROGRESS_FILL}; border-radius: 3px; }}
        """)

        div = QFrame()
        div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet(f"color: {BORDER_COLOR};")

        root.addWidget(date_lbl)
        root.addLayout(row)
        root.addWidget(pbar)
        root.addStretch()
        root.addWidget(div)

    def mousePressEvent(self, event):
        if self.session_id:
            self.clicked.emit(self.data)
        super().mousePressEvent(event)

class AllResultsList(QWidget):
    """
    Scrollable list displaying all exam history.
    """
    review_requested = Signal(str, str) # session_id, exam_id

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            AllResultsList {{
                background: {CARD_BG};
                border-radius: {CARD_RADIUS}px;
                border: 1px solid {BORDER_COLOR};
            }}
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(16)

        title = QLabel("All Attempted Exams")
        title.setStyleSheet(f"color:{TEXT_PRIMARY}; font-size:16px; font-weight:700; background:transparent;")
        root.addWidget(title)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QScrollArea > QWidget > QWidget { background: transparent; }
            QScrollBar:vertical { width: 6px; background: transparent; }
            QScrollBar::handle:vertical { background: #D1D5DB; border-radius: 3px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
        """)

        self._list_container = QWidget()
        self._list_lay = QVBoxLayout(self._list_container)
        self._list_lay.setContentsMargins(0, 0, 10, 0)
        self._list_lay.setSpacing(0)
        self._list_lay.addStretch()

        self._scroll.setWidget(self._list_container)
        root.addWidget(self._scroll, stretch=1)

    def update_history(self, history: list[dict]) -> None:
        # Clear existing
        while self._list_lay.count() > 1:
            item = self._list_lay.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        # Sort by date descending (already done by backend typically, but let's ensure)
        sorted_history = sorted(
            history,
            key=lambda x: x.get("started_at") or "",
            reverse=True
        )

        for data in sorted_history:
            item_widget = _ResultItem(data)
            item_widget.clicked.connect(self._on_item_clicked)
            self._list_lay.insertWidget(self._list_lay.count() - 1, item_widget)

    def _on_item_clicked(self, data: dict):
        dialog = ExamStatusDialog(data, parent=self.window())
        dialog.review_requested.connect(self.review_requested.emit)
        dialog.exec()
