from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from ..ai_auth import get_ai_athlete
from ..database import get_db
from ..models.user import User
from ..models.workout import Workout
from ..schemas.workout import WorkoutResponse
from ..services.workouts import create_workout, list_workouts, update_workout


router = APIRouter(prefix="/ai", tags=["ai-workouts"])


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Interval(StrictModel):
    type: Optional[str] = None
    duration: Optional[float] = Field(None, ge=0)
    distance: Optional[float] = Field(None, ge=0)
    pace_min: Optional[str] = None
    pace_max: Optional[str] = None
    power_watt_min: Optional[float] = None
    power_watt_max: Optional[float] = None
    exercise_repetitions: Optional[int] = Field(None, ge=0)
    load_kg: Optional[float] = Field(None, ge=0)
    recovery_seconds: Optional[float] = Field(None, ge=0)


class Block(StrictModel):
    repetitions: int = Field(1, ge=1)
    intervals: list[Interval]


class AIWorkoutCreate(StrictModel):
    sport: str = "running"
    workout_type: str
    category: Optional[str] = None
    name: str
    duration_minutes: int = Field(..., ge=0)
    distance_km: Optional[float] = Field(None, ge=0)
    difficulty_level: int = Field(..., ge=1, le=10)
    description: Optional[str] = None
    scheme: Optional[list[Block]] = None
    date: datetime


class AIWorkoutUpdate(StrictModel):
    sport: Optional[str] = None
    workout_type: Optional[str] = None
    category: Optional[str] = None
    name: Optional[str] = None
    duration_minutes: Optional[int] = Field(None, ge=0)
    distance_km: Optional[float] = Field(None, ge=0)
    difficulty_level: Optional[int] = Field(None, ge=1, le=10)
    description: Optional[str] = None
    scheme: Optional[list[Block]] = None
    date: Optional[datetime] = None


def owned_workout(db, athlete, workout_id):
    workout = db.query(Workout).filter(Workout.id == workout_id, Workout.athlete_id == athlete.id).first()
    if workout is None:
        raise HTTPException(status_code=404, detail="Workout not found")
    return workout


@router.get("/workouts", response_model=list[WorkoutResponse])
def read_workouts(skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=500),
                  include_archived: bool = True, date_from: Optional[datetime] = None,
                  date_to: Optional[datetime] = None, db: Session = Depends(get_db),
                  athlete: User = Depends(get_ai_athlete)):
    return list_workouts(db, athlete.id, skip, limit, include_archived, date_from, date_to)


@router.post("/workouts", response_model=WorkoutResponse, status_code=status.HTTP_201_CREATED)
def add_workout(data: AIWorkoutCreate, db: Session = Depends(get_db), athlete: User = Depends(get_ai_athlete)):
    return create_workout(db, data.model_dump(exclude_unset=True), athlete.id)


@router.get("/workouts/{workout_id}", response_model=WorkoutResponse)
def read_workout(workout_id: int, db: Session = Depends(get_db), athlete: User = Depends(get_ai_athlete)):
    return owned_workout(db, athlete, workout_id)


@router.patch("/workouts/{workout_id}", response_model=WorkoutResponse)
def edit_workout(workout_id: int, data: AIWorkoutUpdate, db: Session = Depends(get_db),
                 athlete: User = Depends(get_ai_athlete)):
    workout = owned_workout(db, athlete, workout_id)
    changes = data.model_dump(exclude_unset=True)
    if any(changes.get(key, True) is None for key in ("sport", "workout_type", "name", "duration_minutes", "difficulty_level", "date")):
        raise HTTPException(status_code=422, detail="Required workout fields cannot be null")
    return update_workout(db, workout, changes)