from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from datetime import datetime
from ..database import get_db
from ..auth import get_current_coach
from ..models.user import User
from ..models.plan import Plan
from ..models.workout import Workout
from pydantic import BaseModel

router = APIRouter(prefix="/coach", tags=["coach"])

class AthleteSummary(BaseModel):
    id: int
    email: str
    race_name: str = "Aucun"
    duration_weeks: int = 0
    sessions_per_week: int = 0
    progress_weeks: int = 0
    completion_rate: float = 0.0

@router.get("/athletes", response_model=List[AthleteSummary])
def get_athletes_summary(db: Session = Depends(get_db), coach: User = Depends(get_current_coach)):
    athletes = db.query(User).filter(User.role == "athlete").all()
    summaries = []
    
    now = datetime.now()
    
    for athlete in athletes:
        plan = db.query(Plan).filter(Plan.athlete_id == athlete.id, Plan.is_archived == False).first()
        summary = AthleteSummary(id=athlete.id, email=athlete.email)
        
        if plan:
            summary.race_name = plan.race_name
            total_days = (plan.race_date - plan.start_date).days
            summary.duration_weeks = (total_days // 7) + 1
            summary.sessions_per_week = plan.sessions_per_week
            
            days_passed = (now - plan.start_date).days
            summary.progress_weeks = max(0, (days_passed // 7) + 1)
            
            # Taux de réalisation
            planned_before_now = db.query(Workout).filter(
                Workout.athlete_id == athlete.id,
                Workout.plan_id == plan.id,
                Workout.date <= now
            ).count()
            
            validated_before_now = db.query(Workout).filter(
                Workout.athlete_id == athlete.id,
                Workout.plan_id == plan.id,
                Workout.date <= now,
                Workout.is_validated == True
            ).count()
            
            if planned_before_now > 0:
                summary.completion_rate = (validated_before_now / planned_before_now) * 100
                
        summaries.append(summary)
        
    return summaries
