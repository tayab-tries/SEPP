import sys
from PySide6.QtWidgets import QApplication

from client.review.views.review_screen_widget import ReviewScreenWidget

def main():
    app = QApplication(sys.argv)

    # Mock Data
    questions = [
        {
            "id": "q1",
            "question_type": "mcq",
            "text": "What is the capital of France?",
            "marks": 2.0,
            "options": ["Berlin", "Madrid", "Paris", "Rome"],
            "correct_option": "C",  # Paris
        },
        {
            "id": "q2",
            "question_type": "essay",
            "text": "Explain the significance of the Eiffel Tower.",
            "marks": 5.0,
            "min_words": 10,
            "max_words": 100,
        },
        {
            "id": "q3",
            "question_type": "mcq",
            "text": "Which programming language is known for its readability?",
            "marks": 1.0,
            "options": ["C++", "Assembly", "Python", "Java"],
            "correct_option": "C", # Python
        }
    ]

    answers = [
        {
            "question_id": "q1",
            "selected_option": "A",  # Student answered Berlin (Incorrect)
            "is_correct": False,
            "examiner_score": 0.0,
            "examiner_comment": "Incorrect. The capital of France is Paris, not Berlin."
        },
        {
            "question_id": "q2",
            "answer_text": "The Eiffel Tower is a very tall iron structure in Paris. It was built for the World's Fair.",
            "examiner_score": 4.5,
            "examiner_comment": "Good explanation, but you could have mentioned Gustave Eiffel or the year it was built."
        },
        {
            "question_id": "q3",
            "selected_option": "C", # Student answered Python (Correct)
            "is_correct": True,
            "examiner_score": 1.0,
            "examiner_comment": "" # No comment
        }
    ]

    exam = {
        "title": "History & Computer Science Midterm Review"
    }

    session = {
        "mcq_score": 1.0,
        "essay_score": 4.5,
    }

    # Initialize Widget
    widget = ReviewScreenWidget(
        questions=questions,
        answers=answers,
        exam=exam,
        session=session
    )
    
    # We set a good default window size to preview
    widget.resize(1024, 768)
    widget.setWindowTitle("Review Screen Preview")
    widget.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
