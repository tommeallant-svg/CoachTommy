"""
API routes for Garmin Connect authentication and workout sync.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel
from ..database import get_db
from ..models.user import User
import os
from pathlib import Path
from ..auth import get_current_user
from garminconnect import Garmin
from ..services.garmin_client import GarminClient
from ..services.garmin_workout_service import GarminWorkoutService
from ..models.workout import Workout
from garminconnect import (
    GarminConnectAuthenticationError,
    GarminConnectTooManyRequestsError,
    GarminConnectConnectionError
)

router = APIRouter(prefix="/auth/garmin", tags=["garmin"])


class GarminLoginRequest(BaseModel):
    """Request body for Garmin login."""
    email: str
    password: str


class GarminStatusResponse(BaseModel):
    """Response for Garmin auth status."""
    is_connected: bool
    garmin_email: Optional[str] = None


@router.post("/login", response_model=GarminStatusResponse)
async def garmin_login(
    request: GarminLoginRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Connect to Garmin Connect with provided credentials.
    Stores tokens in the user's profile.
    """
    try:
        # Create Garmin client and login
        garmin_client = GarminClient(email=request.email, password=request.password)
        tokenstore_path = garmin_client.login()
        
        if not tokenstore_path:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Failed to authenticate with Garmin Connect"
            )
        
        # Store tokens in database
        import json
        current_user.garmin_email = request.email
        # On stocke le dictionnaire complet en JSON dans garmin_token pour plus de robustesse
        tokens_dict = garmin_client.get_token_dict()
        if tokens_dict:
            current_user.garmin_token = json.dumps(tokens_dict)
            
        db.commit()
        db.refresh(current_user)
        
        return GarminStatusResponse(
            is_connected=True,
            garmin_email=request.email
        )
        
    except GarminConnectTooManyRequestsError:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Garmin Connect is rate limiting requests. Please wait a few minutes before trying again."
        )
    except GarminConnectAuthenticationError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Garmin Connect credentials. Please check your email and password."
        )
    except GarminConnectConnectionError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not connect to Garmin Connect services. Please try again later."
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Garmin authentication failed: {str(e)}"
        )


@router.post("/logout", response_model=GarminStatusResponse)
async def garmin_logout(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Disconnect from Garmin Connect by clearing stored tokens.
    """
    current_user.garmin_email = None
    current_user.garmin_token = None
    current_user.garmin_refresh_token = None
    db.commit()
    db.refresh(current_user)
    
    return GarminStatusResponse(is_connected=False)


@router.get("/status", response_model=GarminStatusResponse)
async def garmin_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Check if user is connected to Garmin Connect.
    """
    tokenstore_path = GarminClient.sync_tokens_to_file(current_user.garmin_token)
    is_connected = False
    
    if not current_user.garmin_token:
        return GarminStatusResponse(is_connected=False, garmin_email=current_user.garmin_email)

    try:
        garmin = Garmin()
        garmin.login(tokenstore_path)
        is_connected = True
    except (GarminConnectAuthenticationError, GarminConnectConnectionError):
        print("No valid tokens found — please log in.")
    except Exception as e:
        print(f"Error checking Garmin status: {e}")
        
    return GarminStatusResponse(
        is_connected = is_connected,
        garmin_email=current_user.garmin_email
    )


@router.post("/sync-workout/{workout_id}")
async def sync_workout_to_garmin(
    workout_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Synchronise un workout spécifique vers Garmin Connect.
    """
    # 1. Récupérer le workout
    workout = db.query(Workout).filter(Workout.id == workout_id).first()
    if not workout:
        raise HTTPException(status_code=404, detail="Workout non trouvé")
    if (workout.sport or '').lower() in ('swimming', 'strength'):
        raise HTTPException(status_code=422, detail="Export Garmin indisponible pour ce sport")
        
    # 2. Vérifier la connexion Garmin
    tokenstore_path = GarminClient.sync_tokens_to_file(current_user.garmin_token)
    
    if not current_user.garmin_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Non connecté à Garmin Connect. Veuillez vous reconnecter."
        )

    try:
        garmin = Garmin()
        garmin.login(tokenstore_path)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Non connecté à Garmin Connect. Veuillez vous reconnecter."
        )

    # 3. Transformer le workout
    try:
        garmin_workout = GarminWorkoutService.transform_to_garmin(workout, current_user)
        workout_dict = garmin_workout.to_dict()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur lors de la transformation du workout : {str(e)}")

    # 4. Uploader sur Garmin
    try:
        result = garmin.upload_workout(workout_dict)
        # Le résultat contient souvent le workoutId créé
        garmin_workout_id = result.get("workoutId")
        if garmin_workout_id:
            workout.garmin_workout_id = str(garmin_workout_id)
            db.commit()
            
        return {"status": "success", "garmin_workout_id": garmin_workout_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'upload vers Garmin : {str(e)}")
