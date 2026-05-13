"""
WebSocket client for examiner live monitoring channel.
"""

import asyncio
import json
import threading
from typing import Optional

import websockets
from PySide6.QtCore import QObject, Signal

from client.config import WS_URL
from shared.constants import WSMessageType


class ExaminerWsClient(QObject):
    connected = Signal()
    disconnected = Signal()
    event_received = Signal(dict)
    error = Signal(str)

    def __init__(self, exam_id: str, token: str):
        super().__init__()
        self.exam_id = exam_id
        self.token = token
        self._running = False
        self._ws = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="ExaminerWsThread")
        self._thread.start()

    def stop(self):
        self._running = False
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)

    def send_control(self, msg_type: str, session_id: str | None = None, reason: str | None = None):
        if not self._ws or not self._loop:
            return
        payload = {"type": msg_type}
        if session_id:
            payload["session_id"] = session_id
        if reason:
            payload["reason"] = reason
        asyncio.run_coroutine_threadsafe(self._ws.send(json.dumps(payload)), self._loop)

    def _run_loop(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._main())
        finally:
            self._loop.close()

    async def _main(self):
        uri = f"{WS_URL}/ws/examiner/{self.exam_id}"
        while self._running:
            try:
                async with websockets.connect(uri, ping_interval=None, open_timeout=10) as ws:
                    self._ws = ws
                    await ws.send(json.dumps({"type": "auth", "token": self.token}))
                    raw = await asyncio.wait_for(ws.recv(), timeout=10)
                    msg = json.loads(raw)
                    if msg.get("type") != "auth_ok":
                        self.error.emit("Examiner WS authentication failed.")
                        self._running = False
                        return
                    self.connected.emit()
                    async for raw_msg in ws:
                        body = json.loads(raw_msg)
                        self.event_received.emit(body)
            except Exception as exc:
                if self._running:
                    self.disconnected.emit()
                    self.error.emit(f"Examiner WS disconnected: {exc}")
                    await asyncio.sleep(3)
            finally:
                self._ws = None

    def pause_exam(self):
        self.send_control(WSMessageType.EXAM_PAUSE)

    def end_exam(self):
        self.send_control(WSMessageType.EXAM_END)

    def terminate_session(self, session_id: str, reason: str = "Terminated by examiner"):
        self.send_control(WSMessageType.EXAMINER_TERMINATE, session_id=session_id, reason=reason)
