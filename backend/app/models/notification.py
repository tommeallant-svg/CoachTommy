from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from ..database import Base


class PushSubscription(Base):
    __tablename__ = "push_subscriptions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    endpoint_hash = Column(String(64), nullable=False, unique=True)
    endpoint = Column(Text, nullable=False)
    p256dh = Column(String(128), nullable=False)
    auth = Column(String(64), nullable=False)


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    push_enabled = Column(Boolean, nullable=False, default=False)


class NotificationEvent(Base):
    __tablename__ = "notification_events"

    id = Column(Integer, primary_key=True)
    event_key = Column(String(128), nullable=False, unique=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    kind = Column(String(32), nullable=False)
    workout_id = Column(Integer, ForeignKey("workouts.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


class NotificationScheduleCursor(Base):
    __tablename__ = "notification_schedule_cursors"

    name = Column(String(32), primary_key=True)
    processed_at = Column(DateTime, nullable=False)


class NotificationDispatch(Base):
    __tablename__ = "notification_dispatches"

    event_id = Column(Integer, ForeignKey("notification_events.id", ondelete="CASCADE"), primary_key=True)


class NotificationDelivery(Base):
    __tablename__ = "notification_deliveries"
    __table_args__ = (UniqueConstraint("event_id", "subscription_id"),)

    id = Column(Integer, primary_key=True)
    event_id = Column(Integer, ForeignKey("notification_events.id", ondelete="CASCADE"), nullable=False)
    subscription_id = Column(Integer, ForeignKey("push_subscriptions.id", ondelete="CASCADE"), nullable=False)
    attempts = Column(Integer, nullable=False, default=0)
    next_attempt_at = Column(DateTime, nullable=False)
    delivered_at = Column(DateTime, nullable=True)