from typing import Optional, List, Dict, Union
from pydantic import BaseModel, field_validator
from datetime import datetime

class PlanBase(BaseModel):
    race_name: str
    race_date: datetime
    race_distance: float
    race_estimated_time: Optional[str] = None
    start_date: datetime
    sessions_per_week: int
    goal_type: str
    training_days: Union[List[int], Dict[int, str]]
    estimated_vma: float

    @field_validator('start_date')
    @classmethod
    def validate_start_date(cls, v: datetime) -> datetime:
        if v.weekday() != 0:
            raise ValueError("Le plan doit impérativement commencer un lundi")
        return v

class PlanCreate(PlanBase):
    athlete_id: Optional[int] = None

class PlanArchive(BaseModel):
    cancellation_comment: str

class PlanResponse(PlanBase):
    id: int
    athlete_id: int
    is_archived: bool
    cancellation_comment: Optional[str] = None

    class Config:
        from_attributes = True
