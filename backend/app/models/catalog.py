from sqlalchemy import Column, Integer, String, JSON
from ..database import Base

class CatalogWorkout(Base):
    __tablename__ = "catalog_workouts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    workout_type = Column(String) # tempo, VO2Max, etc.
    category = Column(String) # Fractionné
    description = Column(String, nullable=True)
    perceived_difficulty = Column(Integer)
    scheme = Column(JSON) # allures en % VMA
