from datetime import datetime
from sqlalchemy import BigInteger, Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, Text
from ..database import Base


class StravaConnection(Base):
    __tablename__ = "strava_connections"

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    athlete_id = Column(BigInteger, nullable=False, unique=True)
    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text, nullable=False)
    expires_at = Column(Integer, nullable=False)
    scope = Column(String, nullable=False)


class StravaOAuthState(Base):
    __tablename__ = "strava_oauth_states"

    state_hash = Column(String(64), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)


class StravaActivity(Base):
    __tablename__ = "strava_activities"

    id = Column(BigInteger, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    workout_id = Column(Integer, ForeignKey("workouts.id", ondelete="SET NULL"), unique=True, nullable=True)
    validation_created = Column(Boolean, nullable=False, default=False)
    data = Column(JSON, nullable=False)


class StravaTask(Base):
    __tablename__ = "strava_tasks"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    kind = Column(String, nullable=False)
    payload = Column(JSON, nullable=False)
    status = Column(String, nullable=False, default="pending")
    attempts = Column(Integer, nullable=False, default=0)
    due_at = Column(DateTime, nullable=False, default=datetime.utcnow)