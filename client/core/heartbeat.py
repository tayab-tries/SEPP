"""
client/core/heartbeat.py
Module 8 (cont.) — Heartbeat & Lockdown State Machine

The heartbeat thread runs independently of the UI thread.
It drives the lockdown state machine:

  ACTIVE ──(heartbeat fails)──► LOCKED ──(120s expire)──► TERMINATED
          ◄──(reconnects)──────────────

Optimizations implemented:
  - Heartbeat payload minimization (timestamp only — no full state)
  - Answer sync on change only (hash comparison before sending)
  - First-message WebSocket auth (token never in URL or logs)

Emits PySide6 signals so the UI can react without threading issues.
"""

import asyncio
import hashlib
import json
import threading
import websockets
from datetime import datetime
from typing import Optional

from PySide6.QtCore import QObject, Signal

from shared.constants import (
    SessionStatus,
    WSMessageType,
    HEARTBEAT_INTERVAL_SECONDS,
    NETWORK_LOCKDOWN_DURATION_SECONDS,
)
from client.core.local_cache import LocalCache
from client.config import WS_URL


class HeartbeatManager(QObject):
    """
    Manages the WebSocket connection in a background asyncio thread.
    Emits PySide6 signals to the UI thread — never touches UI directly.

    Auth flow (first-message auth):
      1. Connect to WS endpoint (no token in URL)
      2. Immediately send {"type": "auth", "token": "..."}
      3. Wait for {"type": "auth_ok"} before starting heartbeat loop
      4. On auth failure server closes with 4001 → enter lockdown
    """

    # ── Signals ────────────────────────────────────────────────────────────
    connection_lost      = Signal()       # Enter lockdown UI
    connection_restored  = Signal()       # Exit lockdown UI
    session_terminated   = Signal(str)    # reason string
    examiner_command     = Signal(dict)   # Pause, end exam, time sync
    lockdown_tick        = Signal(int)    # Seconds remaining in lockdown
    answer_sync_requested = Signal()      # Tell exam engine to push answers now

    def __init__(
        self,
        session_id: str,
        exam_id: str,
        token: str,
        cache: LocalCache,
    ):
        super().__init__()
        self.session_id = session_id
        self.exam_id    = exam_id
        self.token      = token
        self.cache      = cache

        self._running         = False
        self._in_lockdown     = False
        self._lockdown_start: Optional[datetime] = None
        self._ws              = None
        self._thread: Optional[threading.Thread] = None
        self._loop:   Optional[asyncio.AbstractEventLoop] = None

        # Answer sync change detection
        # Tracks hash of last successfully synced answer set
        # so we only send when answers have actually changed
        self._last_sync_hash: Optional[str] = None

    # ── Public API ─────────────────────────────────────────────────────────

    def start(self):
        """Start the WebSocket connection in a background daemon thread."""
        self._running = True
        self._thread = threading.Thread(
            target=self._run_loop,
            daemon=True,
            name="HeartbeatThread",
        )
        self._thread.start()

    def stop(self):
        """Signal the heartbeat loop to stop and shut down the event loop."""
        self._running = False
        
        async def _shutdown():
            if self._ws:
                await self._ws.close()
            # Cancel all tasks
            for task in asyncio.all_tasks(self._loop):
                if task is not asyncio.current_task():
                    task.cancel()
                    
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(_shutdown(), self._loop)

        # Wait for the background thread to finish so callers can safely
        # destroy objects the thread references (prevents "QThread:
        # Destroyed while thread is still running" on exam teardown).
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=5)

    def send_event_batch(self, events: list):
        """
        Called from EventLogger to flush a batch of proctoring events.
        Thread-safe — schedules the coroutine on the background event loop.
        """
        if not events or not self._ws or not self._loop:
            return
        payload = json.dumps({
            "type": WSMessageType.EVENT_BATCH,
            "events": events,
        })
        asyncio.run_coroutine_threadsafe(
            self._ws.send(payload), self._loop
        )

    def send_answer_sync(self, answers: list):
        """
        Called from exam engine to sync answers to server.

        Optimization 11 — sync on change only:
        Computes a hash of the answer set and skips sending if identical
        to the last successfully synced set. Avoids redundant network traffic
        when the student hasn't changed any answers since last sync.
        """
        if not self._ws or not self._loop:
            return

        # Hash the answer set to detect changes
        answer_hash = self._hash_answers(answers)
        if answer_hash == self._last_sync_hash:
            return  # No change since last sync — skip

        payload = json.dumps({
            "type": WSMessageType.ANSWER_SYNC,
            "answers": answers,
        })
        asyncio.run_coroutine_threadsafe(
            self._ws.send(payload), self._loop
        )
        self._last_sync_hash = answer_hash

    def send_session_state(self, state: str):
        """
        Emit explicit session state transitions for examiner dashboards.
        """
        if not self._ws or not self._loop:
            return
        payload = json.dumps({
            "type": WSMessageType.SESSION_STATE,
            "state": state,
            "client_time": datetime.utcnow().isoformat(),
        })
        asyncio.run_coroutine_threadsafe(
            self._ws.send(payload), self._loop
        )

    # ── Internal — thread entry point ─────────────────────────────────────

    def _run_loop(self):
        """Entry point for the background thread. Creates and runs event loop."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._main())
        except asyncio.CancelledError:
            pass  # Clean shutdown — stop() cancelled our tasks
        finally:
            self._loop.close()

    # ── Internal — main WebSocket loop ────────────────────────────────────

    async def _main(self):
        ws_uri = f"{WS_URL}/ws/student/{self.session_id}/{self.exam_id}"

        while self._running:
            try:
                async with websockets.connect(
                    ws_uri,
                    ping_interval=None,  # We manage heartbeats manually
                    open_timeout=10,     # Fail fast if server unreachable
                ) as ws:
                    self._ws = ws

                    # ── First-message auth ─────────────────────────────
                    authenticated = await self._authenticate(ws)
                    if not authenticated:
                        # Server rejected auth — terminate session
                        self.session_terminated.emit(
                            "Authentication failed. Please restart the exam client."
                        )
                        self._running = False
                        return

                    # ── Reconnect recovery ─────────────────────────────
                    if self._in_lockdown:
                        await self._handle_reconnect()
                    else:
                        self.send_session_state(SessionStatus.ACTIVE.value)

                    # ── Run heartbeat + listener concurrently ──────────
                    await asyncio.gather(
                        self._heartbeat_loop(ws),
                        self._listen_loop(ws),
                    )

            except asyncio.CancelledError:
                self._ws = None
                return  # Clean shutdown — stop() cancelled our tasks

            except (websockets.ConnectionClosed, OSError, Exception):
                self._ws = None
                if self._running and not self._in_lockdown:
                    await self._enter_lockdown()

                if self._running:
                    # Retry every 5 seconds during lockdown
                    await asyncio.sleep(5)

    async def _authenticate(self, ws) -> bool:
        """
        First-message auth — send token, wait for auth_ok.
        Returns True if authenticated, False if rejected.
        Token never appears in URL or server logs.
        """
        try:
            await ws.send(json.dumps({
                "type": "auth",
                "token": self.token,
            }))

            raw = await asyncio.wait_for(ws.recv(), timeout=10)
            msg = json.loads(raw)

            if msg.get("type") == "auth_ok":
                return True

            return False

        except (asyncio.TimeoutError, Exception):
            return False

    # ── Internal — heartbeat loop ─────────────────────────────────────────

    async def _heartbeat_loop(self, ws):
        """
        Send a heartbeat every HEARTBEAT_INTERVAL_SECONDS.

        Optimization 14 — payload minimization:
        Only sends timestamp. The server only needs to know the client
        is alive and what time the client thinks it is (for clock drift).
        No full session state on every beat.
        """
        while self._running:
            await asyncio.sleep(HEARTBEAT_INTERVAL_SECONDS)
            try:
                # Minimal payload — timestamp only
                await ws.send(json.dumps({
                    "type": WSMessageType.HEARTBEAT,
                    "client_time": datetime.utcnow().isoformat(),
                }))
            except Exception:
                raise  # Let _main catch and enter lockdown

    # ── Internal — message listener ───────────────────────────────────────

    async def _listen_loop(self, ws):
        """Listen for incoming server messages and route them."""
        async for raw in ws:
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            msg_type = msg.get("type")

            if msg_type == WSMessageType.CONNECTIVITY_ACK:
                # Server acknowledged heartbeat
                if self._in_lockdown:
                    await self._handle_reconnect()

            elif msg_type == WSMessageType.EXAMINER_TERMINATE:
                reason = msg.get("reason", "Session terminated by examiner")
                self.session_terminated.emit(reason)
                self._running = False
                return

            elif msg_type == WSMessageType.EXAM_PAUSE:
                self.examiner_command.emit(msg)

            elif msg_type == WSMessageType.EXAM_END:
                self.examiner_command.emit(msg)

            elif msg_type == WSMessageType.TIME_SYNC:
                self.examiner_command.emit(msg)

    # ── Internal — lockdown state machine ────────────────────────────────

    async def _enter_lockdown(self):
        """Transition to LOCKED state. Start countdown ticker."""
        self._in_lockdown    = True
        self._lockdown_start = datetime.utcnow()
        self.cache.record_lockdown_start()
        self.connection_lost.emit()
        self.send_session_state(SessionStatus.LOCKED.value)

        # Start countdown as a concurrent task
        asyncio.create_task(self._lockdown_countdown())

    async def _lockdown_countdown(self):
        """
        Tick every second while in lockdown.
        Terminates session if lockdown exceeds NETWORK_LOCKDOWN_DURATION_SECONDS.
        """
        while self._in_lockdown and self._running:
            # Guard against _lockdown_start being None
            if self._lockdown_start is None:
                break

            elapsed   = (datetime.utcnow() - self._lockdown_start).total_seconds()
            remaining = int(NETWORK_LOCKDOWN_DURATION_SECONDS - elapsed)

            if remaining <= 0:
                self.session_terminated.emit(
                    "Session terminated: network connection lost for "
                    f"{NETWORK_LOCKDOWN_DURATION_SECONDS} seconds."
                )
                self._running = False
                return

            self.lockdown_tick.emit(remaining)
            await asyncio.sleep(1)

    async def _handle_reconnect(self):
        """
        Called when connectivity is restored after a lockdown.
        Clears lockdown state, triggers immediate answer + event flush.
        """
        self._in_lockdown    = False
        self._lockdown_start = None
        self._last_sync_hash = None  # Force full answer sync on reconnect

        self.cache.clear_lockdown()
        self.connection_restored.emit()
        self.send_session_state(SessionStatus.ACTIVE.value)

        # Trigger immediate flush of answers and events
        self.answer_sync_requested.emit()

    # ── Helpers ────────────────────────────────────────────────────────────

    @staticmethod
    def _hash_answers(answers: list) -> str:
        """
        Compute a stable hash of an answer list for change detection.
        Sorts by question_id first so order doesn't matter.
        """
        sorted_answers = sorted(answers, key=lambda a: a.get("question_id", ""))
        content = json.dumps(sorted_answers, sort_keys=True)
        return hashlib.md5(content.encode()).hexdigest()
