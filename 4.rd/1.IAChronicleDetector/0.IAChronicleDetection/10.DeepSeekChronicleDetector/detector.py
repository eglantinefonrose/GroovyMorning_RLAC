import os
import json
import requests
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
MODEL = "deepseek-v4-flash"

class ChronicleDetector:
    def __init__(self, chroniques_prompt, max_context=5):
        self.chroniques_prompt = chroniques_prompt
        self.context_buffer = []
        self.max_context = max_context
        self.api_key = DEEPSEEK_API_KEY
        self.last_detected_chronique = None
        
        if not self.api_key:
            raise ValueError("DEEPSEEK_API_KEY is not set in environment variables.")

    def get_dynamic_system_prompt(self):
        last_info = f"\nDERNIÈRE CHRONIQUE DÉTECTÉE : {self.last_detected_chronique}" if self.last_detected_chronique else ""
        
        return f"""Tu es un expert radio chargé de détecter le début exact des chroniques.
Tu reçois un flux de phrases. Ta mission est de dire si la TOUTE DERNIÈRE phrase reçue marque le début d'une chronique.

Liste des chroniques à surveiller (dans l'ordre) :
{json.dumps(self.chroniques_prompt, ensure_ascii=False)}
{last_info}

DÉFINITIONS CRUCIALES :
- ANNONCE / TEASING (À IGNORER) : L'animateur annonce ce qui va arriver PLUS TARD ("Tout à l'heure à 8h20...", "On en parlera avec notre invité après le journal..."). Le futur est utilisé.
- LANCEMENT RÉEL (À DÉTECTER) : C'est le moment précis où la chronique commence MAINTENANT.

RÈGLE D'OR :
- Une chronique ne peut pas être détectée deux fois de suite. Si le lancement s'étale sur plusieurs phrases, seul le TOUT PREMIER segment doit être marqué comme 'detecte: true'.

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

    def analyze_sentence(self, sentence):
        """Appelle l'API DeepSeek pour analyser une phrase avec son contexte."""
        url = "https://api.deepseek.com/chat/completions"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        context_text = "\n".join(self.context_buffer)
        user_content = f"CONTEXTE PRÉCÉDENT :\n{context_text}\n\nNOUVELLE PHRASE À ANALYSER :\n{sentence}"
        
        data = {
            "model": MODEL,
            "messages": [
                {"role": "system", "content": self.get_dynamic_system_prompt()},
                {"role": "user", "content": user_content}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0,
            "max_tokens": 1000
        }
        
        try:
            response = requests.post(url, headers=headers, json=data)
            if response.status_code != 200:
                print(f"\n[ERREUR API] Status {response.status_code}: {response.text}")
                return {"detecte": False}
                
            result = response.json()
            content_str = result["choices"][0]["message"]["content"].strip()
            content = json.loads(content_str)
            
            # Si détecté, on met à jour la dernière chronique pour éviter les doublons
            if content.get("detecte"):
                self.last_detected_chronique = content.get("chronique")

            # Mise à jour du buffer de contexte
            self.context_buffer.append(sentence)
            if len(self.context_buffer) > self.max_context:
                self.context_buffer.pop(0)
                
            return content
        except Exception as e:
            print(f"\n[ERREUR DETECTEUR] {e}")
            return {"detecte": False}
