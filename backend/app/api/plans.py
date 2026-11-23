from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List, Optional
from ..database import get_db
from ..auth import get_current_user, check_athlete_access
from ..models.user import User
from ..models.plan import Plan
from ..schemas.plan import PlanCreate, PlanResponse, PlanArchive, PlanWeeklyStats

from ..services import plans as plan_service

router = APIRouter(prefix="/plans", tags=["plans"])

@router.get("/current", response_model=Optional[PlanResponse])
def get_current_plan(athlete_id: Optional[int] = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    target_athlete_id = athlete_id or current_user.id
    check_athlete_access(current_user, target_athlete_id, db)
    
    return db.query(Plan).filter(Plan.athlete_id == target_athlete_id, Plan.is_archived == False).first()

@router.get("/history", response_model=List[PlanResponse])
def get_plan_history(athlete_id: Optional[int] = None, skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=500), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    target_athlete_id = athlete_id if athlete_id is not None else current_user.id
    check_athlete_access(current_user, target_athlete_id, db)
    return (db.query(Plan).filter(Plan.athlete_id == target_athlete_id, Plan.is_archived == True)
            .order_by(Plan.race_date.desc(), Plan.id.desc()).offset(skip).limit(limit).all())

@router.get("/{plan_id}/weekly-stats", response_model=List[PlanWeeklyStats])
def get_plan_weekly_stats(plan_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    db_plan = db.query(Plan).filter(Plan.id == plan_id).first()
    if not db_plan:
        raise HTTPException(status_code=404, detail="Plan non trouvé")
    check_athlete_access(current_user, db_plan.athlete_id, db)

    return plan_service.weekly_stats(db, db_plan)

@router.get("/{plan_id}", response_model=PlanResponse)
def get_plan(plan_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    db_plan = db.query(Plan).filter(Plan.id == plan_id).first()
    if not db_plan:
        raise HTTPException(status_code=404, detail="Plan non trouvé")
    
    check_athlete_access(current_user, db_plan.athlete_id, db)
    return db_plan


@router.post("", response_model=PlanResponse)
def create_plan(plan_in: PlanCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role == "coach" and plan_in.athlete_id is None:
        raise HTTPException(status_code=422, detail="Le coach doit sélectionner le destinataire du plan.")
    target_athlete_id = plan_in.athlete_id or current_user.id
    check_athlete_access(current_user, target_athlete_id, db)
    
    return plan_service.create_plan(db, plan_in, target_athlete_id)

@router.post("/{plan_id}/archive", response_model=PlanResponse)
def archive_plan(plan_id: int, archive_data: PlanArchive, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    db_plan = db.query(Plan).filter(Plan.id == plan_id).first()
    if not db_plan:
        raise HTTPException(status_code=404, detail="Plan non trouvé")
    
    check_athlete_access(current_user, db_plan.athlete_id, db)
    
    return plan_service.archive_plan(db, db_plan, archive_data.cancellation_comment)

@router.delete("/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_plan(plan_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    db_plan = db.query(Plan).filter(Plan.id == plan_id).first()
    if not db_plan:
        raise HTTPException(status_code=404, detail="Plan non trouvé")
    
    check_athlete_access(current_user, db_plan.athlete_id, db)
    
    plan_service.delete_plan(db, db_plan)
    return None
