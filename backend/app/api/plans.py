from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List, Optional
from ..database import get_db
from ..auth import get_current_user, check_athlete_access
from ..models.user import User
from ..models.plan import Plan
from ..schemas.plan import PlanCreate, PlanResponse, PlanArchive, PlanWeeklyStats

from ..models.catalog import CatalogWorkout
from ..services.plan_generator import PlanGenerator
from ..services.workout_volumes import calculate_volumes
from ..models.workout import Workout

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

    start = db_plan.start_date.date()
    end = db_plan.race_date.date()
    workouts = db.query(Workout).filter(
        Workout.plan_id == plan_id, Workout.athlete_id == db_plan.athlete_id,
        Workout.date.isnot(None),
    ).all()
    if workouts:
        start = min(start, min(workout.date.date() for workout in workouts))
        end = max(end, max(workout.date.date() for workout in workouts))
    weeks = []
    week_start = start - timedelta(days=start.weekday())
    while week_start <= end:
        weeks.append(PlanWeeklyStats(week_start=week_start, week_end=week_start + timedelta(days=6)))
        week_start += timedelta(days=7)
    if not weeks:
        return weeks
    for workout in workouts:
        week = weeks[(workout.date.date() - weeks[0].week_start).days // 7]
        week.workout_count += 1
        week.validated_count += int(bool(workout.is_validated))
        week.duration_minutes += workout.duration_minutes or 0
        week.distance_km += workout.distance_km or 0
        week.estimated_load += workout.estimated_load or 0
    return weeks

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
    
    # Vérifier s'il y a déjà un plan actif pour cet athlète
    active_plan = db.query(Plan).filter(Plan.athlete_id == target_athlete_id, Plan.is_archived == False).first()
    if active_plan:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Un plan actif existe déjà pour cet athlète.")
    
    plan_data = plan_in.model_dump()
    plan_data.pop("athlete_id", None)
    db_plan = Plan(**plan_data, athlete_id=target_athlete_id)
    db.add(db_plan)
    
    # Récupérer le catalogue
    catalog = db.query(CatalogWorkout).all()
    
    # Générer les entraînements
    try:
        generator = PlanGenerator(db, db_plan, catalog)
        workouts = generator.generate()
        
        db.flush() # Pour avoir l'ID du plan si nécessaire
        
        for workout in workouts:
            workout.plan_id = db_plan.id
            if workout.scheme:
                workout.duration_minutes, workout.distance_km = calculate_volumes(workout.scheme)
                workout.estimated_load = workout.duration_minutes * (1 + workout.difficulty_level / 5)
            db.add(workout)

        athlete = db.query(User).filter(User.id == target_athlete_id).one()
        athlete.vma = 60 / plan_in.estimated_vma
        db.commit()
        db.refresh(db_plan)
        return db_plan
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e500:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erreur lors de la génération du plan : {str(e500)}")

@router.post("/{plan_id}/archive", response_model=PlanResponse)
def archive_plan(plan_id: int, archive_data: PlanArchive, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    db_plan = db.query(Plan).filter(Plan.id == plan_id).first()
    if not db_plan:
        raise HTTPException(status_code=404, detail="Plan non trouvé")
    
    check_athlete_access(current_user, db_plan.athlete_id, db)
    
    db_plan.is_archived = True
    db_plan.cancellation_comment = archive_data.cancellation_comment
    
    # Optionnel: Supprimer les séances futures non validées du calendrier ? 
    # L'énoncé dit : "son plan ne s'affiche plus dans le calendrier"
    # On peut filtrer dans la route /workouts pour ne pas renvoyer les séances des plans archivés.
    
    db.commit()
    db.refresh(db_plan)
    return db_plan

@router.delete("/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_plan(plan_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    db_plan = db.query(Plan).filter(Plan.id == plan_id).first()
    if not db_plan:
        raise HTTPException(status_code=404, detail="Plan non trouvé")
    
    check_athlete_access(current_user, db_plan.athlete_id, db)
    
    db.delete(db_plan)
    db.commit()
    return None
