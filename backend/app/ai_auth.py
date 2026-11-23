import hashlib

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .database import get_db
from .models.ai_access import AIAccessKey
from .models.user import User


ai_bearer = HTTPBearer(auto_error=False, scheme_name="AIAccessKey")


def hash_ai_key(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def get_ai_athlete(
    credentials: HTTPAuthorizationCredentials = Depends(ai_bearer),
    db: Session = Depends(get_db),
):
    error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid AI access key",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not credentials or not credentials.credentials.startswith("ct_ai_"):
        raise error
    key_hash = hash_ai_key(credentials.credentials)
    athlete = (
        db.query(User)
        .join(AIAccessKey, AIAccessKey.athlete_id == User.id)
        .filter(AIAccessKey.key_hash == key_hash, User.role == "athlete")
        .first()
    )
    if not athlete:
        raise error
    return athlete