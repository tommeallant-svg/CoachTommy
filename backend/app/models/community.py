from sqlalchemy import Boolean, CheckConstraint, Column, ForeignKey, Integer, UniqueConstraint
from ..database import Base


class Friendship(Base):
    __tablename__ = "community_friendships"
    __table_args__ = (
        UniqueConstraint("user_low_id", "user_high_id", name="uq_community_pair"),
        CheckConstraint("user_low_id < user_high_id", name="ck_community_order"),
        CheckConstraint("requester_id = user_low_id OR requester_id = user_high_id", name="ck_community_requester"),
    )

    id = Column(Integer, primary_key=True)
    user_low_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user_high_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    requester_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    accepted = Column(Boolean, nullable=False, default=False)