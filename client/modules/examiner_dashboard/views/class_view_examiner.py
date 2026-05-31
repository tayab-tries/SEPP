from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QListWidget,
    QListWidgetItem,
)


class ExaminerClassView(QWidget):
    back_requested = Signal()
    create_exam_requested = Signal(dict)
    refresh_exams_requested = Signal()
    refresh_enrollments_requested = Signal()
    enrollment_approve_requested = Signal(str, str)  # class_id, enrollment_id
    enrollment_reject_requested = Signal(str, str)   # class_id, enrollment_id
    exam_monitor_requested = Signal(dict)
    exam_status_change_requested = Signal(str, str)  # exam_id, target status string

    def __init__(self, apply_shadow, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._apply_shadow = apply_shadow
        self._class_payload: dict = {}

        self._class_name = QLabel("--")
        self._class_code = QLabel("--")
        self._class_desc = QLabel("--")
        self._enrollments_list = QListWidget()
        self._refresh_enrollments_btn = QPushButton("Refresh enrollments")
        self._btn_approve = QPushButton("Approve selected student")
        self._btn_reject = QPushButton("Reject selected student")
        self._exams_list = QListWidget()
        self._refresh_exams_btn = QPushButton("Refresh exams")
        self._btn_scheduled = QPushButton("Mark scheduled")
        self._btn_draft = QPushButton("Return to draft")
        self._btn_live = QPushButton("Go live")
        self._btn_close = QPushButton("Close exam")
        self._btn_monitor = QPushButton("Monitor sessions")
        self._status = QLabel("")
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(12)

        top = QHBoxLayout()
        back = QPushButton("Back")
        back.clicked.connect(self.back_requested.emit)
        create_exam = QPushButton("Create New Exam")
        create_exam.clicked.connect(lambda: self.create_exam_requested.emit(self._class_payload))
        top.addWidget(back)
        top.addStretch(1)
        top.addWidget(create_exam)
        root.addLayout(top)

        details_card = QFrame()
        details_card.setObjectName("mainCard")
        self._apply_shadow(details_card)
        details_col = QVBoxLayout(details_card)
        details_col.setContentsMargins(18, 18, 18, 18)

        heading = QLabel("Exam Group Details")
        heading.setObjectName("sectionHeading")
        self._class_name.setObjectName("subtitleLabel")
        self._class_code.setObjectName("subtitleLabel")
        self._class_desc.setObjectName("subtitleLabel")
        self._class_desc.setWordWrap(True)

        details_col.addWidget(heading)
        details_col.addWidget(self._class_name)
        details_col.addWidget(self._class_code)
        details_col.addWidget(self._class_desc)
        root.addWidget(details_card)

        enrollments_card = QFrame()
        enrollments_card.setObjectName("mainCard")
        self._apply_shadow(enrollments_card)
        enrollments_col = QVBoxLayout(enrollments_card)
        enrollments_col.setContentsMargins(18, 18, 18, 18)
        enrollments_head = QLabel("Enrollment Requests")
        enrollments_head.setObjectName("sectionHeading")
        enrollments_col.addWidget(enrollments_head)
        enrollments_col.addWidget(self._refresh_enrollments_btn)
        enrollments_col.addWidget(self._enrollments_list, 1)
        enrollments_row = QHBoxLayout()
        enrollments_row.addWidget(self._btn_approve)
        enrollments_row.addWidget(self._btn_reject)
        enrollments_col.addLayout(enrollments_row)
        root.addWidget(enrollments_card, 1)

        self._refresh_enrollments_btn.clicked.connect(self.refresh_enrollments_requested.emit)
        self._btn_approve.clicked.connect(lambda: self._emit_enrollment_action("approve"))
        self._btn_reject.clicked.connect(lambda: self._emit_enrollment_action("reject"))
        self._enrollments_list.currentItemChanged.connect(self._update_enrollment_buttons)

        exams_card = QFrame()
        exams_card.setObjectName("mainCard")
        self._apply_shadow(exams_card)
        exams_col = QVBoxLayout(exams_card)
        exams_col.setContentsMargins(18, 18, 18, 18)
        exams_head = QLabel("Exams")
        exams_head.setObjectName("sectionHeading")
        self._exams_list.setObjectName("examsList")
        self._refresh_exams_btn.clicked.connect(self.refresh_exams_requested.emit)

        row_btns = QHBoxLayout()
        for b in (
            self._btn_scheduled,
            self._btn_draft,
            self._btn_live,
            self._btn_close,
            self._btn_monitor,
        ):
            row_btns.addWidget(b)

        self._btn_scheduled.clicked.connect(lambda: self._emit_status("scheduled"))
        self._btn_draft.clicked.connect(lambda: self._emit_status("draft"))
        self._btn_live.clicked.connect(lambda: self._emit_status("live"))
        self._btn_close.clicked.connect(lambda: self._emit_status("closed"))
        self._btn_monitor.clicked.connect(self._emit_monitor)

        exams_col.addWidget(exams_head)
        exams_col.addWidget(self._refresh_exams_btn)
        exams_col.addWidget(self._exams_list, 1)
        exams_col.addLayout(row_btns)
        self._status.setWordWrap(True)
        exams_col.addWidget(self._status)
        root.addWidget(exams_card, 1)

        self._exams_list.currentItemChanged.connect(self._update_action_buttons)

    def set_class_payload(self, payload: dict):
        self._class_payload = dict(payload or {})
        self._class_name.setText(f"Group: {self._class_payload.get('name', 'Unknown')}")
        self._class_code.setText(f"Legacy Code: {self._class_payload.get('join_code', 'N/A')}")
        self._class_desc.setText(
            f"Description: {self._class_payload.get('description') or 'No description provided.'}"
        )
        self.set_enrollments([])

    def set_enrollments(self, rows: list[dict]):
        from client.core.contracts import resolve_student_name
        self._enrollments_list.clear()
        if not rows:
            self._enrollments_list.addItem("No enrollment requests yet.")
            self._update_enrollment_buttons()
            return
        for row in rows:
            approved = bool(row.get("approved"))
            status = "Approved" if approved else "Pending"
            student_disp = resolve_student_name(row)
            item = QListWidgetItem(f"{student_disp} | {status}")
            item.setData(Qt.ItemDataRole.UserRole, row)
            self._enrollments_list.addItem(item)
        self._update_enrollment_buttons()

    def set_exams(self, rows: list[dict]):
        self._exams_list.clear()
        for row in rows or []:
            title = row.get("title", "Exam")
            status = row.get("status", "?")
            eid = str(row.get("exam_id", ""))
            id_disp = f"{eid[:8]}…" if len(eid) > 8 else eid
            line = f"{title}  |  {status}  |  {id_disp}"
            item = QListWidgetItem(line)
            item.setData(Qt.ItemDataRole.UserRole, row)
            self._exams_list.addItem(item)
        self._update_action_buttons()

    def selected_exam(self) -> Optional[dict]:
        item = self._exams_list.currentItem()
        if item is None:
            return None
        data = item.data(Qt.ItemDataRole.UserRole)
        return dict(data) if isinstance(data, dict) else None

    @Slot()
    def _emit_monitor(self):
        row = self.selected_exam()
        if not row or not row.get("exam_id"):
            self._status.setText("Select an exam first.")
            return
        self.exam_monitor_requested.emit(row)

    @Slot()
    def _emit_status(self, target: str):
        row = self.selected_exam()
        if not row or not row.get("exam_id"):
            self._status.setText("Select an exam first.")
            return
        self.exam_status_change_requested.emit(str(row["exam_id"]), target)

    @Slot()
    def _emit_enrollment_action(self, action: str):
        class_id = str(self._class_payload.get("class_id") or "")
        item = self._enrollments_list.currentItem()
        row = item.data(Qt.ItemDataRole.UserRole) if item else None
        if not class_id or not isinstance(row, dict) or not row.get("enrollment_id"):
            self._status.setText("Select an enrollment first.")
            return
        enrollment_id = str(row["enrollment_id"])
        if action == "approve":
            self.enrollment_approve_requested.emit(class_id, enrollment_id)
        else:
            self.enrollment_reject_requested.emit(class_id, enrollment_id)

    @Slot()
    def _update_action_buttons(self):
        row = self.selected_exam()
        if not row:
            for b in (
                self._btn_scheduled,
                self._btn_draft,
                self._btn_live,
                self._btn_close,
                self._btn_monitor,
            ):
                b.setEnabled(False)
            return

        status = str(row.get("status", "")).lower().strip()
        self._btn_monitor.setEnabled(bool(row.get("exam_id")))
        self._btn_scheduled.setEnabled(status == "draft")
        self._btn_draft.setEnabled(status == "scheduled")
        self._btn_live.setEnabled(status in {"draft", "scheduled"})
        self._btn_close.setEnabled(status == "live")

    @Slot()
    def _update_enrollment_buttons(self):
        item = self._enrollments_list.currentItem()
        row = item.data(Qt.ItemDataRole.UserRole) if item else None
        if not isinstance(row, dict) or not row.get("enrollment_id"):
            self._btn_approve.setEnabled(False)
            self._btn_reject.setEnabled(False)
            return
        is_pending = not bool(row.get("approved"))
        self._btn_approve.setEnabled(bool(is_pending))
        self._btn_reject.setEnabled(True)
