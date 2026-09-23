from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from ..database import get_db
from ..models.workout import Workout
from ..models.user import User
from ..schemas.workout import WorkoutCreate, WorkoutResponse, WorkoutUpdate, WorkoutValidation, WorkoutManualCreate
from ..auth import get_current_user

router = APIRouter(prefix="/workouts", tags=["workouts"])

def calculate_load(duration_minutes: int, difficulty_level: int) -> float:
    return duration_minutes + duration_minutes * difficulty_level / 5

def format_pace(duration_min, distance_km):
    if distance_km <= 0: return "0:00"
    pace_decimal = duration_min / distance_km
    minutes = int(pace_decimal)
    seconds = int((pace_decimal - minutes) * 60)
    return f"{minutes}:{seconds:02d}"

@router.post("", response_model=WorkoutResponse, status_code=status.HTTP_201_CREATED)
def create_workout(workout: WorkoutCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    db_workout = Workout(**workout.model_dump())
    db_workout.athlete_id = current_user.id
    db_workout.estimated_load = calculate_load(db_workout.duration_minutes, db_workout.difficulty_level)
    db.add(db_workout)
    db.commit()
    db.refresh(db_workout)
    return db_workout

@router.post("/manual", response_model=WorkoutResponse, status_code=status.HTTP_201_CREATED)
def create_manual_workout(workout: WorkoutManualCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    name = f"Séance manuelle - {workout.duration_minutes} - {workout.distance_km}"
    pace = format_pace(workout.duration_minutes, workout.distance_km)
    
    db_workout = Workout(
        workout_type=workout.workout_type,
        name=name,
        duration_minutes=workout.duration_minutes,
        distance_km=workout.distance_km,
        difficulty_level=workout.perceived_difficulty,
        perceived_difficulty=workout.perceived_difficulty,
        athlete_comment=workout.athlete_comment,
        description=f"{name}\n\n{workout.athlete_comment}" if workout.athlete_comment else name,
        date=workout.date,
        is_validated=True,
        athlete_id=current_user.id,
        category=workout.workout_type, # By default
        estimated_load=calculate_load(workout.duration_minutes, workout.perceived_difficulty),
        scheme=[{
            "repetitions": 1,
            "intervals": [{
                "type": "Course à pied",
                "duration": workout.duration_minutes,
                "distance": workout.distance_km,
                "pace_min": pace,
                "pace_max": pace
            }]
        }]
    )
    db.add(db_workout)
    db.commit()
    db.refresh(db_workout)
    return db_workout

from ..models.plan import Plan

@router.get("", response_model=List[WorkoutResponse])
def read_workouts(skip: int = 0, limit: int = 100, athlete_id: Optional[int] = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    target_athlete_id = current_user.id
    if athlete_id and athlete_id != current_user.id:
        if current_user.role != "coach":
            raise HTTPException(status_code=403, detail="Seuls les coachs peuvent voir les séances d'autres athlètes")
        target_athlete_id = athlete_id
        
    return db.query(Workout).join(Plan, Workout.plan_id == Plan.id, isouter=True).filter(
        Workout.athlete_id == target_athlete_id,
        (Plan.id == None) | (Plan.is_archived == False)
    ).order_by(Workout.date.asc()).offset(skip).limit(limit).all()

@router.get("/{workout_id}", response_model=WorkoutResponse)
def read_workout(workout_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    query = db.query(Workout).filter(Workout.id == workout_id)
    if current_user.role != "coach":
        query = query.filter(Workout.athlete_id == current_user.id)
        
    db_workout = query.first()
    if db_workout is None:
        raise HTTPException(status_code=404, detail="Workout not found")
    return db_workout

@router.patch("/{workout_id}", response_model=WorkoutResponse)
def update_workout(workout_id: int, workout: WorkoutUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    query = db.query(Workout).filter(Workout.id == workout_id)
    if current_user.role != "coach":
        query = query.filter(Workout.athlete_id == current_user.id)
        
    db_workout = query.first()
    if db_workout is None:
        raise HTTPException(status_code=404, detail="Workout not found")
    
    update_data = workout.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_workout, key, value)
    
    if "duration_minutes" in update_data or "difficulty_level" in update_data:
        db_workout.estimated_load = calculate_load(db_workout.duration_minutes, db_workout.difficulty_level)
        
    db.commit()
    db.refresh(db_workout)
    return db_workout

@router.post("/{workout_id}/validate", response_model=WorkoutResponse)
def validate_workout(workout_id: int, validation: WorkoutValidation, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    query = db.query(Workout).filter(Workout.id == workout_id)
    if current_user.role != "coach":
        query = query.filter(Workout.athlete_id == current_user.id)
        
    db_workout = query.first()
    if db_workout is None:
        raise HTTPException(status_code=404, detail="Workout not found")
    
    db_workout.is_validated = True
    db_workout.perceived_difficulty = validation.perceived_difficulty
    db_workout.athlete_comment = validation.athlete_comment
    
    db.commit()
    db.refresh(db_workout)
    return db_workout

@router.delete("/{workout_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_workout(workout_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    query = db.query(Workout).filter(Workout.id == workout_id)
    if current_user.role != "coach":
        query = query.filter(Workout.athlete_id == current_user.id)
        
    db_workout = query.first()
    if db_workout is None:
        raise HTTPException(status_code=404, detail="Workout not found")
    db.delete(db_workout)
    db.commit()
    return None
