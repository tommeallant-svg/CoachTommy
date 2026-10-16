"""
Moteur de génération des plans d'entraînement — v3 : RÉTRO-PLANNING PAR LA CHARGE.

Principe : on part de la course et on remonte le temps.

1) Charge de la séance course :
   L_course = durée_course × (1 + intensité/5), avec l'intensité de course :
   trail long = 5, trail court = 6, marathon = 7, semi = 8, 10 km = 9, 5 km = 10.

2) Charge de la semaine de course :
   C_course = RACE_WEEK_CHARGE_RATIO × L_course
   (la course + quelques séances légères autour).

3) Semaine PIC = dernière semaine avant l'affûtage (dernière semaine
   spécifique) : C_pic = PEAK_MULTIPLIER × C_course = 1.5 × C_course.
   C'est la semaine la plus chargée du plan.

4) Affûtage (semaines de course incluse) : rampe linéaire, de C_course
   (semaine de course) à C_pic (semaine précédant l'affûtage).

5) Avant le pic : plus on s'éloigne de la course, moins la semaine est
   chargée — décroissance linéaire en remontant le temps, avec un plancher
   à START_RATIO × C_pic pour la première semaine du plan.

6) Semaine allégée : toutes les 4 semaines, la charge cible est multipliée
   par REST_WEEK_FACTOR (jamais à l'approche de la course ni au pic).

7) Sortie longue : elle reçoit toujours sa part de la charge hebdomadaire
   (≈ 30 % à partir de 4 séances/semaine, ≈ 40 % pour 3 ou moins).
   Sa durée est recalculée chaque semaine → elle suit la courbe de charge.
   En semaine de course, pas de sortie longue (elle devient Endurance).

8) Les autres séances se partagent le budget restant au prorata de leur
   charge nominale (Endurance 45 min, Libre 40 min, Fractionné = durée du
   catalogue). Le fractionné du catalogue est ajusté en répétitions pour
   viser sa durée allouée.

Hérité de la v2 : validation des entrées (ValueError → 422), choix du
catalogue par phase (mots-clés + rotation anti-répétition), jours choisis
sans wrap, séance du jour de course, aucune séance la veille de la course.
"""

from datetime import timedelta
import math
import unicodedata

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

LONG_RUN_CATEGORIES = {"Sortie longue", "Trail"}

GOAL_TYPES = ("plaisir", "maintien", "mixte", "intensité", "trail")

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
    },
}

# Rétro-planning : phases selon la distance (en semaines avant la course)
PHASES_BY_DISTANCE = {
    "5km": {"affutage": 1, "specifique": [2, 4], "montee": [5, 8], "non_specifique": 9},
    "10km": {"affutage": 1, "specifique": [2, 4], "montee": [5, 8], "non_specifique": 9},
    "21km": {"affutage": [1, 2], "specifique": [3, 5], "montee": [6, 13], "non_specifique": 14},
    "42km": {"affutage": [1, 3], "specifique": [4, 6], "montee": [7, 14], "non_specifique": 15},
    "trail_small": {"affutage": 1, "specifique": [2, 4], "montee": [5, 12], "non_specifique": 13},
    "trail_large": {"affutage": [1, 2], "specifique": [3, 5], "montee": [6, 13], "non_specifique": 14},
}

# Mots-clés (sans accents, minuscules) pour orienter le choix des séances de
# fractionné du catalogue selon la phase.
PHASE_KEYWORDS = {
    "non_specifique": ["vma", "tempo", "seuil", "vo2"],
    "montee": ["vma", "seuil", "vo2", "tempo", "allure"],
    "specifique": ["seuil", "tempo", "allure", "specifique"],
    "affutage": ["tempo", "allure", "court"],
}

# --- Paramètres du rétro-planning v3 (ajustables par le coach) ---

