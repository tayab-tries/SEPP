from __future__ import annotations

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from .main_screen import MainScreenWidget
from .sidebar import SidebarWidget
from .styles import APP_BG, global_stylesheet
from .top_bar import TopBarWidget


class ReviewScreenWidget(QWidget):
    """
    Modular view-only QWidget for reviewing a graded exam.
    """

    prev_requested = Signal()
    next_requested = Signal()
    close_requested = Signal()
    
    current_index = 0

    def __init__(
        self,
        questions: list[dict],
        answers: list[dict],
        exam: dict | None = None,
        session: dict | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.exam = dict(exam or {})
        self.questions = [dict(q or {}) for q in questions]
        self.answers = [dict(a or {}) for a in answers]
        self.session = dict(session or {})
        
        self.setObjectName("reviewScreen")
        self.setStyleSheet(global_stylesheet() + f"""
            QWidget#reviewScreen {{
                background: {APP_BG};
            }}
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.top_bar = TopBarWidget()
        self.top_bar.set_title(str(self.exam.get("title") or "Exam Review"))
        
        # Display total score if available
        mcq_score = self.session.get("mcq_score") or 0.0
        essay_score = self.session.get("essay_score") or 0.0
        total_score = mcq_score + essay_score
        total_marks = sum(q.get("marks", 1.0) for q in self.questions)
        self.top_bar.set_score(f"Total Score: {total_score} / {total_marks}")
        
        root.addWidget(self.top_bar)

        body = QWidget()
        body_lay = QHBoxLayout(body)
        body_lay.setContentsMargins(22, 22, 22, 22)
        body_lay.setSpacing(18)

        self.main_screen = MainScreenWidget(
            questions=self.questions,
            answers=self.answers,
        )
        self.main_screen.prev_requested.connect(self._on_prev)
        self.main_screen.next_requested.connect(self._on_next)
        
        # Also bubble up for external listeners if needed
        self.main_screen.prev_requested.connect(self.prev_requested.emit)
        self.main_screen.next_requested.connect(self.next_requested.emit)
        body_lay.addWidget(self.main_screen, stretch=1)

        self.sidebar = SidebarWidget()
        body_lay.addWidget(self.sidebar, stretch=0, alignment=Qt.AlignmentFlag.AlignRight)
        root.addWidget(body, stretch=1)

        # Connect top bar toggle button to sidebar
        self.top_bar.toggle_sidebar_requested.connect(self.sidebar.toggle_sidebar)
        self.top_bar.close_requested.connect(self.close_requested.emit)

        total = max(1, len(self.questions))
        self.update_progress(1, total)
        self.set_navigation_enabled(False, total > 1)
        
        # Set initial comment and state
        self.set_current_question(0)
        self._update_nav_state()

    def _on_prev(self):
        if self.current_index > 0:
            self.set_current_question(self.current_index - 1)

    def _on_next(self):
        if self.current_index < len(self.questions) - 1:
            self.set_current_question(self.current_index + 1)

    def _update_nav_state(self):
        has_prev = self.current_index > 0
        has_next = self.current_index < len(self.questions) - 1
        self.set_navigation_enabled(has_prev, has_next)

    @property
    def question_widgets(self):
        return self.main_screen.question_widgets

    def update_progress(self, current: int, total: int) -> None:
        self.top_bar.update_progress(current, total)

    def set_navigation_enabled(self, prev_enabled: bool, next_enabled: bool) -> None:
        self.main_screen.set_navigation_enabled(prev_enabled, next_enabled)

    def set_current_question(self, index: int) -> None:
        self.current_index = index
        self.main_screen.set_current_question(index)
        self.update_progress(index + 1, len(self.questions))
        self._update_nav_state()
        
        # Update sidebar comment based on the current question
        if 0 <= index < len(self.questions):
            q = self.questions[index]
            qid = str(q.get("id") or q.get("question_id") or "")
            ans = self.main_screen.answers_map.get(qid, {})
            comment = ans.get("examiner_comment", "")
            self.sidebar.set_comment(comment)

