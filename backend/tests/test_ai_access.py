import hashlib
import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from unittest.mock import patch

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from app.ai_auth import get_ai_athlete
from app.api.ai_access import router
from app.auth import create_access_token
from app.database import Base, get_db
from app.models.ai_access import AIAccessKey
from app.models.user import User


class AIAccessTest(unittest.TestCase):
    def setUp(self):
        self.secret = patch.dict(os.environ, {"JWT_SECRET_KEY": "test-secret-with-at-least-32-characters"})
        self.secret.start()
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.engine = create_engine(
            "sqlite:///" + str(Path(self.temp.name) / "test.db"),
            connect_args={"check_same_thread": False, "timeout": 30},
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)
        with self.Session() as db:
            db.add_all([User(id=1, email="athlete@example.com", role="athlete"),
                        User(id=2, email="other@example.com", role="athlete"),
                        User(id=3, email="coach@example.com", role="coach")])
            db.commit()
        app = FastAPI()
        app.include_router(router, prefix="/api")

        @app.get("/test/ai-athlete")
        def ai_athlete(athlete: User = Depends(get_ai_athlete)):
            return {"id": athlete.id}

        def override_db():
            with self.Session() as db:
                yield db

        app.dependency_overrides[get_db] = override_db
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        self.engine.dispose()
        self.temp.cleanup()
        self.secret.stop()

    def jwt(self, email="athlete@example.com"):
        return {"Authorization": "Bearer " + create_access_token({"sub": email})}

    def ai(self, key):
        return {"Authorization": "Bearer " + key}

    def test_jwt_permissions(self):
        for method in (self.client.get, self.client.post, self.client.delete):
            self.assertEqual(method("/api/ai-access").status_code, 401)
            self.assertEqual(method("/api/ai-access", headers=self.ai("invalid")).status_code, 401)
            self.assertEqual(method("/api/ai-access", headers=self.jwt("coach@example.com")).status_code, 403)
        self.assertEqual(self.client.get("/api/ai-access", headers=self.jwt()).json(), {"active": False})

    def test_rotation_revocation_and_isolation(self):
        headers = self.jwt()
        response = self.client.post("/api/ai-access", headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.json()), {"key"})
        key = response.json()["key"]
        self.assertTrue(key.startswith("ct_ai_"))
        with self.Session() as db:
            stored = db.get(AIAccessKey, 1)
            self.assertEqual(stored.key_hash, hashlib.sha256(key.encode()).hexdigest())
            self.assertNotEqual(stored.key_hash, key)
        self.assertEqual(self.client.get("/api/ai-access", headers=headers).json(), {"active": True})
        self.assertEqual(self.client.get("/api/ai-access", headers=self.jwt("other@example.com")).json(), {"active": False})
        self.assertEqual(self.client.get("/test/ai-athlete", headers=self.ai(key)).json(), {"id": 1})
        other = self.client.post("/api/ai-access", headers=self.jwt("other@example.com")).json()["key"]
        new = self.client.post("/api/ai-access", headers=headers).json()["key"]
        self.assertNotEqual(new, key)
        self.assertEqual(self.client.get("/test/ai-athlete", headers=self.ai(key)).status_code, 401)
        self.assertEqual(self.client.get("/test/ai-athlete", headers=self.ai(new)).json(), {"id": 1})
        response = self.client.delete("/api/ai-access", headers=headers)
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.content, b"")
        self.assertEqual(self.client.delete("/api/ai-access", headers=headers).status_code, 204)
        self.assertEqual(self.client.get("/api/ai-access", headers=headers).json(), {"active": False})
        self.assertEqual(self.client.get("/test/ai-athlete", headers=self.ai(new)).status_code, 401)
        self.assertEqual(self.client.get("/test/ai-athlete", headers=self.ai(other)).json(), {"id": 2})

    def test_invalid_ai_credentials_and_role_change(self):
        key = self.client.post("/api/ai-access", headers=self.jwt()).json()["key"]
        for headers in ({}, self.ai("wrong"), self.ai("ct_ai_unknown"),
                        self.jwt(), {"Authorization": "Basic " + key}):
            response = self.client.get("/test/ai-athlete", headers=headers)
            self.assertEqual(response.status_code, 401)
            self.assertEqual(response.headers["www-authenticate"], "Bearer")
        with self.Session() as db:
            db.get(User, 1).role = "coach"
            db.commit()
        self.assertEqual(self.client.get("/test/ai-athlete", headers=self.ai(key)).status_code, 401)

    def test_concurrent_rotations(self):
        barrier = Barrier(8)
        headers = self.jwt()

        def rotate(_):
            barrier.wait(timeout=10)
            return self.client.post("/api/ai-access", headers=headers)

        with ThreadPoolExecutor(max_workers=8) as executor:
            responses = list(executor.map(rotate, range(8)))
        self.assertEqual([r.status_code for r in responses], [200] * 8)
        keys = [r.json()["key"] for r in responses]
        self.assertEqual(len(set(keys)), 8)
        with self.Session() as db:
            rows = db.query(AIAccessKey).filter_by(athlete_id=1).all()
            self.assertEqual(len(rows), 1)
            self.assertIn(rows[0].key_hash, [hashlib.sha256(k.encode()).hexdigest() for k in keys])
        self.assertEqual(sum(self.client.get("/test/ai-athlete", headers=self.ai(k)).status_code == 200 for k in keys), 1)

    def test_existing_sqlite_database_creates_table_idempotently(self):
        AIAccessKey.__table__.drop(self.engine)
        self.assertNotIn("ai_access_keys", inspect(self.engine).get_table_names())
        Base.metadata.create_all(self.engine)
        Base.metadata.create_all(self.engine)
        self.assertIn("ai_access_keys", inspect(self.engine).get_table_names())
        with self.Session() as db:
            self.assertEqual(db.get(User, 1).email, "athlete@example.com")
        self.assertEqual(self.client.post("/api/ai-access", headers=self.jwt()).status_code, 200)


if __name__ == "__main__":
    unittest.main()