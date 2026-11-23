from copy import deepcopy

from fastapi import HTTPException
from sqlalchemy import func, or_

from ..models.plan import Plan
from ..models.workout import Workout
from .workout_volumes import calculate_volumes


def calculate_load(duration_minutes, difficulty_level):
    return duration_minutes + duration_minutes * difficulty_level / 5


def workout_volumes(scheme):
    try:
        return calculate_volumes(scheme)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


def list_workouts(db, athlete_id, skip, limit, include_archived, date_from, date_to):
    if date_from and date_to and date_from > date_to:
        raise HTTPException(status_code=422, detail="Invalid date range")
    query = db.query(Workout).join(Plan, Workout.plan_id == Plan.id, isouter=True).filter(
        Workout.athlete_id == athlete_id)
    if not include_archived:
        query = query.filter(or_(Plan.id == None, Plan.is_archived == False,
                                 Workout.is_validated == True,
                                 (Plan.is_archived == True) & (Workout.date < func.now())))
    if date_from:
        query = query.filter(Workout.date >= date_from)
    if date_to:
        query = query.filter(Workout.date < date_to)
    return query.order_by(Workout.date.asc(), Workout.id.asc()).offset(skip).limit(limit).all()


def create_workout(db, data, athlete_id):
    workout = Workout(**{**data, "athlete_id": athlete_id})
    if workout.scheme:
        workout.duration_minutes, workout.distance_km = workout_volumes(workout.scheme)
    workout.estimated_load = calculate_load(workout.duration_minutes, workout.difficulty_level)
    db.add(workout)
    db.commit()
    db.refresh(workout)
    return workout


def update_workout(db, workout, data):
    old_scheme = workout.scheme or []
    if (len(old_scheme) == 1 and isinstance(old_scheme[0], dict)
            and len(old_scheme[0].get("intervals", [])) == 1
            and isinstance(old_scheme[0]["intervals"][0], dict)):
        interval = old_scheme[0]["intervals"][0]
        distance = workout.distance_km
        if interval.get("type") == "Course" and workout.plan:
            distance = workout.plan.race_distance
        if interval.get("type") in ("Course à pied", "Course") and distance and interval.get("distance") == distance:
            scheme = deepcopy(data.get("scheme", old_scheme))
            if scheme == old_scheme:
                scheme[0]["intervals"][0]["distance"] *= 1000
                data["scheme"] = scheme
    for key, value in data.items():
        setattr(workout, key, value)
    if workout.scheme and any(key in data for key in ("scheme", "duration_minutes", "distance_km")):
        workout.duration_minutes, workout.distance_km = workout_volumes(workout.scheme)
    if any(key in data for key in ("scheme", "duration_minutes", "distance_km", "difficulty_level")):
        workout.estimated_load = calculate_load(workout.duration_minutes, workout.difficulty_level)
    db.commit()
    db.refresh(workout)
    return workout