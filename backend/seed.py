import os
import json
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base, SQLALCHEMY_DATABASE_URL
from app.models.workout import Workout
from app.models.user import User
from app.models.plan import Plan
from app.models.catalog import CatalogWorkout
from app.auth import get_password_hash

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def seed():
    # Create tables
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    # Clean existing data
    db.query(Workout).delete()
    db.query(Plan).delete()
    db.query(User).delete()
    db.query(CatalogWorkout).delete()

    # Create users
    coach = User(
        email="tom.meallant@gmail.com",
        hashed_password=get_password_hash("ToML2Bégé"),
        role="coach"
    )
    athlete = User(
        email="paloma.mouyade@gmail.com",
        hashed_password=get_password_hash("Pal0LaPl0uBéL"),
        role="athlete"
    )
    db.add(coach)
    db.add(athlete)
    db.commit()
    db.refresh(coach)
    db.refresh(athlete)
    
    # Create default catalog workouts
    catalog_workouts = [
        {
            "name": "VMA Courte 30/30",
            "workout_type": "VO2 Max",
            "category": "Fractionné",
            "description": "Séance de VMA courte pour développer la puissance aérobie. Alternance de 30 secondes d'effort intense et 30 secondes de récupération active.",
            "perceived_difficulty": 8,
            "scheme": [
                {
                    "repetitions": 1,
                    "intervals": [{"type": "Echauffement", "duration": 15, "pace_vma_min": 65, "pace_vma_max": 65}]
                },
                {
                    "repetitions": 10,
                    "intervals": [
                        {"type": "Vite", "duration": 0.5, "pace_vma_min": 105, "pace_vma_max": 105},
                        {"type": "Lent", "duration": 0.5, "pace_vma_min": 60, "pace_vma_max": 60}
                    ]
                },
                {
                    "repetitions": 1,
                    "intervals": [{"type": "Retour calme", "duration": 10, "pace_vma_min": 65, "pace_vma_max": 65}]
                }
            ]
        },
        {
            "name": "VMA Longue 1000m",
            "workout_type": "Seuil",
            "category": "Fractionné",
            "description": "Travail au seuil anaérobie sur des répétitions de 1000m. Idéal pour améliorer sa vitesse de croisière sur 10km ou semi-marathon.",
            "perceived_difficulty": 7,
            "scheme": [
                {
                    "repetitions": 1,
                    "intervals": [{"type": "Echauffement", "duration": 20, "pace_vma_min": 65, "pace_vma_max": 65}]
                },
                {
                    "repetitions": 5,
                    "intervals": [
                        {"type": "Fraction", "duration": 4, "pace_vma_min": 90, "pace_vma_max": 90},
                        {"type": "Récup", "duration": 2, "pace_vma_min": 60, "pace_vma_max": 60}
                    ]
                },
                {
                    "repetitions": 1,
                    "intervals": [{"type": "Retour calme", "duration": 10, "pace_vma_min": 65, "pace_vma_max": 65}]
                }
            ]
        }
    ]
    for cw_data in catalog_workouts:
        cw = CatalogWorkout(**cw_data)
        db.add(cw)
    db.commit()
    print("Database seeded (users and catalog only)!")

if __name__ == "__main__":
    seed()
