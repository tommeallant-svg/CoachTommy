from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from ..api.notifications import insert_for
from ..models.notification import NotificationEvent, NotificationScheduleCursor
from ..models.workout import Workout


PARIS = ZoneInfo("Europe/Paris")


def schedule_reminders(db, now):
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("An aware datetime is required")
    now = now.astimezone(timezone.utc)
    local = now.astimezone(PARIS)
    initial = datetime.combine(local.date(), time.min, PARIS).astimezone(timezone.utc) - timedelta(microseconds=1)
    statement = insert_for(db)(NotificationScheduleCursor).values(
        name="reminders", processed_at=initial.replace(tzinfo=None)
    ).on_conflict_do_nothing(index_elements=[NotificationScheduleCursor.name])
    db.execute(statement)
    cursor = db.query(NotificationScheduleCursor).filter_by(name="reminders").with_for_update().first()
    previous = cursor.processed_at.replace(tzinfo=timezone.utc)
    if now < previous:
        db.rollback()
        return
    day = previous.astimezone(PARIS).date()
    while day <= local.date():
        start = datetime.combine(day, time.min)
        workouts = db.query(Workout).filter(
            Workout.date >= start, Workout.date < start + timedelta(days=1),
            Workout.athlete_id.is_not(None), Workout.is_validated.is_not(True),
        ).all()
        for hour, kind in ((8, "morning_reminder"), (21, "evening_reminder")):
            due = datetime.combine(day, time(hour), PARIS).astimezone(timezone.utc)
            if due > now or due <= previous:
                continue
            for workout in workouts:
                statement = insert_for(db)(NotificationEvent).values(
                    event_key=f"{kind}:{workout.id}:{day.isoformat()}",
                    user_id=workout.athlete_id, kind=kind, workout_id=workout.id,
                ).on_conflict_do_nothing(index_elements=[NotificationEvent.event_key])
                db.execute(statement)
        day += timedelta(days=1)
    cursor.processed_at = now.replace(tzinfo=None)
    db.commit()