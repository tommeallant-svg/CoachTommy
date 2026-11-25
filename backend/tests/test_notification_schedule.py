import unittest
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.notification import NotificationEvent
from app.models.plan import Plan
from app.models.user import User
from app.models.workout import Workout
from app.services.notification_schedule import schedule_reminders


class NotificationScheduleTest(unittest.TestCase):
    def test_resume_across_days(self):
        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        with Session() as db:
            db.add(User(id=1, email="a@example.com", role="athlete"))
            db.add_all([Workout(id=1, athlete_id=1, date=datetime(2026, 3, 28, 10), is_validated=False),
                        Workout(id=2, athlete_id=1, date=datetime(2026, 3, 29, 10), is_validated=False)])
            db.commit()
            schedule_reminders(db, datetime(2026, 3, 28, 6, tzinfo=timezone.utc))
            schedule_reminders(db, datetime(2026, 3, 30, 7, tzinfo=timezone.utc))
            schedule_reminders(db, datetime(2026, 3, 30, 7, tzinfo=timezone.utc))
            self.assertEqual(db.query(NotificationEvent).count(), 4)
        engine.dispose()

    def test_paris_hours_dst_and_idempotence(self):
        for day, morning, evening in [(29, 6, 19), (25, 7, 20)]:
            month = 3 if day == 29 else 10
            engine = create_engine("sqlite://")
            Base.metadata.create_all(engine)
            Session = sessionmaker(bind=engine)
            with Session() as db:
                db.add(User(id=1, email="a@example.com", role="athlete"))
                db.add(Workout(id=1, athlete_id=1, date=datetime(2026, month, day, 10), is_validated=False))
                db.commit()
                schedule_reminders(db, datetime(2026, month, day, morning - 1, 59, tzinfo=timezone.utc))
                self.assertEqual(db.query(NotificationEvent).count(), 0)
                schedule_reminders(db, datetime(2026, month, day, morning, tzinfo=timezone.utc))
                schedule_reminders(db, datetime(2026, month, day, morning, tzinfo=timezone.utc))
                self.assertEqual(db.query(NotificationEvent).count(), 1)
                schedule_reminders(db, datetime(2026, month, day, evening, tzinfo=timezone.utc))
                self.assertEqual(db.query(NotificationEvent).count(), 2)
            engine.dispose()


if __name__ == "__main__":
    unittest.main()