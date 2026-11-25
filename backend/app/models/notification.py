from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Text
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