"""
server/services/face_service.py

Face service — wraps facenet-pytorch for embedding extraction and verification.
No TensorFlow dependency. GPU-accelerated if CUDA is available.

Used by:
  - POST /auth/enroll-face  (extract + store embedding)
  - POST /auth/verify-face  (compare live face vs stored embedding)
  - Camera monitor snapshot uploads (server-side re-verification)
"""

import numpy as np
import torch
from PIL import Image
from facenet_pytorch import MTCNN, InceptionResnetV1
from typing import Optional

# ── Device selection ────────────────────────────────────────────────────────
# Automatically uses GPU if available, falls back to CPU silently.
# On your RTX 3050 this will always be cuda.

_device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# ── Model init ──────────────────────────────────────────────────────────────
# Loaded ONCE at module import time and reused across all requests.
# MTCNN  : face detection + alignment + crop → 160x160 tensor
# Resnet : face recognition → 512-dim embedding vector

_mtcnn = MTCNN(
    image_size=160,
    margin=20,
    keep_all=True,       # Return all faces to detect multiples
    post_process=True,    # Normalize pixel values
    device=_device,
)

class MultipleFacesError(Exception):
    pass

_resnet = InceptionResnetV1(pretrained="vggface2").eval().to(_device)

print(f"[face_service] Models loaded on: {_device}")


# ── Public API ───────────────────────────────────────────────────────────────

def extract_embedding(image_path: str) -> Optional[list[float]]:
    """
    Detect a face in the image at image_path and return a 512-dim embedding.
    Returns None if no face is detected or the image cannot be processed.

    Args:
        image_path: Absolute path to a JPEG/PNG image file.

    Returns:
        List of 512 floats, or None on failure.
    """
    try:
        img = Image.open(image_path).convert("RGB")

        # MTCNN detects + crops + aligns the face → (N, 3, 160, 160) tensor with keep_all=True
        face_tensor = _mtcnn(img)

        if face_tensor is None:
            return None  # No face found

        # With keep_all=True, face_tensor has shape (N, 3, 160, 160)
        if face_tensor.dim() == 4 and face_tensor.shape[0] > 1:
            raise MultipleFacesError("Multiple faces detected in the image.")

        if face_tensor.dim() == 4:
            # Extract the single face and ensure it has batch dimension
            face_tensor = face_tensor[0].unsqueeze(0).to(_device)
        else:
            # Fallback just in case
            face_tensor = face_tensor.unsqueeze(0).to(_device)

        with torch.no_grad():
            embedding = _resnet(face_tensor)  # → (1, 512)

        return embedding.squeeze().cpu().tolist()  # 512 Python floats

    except MultipleFacesError:
        raise
    except Exception:
        return None


def verify_embedding(
    image_path: str,
    stored_embedding: list[float],
    threshold: float = 0.80,
) -> dict:
    """
    Compare a live face image against a stored enrollment embedding.

    Uses cosine similarity:
      - 1.0  = identical
      - 0.0  = completely different
      - threshold (default 0.80) = minimum similarity to accept as match

    Threshold guide:
      0.75 = lenient (more false accepts, fewer false rejects)
      0.80 = balanced (recommended)
      0.85 = strict  (fewer false accepts, more false rejects)

    Args:
        image_path:       Path to the live capture image.
        stored_embedding: The 512-dim list stored at enrollment.
        threshold:        Minimum cosine similarity to verify as match.

    Returns:
        {
            "verified":   bool,
            "similarity": float,  # cosine similarity 0.0–1.0
            "distance":   float,  # 1 - similarity
        }
        On detection failure, adds "error" key and verified=False.
    """
    try:
        live_embedding = extract_embedding(image_path)
    except MultipleFacesError:
        return {
            "verified": False,
            "similarity": 0.0,
            "distance": 1.0,
            "error": "Multiple faces detected. Please ensure only you are in the camera frame.",
        }

    if live_embedding is None:
        return {
            "verified": False,
            "similarity": 0.0,
            "distance": 1.0,
            "error": "No face detected in image. Ensure good lighting and a clear front-facing view.",
        }

    a = np.array(live_embedding,    dtype=np.float32)
    b = np.array(stored_embedding,  dtype=np.float32)

    # Cosine similarity: dot(a, b) / (||a|| * ||b||)
    similarity = float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
    distance   = 1.0 - similarity
    verified   = similarity >= threshold

    return {
        "verified":   verified,
        "similarity": round(similarity, 4),
        "distance":   round(distance,   4),
    }
