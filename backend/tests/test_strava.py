import os
import time
import uuid
from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.strava import router
from app.auth import create_access_token
from app.database import Base, get_db
from app.models import user, workout, plan, catalog, strava
from app.services.strava_client import valid_access_token
from app.strava_migration import migrate_strava


@pytest.fixture
def context(monkeypatch):
    for key, value in {"STRAVA_CLIENT_ID": "123", "STRAVA_CLIENT_SECRET": "secret",
                       "STRAVA_REDIRECT_URI": "https://example.com/api/auth/strava/callback",
                       "STRAVA_ENCRYPTION_KEY": Fernet.generate_key().decode(),
                       "JWT_SECRET_KEY": "test-secret-with-at-least-32-characters"}.items():
        monkeypatch.setenv(key, value)
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as db:
        db.add_all([user.User(id=1, email="one@example.com"), user.User(id=2, email="two@example.com")])
        db.commit()
    app = FastAPI()
    app.include_router(router, prefix="/api")
    def override_db():
        with Session() as db:
            yield db
    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as client:
        yield client, Session
    engine.dispose()


def headers(email="one@example.com"):
    return {"Authorization": "Bearer " + create_access_token({"sub": email})}


def start(client):
    response = client.post("/api/auth/strava/authorize", headers=headers())
    assert response.status_code == 200
    return parse_qs(urlparse(response.json()["authorization_url"]).query)["state"][0]


def test_jwt_authentication_rejects_forged_and_expired_tokens(context):
    client, _ = context
    assert client.get("/api/auth/strava/status", headers=headers()).status_code == 200
    forged = jwt.encode({"sub": "one@example.com"}, "SUPER_SECRET_KEY_FOR_JWT", algorithm="HS256")
    assert client.get("/api/auth/strava/status", headers={"Authorization": "Bearer " + forged}).status_code == 401
    expired = create_access_token({"sub": "one@example.com"}, expires_delta=timedelta(seconds=-1))
    assert client.get("/api/auth/strava/status", headers={"Authorization": "Bearer " + expired}).status_code == 401


def test_jwt_secret_must_be_configured(monkeypatch):
    from app.auth import jwt_secret_key
    for value in (None, "short", "SUPER_SECRET_KEY_FOR_JWT", " " * 40):
        if value is None:
            monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
        else:
            monkeypatch.setenv("JWT_SECRET_KEY", value)
        with pytest.raises(RuntimeError):
            jwt_secret_key()


def test_oauth_refresh_disconnect(context, monkeypatch):
    client, Session = context
    calls = []
    def post(url, **kwargs):
        calls.append((url, kwargs))
        if url.endswith("deauthorize"):
            return httpx.Response(200, json={}, request=httpx.Request("POST", url))
        refresh = kwargs["data"]["grant_type"] == "refresh_token"
        return httpx.Response(200, json={"access_token": "new-access" if refresh else "access-secret",
            "refresh_token": "new-refresh" if refresh else "refresh-secret", "expires_at": int(time.time()) + (3600 if refresh else 1),
            "athlete": {"id": 1234}}, request=httpx.Request("POST", url))
    monkeypatch.setattr(httpx, "post", post)
    assert client.get("/api/auth/strava/status").status_code == 401
    state = start(client)
    params = {"state": state, "code": "code", "scope": "read,activity:read"}
    assert client.get("/api/auth/strava/callback", params=params).status_code == 200
    assert client.get("/api/auth/strava/callback", params=params).status_code == 400
    assert client.get("/api/auth/strava/status", headers=headers()).json()["connected"]
    assert not client.get("/api/auth/strava/status", headers=headers("two@example.com")).json()["connected"]
    with Session() as db:
        connection = db.get(strava.StravaConnection, 1)
        assert "access-secret" not in connection.access_token
        assert "refresh-secret" not in connection.refresh_token
        assert valid_access_token(db, 1) == "new-access"
        assert "new-refresh" not in connection.refresh_token
    assert client.post("/api/auth/strava/disconnect", headers=headers()).json() == {"connected": False}
    assert calls[-1][1]["headers"]["Authorization"] == "Bearer new-access"
    assert not client.get("/api/auth/strava/status", headers=headers()).json()["connected"]


def test_denial_expiry_and_configuration(context, monkeypatch):
    client, Session = context
    state = start(client)
    assert client.get("/api/auth/strava/callback", params={"state": state, "error": "access_denied"}).status_code == 400
    assert client.get("/api/auth/strava/callback", params={"state": state, "code": "x", "scope": "activity:read"}).status_code == 400
    state = start(client)
    with Session() as db:
        db.query(strava.StravaOAuthState).update({strava.StravaOAuthState.expires_at: datetime.utcnow() - timedelta(seconds=1)})
        db.commit()
    assert client.get("/api/auth/strava/callback", params={"state": state}).status_code == 400
    monkeypatch.delenv("STRAVA_ENCRYPTION_KEY")
    assert client.post("/api/auth/strava/authorize", headers=headers()).status_code == 503


def test_migration_preserves_existing_sqlite():
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY, email VARCHAR)"))
        conn.execute(text("CREATE TABLE workouts (id INTEGER PRIMARY KEY, name VARCHAR)"))
        conn.execute(text("INSERT INTO users VALUES (1, 'existing')"))
        conn.execute(text("INSERT INTO workouts VALUES (1, 'planned')"))
    migrate_strava(engine)
    migrate_strava(engine)
    with engine.connect() as conn:
        assert conn.execute(text("SELECT email FROM users")).scalar_one() == "existing"
        assert conn.execute(text("SELECT name FROM workouts")).scalar_one() == "planned"
        assert conn.execute(text("SELECT count(*) FROM strava_connections")).scalar_one() == 0
    engine.dispose()


def test_migration_postgresql():
    url = os.getenv("STRAVA_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("STRAVA_TEST_POSTGRES_URL not configured")
    schema = "strava_test_" + uuid.uuid4().hex
    admin = create_engine(url)
    with admin.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(url)
    @event.listens_for(engine, "connect")
    def set_schema(connection, record):
        cursor = connection.cursor()
        cursor.execute(f'SET search_path TO "{schema}"')
        cursor.close()
        connection.commit()
    try:
        with engine.begin() as conn:
            conn.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY, email VARCHAR)"))
            conn.execute(text("CREATE TABLE workouts (id INTEGER PRIMARY KEY, name VARCHAR)"))
            conn.execute(text("INSERT INTO users VALUES (1, 'existing')"))
            conn.execute(text("INSERT INTO workouts VALUES (1, 'planned')"))
        migrate_strava(engine)
        migrate_strava(engine)
        with engine.connect() as conn:
            assert conn.execute(text("SELECT email FROM users")).scalar_one() == "existing"
            assert conn.execute(text("SELECT name FROM workouts")).scalar_one() == "planned"
            assert conn.execute(text("SELECT count(*) FROM strava_connections")).scalar_one() == 0
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


def test_failed_exchange_and_rejected_scope(context, monkeypatch):
    client, _ = context
    def fail(url, **kwargs):
        raise httpx.ConnectError("network unavailable")
    monkeypatch.setattr(httpx, "post", fail)
    state = start(client)
    assert client.get("/api/auth/strava/callback", params={"state": state, "code": "x", "scope": "read"}).status_code == 400
    state = start(client)
    params = {"state": state, "code": "x", "scope": "activity:read"}
    response = client.get("/api/auth/strava/callback", params=params)
    assert response.status_code == 502
    assert "network unavailable" not in response.text
    assert client.get("/api/auth/strava/callback", params=params).status_code == 400