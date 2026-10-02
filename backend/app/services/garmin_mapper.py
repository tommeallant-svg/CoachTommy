from typing import Any
from app.models.workout import Workout


SPORT_MAPPING = {
    "running": "running",
    "trail": "running",
    "marathon": "running",
    "cycling": "cycling",
    "bike": "cycling",
    "swimming": "swimming",
}


class GarminMapper:

    @staticmethod
    def workout_to_garmin(workout: Workout) -> dict[str, Any]:

        sport = SPORT_MAPPING.get(
            workout.workout_type,
            "running"
        )

        garmin_workout = {
            "workoutName": workout.name,
            "description": workout.description or "",
            "sportType": {
                "sportTypeKey": sport
            },
            "estimatedDurationInSecs": (
                workout.duration_minutes * 60
                if workout.duration_minutes
                else 0
            ),
            "workoutSegments": []
        }

        order = 1

        for block in workout.scheme or []:

            segment = GarminMapper._map_block(
                block=block,
                order=order
            )

            garmin_workout["workoutSegments"].append(segment)

            order += 1

        return garmin_workout

    @staticmethod
    def _map_block(
        block: dict,
        order: int
    ) -> dict:

        repetitions = block.get(
            "repetitions",
            1
        )

        intervals = block.get(
            "intervals",
            []
        )

        steps = []

        step_order = 1

        for interval in intervals:

            step = GarminMapper._map_interval(
                interval=interval,
                step_order=step_order
            )

            steps.append(step)

            step_order += 1

        return {
            "segmentOrder": order,
            "sportType": {
                "sportTypeKey": "running"
            },
            "workoutSteps": steps,
            "repeatCount": repetitions
        }

    @staticmethod
    def _map_interval(
        interval: dict,
        step_order: int
    ) -> dict:

        duration = interval.get(
            "duration",
            1
        )

        interval_type = interval.get(
            "type",
            "Interval"
        )

        step = {
            "stepOrder": step_order,
            "stepType": GarminMapper._step_type(
                interval_type
            ),
            "description": interval_type,
            "durationType": "TIME",
            "durationValue": duration * 60,
        }

        target = GarminMapper._build_target(
            interval
        )

        if target:
            step["targetType"] = target["type"]
            step["targetValueOne"] = target["from"]
            step["targetValueTwo"] = target["to"]

        return step

    @staticmethod
    def _step_type(interval_type: str) -> str:

        interval_type = interval_type.lower()

        if "échauffement" in interval_type:
            return "WARMUP"

        if "warm" in interval_type:
            return "WARMUP"

        if "retour" in interval_type:
            return "COOLDOWN"

        if "cool" in interval_type:
            return "COOLDOWN"

        if "recup" in interval_type:
            return "RECOVERY"

        if "recovery" in interval_type:
            return "RECOVERY"

        return "INTERVAL"

    @staticmethod
    def _build_target(
        interval: dict
    ) -> dict | None:

        if (
            "pace_vma_min" in interval
            and
            "pace_vma_max" in interval
        ):
            return {
                "type": "PACE",
                "from": interval["pace_vma_min"],
                "to": interval["pace_vma_max"],
            }

        if (
            "hr_min" in interval
            and
            "hr_max" in interval
        ):
            return {
                "type": "HEART_RATE",
                "from": interval["hr_min"],
                "to": interval["hr_max"],
            }

        if (
            "power_min" in interval
            and
            "power_max" in interval
        ):
            return {
                "type": "POWER",
                "from": interval["power_min"],
                "to": interval["power_max"],
            }

        return None