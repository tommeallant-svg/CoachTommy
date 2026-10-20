
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

def vma_to_speed_ms(vma_min_km, percentage):
    """
    Convertit un pourcentage de VMA en vitesse m/s.
    vma_min_km: allure VMA en min/km (ex: 4.0 pour 4:00/km)
    percentage: pourcentage (ex: 100)
    """
    if not vma_min_km or not percentage:
        return None
    try:
        # VMA speed in m/s
        vma_speed_ms = 1000.0 / (float(vma_min_km) * 60.0)
        # Apply percentage
        return vma_speed_ms * (float(percentage) / 100.0)
    except (ValueError, ZeroDivisionError):
        return None
