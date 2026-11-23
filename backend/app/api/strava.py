import hashlib
import secrets
from datetime import datetime, timedelta
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models.strava import StravaActivity, StravaConnection, StravaOAuthState, StravaTask
from ..models.user import User
from ..services.strava_client import configuration, store_tokens, token_request, valid_access_token

router = APIRouter(prefix="/auth/strava", tags=["strava"])


@router.post("/authorize")
def authorize(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    client_id, _, redirect_uri, _ = configuration()
    state = secrets.token_urlsafe(32)
    db.query(StravaOAuthState).filter_by(user_id=current_user.id).delete()
    db.add(StravaOAuthState(state_hash=hashlib.sha256(state.encode()).hexdigest(),
                            user_id=current_user.id, expires_at=datetime.utcnow() + timedelta(minutes=10)))
    db.commit()
    params = {"client_id": client_id, "redirect_uri": redirect_uri, "response_type": "code",
              "approval_prompt": "auto", "scope": "read,activity:read", "state": state}
    return {"authorization_url": "https://www.strava.com/oauth/authorize?" + urlencode(params)}


@router.get("/callback")
def callback(state: str = "", code: str = "", scope: str = "", error: str = "", db: Session = Depends(get_db)):
    digest = hashlib.sha256(state.encode()).hexdigest()
    pending = db.query(StravaOAuthState).filter_by(state_hash=digest).first()
    if not pending or pending.expires_at <= datetime.utcnow():
        raise HTTPException(400, "Invalid or expired OAuth state")
    user_id = pending.user_id
    deleted = db.query(StravaOAuthState).filter_by(state_hash=digest).delete(synchronize_session=False)
    db.commit()
    if not deleted:
        raise HTTPException(400, "Invalid or expired OAuth state")
    if error or not code:
        raise HTTPException(400, "Strava authorization declined")
    scopes = set(scope.split(","))
    if "activity:read" not in scopes and "activity:read_all" not in scopes:
        raise HTTPException(400, "Strava activity permission required")
    client_id, secret, _, cipher = configuration()
    tokens = token_request({"client_id": client_id, "client_secret": secret,
                            "code": code, "grant_type": "authorization_code"})
    try:
        athlete_id = int(tokens["athlete"]["id"])
        if athlete_id <= 0:
            raise ValueError()
    except (KeyError, TypeError, ValueError):
        raise HTTPException(502, "Invalid Strava token response")
    connection = db.query(StravaConnection).filter_by(user_id=user_id).first()
    if connection and connection.athlete_id != athlete_id:
        raise HTTPException(409, "Disconnect the existing Strava account first")
    if not connection:
        connection = StravaConnection(user_id=user_id, athlete_id=athlete_id)
        db.add(connection)
    connection.scope = scope
    store_tokens(connection, tokens, cipher)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Strava account already connected")
    return {"connected": True}


@router.get("/status")
def connection_status(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    connection = db.query(StravaConnection).filter_by(user_id=current_user.id).first()
    return {"connected": connection is not None, "scope": connection.scope if connection else None}


@router.post("/disconnect")
def disconnect(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    connection = db.query(StravaConnection).filter_by(user_id=current_user.id).first()
    if connection:
        token = valid_access_token(db, current_user.id)
        try:
            response = httpx.post("https://www.strava.com/oauth/deauthorize",
                                  headers={"Authorization": "Bearer " + token}, timeout=10.0)
            if response.status_code not in (200, 401):
                response.raise_for_status()
        except httpx.HTTPError:
            raise HTTPException(502, "Strava disconnection failed")
    db.query(StravaOAuthState).filter_by(user_id=current_user.id).delete()
    db.query(StravaTask).filter_by(user_id=current_user.id).delete()
    db.query(StravaActivity).filter_by(user_id=current_user.id).delete()
    db.query(StravaConnection).filter_by(user_id=current_user.id).delete()
    db.commit()
    return {"connected": False}