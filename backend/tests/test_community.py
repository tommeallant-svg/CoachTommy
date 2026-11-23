import os
import unittest
from datetime import datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import community, plans, workouts
from app.auth import create_access_token
from app.database import Base, get_db
from app.models import user, plan, workout, catalog
from app.models.community import Friendship


class CommunityTest(unittest.TestCase):
    def setUp(self):
        self.old_secret = os.environ.get("JWT_SECRET_KEY")
        os.environ["JWT_SECRET_KEY"] = "test-secret-with-at-least-32-characters"
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)
        with self.Session() as db:
            db.add_all([user.User(id=i, email=f"user{i}@example.com", role="athlete") for i in range(1, 4)])
            db.add(plan.Plan(id=1, athlete_id=2, is_archived=False, race_name="private race", cancellation_comment="private"))
            db.add_all([
                workout.Workout(id=1, athlete_id=2, plan_id=1, name="Tempo", date=datetime(2026, 1, 2), sport="running", duration_minutes=30, distance_km=5, description="Training", athlete_comment="private", is_validated=True, scheme=[{"repetitions": 1, "comment": "private", "intervals": [{"type": "tempo", "duration": 30, "strava": "private"}]}]),
                workout.Workout(id=2, athlete_id=3, plan_id=1, name="other", date=datetime(2026, 1, 3)),
                workout.Workout(id=3, athlete_id=2, plan_id=1, name="undated"),
            ])
            db.commit()
        app = FastAPI()
        for router in (community.router, plans.router, workouts.router):
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

    def headers(self, uid):
        return {"Authorization": "Bearer " + create_access_token({"sub": f"user{uid}@example.com"})}

    def test_invitations_and_revocation(self):
        base = "/api/community"
        h1, h2, h3 = (self.headers(i) for i in (1, 2, 3))
        self.assertEqual(self.client.get(base + "/friends").status_code, 401)
        self.assertEqual(self.client.post(base + "/invitations", headers=h1, json={"email": "user1@example.com"}).status_code, 400)
        self.assertEqual(self.client.post(base + "/invitations", headers=h1, json={"email": "absent@example.com"}).status_code, 404)
        self.assertEqual(self.client.get(base + "/friends/2/plan", headers=h1).status_code, 403)
        response = self.client.post(base + "/invitations", headers=h1, json={"email": "USER2@example.com"})
        self.assertEqual(response.status_code, 201)
        cid = response.json()["id"]
        self.assertEqual(self.client.get(base + "/invitations", headers=h2).json()[0]["direction"], "received")
        for headers, email in ((h1, "user2@example.com"), (h2, "user1@example.com")):
            self.assertEqual(self.client.post(base + "/invitations", headers=headers, json={"email": email}).status_code, 409)
        self.assertEqual(self.client.post(f"{base}/invitations/{cid}/accept", headers=h1).status_code, 404)
        self.assertEqual(self.client.post(f"{base}/invitations/{cid}/accept", headers=h3).status_code, 404)
        self.assertEqual(self.client.delete(f"{base}/connections/{cid}", headers=h3).status_code, 404)
        self.assertEqual(self.client.get(base + "/friends/2/plan", headers=h1).status_code, 403)
        self.assertEqual(self.client.post(f"{base}/invitations/{cid}/accept", headers=h2).status_code, 200)
        self.assertEqual(len(self.client.get(base + "/friends", headers=h1).json()), 1)
        shared = self.client.get(base + "/friends/2/plan", headers=h1).json()
        self.assertEqual(shared, {"workouts": [{"name": "Tempo", "date": "2026-01-02T00:00:00", "sport": "running", "duration_minutes": 30, "distance_km": 5.0, "description": "Training", "scheme": [{"repetitions": 1, "intervals": [{"type": "tempo", "duration": 30}]}]}]})
        self.assertIsNone(self.client.get(base + "/friends/1/plan", headers=h2).json())
        self.assertEqual(self.client.get(base + "/friends/2/plan", headers=h3).status_code, 403)
        self.assertEqual(self.client.patch("/api/workouts/1", headers=h1, json={"name": "changed"}).status_code, 404)
        self.assertEqual(self.client.delete("/api/plans/1", headers=h1).status_code, 403)
        self.assertEqual(self.client.delete(f"{base}/connections/{cid}", headers=h2).status_code, 204)
        self.assertEqual(self.client.get(base + "/friends/2/plan", headers=h1).status_code, 403)
        response = self.client.post(base + "/invitations", headers=h2, json={"email": "user1@example.com"})
        self.assertEqual(self.client.delete(f"{base}/connections/{response.json()['id']}", headers=h1).status_code, 204)

    def test_database_pair_constraints(self):
        with self.Session() as db:
            db.add(Friendship(user_low_id=1, user_high_id=2, requester_id=1))
            db.commit()
            db.add(Friendship(user_low_id=1, user_high_id=2, requester_id=2))
            with self.assertRaises(IntegrityError):
                db.commit()
            db.rollback()
            db.add(Friendship(user_low_id=2, user_high_id=1, requester_id=2))
            with self.assertRaises(IntegrityError):
                db.commit()
            db.rollback()


if __name__ == "__main__":
    unittest.main()