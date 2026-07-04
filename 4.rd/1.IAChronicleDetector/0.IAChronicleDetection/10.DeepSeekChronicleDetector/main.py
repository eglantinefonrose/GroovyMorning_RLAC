"""
Détection de début de chroniques en flux simulé via DeepSeek.
"""

import os
import json
import re
import time
import sys
import requests
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()

from scrape_france_inter import get_chroniques

# Configuration
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
MODEL = "deepseek-v4-flash"

if not DEEPSEEK_API_KEY:
    print("[ERREUR] La variable d'environnement DEEPSEEK_API_KEY n'est pas définie.")
    sys.exit(1)

# Chargement dynamique des chroniques du jour
print("Chargement dynamique des chroniques France Inter...")
CHRONIQUES_DATA = get_chroniques()

if not CHRONIQUES_DATA:
    print("[ALERTE] Aucune chronique récupérée, utilisation d'une liste par défaut.")
    CHRONIQUES_DATA = [
        {"time": "07h00", "title": "Le journal de 7h"},
        {"time": "08h00", "title": "Le journal de 8h"},
        {"time": "09h00", "title": "Le journal de 9h"},
        {"time": "08h20", "title": "L'invité de 8h20"}
    ]

# Option pour inclure ou non les horaires dans le prompt
INCLUDE_SCHEDULE = "no-schedule" not in sys.argv

if INCLUDE_SCHEDULE:
    # On garde les dicts {time, title}
    CHRONIQUES_PROMPT = CHRONIQUES_DATA
else:
    # On ne garde que les titres
    if CHRONIQUES_DATA and isinstance(CHRONIQUES_DATA[0], dict):
        CHRONIQUES_PROMPT = [c['title'] for c in CHRONIQUES_DATA]
    else:
        CHRONIQUES_PROMPT = CHRONIQUES_DATA

SYSTEM_PROMPT = f"""Tu es un expert radio chargé de détecter le début exact des chroniques.
Tu reçois un flux de phrases. Ta mission est de dire si la TOUTE DERNIÈRE phrase reçue marque le début d'une chronique.

Liste des chroniques à surveiller (dans l'ordre) :
{json.dumps(CHRONIQUES_PROMPT, ensure_ascii=False)}

DÉFINITIONS CRUCIALES :
- ANNONCE / TEASING (À IGNORER) : L'animateur annonce ce qui va arriver PLUS TARD ("Tout à l'heure à 8h20...", "On en parlera avec notre invité après le journal..."). Le futur est utilisé.
- LANCEMENT RÉEL (À DÉTECTER) : C'est le moment précis où la chronique commence MAINTENANT.

EXEMPLES DE RÉFÉRENCE :

1. ANNONCE (À IGNORER) :
Phrase : "À 8h20, Raphaël Glucksmann sera notre invité dans le grand entretien."
JSON : {{
  "raisonnement": "C'est une annonce pour un segment futur (8h20).",
  "detecte": false,
  "chronique": null,
  "phrase": null
}}

2. LANCEMENT RÉEL (À DÉTECTER) :
Phrase : "Il est 8h20, l'invité de 8h20, Benjamin Duhamel vous recevez Raphaël Glucksmann."
JSON : {{
  "raisonnement": "Lancement immédiat, l'heure coïncide et l'invité est introduit.",
  "detecte": true,
  "chronique": "l'invité de 8h20",
  "phrase": "Il est 8h20, l'invité de 8h20, Benjamin Duhamel vous recevez Raphaël Glucksmann."
}}

CONSIGNES :
1. Analyse le contexte précédent (5 phrases) pour détecter les indicateurs temporels.
2. Réponds UNIQUEMENT en JSON.

Format de réponse attendu :
{{
  "raisonnement": "Analyse brève",
  "detecte": true/false,
  "chronique": "Nom exact ou null",
  "phrase": "La phrase exacte ou null"
}}
"""

def split_sentences(text):
    """Découpage simple en phrases pour simuler un flux de transcription."""
    # Split sur . ! ? suivi d'un espace, tout en préservant l'heure (ex: 7h50)
    sentences = re.split(r'(?<=[.!?])\s+', text)
    return [s.strip() for s in sentences if s.strip()]

def call_deepseek_live(sentence, context_buffer):
    """Appelle l'API DeepSeek via requests (compatible OpenAI)."""
    url = "https://api.deepseek.com/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    
    context_text = "\n".join(context_buffer)
    user_content = f"CONTEXTE PRÉCÉDENT :\n{context_text}\n\nNOUVELLE PHRASE À ANALYSER :\n{sentence}"
    
    data = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content}
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0,
        "max_tokens": 1000
    }
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)
        if response.status_code != 200:
            print(f"\n[ERREUR API] Status {response.status_code}: {response.text}")
            return {"detecte": False}
            
        result = response.json()
        if not result.get("choices"):
            print(f"\n[ERREUR] Aucune réponse (choices vide) : {result}")
            return {"detecte": False}
            
        content_str = result["choices"][0]["message"]["content"].strip()
        
        # Nettoyage si le modèle renvoie du markdown
        if content_str.startswith("```"):
            lines = content_str.split("\n")
            if lines[0].startswith("```"):
                content_str = "\n".join(lines[1:-1]) if lines[-1].startswith("```") else "\n".join(lines[1:])
            if content_str.startswith("json"):
                content_str = content_str[4:].strip()

        if not content_str:
            print("\n[ERREUR] Le contenu de la réponse est vide.")
            return {"detecte": False}
            
        return json.loads(content_str)
    except Exception as e:
        print(f"\n[ERREUR] {e}")
        return {"detecte": False}

def simulate_audio_stream(file_path):
    """Lit le fichier et simule l'arrivée des phrases une par une."""
    print(f"Lecture du fichier : {file_path}")
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            full_text = f.read()
    except FileNotFoundError:
        print(f"Erreur : le fichier {file_path} est introuvable.")
        return []
    
    sentences = split_sentences(full_text)
    print(f"Simulation lancée : {len(sentences)} phrases à traiter.")
    print(f"Modèle utilisé : {MODEL}\n")
    
    context_buffer = []
    max_context = 5
    detections = []

    for i, current_sentence in enumerate(sentences):
        # Progression
        sys.stdout.write(f"\rTraitement phrase {i+1}/{len(sentences)}... ")
        sys.stdout.flush()
        
        result = call_deepseek_live(current_sentence, context_buffer)
        
        if result.get("detecte"):
            chronique = result.get("chronique")
            phrase = result.get("phrase")
            print(f"\n\n[DÉTECTION] 🔔 Chronique trouvée : {chronique}")
            print(f"Raisonnement : {result.get('raisonnement')}")
            print(f"Phrase : \"{phrase}\"")
            print("-" * 50)
            detections.append({
                "index": i,
                "result": result
            })
            
        context_buffer.append(current_sentence)
        if len(context_buffer) > max_context:
            context_buffer.pop(0)
            
    print(f"\nFin de la simulation. {len(detections)} chroniques détectées.")
    return detections

if __name__ == "__main__":
    if "show-prompt" in sys.argv:
        print("\n" + "="*50)
        print(" SYSTEM PROMPT ")
        print("="*50)
        print(SYSTEM_PROMPT)
        print("="*50 + "\n")
        sys.exit(0)

    TRANSCRIPTION_FILE = "full_show_transcription.txt"
    all_detections = simulate_audio_stream(TRANSCRIPTION_FILE)
    
    if all_detections:
        with open("detections_live_deepseek.json", "w", encoding="utf-8") as f:
            json.dump(all_detections, f, ensure_ascii=False, indent=2)
