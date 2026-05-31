from typing import Callable
from PySide6.QtWidgets import QWidget, QVBoxLayout
from PySide6.QtCore import Qt, Signal
from client.dashboard.views.sidebar import MAIN_BG
from client.modules.assessments.assessments_panel import ExaminerAssessmentsPanel

class ExaminerAssessmentsView(QWidget):
    assessment_exam_selected = Signal(str)

    def __init__(self, apply_shadow: Callable[[QWidget], None], parent: QWidget | None = None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"background: {MAIN_BG};")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 20, 28, 20)
        
        self._panel = ExaminerAssessmentsPanel()
        apply_shadow(self._panel)
        self._panel.assessment_exam_selected.connect(self.assessment_exam_selected)
        
        layout.addWidget(self._panel)

    def set_loading(self):
        self._panel.set_loading()

    def set_exams(self, exams: list[dict]):
        self._panel.set_exams(exams)

    def set_error(self, message: str):
        self._panel.set_error(message)
