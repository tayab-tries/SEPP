"""
Client-side configuration.
Values can be overridden via a local .env file.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Server connection
SERVER_HOST = os.getenv("SERVER_HOST", "localhost")
SERVER_PORT = int(os.getenv("SERVER_PORT", "8000"))
BASE_URL = f"http://{SERVER_HOST}:{SERVER_PORT}"
WS_URL = f"ws://{SERVER_HOST}:{SERVER_PORT}"

# Local encrypted cache
APP_DIR = Path.home() / ".examapp"
APP_DIR.mkdir(exist_ok=True)
LOCAL_DB_PATH = str(APP_DIR / "local_cache.db")
LOCAL_DB_KEY = os.getenv("LOCAL_DB_KEY", "CHANGE_THIS_KEY")  # Should be unique per install

# Snapshots saved locally before uploading
SNAPSHOT_DIR = APP_DIR / "snapshots"
SNAPSHOT_DIR.mkdir(exist_ok=True)

# Camera
CAMERA_INDEX = int(os.getenv("CAMERA_INDEX", "0"))
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480

# Entry liveness (blink + head turn) — wall-clock cap in the worker process.
# Typical completion is much faster once gestures are detected; the camera
# device is released as soon as this subprocess exits (pass, fail, or timeout).
LIVENESS_TIMEOUT_SECONDS = max(20, int(os.getenv("LIVENESS_TIMEOUT_SECONDS", "45")))
