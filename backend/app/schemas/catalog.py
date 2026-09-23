from typing import List, Any, Optional
from pydantic import BaseModel

class CatalogWorkoutBase(BaseModel):
    name: str
    workout_type: str
    category: str
    description: Optional[str] = None
    perceived_difficulty: int
    scheme: List[Any]

class CatalogWorkoutCreate(CatalogWorkoutBase):
    pass

class CatalogWorkoutUpdate(BaseModel):
    name: Optional[str] = None
    workout_type: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    perceived_difficulty: Optional[int] = None
    scheme: Optional[List[Any]] = None

class CatalogWorkoutResponse(CatalogWorkoutBase):
    id: int

    class Config:
        from_attributes = True
