from typing import Optional, List, Any
from pydantic import BaseModel, Field, field_validator
from datetime import datetime

class WorkoutBase(BaseModel):
    workout_type: str
    category: Optional[str] = None
    name: str
    duration_minutes: int
    distance_km: Optional[float] = None
    difficulty_level: int = Field(..., ge=1, le=10)
    estimated_load: Optional[float] = None
    description: Optional[str] = None
    scheme: Optional[List[Any]] = None
    date: datetime
    plan_id: Optional[int] = None
    athlete_id: Optional[int] = None

    @field_validator('duration_minutes')
    @classmethod
    def validate_duration(cls, v: int, info: Any) -> int:
        workout_type = info.data.get('workout_type')
        if workout_type and workout_type.lower() in ["sortie longue", "libre"] and v % 5 != 0:
            raise ValueError("La durée doit être un multiple de 5 minutes pour les sorties longues et libres")
        return v

class WorkoutCreate(WorkoutBase):
    pass

class WorkoutUpdate(BaseModel):
    workout_type: Optional[str] = None
    category: Optional[str] = None
    name: Optional[str] = None
    duration_minutes: Optional[int] = None
    distance_km: Optional[float] = None
    difficulty_level: Optional[int] = None
    estimated_load: Optional[float] = None
    description: Optional[str] = None
    scheme: Optional[List[Any]] = None
    date: Optional[datetime] = None
    is_validated: Optional[bool] = None
    perceived_difficulty: Optional[int] = Field(None, ge=1, le=10)
    athlete_comment: Optional[str] = None
    plan_id: Optional[int] = None

class WorkoutManualCreate(BaseModel):
    duration_minutes: int
    distance_km: float
    workout_type: str
    perceived_difficulty: int
    athlete_comment: Optional[str] = None
    date: datetime

class WorkoutValidation(BaseModel):
    perceived_difficulty: int = Field(..., ge=1, le=10)
    athlete_comment: Optional[str] = None

class WorkoutResponse(WorkoutBase):
    id: int
    is_validated: bool
    perceived_difficulty: Optional[int] = None
    athlete_comment: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
