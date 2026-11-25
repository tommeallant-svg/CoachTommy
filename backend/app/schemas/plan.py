from typing import Optional, List, Dict, Union, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator
from datetime import date, datetime

class TrainingDay(BaseModel):
    model_config = ConfigDict(extra='forbid')
    sport: Literal['running', 'cycling', 'swimming', 'strength']
    category: str = 'Endurance'


class PlanBase(BaseModel):
    race_name: str
    race_date: datetime
    race_distance: float
    race_estimated_time: Optional[str] = None
    start_date: datetime
    sessions_per_week: int
    goal_type: str
    training_days: Union[List[int], Dict[int, Union[str, TrainingDay]]]
    estimated_vma: Optional[float] = Field(None, gt=0)

    @field_validator('start_date')
    @classmethod
    def validate_start_date(cls, v: datetime) -> datetime:
        if v.weekday() != 0:
            raise ValueError("Le plan doit impérativement commencer un lundi")
        return v

class PlanCreate(PlanBase):
    athlete_id: Optional[int] = None

class PlanArchive(BaseModel):
    cancellation_comment: Optional[str] = None

class PlanResponse(PlanBase):
    id: int
    athlete_id: int
    is_archived: bool
    cancellation_comment: Optional[str] = None

    class Config:
        from_attributes = True

class PlanWeeklyStats(BaseModel):
    week_start: date
    week_end: date
    workout_count: int = 0
    validated_count: int = 0
    duration_minutes: int = 0
    distance_km: float = 0
    estimated_load: float = 0
