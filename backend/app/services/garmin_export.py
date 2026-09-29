# backend/app/services/garmin_export.py
"""
Génération de fichiers FIT "Workout" pour Garmin.

Utilise fit_tool, la librairie officielle open-source de Garmin :
  https://github.com/garmin/fittool-python
  pip install fit-tool

Le fichier généré s'importe dans Garmin Connect (navigateur web) :
  Training → Entraînements (Workouts) → Importer
"""

import os
import tempfile
from datetime import datetime

from fit_tool.fit_file_builder import FitFileBuilder
from fit_tool.profile.messages.file_id_message import FileIdMessage
from fit_tool.profile.messages.workout_message import WorkoutMessage
from fit_tool.profile.messages.workout_step_message import WorkoutStepMessage
from fit_tool.profile.profile_type import (
    FileType,
    Intensity,
    Manufacturer,
    Sport,
    WorkoutStepDuration,
    WorkoutStepTarget,
)


def pace_str_to_speed_ms(pace):
    """
    Convertit une allure 'M:SS' (min/km) en vitesse m/s.
    Retourne None si l'allure est absente ou invalide.
    """
    if not pace or not isinstance(pace, str):
        return None
    try:
        parts = pace.strip().split(":")
        minutes = int(parts[0])
        seconds = int(parts[1]) if len(parts) > 1 else 0
        total_seconds = minutes * 60 + seconds
        if total_seconds <= 0:
            return None
        return 1000.0 / total_seconds
    except (ValueError, IndexError):
        return None


def intensity_for_interval(interval_type):
    """Mappe le type d'intervalle vers l'intensité FIT."""
    t = (interval_type or "").lower()
    if "chauff" in t:
        return Intensity.WARMUP
    if "retour" in t or "calme" in t:
        return Intensity.COOLDOWN
    if "récup" in t or "recup" in t or "lent" in t or "repos" in t:
        return Intensity.REST
    return Intensity.ACTIVE


def _build_step(idx, interval, repetition_tag=""):
    """Construit une étape FIT (WorkoutStepMessage) à partir d'un intervalle du schéma."""
    step = WorkoutStepMessage()
    step.message_index = idx

    name = interval.get("type", "Intervalle")
    if repetition_tag:
        name = f"{name} ({repetition_tag})"
    step.workout_step_name = name[:40]  # Limite conseillée pour l'affichage Garmin
    step.intensity = intensity_for_interval(interval.get("type"))

    # --- Durée de l'étape : distance prioritaire, sinon temps, sinon ouverte ---
    if interval.get("distance"):
        step.duration_type = WorkoutStepDuration.DISTANCE
        step.duration_distance = float(interval["distance"]) * 1000.0  # km -> mètres
    elif interval.get("duration"):
        step.duration_type = WorkoutStepDuration.TIME
        step.duration_time = float(interval["duration"]) * 60.0  # minutes -> secondes
    else:
        step.duration_type = WorkoutStepDuration.OPEN
        step.duration_value = 0

    # --- Cible d'allure : pace_min / pace_max (min/km) -> vitesse (m/s) ---
    speed_low = pace_str_to_speed_ms(interval.get("pace_min"))
    speed_high = pace_str_to_speed_ms(interval.get("pace_max"))
    if speed_low is None and speed_high is None:
        step.target_type = WorkoutStepTarget.OPEN
        step.target_value = 0
    else:
        speeds = [s for s in (speed_low, speed_high) if s is not None]
        step.target_type = WorkoutStepTarget.SPEED
        step.target_speed_low = min(speeds)   # allure la plus lente
        step.target_speed_high = max(speeds)  # allure la plus rapide

    return step


def generate_workout_fit(workout):
    """
    Génère les bytes d'un fichier FIT Workout à partir d'un modèle Workout SQLAlchemy.

    Le schéma est déplié : un bloc avec `repetitions: N` produit N x ses intervalles
    (plus robuste à l'import que les repeat-groups FIT natifs).
    """
    builder = FitFileBuilder(auto_define=True, min_string_size=50)

    file_id_message = FileIdMessage()
    file_id_message.type = FileType.WORKOUT
    file_id_message.manufacturer = Manufacturer.DEVELOPMENT.value
    file_id_message.product = 0
    file_id_message.time_created = round(datetime.utcnow().timestamp() * 1000)
    file_id_message.serial_number = 0x1A2B3C4D
    builder.add(file_id_message)

    steps = []
    for block in (workout.scheme or []):
        if not isinstance(block, dict):
            continue
        repetitions = int(block.get("repetitions", 1) or 1)
        intervals = block.get("intervals", [])
        for rep in range(1, repetitions + 1):
            tag = f"x{repetitions} #{rep}" if repetitions > 1 else ""
            for interval in intervals:
                steps.append(_build_step(len(steps), interval, tag))

    # Fallback : séance sans schéma -> une seule étape de la durée totale
    if not steps:
        steps.append(_build_step(0, {
            "type": workout.workout_type or "Séance",
            "duration": workout.duration_minutes,
        }))

    workout_message = WorkoutMessage()
    workout_message.workout_name = (workout.name or "Séance")[:40]
    workout_message.sport = Sport.RUNNING
    workout_message.num_valid_steps = len(steps)
    builder.add(workout_message)
    builder.add_all(steps)

    fit_file = builder.build()

    # to_file() est l'API documentée : on passe par un fichier temporaire
    fd, tmp_path = tempfile.mkstemp(suffix=".fit")
    try:
        fit_file.to_file(tmp_path)
        with open(tmp_path, "rb") as f:
            data = f.read()
    finally:
        os.close(fd)
        os.remove(tmp_path)

    return data
