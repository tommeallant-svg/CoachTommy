# backend/app/api/workouts.py — version complète avec la route d'export Garmin
# Nouveautés par rapport à l'existant :
#   - import de `Response` (fastapi), `re`, et du service garmin_export
#   - route GET /api/workouts/{workout_id}/garmin -> téléchargement du fichier .fit

import re
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import or_
from sqlalchemy.orm import Session
from typing import List, Optional
from ..database import get_db
from ..models.workout import Workout
from ..models.user import User
from ..models.notification import NotificationEvent
from .notifications import insert_for
from garminconnect import Garmin
import os
from pathlib import Path
from ..schemas.workout import WorkoutCreate, WorkoutResponse, WorkoutUpdate, WorkoutValidation, WorkoutManualCreate
from ..auth import get_current_user
from ..services.garmin_export import generate_workout_fit
from ..services.garmin_mapper import GarminMapper
from ..services.workouts import calculate_load, create_workout as create_workout_service, list_workouts, update_workout as update_workout_service
from garminconnect import (
    GarminConnectAuthenticationError,
    GarminConnectTooManyRequestsError,
    GarminConnectConnectionError
)

router = APIRouter(prefix="/workouts", tags=["workouts"])

def format_pace(duration_min, distance_km):
    if distance_km <= 0: return "0:00"
    pace_decimal = duration_min / distance_km
    minutes = int(pace_decimal)
    seconds = int((pace_decimal - minutes) * 60)
    return f"{minutes}:{seconds:02d}"

def accessible_workouts(db, current_user):
    query = db.query(Workout)
    if current_user.role == "coach":
        assigned = db.query(User.id).filter(User.coach_id == current_user.id)
        return query.filter(or_(Workout.athlete_id == current_user.id, Workout.athlete_id.in_(assigned)))
    return query.filter(Workout.athlete_id == current_user.id)

@router.post("", response_model=WorkoutResponse, status_code=status.HTTP_201_CREATED)
def create_workout(workout: WorkoutCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    athlete_id = current_user.id
    
    # Si athlete_id est fourni et l'utilisateur est un coach, on l'utilise
    if workout.athlete_id and current_user.role == "coach":
        # Vérifier que l'athlète existe et est soit un athlète, soit le coach lui-même
        athlete = db.query(User).filter(User.id == workout.athlete_id).first()
        if not athlete or (athlete.id != current_user.id and (athlete.role != "athlete" or athlete.coach_id != current_user.id)):
            raise HTTPException(status_code=404, detail="Athlète non trouvé")
        athlete_id = workout.athlete_id
    return create_workout_service(db, workout.model_dump(), athlete_id)

@router.post("/manual", response_model=WorkoutResponse, status_code=status.HTTP_201_CREATED)
def create_manual_workout(workout: WorkoutManualCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    default_name = f"Séance manuelle - {workout.duration_minutes} - {workout.distance_km}"
    name = workout.name or default_name
    pace = format_pace(workout.duration_minutes, workout.distance_km)
    
    athlete_id = current_user.id
    is_validated = True
    
    if workout.athlete_id and current_user.role == "coach":
        # Vérifier que l'athlète existe et est soit un athlète, soit le coach lui-même
        athlete = db.query(User).filter(User.id == workout.athlete_id).first()
        if not athlete or (athlete.id != current_user.id and (athlete.role != "athlete" or athlete.coach_id != current_user.id)):
            raise HTTPException(status_code=404, detail="Athlète non trouvé")
        athlete_id = workout.athlete_id
        # Si c'est un coach qui crée pour un athlète (différent de lui-même), la séance n'est pas validée par défaut
        if athlete_id != current_user.id:
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
                "distance": workout.distance_km * 1000,
                "pace_min": pace,
                "pace_max": pace
            }]
        }]
    )
    db.add(db_workout)
    db.commit()
    db.refresh(db_workout)
    return db_workout

@router.get("", response_model=List[WorkoutResponse])
def read_workouts(skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=500), athlete_id: Optional[int] = None,
                  include_archived: bool = False, date_from: Optional[datetime] = None,
                  date_to: Optional[datetime] = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    target_athlete_id = current_user.id
    if athlete_id and athlete_id != current_user.id:
        if current_user.role != "coach":
            raise HTTPException(status_code=403, detail="Seuls les coachs peuvent voir les séances d'autres athlètes")
        # Vérifier que l'athlète est bien attribué à ce coach
        athlete = db.query(User).filter(User.id == athlete_id).first()
        if not athlete or athlete.coach_id != current_user.id:
            raise HTTPException(status_code=403, detail="Cet athlète ne vous est pas attribué")

        target_athlete_id = athlete_id
        
    return list_workouts(db, target_athlete_id, skip, limit, include_archived, date_from, date_to)

