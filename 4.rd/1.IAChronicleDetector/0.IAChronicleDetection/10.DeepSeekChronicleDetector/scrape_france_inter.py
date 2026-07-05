import requests
import re
import json
import base64
from datetime import datetime

# Configuration
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:151.0) Gecko/20100101 Firefox/151.0',
    'Accept': '*/*',
    'Content-Type': 'application/json',
}

_cached_hash = None

def get_rpc_hash(date_str=None):
    """Récupère dynamiquement le hash RPC (ex: 1vzv7fl) depuis la page d'accueil."""
    global _cached_hash
    if _cached_hash:
        return _cached_hash
    
    try:
        # On tente de trouver le hash dans la page de la grille
        url = "https://www.radiofrance.fr/franceinter/grille-programmes"
        if date_str:
            try:
                dt = datetime.strptime(date_str, "%Y-%m-%d")
                url += f"?date={dt.strftime('%d-%m-%Y')}"
            except:
                pass
        
        print(f"[SCRAPER] Récupération du hash RPC depuis : {url}")
        res = requests.get(url, headers=HEADERS, timeout=5)
        res.raise_for_status()
        
        # Pattern 1: "HASH/loadProgramGrid" (nouveau format JSON)
        match = re.search(r'["\']([a-z0-9]+)/loadProgramGrid', res.text)
        if match:
            _cached_hash = match.group(1)
            return _cached_hash

        # Pattern 2: /_app/remote/HASH/loadProgramGrid
        match = re.search(r'/_app/remote/([a-z0-9]+)/loadProgramGrid', res.text)
        if match:
            _cached_hash = match.group(1)
            return _cached_hash
        
        # Fallback regex: chercher n'importe quel hash après /_app/remote/
        match = re.search(r'/_app/remote/([a-z0-9]+)/', res.text)
        if match:
            _cached_hash = match.group(1)
            return _cached_hash
    except Exception as e:
        print(f"[SCRAPER] Erreur lors de la récupération du hash RPC : {e}")
    
    return "10b9rtu" # Fallback actuel au 2026-07-03

