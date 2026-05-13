"""
server/dependencies.py

Shared FastAPI dependencies — import these into any route that needs auth.

Usage:
    from server.dependencies import get_current_user, require_examiner, require_student

    @router.get("/some-route")
    def my_route(current_user: User = Depends(get_current_user)):
        ...
"""

from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from jose import jwt, JWTError

from server.database import get_db
from server.config import get_settings
from server.models.models import User
from shared.constants import Role

settings = get_settings()

# Points to the login endpoint — used by Swagger UI Authorize button
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


# ── Core dependency ─────────────────────────────────────────────────────────

def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    Decodes the Bearer JWT from the Authorization header.
    Loads and returns the User from DB.
    Raises 401 if token is missing, invalid, expired, or user is inactive.
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        user_id: str | None = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token payload")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user = db.query(User).filter(User.id == user_id).first()
    if not user or user.is_active is False:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    return user


# ── Role-gated dependencies ─────────────────────────────────────────────────

def require_examiner(current_user: User = Depends(get_current_user)) -> User:
    """
    Use on examiner-only routes.
    Raises 403 if the authenticated user is not an examiner.
    """
    if current_user.role != Role.EXAMINER:
        raise HTTPException(status_code=403, detail="Examiner access required")
    return current_user


def require_student(current_user: User = Depends(get_current_user)) -> User:
    """
    Use on student-only routes.
    Raises 403 if the authenticated user is not a student.
    """
    if current_user.role != Role.STUDENT:
        raise HTTPException(status_code=403, detail="Student access required")
    return current_user
