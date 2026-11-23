from sqlalchemy import Column, ForeignKey, Integer, String
from ..database import Base


class AIAccessKey(Base):
    __tablename__ = "ai_access_keys"

    athlete_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    key_hash = Column(String(64), nullable=False, unique=True)