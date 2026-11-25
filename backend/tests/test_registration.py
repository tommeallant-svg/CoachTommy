import os
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.auth import router
from app.auth import verify_password
from app.database import Base, get_db
from app.models import user, workout, plan, catalog


class RegistrationTest(unittest.TestCase):
    def setUp(self):
        self.secret = os.environ.get("JWT_SECRET_KEY")
        os.environ["JWT_SECRET_KEY"] = "test-secret-with-at-least-32-characters"
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)
        app = FastAPI()
        app.include_router(router, prefix="/api")

        def db_override():
            with self.Session() as db:
                yield db

        app.dependency_overrides[get_db] = db_override
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        self.engine.dispose()
        if self.secret is None:
            os.environ.pop("JWT_SECRET_KEY", None)
        else:
            os.environ["JWT_SECRET_KEY"] = self.secret

    def test_create_login_and_duplicates(self):
        response = self.client.post("/api/auth/register", json={"email": "  Test@Example.COM  ", "password": "password123"})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["email"], "test@example.com")
        self.assertEqual(response.json()["role"], "athlete")
        self.assertIsNone(response.json()["coach_id"])
        self.assertNotIn("password", response.text)
        with self.Session() as db:
            account = db.query(user.User).one()
            self.assertNotEqual(account.hashed_password, "password123")
            self.assertTrue(verify_password("password123", account.hashed_password))
        login = self.client.post("/api/auth/login", data={"username": " TEST@example.com ", "password": "password123"})
        self.assertEqual(login.status_code, 200)
        self.assertEqual(self.client.get("/api/auth/me", headers={"Authorization": "Bearer " + login.json()["access_token"]}).status_code, 200)
        self.assertEqual(self.client.post("/api/auth/login", data={"username": "test@example.com", "password": "incorrect"}).status_code, 401)
        self.assertEqual(self.client.post("/api/auth/register", json={"email": " TEST@example.com ", "password": "password123"}).status_code, 409)
        with self.Session() as db:
            db.add(user.User(email="Old@Example.com", hashed_password="x", role="athlete"))
            db.commit()
        self.assertEqual(self.client.post("/api/auth/register", json={"email": "old@example.com", "password": "password123"}).status_code, 409)

    def test_validation_does_not_expose_password(self):
        for data in [
            {"email": "invalid", "password": "password123"},
            {"email": "a@example.com", "password": "short"},
            {"email": "a@example.com", "password": "é" * 37},
            {"email": "a@example.com", "password": "password123", "role": "coach"},
            {"email": "a@example.com", "password": "password123", "coach_id": 1},
        ]:
            response = self.client.post("/api/auth/register", json=data)
            self.assertEqual(response.status_code, 422)
            self.assertNotIn(data["password"], response.text)
        self.assertEqual(self.client.post("/api/auth/register", json={"email": "a@example.com", "password": "é" * 36}).status_code, 201)

    def test_special_characters_and_login(self):
        password = "éà!#$%&'()*+,-./:;<=>?@[\\]^_`{|}~"
        response = self.client.post("/api/auth/register", json={"email": "special+tag@example.com", "password": password})
        self.assertEqual(response.status_code, 201)
        login = self.client.post("/api/auth/login", data={"username": "special+tag@example.com", "password": password})
        self.assertEqual(login.status_code, 200)
        self.assertEqual(self.client.post("/api/auth/register", json={"email": "SPECIAL+TAG@example.com", "password": password}).status_code, 409)

    def test_null_password_is_rejected_without_disclosure(self):
        password = "password\u0000special"
        response = self.client.post("/api/auth/register", json={"email": "null@example.com", "password": password})
        self.assertEqual(response.status_code, 422)
        self.assertNotIn("password\\u0000special", response.text)

    def test_unrelated_integrity_error_is_not_a_duplicate(self):
        with TestClient(self.client.app, raise_server_exceptions=False) as client, patch("sqlalchemy.orm.Session.commit", side_effect=IntegrityError("insert", {}, Exception())):
            response = client.post("/api/auth/register", json={"email": "a@example.com", "password": "password123"})
        self.assertEqual(response.status_code, 500)
        with self.Session() as db:
            self.assertEqual(db.query(user.User).count(), 0)

    def test_duplicate_insert_race_returns_conflict(self):
        from app.auth import get_password_hash

        def insert_competing_account(password):
            with self.Session() as db:
                db.add(user.User(email="race@example.com", hashed_password="x", role="athlete"))
                db.commit()
            return get_password_hash(password)

        with patch("app.api.auth.get_password_hash", side_effect=insert_competing_account):
            response = self.client.post("/api/auth/register", json={"email": "race@example.com", "password": "password123"})
        self.assertEqual(response.status_code, 409)
        with self.Session() as db:
            self.assertEqual(db.query(user.User).count(), 1)


if __name__ == "__main__":
    unittest.main()