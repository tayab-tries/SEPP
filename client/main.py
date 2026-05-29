"""
client/main.py
ExamApp Client — Entry Point

Run from project root:
    cd D:\\Bullshit\\2.0\\SE\\EXAM
    client\\.venv\\Scripts\\activate
    python -m client.main
"""

import sys
import logging
import multiprocessing
from pathlib import Path

if __name__ == "__main__":
    multiprocessing.set_start_method("spawn", force=True)

from PySide6.QtWidgets import QApplication


def setup_logging() -> logging.Logger:
    import os
    debug = os.getenv("DEBUG", "false").lower() == "true"
    level = logging.DEBUG if debug else logging.INFO

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    for noisy in ("urllib3", "requests", "websockets", "mediapipe", "absl"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    return logging.getLogger("ExamApp")


def load_stylesheet(app: QApplication) -> bool:
    qss_path = Path(__file__).parent / "styles" / "exam.qss"
    if not qss_path.exists():
        logging.warning("exam.qss not found — using default style")
        return False
    try:
        app.setStyleSheet(qss_path.read_text(encoding="utf-8"))
        logging.info("Stylesheet loaded")
        return True
    except Exception as e:
        logging.error("Failed to load stylesheet: %s", e)
        return False


def create_app() -> QApplication:
    app = QApplication(sys.argv)
    app.setApplicationName("ExamApp")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("ExamApp")
    app.setStyle("Fusion")
    app.setQuitOnLastWindowClosed(False)
    return app


def main():
    logger = setup_logging()
    logger.info("ExamApp starting")

    app = create_app()
    load_stylesheet(app)

    from client.main_window import MainWindow
    window = MainWindow()
    window.showFullScreen()

    logger.info("Qt event loop started")
    exit_code = app.exec()
    logger.info("ExamApp exiting (code %d)", exit_code)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
