import os
import unittest
from datetime import datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.plans import router
from app.auth import create_access_token
from app.database import Base, get_db
from app.models import user, workout, plan, catalog


class PlanHistoryTest(unittest.TestCase):
    def setUp(self):
        self.old_secret = os.environ.get("JWT_SECRET_KEY")
        os.environ["JWT_SECRET_KEY"] = "test-secret-with-at-least-32-characters"
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)
        with self.Session() as db:
            db.add_all([user.User(id=1, email="athlete@example.com", role="athlete", coach_id=2),
                        user.User(id=2, email="coach@example.com", role="coach"),
                        user.User(id=3, email="other@example.com", role="athlete")])
            for id, archived in [(1, False), (2, True), (3, True)]:
                db.add(plan.Plan(id=id, athlete_id=1, race_name=f"Race {id}",
                                 start_date=datetime(2026, 1, 5), race_date=datetime(2026, 1, 25),
                                 race_distance=10, sessions_per_week=2, goal_type="plaisir",
                                 training_days=[0, 2], estimated_vma=5, is_archived=archived))
            db.add_all([
                workout.Workout(id=1, athlete_id=1, plan_id=1, date=datetime(2026, 1, 5), duration_minutes=30, distance_km=5, estimated_load=40, is_validated=True),
                workout.Workout(id=2, athlete_id=1, plan_id=1, date=datetime(2026, 1, 6), duration_minutes=20, distance_km=None, estimated_load=None, is_validated=False),
                workout.Workout(id=3, athlete_id=1, plan_id=2, date=datetime(2026, 1, 20), duration_minutes=45, distance_km=8, estimated_load=60, is_validated=True),
                workout.Workout(id=4, athlete_id=1, plan_id=None, date=datetime(2026, 1, 5), duration_minutes=99, distance_km=99),
                workout.Workout(id=5, athlete_id=1, plan_id=1, date=datetime(2026, 1, 4, 23, 59), duration_minutes=99),
                workout.Workout(id=6, athlete_id=1, plan_id=1, date=datetime(2026, 1, 26), duration_minutes=99),
                workout.Workout(id=7, athlete_id=3, plan_id=1, date=datetime(2026, 1, 5), duration_minutes=99),
            ])
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
        if self.old_secret is None:
            os.environ.pop("JWT_SECRET_KEY", None)
        else:
            os.environ["JWT_SECRET_KEY"] = self.old_secret

    def headers(self, email="athlete@example.com"):
        return {"Authorization": "Bearer " + create_access_token({"sub": email})}

    def test_history_pagination_and_access(self):
        url = "/api/plans/history"
        response = self.client.get(url, headers=self.headers(), params={"skip": 0, "limit": 1})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["id"], 3)
        self.assertEqual(self.client.get(url, headers=self.headers(), params={"skip": 1}).json()[0]["id"], 2)
        self.assertEqual(self.client.get(url, headers=self.headers(), params={"skip": 3}).json(), [])
        self.assertEqual(self.client.get(url, headers=self.headers("coach@example.com"), params={"athlete_id": 1}).status_code, 200)
        self.assertEqual(self.client.get(url, headers=self.headers("other@example.com"), params={"athlete_id": 1}).status_code, 403)
        self.assertEqual(self.client.get(url, headers=self.headers("coach@example.com"), params={"athlete_id": 3}).status_code, 403)
        self.assertEqual(self.client.get(url, headers=self.headers(), params={"limit": 0}).status_code, 422)
        self.assertEqual(self.client.get(url, headers=self.headers(), params={"skip": -1}).status_code, 422)
        self.assertEqual(self.client.get(url).status_code, 401)

    def test_weekly_statistics_archive_and_cascade(self):
        url = "/api/plans/1/weekly-stats"
        response = self.client.get(url, headers=self.headers())
        self.assertEqual(response.status_code, 200)
        weeks = response.json()
        self.assertEqual(len(weeks), 5)
        self.assertEqual(weeks[0]["workout_count"], 1)
        self.assertEqual(weeks[1], {"week_start": "2026-01-05", "week_end": "2026-01-11", "workout_count": 2, "validated_count": 1, "duration_minutes": 50, "distance_km": 5.0, "estimated_load": 40.0})
        self.assertEqual(weeks[2]["workout_count"], 0)
        self.assertEqual(weeks[2]["duration_minutes"], 0)
        self.assertEqual(weeks[4]["workout_count"], 1)
        self.assertEqual(self.client.get("/api/plans/2/weekly-stats", headers=self.headers()).json()[2]["workout_count"], 1)
        self.assertEqual(self.client.get(url, headers=self.headers("other@example.com")).status_code, 403)
        self.assertEqual(self.client.get(url, headers=self.headers("coach@example.com")).status_code, 200)
        self.assertEqual(self.client.get("/api/plans/999/weekly-stats", headers=self.headers()).status_code, 404)
        self.assertEqual(self.client.post("/api/plans/1/archive", headers=self.headers(), json={"cancellation_comment": "arrêt"}).status_code, 200)
        self.assertEqual(len(self.client.get("/api/plans/history", headers=self.headers()).json()), 3)
        self.assertEqual(self.client.get(url, headers=self.headers()).json(), weeks)
        self.assertEqual(self.client.delete("/api/plans/1", headers=self.headers()).status_code, 204)
        self.assertEqual(self.client.get(url, headers=self.headers()).status_code, 404)
        self.assertEqual(len(self.client.get("/api/plans/history", headers=self.headers()).json()), 2)
        with self.Session() as db:
            self.assertIsNone(db.get(workout.Workout, 1))
            self.assertIsNotNone(db.get(workout.Workout, 4))


if __name__ == "__main__":
    unittest.main()