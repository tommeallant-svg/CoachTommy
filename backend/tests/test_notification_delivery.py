import base64
import socket
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

import requests

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.notification import NotificationDelivery, NotificationEvent, NotificationPreference, PushSubscription
from app.models.plan import Plan
from app.models.user import User
from app.models.workout import Workout
from app.services.notification_delivery import PublicHTTPSConnection, SafePushSession, deliver_due, enqueue_events


def b64(value):
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def response(status):
    result = requests.Response()
    result.status_code = status
    result._content = b""
    return result


class DeliveryTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        receiver = ec.generate_private_key(ec.SECP256R1()).public_key().public_bytes(
            serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
        self.private_key = b64(ec.generate_private_key(ec.SECP256R1()).private_numbers().private_value.to_bytes(32, "big"))
        self.now = datetime(2026, 1, 1)
        self.db.add(User(id=1, email="a@example.com", role="athlete"))
        self.db.add(Workout(id=1, athlete_id=1, date=self.now))
        self.db.add(NotificationEvent(id=1, event_key="event:1", user_id=1, kind="morning_reminder", workout_id=1))
        self.db.add(NotificationPreference(user_id=1, push_enabled=True))
        self.db.add(PushSubscription(id=1, user_id=1, endpoint_hash="hash", endpoint="https://fcm.googleapis.com/send/token",
                                     p256dh=b64(receiver), auth=b64(b"a" * 16)))
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def deliver(self, now):
        deliver_due(self.db, now, self.private_key, "mailto:test@example.com")

    def test_encrypted_delivery_retry_and_idempotence(self):
        enqueue_events(self.db, self.now)
        enqueue_events(self.db, self.now)
        self.assertEqual(self.db.query(NotificationDelivery).count(), 1)
        with patch.object(SafePushSession, "post", side_effect=[response(503), response(201)]) as post:
            self.deliver(self.now)
            row = self.db.query(NotificationDelivery).one()
            self.assertEqual(row.attempts, 1)
            self.assertEqual(row.next_attempt_at, self.now + timedelta(seconds=60))
            self.deliver(self.now)
            self.assertEqual(post.call_count, 1)
            self.deliver(self.now + timedelta(seconds=60))
            self.assertIsNotNone(row.delivered_at)
            self.assertEqual(post.call_count, 2)
            self.assertNotIn(b"morning_reminder", post.call_args.kwargs["data"])
            self.deliver(self.now + timedelta(days=1))
            self.assertEqual(post.call_count, 2)

    def test_expired_subscription_removed(self):
        enqueue_events(self.db, self.now)
        with patch.object(SafePushSession, "post", return_value=response(410)):
            self.deliver(self.now)
        self.assertEqual(self.db.query(PushSubscription).count(), 0)
        self.assertEqual(self.db.query(NotificationDelivery).count(), 0)

    def test_disabled_preference_prevents_delivery(self):
        enqueue_events(self.db, self.now)
        self.db.get(NotificationPreference, 1).push_enabled = False
        self.db.commit()
        with patch("app.services.notification_delivery.webpush") as send:
            self.deliver(self.now)
            send.assert_not_called()
        self.assertEqual(self.db.query(NotificationDelivery).count(), 0)

    def test_private_or_mixed_dns_rejected_before_connection(self):
        for addresses in [["127.0.0.1"], ["8.8.8.8", "10.0.0.1"], ["::1"], ["224.0.0.1"]]:
            results = [(socket.AF_INET6 if ":" in ip else socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 443)) for ip in addresses]
            with patch("socket.getaddrinfo", return_value=results), patch("socket.socket") as sock:
                with self.assertRaises(ValueError):
                    PublicHTTPSConnection("fcm.googleapis.com", timeout=1).connect()
                sock.assert_not_called()

    def test_bad_endpoint_rejected_without_connection(self):
        with patch("app.services.notification_delivery.PublicHTTPSConnection") as connection:
            with self.assertRaises(ValueError):
                SafePushSession().post("https://fcm.googleapis.com@127.0.0.1/")
            connection.assert_not_called()

    def test_connection_pins_public_ip_and_tls_hostname(self):
        address = (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443))
        with patch("socket.getaddrinfo", return_value=[address]), patch("socket.socket") as sock, \
                patch("ssl.create_default_context") as context:
            connection = PublicHTTPSConnection("fcm.googleapis.com", timeout=10)
            connection.connect()
            sock.return_value.connect.assert_called_once_with(("8.8.8.8", 443))
            context.return_value.wrap_socket.assert_called_once_with(sock.return_value, server_hostname="fcm.googleapis.com")

    def test_redirect_is_not_followed(self):
        with patch("app.services.notification_delivery.PublicHTTPSConnection") as connection:
            result = connection.return_value.getresponse.return_value
            result.status = 302
            result.read.return_value = b""
            result.getheaders.return_value = [("Location", "http://127.0.0.1/")]
            self.assertEqual(SafePushSession().post("https://fcm.googleapis.com/send/token").status_code, 302)
            connection.assert_called_once()