# Intensité de la course (échelle de difficulté des séances)
RACE_INTENSITY = {
    "trail_large": 8,
    "trail_small": 10,
    "42km": 10,
    "21km": 15,
    "10km": 20,
    "5km": 30,
}

# %VMA indicatif de l'allure de course selon la distance (estimation)
RACE_PACE_VMA = {
    "5km": 95, "10km": 90, "21km": 82, "42km": 75,
    "trail_small": 70, "trail_large": 65,
}

# Charge de la semaine de course = ratio × charge de la séance course
# (la course + séances légères d'activation autour)
RACE_WEEK_CHARGE_RATIO = 2.0

# Semaine PIC (dernière semaine avant l'affûtage) = 1.5 × charge semaine course
PEAK_MULTIPLIER = 1.5

# Plancher de charge de la 1re semaine du plan = START_RATIO × charge du pic
START_RATIO = 0.5

# Semaine allégée : toutes les 4 semaines, charge × REST_WEEK_FACTOR
REST_WEEK_FACTOR = 0.7
REST_WEEK_EVERY = 4

# --- Durées nominales et bornes ---

# (durée nominale en minutes, difficulté) par catégorie de séance
NOMINAL = {
    "Endurance": (45, 3),
    "Libre": (40, 2),
}
ENDURANCE_RANGE = (30, 90)
LIBRE_RANGE = (20, 75)

LONG_RUN_DIFFICULTY = 5  # charge sortie longue = durée × 2
LONG_RUN_FLOORS = {"5km": 40, "10km": 50, "21km": 60, "42km": 70, "trail_small": 60, "trail_large": 70}
LONG_RUN_CAPS = {"5km": 90, "10km": 105, "21km": 140, "42km": 180, "trail_small": 150, "trail_large": 165}

# Bornes d'ajustement du fractionné du catalogue (facteur sur les répétitions)
FRACTIONNE_SCALE_RANGE = (0.6, 1.6)

# Séance 30/30 par défaut si le catalogue est vide
DEFAULT_FRACTIONNE = (50, 7)  # (durée nominale, difficulté)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _norm(text):
    """Normalise un texte : sans accents, minuscules (comparaisons robustes)."""
    if not text:
        return ""
    return (
        unicodedata.normalize("NFKD", str(text))
        .encode("ascii", "ignore")
        .decode("ascii")
        .strip()
        .lower()
    )


