from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, JSON, ForeignKey, Float
from sqlalchemy.orm import relationship
from ..database import Base

class Plan(Base):
    __tablename__ = "plans"

    id = Column(Integer, primary_key=True, index=True)
    athlete_id = Column(Integer, ForeignKey("users.id"))
    
    race_name = Column(String)
    race_date = Column(DateTime)
    race_distance = Column(Float)
    race_estimated_time = Column(String, nullable=True) # hh:mm:ss
    
    start_date = Column(DateTime)
    sessions_per_week = Column(Integer)
    goal_type = Column(String) # plaisir, maintien, mixte, intensité, trail
    training_days = Column(JSON) # e.g. [0, 2, 4] for Mon, Wed, Fri
    estimated_vma = Column(Float) # min/km
    
    is_archived = Column(Boolean, default=False)
    cancellation_comment = Column(Text, nullable=True)
    
    athlete = relationship("User", foreign_keys=[athlete_id])
    workouts = relationship("Workout", back_populates="plan", cascade="all, delete-orphan")
