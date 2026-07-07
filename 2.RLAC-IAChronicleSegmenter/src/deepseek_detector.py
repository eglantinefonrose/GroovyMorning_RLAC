import os
import json
import requests
from datetime import datetime, timedelta

class DeepSeekDetector:
    def __init__(self, api_key, model="deepseek-chat", schedule=None, is_simulation=False):
        self.api_key = api_key
        self.model = model
        self.schedule = schedule or []
        self.validated_chroniques = set()
        self.last_theo_minutes = -1
        self.is_simulation = is_simulation
        
        # Déterminer l'heure de début du flux (pour la simulation)
        # On prend l'heure de la première chronique de la grille (ex: 06:00 ou 07:00)
        self.show_start_minutes = 420 # Par défaut 07:00 (7*60)
        if self.schedule:
            first_time = self.schedule[0].get("time", "07:00")
            self.show_start_minutes = self._time_to_minutes(first_time)
            # Si c'est 06:11 par exemple, on arrondit à l'heure pile (06:00)
            if self.show_start_minutes > 0:
                self.show_start_minutes = (self.show_start_minutes // 60) * 60

        self.system_prompt = self._generate_system_prompt()
        print(f"[DeepSeekDetector] Initialized. Model: {self.model}, Simu: {self.is_simulation}, Base Time: {self.show_start_minutes//60}h")

    def _generate_system_prompt(self):
        chroniques_json = json.dumps(self.schedule, ensure_ascii=False)
        return f"""Tu es un expert radio chargé de détecter le début exact des chroniques.
Tu reçois un flux de phrases. Ta mission est de dire si la TOUTE DERNIÈRE phrase reçue marque le début d'une chronique.

Liste des chroniques à surveiller (dans l'ordre) :
{chroniques_json}

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

    def _time_to_minutes(self, t_str):
        try:
            h, m = map(int, t_str.split(':'))
            return h * 60 + m
        except:
            return 0

    def analyze_sentence(self, sentence, context_buffer, current_time_sec=None):
        """
        Appelle l'API DeepSeek pour analyser une phrase.
        """
        if not self.api_key:
            return {"detecte": False}

        url = "https://api.deepseek.com/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        context_text = "\n".join(context_buffer)
        user_content = f"CONTEXTE PRÉCÉDENT :\n{context_text}\n\nNOUVELLE PHRASE À ANALYSER :\n{sentence}"
        
        data = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_content}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0,
            "max_tokens": 500
        }
        
        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                response = requests.post(url, headers=headers, json=data, timeout=20)
                if response.status_code == 200:
                    result = response.json()
                    if not result.get("choices"):
                        print(f"[DeepSeek Error] No choices in response: {result}")
                        return {"detecte": False}

                    content = result["choices"][0]["message"]["content"].strip()
                    
                    # Nettoyage au cas où le modèle renvoie des blocs de code markdown
                    if content.startswith("```"):
                        content = content.split("```")[1]
                        if content.startswith("json"):
                            content = content[4:].strip()
                    
                    if not content:
                        print("[DeepSeek Error] Empty content in response")
                        return {"detecte": False}

                    try:
                        detection = json.loads(content)
                    except json.JSONDecodeError as je:
                        print(f"[DeepSeek JSON Error] {je}")
                        print(f"Raw content: {content}")
                        return {"detecte": False}
                    
                    if detection.get("detecte"):
                        return self.validate_detection(detection, current_time_sec)
                    
                    return detection
                elif response.status_code == 429:
                    print(f"⚠️ [DeepSeek API] Rate limit (429). Tentative {attempt+1}/{max_retries+1}...")
                    time.sleep(2)
                else:
                    print(f"[DeepSeek API Error] {response.status_code}: {response.text}")
                    return {"detecte": False}
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                print(f"⚠️ [DeepSeek Network Error] {e}. Tentative {attempt+1}/{max_retries+1}...")
                time.sleep(1)
            except Exception as e:
                print(f"[DeepSeek Error] {e}")
                return {"detecte": False}
        
        return {"detecte": False}

    def validate_detection(self, detection, current_time_sec):
        """
        Valide une détection par rapport au planning.
        """
        name = detection.get("chronique", "").lower()
        if not name:
            detection["detecte"] = False
            return detection

        # CALCUL DE L'HEURE COURANTE
        if self.is_simulation and current_time_sec is not None:
            # En simulation, l'heure = Heure de début + secondes écoulées dans le flux
            current_minutes = self.show_start_minutes + (current_time_sec / 60.0)
        else:
            # En live, on utilise l'horloge réelle
            now = datetime.now()
            current_minutes = now.hour * 60 + now.minute

        best_match = None
        theo_minutes = -1
        
        # On trie la grille par longueur de titre décroissante pour éviter les conflits de sous-chaînes
        sorted_schedule = sorted(self.schedule, key=lambda x: len(x.get("title", "")), reverse=True)
        
        for item in sorted_schedule:
            theo_time = item.get("time", "00:00")
            theo_title = item.get("title", "").lower()
            
            if theo_title in name or name in theo_title:
                best_match = item
                theo_minutes = self._time_to_minutes(theo_time)
                break
        
        if not best_match:
            print(f"[DeepSeek] Rejeté: '{name}' non trouvé dans la grille.")
            detection["detecte"] = False
            detection["raison"] = "Hors grille"
            return detection

        diff = current_minutes - theo_minutes
        
        # RÈGLE 1 : Trop tôt (> 1 min avant l'horaire théorique)
        if diff < -1:
            time_info = f"{int(current_minutes//60)}h{int(current_minutes%60):02d}"
            print(f"[DeepSeek] Rejeté: '{name}' trop tôt à {time_info} (Prévu: {best_match.get('time')}, Delta: {diff:.1f} min).")
            detection["detecte"] = False
            detection["raison"] = "Trop tôt"
            return detection
        
        # RÈGLE 2 : Déjà validée (doublon)
        if best_match["title"] in self.validated_chroniques:
            print(f"[DeepSeek] Rejeté: '{name}' déjà passée.")
            detection["detecte"] = False
            detection["raison"] = "Déjà passée"
            return detection
        
        # RÈGLE 3 : Ordre chronologique
        if theo_minutes < self.last_theo_minutes:
            print(f"[DeepSeek] Rejeté: '{name}' hors ordre.")
            detection["detecte"] = False
            detection["raison"] = "Hors ordre"
            return detection

        # VALIDÉ
        log_time = datetime.now().strftime('%H:%M:%S') if not self.is_simulation else f"Flux+{int(current_time_sec)}s"
        print(f"[DeepSeek] VALIDÉ: '{name}' à {log_time} (Ecart: {diff:+.1f} min)")
        self.validated_chroniques.add(best_match["title"])
        self.last_theo_minutes = theo_minutes
        detection["chronique"] = best_match["title"] # Utiliser le nom officiel
        return detection
