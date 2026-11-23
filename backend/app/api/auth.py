from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from datetime import timedelta
from ..database import get_db
from ..auth import verify_password, get_password_hash, create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES, get_current_user
from ..models.user import User
from ..schemas.user import Token, UserResponse, UserUpdateStats, UserRegister

class AuthRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def safe_handler(request):
            try:
                return await handler(request)
            except RequestValidationError as exc:
                errors = [{key: value for key, value in error.items() if key not in ("input", "ctx")} for error in exc.errors()]
                return JSONResponse(status_code=422, content={"detail": errors})

        return safe_handler

router = APIRouter(prefix="/auth", tags=["auth"], route_class=AuthRoute)

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(data: UserRegister, db: Session = Depends(get_db)):
    email = str(data.email).strip().lower()
    if db.query(User).filter(func.lower(func.trim(User.email)) == email).first():
        raise HTTPException(status_code=409, detail="Cette adresse email est déjà utilisée.")
    user = User(email=email, hashed_password=get_password_hash(data.password), role="athlete", coach_id=None)
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Cette adresse email est déjà utilisée.")
    db.refresh(user)
    return user

@router.post("/login", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(func.lower(func.trim(User.email)) == form_data.username.strip().lower()).first()
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
