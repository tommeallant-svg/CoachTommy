import logging
import time
from datetime import datetime, timezone

from .database import Base, SessionLocal, engine
from .models import notification, plan, user, workout
from .services.notification_schedule import schedule_reminders
from .services.notification_delivery import process_deliveries


def main():
    logging.basicConfig(level=logging.INFO)
    Base.metadata.create_all(bind=engine)
    while True:
        try:
            with SessionLocal() as db:
                schedule_reminders(db, datetime.now(timezone.utc))
                process_deliveries(db, datetime.now(timezone.utc))
        except Exception:
            logging.exception("Notification scheduling failed")
        time.sleep(60)


if __name__ == "__main__":
    main()