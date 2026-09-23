from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, JSON, ForeignKey, Float
from sqlalchemy.orm import relationship
from datetime import datetime
from ..database import Base

class Workout(Base):
    __tablename__ = "workouts"

    id = Column(Integer, primary_key=True, index=True)
    workout_type = Column(String, index=True)  # Endurance, Tempo, Seuil, VO2 Max, Sprint, Libre
    category = Column(String, index=True) # Endurance, Libre, Fractionné, Sortie Longue, Trail
    name = Column(String, index=True)
    duration_minutes = Column(Integer)
    distance_km = Column(Float, nullable=True)
    difficulty_level = Column(Integer)  # 1 to 10
    estimated_load = Column(Float, nullable=True)
    description = Column(Text)
    
    # Training scheme stored as JSON
    # Structure example: [{"type": "interval", "pace": "4:00", "duration": 5, "distance": 1.25, "repetitions": 1}]
    scheme = Column(JSON, nullable=True)
    
    # Execution data
    date = Column(DateTime, index=True)
    is_validated = Column(Boolean, default=False)
    perceived_difficulty = Column(Integer, nullable=True)
    athlete_comment = Column(Text, nullable=True)
    
    plan_id = Column(Integer, ForeignKey("plans.id"), nullable=True)
    plan = relationship("Plan", back_populates="workouts")
    
    athlete_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    athlete = relationship("User")

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
