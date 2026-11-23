import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.ai_auth import hash_ai_key
from app.api.ai_plans import router
from app.database import Base, get_db
from app.models import user, workout, plan, catalog, ai_access


class AIPlansTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)
        with self.Session() as db:
            db.add_all([user.User(id=1, email="a@example.com", role="athlete", vma=10),
                        user.User(id=2, email="b@example.com", role="athlete", vma=11)])
            db.add_all([ai_access.AIAccessKey(athlete_id=1, key_hash=hash_ai_key("ct_ai_a")),
                        ai_access.AIAccessKey(athlete_id=2, key_hash=hash_ai_key("ct_ai_b"))])
            db.commit()
        app = FastAPI()
        app.include_router(router, prefix="/api")

        def override_db():
            with self.Session() as db:
                yield db

        app.dependency_overrides[get_db] = override_db
        self.client = TestClient(app)
        self.headers = {"Authorization": "Bearer ct_ai_a"}
        self.other = {"Authorization": "Bearer ct_ai_b"}
        self.payload = {"race_name": "10 km", "race_date": "2026-03-01T00:00:00",
                        "race_distance": 10, "start_date": "2026-01-05T00:00:00",
                        "sessions_per_week": 3, "goal_type": "plaisir",
                        "training_days": [1, 3, 5], "estimated_vma": 5}

    def tearDown(self):
        self.client.close()
        self.engine.dispose()

    def test_create_archive_delete_and_isolation(self):
        url = "/api/ai/plans"
        self.assertEqual(self.client.get(url + "/current").status_code, 401)
        self.assertIsNone(self.client.get(url + "/current", headers=self.headers).json())
        result = self.client.post(url, headers=self.headers, json=self.payload)
        self.assertEqual(result.status_code, 200, result.text)
        plan_id = result.json()["id"]
        self.assertEqual(self.client.get(f"{url}/{plan_id}/weekly-stats", headers=self.other).status_code, 404)
        self.assertGreater(len(self.client.get(f"{url}/{plan_id}/weekly-stats", headers=self.headers).json()), 0)
        with self.Session() as db:
            self.assertEqual(db.get(user.User, 1).vma, 12)
            self.assertEqual(db.get(user.User, 2).vma, 11)
            self.assertGreater(db.query(workout.Workout).filter_by(plan_id=plan_id, athlete_id=1).count(), 0)
        self.assertEqual(self.client.post(url, headers=self.headers, json=self.payload).status_code, 400)
        for method, suffix in [(self.client.get, ""), (self.client.post, "/archive"), (self.client.delete, "")]:
            kwargs = {"headers": self.other}
            if suffix:
                kwargs["json"] = {}
            self.assertEqual(method(f"{url}/{plan_id}{suffix}", **kwargs).status_code, 404)
        self.assertEqual(self.client.post(f"{url}/{plan_id}/archive", headers=self.headers, json={"cancellation_comment": "stop"}).status_code, 200)
        self.assertEqual(len(self.client.get(url + "/history", headers=self.headers).json()), 1)
        self.assertEqual(self.client.get(url + "/history", headers=self.other).json(), [])
        self.assertEqual(self.client.delete(f"{url}/{plan_id}", headers=self.headers).status_code, 204)
        with self.Session() as db:
            self.assertEqual(db.query(workout.Workout).filter_by(plan_id=plan_id).count(), 0)

    def test_rejects_targets_validation_and_bad_plan(self):
        url = "/api/ai/plans"
        for field in ("athlete_id", "is_validated", "is_archived"):
            self.assertEqual(self.client.post(url, headers=self.headers, json={**self.payload, field: 2}).status_code, 422)
        nested = {**self.payload, "training_days": {"1": {"athlete_id": 2}}}
        self.assertEqual(self.client.post(url, headers=self.headers, json=nested).status_code, 422)
        self.assertEqual(self.client.get(url + "/current?athlete_id=2", headers=self.headers).status_code, 422)
        self.assertEqual(self.client.post(url, headers=self.headers, json={**self.payload, "race_distance": -1}).status_code, 422)
        self.assertEqual(self.client.post(url, headers=self.headers, json={**self.payload, "start_date": "2026-01-06T00:00:00"}).status_code, 422)
        with self.Session() as db:
            self.assertEqual(db.query(plan.Plan).count(), 0)
            self.assertEqual(db.get(user.User, 1).vma, 10)


if __name__ == "__main__":
    unittest.main()