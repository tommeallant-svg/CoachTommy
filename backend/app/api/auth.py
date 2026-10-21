from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta
from ..database import get_db
from ..auth import verify_password, create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES, get_current_user
from ..models.user import User
from ..schemas.user import Token, UserResponse, UserUpdateMenstrualCycle, UserUpdateStats

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/login", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    return {
        "access_token": access_token, 
        "token_type": "bearer", 
        "id": user.id,
        "role": user.role,
        "email": user.email
    }

@router.get("/me", response_model=UserResponse)
async def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user

@router.patch("/me/menstrual-cycle", response_model=UserResponse)
async def update_menstrual_cycle(
    update_data: UserUpdateMenstrualCycle,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update menstrual cycle information for the current user."""
    current_user.last_period_date = update_data.last_period_date
    current_user.cycle_length = update_data.cycle_length
    current_user.period_length = update_data.period_length
    db.commit()
    db.refresh(current_user)
    return current_user

@router.patch("/me/stats", response_model=UserResponse)
async def update_athlete_stats(
    update_data: UserUpdateStats,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update VMA and FTP information for the current user."""
    if update_data.vma is not None:
        current_user.vma = update_data.vma
    if update_data.ftp is not None:
        current_user.ftp = update_data.ftp
    db.commit()
    db.refresh(current_user)
    return current_user
