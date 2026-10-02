from sqlalchemy import Column, Integer, String
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
