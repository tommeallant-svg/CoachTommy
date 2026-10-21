from sqlalchemy import Column, Integer, String, Date, Float
from ..database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    role = Column(String, default="athlete") # athlete, coach
    garmin_email = Column(String, nullable=True)
    garmin_token = Column(String, nullable=True)
    garmin_refresh_token = Column(String, nullable=True)

    # Menstrual cycle tracking
    last_period_date = Column(Date, nullable=True)
    cycle_length = Column(Integer, default=28)
    period_length = Column(Integer, default=5)

    # Athlete stats
    vma = Column(Float, nullable=True)
    ftp = Column(Integer, nullable=True) # Watts
