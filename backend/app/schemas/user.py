from typing import Optional
from pydantic import BaseModel
from datetime import date

class UserBase(BaseModel):
    email: str
    role: str

class UserCreate(UserBase):
    password: str

class UserResponse(UserBase):
    id: int
    last_period_date: Optional[date] = None
    cycle_length: Optional[int] = 28
    period_length: Optional[int] = 5
    vma: Optional[float] = None
    ftp: Optional[int] = None

    class Config:
        from_attributes = True

class UserUpdateStats(BaseModel):
    vma: Optional[float] = None
    ftp: Optional[int] = None

class Token(BaseModel):
    access_token: str
    token_type: str
    id: int
    role: str
    email: str

class TokenData(BaseModel):
    email: Optional[str] = None