def get_matinale_step_ids(date_str=None):
    """
    Récupère dynamiquement les IDs potentiels du segment 'Matinale' pour aujourd'hui
    en interrogeant la grille des programmes via RPC.
    """
    if not date_str:
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        day_of_week = now.weekday()
    else:
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            day_of_week = dt.weekday()
        except:
            day_of_week = datetime.now().weekday()

    rpc_hash = get_rpc_hash(date_str)
    is_friday = day_of_week == 4 # 4 = Vendredi
    
    # Construction du payload pour loadProgramGrid
    # Note : Radio France RPC semble préférer YYYY-MM-DD dans le payload JSON
    payload_raw = [["__skrao", 1], {"brand": 2, "date": 3}, "franceinter", date_str]
    payload_b64 = base64.b64encode(json.dumps(payload_raw, separators=(',', ':')).encode()).decode()
    
    url_grid = f"https://www.radiofrance.fr/_app/remote/{rpc_hash}/loadProgramGrid?payload={payload_b64}"
    
    potential_ids = []
    try:
        response = requests.get(url_grid, headers=HEADERS, timeout=10)
        response.raise_for_status()
        data = response.json()
        items = json.loads(data.get('result', '[]'))
        
        # Sur France Inter, la matinale s'appelle "Le 7/10" en semaine et "Le 6/9" le week-end.
        # Règle spéciale utilisateur : Si on est vendredi, on cherche spécifiquement "Le 6/9".
        target_programs = ["Le 7/10", "Le 6/9", "Le 7/9", "La Grande matinale"]
        if is_friday:
            target_programs = ["Le 6/9"] + target_programs
        
        for i, item in enumerate(items):
            if isinstance(item, str) and any(tp in item for tp in target_programs):
                # On collecte tous les UUIDs à proximité (souvent ConceptID, StepID, PlayerID)
                for offset in range(-15, 15):
                    idx = i + offset
                    if 0 <= idx < len(items):
                        val = items[idx]
                        if isinstance(val, str) and re.match(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', val):
                            if val not in potential_ids:
                                potential_ids.append(val)
    except Exception as e:
        print(f"[SCRAPER] Erreur lors de la recherche de l'ID matinale : {e}")
    
    # Fallback si rien trouvé
    if not potential_ids:
        potential_ids = ["4d701356-e8ea-40fc-b4e8-030bbd23ddce"]
    
    return potential_ids

def fetch_chroniques_from_rpc(date_str=None):
    """Récupère et parse les chroniques via l'appel RPC complet."""
    step_ids = get_matinale_step_ids(date_str)
    
    # On tente avec le hash détecté, sinon on essaie un fallback connu
    rpc_hash_detected = get_rpc_hash(date_str)
    hashes_to_try = [rpc_hash_detected, "1vzv7fl", "10b9rtu"]
    
    items = []
    last_error = None
    
    # On essaie toutes les combinaisons Hash x UUID jusqu'à ce qu'on ait des résultats
    for rpc_hash in hashes_to_try:
        for sid in step_ids:
            payload_raw = [["__skrao", 1], {"brand": 2, "parentStep": 3}, "franceinter", sid]
            payload_b64 = base64.b64encode(json.dumps(payload_raw, separators=(',', ':')).encode()).decode()
            url_rpc = f'https://www.radiofrance.fr/_app/remote/{rpc_hash}/loadChroniclesGrid?payload={payload_b64}'
            
            try:
                response = requests.get(url_rpc, headers=HEADERS, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    res_json = json.loads(data.get('result', '[]'))
                    if res_json and isinstance(res_json[0], list) and len(res_json[0]) > 0:
                        items = res_json
                        break # Succès !
                else:
                    last_error = f"{response.status_code} {response.reason}"
            except Exception as e:
                last_error = str(e)
        if items: break
            
    if not items or not isinstance(items[0], list):
        if last_error:
            print(f"[SCRAPER] Erreur RPC (après plusieurs essais) : {last_error}")
        return []

    start_indices = items[0]
    chroniques_ordered = []
    seen = set()
    keywords = ["journal", "édito", "billet", "chronique", "invité", "géopolitique", "mots nouveaux", "prouvé", "80 secondes", "oeil de", "un été avec", "la météo", "le grand entretien"]

    def normalize(text):
        t = text.lower()
        t = t.replace("é", "e").replace("è", "e").replace("ê", "e").replace("à", "a").replace("î", "i").replace("ï", "i")
        return t

    for start_idx in start_indices:
        time_str = "??h??"
        for offset in range(1, 15):
            idx = start_idx + offset
            if idx < len(items):
                val = items[idx]
                if isinstance(val, str) and re.match(r'\d{2}h\d{2}', val):
                    time_str = val
                    break
        
        block_title = ""
        for offset in range(1, 12):
            idx = start_idx + offset
            if idx < len(items):
                obj = items[idx]
                if isinstance(obj, dict) and 'title' in obj:
                    title_idx = obj['title']
                    if title_idx < len(items) and isinstance(items[title_idx], str):
                        block_title = items[title_idx]
                        break
        
        if not block_title:
            for offset in range(1, 20):
                idx = start_idx + offset
                if idx < len(items):
                    val = items[idx]
                    if isinstance(val, str) and len(val) > 3 and not val.startswith('/') and '©' not in val and not re.match(r'\d{2}h\d{2}', val):
                        if any(kw in normalize(val) for kw in keywords):
                            block_title = val
                            break

        if block_title:
            title_clean = block_title.strip()
            if "journal de 0" in title_clean.lower():
                title_clean = re.sub(r'[Ll]e journal de 0(\d)h[0-9]+.*', r'Le journal de \1h', title_clean)
            elif "journal de " in title_clean.lower():
                title_clean = re.sub(r'[Ll]e journal de (\d+)h[0-9]+.*', r'Le journal de \1h', title_clean)

            if title_clean not in seen:
                chroniques_ordered.append({"time": time_str.replace('h', ':'), "title": title_clean})
                seen.add(title_clean)

    return chroniques_ordered

def get_chroniques(date_str=None):
    return fetch_chroniques_from_rpc(date_str)

if __name__ == "__main__":
    import sys
    date_to_fetch = sys.argv[1] if len(sys.argv) > 1 else None
    res = get_chroniques(date_to_fetch)
    for c in res:
        print(f"{c['time']} | {c['title']}")
