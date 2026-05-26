from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class ExaminerAccessRequestsView(QWidget):
    refresh_requested = Signal()
    exam_selected = Signal(str)
    approve_requested = Signal(str, str)
    reject_requested = Signal(str, str)

    def __init__(self, apply_shadow, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._apply_shadow = apply_shadow
        self._selected_exam_id = ""
        self._selected_request_id = ""

        self._summary = QLabel("Select an exam to review its access requests.")
        self._exam_list = QListWidget()
        self._request_list = QListWidget()
        self._refresh_btn = QPushButton("Refresh")
        self._approve_btn = QPushButton("Approve selected request")
        self._reject_btn = QPushButton("Reject selected request")
        self._status = QLabel("")

        self._build()

    def _build(self):
        self.setStyleSheet(
            """
            QListWidget::item {
                padding: 8px 10px;
                margin: 2px 0;
                border-radius: 10px;
            }
            QListWidget::item:selected {
                background-color: #DCE9FF;
                color: #0F2454;
                border: 1px solid #AFC6F8;
            }
            QListWidget::item:hover {
                background-color: #EDF4FF;
            }
            """
        )
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(12)

        self._summary.setObjectName("subtitleLabel")
        self._summary.setWordWrap(True)
        root.addWidget(self._summary)

        row = QHBoxLayout()
        row.setSpacing(12)

        exams_card = QFrame()
        exams_card.setObjectName("mainCard")
        self._apply_shadow(exams_card)
        exams_col = QVBoxLayout(exams_card)
        exams_col.setContentsMargins(18, 18, 18, 18)

        exams_heading = QLabel("Owned Exams")
        exams_heading.setObjectName("sectionHeading")
        exams_subtitle = QLabel("Choose an exam to review pending direct-access requests.")
        exams_subtitle.setObjectName("subtitleLabel")
        exams_subtitle.setWordWrap(True)
        exams_col.addWidget(exams_heading)
        exams_col.addWidget(exams_subtitle)
        exams_col.addWidget(self._exam_list, 1)

        requests_card = QFrame()
        requests_card.setObjectName("mainCard")
        self._apply_shadow(requests_card)
        requests_col = QVBoxLayout(requests_card)
        requests_col.setContentsMargins(18, 18, 18, 18)

        top = QHBoxLayout()
        requests_heading = QLabel("Exam Access Requests")
        requests_heading.setObjectName("sectionHeading")
        top.addWidget(requests_heading)
        top.addStretch(1)
        top.addWidget(self._refresh_btn)
        requests_col.addLayout(top)

        requests_subtitle = QLabel(
            "Approve students who should be allowed to join this exam directly. Approved requests drop out of this queue."
        )
        requests_subtitle.setObjectName("subtitleLabel")
        requests_subtitle.setWordWrap(True)
        requests_col.addWidget(requests_subtitle)
        requests_col.addWidget(self._request_list, 1)

        actions = QHBoxLayout()
        actions.addWidget(self._approve_btn)
        actions.addWidget(self._reject_btn)
        requests_col.addLayout(actions)

        self._status.setObjectName("subtitleLabel")
        self._status.setWordWrap(True)
        requests_col.addWidget(self._status)

        row.addWidget(exams_card, 4)
        row.addWidget(requests_card, 7)
        root.addLayout(row, 1)

        self._refresh_btn.clicked.connect(self.refresh_requested.emit)
        self._exam_list.currentItemChanged.connect(self._on_exam_changed)
        self._request_list.currentItemChanged.connect(self._on_request_changed)
        self._approve_btn.clicked.connect(self._emit_approve)
        self._reject_btn.clicked.connect(self._emit_reject)
        self._update_request_buttons()

    def set_exam_rows(self, rows: list[dict]):
        current_exam_id = self._selected_exam_id
        self._exam_list.clear()
        if not rows:
            self._exam_list.addItem("No exams available yet.")
            self._selected_exam_id = ""
            self._summary.setText("Create an exam first, then review incoming access requests here.")
            self._request_list.clear()
            self._request_list.addItem("Select an exam to view requests.")
            self._update_request_buttons()
            return

        for row in rows:
            exam_id = str(row.get("exam_id") or "")
            title = str(row.get("title") or "Untitled Exam")
            class_name = str(row.get("class_name") or "Unknown group")
            status = str(row.get("status") or "Draft")
            text = f"{title}\n{class_name}  •  {status}"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, row)
            self._exam_list.addItem(item)
            if exam_id and exam_id == current_exam_id:
                self._exam_list.setCurrentItem(item)

        if not self._exam_list.currentItem():
            self._exam_list.setCurrentRow(0)

    def set_requests(self, exam_title: str, rows: list[dict]):
        self._selected_request_id = ""
        self._request_list.clear()
        self._summary.setText(
            f"Reviewing pending direct access requests for {exam_title or 'the selected exam'}."
        )
        pending_rows = [row for row in rows if not bool(row.get("approved"))]
        if not pending_rows:
            self._request_list.addItem("No pending access requests for this exam.")
            self._update_request_buttons()
            return

        for row in pending_rows:
            student_name = str(row.get("student_name") or "Unknown student")
            student_email = str(row.get("student_email") or "No email")
            status = "Approved" if bool(row.get("approved")) else "Awaiting Approval"
            requested_at = str(row.get("requested_at") or "")
            requested_display = requested_at.replace("T", " ")[:16] if requested_at else "Unknown time"
            text = f"{student_name}\n{student_email}  •  {status}  •  {requested_display}"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, row)
            self._request_list.addItem(item)

        self._request_list.setCurrentRow(0)
        self._update_request_buttons()

    def set_status_message(self, message: str):
        self._status.setText(message)

    def set_busy(self, busy: bool) -> None:
        self._refresh_btn.setEnabled(not busy)
        self._exam_list.setEnabled(not busy)
        self._request_list.setEnabled(not busy)
        if busy:
            self._approve_btn.setEnabled(False)
            self._reject_btn.setEnabled(False)
            return
        self._update_request_buttons()

    def selected_exam_id(self) -> str:
        return self._selected_exam_id

    @Slot()
    def _emit_approve(self):
        if self._selected_exam_id and self._selected_request_id:
            self.approve_requested.emit(self._selected_exam_id, self._selected_request_id)

    @Slot()
    def _emit_reject(self):
        if self._selected_exam_id and self._selected_request_id:
            self.reject_requested.emit(self._selected_exam_id, self._selected_request_id)

    @Slot()
    def _on_exam_changed(self):
        item = self._exam_list.currentItem()
        row = item.data(Qt.ItemDataRole.UserRole) if item else None
        if not isinstance(row, dict) or not row.get("exam_id"):
            self._selected_exam_id = ""
            self._request_list.clear()
            self._request_list.addItem("Select a valid exam to view requests.")
            self._update_request_buttons()
            return
        self._selected_exam_id = str(row["exam_id"])
        self._selected_request_id = ""
        self._request_list.clear()
        self._request_list.addItem("Loading access requests…")
        self._update_request_buttons()
        self.exam_selected.emit(self._selected_exam_id)

    @Slot()
    def _on_request_changed(self):
        item = self._request_list.currentItem()
        row = item.data(Qt.ItemDataRole.UserRole) if item else None
        if not isinstance(row, dict) or not row.get("request_id"):
            self._selected_request_id = ""
            self._update_request_buttons()
            return
        self._selected_request_id = str(row["request_id"])
        self._update_request_buttons()

    def _update_request_buttons(self):
        item = self._request_list.currentItem()
        row = item.data(Qt.ItemDataRole.UserRole) if item else None
        if not isinstance(row, dict) or not row.get("request_id"):
            self._approve_btn.setEnabled(False)
            self._reject_btn.setEnabled(False)
            return
        approved = bool(row.get("approved"))
        self._approve_btn.setEnabled(not approved)
        self._reject_btn.setEnabled(True)
