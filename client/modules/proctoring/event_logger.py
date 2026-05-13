"""
client/modules/proctoring/event_logger.py
Module 4c — Event Logger

Sits between the monitors and the heartbeat/sync layer:
  - Receives events from CameraMonitor and ActivityMonitor
  - Writes them to local cache immediately
  - Routes based on severity:
      CRITICAL/HIGH → flush to server immediately
      MEDIUM/LOW/INFO → batch flush every 30 seconds

Optimizations implemented:
  - Severity-based flushing (optimization 6)
  - Keystroke cadence analysis for paste detection
"""

import uuid
import threading
import time
import logging
from datetime import datetime
from typing import Callable, Optional

from shared.constants import EventType, EventSeverity, EVENT_SEVERITY_MAP
from client.core.local_cache import LocalCache

logger = logging.getLogger(__name__)

# Severities that get flushed to server immediately
IMMEDIATE_SEVERITIES = {EventSeverity.CRITICAL, EventSeverity.HIGH}

# Seconds between batch flushes for LOW/MEDIUM/INFO events
BATCH_FLUSH_INTERVAL = 30

# Keystroke analysis
KEYSTROKE_BUFFER_SIZE   = 20    # Analyze every N keystrokes
RAPID_INPUT_THRESHOLD_MS = 20   # Below this median interval → flag as rapid input


# ── Event dataclass ────────────────────────────────────────────────────────
# Defined here so both camera_monitor and activity_monitor can import it
# without circular dependency issues

from dataclasses import dataclass, field

@dataclass
class ProctoringEvent:
    event_type:    EventType
    severity:      EventSeverity
    timestamp:     datetime
    metadata:      dict = field(default_factory=dict)
    snapshot_path: Optional[str] = None


class EventLogger:
    """
    Thread-safe event aggregation and severity-based batching.

    send_batch: callable that takes a list of event dicts and sends over WS.
                This is HeartbeatManager.send_event_batch in normal operation.
    """

    def __init__(
        self,
        session_id: str,
        cache: LocalCache,
        send_batch: Callable[[list], None],
    ):
        self.session_id = session_id
        self.cache      = cache
        self.send_batch = send_batch

        self._lock    = threading.Lock()
        self._running = False
        self._flush_thread: Optional[threading.Thread] = None

        # Keystroke cadence tracking
        self._last_keystroke_time: Optional[datetime] = None
        self._keystrokes_buffer: list[float] = []

    # ── Lifecycle ──────────────────────────────────────────────────────────

    def start(self):
        self._running = True
        self._flush_thread = threading.Thread(
            target=self._flush_loop,
            daemon=True,
            name="EventLoggerFlushThread",
        )
        self._flush_thread.start()
        logger.info("EventLogger started")

    def stop(self):
        """Stop the flush loop and do a final flush before shutdown."""
        self._running = False
        self._flush_batch()  # Final flush
        logger.info("EventLogger stopped")

    # ── Public logging API ─────────────────────────────────────────────────

    def log(self, event: ProctoringEvent):
        """
        Accept an event from any monitor and persist it locally.
        Thread-safe — can be called from any thread.

        Optimization 6 — severity-based flushing:
        CRITICAL and HIGH events are sent to the server immediately.
        Everything else waits for the 30-second batch window.
        """
        event_id = str(uuid.uuid4())

        # Write to local cache immediately regardless of severity
        self.cache.queue_event(
            session_id=self.session_id,
            event_id=event_id,
            event_type=event.event_type.value,
            severity=event.severity.value,
            timestamp=event.timestamp,
            metadata=event.metadata,
            snapshot_path=event.snapshot_path,
        )

        logger.debug(
            f"Event logged: {event.event_type.value} "
            f"[{event.severity.value}] at {event.timestamp.isoformat()}"
        )

        # Immediate flush for CRITICAL and HIGH severity
        if event.severity in IMMEDIATE_SEVERITIES:
            logger.info(
                f"Immediate flush triggered by {event.severity.value} event: "
                f"{event.event_type.value}"
            )
            self._flush_batch()

    def log_keystroke(self, question_id: str):
        """
        Track typing cadence for essay answers.
        Called on every keypress in the essay box.
        Analyzes inter-key intervals to detect suspiciously fast input.
        """
        now = datetime.utcnow()

        if self._last_keystroke_time is not None:
            interval_ms = (now - self._last_keystroke_time).total_seconds() * 1000
            self._keystrokes_buffer.append(interval_ms)

            if len(self._keystrokes_buffer) >= KEYSTROKE_BUFFER_SIZE:
                self._analyze_keystroke_cadence(question_id)
                self._keystrokes_buffer.clear()

        self._last_keystroke_time = now

    def log_paste_attempt(self, question_id: str, text_length: int):
        """
        Called when a paste is detected or intercepted in the essay box.
        Large pastes (>50 chars) are HIGH severity.
        Small pastes (autocomplete, single words) are LOW severity.
        """
        severity = EventSeverity.HIGH if text_length > 50 else EventSeverity.LOW
        self.log(ProctoringEvent(
            event_type=EventType.PASTE_ATTEMPT,
            severity=severity,
            timestamp=datetime.utcnow(),
            metadata={
                "question_id": question_id,
                "pasted_length": text_length,
            },
        ))

    # ── Keystroke analysis ─────────────────────────────────────────────────

    def _analyze_keystroke_cadence(self, question_id: str):
        """
        Flag suspiciously fast typing that suggests a paste bypassed the block.

        Normal human typing: 80-200ms between keystrokes
        Programmatic input / paste bypass: < 20ms between keystrokes

        Uses median (not mean) to avoid false positives from occasional
        fast consecutive keypresses during normal typing.
        """
        if not self._keystrokes_buffer:
            return

        sorted_intervals = sorted(self._keystrokes_buffer)
        median_interval  = sorted_intervals[len(sorted_intervals) // 2]

        if median_interval < RAPID_INPUT_THRESHOLD_MS:
            self.log(ProctoringEvent(
                event_type=EventType.RAPID_TEXT_INPUT,
                severity=EventSeverity.HIGH,
                timestamp=datetime.utcnow(),
                metadata={
                    "question_id":       question_id,
                    "median_interval_ms": round(median_interval, 1),
                    "min_interval_ms":    round(sorted_intervals[0], 1),
                    "sample_size":        len(self._keystrokes_buffer),
                },
            ))

    # ── Flush logic ────────────────────────────────────────────────────────

    def _flush_loop(self):
        """Background thread — flush batched events every BATCH_FLUSH_INTERVAL seconds."""
        while self._running:
            time.sleep(BATCH_FLUSH_INTERVAL)
            self._flush_batch()

    def _flush_batch(self):
        """
        Send all unsynced events to server via WebSocket.
        Safe to call from any thread — uses local cache lock internally.
        Events remain in cache and retry on next cycle if send fails.
        """
        try:
            unsynced = self.cache.get_unsynced_events(self.session_id)
        except Exception:
            return 

        if not unsynced:
            return

        try:
            self.send_batch(unsynced)
            event_ids = [e["id"] for e in unsynced]
            self.cache.mark_events_synced(event_ids)
            logger.debug(f"Flushed {len(unsynced)} events to server")
        except Exception as e:
            # Events stay in local cache — will retry next flush cycle
            logger.warning(f"Event flush failed: {e} — will retry")
