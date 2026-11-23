import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from ..ai_auth import hash_ai_key
from ..auth import get_current_user
from ..database import get_db
from ..models.ai_access import AIAccessKey
from ..models.user import User


router = APIRouter(prefix="/ai-access", tags=["ai-access"])


def get_current_athlete(current_user: User = Depends(get_current_user)):
    if current_user.role != "athlete":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Athlete access required")
    return current_user


@router.get("")
def ai_access_status(athlete: User = Depends(get_current_athlete), db: Session = Depends(get_db)):
    return {"active": db.query(AIAccessKey).filter_by(athlete_id=athlete.id).first() is not None}


@router.post("")
def rotate_ai_access(athlete: User = Depends(get_current_athlete), db: Session = Depends(get_db)):
    key = "ct_ai_" + secrets.token_urlsafe(32)
    key_hash = hash_ai_key(key)
    dialect = db.get_bind().dialect.name
    if dialect == "postgresql":
        insert = postgresql_insert
    elif dialect == "sqlite":
        insert = sqlite_insert
    else:
        raise HTTPException(status_code=500, detail="Unsupported database for AI key rotation")
    statement = insert(AIAccessKey).values(athlete_id=athlete.id, key_hash=key_hash)
    statement = statement.on_conflict_do_update(
        index_elements=[AIAccessKey.athlete_id], set_={"key_hash": key_hash}
    )
    db.execute(statement)
    db.commit()
    return {"key": key}


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def revoke_ai_access(athlete: User = Depends(get_current_athlete), db: Session = Depends(get_db)):
    db.query(AIAccessKey).filter_by(athlete_id=athlete.id).delete(synchronize_session=False)
    db.commit()