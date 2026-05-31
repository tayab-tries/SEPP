from __future__ import annotations

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from .main_screen import MainScreenWidget
from .sidebar import SidebarWidget
from .styles import APP_BG, global_stylesheet
from .top_bar import TopBarWidget


class ExaminerGradingScreenWidget(QWidget):
    """
    Modular view-only QWidget for reviewing a graded exam.
    """

    prev_requested = Signal()
    next_requested = Signal()
    close_requested = Signal()
    submit_grading_requested = Signal(str) # Emits session_id
    batch_sync_requested = Signal(str, list) # Emits session_id, list[question_ids]
    
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
        self.session_id = str(self.session.get("session_id") or self.session.get("id") or "")
        
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
            session_id=self.session_id
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
        self.top_bar.close_requested.connect(self._on_close_requested)
        
        # Connect sidebar save
        self.sidebar.comment_saved.connect(self._on_comment_saved)
        
        # Connect complete grading button
        self.top_bar.complete_grading_button.clicked.connect(lambda: self.submit_grading_requested.emit(self.session_id))

        total = max(1, len(self.questions))
        self.update_progress(1, total)
        self.set_navigation_enabled(False, total > 1)
        
        self.batch_size = max(5, len(self.questions) // 10)
        
        self.main_screen.prev_requested.connect(self._check_batch_sync)
        self.main_screen.next_requested.connect(self._check_batch_sync)
        
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
            
            from client.modules.assessments.examinergradingview.grading_cache import get_session_cache
            cache = get_session_cache(self.session_id)
            draft = cache.get(qid, {})
            comment = draft.get("examiner_comment", ans.get("examiner_comment", ""))
            self.sidebar.set_comment(comment)

    def _on_comment_saved(self, text: str) -> None:
        if 0 <= self.current_index < len(self.questions):
            q = self.questions[self.current_index]
            qid = str(q.get("id") or q.get("question_id") or "")
            
            from client.modules.assessments.examinergradingview.grading_cache import save_answer_draft, get_session_cache
            cache = get_session_cache(self.session_id)
            draft = cache.get(qid, {})
            score = draft.get("examiner_score")
            
            if score is None:
                # If score is not explicitly set, fetch the current spinbox value
                widget = self.main_screen.question_widgets[self.current_index]
                if hasattr(widget, 'score_spinbox'):
                    score = widget.score_spinbox.value()
                else:
                    ans = self.main_screen.answers_map.get(qid, {})
                    score = ans.get("examiner_score", 0.0)
                    
            save_answer_draft(self.session_id, qid, score, text)
            self._check_batch_sync()

    def _check_batch_sync(self):
        from client.modules.assessments.examinergradingview.grading_cache import get_unsynced_drafts
        unsynced = get_unsynced_drafts(self.session_id)
        if len(unsynced) >= self.batch_size:
            self.top_bar.set_sync_status(f"Syncing {len(unsynced)} drafts...")
            self.batch_sync_requested.emit(self.session_id, list(unsynced.keys()))

    def _on_close_requested(self):
        from client.modules.assessments.examinergradingview.grading_cache import get_unsynced_drafts
        unsynced = get_unsynced_drafts(self.session_id)
        if unsynced:
            self.top_bar.set_sync_status("Syncing...")
            self.batch_sync_requested.emit(self.session_id, list(unsynced.keys()))
        self.close_requested.emit()

    def set_sync_status(self, text: str):
        self.top_bar.set_sync_status(text)

