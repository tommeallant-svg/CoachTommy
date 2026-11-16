from garminconnect.workout import (
    RunningWorkout, 
    CyclingWorkout, 
    WorkoutSegment, 
    PaceTarget, 
    CustomPowerTarget,
    create_warmup_step,
    create_interval_step,
    create_recovery_step,
    create_cooldown_step,
    create_repeat_group,
    create_targeted_interval_step,
    pace_to_mps,
    SportType
)
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
        all_steps = []
        global_step_order = 1
        total_duration_secs = 0
        
        for rep_group in (workout.scheme or []):
            repetitions = rep_group.get("repetitions", 1)
            intervals = rep_group.get("intervals", [])
            
            group_steps = []
            for interval in intervals:
                step_type_internal = interval.get("type")
                duration_min = interval.get("duration", 0)
                duration_secs = int(duration_min * 60)
                
                target = None
                if user.vma and interval.get("pace_vma_min"):
                    pace_min = GarminWorkoutService._calculate_pace(user.vma, interval.get("pace_vma_min"))
                    pace_max = GarminWorkoutService._calculate_pace(user.vma, interval.get("pace_vma_max", interval.get("pace_vma_min")))
                    
                    if pace_min and pace_max:
                        # On convertit les allures en m/s
                        m_min, s_min = int(pace_min), int(round((pace_min - int(pace_min)) * 60))
                        m_max, s_max = int(pace_max), int(round((pace_max - int(pace_max)) * 60))
                        mps_min = pace_to_mps(m_min, s_min, "km")
                        mps_max = pace_to_mps(m_max, s_max, "km")
                        # PaceTarget: lower_limit est la vitesse min (allure lente), upper_limit est la vitesse max (allure rapide)
                        target = PaceTarget(lower_limit=min(mps_min, mps_max), upper_limit=max(mps_min, mps_max))

                if step_type_internal == "Echauffement":
                    step = create_warmup_step(duration_seconds=float(duration_secs), step_order=global_step_order)
                elif step_type_internal in ["Lent", "Récup", "Récupération"]:
                    step = create_recovery_step(duration_seconds=float(duration_secs), step_order=global_step_order)
                elif step_type_internal == "Retour calme":
                    step = create_cooldown_step(duration_seconds=float(duration_secs), step_order=global_step_order)
                else:
                    if target:
                        step = create_targeted_interval_step(duration_seconds=float(duration_secs), step_order=global_step_order, target=target)
                    else:
                        step = create_interval_step(duration_seconds=float(duration_secs), step_order=global_step_order)
                
                group_steps.append(step)
                global_step_order += 1
                total_duration_secs += duration_secs * repetitions

            if repetitions > 1:
                # Créer un groupe de répétition
                group_start_order = global_step_order - len(group_steps)
                # On ajuste les ordres des étapes internes : le groupe prend l'ordre initial, 
                # les étapes commencent à l'ordre suivant
                for i, s in enumerate(group_steps):
                    s.stepOrder = group_start_order + i + 1
                
                repeat_group = create_repeat_group(
                    iterations=repetitions, 
                    workout_steps=group_steps, 
                    step_order=group_start_order
                )
                all_steps.append(repeat_group)
                # Le global_step_order doit maintenant pointer après le dernier élément du groupe
                global_step_order = group_start_order + len(group_steps) + 1
            else:
                all_steps.extend(group_steps)

        segment = WorkoutSegment(
            segmentOrder=1,
            sportType={
                "sportTypeId": SportType.RUNNING,
                "sportTypeKey": "running",
                "displayOrder": 1,
            },
            workoutSteps=all_steps
        )
        
        return RunningWorkout(
            workoutName=workout.name,
            description=workout.description or "",
            estimatedDurationInSecs=total_duration_secs,
            workoutSegments=[segment]
        )

    @staticmethod
    def _create_cycling_workout(workout: Workout, user: User):
        all_steps = []
        global_step_order = 1
        total_duration_secs = 0
        
        for rep_group in (workout.scheme or []):
            repetitions = rep_group.get("repetitions", 1)
            intervals = rep_group.get("intervals", [])
            
            group_steps = []
            for interval in intervals:
                step_type_internal = interval.get("type")
                duration_min = interval.get("duration", 0)
                duration_secs = int(duration_min * 60)
                
                target = None
                if user.ftp and interval.get("power_ftp_min"):
                    target_value_low = int(user.ftp * (interval.get("power_ftp_min") / 100))
                    target_value_high = int(user.ftp * (interval.get("power_ftp_max", interval.get("power_ftp_min")) / 100))
                    target = CustomPowerTarget(lower_limit=float(target_value_low), upper_limit=float(target_value_high))
                
                if step_type_internal == "Echauffement":
                    step = create_warmup_step(duration_seconds=float(duration_secs), step_order=global_step_order)
                elif step_type_internal in ["Lent", "Récup", "Récupération"]:
                    step = create_recovery_step(duration_seconds=float(duration_secs), step_order=global_step_order)
                elif step_type_internal == "Retour calme":
                    step = create_cooldown_step(duration_seconds=float(duration_secs), step_order=global_step_order)
                else:
                    if target:
                        step = create_targeted_interval_step(duration_seconds=float(duration_secs), step_order=global_step_order, target=target)
                    else:
                        step = create_interval_step(duration_seconds=float(duration_secs), step_order=global_step_order)
                
                group_steps.append(step)
                global_step_order += 1
                total_duration_secs += duration_secs * repetitions

            if repetitions > 1:
                group_start_order = global_step_order - len(group_steps)
                for i, s in enumerate(group_steps):
                    s.stepOrder = group_start_order + i + 1
                
                repeat_group = create_repeat_group(
                    iterations=repetitions, 
                    workout_steps=group_steps, 
                    step_order=group_start_order
                )
                all_steps.append(repeat_group)
                global_step_order = group_start_order + len(group_steps) + 1
            else:
                all_steps.extend(group_steps)

        segment = WorkoutSegment(
            segmentOrder=1,
            sportType={
                "sportTypeId": SportType.CYCLING,
                "sportTypeKey": "cycling",
                "displayOrder": 2,
            },
            workoutSteps=all_steps
        )
        
        return CyclingWorkout(
            workoutName=workout.name,
            description=workout.description or "",
            estimatedDurationInSecs=total_duration_secs,
            workoutSegments=[segment]
        )

    @staticmethod
    def _calculate_pace(vma, percentage):
        """Calcule l'allure en min/km pour un % de VMA."""
        if not vma or not percentage:
            return None
        speed_kmh = vma * (percentage / 100)
        pace_min_per_km = 60 / speed_kmh
        return pace_min_per_km