def _round5(value):
    """Arrondit une durée au multiple de 5 inférieur."""
    return int(value // 5 * 5)


def _load_of(duration, difficulty):
    """Charge d'une séance : durée × (1 + difficulté/5) — même formule que le modèle Workout."""
    return duration * (1.0 + difficulty / 5.0)


def _clamp(value, low, high):
    return max(low, min(high, value))


def get_distance_key(distance, goal_type):
    if goal_type == "trail":
        return "trail_small" if distance < 20 else "trail_large"
    if distance <= 7.5:
        return "5km"
    if distance <= 15:
        return "10km"
    if distance <= 30:
        return "21km"
    return "42km"


def long_run_ratio(sessions_per_week):
    """
    Part de la charge hebdomadaire reçue par la sortie longue :
    ≈ 40 % pour 3 séances/semaine ou moins, ≈ 30 % à partir de 4 séances.
    """
    return 0.40 if sessions_per_week <= 3 else 0.30


def normalize_goal_type(goal_type):
    """Valide et normalise le goal_type (accents et casse tolérés) → ValueError si inconnu."""
    if not goal_type or not isinstance(goal_type, str):
        raise ValueError("Le type d'objectif (goal_type) est obligatoire.")
    key = _norm(goal_type)
    for goal in GOAL_TYPES:
        if _norm(goal) == key:
            return goal
    raise ValueError(
        f"Type d'objectif inconnu : '{goal_type}'. Valeurs acceptées : {', '.join(GOAL_TYPES)}."
    )


def validate_plan_inputs(plan):
    """
    Valide les entrées du plan AVANT toute génération. Lève ValueError avec un
    message utilisateur clair (la route la convertit en HTTP 422).
    """
    plan.goal_type = normalize_goal_type(plan.goal_type)

    sessions = plan.sessions_per_week
    if isinstance(sessions, bool) or not isinstance(sessions, int) or not 1 <= sessions <= 7:
        raise ValueError("sessions_per_week doit être un entier entre 1 et 7.")

    if plan.race_distance is None or plan.race_distance <= 0:
        raise ValueError("La distance de course (race_distance) doit être strictement positive.")

    if plan.start_date is None or plan.race_date is None:
        raise ValueError("Les dates de début et de course sont obligatoires.")

    if plan.race_date <= plan.start_date:
        raise ValueError("La date de course doit être postérieure à la date de début du plan.")

    if not plan.estimated_vma or plan.estimated_vma <= 0:
        raise ValueError("La VMA estimée (min/km) est obligatoire et doit être positive.")


# ---------------------------------------------------------------------------
# Générateur
# ---------------------------------------------------------------------------

class PlanGenerator:
    def __init__(self, db, plan_data, catalog_workouts):
        self.db = db
        self.plan = plan_data
        self.catalog = catalog_workouts or []
        self.workouts = []
        # Rotation anti-répétition pour les séances de fractionné
        self._frac_counter = 0
        self._last_frac_id = None
        # Cache des infos de la séance course
        self._race = None

    # -- Orchestration --------------------------------------------------------

    def generate(self):
        validate_plan_inputs(self.plan)

        race_date = self.plan.race_date
        start_date = self.plan.start_date

        total_days = (race_date - start_date).days
        total_weeks = math.ceil(total_days / 7)

        self.dist_key = get_distance_key(self.plan.race_distance, self.plan.goal_type)
        self.phases = PHASES_BY_DISTANCE[self.dist_key]

        assignment = self._build_assignment()

        for week_idx in range(total_weeks):
            week_start = start_date + timedelta(weeks=week_idx)
            weeks_to_race = total_weeks - week_idx
            phase = self.get_phase(weeks_to_race, self.phases)

            self._generate_week(
                week_idx, week_start, race_date, assignment, phase, total_weeks, weeks_to_race
            )

        # Le jour de course fait partie du plan
        race_workout = self._create_race_workout()
        if race_workout:
            self.workouts.append(race_workout)

        return self.workouts

    # -- Phases --------------------------------------------------------------

    def get_phase(self, weeks_to_race, phases):
        affutage = phases["affutage"]
        if isinstance(affutage, list):
            if weeks_to_race <= affutage[1]:
                return "affutage"
        elif weeks_to_race <= affutage:
            return "affutage"

        spec = phases["specifique"]
        if weeks_to_race <= spec[1]:
            return "specifique"

        montee = phases["montee"]
        if weeks_to_race <= montee[1]:
            return "montee"

        return "non_specifique"

    def is_near_race(self, week_idx, total_weeks, phases):
        """"Proche de la course" = affûtage + 1 semaine (= semaine pic incluse)."""
        weeks_to_race = total_weeks - week_idx
        affutage = phases["affutage"]
        max_affutage = affutage[1] if isinstance(affutage, list) else affutage
        return weeks_to_race <= max_affutage + 1

    # -- Rétro-planning v3 : charge cible de chaque semaine ---------------------

    def _race_info(self):
        """Charge et caractéristiques de la séance course (ancrage du rétro-planning)."""
        if self._race is None:
            distance = self.plan.race_distance
            vma_percent = RACE_PACE_VMA.get(self.dist_key, 80)
            pace = self.format_pace_vma(vma_percent)
            pace_decimal = self.plan.estimated_vma / (vma_percent / 100.0)
            duration = int(round(distance * pace_decimal))
            difficulty = RACE_INTENSITY.get(self.dist_key, 8)
            self._race = {
                "distance": distance,
                "pace": pace,
                "duration": duration,
                "difficulty": difficulty,
                "load": _load_of(duration, difficulty),
            }
        return self._race

    def _week_target_load(self, weeks_to_race, total_weeks, is_rest_week):
        """
        Charge cible d'une semaine, calculée en rétro-planning depuis la course :

        - semaine de course           : C_course = RACE_WEEK_CHARGE_RATIO × L_course
        - affûtage                    : rampe C_course → pic (1.5 × C_course)
        - semaine pic                 : 1.5 × C_course (dernière avant affûtage)
        - avant le pic                : décroissance linéaire en remontant le temps,
                                        plancher START_RATIO × pic à la 1re semaine
        - semaine allégée (S4)         : charge × REST_WEEK_FACTOR
        """
        race = self._race_info()
        race_week_charge = race["load"] * RACE_WEEK_CHARGE_RATIO
        peak = PEAK_MULTIPLIER * race_week_charge

        affutage = self.phases["affutage"]
        max_affutage = affutage[1] if isinstance(affutage, list) else affutage

        if weeks_to_race <= max_affutage:
            # Affûtage (inclut la semaine de course) : rampe C_course → pic
            span = max(1, max_affutage)
            target = race_week_charge + (peak - race_week_charge) * (weeks_to_race - 1) / float(span)
        else:
            # Avant le pic : plus on s'éloigne de la course, moins c'est chargé
            week_peak = max_affutage + 1
            weeks_back = weeks_to_race - week_peak
            total_back = max(1, total_weeks - week_peak)
            factor = max(START_RATIO, 1.0 - weeks_back / float(total_back))
            target = peak * factor

        if is_rest_week:
            target *= REST_WEEK_FACTOR
        return target

    # -- Attribution des jours -------------------------------------------------

    def _build_assignment(self):
        """
        Construit le mapping {jour: catégorie} de la semaine, sans duplication
        de sortie longue et sans "wrap" des catégories.
        """
        default = DEFAULT_ASSIGNMENTS[self.plan.goal_type][self.plan.sessions_per_week]
        training_days = self.plan.training_days

        if not training_days:
            assignment = {int(day): cat for day, cat in default.items()}
        elif isinstance(training_days, dict):
            assignment = {}
            for key, category in training_days.items():
                try:
                    day = int(key)
                except (TypeError, ValueError):
                    raise ValueError(
                        f"Jour invalide dans training_days : '{key}'. Utilisez 0=lundi ... 6=dimanche."
                    )
                if not 0 <= day <= 6:
                    raise ValueError(
                        f"Jour invalide dans training_days : {day}. Utilisez 0=lundi ... 6=dimanche."
                    )
                assignment[day] = category
        else:
            # Jours choisis par l'utilisateur : mapping SANS modulo — les jours en
            # surnombre deviennent "Libre" et la sortie longue est toujours gardée.
            try:
                days = sorted({int(d) for d in training_days})
            except (TypeError, ValueError):
                raise ValueError(
                    "training_days doit contenir des numéros de jours (0=lundi ... 6=dimanche)."
                )
            for day in days:
                if not 0 <= day <= 6:
                    raise ValueError(
                        f"Jour invalide dans training_days : {day}. Utilisez 0=lundi ... 6=dimanche."
                    )
            if not days:
                assignment = {int(day): cat for day, cat in default.items()}
            else:
                categories = list(default.values())
                selected = categories[: len(days)] or ["Libre"]
                has_long_default = any(c in LONG_RUN_CATEGORIES for c in categories)
                if has_long_default and not any(c in LONG_RUN_CATEGORIES for c in selected):
                    selected[-1] = next(c for c in categories if c in LONG_RUN_CATEGORIES)
                if len(days) > len(categories):
                    selected += ["Libre"] * (len(days) - len(categories))
                assignment = dict(zip(days, selected))

        # Sécurité : au plus une sortie longue par semaine (on garde celle du week-end)
        long_days = [d for d, c in assignment.items() if c in LONG_RUN_CATEGORIES]
        if len(long_days) > 1:
            keep = max(long_days)
            for day in long_days:
                if day != keep:
                    assignment[day] = "Endurance"

        self.plan.training_days = sorted(assignment.keys())
        return assignment

    # -- Génération d'une semaine ----------------------------------------------

    def _generate_week(self, week_idx, week_start, race_date, assignment, phase, total_weeks, weeks_to_race):
        # Semaine allégée toutes les 4 semaines, sauf à l'approche de la course
        is_rest_week = (
            (week_idx + 1) % REST_WEEK_EVERY == 0
            and not self.is_near_race(week_idx, total_weeks, self.phases)
        )

        # Charge cible de la semaine (rétro-planning)
        target = self._week_target_load(weeks_to_race, total_weeks, is_rest_week)

        race_week = weeks_to_race == 1
        race = self._race_info()

        # 1) Collecter les sessions de la semaine (hors sortie longue)
        entries = []  # (catégorie, date)
        long_run_slot = None
        for day_offset, category_choice in assignment.items():
            category = category_choice
            if isinstance(category_choice, (tuple, list)) and category_choice:
                # Alternance une semaine sur deux
                category = category_choice[week_idx % 2]

            workout_date = week_start + timedelta(days=day_offset)
            if self._skip_date(workout_date, race_date):
                continue

            if category in LONG_RUN_CATEGORIES:
                if race_week:
                    # Pas de sortie longue en semaine de course : séance d'endurance
                    category = "Endurance"
                else:
                    long_run_slot = (category, workout_date)
                    continue
            entries.append((category, workout_date))

        # 2) Budget de charge pour les séances hors sortie longue
        ratio = long_run_ratio(self.plan.sessions_per_week) if long_run_slot else 0.0
        if race_week:
            # La course occupe déjà une partie de la charge de sa semaine
            others_budget = max(0.0, target - race["load"])
        else:
            others_budget = target * (1.0 - ratio)

        if not race_week or others_budget > 1e-9:
            others = self._create_week_sessions(entries, others_budget, phase)
        else:
            others = []

        # 3) En semaine de course : ne pas dépasser le budget (retirer les moins prioritaires)
        if race_week and others:
            limit = others_budget * 1.25
            for category_priority in ("Libre", "Endurance"):
                while sum(w.estimated_load or 0 for w in others) > limit:
                    index = next(
                        (i for i in range(len(others) - 1, -1, -1)
                         if others[i].category == category_priority),
                        None,
                    )
                    if index is None:
                        break
                    others.pop(index)

        # 4) Sortie longue : sa part de la charge hebdomadaire
        if long_run_slot:
            category, long_date = long_run_slot
            long_charge = ratio * target
            long_workout = self._create_long_run(category, long_date, long_charge)
            if long_workout:
                others.append(long_workout)

        self.workouts.extend(others)

    def _create_week_sessions(self, entries, budget, phase):
        """
        Crée les séances hors sortie longue en répartissant le budget de charge
        au prorata de leur charge nominale.
        """
        # Charge nominale de chaque séance
        nominals = []
        for category, date in entries:
            if category == "Fractionné":
                cat_workout = self._pick_catalog_workout(phase)
                if cat_workout is None:
                    nominal_duration, difficulty = DEFAULT_FRACTIONNE
                    nominals.append((category, date, float(nominal_duration), difficulty, None, None))
                else:
                    scheme = self._convert_scheme(cat_workout.scheme)
                    nominal_duration = self._scheme_duration(scheme) or 30
                    difficulty = getattr(cat_workout, "perceived_difficulty", None) or 7
                    nominals.append((category, date, float(nominal_duration), difficulty, cat_workout, scheme))
            else:
                nominal_duration, difficulty = NOMINAL.get(category, (40, 3))
                nominals.append((category, date, float(nominal_duration), difficulty, None, None))

        total_nominal = sum(_load_of(d, diff) for _, _, d, diff, _, _ in nominals)
        scale = (budget / total_nominal) if total_nominal > 0 else 1.0

        workouts = []
        for category, date, nominal_duration, difficulty, cat_workout, scheme in nominals:
            target_duration = nominal_duration * scale
            if category == "Endurance":
                duration = _clamp(_round5(target_duration), *ENDURANCE_RANGE)
                workout = self._create_endurance(date, duration)
            elif category == "Libre":
                duration = _clamp(_round5(target_duration), *LIBRE_RANGE)
                workout = self._create_libre(date, duration)
            elif category == "Fractionné":
                workout = self._create_fractionne(date, cat_workout, scheme, target_duration)
            else:
                workout = None
            if workout:
                workouts.append(workout)
        return workouts

    def _skip_date(self, workout_date, race_date):
        # Pas de séance le jour de la course ni la veille
        if workout_date >= race_date:
            return True
        if (race_date - workout_date).days == 1:
            return True
        return False

    # -- Création des séances -----------------------------------------------------

    def _create_endurance(self, date, duration):
        from ..models.workout import Workout

        pace = self.format_pace_vma(70)
        scheme = [{
            "repetitions": 1,
            "intervals": [
                {"type": "Endurance", "duration": duration, "pace_min": pace, "pace_max": pace}
            ],
        }]
        return Workout(
            name=f"Endurance Fondamentale - {duration}min",
            workout_type="Endurance",
            category="Endurance",
            duration_minutes=duration,
            difficulty_level=3,
            date=date,
            scheme=scheme,
            athlete_id=self.plan.athlete_id,
            description=(
                "Le footing de la semaine, un moment pour faire du bien à votre corps, "
                "prenez le temps de vider votre tête."
            ),
            estimated_load=_load_of(duration, 3),
        )

    def _create_libre(self, date, duration):
        from ..models.workout import Workout

        scheme = [{
            "repetitions": 1,
            "intervals": [{"type": "Libre", "duration": duration}],
        }]
        return Workout(
            name=f"Séance Libre - {duration}min",
            workout_type="Libre",
            category="Libre",
            duration_minutes=duration,
            difficulty_level=2,
            date=date,
            scheme=scheme,
            athlete_id=self.plan.athlete_id,
            description=(
                "C'est le moment détente, faites ce que vous voulez, sans regarder la montre. "
                "Essayez tout de même de ne pas générer trop de fatigue. "
                "Excellente occasion pour courir avec des amis."
            ),
            estimated_load=_load_of(duration, 2),
        )

    def _create_fractionne(self, date, cat_workout, scheme, target_duration):
        """
        Séance de fractionné : issue du catalogue (ou 30/30 par défaut), ajustée
        en répétitions pour viser la durée allouée par le budget de la semaine.
        """
        from ..models.workout import Workout

        if cat_workout is None:
            # Catalogue vide : séance 30/30 par défaut
            pace_end = self.format_pace_vma(65)
            scheme = [
                {
                    "repetitions": 1,
                    "intervals": [{"type": "Echauffement", "duration": 15, "pace_min": pace_end, "pace_max": pace_end}],
                },
                {
                    "repetitions": 10,
                    "intervals": [
                        {"type": "Vite", "duration": 0.5, "pace_min": self.format_pace_vma(105), "pace_max": self.format_pace_vma(105)},
                        {"type": "Lent", "duration": 0.5, "pace_min": self.format_pace_vma(60), "pace_max": self.format_pace_vma(60)},
                    ],
                },
                {
                    "repetitions": 1,
                    "intervals": [{"type": "Retour calme", "duration": 10, "pace_min": pace_end, "pace_max": pace_end}],
                },
            ]
            difficulty = DEFAULT_FRACTIONNE[1]
            name = "Fractionné 30/30"
            description = (
                "Séance de VMA courte : 30 secondes d'effort à 105% VMA suivies "
                "de 30 secondes de récupération."
            )
            workout_type = "Fractionné"
        else:
            difficulty = getattr(cat_workout, "perceived_difficulty", None) or 7
            name = cat_workout.name
            description = getattr(cat_workout, "description", None)
            workout_type = cat_workout.workout_type

        # Ajuster le nombre de répétitions pour viser la durée allouée
        scheme_duration = self._scheme_duration(scheme)
        if scheme_duration > 0:
            factor = _clamp(target_duration / float(scheme_duration), *FRACTIONNE_SCALE_RANGE)
            scheme = self._scale_repetitions(scheme, factor)
        duration = self._scheme_duration(scheme)

        return Workout(
            name=name,
            workout_type=workout_type,
            category="Fractionné",
            duration_minutes=duration,
            difficulty_level=difficulty,
            date=date,
            scheme=scheme,
            athlete_id=self.plan.athlete_id,
            description=description,
            estimated_load=_load_of(duration, difficulty),
        )

    def _create_long_run(self, category, date, charge):
        """
        Sortie longue dimensionnée comme part de la charge hebdomadaire.
        Charge d'une séance = durée × (1 + difficulté/5) ; difficulté 5 →
        charge = durée × 2, d'où durée = charge / 2.
        """
        from ..models.workout import Workout

        duration = int(charge / (1.0 + LONG_RUN_DIFFICULTY / 5.0))
        duration = _round5(duration)
        duration = _clamp(
            duration,
            LONG_RUN_FLOORS.get(self.dist_key, 50),
            LONG_RUN_CAPS.get(self.dist_key, 150),
        )

        pace = self.format_pace_vma(65)
        scheme = [{
            "repetitions": 1,
            "intervals": [{"type": category, "duration": duration, "pace_min": pace, "pace_max": pace}],
        }]

        if category == "Trail":
            description = (
                "Sortie longue sur terrain de trail : privilégiez le dénivelé et le feeling, "
                "hydratation et ravitaillement comme en course."
            )
        else:
            description = (
                "C'est la sortie longue de la semaine, hydratez-vous bien, prenez votre temps, "
                "faites un parcours que vous appréciez et essayez de garder un cardio bas."
            )

        return Workout(
            name=f"{category} - {duration}min",
            workout_type=category,
            category=category,
            duration_minutes=duration,
            difficulty_level=LONG_RUN_DIFFICULTY,
            date=date,
            scheme=scheme,
            athlete_id=self.plan.athlete_id,
            description=description,
            estimated_load=_load_of(duration, LONG_RUN_DIFFICULTY),
        )

    def _create_race_workout(self):
        """Le jour de course fait partie du plan — ancre du rétro-planning."""
        from ..models.workout import Workout

        race = self._race_info()
        scheme = [{
            "repetitions": 1,
            "intervals": [{
                "type": "Course",
                "duration": race["duration"],
                "distance": race["distance"],
                "pace_min": race["pace"],
                "pace_max": race["pace"],
            }],
        }]

        return Workout(
            name=f"Jour de course - {race['distance']} km",
            workout_type="Course",
            category="Course",
            duration_minutes=race["duration"],
            difficulty_level=race["difficulty"],
            date=self.plan.race_date,
            scheme=scheme,
            athlete_id=self.plan.athlete_id,
            description="Jour J ! Rien à prouver, tout ce que vous avez fait compte. Bonne course !",
            estimated_load=race["load"],
        )

    # -- Catalogue ---------------------------------------------------------------

    def _pick_catalog_workout(self, phase):
        """
        Choisit une séance de fractionné dans le catalogue selon la phase :
        1. scoring par mots-clés (workout_type + name, insensible aux accents)
        2. en affûtage, on restreint à la moitié la plus courte du pool
        3. rotation round-robin avec anti-répétition immédiate
        """
        if not self.catalog:
            return None

        keywords = [_norm(kw) for kw in PHASE_KEYWORDS.get(phase, [])]
        scored = []
        for workout in self.catalog:
            haystack = _norm(
                f"{getattr(workout, 'workout_type', '') or ''} {getattr(workout, 'name', '') or ''}"
            )
            score = sum(1 for kw in keywords if kw and kw in haystack)
            scored.append((score, workout))

        best_score = max(score for score, _ in scored)
        pool = [workout for score, workout in scored if score == best_score]

        pool.sort(key=lambda w: (self._scheme_duration(getattr(w, "scheme", None) or []), getattr(w, "id", 0) or 0))

        # En affûtage, préférer les séances courtes (moitié la plus courte du pool)
        if phase == "affutage" and len(pool) > 2:
            pool = pool[: (len(pool) + 1) // 2]

        # Rotation anti-répétition
        index = self._frac_counter % len(pool)
        candidate = pool[index]
        candidate_id = getattr(candidate, "id", None)
        if len(pool) > 1 and candidate_id is not None and candidate_id == self._last_frac_id:
            candidate = pool[(index + 1) % len(pool)]
            candidate_id = getattr(candidate, "id", None)
        self._frac_counter += 1
        self._last_frac_id = candidate_id
        return candidate

    def _scheme_duration(self, scheme):
        """Durée totale d'un schéma (en tenant compte des répétitions)."""
        total = 0
        for block in scheme or []:
            if not isinstance(block, dict):
                continue
            repetitions = block.get("repetitions", 1) or 1
            block_time = sum(
                interval.get("duration", 0) or 0
                for interval in block.get("intervals", [])
                if isinstance(interval, dict)
            )
            total += repetitions * block_time
        return int(round(total))

    def _scale_repetitions(self, scheme, factor):
        """
        Ajuste une séance en jouant sur le nombre de répétitions des blocs
        répétés — jamais en dessous de 1. Les blocs en 1 répétition
        (échauffement, retour au calme) sont préservés.
        """
        if abs(factor - 1.0) < 1e-9:
            return scheme
        new_scheme = []
        for block in scheme or []:
            if not isinstance(block, dict):
                continue
            repetitions = block.get("repetitions", 1) or 1
            if repetitions > 1:
                repetitions = max(1, int(round(repetitions * factor)))
            new_scheme.append({**block, "repetitions": repetitions})
        return new_scheme

    def _convert_scheme(self, scheme):
        """Convertit les allures %VMA du catalogue en min/km (comportement v1 conservé)."""
        new_scheme = []
        for block in scheme or []:
            if not isinstance(block, dict):
                continue
            new_block = {"repetitions": block.get("repetitions", 1), "intervals": []}
            for interval in block.get("intervals", []):
                if not isinstance(interval, dict):
                    continue
                new_interval = dict(interval)
                if "pace_vma_min" in new_interval:
                    new_interval["pace_min"] = self.format_pace_vma(new_interval["pace_vma_min"])
                if "pace_vma_max" in new_interval:
                    new_interval["pace_max"] = self.format_pace_vma(new_interval["pace_vma_max"])
                elif "pace_vma" in new_interval:
                    # Support legacy
                    new_interval["pace_min"] = self.format_pace_vma(new_interval["pace_vma"])
                    new_interval["pace_max"] = new_interval["pace_min"]
                new_block["intervals"].append(new_interval)
            new_scheme.append(new_block)
        return new_scheme

    # -- Allures ------------------------------------------------------------------

    def format_pace_vma(self, vma_percent):
        vma_min_km = self.plan.estimated_vma
        if vma_percent <= 0:
            return "0:00"
        pace_decimal = vma_min_km / (vma_percent / 100.0)
        minutes = int(pace_decimal)
        seconds = int(round((pace_decimal - minutes) * 60))
        if seconds >= 60:
            minutes += 1
            seconds = 0
        return f"{minutes}:{seconds:02d}"
