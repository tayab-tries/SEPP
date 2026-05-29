"""Shared visual constants for the student exam screen."""

APP_BG = "#F4F8FC"

TOPBAR_BG = "#F8FAFC"
TOPBAR_BORDER = "#DDE5EF"
TOPBAR_TIMER_BG = "#EEF2F7"
TOPBAR_TIMER_BORDER = "#DDE3EC"

CARD_BG = "#FFFFFF"
CARD_BORDER = "#D6DEE9"

TEXT_PRIMARY = "#081B3A"
TEXT_SECONDARY = "#4B5F7A"
TEXT_MUTED = "#8A98AA"

ACCENT = "#0B2D5C"
ACCENT_DARK = "#061E40"

DANGER = "#0B2D5C"
DANGER_DARK = "#061E40"

SUCCESS = "#16A34A"
WARNING = "#F3B23F"

OPTION_BG = "#F8FAFC"
OPTION_SELECTED_BG = "#EAF1FA"
OPTION_SELECTED_BORDER = "#0B2D5C"

FONT_FAMILY = "Inter, Segoe UI, Arial"

FONT_FAMILY = "Inter, Segoe UI, Arial"


def global_stylesheet() -> str:
    return f"""
        QWidget {{
            font-family: {FONT_FAMILY};
            color: {TEXT_PRIMARY};
            background: transparent;
        }}
        QScrollArea {{
            border: none;
            background: transparent;
        }}
        QScrollBar:vertical {{
            background: transparent;
            width: 9px;
            margin: 2px;
        }}
        QScrollBar::handle:vertical {{
            background: #BFC8D4;
            border-radius: 4px;
            min-height: 34px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: #A7B3C2;
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
            border: none;
            background: transparent;
        }}
        QScrollBar:horizontal {{
            background: transparent;
            height: 9px;
            margin: 2px;
        }}
        QScrollBar::handle:horizontal {{
            background: #c8d2df;
            border-radius: 4px;
            min-width: 34px;
        }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
            width: 0px;
            border: none;
            background: transparent;
        }}
    """


PRIMARY_BUTTON = f"""
    QPushButton {{
        background: {ACCENT};
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0 18px;
        font-size: 13px;
        font-weight: 700;
    }}
    QPushButton:hover {{ background: {ACCENT_DARK}; }}
    QPushButton:disabled {{
        background: #B8CCE5;
        color: rgba(255,255,255,0.85);
    }}
"""

SECONDARY_BUTTON = f"""
    QPushButton {{
        background: transparent;
        color: {TEXT_PRIMARY};
        border: none;
        border-radius: 8px;
        padding: 0 18px;
        font-size: 13px;
        font-weight: 700;
    }}
    QPushButton:hover {{ background: #EAF0F7; }}
    QPushButton:disabled {{
        background: transparent;
        color: {TEXT_MUTED};
        border: none;
    }}
"""

DANGER_BUTTON = f"""
    QPushButton {{
        background: {ACCENT};
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0 18px;
        font-size: 13px;
        font-weight: 700;
    }}
    QPushButton:hover {{ background: {ACCENT_DARK}; }}
    QPushButton:disabled {{
        background: #B8CCE5;
        color: rgba(255,255,255,0.85);
    }}
"""