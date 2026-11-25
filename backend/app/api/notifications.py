import base64
import hashlib
import re
from urllib.parse import urlsplit

from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models.notification import NotificationPreference, PushSubscription
from ..models.user import User


class SafeValidationRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def safe_handler(request: Request):
            try:
                response = await handler(request)
            except RequestValidationError:
                response = JSONResponse(status_code=422, content={"detail": "Invalid request"})
            response.headers["Cache-Control"] = "no-store"
            return response

        return safe_handler


router = APIRouter(prefix="/notifications", tags=["notifications"], route_class=SafeValidationRoute)

PUSH_HOSTS = frozenset({"fcm.googleapis.com", "updates.push.services.mozilla.com", "web.push.apple.com"})


class Keys(BaseModel):
    model_config = ConfigDict(extra="forbid")
    p256dh: str = Field(min_length=1, max_length=128, strict=True)
    auth: str = Field(min_length=1, max_length=64, strict=True)

    @field_validator("p256dh", "auth")
    @classmethod
    def validate_key(cls, value, info):
        try:
            if not re.fullmatch(r"[A-Za-z0-9_-]+={0,2}", value):
                raise ValueError()
            raw = base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)
            if info.field_name == "auth" and len(raw) != 16:
                raise ValueError()
            if info.field_name == "p256dh":
                if len(raw) != 65 or raw[0] != 4:
                    raise ValueError()
                ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), raw)
        except ValueError:
            raise ValueError("Invalid key") from None
        return value


class SubscriptionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    endpoint: str = Field(min_length=1, max_length=2048, strict=True)
    keys: Keys

    @field_validator("endpoint")
    @classmethod
    def validate_endpoint(cls, value):
        try:
            url = urlsplit(value)
            if (url.scheme != "https" or url.hostname not in PUSH_HOSTS or url.username is not None
                    or url.password is not None or url.fragment or url.port not in (None, 443)
                    or any(ord(c) <= 32 or ord(c) == 127 for c in value)):
                raise ValueError()
        except ValueError:
            raise ValueError("Invalid endpoint") from None
        return value


class PreferencesIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    push_enabled: StrictBool


def insert_for(db):
    dialect = db.get_bind().dialect.name
    if dialect == "sqlite":
        return sqlite_insert
    if dialect == "postgresql":
        return postgresql_insert
    raise HTTPException(status_code=500, detail="Unsupported database")


@router.get("/subscriptions")
def list_subscriptions(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(PushSubscription.id).filter_by(user_id=user.id).order_by(PushSubscription.id).all()
    return [{"id": row.id} for row in rows]


@router.post("/subscriptions")
def register_subscription(data: SubscriptionIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    endpoint_hash = hashlib.sha256(data.endpoint.encode("utf-8")).hexdigest()
    statement = insert_for(db)(PushSubscription).values(
        user_id=user.id, endpoint_hash=endpoint_hash, endpoint=data.endpoint,
        p256dh=data.keys.p256dh, auth=data.keys.auth,
    )
    statement = statement.on_conflict_do_update(
        index_elements=[PushSubscription.endpoint_hash],
        set_={"p256dh": data.keys.p256dh, "auth": data.keys.auth},
        where=(PushSubscription.user_id == user.id) & (PushSubscription.endpoint == data.endpoint),
    ).returning(PushSubscription.id)
    subscription_id = db.execute(statement).scalar_one_or_none()
    db.commit()
    if subscription_id is None:
        raise HTTPException(status_code=409, detail="Subscription unavailable")
    return {"id": subscription_id}


@router.delete("/subscriptions/{subscription_id}", status_code=204)
def delete_subscription(subscription_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    deleted = db.query(PushSubscription).filter_by(id=subscription_id, user_id=user.id).delete()
    db.commit()
    if not deleted:
        raise HTTPException(status_code=404, detail="Subscription not found")


@router.get("/preferences")
def get_preferences(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    preference = db.get(NotificationPreference, user.id)
    return {"push_enabled": preference.push_enabled if preference else False}


@router.put("/preferences")
def set_preferences(data: PreferencesIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    statement = insert_for(db)(NotificationPreference).values(user_id=user.id, push_enabled=data.push_enabled)
    statement = statement.on_conflict_do_update(
        index_elements=[NotificationPreference.user_id], set_={"push_enabled": data.push_enabled}
    )
    db.execute(statement)
    db.commit()
    return {"push_enabled": data.push_enabled}