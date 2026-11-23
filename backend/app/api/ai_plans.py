from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import ConfigDict
from sqlalchemy.orm import Session

from ..ai_auth import get_ai_athlete
from ..database import get_db
from ..models.plan import Plan
from ..models.user import User
from ..schemas.plan import PlanArchive, PlanBase, PlanResponse, PlanWeeklyStats
from ..services import plans as plan_service


class AIPlanCreate(PlanBase):
    model_config = ConfigDict(extra="forbid")


class AIPlanArchive(PlanArchive):
    model_config = ConfigDict(extra="forbid")


def reject_extra_query(request: Request):
    allowed = {"skip", "limit"} if request.url.path.endswith("/history") else set()
    if set(request.query_params) - allowed:
        raise HTTPException(status_code=422, detail="Paramètre de requête inconnu")


router = APIRouter(prefix="/ai", tags=["ai plans"], dependencies=[Depends(reject_extra_query)])


@router.get("/plans/current", response_model=Optional[PlanResponse])
def current_plan(db: Session = Depends(get_db), athlete: User = Depends(get_ai_athlete)):
    return db.query(Plan).filter(Plan.athlete_id == athlete.id, Plan.is_archived == False).first()


@router.get("/plans/history", response_model=List[PlanResponse])
def history(skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=500), db: Session = Depends(get_db), athlete: User = Depends(get_ai_athlete)):
    return (db.query(Plan).filter(Plan.athlete_id == athlete.id, Plan.is_archived == True)
            .order_by(Plan.race_date.desc(), Plan.id.desc()).offset(skip).limit(limit).all())


@router.get("/plans/{plan_id}", response_model=PlanResponse)
def get_plan(plan_id: int, db: Session = Depends(get_db), athlete: User = Depends(get_ai_athlete)):
    return plan_service.get_owned_plan(db, plan_id, athlete.id)


@router.get("/plans/{plan_id}/weekly-stats", response_model=List[PlanWeeklyStats])
def weekly_stats(plan_id: int, db: Session = Depends(get_db), athlete: User = Depends(get_ai_athlete)):
    return plan_service.weekly_stats(db, plan_service.get_owned_plan(db, plan_id, athlete.id))


@router.post("/plans", response_model=PlanResponse)
def create_plan(plan: AIPlanCreate, db: Session = Depends(get_db), athlete: User = Depends(get_ai_athlete)):
    return plan_service.create_plan(db, plan, athlete.id)


@router.post("/plans/{plan_id}/archive", response_model=PlanResponse)
def archive_plan(plan_id: int, data: AIPlanArchive, db: Session = Depends(get_db), athlete: User = Depends(get_ai_athlete)):
    return plan_service.archive_plan(db, plan_service.get_owned_plan(db, plan_id, athlete.id), data.cancellation_comment)


@router.delete("/plans/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_plan(plan_id: int, db: Session = Depends(get_db), athlete: User = Depends(get_ai_athlete)):
    plan_service.delete_plan(db, plan_service.get_owned_plan(db, plan_id, athlete.id))