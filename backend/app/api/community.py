from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, EmailStr
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models.community import Friendship
from ..models.plan import Plan
from ..models.user import User
from ..models.workout import Workout

router = APIRouter(prefix="/community", tags=["community"])


class Invitation(BaseModel):
    email: EmailStr


class Person(BaseModel):
    id: int
    email: str


class Connection(BaseModel):
    id: int
    person: Person
    direction: str


class SharedWorkout(BaseModel):
    name: Optional[str]
    date: datetime
    sport: Optional[str]
    duration_minutes: Optional[int]
    distance_km: Optional[float]
    description: Optional[str]
    scheme: Optional[list[Any]]


class SharedPlan(BaseModel):
    workouts: list[SharedWorkout]


SCHEME_KEYS = {"repetitions", "intervals", "type", "duration", "distance", "unit", "duration_unit", "distance_unit", "pace", "pace_min", "pace_max", "pace_vma_min", "pace_vma_max", "power", "power_min", "power_max", "power_ftp_min", "power_ftp_max", "rest"}


def safe_scheme(value):
    if isinstance(value, list):
        return [safe_scheme(item) for item in value]
    if isinstance(value, dict):
        return {key: safe_scheme(item) for key, item in value.items() if key in SCHEME_KEYS}
    return value


def pair(a, b):
    return min(a, b), max(a, b)


def connection_data(db, friendship, user_id):
    other_id = friendship.user_high_id if friendship.user_low_id == user_id else friendship.user_low_id
    person = db.get(User, other_id)
    return {"id": friendship.id, "person": {"id": person.id, "email": person.email},
            "direction": "sent" if friendship.requester_id == user_id else "received"}


@router.post("/invitations", response_model=Connection, status_code=201)
def invite(invitation: Invitation, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    targets = db.query(User).filter(func.lower(User.email) == invitation.email.lower()).limit(2).all()
    if not targets:
        raise HTTPException(404, "Compte introuvable")
    if len(targets) > 1:
        raise HTTPException(409, "Adresse ambiguë")
    target = targets[0]
    if target.id == user.id:
        raise HTTPException(400, "Auto-invitation interdite")
    low, high = pair(user.id, target.id)
    friendship = Friendship(user_low_id=low, user_high_id=high, requester_id=user.id)
    db.add(friendship)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Une relation existe déjà")
    db.refresh(friendship)
    return connection_data(db, friendship, user.id)


@router.get("/invitations", response_model=list[Connection])
def invitations(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = db.query(Friendship).filter(Friendship.accepted == False, or_(Friendship.user_low_id == user.id, Friendship.user_high_id == user.id)).order_by(Friendship.id).all()
    return [connection_data(db, row, user.id) for row in rows]


@router.get("/friends", response_model=list[Connection])
def friends(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = db.query(Friendship).filter(Friendship.accepted == True, or_(Friendship.user_low_id == user.id, Friendship.user_high_id == user.id)).order_by(Friendship.id).all()
    return [connection_data(db, row, user.id) for row in rows]


@router.post("/invitations/{connection_id}/accept", response_model=Connection)
def accept(connection_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    updated = db.query(Friendship).filter(Friendship.id == connection_id, Friendship.accepted == False,
        Friendship.requester_id != user.id, or_(Friendship.user_low_id == user.id, Friendship.user_high_id == user.id)).update({Friendship.accepted: True}, synchronize_session=False)
    if not updated:
        raise HTTPException(404, "Invitation reçue introuvable")
    result = connection_data(db, db.get(Friendship, connection_id), user.id)
    db.commit()
    return result


@router.delete("/connections/{connection_id}", status_code=204)
def remove(connection_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    deleted = db.query(Friendship).filter(Friendship.id == connection_id, or_(Friendship.user_low_id == user.id, Friendship.user_high_id == user.id)).delete(synchronize_session=False)
    if not deleted:
        raise HTTPException(404, "Relation introuvable")
    db.commit()
    return Response(status_code=204)


@router.get("/friends/{friend_id}/plan", response_model=Optional[SharedPlan])
def friend_plan(friend_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    low, high = pair(user.id, friend_id)
    relation = db.query(Friendship).filter_by(user_low_id=low, user_high_id=high, accepted=True).first()
    if relation is None:
        raise HTTPException(403, "Amitié acceptée requise")
    plan = db.query(Plan).filter_by(athlete_id=friend_id, is_archived=False).first()
    if plan is None:
        return None
    workouts = db.query(Workout).filter(Workout.plan_id == plan.id, Workout.athlete_id == friend_id, Workout.date.isnot(None)).order_by(Workout.date, Workout.id).all()
    return {"workouts": [{"name": w.name, "date": w.date, "sport": w.sport, "duration_minutes": w.duration_minutes,
        "distance_km": w.distance_km, "description": w.description, "scheme": safe_scheme(w.scheme)} for w in workouts]}