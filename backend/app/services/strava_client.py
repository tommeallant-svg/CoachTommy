import os
import time
from urllib.parse import urlparse

import httpx
from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException

from ..models.strava import StravaConnection


def configuration():
    client_id = os.getenv("STRAVA_CLIENT_ID")
    client_secret = os.getenv("STRAVA_CLIENT_SECRET")
    redirect_uri = os.getenv("STRAVA_REDIRECT_URI", "")
    key = os.getenv("STRAVA_ENCRYPTION_KEY")
    parsed = urlparse(redirect_uri)
    if not client_id or not client_secret or not key or parsed.scheme != "https" or not parsed.netloc:
        raise HTTPException(503, "Strava configuration unavailable")
    try:
        cipher = Fernet(key.encode())
    except (ValueError, TypeError):
        raise HTTPException(503, "Strava configuration unavailable")
    return client_id, client_secret, redirect_uri, cipher


def token_request(data):
    try:
        response = httpx.post("https://www.strava.com/oauth/token", data=data, timeout=10.0)
        response.raise_for_status()
        result = response.json()
        if not isinstance(result.get("access_token"), str) or not isinstance(result.get("refresh_token"), str):
            raise ValueError()
        result["expires_at"] = int(result["expires_at"])
        return result
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        raise HTTPException(502, "Strava token request failed")


def store_tokens(connection, tokens, cipher):
    connection.access_token = cipher.encrypt(tokens["access_token"].encode()).decode()
    connection.refresh_token = cipher.encrypt(tokens["refresh_token"].encode()).decode()
    connection.expires_at = tokens["expires_at"]


def valid_access_token(db, user_id):
    client_id, secret, _, cipher = configuration()
    connection = db.query(StravaConnection).filter_by(user_id=user_id).with_for_update().first()
    if not connection:
        raise HTTPException(404, "Strava not connected")
    try:
        if connection.expires_at <= time.time() + 60:
            refresh = cipher.decrypt(connection.refresh_token.encode()).decode()
            tokens = token_request({"client_id": client_id, "client_secret": secret,
                                    "grant_type": "refresh_token", "refresh_token": refresh})
            store_tokens(connection, tokens, cipher)
            db.commit()
        return cipher.decrypt(connection.access_token.encode()).decode()
    except (InvalidToken, UnicodeError):
        db.rollback()
        raise HTTPException(503, "Strava token encryption unavailable")