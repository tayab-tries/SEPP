"""
client/core/api_worker.py
Generic background worker — runs one blocking callable on a QThread.
"""
from PySide6.QtCore import QThread, Signal


class ApiWorker(QThread):
    """
    Runs ``fn(*args, **kwargs)`` on a background thread and emits the
    result back on the main thread via Qt signals.

    IMPORTANT: always store as an instance variable (``self._worker = ApiWorker(...)``).
    Python's GC will silently kill a locally-scoped running QThread.
    """

    finished = Signal(object)   # result of fn(...)
    errored  = Signal(str)      # str(exc) on any exception

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self._fn     = fn
        self._args   = args
        self._kwargs = kwargs

    def run(self):
        try:
            self.finished.emit(self._fn(*self._args, **self._kwargs))
        except Exception as exc:  # noqa: BLE001
            self.errored.emit(str(exc))
