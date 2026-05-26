from __future__ import annotations

import sys
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout
from PySide6.QtCore import Qt, QTimer

from client.student_exam_screen.view.exam_screen_widget import StudentExamScreenWidget


class StudentExamScreenPreview(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Student Exam Screen Preview")
        self.resize(1366, 768)

        self.current_index = 0
        self.setStyleSheet("background: #F4F8FC;")

        self.questions = [
            {
                "id": "q1",
                "question_id": "q1",
                "order_index": 0,
                "question_type": "mcq",
                "text": "Which of the following best describes a WebSocket connection?",
                "marks": 2,
                "options": [
                    "A temporary HTTP request only",
                    "A persistent two-way communication channel",
                    "A local database table",
                    "A static HTML page",
                    "A one-time file upload method",
                    "A background image renderer",
                ],
                "min_words": None,
                "max_words": None,
            },
            {
                "id": "q2",
                "question_id": "q2",
                "order_index": 1,
                "question_type": "essay",
                "text": (
                    "Explain how a proctored online exam system can combine local caching, "
                    "heartbeat monitoring, and periodic answer syncing to protect students' answers "
                    "during poor network conditions."
                ),
                "marks": 10,
                "options": None,
                "min_words": 80,
                "max_words": 250,
            },
            {
                "id": "q3",
                "question_id": "q3",
                "order_index": 2,
                "question_type": "mcq",
                "text": "Which backend key should be stored when a student selects the second MCQ option?",
                "marks": 1,
                "options": [
                    "A",
                    "B",
                    "C",
                    "D",
                ],
                "min_words": None,
                "max_words": None,
            },
            {
                "id": "q4",
                "question_id": "q4",
                "order_index": 3,
                "question_type": "essay",
                "text": (
                    "Write a longer answer here to test the essay box expansion and internal scrolling. "
                    "The editor should grow while there is space, and once it reaches its maximum height, "
                    "the content inside the answer box should scroll instead of clipping or breaking the layout."
                ),
                "marks": 15,
                "options": None,
                "min_words": 120,
                "max_words": 500,
            },
        ]

        self.exam = {
            "exam_id": "preview-exam",
            "title": "Preview Exam",
            "duration_minutes": 90,
            "allow_paste_in_essay": False,
            "require_liveness_check": False,
        }

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.exam_ui = StudentExamScreenWidget(
            questions=self.questions,
            exam=self.exam,
            parent=self,
        )
        layout.addWidget(self.exam_ui)

        self._wire_signals()
        self._refresh_state()

        # Fake timer countdown display
        self.remaining_seconds = 90 * 60
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick_timer)
        self.timer.start(1000)

    def _wire_signals(self):
        self.exam_ui.prev_requested.connect(self._go_prev)
        self.exam_ui.next_requested.connect(self._go_next)
        self.exam_ui.submit_requested.connect(self._submit_preview)

        self.exam_ui.keystroke.connect(
            lambda question_id: print(f"[keystroke] question_id={question_id}")
        )
        self.exam_ui.paste_attempted.connect(
            lambda question_id, length: print(
                f"[paste blocked] question_id={question_id}, length={length}"
            )
        )

    def _go_prev(self):
        if self.current_index <= 0:
            return

        print(
            f"[save before prev] q={self.questions[self.current_index]['id']} "
            f"answer={self.exam_ui.get_current_answer()!r}"
        )

        self.current_index -= 1
        self._refresh_state()

    def _go_next(self):
        if self.current_index >= len(self.questions) - 1:
            return

        print(
            f"[save before next] q={self.questions[self.current_index]['id']} "
            f"answer={self.exam_ui.get_current_answer()!r}"
        )

        self.current_index += 1
        self._refresh_state()

    def _refresh_state(self):
        self.exam_ui.set_current_question(self.current_index)
        self.exam_ui.update_progress(self.current_index + 1, len(self.questions))
        self.exam_ui.set_navigation_enabled(
            self.current_index > 0,
            self.current_index < len(self.questions) - 1,
            True,
        )

    def _tick_timer(self):
        self.remaining_seconds = max(0, self.remaining_seconds - 1)
        mins, secs = divmod(self.remaining_seconds, 60)
        self.exam_ui.update_timer(f"Time remaining: {mins:02d}:{secs:02d}")

        if self.remaining_seconds <= 300:
            self.exam_ui.set_timer_warning(True)

    def _submit_preview(self):
        print(
            f"[submit clicked] current_answer={self.exam_ui.get_current_answer()!r}"
        )

        # Test finalizing overlay if the widget exposes it
        if hasattr(self.exam_ui, "show_finalizing"):
            self.exam_ui.show_finalizing(
                "Submitting Preview",
                "This is only a UI preview. No backend request is being made.",
            )
            QTimer.singleShot(2500, self.exam_ui.hide_finalizing)

    def keyPressEvent(self, event):
        # F9 = manually test finalizing overlay
        if event.key() == Qt.Key.Key_F9:
            if hasattr(self.exam_ui, "show_finalizing"):
                self.exam_ui.show_finalizing(
                    "Connection Timeout",
                    "Please do not close the app while answers are syncing.",
                )
                QTimer.singleShot(3000, self.exam_ui.hide_finalizing)
            return

        super().keyPressEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = StudentExamScreenPreview()
    window.show()
    sys.exit(app.exec())