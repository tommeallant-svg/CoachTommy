def _pace_minutes(value):
    try:
        parts = str(value).split(':')
        pace = float(parts[0]) + (float(parts[1]) / 60 if len(parts) == 2 else 0)
        return pace if pace > 0 else None
    except (TypeError, ValueError, IndexError):
        return None


def calculate_volumes(scheme):
    """Les durées sont en minutes, les distances des intervalles en mètres."""
    duration = 0.0
    distance = 0.0
    distance_known = True
    for block in scheme:
        if not isinstance(block, dict) or not isinstance(block.get('intervals', []), list):
            raise ValueError('Structure de séance invalide')
        repetitions = block.get('repetitions', 1)
        if not isinstance(repetitions, int) or repetitions < 1:
            raise ValueError('Nombre de répétitions invalide')
        for interval in block.get('intervals', []):
            if not isinstance(interval, dict):
                raise ValueError('Intervalle invalide')
            minutes = interval.get('duration')
            km = interval.get('distance')
            if any(value is not None and (not isinstance(value, (int, float)) or value < 0) for value in (minutes, km)):
                raise ValueError('Volume de séance invalide')
            km = km / 1000 if km is not None else None
            paces = [_pace_minutes(interval.get(key)) for key in ('pace_min', 'pace_max')]
            paces = [pace for pace in paces if pace is not None]
            pace = sum(paces) / len(paces) if paces else None
            if minutes is None and km is not None and pace:
                minutes = km * pace
            if minutes is None:
                raise ValueError('Une durée ou une distance avec allure est nécessaire pour chaque intervalle')
            if km is None and minutes is not None and pace:
                km = minutes / pace
            duration += (minutes or 0) * repetitions
            if km is None:
                distance_known = False
            else:
                distance += km * repetitions
    return round(duration), round(distance, 3) if distance_known else None