from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr, field_validator
from datetime import date

class UserBase(BaseModel):
    email: str
    role: str

class UserCreate(UserBase):
    password: str

class UserRegister(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value):
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("password")
    @classmethod
    def validate_password(cls, value):
        if len(value) < 8 or len(value.encode("utf-8")) > 72:
            raise ValueError("Le mot de passe doit comporter au moins 8 caractères et au maximum 72 octets UTF-8.")
        return value

class UserResponse(UserBase):
    id: int
    coach_id: Optional[int] = None
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
