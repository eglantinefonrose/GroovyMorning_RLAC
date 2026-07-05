import os
import sys
import json
import argparse
import requests
import re
import base64
from datetime import datetime

# Logic from scrape_france_inter.py
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
        target_programs = ["Le 7/10", "Le 6/9", "Le 7/9", "La Grande matinale"]
        if is_friday:
            target_programs = ["Le 6/9"] + target_programs
        
        for i, item in enumerate(items):
            if isinstance(item, str) and any(tp in item for tp in target_programs):
                for offset in range(-15, 15):
                    idx = i + offset
                    if 0 <= idx < len(items):
                        val = items[idx]
                        if isinstance(val, str) and re.match(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', val):
                            if val not in potential_ids:
                                potential_ids.append(val)
    except Exception as e:
        print(f"[SCRAPER] Erreur lors de la recherche de l'ID matinale : {e}")
    
    if not potential_ids:
        potential_ids = ["4d701356-e8ea-40fc-b4e8-030bbd23ddce"]
    
    return potential_ids

def fetch_chroniques_from_rpc(date_str=None):
    """Récupère et parse les chroniques via l'appel RPC complet."""
    step_ids = get_matinale_step_ids(date_str)
    rpc_hash_detected = get_rpc_hash(date_str)
    hashes_to_try = [rpc_hash_detected, "1vzv7fl", "10b9rtu"]
    
    items = []
    last_error = None
    
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
                        break
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

# Imports for the rest of audio_detector.py
from detector import ChronicleDetector
from audio_processor import accelerate_audio, map_timestamp, format_timestamp
from transcriber import Transcriber
from validator import ChronicleValidator

def main():
    parser = argparse.ArgumentParser(description="Détection de chroniques radio dans un fichier audio.")
    parser.add_argument("audio_path", help="Chemin vers le fichier audio (mp3, wav, etc.)")
    parser.add_argument("--speed", type=float, default=1.0, help="Facteur d'accélération (ex: 2.0)")
    parser.add_argument("--date", help="Date de l'émission au format YYYY-MM-DD (par défaut: aujourd'hui)")
    parser.add_argument("--start-time", default="07:00", help="Heure de début de l'enregistrement (ex: 07:00)")
    parser.add_argument("--model", default="base", help="Taille du modèle Whisper (tiny, base, small, medium, large-v3)")
    parser.add_argument("--output", default="detections_audio.json", help="Fichier de sortie JSON")
    
    args = parser.parse_args()

    if not args.date:
        args.date = datetime.now().strftime("%Y-%m-%d")

    if not os.path.exists(args.audio_path):
        print(f"[ERREUR] Le fichier {args.audio_path} n'existe pas.")
        sys.exit(1)

    # 1. Chargement de la grille des programmes
    print(f"\n[1/4] Récupération de la grille France Inter ({args.date})...")
    chroniques_data = get_chroniques(args.date)
    if not chroniques_data:
        print("[ALERTE] Aucune chronique récupérée, utilisation d'une liste par défaut.")
        chroniques_data = [
            {"time": "07h00", "title": "Le journal de 7h"},
            {"time": "08h00", "title": "Le journal de 8h"},
            {"time": "08h20", "title": "L'invité de 8h20"}
        ]
    
    print(f"--- {len(chroniques_data)} chroniques trouvées pour le {args.date} ---")
    for c in chroniques_data:
        print(f"  - {c['time']} : {c['title']}")
    print("-" * 30)
    
    # 2. Préparation de l'audio
    print(f"\n[2/4] Préparation de l'audio...")
    processed_audio, is_temp = accelerate_audio(args.audio_path, args.speed)

    try:
        # 3. Initialisation des modules
        print(f"\n[3/4] Initialisation des modèles IA et du validateur...")
        transcriber = Transcriber(model_size=args.model)
        detector = ChronicleDetector(chroniques_data)
        validator = ChronicleValidator(chroniques_data)
        
        detections = []
        
        # 4. Traitement en flux
        print(f"\n[4/4] Analyse en cours (Heure de début : {args.start_time})...")
        print("-" * 100)
        print(f"{'HEURE':<8} | {'CHRONIQUE':<25} | {'ÉCART':<8} | {'STATUT'}")
        print("-" * 100)
        
        for segment in transcriber.transcribe_stream(processed_audio):
            text = segment["text"]
            if not text:
                continue
                
            result = detector.analyze_sentence(text)
            
            if result.get("detecte"):
                chronique_name = result.get("chronique")
                
                # Calcul du timestamp original (secondes écoulées)
                orig_seconds = map_timestamp(segment["start"], args.speed)
                
                # Validation via la grille
                is_valid, status, wall_time, diff_str = validator.validate(
                    chronique_name, 
                    orig_seconds, 
                    args.start_time
                )
                
                print(f"{wall_time:<8} | {chronique_name[:25]:<25} | {diff_str:<8} | {status}")
                
                if is_valid:
                    detections.append({
                        "wall_time": wall_time,
                        "audio_timestamp": format_timestamp(orig_seconds),
                        "chronique": chronique_name,
                        "diff": diff_str,
                        "text": text
                    })

        # Sauvegarde des résultats
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump({
                "file": args.audio_path,
                "date": args.date,
                "speed": args.speed,
                "start_time": args.start_time,
                "detections": detections
            }, f, ensure_ascii=False, indent=2)
            
        if detections:
            print("\n" + "="*60)
            print("   RÉSUMÉ DES CHRONIQUES VALIDÉES")
            print("="*60)
            print(f"{'HEURE':<8} | {'CHRONIQUE':<30} | {'ÉCART'}")
            print("-" * 60)
            for d in detections:
                print(f"{d['wall_time']:<8} | {d['chronique'][:30]:<30} | {d['diff']}")
            print("="*60)
        else:
            print("\nAucune chronique n'a été validée.")

    finally:
        # Nettoyage
        if is_temp and os.path.exists(processed_audio):
            print(f"\n[CLEANUP] Suppression du fichier temporaire : {processed_audio}")
            os.remove(processed_audio)

if __name__ == "__main__":
    main()
