from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from ..database import get_db
from ..auth import get_current_user
from ..models.user import User
from ..models.plan import Plan
from ..schemas.plan import PlanCreate, PlanResponse, PlanArchive

from ..models.catalog import CatalogWorkout
from ..services.plan_generator import PlanGenerator
from ..models.workout import Workout

router = APIRouter(prefix="/plans", tags=["plans"])

@router.get("/current", response_model=Optional[PlanResponse])
def get_current_plan(athlete_id: Optional[int] = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    target_athlete_id = current_user.id
    if athlete_id and athlete_id != current_user.id:
        if current_user.role != "coach":
            raise HTTPException(status_code=403, detail="Seuls les coachs peuvent voir les plans d'autres athlètes")
        target_athlete_id = athlete_id
    
    return db.query(Plan).filter(Plan.athlete_id == target_athlete_id, Plan.is_archived == False).first()

@router.post("", response_model=PlanResponse)
def create_plan(plan_in: PlanCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    target_athlete_id = current_user.id
    if plan_in.athlete_id and plan_in.athlete_id != current_user.id:
        if current_user.role != "coach":
            raise HTTPException(status_code=403, detail="Seuls les coachs peuvent créer des plans pour d'autres athlètes")
        target_athlete_id = plan_in.athlete_id
    
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
            db.add(workout)
        
        db.commit()
        db.refresh(db_plan)
        return db_plan
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erreur lors de la génération du plan : {str(e)}")

@router.post("/{plan_id}/archive", response_model=PlanResponse)
def archive_plan(plan_id: int, archive_data: PlanArchive, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    query = db.query(Plan).filter(Plan.id == plan_id)
    if current_user.role != "coach":
        query = query.filter(Plan.athlete_id == current_user.id)
        
    db_plan = query.first()
    if not db_plan:
        raise HTTPException(status_code=404, detail="Plan non trouvé")
    
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
    query = db.query(Plan).filter(Plan.id == plan_id)
    if current_user.role != "coach":
        query = query.filter(Plan.athlete_id == current_user.id)
    
    db_plan = query.first()
    if not db_plan:
        raise HTTPException(status_code=404, detail="Plan non trouvé")
    
    db.delete(db_plan)
    db.commit()
    return None
