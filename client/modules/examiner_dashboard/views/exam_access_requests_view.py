from __future__ import annotations

import csv
from typing import Optional, Callable
from datetime import datetime

from PySide6.QtCore import Qt, Signal, Slot, QSize, QTimer
from PySide6.QtGui import QIcon, QCursor, QColor
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QScrollArea,
    QFileDialog,
    QDialog,
    QLineEdit,
    QFormLayout,
    QGraphicsDropShadowEffect,
)


def get_initials(name: str) -> str:
    if not name:
        return "?"
    parts = name.split()
    if len(parts) >= 2:
        return (parts[0][0] + parts[-1][0]).upper()
    return name[0].upper()


def get_avatar_color(name: str) -> str:
    colors = ["#adc7f7", "#7d5700", "#5caf81", "#ffdad6", "#adc7f7", "#d6e3ff", "#ffdeaa", "#83d8a6"]
    if not name:
        return colors[0]
    val = sum(ord(c) for c in name)
    return colors[val % len(colors)]


class ScrollListWidget(QScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setStyleSheet("background: transparent; border: none;")
        
        self.container = QWidget()
        self.container.setStyleSheet("background: transparent;")
        self.layout = QVBoxLayout(self.container)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(8)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        self.setWidget(self.container)
        
        # Style vertical scroll bar to match Tailwind custom scrollbar
        self.verticalScrollBar().setStyleSheet("""
            QScrollBar:vertical {
                width: 6px;
                background: transparent;
            }
            QScrollBar::handle:vertical {
                background: #c4c6cf;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical:hover {
                background: #a0a2aa;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

    def clear(self):
        while self.layout.count():
            item = self.layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def add_row(self, widget: QWidget):
        self.layout.addWidget(widget)


class ExamCardWidget(QFrame):
    def __init__(self, row: dict, is_selected: bool = False, parent=None):
        super().__init__(parent)
        self.row = row
        self._is_selected = is_selected
        self._build_ui()
        self.set_selected(is_selected)

    def _build_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(16, 16, 16, 16)
        self.layout.setSpacing(8)

        # Top row (Badge & Selection Indicator)
        self.top_row = QHBoxLayout()
        self.badge = QLabel("CURRENT")
        self.badge.setStyleSheet("""
            background-color: #ffc250;
            color: #725000;
            border-radius: 4px;
            padding: 2px 8px;
            font-size: 10px;
            font-weight: bold;
            border: none;
        """)
        self.top_row.addWidget(self.badge)
        self.top_row.addStretch()

        self.icon_lbl = QLabel("✔")
        self.icon_lbl.setStyleSheet("font-size: 12px; font-weight: bold; border: none;")
        self.top_row.addWidget(self.icon_lbl)
        self.layout.addLayout(self.top_row)

        self.title_lbl = QLabel(str(self.row.get("title") or "Untitled Exam"))
        self.title_lbl.setWordWrap(True)
        self.title_lbl.setStyleSheet("font-size: 14px; font-weight: bold; border: none; background: transparent;")
        self.layout.addWidget(self.title_lbl)

        self.subtitle_lbl = QLabel()
        self.subtitle_lbl.setStyleSheet("font-size: 12px; border: none; background: transparent;")
        self.layout.addWidget(self.subtitle_lbl)

    def set_selected(self, selected: bool):
        self._is_selected = selected
        waiting = self.row.get("waiting_count", 0)
        approved = self.row.get("approved_count", 0)
        self.subtitle_lbl.setText(f"{waiting} Waiting • {approved} Approved")

        if selected:
            self.setStyleSheet("""
                QFrame {
                    background-color: #1a365d;
                    color: #ffffff;
                    border: 1px solid #1a365d;
                    border-radius: 8px;
                }
            """)
            self.badge.show()
            self.icon_lbl.show()
            self.title_lbl.setStyleSheet("color: white; font-size: 14px; font-weight: bold; border: none; background: transparent;")
            self.subtitle_lbl.setStyleSheet("color: #86a0cd; font-size: 12px; border: none; background: transparent;")
            self.icon_lbl.setStyleSheet("color: white; font-size: 12px; font-weight: bold; border: none; background: transparent;")
        else:
            self.setStyleSheet("""
                QFrame {
                    background-color: #ffffff;
                    color: #181c1e;
                    border: 1px solid #c4c6cf;
                    border-radius: 8px;
                }
            """)
            self.badge.hide()
            self.icon_lbl.hide()
            self.title_lbl.setStyleSheet("color: #181c1e; font-size: 14px; font-weight: bold; border: none; background: transparent;")
            self.subtitle_lbl.setStyleSheet("color: #43474e; font-size: 12px; border: none; background: transparent;")



class PendingRequestRow(QFrame):
    approve_clicked = Signal(str) # request_id
    deny_clicked = Signal(str) # request_id

    def __init__(self, row: dict, parent=None):
        super().__init__(parent)
        self.row = row
        self.request_id = str(row.get("request_id") or "")
        self._build_ui()

    def _build_ui(self):
        self.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: 1px solid #e0e3e5;
                border-radius: 8px;
            }
        """)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(12)

        # Avatar circle
        name = str(self.row.get("student_name") or "Unknown Student")
        initials = get_initials(name)
        self.avatar = QLabel(initials)
        self.avatar.setFixedSize(32, 32)
        self.avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.avatar.setStyleSheet(f"""
            background-color: {get_avatar_color(name)};
            color: #ffffff;
            border-radius: 16px;
            font-size: 11px;
            font-weight: bold;
            border: none;
        """)
        lay.addWidget(self.avatar)

        # Middle Column (Name + ID/Time)
        mid = QVBoxLayout()
        mid.setSpacing(2)
        
        name_lbl = QLabel(name)
        name_lbl.setStyleSheet("font-size: 13px; font-weight: 600; color: #181c1e; border: none; background: transparent;")
        mid.addWidget(name_lbl)
        
        req_at = str(self.row.get("requested_at") or "")
        display_time = req_at.replace("T", " ")[:16] if req_at else "Unknown time"
        std_id = str(self.row.get("student_id") or "")[:8]
        sub_lbl = QLabel(f"ID: #{std_id} • {display_time}")
        sub_lbl.setStyleSheet("font-size: 11px; color: #43474e; border: none; background: transparent;")
        mid.addWidget(sub_lbl)
        
        lay.addLayout(mid, 1)

        # Action Buttons
        actions = QHBoxLayout()
        actions.setSpacing(8)
        
        deny_btn = QPushButton("Deny")
        deny_btn.setFixedSize(56, 28)
        deny_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        deny_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: 1px solid #74777f;
                color: #002045;
                font-size: 11px;
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: rgba(0, 32, 69, 0.05);
            }
        """)
        deny_btn.clicked.connect(lambda: self.deny_clicked.emit(self.request_id))
        actions.addWidget(deny_btn)

        approve_btn = QPushButton("Approve")
        approve_btn.setFixedSize(68, 28)
        approve_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        approve_btn.setStyleSheet("""
            QPushButton {
                background-color: #002045;
                border: none;
                color: #ffffff;
                font-size: 11px;
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #1a365d;
            }
        """)
        approve_btn.clicked.connect(lambda: self.approve_clicked.emit(self.request_id))
        actions.addWidget(approve_btn)

        lay.addLayout(actions)


class ApprovedCandidateRow(QFrame):
    revoke_clicked = Signal(str) # request_id

    def __init__(self, row: dict, parent=None):
        super().__init__(parent)
        self.row = row
        self.request_id = str(row.get("request_id") or "")
        self._build_ui()

    def _build_ui(self):
        self.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: 1px solid #e0e3e5;
                border-radius: 8px;
            }
        """)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(12)

        # Avatar circle
        name = str(self.row.get("student_name") or "Unknown Student")
        initials = get_initials(name)
        self.avatar = QLabel(initials)
        self.avatar.setFixedSize(32, 32)
        self.avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.avatar.setStyleSheet(f"""
            background-color: {get_avatar_color(name)};
            color: #ffffff;
            border-radius: 16px;
            font-size: 11px;
            font-weight: bold;
            border: none;
        """)
        lay.addWidget(self.avatar)

        # Middle Column (Name + Invite Method)
        mid = QVBoxLayout()
        mid.setSpacing(2)
        
        name_lbl = QLabel(name)
        name_lbl.setStyleSheet("font-size: 13px; font-weight: 600; color: #181c1e; border: none; background: transparent;")
        mid.addWidget(name_lbl)
        
        sub_lbl = QLabel("Code Entry")
        sub_lbl.setStyleSheet("font-size: 11px; color: #5caf81; border: none; background: transparent;")
        mid.addWidget(sub_lbl)
        
        lay.addLayout(mid, 1)

        # Revoke/Close Button
        revoke_btn = QPushButton("×")
        revoke_btn.setFixedSize(24, 24)
        revoke_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        revoke_btn.setStyleSheet("""
            QPushButton {
                background-color: #ffdad6;
                color: #93000a;
                border: none;
                border-radius: 12px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #ba1a1a;
                color: #ffffff;
            }
        """)
        revoke_btn.clicked.connect(lambda: self.revoke_clicked.emit(self.request_id))
        lay.addWidget(revoke_btn)


class AddCandidateDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Candidate")
        self.setFixedSize(360, 160)
        self._email = ""
        self._build_ui()

    def _build_ui(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #f7fafc;
            }
            QLabel {
                font-size: 12px;
                color: #181c1e;
                font-weight: bold;
            }
            QLineEdit {
                background-color: #ffffff;
                border: 1px solid #c4c6cf;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 12px;
                color: #181c1e;
            }
            QLineEdit:focus {
                border: 2px solid #002045;
            }
        """)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(12)

        form = QFormLayout()
        form.setSpacing(8)
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("student@institution.edu")
        form.addRow("Student Email:", self.email_input)
        lay.addLayout(form)

        # Buttons
        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        buttons.addStretch()

        cancel = QPushButton("Cancel")
        cancel.setFixedSize(70, 30)
        cancel.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: 1px solid #74777f;
                color: #181c1e;
                font-size: 12px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: rgba(0,0,0,0.05);
            }
        """)
        cancel.clicked.connect(self.reject)
        buttons.addWidget(cancel)

        add_btn = QPushButton("Add")
        add_btn.setFixedSize(70, 30)
        add_btn.setStyleSheet("""
            QPushButton {
                background-color: #002045;
                border: none;
                color: #ffffff;
                font-size: 12px;
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #1a365d;
            }
        """)
        add_btn.clicked.connect(self._on_add)
        buttons.addWidget(add_btn)
        lay.addLayout(buttons)

    def _on_add(self):
        self._email = self.email_input.text().strip()
        if self._email:
            self.accept()

    def get_email(self) -> str:
        return self._email


