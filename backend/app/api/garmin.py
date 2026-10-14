"""
API routes for Garmin Connect authentication and workout sync.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel
from ..database import get_db
from ..models.user import User
from ..auth import get_current_user
from ..services.garmin_client import GarminClient

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
    email: str,
    password: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Connect to Garmin Connect with provided credentials.
    Stores tokens in the user's profile.
    """
    try:
        # Create Garmin client and login
        garmin_client = GarminClient(email=email, password=password)
        token_dict = garmin_client.login()
        
        if not token_dict:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Failed to authenticate with Garmin Connect"
            )
        
        # Store tokens in database
        current_user.garmin_email = email
        current_user.garmin_token = token_dict.get("access_token")
        current_user.garmin_refresh_token = token_dict.get("refresh_token")
        db.commit()
        db.refresh(current_user)
        
        return GarminStatusResponse(
            is_connected=True,
            garmin_email=email
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
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
    return GarminStatusResponse(
        is_connected=current_user.garmin_token is not None,
        garmin_email=current_user.garmin_email
    )
