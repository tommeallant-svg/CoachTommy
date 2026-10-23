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
    
    tokenstore = os.getenv("GARMINTOKENS", "~/.garminconnect")
    tokenstore_path = str(Path(tokenstore).expanduser())
    print("tokenstore_path")
    is_connected = False
    try:
        garmin = Garmin()
        garmin.login(tokenstore_path)
        is_connected = True
    except (GarminConnectAuthenticationError, GarminConnectConnectionError):
        print("No valid tokens found — please log in.")
    return GarminStatusResponse(
        is_connected = is_connected,
        garmin_email=current_user.garmin_email
    )
