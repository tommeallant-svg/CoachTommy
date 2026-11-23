import time
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from .database import engine, Base
from .api import workouts, auth, plans, catalog, coach, garmin, strava, community
from .models import user, workout, plan, catalog as catalog_model, community as community_model
from .strava_migration import migrate_strava
from .auth import jwt_secret_key

jwt_secret_key()

# Create tables with retry logic
for i in range(5):
    try:
        Base.metadata.create_all(bind=engine)
        migrate_strava(engine)
        # Migration: Add garmin_workout_id to workouts table if it doesn't exist
        with engine.connect() as conn:
            try:
                conn.execute(text("ALTER TABLE workouts ADD COLUMN garmin_workout_id VARCHAR"))
                conn.commit()
            except Exception:
                # The column probably already exists
                pass
        break
    except Exception as e:
        print(f"Waiting for database... ({i+1}/5) - Error: {e}")
        time.sleep(2)

app = FastAPI(title="Application Entrainement API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(workouts.router, prefix="/api")
app.include_router(plans.router, prefix="/api")
app.include_router(catalog.router, prefix="/api")
app.include_router(coach.router, prefix="/api")
app.include_router(garmin.router, prefix="/api")
app.include_router(strava.router, prefix="/api")
app.include_router(community.router, prefix="/api")

@app.get("/")
def read_root():
    return {"message": "Welcome to Application Entrainement API"}
