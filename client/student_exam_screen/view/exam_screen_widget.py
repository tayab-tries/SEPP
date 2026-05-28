from __future__ import annotations

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from .main_screen import MainScreenWidget
from .sidebar import SidebarWidget
from .styles import APP_BG, global_stylesheet
from .top_bar import TopBarWidget


class StudentExamScreenWidget(QWidget):
    """
    Modular view-only QWidget for the active student exam screen.

    It owns only visual state and emits signals. The actual controller
    should remain in ExamWindow.
    """

    prev_requested = Signal()
    next_requested = Signal()
    submit_requested = Signal()
    answer_changed = Signal(str, object)
    paste_attempted = Signal(str, int)
    keystroke = Signal(str)

    def __init__(
        self,
        questions: list[dict],
        exam: dict | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.exam = dict(exam or {})
        self.questions = [dict(q or {}) for q in questions]
        self.setObjectName("studentExamScreen")
        self.setStyleSheet(global_stylesheet() + f"""
            QWidget#studentExamScreen {{
                background: {APP_BG};
            }}
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.top_bar = TopBarWidget()
        self.top_bar.set_title(str(self.exam.get("title") or "Exam"))
        self.top_bar.submit_requested.connect(self.submit_requested.emit)
        root.addWidget(self.top_bar)

        body = QWidget()
        body_lay = QHBoxLayout(body)
        body_lay.setContentsMargins(22, 22, 22, 22)
        body_lay.setSpacing(18)

        self.main_screen = MainScreenWidget(
            self.questions,
            allow_paste_in_essay=bool(self.exam.get("allow_paste_in_essay", False)),
        )
        self.main_screen.prev_requested.connect(self.prev_requested.emit)
        self.main_screen.next_requested.connect(self.next_requested.emit)
        self.main_screen.answer_changed.connect(self.answer_changed.emit)
        self.main_screen.paste_attempted.connect(self.paste_attempted.emit)
        self.main_screen.keystroke.connect(self.keystroke.emit)
        body_lay.addWidget(self.main_screen, stretch=1)

        self.sidebar = SidebarWidget()
        body_lay.addWidget(self.sidebar, stretch=0, alignment=Qt.AlignmentFlag.AlignRight)
        root.addWidget(body, stretch=1)

        total = max(1, len(self.questions))
        self.update_progress(1, total)
        self.set_navigation_enabled(False, total > 1, True)

    @property
    def question_widgets(self):
        return self.main_screen.question_widgets

    def set_title(self, title: str) -> None:
        self.top_bar.set_title(title)

    def update_timer(self, text: str) -> None:
        self.top_bar.update_timer(text)

    def set_timer_warning(self, enabled: bool) -> None:
        self.top_bar.set_timer_warning(enabled)

    def update_progress(self, current: int, total: int) -> None:
        self.top_bar.update_progress(current, total)

    def set_navigation_enabled(self, prev_enabled: bool, next_enabled: bool, submit_enabled: bool = True) -> None:
        self.main_screen.set_navigation_enabled(prev_enabled, next_enabled)
        self.top_bar.set_submit_enabled(submit_enabled)

    def set_current_question(self, index: int) -> None:
        self.main_screen.set_current_question(index)
        self.update_progress(index + 1, len(self.questions))

    def get_current_answer(self):
        return self.main_screen.get_current_answer()

    def get_answer_by_index(self, index: int):
        return self.main_screen.get_answer_by_index(index)

    def restore_answer(self, question_id: str, value) -> None:
        self.main_screen.restore_answer(question_id, value)

    def set_exam_enabled(self, enabled: bool) -> None:
        self.main_screen.set_questions_enabled(enabled)
        self.set_navigation_enabled(False, False, enabled)

    # ── Camera feed passthroughs ───────────────────────────────────────────

    def set_preview_frame(self, image_bytes: bytes) -> None:
        """Forward a JPEG camera frame to the sidebar live feed."""
        self.sidebar.set_preview_frame(image_bytes)

    def set_camera_status(self, text: str) -> None:
        """Show a status label in the sidebar camera box (no live feed)."""
        self.sidebar.set_camera_status(text)
