from datetime import datetime
from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QLabel, QFrame
from PySide6.QtCore import Qt

from client.Shared.info_dialog import InfoDialog

# Tokens (matched from info_dialog.py / all_results_list.py)
BORDER_COLOR     = "#DDE0E8"
TEXT_PRIMARY     = "#111827"
TEXT_SECONDARY   = "#6B7280"
ACCENT_GREEN     = "#22c55e"
ACCENT_RED       = "#ef4444"

class ReportCardDialog(InfoDialog):
    """
    Detailed Result Card Popup displaying exam score breakdown.
    Inherits from shared InfoDialog.
    """
    def __init__(self, data: dict, parent=None):
        super().__init__(
            title="Exam Report Card",
            body="",
            parent=parent
        )
        self.data = data
        self.setFixedWidth(420)
        self._build_report_ui()

    def _build_report_ui(self):
        # We append our custom UI directly into self.body_lay provided by InfoDialog
        
        # Exam Info
        info_lay = QVBoxLayout()
        info_lay.setSpacing(4)
        
        exam_title = QLabel(self.data.get("exam_title", "Unknown Exam"))
        exam_title.setStyleSheet(f"color:{TEXT_PRIMARY}; font-size:16px; font-weight:700;")
        exam_title.setWordWrap(True)
        
        class_name = self.data.get("class_name", "Unknown Class")
        
        # Format Date
        date_str = self.data.get("submitted_at") or self.data.get("started_at")
        date_formatted = date_str
        if date_str:
            try:
                dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                date_formatted = dt.strftime("%b %d, %Y • %I:%M %p")
            except ValueError:
                pass
        
        details = QLabel(f"Class: {class_name} | Date: {date_formatted}")
        details.setStyleSheet(f"color:{TEXT_SECONDARY}; font-size:13px;")
        details.setWordWrap(True)
        
        info_lay.addWidget(exam_title)
        info_lay.addWidget(details)
        
        # Divider
        div1 = QFrame()
        div1.setFrameShape(QFrame.Shape.HLine)
        div1.setStyleSheet(f"background: {BORDER_COLOR};")
        div1.setFixedHeight(1)
        
        # Scores Layout
        scores_lay = QVBoxLayout()
        scores_lay.setSpacing(12)
        
        max_marks = self.data.get("max_marks", 0.0)
        total_score = self.data.get("total_score", 0.0)
        
        # Main Score
        score_percentage = (total_score / max_marks * 100) if max_marks > 0 else 0
        color = ACCENT_GREEN if score_percentage >= 50 else ACCENT_RED
        
        main_score_lay = QHBoxLayout()
        main_score_lbl = QLabel("Total Obtained")
        main_score_lbl.setStyleSheet(f"color:{TEXT_PRIMARY}; font-size:15px; font-weight:700;")
        
        main_score_val = QLabel(f"{total_score} / {max_marks}")
        main_score_val.setStyleSheet(f"color:{color}; font-size:22px; font-weight:800;")
        
        main_score_lay.addWidget(main_score_lbl)
        main_score_lay.addStretch()
        main_score_lay.addWidget(main_score_val)
        
        # Breakdown
        mcq_score = self.data.get("mcq_score", 0.0)
        essay_score = self.data.get("essay_score", 0.0)
        
        breakdown_lay = QVBoxLayout()
        breakdown_lay.setSpacing(6)
        
        def make_row(lbl_text, val_text):
            row = QHBoxLayout()
            lbl = QLabel(lbl_text)
            lbl.setStyleSheet(f"color:{TEXT_SECONDARY}; font-size:13px;")
            val = QLabel(val_text)
            val.setStyleSheet(f"color:{TEXT_PRIMARY}; font-size:13px; font-weight:600;")
            row.addWidget(lbl)
            row.addStretch()
            row.addWidget(val)
            return row
            
        breakdown_lay.addLayout(make_row("MCQ Score", str(mcq_score)))
        if self.data.get("is_graded") and essay_score is not None:
            breakdown_lay.addLayout(make_row("Essay Score", str(essay_score)))
        
        # Integrity
        div2 = QFrame()
        div2.setFrameShape(QFrame.Shape.HLine)
        div2.setStyleSheet(f"background: {BORDER_COLOR};")
        div2.setFixedHeight(1)
        
        integrity_score = self.data.get("integrity_score", 100.0)
        integrity_color = ACCENT_GREEN if integrity_score >= 80 else (ACCENT_RED if integrity_score < 50 else "#f59e0b")
        
        integrity_lay = QHBoxLayout()
        int_lbl = QLabel("Trust Score")
        int_lbl.setStyleSheet(f"color:{TEXT_PRIMARY}; font-size:14px; font-weight:600;")
        int_val = QLabel(f"{integrity_score}%")
        int_val.setStyleSheet(f"color:{integrity_color}; font-size:14px; font-weight:700;")
        
        integrity_lay.addWidget(int_lbl)
        integrity_lay.addStretch()
        integrity_lay.addWidget(int_val)
        
        # Assemble into InfoDialog's body layout
        self.body_lay.addLayout(info_lay)
        self.body_lay.addSpacing(4)
        self.body_lay.addWidget(div1)
        self.body_lay.addSpacing(4)
        
        scores_lay.addLayout(main_score_lay)
        scores_lay.addSpacing(4)
        scores_lay.addLayout(breakdown_lay)
        self.body_lay.addLayout(scores_lay)
        
        self.body_lay.addSpacing(4)
        self.body_lay.addWidget(div2)
        self.body_lay.addSpacing(4)
        self.body_lay.addLayout(integrity_lay)
