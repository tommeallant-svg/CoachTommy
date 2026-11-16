from garminconnect import RunningWorkout, CyclingWorkout
from ..models.workout import Workout
from ..models.user import User
import math

class GarminWorkoutService:
    """
    Service pour transformer les workouts de l'application en format Garmin.
    Utilise les classes RunningWorkout et CyclingWorkout de la librairie garminconnect.
    """

    @staticmethod
    def transform_to_garmin(workout: Workout, user: User):
        """
        Transforme un objet Workout en un objet GarminWorkout (RunningWorkout ou CyclingWorkout).
        """
        sport = workout.sport or "running"
        
        if sport == "running":
            return GarminWorkoutService._create_running_workout(workout, user)
        elif sport == "cycling":
            return GarminWorkoutService._create_cycling_workout(workout, user)
        else:
            raise ValueError(f"Sport '{sport}' non support pour la synchronisation Garmin.")

    @staticmethod
    def _create_running_workout(workout: Workout, user: User):
        garmin_workout = RunningWorkout(
            name=workout.name,
            description=workout.description
        )
        
        for rep_idx, rep_group in enumerate(workout.scheme or []):
            repetitions = rep_group.get("repetitions", 1)
            intervals = rep_group.get("intervals", [])
            
            for _ in range(repetitions):
                for interval in intervals:
                    step_type = GarminWorkoutService._map_step_type(interval.get("type"))
                    duration_min = interval.get("duration", 0)
                    
                    # Cible basée sur la VMA
                    target_type = None
                    target_value_low = None
                    target_value_high = None
                    
                    if user.vma and interval.get("pace_vma_min"):
                        target_type = "pace.zone"
                        # Calcul du rythme (min/km)
                        pace_min = GarminWorkoutService._calculate_pace(user.vma, interval.get("pace_vma_min"))
                        pace_max = GarminWorkoutService._calculate_pace(user.vma, interval.get("pace_vma_max", interval.get("pace_vma_min")))
                        
                        target_value_low = pace_min
                        target_value_high = pace_max

                    garmin_workout.add_step(
                        step_type=step_type,
                        duration=f"{int(duration_min * 60)}s",
                        target_type=target_type,
                        target_value_low=target_value_low,
                        target_value_high=target_value_high
                    )
        
        return garmin_workout

    @staticmethod
    def _create_cycling_workout(workout: Workout, user: User):
        garmin_workout = CyclingWorkout(
            name=workout.name,
            description=workout.description
        )
        
        for rep_group in (workout.scheme or []):
            repetitions = rep_group.get("repetitions", 1)
            intervals = rep_group.get("intervals", [])
            
            for _ in range(repetitions):
                for interval in intervals:
                    step_type = GarminWorkoutService._map_step_type(interval.get("type"))
                    duration_min = interval.get("duration", 0)
                    
                    target_type = None
                    target_value_low = None
                    target_value_high = None
                    
                    if user.ftp and interval.get("power_ftp_min"):
                        target_type = "power.zone"
                        target_value_low = int(user.ftp * (interval.get("power_ftp_min") / 100))
                        target_value_high = int(user.ftp * (interval.get("power_ftp_max", interval.get("power_ftp_min")) / 100))
                    
                    garmin_workout.add_step(
                        step_type=step_type,
                        duration=f"{int(duration_min * 60)}s",
                        target_type=target_type,
                        target_value_low=target_value_low,
                        target_value_high=target_value_high
                    )
                    
        return garmin_workout

    @staticmethod
    def _map_step_type(internal_type):
        mapping = {
            "Echauffement": "warmup",
            "Vite": "interval",
            "Fraction": "interval",
            "Lent": "recovery",
            "Récup": "recovery",
            "Récupération": "recovery",
            "Retour calme": "cooldown",
            "Sweet Spot": "interval",
        }
        return mapping.get(internal_type, "interval")

    @staticmethod
    def _calculate_pace(vma, percentage):
        """Calcule l'allure en min/km pour un % de VMA."""
        if not vma or not percentage:
            return None
        speed_kmh = vma * (percentage / 100)
        pace_min_per_km = 60 / speed_kmh
        return pace_min_per_km
