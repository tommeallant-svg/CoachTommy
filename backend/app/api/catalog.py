from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from ..database import get_db
from ..auth import get_current_coach
from ..models.catalog import CatalogWorkout
from ..schemas.catalog import CatalogWorkoutCreate, CatalogWorkoutResponse, CatalogWorkoutUpdate

router = APIRouter(prefix="/catalog", tags=["catalog"])

@router.get("", response_model=List[CatalogWorkoutResponse])
def get_catalog(db: Session = Depends(get_db)):
    return db.query(CatalogWorkout).all()

@router.post("", response_model=CatalogWorkoutResponse, status_code=status.HTTP_201_CREATED)
def create_catalog_workout(workout: CatalogWorkoutCreate, db: Session = Depends(get_db), current_coach = Depends(get_current_coach)):
    db_workout = CatalogWorkout(**workout.model_dump())
    db.add(db_workout)
    db.commit()
    db.refresh(db_workout)
    return db_workout

@router.patch("/{workout_id}", response_model=CatalogWorkoutResponse)
def update_catalog_workout(workout_id: int, workout: CatalogWorkoutUpdate, db: Session = Depends(get_db), current_coach = Depends(get_current_coach)):
    db_workout = db.query(CatalogWorkout).filter(CatalogWorkout.id == workout_id).first()
    if not db_workout:
        raise HTTPException(status_code=404, detail="Workout not found in catalog")
    
    update_data = workout.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_workout, key, value)
    
    db.commit()
    db.refresh(db_workout)
    return db_workout

@router.delete("/{workout_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_catalog_workout(workout_id: int, db: Session = Depends(get_db), current_coach = Depends(get_current_coach)):
    db_workout = db.query(CatalogWorkout).filter(CatalogWorkout.id == workout_id).first()
    if not db_workout:
        raise HTTPException(status_code=404, detail="Workout not found in catalog")
    db.delete(db_workout)
    db.commit()
    return None
