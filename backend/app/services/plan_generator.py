"""
Moteur de génération des plans d'entraînement — v3 : RÉTRO-PLANNING PAR LA CHARGE.

Principe : on part de la course et on remonte le temps.

1) Charge de la séance course :
   L_course = durée_course × (1 + intensité/5), avec l'intensité de course :
   trail long = 5, trail court = 6, marathon = 7, semi = 8, 10 km = 9, 5 km = 10.

2) Charge de la semaine de course :
   C_course = RACE_WEEK_CHARGE_RATIO × L_course_eff, où
   L_course_eff = L_course × facteur de fréquence (TRAINING_FREQUENCY_FACTOR) :
   plus l'athlète s'entraîne par semaine, plus sa capacité de charge — et donc
   sa semaine de course — est élevée. Toute la courbe de rétro-planning
   (C_course, pic, affûtage, plancher de départ) est ancrée sur L_course_eff.
   La séance course elle-même garde sa charge réelle L_course.

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

8) Fractionnés du catalogue : JAMAIS modifiés (ni répétitions, ni durées).
   Le budget de chaque fractionné est calculé après avoir pris en compte la
   charge réelle de la sortie longue (et de la course en semaine de course) ;
   on sélectionne alors, dans le catalogue pré-filtré par PHASE_KEYWORDS
   selon la phase (VMA en non-spécifique/montée, allure/seuil en spécifique),
   la séance dont la charge est la plus proche de la cible de la séance.
   Les séances endurance/libre absorbent l'écart restant du budget.

9) Schémas du catalogue : si un interval est défini par DISTANCE (sans
   durée), sa durée est calculée comme allure × distance — l'allure étant
   celle de l'interval (pace_min/pace_max en min/km) ou dérivée du %VMA
   (pace_vma) à partir de la VMA de l'athlète. La durée calculée est
   écrite dans le schéma généré (le catalogue n'est jamais modifié).

Hérité de la v2 : validation des entrées (ValueError → 422), choix du
catalogue par phase (mots-clés + anti-répétition), jours choisis
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
    "5km": {"affutage": [1, 2], "specifique": [3, 5], "montee": [6, 9], "non_specifique": 10},
    "10km": {"affutage": [1, 2], "specifique": [3, 5], "montee": [6, 9], "non_specifique": 10},
    "21km": {"affutage": [1, 3], "specifique": [4, 6], "montee": [7, 14], "non_specifique": 15},
    "42km": {"affutage": [1, 4], "specifique": [5, 7], "montee": [8, 15], "non_specifique": 16},
    "trail_small": {"affutage": [1, 2], "specifique": [3, 5], "montee": [6, 13], "non_specifique": 14},
    "trail_large": {"affutage": [1, 3], "specifique": [4, 6], "montee": [7, 14], "non_specifique": 15},
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
    "trail_large": 5,
    "trail_small": 6,
    "42km": 7,
    "21km": 8,
    "10km": 9,
    "5km": 10,
}

# %VMA indicatif de l'allure de course selon la distance (estimation)
RACE_PACE_VMA = {
    "5km": 95, "10km": 90, "21km": 82, "42km": 75,
    "trail_small": 70, "trail_large": 65,
}

# Charge de la semaine de course = ratio × charge effective de la séance course
# (la course + séances légères d'activation autour)
RACE_WEEK_CHARGE_RATIO = 2.0

# Facteur de fréquence d'entraînement appliqué à L_course : plus l'athlète
# s'entraîne par semaine, plus sa capacité de charge est élevée — et donc plus
# sa semaine de course (et toute la courbe du plan) est chargée.
# Référence 1.0 = 4 séances/semaine ; ±10 % par séance d'écart.
TRAINING_FREQUENCY_FACTOR = {
    1: 0.5, 2: 0.75, 3: 1, 4: 1.25, 5: 1.5, 6: 1.75, 7: 2.0,
}

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

# Séance 30/30 par défaut si le catalogue est vide (contenu fixe, non modifié)
DEFAULT_FRACTIONNE = (50, 7)  # (durée, difficulté)

# Anti-répétition du fractionné : si la séance la plus proche de la cible est
# celle utilisée la fois précédente, on lui préfère une alternative dont
# l'écart de charge reste dans ce facteur (1.05 = ±5 % de tolérance).
ANTI_REPEAT_TOLERANCE = 1.05

# Si le contenu minimum d'une semaine dépasse ce facteur × le budget, on
# retire les séances les moins prioritaires (Libre puis Endurance).
BUDGET_OVERRUN_TOLERANCE = 1.25


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


def _parse_pace(pace):
    """Convertit une allure en minutes décimales/km : "4:30" → 4.5 (accepte aussi un nombre)."""
    if pace is None or pace == "":
        return None
    if isinstance(pace, (int, float)):
        return float(pace)
    try:
        parts = str(pace).strip().split(":")
        if len(parts) == 2:
            return int(parts[0]) + int(parts[1]) / 60.0
        if len(parts) == 3:
            return int(parts[0]) * 60 + int(parts[1]) + int(parts[2]) / 60.0
    except (ValueError, IndexError):
        return None
    return None


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


def training_frequency_factor(sessions_per_week):
    """
    Facteur de fréquence appliqué à L_course : un athlète qui s'entraîne
    davantage absorbe une charge plus élevée. Référence 1.0 pour 4 séances/
    semaine, ±10 % par séance d'écart.
    """
    return TRAINING_FREQUENCY_FACTOR.get(int(sessions_per_week), 1.0)


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
        # Anti-répétition pour les séances de fractionné
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
            load = _load_of(duration, difficulty)
            self._race = {
                "distance": distance,
                "pace": pace,
                "duration": duration,
                "difficulty": difficulty,
                # Charge réelle de la séance course (ne dépend pas de la fréquence)
                "load": load,
                # Charge effective : ancre le rétro-planning en tenant compte du
                # nombre de séances/semaine (un athlète plus entraîné absorbe plus)
                "anchor_load": 2 * load * training_frequency_factor(self.plan.sessions_per_week),
            }
        return self._race

    def _week_target_load(self, weeks_to_race, total_weeks, is_rest_week):
        """
        Charge cible d'une semaine, calculée en rétro-planning depuis la course :

        - semaine de course           : C_course = RACE_WEEK_CHARGE_RATIO × L_course_eff
                                         (L_course_eff = L_course × facteur de fréquence)
        - affûtage                    : rampe C_course → pic (1.5 × C_course)
        - semaine pic                 : 1.5 × C_course (dernière avant affûtage)
        - avant le pic                : décroissance linéaire en remontant le temps,
                                        plancher START_RATIO × pic à la 1re semaine
        - semaine allégée (S4)         : charge × REST_WEEK_FACTOR
        """
        race = self._race_info()
        race_week_charge = race["anchor_load"] * RACE_WEEK_CHARGE_RATIO
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

        # 2) Sortie longue : sa part de la charge hebdomadaire — créée en PREMIER
        #    pour que la charge cible des fractionnés tienne compte de sa charge réelle
        ratio = long_run_ratio(self.plan.sessions_per_week) if long_run_slot else 0.0
        long_workout = None
        if long_run_slot:
            category, long_date = long_run_slot
            long_workout = self._create_long_run(category, long_date, ratio * target)

        # 3) Budget de charge pour les autres séances (hors sortie longue)
        spent = 0.0
        if long_workout is not None:
            spent += long_workout.estimated_load or 0
        if race_week:
            # La course occupe déjà une partie de la charge de sa semaine
            spent += race["load"]
        others_budget = max(0.0, target - spent)

        if others_budget > 1e-9:
            others = self._create_week_sessions(entries, others_budget, phase)
        else:
            others = []

        if long_workout is not None:
            others.append(long_workout)

        self.workouts.extend(others)

    def _create_week_sessions(self, entries, budget, phase):
        """
        Crée les séances hors sortie longue, dans cet ordre :

        1. Les fractionnés reçoivent chacun une charge cible (part du budget au
           prorata des charges nominales) puis on sélectionne dans le catalogue
           la séance à la charge la plus proche — son contenu n'est JAMAIS
           modifié (ni répétitions, ni durées).
        2. Les séances endurance/libre absorbent l'écart restant du budget.
        3. Si le contenu minimum dépasse trop le budget (début de plan,
           affûtage, semaine allégée), on retire les séances les moins
           prioritaires (Libre puis Endurance) pour rester cohérent avec la
           charge cible — le contenu restant n'est jamais modifié.
        """
        fixed_specs = []  # (catégorie, date, durée nominale, difficulté)
        frac_dates = []
        for category, date in entries:
            if category == "Fractionné":
                frac_dates.append(date)
            else:
                nominal_duration, difficulty = NOMINAL.get(category, (40, 3))
                fixed_specs.append((category, date, nominal_duration, difficulty))

        # Charge nominale d'un fractionné : charge moyenne du pool de la phase
        pool = self._phase_pool(phase)
        if pool:
            frac_nominal = sum(self._catalog_load(w) for w in pool) / float(len(pool))
        else:
            frac_nominal = _load_of(DEFAULT_FRACTIONNE[0], DEFAULT_FRACTIONNE[1])

        fixed_nominal = sum(_load_of(d, diff) for _, _, d, diff in fixed_specs)

        # Répartition du budget au prorata des charges nominales
        nominal_total = fixed_nominal + frac_nominal * len(frac_dates)
        scale = (budget / nominal_total) if nominal_total > 0 else 1.0

        # 1) Fractionnés : sélection catalogue par charge la plus proche (contenu figé)
        frac_workouts = []
        frac_actual = 0.0
        for date in frac_dates:
            workout = self._create_fractionne(date, phase, frac_nominal * scale)
            if workout:
                frac_actual += workout.estimated_load or 0
                frac_workouts.append(workout)

        # 2) Endurance/Libre absorbent le budget restant
        remaining = max(0.0, budget - frac_actual)
        fixed_scale = (remaining / fixed_nominal) if fixed_nominal > 0 else 1.0

        fixed_workouts = []
        for category, date, nominal_duration, difficulty in fixed_specs:
            target_duration = nominal_duration * fixed_scale
            if category == "Endurance":
                duration = _clamp(_round5(target_duration), *ENDURANCE_RANGE)
                fixed_workouts.append(self._create_endurance(date, duration))
            else:
                duration = _clamp(_round5(target_duration), *LIBRE_RANGE)
                fixed_workouts.append(self._create_libre(date, duration))

        # 3) Contenu minimum > budget : retirer les moins prioritaires
        sessions = frac_workouts + fixed_workouts
        limit = budget * BUDGET_OVERRUN_TOLERANCE
        for category_priority in ("Libre", "Endurance"):
            while sessions and sum(w.estimated_load or 0 for w in sessions) > limit:
                index = next(
                    (i for i in range(len(sessions) - 1, -1, -1)
                     if sessions[i].category == category_priority),
                    None,
                )
                if index is None:
                    break
                sessions.pop(index)
        return sessions

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
            difficulty_level=2,
            date=date,
            scheme=scheme,
            athlete_id=self.plan.athlete_id,
            description=(
                "Le footing de la semaine, un moment pour faire du bien à votre corps, "
                "prenez le temps de vider votre tête."
            ),
            estimated_load=_load_of(duration, 2),
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
            difficulty_level=1,
            date=date,
            scheme=scheme,
            athlete_id=self.plan.athlete_id,
            description=(
                "C'est le moment détente, faites ce que vous voulez, sans regarder la montre. "
                "Essayez tout de même de ne pas générer trop de fatigue. "
                "Excellente occasion pour courir avec des amis."
            ),
            estimated_load=_load_of(duration, 1),
        )

    def _create_fractionne(self, date, phase, target_load):
        """
        Séance de fractionné : la séance du catalogue (pré-filtrée par la phase
        via PHASE_KEYWORDS) dont la charge est la plus proche de la charge
        cible — son contenu (répétitions, durées, allures) n'est JAMAIS
        modifié. Si le catalogue est vide, séance 30/30 par défaut (fixe).
        """
        from ..models.workout import Workout

        cat_workout = self._pick_catalog_workout(phase, target_load)

        if cat_workout is None:
            # Catalogue vide : séance 30/30 par défaut (contenu fixe)
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
            duration, difficulty = DEFAULT_FRACTIONNE
            name = "Fractionné 30/30"
            description = (
                "Séance de VMA courte : 30 secondes d'effort à 105% VMA suivies "
                "de 30 secondes de récupération."
            )
            workout_type = "Fractionné"
        else:
            # Séance du catalogue telle quelle : aucune modification de contenu
            scheme = self._convert_scheme(cat_workout.scheme)
            duration = self._scheme_duration(scheme)
            difficulty = getattr(cat_workout, "perceived_difficulty", None) or 7
            name = cat_workout.name
            description = getattr(cat_workout, "description", None)
            workout_type = cat_workout.workout_type

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

    def _catalog_load(self, cat_workout):
        """Charge d'une séance du catalogue (durée × (1 + difficulté/5)), sans la modifier."""
        duration = self._scheme_duration(getattr(cat_workout, "scheme", None) or []) or 30
        difficulty = getattr(cat_workout, "perceived_difficulty", None) or 7
        return _load_of(duration, difficulty)

    def _phase_pool(self, phase):
        """
        Pool de séances du catalogue pour la phase : scoring par mots-clés
        (workout_type + name, insensible aux accents) — VMA/entretien en
        non-spécifique et montée, seuil/tempo/allure en spécifique, relances
        courtes en affûtage — puis tri par charge croissante.
        """
        if not self.catalog:
            return []

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
        pool.sort(key=lambda w: (self._catalog_load(w), getattr(w, "id", 0) or 0))
        return pool

    def _pick_catalog_workout(self, phase, target_load):
        """
        Sélectionne dans le pool de la phase la séance du catalogue dont la
        charge est la PLUS PROCHE de la charge cible — sans jamais modifier
        son contenu. Anti-répétition : si la séance la plus proche est celle
        utilisée la fois précédente, on lui préfère une alternative quasi
        équivalente (écart dans ANTI_REPEAT_TOLERANCE).
        """
        pool = self._phase_pool(phase)
        if not pool:
            return None

        best = min(pool, key=lambda w: abs(self._catalog_load(w) - target_load))
        best_id = getattr(best, "id", None)

        if len(pool) > 1 and best_id is not None and best_id == self._last_frac_id:
            others = [w for w in pool if getattr(w, "id", None) != best_id]
            alternative = min(others, key=lambda w: abs(self._catalog_load(w) - target_load))
            best_gap = abs(self._catalog_load(best) - target_load)
            alt_gap = abs(self._catalog_load(alternative) - target_load)
            if alt_gap <= best_gap * ANTI_REPEAT_TOLERANCE + 1e-9:
                best = alternative

        self._last_frac_id = getattr(best, "id", None)
        return best

    def _scheme_duration(self, scheme):
        """
        Durée totale d'un schéma (en tenant compte des répétitions). Les
        intervals définis par distance (sans durée) sont convertis en durée
        via allure × distance.
        """
        total = 0
        for block in scheme or []:
            if not isinstance(block, dict):
                continue
            repetitions = block.get("repetitions", 1) or 1
            block_time = sum(
                self._interval_duration(interval)
                for interval in block.get("intervals", [])
                if isinstance(interval, dict)
            )
            total += repetitions * block_time
        return int(round(total))

    def _interval_duration(self, interval):
        """
        Durée d'un interval en minutes : durée explicite si présente, sinon
        distance × allure (allure de l'interval, calculée selon la VMA).
        """
        if not isinstance(interval, dict):
            return 0.0
        if interval.get("duration"):
            return float(interval["duration"])
        distance = interval.get("distance") / 1000.0
        if not distance:
            return 0.0
        return float(distance) * self._interval_pace_decimal(interval)

    def _interval_pace_decimal(self, interval):
        """
        Allure d'un interval en minutes décimales / km :
        - moyenne des allures cibles (pace_min/pace_max, format "m:ss"),
        - sinon dérivée du %VMA (pace_vma / pace_vma_min / pace_vma_max)
          à partir de la VMA estimée de l'athlète,
        - sinon allure d'endurance fondamentale (70 % VMA) par défaut.
        """
        paces = [
            pace
            for pace in (_parse_pace(interval.get(k)) for k in ("pace_min", "pace_max"))
            if pace is not None
        ]
        if paces:
            return sum(paces) / len(paces)
        for key in ("pace_vma_min", "pace_vma_max", "pace_vma"):
            percent = interval.get(key)
            if percent and percent > 0 and self.plan.estimated_vma:
                return self.plan.estimated_vma / (percent / 100.0)
        # Pas d'allure renseignée : allure d'endurance fondamentale par défaut
        if self.plan.estimated_vma:
            return self.plan.estimated_vma / 0.70
        return 0.0

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
                # Interval défini par distance : écrire la durée calculée
                # (allure × distance) dans le schéma généré
                if not new_interval.get("duration") and new_interval.get("distance"):
                    new_interval["duration"] = round(
                        float(new_interval["distance"]) * self._interval_pace_decimal(new_interval) / 1000.0,
                        1,
                    )
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
