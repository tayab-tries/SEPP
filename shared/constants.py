"""
Shared constants used across client and server.
Keep this file in sync on both sides — in production, 
package this as a shared module or duplicate it deliberately.
"""

from enum import Enum, IntEnum


# ──────────────────────────────────────────────
# User Roles
# ──────────────────────────────────────────────
class Role(str, Enum):
    EXAMINER = "examiner"
    STUDENT = "student"


# ──────────────────────────────────────────────
# Exam States
# ──────────────────────────────────────────────
class ExamStatus(str, Enum):
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    LIVE = "live"
    CLOSED = "closed"


# ──────────────────────────────────────────────
# Exam Session States (per student)
# ──────────────────────────────────────────────
class SessionStatus(str, Enum):
    PENDING = "pending"           # Enrolled, not yet started
    VERIFYING = "verifying"       # Face verification in progress
    ACTIVE = "active"             # Exam in progress
    LOCKED = "locked"             # Network lost, countdown running
    SUBMITTED = "submitted"       # Completed normally
    TERMINATED = "terminated"     # Force-ended (timeout, violation, examiner action)


# ──────────────────────────────────────────────
# Question Types
# ──────────────────────────────────────────────
class QuestionType(str, Enum):
    MCQ = "mcq"
    ESSAY = "essay"


# ──────────────────────────────────────────────
# Proctoring Event Types
# ──────────────────────────────────────────────
class EventType(str, Enum):
    # Camera events
    FACE_ABSENT = "face_absent"               # No face detected
    MULTIPLE_FACES = "multiple_faces"         # More than one face
    FACE_MISMATCH = "face_mismatch"           # Re-verification failed
    GAZE_AWAY = "gaze_away"                   # Head pose deviation
    LIVENESS_FAIL = "liveness_fail"           # Liveness check failed at entry

    # Window / screen events
    WINDOW_SWITCH = "window_switch"           # App lost focus
    CURSOR_OFF_SCREEN = "cursor_off_screen"   # Cursor moved to secondary monitor
    SCREENSHOT_ATTEMPT = "screenshot_attempt" # PrintScreen or capture API detected
    FULLSCREEN_EXIT = "fullscreen_exit"       # Kiosk mode broken

    # Input events
    PASTE_ATTEMPT = "paste_attempt"           # Paste detected in essay box
    RAPID_TEXT_INPUT = "rapid_text_input"     # Suspiciously fast keystroke cadence

    # Process events
    PROHIBITED_PROCESS = "prohibited_process" # Screen share / remote app detected
    VM_DETECTED = "vm_detected"               # Running inside a virtual machine
    CLIPBOARD_WRITE = "clipboard_write"       # Something written to clipboard

    # Session events
    NETWORK_LOST = "network_lost"             # Heartbeat failed
    NETWORK_RESTORED = "network_restored"     # Connectivity resumed
    SESSION_TERMINATED = "session_terminated" # Session ended abnormally
    EXAM_STARTED = "exam_started"
    EXAM_SUBMITTED = "exam_submitted"


# ──────────────────────────────────────────────
# Event Severity
# ──────────────────────────────────────────────
class EventSeverity(str, Enum):
    INFO = "info"         # Normal operational events
    LOW = "low"           # Minor / possibly innocent
    MEDIUM = "medium"     # Suspicious, worth reviewing
    HIGH = "high"         # Strong indicator of cheating
    CRITICAL = "critical" # Near-certain violation or security breach


# Map each event type to its default severity
EVENT_SEVERITY_MAP: dict[EventType, EventSeverity] = {
    EventType.FACE_ABSENT: EventSeverity.MEDIUM,
    EventType.MULTIPLE_FACES: EventSeverity.HIGH,
    EventType.FACE_MISMATCH: EventSeverity.CRITICAL,
    EventType.GAZE_AWAY: EventSeverity.LOW,
    EventType.LIVENESS_FAIL: EventSeverity.CRITICAL,
    EventType.WINDOW_SWITCH: EventSeverity.MEDIUM,
    EventType.CURSOR_OFF_SCREEN: EventSeverity.MEDIUM,
    EventType.SCREENSHOT_ATTEMPT: EventSeverity.HIGH,
    EventType.FULLSCREEN_EXIT: EventSeverity.HIGH,
    EventType.PASTE_ATTEMPT: EventSeverity.MEDIUM,
    EventType.RAPID_TEXT_INPUT: EventSeverity.HIGH,
    EventType.PROHIBITED_PROCESS: EventSeverity.CRITICAL,
    EventType.VM_DETECTED: EventSeverity.CRITICAL,
    EventType.CLIPBOARD_WRITE: EventSeverity.LOW,
    EventType.NETWORK_LOST: EventSeverity.INFO,
    EventType.NETWORK_RESTORED: EventSeverity.INFO,
    EventType.SESSION_TERMINATED: EventSeverity.INFO,
    EventType.EXAM_STARTED: EventSeverity.INFO,
    EventType.EXAM_SUBMITTED: EventSeverity.INFO,
}


# ──────────────────────────────────────────────
# Timing Constants
# ──────────────────────────────────────────────
HEARTBEAT_INTERVAL_SECONDS = 10
HEARTBEAT_TIMEOUT_SECONDS = 15          # Server marks student disconnected after this
NETWORK_LOCKDOWN_DURATION_SECONDS = 120 # Session terminates after this
ANSWER_SYNC_INTERVAL_SECONDS = 30
ANSWER_LOCAL_SAVE_INTERVAL_SECONDS = 3
FACE_RECHECK_INTERVAL_SECONDS = 300     # Re-verify identity every 5 minutes
FACE_ABSENT_THRESHOLD_SECONDS = 5       # Flag after this many seconds with no face
GAZE_DEVIATION_THRESHOLD_SECONDS = 8   # Flag after looking away this long

# ──────────────────────────────────────────────
# Face Verification
# ──────────────────────────────────────────────
FACE_MATCH_THRESHOLD = 0.6              # Cosine similarity threshold (DeepFace)
FACE_VERIFY_MAX_ATTEMPTS = 2            # Attempts before blocking student entry

# ──────────────────────────────────────────────
# WebSocket Message Types (client <-> server)
# ──────────────────────────────────────────────
class WSMessageType(str, Enum):
    # Server -> Client
    EXAM_START = "exam_start"
    EXAM_PAUSE = "exam_pause"
    EXAM_END = "exam_end"
    TIME_SYNC = "time_sync"
    EXAMINER_TERMINATE = "examiner_terminate"
    CONNECTIVITY_ACK = "connectivity_ack"

    # Client -> Server
    HEARTBEAT = "heartbeat"
    EVENT_BATCH = "event_batch"
    ANSWER_SYNC = "answer_sync"
    SESSION_STATE = "session_state"

    # Examiner dashboard
    STUDENT_FLAG = "student_flag"
    STUDENT_STATUS_UPDATE = "student_status_update"
