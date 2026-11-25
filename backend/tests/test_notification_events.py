import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from threading import Barrier
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.workouts import router
from app.auth import create_access_token
from app.database import Base, get_db
from app.models.notification import NotificationEvent
from app.models.plan import Plan
from app.models.user import User
from app.models.workout import Workout


class NotificationEventsTest(unittest.TestCase):
    def setUp(self):
        self.secret = patch.dict(os.environ, {"JWT_SECRET_KEY": "test-secret-with-at-least-32-characters"})
        self.secret.start()
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.engine = create_engine("sqlite:///" + str(Path(self.temp.name) / "test.db"),
                                    connect_args={"check_same_thread": False})
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)
        with self.Session() as db:
            db.add_all([User(id=1, email="coach@example.com", role="coach"),
                        User(id=2, email="athlete@example.com", role="athlete", coach_id=1),
                        User(id=3, email="other@example.com", role="athlete")])
            db.add(Workout(id=1, athlete_id=2, name="Tempo", workout_type="Tempo", duration_minutes=30,
                           difficulty_level=5, date=datetime(2026, 1, 1), is_validated=False))
            db.commit()
        app = FastAPI()
        app.include_router(router, prefix="/api")

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

    def headers(self, email):
        return {"Authorization": "Bearer " + create_access_token({"sub": email})}

    def test_validation_emits_once_for_coach(self):
        url = "/api/workouts/1/validate"
        body = {"perceived_difficulty": 5}
        self.assertEqual(self.client.post(url, json=body, headers=self.headers("other@example.com")).status_code, 404)
        for _ in range(2):
            self.assertEqual(self.client.post(url, json=body, headers=self.headers("athlete@example.com")).status_code, 200)
        with self.Session() as db:
            events = db.query(NotificationEvent).all()
            self.assertEqual(len(events), 1)
            self.assertEqual((events[0].user_id, events[0].kind), (1, "workout_validated"))

    def test_patch_emits_validation_event(self):
        response = self.client.patch("/api/workouts/1", json={"is_validated": True},
                                     headers=self.headers("athlete@example.com"))
        self.assertEqual(response.status_code, 200)
        with self.Session() as db:
            self.assertEqual(db.query(NotificationEvent).count(), 1)

    def test_coach_can_validate_assigned_athlete(self):
        response = self.client.post("/api/workouts/1/validate", json={"perceived_difficulty": 5},
                                    headers=self.headers("coach@example.com"))
        self.assertEqual(response.status_code, 200)
        with self.Session() as db:
            self.assertEqual(db.query(NotificationEvent).count(), 0)

    def test_concurrent_validation_creates_one_event(self):
        barrier = Barrier(2)
        headers = self.headers("athlete@example.com")

        def validate(_):
            barrier.wait(timeout=10)
            return self.client.post("/api/workouts/1/validate", json={"perceived_difficulty": 5},
                                    headers=headers).status_code

        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(list(pool.map(validate, range(2))), [200, 200])
        with self.Session() as db:
            self.assertEqual(db.query(NotificationEvent).count(), 1)


if __name__ == "__main__":
    unittest.main()