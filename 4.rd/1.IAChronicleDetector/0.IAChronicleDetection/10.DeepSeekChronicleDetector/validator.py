import re
from datetime import datetime, timedelta

def time_to_minutes(t_str):
    """Convertit HH:MM ou HHhMM en minutes depuis minuit."""
    try:
        t_str = t_str.replace('h', ':')
        h, m = map(int, t_str.split(':'))
        return h * 60 + m
    except:
        return 0

def minutes_to_time(minutes):
    """Convertit des minutes en HH:MM."""
    h = int(minutes // 60) % 24
    m = int(minutes % 60)
    return f"{h:02d}:{m:02d}"

class ChronicleValidator:
    def __init__(self, theoretical_schedule):
        """
        theoretical_schedule: Liste de dicts [{"time": "07h00", "title": "..."}]
        """
        self.schedule = {}
        for item in theoretical_schedule:
            name = self.normalize_name(item['title'])
            self.schedule[name] = {
                "original_name": item['title'],
                "time": item['time'],
                "minutes": time_to_minutes(item['time'])
            }
        
        self.validated_names = set()
        self.last_theo_minutes = -1

    def normalize_name(self, name):
        """Nettoyage du nom pour le matching."""
        name = name.lower()
        name = re.sub(r'[^\w\s\']', '', name).strip()
        return name

    def find_best_match(self, detected_name):
        """Trouve la chronique correspondante dans la grille théorique."""
        detected_norm = self.normalize_name(detected_name)
        
        # Tri par longueur décroissante pour éviter les sous-chaînes
        keys = sorted(self.schedule.keys(), key=len, reverse=True)
        for k in keys:
            if k in detected_norm or detected_norm in k:
                return k
        return None

    def validate(self, detected_name, audio_seconds, start_time_str="07:00"):
        """
        Applique les règles de validation de check_schedule.py.
        """
        start_minutes = time_to_minutes(start_time_str)
        current_wall_minutes = start_minutes + (audio_seconds / 60)
        current_wall_time = minutes_to_time(current_wall_minutes)

        match_key = self.find_best_match(detected_name)
        
        if not match_key:
            return False, "HORS GRILLE", current_wall_time, "-"

        theo_info = self.schedule[match_key]
        theo_minutes = theo_info['minutes']
        diff = current_wall_minutes - theo_minutes
        diff_str = f"{int(diff):+} min"

        # RÈGLE 1 : Trop tôt (> 5 min avant l'horaire théorique)
        if diff < -5:
            return False, "REJETÉ (TROP TÔT)", current_wall_time, diff_str

        # RÈGLE 2 : Déjà validée (doublon)
        if match_key in self.validated_names:
            return False, "REJETÉ (DÉJÀ PASSÉ)", current_wall_time, diff_str

        # RÈGLE 3 : Ordre chronologique de la grille
        if theo_minutes < self.last_theo_minutes:
            return False, "REJETÉ (HORS ORDRE)", current_wall_time, diff_str

        # VALIDATION
        self.validated_names.add(match_key)
        self.last_theo_minutes = theo_minutes
        return True, "VALIDÉ", current_wall_time, diff_str
