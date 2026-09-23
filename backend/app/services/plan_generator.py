from datetime import datetime, timedelta
from typing import List, Dict, Any
import math

# Attribution par défaut des séances
# 0=Lundi, 1=Mardi, 2=Mercredi, 3=Jeudi, 4=Vendredi, 5=Samedi, 6=Dimanche
DEFAULT_ASSIGNMENTS = {
    "plaisir": {
        1: {2: "Libre"},
        2: {2: "Endurance", 5: "Libre"},
        3: {1: "Endurance", 3: "Libre", 5: "Sortie longue"},
        4: {1: "Libre", 3: "Endurance", 5: "Libre", 6: "Sortie longue"},
        5: {0: "Endurance", 1: "Libre", 3: "Endurance", 5: "Libre", 6: "Sortie longue"},
        6: {1: "Libre", 2: "Endurance", 3: "Libre", 4: "Endurance", 5: "Libre", 6: "Sortie longue"},
        7: {0: "Endurance", 1: "Libre", 2: "Endurance", 3: "Libre", 4: "Endurance", 5: "Libre", 6: "Sortie longue"},
    },
    "maintien": {
        1: {2: "Endurance"},
        2: {2: "Endurance", 5: ("Libre", "Fractionné")},
        3: {1: "Endurance", 3: ("Libre", "Fractionné"), 5: ("Libre", "Sortie longue")},
        4: {1: "Endurance", 3: "Fractionné", 5: "Endurance", 6: ("Libre", "Sortie longue")},
        5: {0: "Endurance", 1: "Fractionné", 3: "Endurance", 5: "Libre", 6: "Sortie longue"},
        6: {1: "Endurance", 2: "Fractionné", 3: "Endurance", 4: "Libre", 5: "Endurance", 6: "Sortie longue"},
        7: {0: "Endurance", 1: "Fractionné", 2: "Endurance", 3: ("Libre", "Fractionné"), 4: "Endurance", 5: "Libre", 6: "Sortie longue"},
    },
    "mixte": {
        1: {2: "Endurance"},
        2: {2: "Endurance", 5: "Fractionné"},
        3: {1: "Endurance", 3: "Fractionné", 5: "Sortie longue"},
        4: {1: "Endurance", 3: "Fractionné", 5: "Endurance", 6: "Sortie longue"},
        5: {0: "Endurance", 1: "Fractionné", 3: "Endurance", 5: "Fractionné", 6: "Sortie longue"},
        6: {1: "Endurance", 2: "Fractionné", 3: "Endurance", 4: "Fractionné", 5: "Endurance", 6: "Sortie longue"},
        7: {0: "Endurance", 1: "Fractionné", 2: "Endurance", 3: "Fractionné", 4: "Endurance", 5: "Libre", 6: "Sortie longue"},
    },
    "intensité": {
        1: {2: "Fractionné"},
        2: {2: "Endurance", 5: "Fractionné"},
        3: {1: "Endurance", 3: "Fractionné", 5: "Sortie longue"},
        4: {1: "Fractionné", 3: "Endurance", 5: "Fractionné", 6: "Sortie longue"},
        5: {0: "Fractionné", 1: "Endurance", 3: "Fractionné", 5: "Libre", 6: "Sortie longue"},
        6: {1: "Fractionné", 2: "Endurance", 3: "Fractionné", 4: "Endurance", 5: "Libre", 6: "Sortie longue"},
        7: {0: "Endurance", 1: "Fractionné", 2: "Endurance", 3: "Fractionné", 4: "Endurance", 5: "Fractionné", 6: "Sortie longue"},
    },
    "trail": {
        1: {2: "Endurance"},
        2: {2: "Endurance", 5: "Trail"},
        3: {1: "Endurance", 3: "Fractionné", 5: "Trail"},
        4: {1: "Endurance", 3: "Fractionné", 5: "Endurance", 6: "Trail"},
        5: {0: "Endurance", 1: "Fractionné", 3: "Endurance", 5: "Fractionné", 6: "Trail"},
        6: {1: "Endurance", 2: "Fractionné", 3: "Endurance", 4: "Fractionné", 5: "Endurance", 6: "Trail"},
        7: {0: "Endurance", 1: "Fractionné", 2: "Endurance", 3: "Fractionné", 4: "Endurance", 5: "Libre", 6: "Trail"},
    }
}

