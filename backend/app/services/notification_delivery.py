import http.client
import ipaddress
import json
import logging
import os
import socket
import ssl
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

import requests
from pywebpush import WebPushException, webpush

from ..api.notifications import SubscriptionIn, insert_for
from ..models.notification import (
    NotificationDelivery, NotificationDispatch, NotificationEvent,
    NotificationPreference, PushSubscription,
)


class PublicHTTPSConnection(http.client.HTTPSConnection):
    def connect(self):
        addresses = socket.getaddrinfo(self.host, 443, type=socket.SOCK_STREAM)
        ips = [ipaddress.ip_address(a[4][0]) for a in addresses]
        if not ips or any(not ip.is_global or ip.is_multicast or ip.is_reserved for ip in ips):
            raise ValueError("Push host resolved to a non-public address")
        family, socktype, proto, _, address = addresses[0]
        sock = socket.socket(family, socktype, proto)
        try:
            sock.settimeout(self.timeout)
            sock.connect(address)
            self.sock = ssl.create_default_context().wrap_socket(sock, server_hostname=self.host)
        except Exception:
            sock.close()
            raise


class SafePushSession:
    def post(self, url, data=None, headers=None, timeout=None, **kwargs):
        SubscriptionIn.validate_endpoint(url)
        parts = urlsplit(url)
        connection = PublicHTTPSConnection(parts.hostname, 443, timeout=timeout or 10)
        try:
            path = parts.path or "/"
            if parts.query:
                path += "?" + parts.query
            connection.request("POST", path, body=data, headers=headers or {})
            result = connection.getresponse()
            response = requests.Response()
            response.status_code = result.status
            response._content = result.read(4096)
            response.headers.update(dict(result.getheaders()))
            return response
        finally:
            connection.close()


def enqueue_events(db, now):
    events = (db.query(NotificationEvent)
              .outerjoin(NotificationDispatch, NotificationDispatch.event_id == NotificationEvent.id)
              .filter(NotificationDispatch.event_id.is_(None))
              .order_by(NotificationEvent.id).with_for_update(skip_locked=True, of=NotificationEvent).limit(100).all())
    for event in events:
        inserted = db.execute(insert_for(db)(NotificationDispatch).values(event_id=event.id)
                              .on_conflict_do_nothing(index_elements=[NotificationDispatch.event_id])
                              .returning(NotificationDispatch.event_id)).scalar_one_or_none()
        if inserted is None:
            continue
        preference = db.get(NotificationPreference, event.user_id)
        if preference and preference.push_enabled:
            for subscription in db.query(PushSubscription).filter_by(user_id=event.user_id).all():
                db.add(NotificationDelivery(event_id=event.id, subscription_id=subscription.id, next_attempt_at=now))
    db.commit()


def deliver_due(db, now, private_key=None, subject=None):
    private_key = private_key or os.getenv("VAPID_PRIVATE_KEY")
    subject = subject or os.getenv("VAPID_SUBJECT")
    if not private_key or not subject:
        raise ValueError("VAPID_PRIVATE_KEY and VAPID_SUBJECT are required")
    for _ in range(100):
        delivery = (db.query(NotificationDelivery)
                    .filter(NotificationDelivery.delivered_at.is_(None), NotificationDelivery.next_attempt_at <= now)
                    .order_by(NotificationDelivery.id).with_for_update(skip_locked=True).first())
        if not delivery:
            db.rollback()
            break
        subscription = db.get(PushSubscription, delivery.subscription_id)
        event = db.get(NotificationEvent, delivery.event_id)
        preference = db.get(NotificationPreference, event.user_id) if event else None
        if not subscription or not event or not preference or not preference.push_enabled or subscription.user_id != event.user_id:
            db.delete(delivery)
            db.commit()
            continue
        status = None
        try:
            response = webpush(
                subscription_info={"endpoint": subscription.endpoint, "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth}},
                data=json.dumps({"event_id": event.id, "kind": event.kind, "workout_id": event.workout_id}),
                vapid_private_key=private_key, vapid_claims={"sub": subject},
                ttl=86400, timeout=10, requests_session=SafePushSession(),
            )
            status = response.status_code
        except WebPushException as exc:
            status = exc.response.status_code if exc.response is not None else None
        except Exception as exc:
            logging.warning("Push delivery failed (%s)", type(exc).__name__)
        if status in (404, 410):
            db.query(NotificationDelivery).filter_by(subscription_id=subscription.id).delete()
            db.delete(subscription)
        elif status is not None and 200 <= status < 300:
            delivery.delivered_at = now
        else:
            delivery.attempts += 1
            delivery.next_attempt_at = now + timedelta(seconds=min(3600, 60 * 2 ** min(delivery.attempts - 1, 6)))
        db.commit()


def process_deliveries(db, now):
    now = now.astimezone(timezone.utc).replace(tzinfo=None)
    enqueue_events(db, now)
    deliver_due(db, now)