class ExaminerAccessRequestsView(QWidget):
    refresh_requested = Signal()
    exam_selected = Signal(str)
    approve_requested = Signal(str, str)
    reject_requested = Signal(str, str)
    approve_all_requested = Signal(str) # exam_id
    revoke_all_requested = Signal(str) # exam_id
    add_candidate_requested = Signal(str, str) # exam_id, email

    def __init__(self, apply_shadow, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._apply_shadow = apply_shadow
        self._selected_exam_id = ""
        self._selected_exam = {}
        self._pending_requests = []
        self._approved_candidates = []

        self._build_ui()

    def _build_ui(self):
        self.setStyleSheet("""
            ExaminerAccessRequestsView {
                background-color: #f7fafc;
            }
            QLabel {
                font-family: 'Inter';
            }
        """)

        # Main vertical layout
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(16)

        # 1. Context Header Area
        self.header_widget = QWidget()
        self.header_widget.setStyleSheet("background: transparent;")
        header_lay = QVBoxLayout(self.header_widget)
        header_lay.setContentsMargins(0, 0, 0, 0)
        header_lay.setSpacing(6)

        # Exam Title & Status pill
        title_row = QHBoxLayout()
        self.exam_title_lbl = QLabel("Select an Exam")
        self.exam_title_lbl.setStyleSheet("color: #002045; font-size: 26px; font-weight: 800;")
        title_row.addWidget(self.exam_title_lbl)
        title_row.addSpacing(16)

        self.status_pill = QFrame()
        self.status_pill.setStyleSheet("""
            QFrame {
                background-color: rgba(92, 175, 129, 0.15);
                border: 1px solid rgba(92, 175, 129, 0.3);
                border-radius: 12px;
            }
        """)
        pill_lay = QHBoxLayout(self.status_pill)
        pill_lay.setContentsMargins(10, 4, 10, 4)
        pill_lay.setSpacing(6)
        
        self.pulse_dot = QLabel("●")
        self.pulse_dot.setStyleSheet("color: #5caf81; font-size: 10px;")
        self.status_text = QLabel("Live Monitoring Active")
        self.status_text.setStyleSheet("color: #002715; font-size: 11px; font-weight: 600; border: none;")
        pill_lay.addWidget(self.pulse_dot)
        pill_lay.addWidget(self.status_text)
        title_row.addWidget(self.status_pill)
        
        # Session ID sub-info
        self.session_id_lbl = QLabel("Session ID: --")
        self.session_id_lbl.setStyleSheet("color: #43474e; font-size: 13px; font-weight: 500;")
        title_row.addSpacing(16)
        title_row.addWidget(self.session_id_lbl)
        
        title_row.addStretch()
        header_lay.addLayout(title_row)
        root.addWidget(self.header_widget)

        # 2. Three-Pane Horizontal Layout
        pane_layout = QHBoxLayout()
        pane_layout.setSpacing(16)

        # Left Pane: Active Exams selection
        self.left_pane = QFrame()
        self.left_pane.setStyleSheet("""
            QFrame {
                background-color: #f1f4f6;
                border: 1px solid #c4c6cf;
                border-radius: 12px;
            }
        """)
        self._apply_shadow(self.left_pane)
        left_lay = QVBoxLayout(self.left_pane)
        left_lay.setContentsMargins(16, 16, 16, 16)
        left_lay.setSpacing(12)

        left_title = QLabel("Active Exams")
        left_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #002045; border: none;")
        left_lay.addWidget(left_title)

        self._exam_list = QListWidget()
        self._exam_list.setStyleSheet("""
            QListWidget {
                background: transparent;
                border: none;
            }
            QListWidget::item {
                background: transparent;
                border: none;
                margin-bottom: 8px;
            }
        """)
        left_lay.addWidget(self._exam_list, 1)

        self._view_assessments_btn = QPushButton("View All Assessments")
        self._view_assessments_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._view_assessments_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: 1px solid #002045;
                color: #002045;
                border-radius: 8px;
                padding: 8px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(0, 32, 69, 0.05);
            }
        """)
        left_lay.addWidget(self._view_assessments_btn)
        pane_layout.addWidget(self.left_pane, 3)

        # Middle Pane: Pending Access Requests
        self.middle_pane = QFrame()
        self.middle_pane.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: 1px solid #c4c6cf;
                border-radius: 12px;
            }
        """)
        self._apply_shadow(self.middle_pane)
        mid_lay = QVBoxLayout(self.middle_pane)
        mid_lay.setContentsMargins(16, 16, 16, 16)
        mid_lay.setSpacing(12)

        mid_header = QHBoxLayout()
        mid_title = QLabel("Pending Requests")
        mid_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #002045; border: none;")
        mid_header.addWidget(mid_title)
        
        self._approve_all_btn = QPushButton("Approve All")
        self._approve_all_btn.setFixedSize(96, 30)
        self._approve_all_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._approve_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #002045;
                color: #ffffff;
                border-radius: 6px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1a365d;
            }
        """)
        self._approve_all_btn.clicked.connect(self._on_approve_all_clicked)
        mid_header.addWidget(self._approve_all_btn)
        mid_lay.addLayout(mid_header)

        # Pending Requests Scroll List
        self._pending_scroll = ScrollListWidget()
        mid_lay.addWidget(self._pending_scroll, 1)

        # Bottom warning alert bar
        self.warning_bar = QFrame()
        self.warning_bar.setStyleSheet("""
            QFrame {
                background-color: rgba(255, 194, 80, 0.1);
                border: 1px solid rgba(255, 194, 80, 0.3);
                border-radius: 8px;
            }
        """)
        warn_lay = QHBoxLayout(self.warning_bar)
        warn_lay.setContentsMargins(10, 8, 10, 8)
        warn_lay.setSpacing(8)
        
        warn_icon = QLabel("🛡")
        warn_icon.setStyleSheet("color: #7d5700; font-size: 14px; border: none;")
        warn_txt = QLabel("Manual validation required for biometric flags.")
        warn_txt.setStyleSheet("color: #5f4100; font-size: 11px; font-weight: 500; border: none; background: transparent;")
        warn_lay.addWidget(warn_icon)
        warn_lay.addWidget(warn_txt, 1)
        mid_lay.addWidget(self.warning_bar)
        
        pane_layout.addWidget(self.middle_pane, 5)

        # Right Pane: Approved Candidates
        self.right_pane = QFrame()
        self.right_pane.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: 1px solid #c4c6cf;
                border-radius: 12px;
            }
        """)
        self._apply_shadow(self.right_pane)
        right_lay = QVBoxLayout(self.right_pane)
        right_lay.setContentsMargins(16, 16, 16, 16)
        right_lay.setSpacing(12)

        right_header = QHBoxLayout()
        right_title = QLabel("Approved")
        right_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #002045; border: none;")
        right_header.addWidget(right_title)

        self._download_btn = QPushButton("📥 List")
        self._download_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._download_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                color: #002045;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                text-decoration: underline;
                color: #1a365d;
            }
        """)
        self._download_btn.clicked.connect(self._export_csv)
        right_header.addWidget(self._download_btn)
        right_lay.addLayout(right_header)

        self.approved_subtitle = QLabel("0 Students in Session")
        self.approved_subtitle.setStyleSheet("font-size: 12px; color: #43474e; font-weight: 500; border: none;")
        right_lay.addWidget(self.approved_subtitle)

        # Approved Candidates Scroll List
        self._approved_scroll = ScrollListWidget()
        right_lay.addWidget(self._approved_scroll, 1)

        # Revoke All Access Button
        self._revoke_all_btn = QPushButton("Revoke All Access")
        self._revoke_all_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._revoke_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #ba1a1a;
                color: #ffffff;
                border-radius: 8px;
                padding: 8px;
                font-size: 12px;
                font-weight: bold;
                border: none;
            }
            QPushButton:hover {
                background-color: #93000a;
            }
        """)
        self._revoke_all_btn.clicked.connect(self._on_revoke_all_clicked)
        right_lay.addWidget(self._revoke_all_btn)

        pane_layout.addWidget(self.right_pane, 4)
        root.addLayout(pane_layout, 1)

        # Status / Message Area
        self._status = QLabel("")
        self._status.setStyleSheet("font-size: 12px; color: #43474e;")
        self._status.setWordWrap(True)
        root.addWidget(self._status)

        # 3. Floating Action Button (FAB) for Manual Add
        self._fab = QPushButton(self)
        self._fab.setFixedSize(56, 56)
        self._fab.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._fab.setText("+")
        self._fab.setToolTip("Add Candidate")
        self._fab.setStyleSheet("""
            QPushButton {
                background-color: #1a365d;
                color: #ffffff;
                border: none;
                border-radius: 28px;
                font-size: 28px;
                font-weight: 300;
            }
            QPushButton:hover {
                background-color: #002045;
            }
        """)
        
        # Shadow for FAB
        fab_shadow = QGraphicsDropShadowEffect(self._fab)
        fab_shadow.setBlurRadius(15)
        fab_shadow.setColor(QColor(0, 0, 0, 80))
        fab_shadow.setOffset(0, 5)
        self._fab.setGraphicsEffect(fab_shadow)
        
        self._fab.clicked.connect(self._on_fab_clicked)

        # Wire exam selection change
        self._exam_list.currentItemChanged.connect(self._on_exam_changed)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Reposition the FAB at the bottom right corner dynamically
        fab_size = 56
        margin = 32
        self._fab.setGeometry(
            self.width() - fab_size - margin,
            self.height() - fab_size - margin,
            fab_size,
            fab_size,
        )

    def set_exam_rows(self, rows: list[dict]):
        current_exam_id = self._selected_exam_id
        self._exam_list.clear()
        
        if not rows:
            self._selected_exam_id = ""
            self._selected_exam = {}
            self.exam_title_lbl.setText("Select an Exam")
            self.session_id_lbl.setText("Session ID: --")
            self.status_pill.hide()
            self._pending_scroll.clear()
            self._approved_scroll.clear()
            self.approved_subtitle.setText("0 Students in Session")
            return

        for row in rows:
            exam_id = str(row.get("exam_id") or "")
            item = QListWidgetItem()
            item.setSizeHint(QSize(220, 110))
            item.setData(Qt.ItemDataRole.UserRole, row)
            
            is_curr = (exam_id and exam_id == current_exam_id)
            card = ExamCardWidget(row, is_selected=is_curr)
            self._exam_list.addItem(item)
            self._exam_list.setItemWidget(item, card)
            
            if is_curr:
                self._exam_list.setCurrentItem(item)

        if not self._exam_list.currentItem() and self._exam_list.count() > 0:
            self._exam_list.setCurrentRow(0)

    def set_selected_exam(self, exam_row: dict):
        self._selected_exam = exam_row
        self._selected_exam_id = str(exam_row.get("exam_id") or "")
        
        # Update Header Title
        title = str(exam_row.get("title") or "Selected Exam")
        self.exam_title_lbl.setText(title)

        # Update Join Code/Session ID
        code = str(exam_row.get("join_code") or "N/A")
        self.session_id_lbl.setText(f"Session ID: {code}")

        # Update Status Pill
        status = str(exam_row.get("status") or "draft").lower()
        if status == "live":
            self.status_text.setText("Live Monitoring Active")
            self.pulse_dot.setStyleSheet("color: #ffc250; font-size: 14px; font-weight: bold; border: none; background: transparent;")
            self.status_text.setStyleSheet("color: #002045; font-size: 11px; font-weight: 600; border: none; background: transparent;")
            self.status_pill.setStyleSheet("""
                QFrame {
                    background-color: rgba(26, 54, 93, 0.1);
                    border: 1px solid rgba(26, 54, 93, 0.2);
                    border-radius: 12px;
                }
            """)
        elif status == "closed":
            self.status_text.setText("Exam Closed")
            self.pulse_dot.setStyleSheet("color: #ba1a1a; font-size: 14px; font-weight: bold; border: none; background: transparent;")
            self.status_text.setStyleSheet("color: #93000a; font-size: 11px; font-weight: 600; border: none; background: transparent;")
            self.status_pill.setStyleSheet("""
                QFrame {
                    background-color: rgba(186, 26, 26, 0.1);
                    border: 1px solid rgba(186, 26, 26, 0.2);
                    border-radius: 12px;
                }
            """)
        elif status == "scheduled":
            self.status_text.setText("Exam Scheduled")
            self.pulse_dot.setStyleSheet("color: #7d5700; font-size: 14px; font-weight: bold; border: none; background: transparent;")
            self.status_text.setStyleSheet("color: #725000; font-size: 11px; font-weight: 600; border: none; background: transparent;")
            self.status_pill.setStyleSheet("""
                QFrame {
                    background-color: rgba(125, 87, 0, 0.1);
                    border: 1px solid rgba(125, 87, 0, 0.2);
                    border-radius: 12px;
                }
            """)
        else: # draft
            self.status_text.setText("Draft Mode")
            self.pulse_dot.setStyleSheet("color: #74777f; font-size: 14px; font-weight: bold; border: none; background: transparent;")
            self.status_text.setStyleSheet("color: #43474e; font-size: 11px; font-weight: 600; border: none; background: transparent;")
            self.status_pill.setStyleSheet("""
                QFrame {
                    background-color: rgba(116, 119, 127, 0.1);
                    border: 1px solid rgba(116, 119, 127, 0.2);
                    border-radius: 12px;
                }
            """)
        self.status_pill.show()

    def set_requests(self, exam_title: str, rows: list[dict]):
        self._pending_scroll.clear()
        self._approved_scroll.clear()
        
        self._pending_requests = [r for r in rows if not r.get("approved")]
        self._approved_candidates = [r for r in rows if r.get("approved")]

        # Update Approved subtitle
        self.approved_subtitle.setText(f"{len(self._approved_candidates)} Students in Session")

        # Populate Pending list
        for r in self._pending_requests:
            row_widget = PendingRequestRow(r)
            row_widget.approve_clicked.connect(self._on_approve_requested)
            row_widget.deny_clicked.connect(self._on_reject_requested)
            self._pending_scroll.add_row(row_widget)

        # Populate Approved list
        for r in self._approved_candidates:
            row_widget = ApprovedCandidateRow(r)
            row_widget.revoke_clicked.connect(self._on_reject_requested)
            self._approved_scroll.add_row(row_widget)

    def set_status_message(self, message: str):
        self._status.setText(message)

    def set_busy(self, busy: bool) -> None:
        self._exam_list.setEnabled(not busy)
        self._approve_all_btn.setEnabled(not busy)
        self._revoke_all_btn.setEnabled(not busy)
        self._fab.setEnabled(not busy)

    def selected_exam_id(self) -> str:
        return self._selected_exam_id

    @Slot()
    def _on_exam_changed(self):
        item = self._exam_list.currentItem()
        row = item.data(Qt.ItemDataRole.UserRole) if item else None
        
        # Toggle selection styling on cards
        for i in range(self._exam_list.count()):
            itm = self._exam_list.item(i)
            card = self._exam_list.itemWidget(itm)
            if card:
                card.set_selected(itm == item)

        if not isinstance(row, dict) or not row.get("exam_id"):
            self._selected_exam_id = ""
            self._selected_exam = {}
            self.exam_title_lbl.setText("Select an Exam")
            self.session_id_lbl.setText("Session ID: --")
            self.status_pill.hide()
            self._pending_scroll.clear()
            self._approved_scroll.clear()
            self.approved_subtitle.setText("0 Students in Session")
            return

        self._selected_exam_id = str(row["exam_id"])
        self.set_selected_exam(row)
        self.exam_selected.emit(self._selected_exam_id)

    @Slot(str)
    def _on_approve_requested(self, request_id: str):
        if self._selected_exam_id and request_id:
            self.approve_requested.emit(self._selected_exam_id, request_id)

    @Slot(str)
    def _on_reject_requested(self, request_id: str):
        if self._selected_exam_id and request_id:
            self.reject_requested.emit(self._selected_exam_id, request_id)

    @Slot()
    def _on_approve_all_clicked(self):
        if self._selected_exam_id:
            self.approve_all_requested.emit(self._selected_exam_id)

    @Slot()
    def _on_revoke_all_clicked(self):
        if self._selected_exam_id:
            self.revoke_all_requested.emit(self._selected_exam_id)

    @Slot()
    def _on_fab_clicked(self):
        if not self._selected_exam_id:
            self.set_status_message("Please select an exam first.")
            return
        dialog = AddCandidateDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            email = dialog.get_email()
            if email:
                self.add_candidate_requested.emit(self._selected_exam_id, email)

    def _export_csv(self):
        if not self._selected_exam_id or not self._approved_candidates:
            self.set_status_message("No approved candidates to export.")
            return
        
        dialog = QFileDialog(self)
        dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
        dialog.setWindowTitle("Save Approved Candidates List")
        dialog.selectFile(f"approved_candidates_{self._selected_exam_id}.csv")
        dialog.setNameFilter("CSV Files (*.csv)")
        dialog.setDefaultSuffix("csv")
        dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)
        
        # Apply strict styling to prevent white-on-white text
        dialog.setStyleSheet("""
            QFileDialog {
                background-color: #ffffff;
                color: #181c1e;
            }
            QLabel {
                color: #181c1e;
                font-size: 12px;
            }
            QLineEdit {
                background-color: #ffffff;
                color: #181c1e;
                border: 1px solid #c4c6cf;
                border-radius: 4px;
                padding: 4px;
                font-size: 12px;
            }
            QPushButton {
                background-color: #002045;
                color: #ffffff;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #1a365d;
            }
            QTreeView, QListView, QTreeView::item, QListView::item {
                background-color: #ffffff;
                color: #181c1e;
            }
            QTreeView::item:selected, QListView::item:selected {
                background-color: #d6e3ff;
                color: #001b3c;
            }
            QHeaderView::section {
                background-color: #ebeef0;
                color: #181c1e;
                border: 1px solid #c4c6cf;
                padding: 4px;
                font-size: 11px;
            }
            QComboBox {
                background-color: #ffffff;
                color: #181c1e;
                border: 1px solid #c4c6cf;
                border-radius: 4px;
                padding: 4px;
                font-size: 12px;
            }
            QScrollBar:vertical {
                background: #f1f4f6;
                width: 8px;
            }
            QScrollBar::handle:vertical {
                background: #c4c6cf;
                border-radius: 4px;
            }
        """)

        filename = ""
        if dialog.exec() == QFileDialog.DialogCode.Accepted:
            selected = dialog.selectedFiles()
            if selected:
                filename = selected[0]

        if filename:
            try:
                with open(filename, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(["Student Name", "Student Email", "Student ID", "Status"])
                    for r in self._approved_candidates:
                        writer.writerow([
                            r.get("student_name", "Unknown"),
                            r.get("student_email", ""),
                            r.get("student_id", ""),
                            "Approved"
                        ])
                self.set_status_message(f"List successfully saved to {filename}")
            except Exception as e:
                self.set_status_message(f"Error exporting CSV: {str(e)}")