# Rétro-planning selon la distance de course
PHASES_BY_DISTANCE = {
    "5km": {"affutage": 1, "specifique": [2, 4], "montee": [5, 8], "non_specifique": 9},
    "10km": {"affutage": 1, "specifique": [2, 4], "montee": [5, 8], "non_specifique": 9},
    "21km": {"affutage": [1, 2], "specifique": [3, 5], "montee": [6, 13], "non_specifique": 14},
    "42km": {"affutage": [1, 3], "specifique": [4, 6], "montee": [7, 14], "non_specifique": 15},
    "trail_small": {"affutage": 1, "specifique": [2, 4], "montee": [5, 12], "non_specifique": 13},
    "trail_large": {"affutage": [1, 2], "specifique": [3, 5], "montee": [6, 13], "non_specifique": 14},
}

def get_distance_key(distance, goal_type):
    if goal_type == "trail":
        return "trail_small" if distance < 20 else "trail_large"
    if distance <= 7.5: return "5km"
    if distance <= 15: return "10km"
    if distance <= 30: return "21km"
    return "42km"

class PlanGenerator:
    def __init__(self, db, plan_data, catalog_workouts):
        self.db = db
        self.plan = plan_data
        self.catalog = catalog_workouts
        self.workouts = []
        
    def generate(self):
        race_date = self.plan.race_date
        start_date = self.plan.start_date
        
        # Nombre de semaines totales
        total_days = (race_date - start_date).days
        total_weeks = math.ceil(total_days / 7)
        
        dist_key = get_distance_key(self.plan.race_distance, self.plan.goal_type)
        phases = PHASES_BY_DISTANCE[dist_key]
        
        # Attribution des jours
        if not self.plan.training_days:
            base_assignment = DEFAULT_ASSIGNMENTS[self.plan.goal_type][self.plan.sessions_per_week]
            self.plan.training_days = list(base_assignment.keys())
        elif isinstance(self.plan.training_days, list):
            base_assignment = DEFAULT_ASSIGNMENTS[self.plan.goal_type][self.plan.sessions_per_week]
            categories = list(base_assignment.values())
            days = sorted(self.plan.training_days)
            new_assignment = {}
            for i, day in enumerate(days):
                new_assignment[day] = categories[i % len(categories)]
            base_assignment = new_assignment
        else:
            # Format Dict[int, str]
            base_assignment = {int(k): v for k, v in self.plan.training_days.items()}

        current_load = 0
        last_non_rest_load = 0
        
        # Durée de base pour l'endurance fondamentale (45 min par défaut)
        base_endurance_duration = 45
        
        for week_idx in range(total_weeks):
            week_start = start_date + timedelta(weeks=week_idx)
            weeks_to_race = total_weeks - week_idx
            
            is_rest_week = (week_idx + 1) % 4 == 0 and not self.is_near_race(week_idx, total_weeks, phases)
            
            # Déterminer la phase
            phase = self.get_phase(weeks_to_race, phases)
            
            # Facteur de charge selon la phase
            load_factor = 1.0
            if is_rest_week: load_factor = 0.7
            elif phase == "affutage": load_factor = 0.8
            elif phase == "montee": load_factor = 1.0 + (week_idx % 3) * 0.1 # Légère montée
            
            week_workouts = []
            
            for day_offset, category_choice in base_assignment.items():
                category = category_choice
                if isinstance(category_choice, (tuple, list)):
                    # Alternance une semaine sur deux
                    category = category_choice[week_idx % 2]
                
                workout_date = week_start + timedelta(days=day_offset)
                if workout_date >= race_date:
                    continue
                
                workout = self.create_workout_for_category(category, workout_date, load_factor, phase)
                if workout:
                    week_workouts.append(workout)
            
            self.workouts.extend(week_workouts)
            
        return self.workouts

    def get_phase(self, weeks_to_race, phases):
        affutage = phases["affutage"]
        if isinstance(affutage, list):
            if weeks_to_race <= affutage[1]: return "affutage"
        elif weeks_to_race <= affutage: return "affutage"
        
        spec = phases["specifique"]
        if weeks_to_race <= spec[1]: return "specifique"
        
        montee = phases["montee"]
        if weeks_to_race <= montee[1]: return "montee"
        
        return "non_specifique"

    def is_near_race(self, week_idx, total_weeks, phases):
        weeks_to_race = total_weeks - week_idx
        affutage = phases["affutage"]
        # On considère "proche de la course" si on est dans la période d'affûtage + 1 semaine
        max_affutage = affutage[1] if isinstance(affutage, list) else affutage
        return weeks_to_race <= max_affutage + 1

    def create_workout_for_category(self, category, date, load_factor, phase):
        from ..models.workout import Workout
        
        duration = 45 # Default
        difficulty = 3
        workout_type = category
        description = None
        
        if category == "Endurance":
            duration = int(45 * load_factor)
            duration = (duration // 5) * 5 # Divisible par 5
            duration = max(30, min(60, duration))
            difficulty = 3
            name = f"Endurance Fondamentale - {duration}min"
            description = "Le footing de la semaine, un moment pour faire du bien à votre corps, prenez le temps de vider votre tête."
            scheme = [{
                "repetitions": 1,
                "intervals": [{"type": "Endurance", "duration": duration, "pace_min": self.format_pace_vma(70), "pace_max": self.format_pace_vma(70)}]
            }]
        
        elif category == "Sortie longue" or category == "Trail":
            duration = int(80 * load_factor)
            if category == "Sortie longue":
                duration = (duration // 5) * 5
                description = "C’est la sortie longue de la semaine, hydratez-vous bien, prenez votre temps, faites un parcours que vous appréciez et essayez de garder un cardio bas"
            difficulty = 5
            name = f"{category} - {duration}min"
            scheme = [{
                "repetitions": 1,
                "intervals": [{"type": category, "duration": duration, "pace_min": self.format_pace_vma(65), "pace_max": self.format_pace_vma(65)}]
            }]
            
        elif category == "Libre":
            duration = int(40 * load_factor)
            duration = (duration // 5) * 5
            difficulty = 2
            name = f"Séance Libre - {duration}min"
            description = "C’est le moment détente, faites ce que vous voulez, sans regarder la montre. Essayez tout de même de ne pas générer trop de fatigue. Excellente occasion pour courir avec des amis"
            scheme = [{
                "repetitions": 1,
                "intervals": [{"type": "Libre", "duration": duration}]
            }]
            
        elif category == "Fractionné":
            # Piocher dans le catalogue
            if not self.catalog:
                # Séance par défaut si catalogue vide
                duration = 50
                difficulty = 7
                name = "Fractionné 30/30"
                description = "Séance de VMA courte : 30 secondes d'effort à 105% VMA suivies de 30 secondes de récupération."
                scheme = [
                    {
                        "repetitions": 1,
                        "intervals": [{"type": "Echauffement", "duration": 15, "pace_min": self.format_pace_vma(65), "pace_max": self.format_pace_vma(65)}]
                    },
                    {
                        "repetitions": 10,
                        "intervals": [
                            {"type": "Vite", "duration": 0.5, "pace_min": self.format_pace_vma(105), "pace_max": self.format_pace_vma(105)},
                            {"type": "Lent", "duration": 0.5, "pace_min": self.format_pace_vma(60), "pace_max": self.format_pace_vma(60)}
                        ]
                    },
                    {
                        "repetitions": 1,
                        "intervals": [{"type": "Retour calme", "duration": 10, "pace_min": self.format_pace_vma(65), "pace_max": self.format_pace_vma(65)}]
                    }
                ]
            else:
                # TODO: Mieux choisir dans le catalogue selon la phase
                cat_workout = self.catalog[date.day % len(self.catalog)]
                duration = sum(
                    block.get("repetitions", 1) * sum(i.get("duration", 0) for i in block.get("intervals", []))
                    for block in cat_workout.scheme if isinstance(block, dict)
                )
                difficulty = cat_workout.perceived_difficulty
                name = cat_workout.name
                description = getattr(cat_workout, 'description', None)
                workout_type = cat_workout.workout_type
                # Convertir les allures du catalogue
                scheme = []
                for block in cat_workout.scheme:
                    new_block = {"repetitions": block.get("repetitions", 1), "intervals": []}
                    for interval in block.get("intervals", []):
                        new_interval = interval.copy()
                        if "pace_vma_min" in new_interval:
                            new_interval["pace_min"] = self.format_pace_vma(new_interval["pace_vma_min"])
                        if "pace_vma_max" in new_interval:
                            new_interval["pace_max"] = self.format_pace_vma(new_interval["pace_vma_max"])
                        elif "pace_vma" in new_interval: # Support legacy
                            new_interval["pace_min"] = self.format_pace_vma(new_interval["pace_vma"])
                            new_interval["pace_max"] = self.format_pace_vma(new_interval["pace_vma"])
                        new_block["intervals"].append(new_interval)
                    scheme.append(new_block)
        
        else:
            return None

        return Workout(
            name=name,
            workout_type=workout_type,
            category=category,
            duration_minutes=duration,
            difficulty_level=difficulty,
            date=date,
            scheme=scheme,
            athlete_id=self.plan.athlete_id,
            description=description,
            estimated_load=duration + duration * difficulty / 5
        )

    def format_pace_vma(self, vma_percent):
        vma_min_km = self.plan.estimated_vma
        if vma_percent <= 0: return "0:00"
        pace_decimal = vma_min_km / (vma_percent / 100)
        minutes = int(pace_decimal)
        seconds = int(round((pace_decimal - minutes) * 60))
        if seconds >= 60:
            minutes += 1
            seconds = 0
        return f"{minutes}:{seconds:02d}"
