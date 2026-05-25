"""
client/exam/services/api_worker.py
Generic background worker — runs one blocking callable on a QThread.
"""

from PySide6.QtCore import QThread, Signal


class ApiWorker(QThread):
    """
    Runs fn(*args, **kwargs) on a background thread and emits the
    result back on the main thread via Qt signals.

    IMPORTANT:
    Always store workers somewhere while running.
    If a QThread is only stored in a local variable, Python GC can kill it.
    """

    finished = Signal(object)
    errored = Signal(str)

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs

    def run(self):
        try:
            self.finished.emit(self._fn(*self._args, **self._kwargs))
        except Exception as exc:
            self.errored.emit(str(exc))