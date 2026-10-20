# backend/app/api/workouts.py — version complète avec la route d'export Garmin
# Nouveautés par rapport à l'existant :
#   - import de `Response` (fastapi), `re`, et du service garmin_export
#   - route GET /api/workouts/{workout_id}/garmin -> téléchargement du fichier .fit

import re

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session
from typing import List, Optional
from ..database import get_db
from ..models.workout import Workout
from ..models.user import User
from ..schemas.workout import WorkoutCreate, WorkoutResponse, WorkoutUpdate, WorkoutValidation, WorkoutManualCreate
from ..auth import get_current_user
from ..services.garmin_export import generate_workout_fit

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
    
    # Si athlete_id est fourni et l'utilisateur est un coach, on l'utilise
    if workout.athlete_id and current_user.role == "coach":
        # Vérifier que l'athlète existe
        athlete = db.query(User).filter(User.id == workout.athlete_id, User.role == "athlete").first()
        if not athlete:
            raise HTTPException(status_code=404, detail="Athlète non trouvé")
        db_workout.athlete_id = workout.athlete_id
    else:
        db_workout.athlete_id = current_user.id
        
    db_workout.estimated_load = calculate_load(db_workout.duration_minutes, db_workout.difficulty_level)
    db.add(db_workout)
    db.commit()
    db.refresh(db_workout)
    return db_workout

@router.post("/manual", response_model=WorkoutResponse, status_code=status.HTTP_201_CREATED)
def create_manual_workout(workout: WorkoutManualCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    default_name = f"Séance manuelle - {workout.duration_minutes} - {workout.distance_km}"
    name = workout.name or default_name
    pace = format_pace(workout.duration_minutes, workout.distance_km)
    
    athlete_id = current_user.id
    is_validated = True
    
    if workout.athlete_id and current_user.role == "coach":
        # Vérifier que l'athlète existe
        athlete = db.query(User).filter(User.id == workout.athlete_id, User.role == "athlete").first()
        if not athlete:
            raise HTTPException(status_code=404, detail="Athlète non trouvé")
        athlete_id = workout.athlete_id
        # Si c'est un coach qui crée pour un athlète, la séance n'est pas validée par défaut
        is_validated = False

    difficulty_level = workout.difficulty_level or workout.perceived_difficulty or 5
    perceived_diff = workout.perceived_difficulty if is_validated else None
    athlete_comment = workout.athlete_comment if is_validated else None
    
    db_workout = Workout(
        workout_type=workout.workout_type,
        name=name,
        duration_minutes=workout.duration_minutes,
        distance_km=workout.distance_km,
        difficulty_level=difficulty_level,
        perceived_difficulty=perceived_diff,
        athlete_comment=athlete_comment,
        description=workout.description or (f"{name}\n\n{athlete_comment}" if athlete_comment else name),
        date=workout.date,
        is_validated=is_validated,
        athlete_id=athlete_id,
        category=workout.workout_type, # By default
        estimated_load=calculate_load(workout.duration_minutes, difficulty_level),
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

# ---------------------------------------------------------------------------
# NOUVEAU : Export Garmin — télécharge la séance au format FIT Workout
# ---------------------------------------------------------------------------
@router.get("/{workout_id}/garmin")
def export_workout_garmin(workout_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    query = db.query(Workout).filter(Workout.id == workout_id)
    if current_user.role != "coach":
        query = query.filter(Workout.athlete_id == current_user.id)

    db_workout = query.first()
    if db_workout is None:
        raise HTTPException(status_code=404, detail="Workout not found")

    try:
        fit_bytes = generate_workout_fit(db_workout)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la génération du fichier FIT : {str(e)}")

    safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", db_workout.name or "seance")
    return Response(
        content=fit_bytes,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}.fit"'},
    )

@router.patch("/{workout_id}", response_model=WorkoutResponse)
def update_workout(workout_id: int, workout: WorkoutUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    query = db.query(Workout).filter(Workout.id == workout_id)
    if current_user.role != "coach":
        query = query.filter(Workout.athlete_id == current_user.id)
        
    db_workout = query.first()
    if db_workout is None:
        raise HTTPException(status_code=404, detail="Workout not found")
    
    update_data = workout.model_dump(exclude_unset=True)
    
    # Si athlete_id est mis à jour, vérifier qu'il s'agit d'un athlète valide (si coach)
    if "athlete_id" in update_data and current_user.role == "coach":
        athlete_id = update_data["athlete_id"]
        if athlete_id:
            athlete = db.query(User).filter(User.id == athlete_id, User.role == "athlete").first()
            if not athlete:
                raise HTTPException(status_code=404, detail="Athlète non trouvé")
    elif "athlete_id" in update_data:
        # Un athlète ne peut pas changer son propre athlete_id pour celui d'un autre
        update_data.pop("athlete_id")

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

from ..services.garmin_export import push_workout
from ..services.garmin_client import GarminClient

@router.post("/{workout_id}/garmin/push", status_code=status.HTTP_200_OK)
async def push_workout_to_garmin(workout_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Push a workout to the athlete's Garmin Connect account.
    Requires the athlete to be connected to Garmin (tokens stored in database).
    """
    query = db.query(Workout).filter(Workout.id == workout_id)
    if current_user.role != "coach":
        query = query.filter(Workout.athlete_id == current_user.id)
    
    db_workout = query.first()
    
    if db_workout is None:
        raise HTTPException(status_code=404, detail="Workout not found")
    
    # Check if user has Garmin tokens
    if not current_user.garmin_token or not current_user.garmin_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not connected to Garmin Connect. Please connect via /auth/garmin/login first."
        )
    
    try:
        # Initialize Garmin client with stored tokens
        token_dict = {
            "access_token": current_user.garmin_token,
            "refresh_token": current_user.garmin_refresh_token,
            "token_type": "Bearer"
        }
        garmin_client = GarminClient(token_dict=token_dict)
        
        # Push workout to Garmin
        push_workout(db_workout, garmin_client)
        
        return {"status": "ok", "message": "Workout pushed to Garmin Connect successfully"}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to push workout to Garmin Connect: {str(e)}"
        )
