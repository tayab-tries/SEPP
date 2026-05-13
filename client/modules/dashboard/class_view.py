from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFrame,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
)


class ClassView(QWidget):
    join_exam_requested = Signal()

    def __init__(self, apply_shadow, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._apply_shadow = apply_shadow
        self.class_subject_value = QLabel("--")
        self.class_instructor_value = QLabel("--")
        self.class_code_value = QLabel("--")
        self.class_desc_value = QLabel("--")
        self.upcoming_exams_list = QListWidget()
        self.join_exam_btn = QPushButton("Join Selected Exam")
        self.attempted_exams_list = QListWidget()
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        details_card = QFrame()
        details_card.setObjectName("mainCard")
        self._apply_shadow(details_card)
        details_col = QVBoxLayout(details_card)
        details_col.setContentsMargins(18, 18, 18, 18)
        heading = QLabel("Class Details")
        heading.setObjectName("sectionHeading")
        details_col.addWidget(heading)
        self.class_subject_value.setObjectName("subtitleLabel")
        self.class_instructor_value.setObjectName("subtitleLabel")
        self.class_code_value.setObjectName("subtitleLabel")
        self.class_desc_value.setObjectName("subtitleLabel")
        self.class_desc_value.setWordWrap(True)
        details_col.addWidget(self.class_subject_value)
        details_col.addWidget(self.class_instructor_value)
        details_col.addWidget(self.class_code_value)
        details_col.addWidget(self.class_desc_value)
        layout.addWidget(details_card)

        exams_row = QHBoxLayout()
        exams_row.setSpacing(12)

        upcoming_card = QFrame()
        upcoming_card.setObjectName("mainCard")
        self._apply_shadow(upcoming_card)
        upcoming_col = QVBoxLayout(upcoming_card)
        upcoming_col.setContentsMargins(18, 18, 18, 18)
        up_head = QLabel("Upcoming Exams")
        up_head.setObjectName("sectionHeading")
        self.upcoming_exams_list.setObjectName("examsList")
        self.join_exam_btn.setObjectName("primaryBtn")
        self.join_exam_btn.setEnabled(False)
        self.join_exam_btn.clicked.connect(self.join_exam_requested.emit)
        upcoming_col.addWidget(up_head)
        upcoming_col.addWidget(self.upcoming_exams_list, 1)
        upcoming_col.addWidget(self.join_exam_btn)
        exams_row.addWidget(upcoming_card, 1)

        attempted_card = QFrame()
        attempted_card.setObjectName("mainCard")
        self._apply_shadow(attempted_card)
        attempted_col = QVBoxLayout(attempted_card)
        attempted_col.setContentsMargins(18, 18, 18, 18)
        at_head = QLabel("Attempted Exams")
        at_head.setObjectName("sectionHeading")
        self.attempted_exams_list.setObjectName("analysisList")
        attempted_col.addWidget(at_head)
        attempted_col.addWidget(self.attempted_exams_list, 1)
        exams_row.addWidget(attempted_card, 1)

        layout.addLayout(exams_row, 1)

    def selected_upcoming_exam(self) -> Optional[QListWidgetItem]:
        return self.upcoming_exams_list.currentItem()
