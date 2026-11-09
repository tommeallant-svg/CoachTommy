from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
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
    vma: Optional[float] = None
    ftp: Optional[int] = None
    race_name: str = "Aucun"
    duration_weeks: int = 0
    sessions_per_week: int = 0
    progress_weeks: int = 0
    completion_rate: float = 0.0

class AddAthleteRequest(BaseModel):
    email: str

@router.get("/athletes", response_model=List[AthleteSummary])
def get_athletes_summary(db: Session = Depends(get_db), coach: User = Depends(get_current_coach)):
    athletes = db.query(User).filter(User.role == "athlete", User.coach_id == coach.id).all()
    summaries = []
    
    now = datetime.now()
    
    for athlete in athletes:
        plan = db.query(Plan).filter(Plan.athlete_id == athlete.id, Plan.is_archived == False).first()
        summary = AthleteSummary(
            id=athlete.id, 
            email=athlete.email,
            vma=athlete.vma,
            ftp=athlete.ftp
        )
        
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

@router.post("/athletes", response_model=AthleteSummary)
def add_athlete(request: AddAthleteRequest, db: Session = Depends(get_db), coach: User = Depends(get_current_coach)):
    athlete = db.query(User).filter(User.email == request.email, User.role == "athlete").first()
    if not athlete:
        raise HTTPException(status_code=404, detail="Athlète non trouvé")
    
    if athlete.coach_id and athlete.coach_id != coach.id:
        raise HTTPException(status_code=400, detail="Cet athlète a déjà un coach")
    
    athlete.coach_id = coach.id
    db.commit()
    db.refresh(athlete)
    
    # Return summary for the newly added athlete
    summary = AthleteSummary(
        id=athlete.id, 
        email=athlete.email,
        vma=athlete.vma,
        ftp=athlete.ftp
    )
    return summary
