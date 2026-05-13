"""
Shared dark-first design tokens for student + examiner surfaces.
Keep all screen styles on these values to make later light-theme work
an additive palette pass instead of a structural refactor.
"""

FONT_FAMILY = '"Inter", "Segoe UI", "Arial"'

# Typography scale
FONT_SIZE_HEADER = 24
FONT_WEIGHT_HEADER = 700
FONT_SIZE_SUBHEADER = 14
FONT_WEIGHT_SUBHEADER = 500

# Brand / semantic palette
COLOR_PRIMARY = "#5B8CFF"
COLOR_PRIMARY_HOVER = "#7BA2FF"
COLOR_PRIMARY_DARK = "#3C73F0"
COLOR_PRIMARY_ALT = "#7BA2FF"

# Dark-first surfaces
COLOR_BG_APP = "#0D1117"
COLOR_BG_CARD = "#151B23"
COLOR_BG_SOFT = "#1C2430"
COLOR_BORDER_SOFT = "#2A3442"

# Typography colors
COLOR_TEXT_DARK = "#E6EDF3"
COLOR_TEXT_HEAD = "#F2F6FB"
COLOR_TEXT_MUTED = "#9AA8BC"
COLOR_TEXT_LIGHT = "#7F8EA3"
COLOR_TEXT_SUBTLE = "#73839B"

# Supporting accents
COLOR_BRAND_DARK = "#3C73F0"
COLOR_BRAND_MID = "#5B8CFF"
COLOR_DOT_INACTIVE = "#3D4A5E"
COLOR_SUCCESS = "#1E3A2F"
COLOR_ERROR = "#3C1F25"
COLOR_SUCCESS_BTN = "#2D8A57"
COLOR_SUCCESS_BTN_HOVER = "#35A469"
COLOR_SUCCESS_BTN_PRESSED = "#246D46"

# Input
COLOR_INPUT_BORDER = "#364357"
COLOR_INPUT_FOCUS = "#5B8CFF"

# Monitoring severity colors (contract aligned)
COLOR_SEVERITY_INFO = "#4EA1FF"
COLOR_SEVERITY_LOW = "#22B8A7"
COLOR_SEVERITY_MEDIUM = "#FFB454"
COLOR_SEVERITY_HIGH = "#FF7A45"
COLOR_SEVERITY_CRITICAL = "#FF4D6D"

# Radii
RADIUS_SM = 12
RADIUS_MD = 12
RADIUS_LG = 14
RADIUS_CARD = 14
RADIUS_BUTTON = 10

# Sizing
FORM_WIDTH = 380


def severity_color(severity: str) -> str:
    normalized = str(severity or "").lower()
    if normalized == "low":
        return COLOR_SEVERITY_LOW
    if normalized == "medium":
        return COLOR_SEVERITY_MEDIUM
    if normalized == "high":
        return COLOR_SEVERITY_HIGH
    if normalized == "critical":
        return COLOR_SEVERITY_CRITICAL
    return COLOR_SEVERITY_INFO
