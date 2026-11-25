import base64
import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from app.api.notifications import router
from app.auth import create_access_token
from app.database import Base, get_db
from app.models.notification import NotificationPreference, PushSubscription
from app.models.user import User


class NotificationsTest(unittest.TestCase):
    def setUp(self):
        self.secret = patch.dict(os.environ, {"JWT_SECRET_KEY": "test-secret-with-at-least-32-characters"})
        self.secret.start()
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.engine = create_engine("sqlite:///" + str(Path(self.temp.name) / "test.db"),
                                    connect_args={"check_same_thread": False, "timeout": 30})
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)
        with self.Session() as db:
            db.add_all([User(id=1, email="a@example.com", role="athlete"),
                        User(id=2, email="b@example.com", role="coach")])
            db.commit()
        app = FastAPI()
        app.include_router(router, prefix="/api")

        def override_db():
            with self.Session() as db:
                yield db

        app.dependency_overrides[get_db] = override_db
        self.client = TestClient(app)
        public = ec.generate_private_key(ec.SECP256R1()).public_key().public_bytes(
            serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
        encode = lambda value: base64.urlsafe_b64encode(value).decode().rstrip("=")
        self.data = {"endpoint": "https://fcm.googleapis.com/fcm/send/secret-token", "keys": {
            "p256dh": encode(public), "auth": encode(b"0123456789abcdef")}}

    def tearDown(self):
        self.client.close()
        self.engine.dispose()
        self.temp.cleanup()
        self.secret.stop()

    def jwt(self, email="a@example.com"):
        return {"Authorization": "Bearer " + create_access_token({"sub": email})}

    def test_authentication_and_preferences(self):
        for method, path in [(self.client.get, "/subscriptions"), (self.client.post, "/subscriptions"),
                             (self.client.delete, "/subscriptions/1"), (self.client.get, "/preferences"),
                             (self.client.put, "/preferences")]:
            self.assertEqual(method("/api/notifications" + path).status_code, 401)
            self.assertEqual(method("/api/notifications" + path, headers={"Authorization": "Bearer invalid"}).status_code, 401)
        path = "/api/notifications/preferences"
        self.assertEqual(self.client.get(path, headers=self.jwt()).json(), {"push_enabled": False})
        self.assertEqual(self.client.put(path, headers=self.jwt(), json={"push_enabled": True}).json(), {"push_enabled": True})
        self.assertEqual(self.client.get(path, headers=self.jwt("b@example.com")).json(), {"push_enabled": False})
        for body in ({}, {"push_enabled": 1}, {"push_enabled": True, "user_id": 2}):
            self.assertEqual(self.client.put(path, headers=self.jwt(), json=body).status_code, 422)

    def test_ownership_rotation_and_redaction(self):
        path = "/api/notifications/subscriptions"
        a, b = self.jwt(), self.jwt("b@example.com")
        response = self.client.post(path, headers=a, json=self.data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["cache-control"], "no-store")
        subscription_id = response.json()["id"]
        rotated = {**self.data, "keys": {**self.data["keys"], "auth": base64.urlsafe_b64encode(b"fedcba9876543210").decode().rstrip("=")}}
        self.assertEqual(self.client.post(path, headers=a, json=rotated).json(), {"id": subscription_id})
        self.assertEqual(self.client.post(path, headers=b, json=self.data).status_code, 409)
        self.assertEqual(self.client.get(path, headers=b).json(), [])
        self.assertEqual(self.client.get(path, headers=a).json(), [{"id": subscription_id}])
        self.assertEqual(self.client.delete(f"{path}/{subscription_id}", headers=b).status_code, 404)
        with self.Session() as db:
            self.assertEqual(db.get(PushSubscription, subscription_id).user_id, 1)
            self.assertEqual(db.get(PushSubscription, subscription_id).auth, rotated["keys"]["auth"])
        self.assertEqual(self.client.delete(f"{path}/{subscription_id}", headers=a).status_code, 204)
        self.assertEqual(self.client.post(path, headers=b, json=self.data).status_code, 200)

    def test_validation_does_not_echo_secrets(self):
        path = "/api/notifications/subscriptions"
        for endpoint in ("http://fcm.googleapis.com/secret", "https://user:pass@fcm.googleapis.com/secret", "https://fcm.googleapis.com:444/", "https://fcm.googleapis.com/#fragment", "https://example.com/secret", "https://fcm.googleapis.com.evil.example/secret", "https://127.0.0.1/secret"):
            data = {**self.data, "endpoint": endpoint}
            response = self.client.post(path, headers=self.jwt(), json=data)
            self.assertEqual(response.status_code, 422)
            self.assertEqual(response.json(), {"detail": "Invalid request"})
        for keys in ({"p256dh": "secret", "auth": "secret"}, {**self.data["keys"], "auth": "x"}):
            response = self.client.post(path, headers=self.jwt(), json={**self.data, "keys": keys})
            self.assertEqual(response.status_code, 422)
            self.assertEqual(response.json(), {"detail": "Invalid request"})

    def test_concurrent_claim_and_additive_creation(self):
        PushSubscription.__table__.drop(self.engine)
        NotificationPreference.__table__.drop(self.engine)
        Base.metadata.create_all(self.engine)
        Base.metadata.create_all(self.engine)
        self.assertIn("push_subscriptions", inspect(self.engine).get_table_names())
        barrier = Barrier(2)

        def claim(email):
            headers = self.jwt(email)
            barrier.wait(timeout=10)
            return self.client.post("/api/notifications/subscriptions", headers=headers, json=self.data).status_code

        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(claim, ["a@example.com", "b@example.com"])), [200, 409])
        with self.Session() as db:
            self.assertEqual(db.query(PushSubscription).count(), 1)
            self.assertIsNotNone(db.get(User, 1))


if __name__ == "__main__":
    unittest.main()