@router.get("/{workout_id}", response_model=WorkoutResponse)
def read_workout(workout_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    query = accessible_workouts(db, current_user).filter(Workout.id == workout_id)
        
    db_workout = query.first()
    if db_workout is None:
        raise HTTPException(status_code=404, detail="Workout not found")
    return db_workout

# ---------------------------------------------------------------------------
# NOUVEAU : Export Garmin — télécharge la séance au format FIT Workout
# ---------------------------------------------------------------------------
@router.get("/{workout_id}/garmin")
def export_workout_garmin(workout_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    query = accessible_workouts(db, current_user).filter(Workout.id == workout_id)

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
    query = accessible_workouts(db, current_user).filter(Workout.id == workout_id)
        
    db_workout = query.first()
    if db_workout is None:
        raise HTTPException(status_code=404, detail="Workout not found")
    
    update_data = workout.model_dump(exclude_unset=True)

    # Si athlete_id est mis à jour, vérifier qu'il s'agit d'un athlète valide (si coach)
    if "athlete_id" in update_data and current_user.role == "coach":
        athlete_id = update_data["athlete_id"]
        if athlete_id:
            athlete = db.query(User).filter(User.id == athlete_id).first()
            if not athlete or (athlete.id != current_user.id and athlete.coach_id != current_user.id):
                raise HTTPException(status_code=404, detail="Athlète non trouvé")
    elif "athlete_id" in update_data:
        # Un athlète ne peut pas changer son propre athlete_id pour celui d'un autre
        update_data.pop("athlete_id")

    if update_data.get("is_validated") is True and db_workout.athlete_id == current_user.id and current_user.coach_id:
        changed = db.query(Workout).filter(
            Workout.id == workout_id, Workout.is_validated.is_not(True)
        ).update({Workout.is_validated: True}, synchronize_session=False)
        if changed:
            statement = insert_for(db)(NotificationEvent).values(
                event_key=f"workout_validated:{workout_id}", user_id=current_user.coach_id,
                kind="workout_validated", workout_id=workout_id,
            ).on_conflict_do_nothing(index_elements=[NotificationEvent.event_key])
            db.execute(statement)
    return update_workout_service(db, db_workout, update_data)

@router.post("/{workout_id}/validate", response_model=WorkoutResponse)
def validate_workout(workout_id: int, validation: WorkoutValidation, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    query = accessible_workouts(db, current_user).filter(Workout.id == workout_id)
        
    db_workout = query.first()
    if db_workout is None:
        raise HTTPException(status_code=404, detail="Workout not found")

    changed = db.query(Workout).filter(
        Workout.id == workout_id, Workout.is_validated.is_not(True)
    ).update({Workout.is_validated: True}, synchronize_session=False)
    if changed and db_workout.athlete_id == current_user.id and current_user.coach_id and current_user.coach_id != current_user.id:
        statement = insert_for(db)(NotificationEvent).values(
            event_key=f"workout_validated:{workout_id}", user_id=current_user.coach_id,
            kind="workout_validated", workout_id=workout_id,
        ).on_conflict_do_nothing(index_elements=[NotificationEvent.event_key])
        db.execute(statement)
    db_workout.perceived_difficulty = validation.perceived_difficulty
    db_workout.athlete_comment = validation.athlete_comment
    
    db.commit()
    db.refresh(db_workout)
    return db_workout

@router.delete("/{workout_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_workout(workout_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    query = accessible_workouts(db, current_user).filter(Workout.id == workout_id)
        
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
    query = accessible_workouts(db, current_user).filter(Workout.id == workout_id)
    
    db_workout = query.first()
    
    if db_workout is None:
        raise HTTPException(status_code=404, detail="Workout not found")
    payload = GarminMapper.workout_to_garmin(db_workout)

    # Check if user has Garmin tokens
    tokenstore_path = GarminClient.sync_tokens_to_file(current_user.garmin_token)
    
    if not current_user.garmin_token:
        raise HTTPException(status_code=401, detail="Please log in to Garmin Connect first")

    try:
        garmin = Garmin()
        garmin.login(tokenstore_path)
        print(payload)
        garmin.upload_workout(payload)
        return {"status": "ok", "message": "Workout pushed to Garmin Connect successfully"}

    except (GarminConnectAuthenticationError, GarminConnectConnectionError):
        print("No valid tokens found — please log in.")
        raise HTTPException(status_code=401, detail="Please log in")

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to push workout to Garmin Connect: {str(e)}"
        )
