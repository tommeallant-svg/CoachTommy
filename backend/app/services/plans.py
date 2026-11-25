from datetime import timedelta

from fastapi import HTTPException, status

from ..models.catalog import CatalogWorkout
from ..models.plan import Plan
from ..models.user import User
from ..models.workout import Workout
from ..schemas.plan import PlanWeeklyStats
from ..services.plan_generator import PlanGenerator
from ..services.workout_volumes import calculate_volumes


def get_owned_plan(db, plan_id, athlete_id):
    plan = db.query(Plan).filter(Plan.id == plan_id, Plan.athlete_id == athlete_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan non trouvé")
    return plan


def weekly_stats(db, plan):
    start = plan.start_date.date()
    end = plan.race_date.date()
    workouts = db.query(Workout).filter(
        Workout.plan_id == plan.id, Workout.athlete_id == plan.athlete_id,
        Workout.date.isnot(None),
    ).all()
    if workouts:
        start = min(start, min(workout.date.date() for workout in workouts))
        end = max(end, max(workout.date.date() for workout in workouts))
    weeks = []
    week_start = start - timedelta(days=start.weekday())
    while week_start <= end:
        weeks.append(PlanWeeklyStats(week_start=week_start, week_end=week_start + timedelta(days=6)))
        week_start += timedelta(days=7)
    for workout in workouts:
        week = weeks[(workout.date.date() - weeks[0].week_start).days // 7]
        week.workout_count += 1
        week.validated_count += int(bool(workout.is_validated))
        week.duration_minutes += workout.duration_minutes or 0
        week.distance_km += workout.distance_km or 0
        week.estimated_load += workout.estimated_load or 0
    return weeks


def create_plan(db, plan_in, athlete_id):
    if db.query(Plan).filter(Plan.athlete_id == athlete_id, Plan.is_archived == False).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Un plan actif existe déjà pour cet athlète.")
    plan_data = plan_in.model_dump()
    plan_data.pop("athlete_id", None)
    db_plan = Plan(**plan_data, athlete_id=athlete_id)
    db.add(db_plan)
    try:
        catalog = db.query(CatalogWorkout).all()
        workouts = PlanGenerator(db, db_plan, catalog).generate()
        db.flush()
        for workout in workouts:
            workout.plan_id = db_plan.id
            if workout.scheme:
                workout.duration_minutes, workout.distance_km = calculate_volumes(workout.scheme)
                workout.estimated_load = workout.duration_minutes * (1 + workout.difficulty_level / 5)
            db.add(workout)
        athlete = db.query(User).filter(User.id == athlete_id).one()
        if plan_in.estimated_vma is not None:
            athlete.vma = 60 / plan_in.estimated_vma
        db.commit()
        db.refresh(db_plan)
        return db_plan
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erreur lors de la génération du plan : {str(e)}")


def archive_plan(db, plan, cancellation_comment):
    plan.is_archived = True
    plan.cancellation_comment = cancellation_comment
    db.commit()
    db.refresh(plan)
    return plan


def delete_plan(db, plan):
    db.delete(plan)
    db.commit()