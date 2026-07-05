import os
import sys
import json
import ollama
import re

# Configuration des chemins
METHOD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../0.IAChronicleDetection/0.TranscriptionAndLLMMethod"))
sys.path.append(METHOD_DIR)

try:
    from detect import transcribe_audio
except ImportError as e:
    print(f"Warning: Could not import detection modules from {METHOD_DIR}: {e}")

class Wrapper:
    def __init__(self, model="mistral"):
        self.model = model
        self.prompt_path = os.path.join(METHOD_DIR, "prompt.txt")

    def timecode_to_seconds(self, tc):
        """Convertit HH:MM:SS,mmm ou MM:SS.mmm en secondes"""
        try:
            tc = tc.replace(',', '.')
            parts = tc.split(':')
            if len(parts) == 3:
                h, m, s = parts
                return int(h) * 3600 + int(m) * 60 + float(s)
            elif len(parts) == 2:
                m, s = parts
                return int(m) * 60 + float(s)
            return float(tc)
        except:
            return 0.0

    def process_stream(self, audio_path, buffer_size_seconds=None):
        """
        Implémentation de l'interface standard.
        Cette approche est 'Global', elle prend toute la transcription d'un coup.
        """
        if not os.path.exists(self.prompt_path):
            print(f"Error: Prompt file not found at {self.prompt_path}")
            return []

        # 1. Transcription complète
        srt_content = transcribe_audio(audio_path)
        
        # 2. Préparation du prompt
        with open(self.prompt_path, 'r', encoding='utf-8') as f:
            prompt_template = f.read()
        
        # Si le template contient un placeholder, on l'utilise
        if "[TRANSCRIPTION]" in prompt_template:
            full_prompt = prompt_template.replace("[TRANSCRIPTION]", srt_content)
        else:
            # Sinon on l'ajoute à la fin
            full_prompt = prompt_template + "\n\nTranscription à analyser :\n" + srt_content

        # 3. Appel LLM
        try:
            response = ollama.chat(model=self.model, messages=[
                {'role': 'user', 'content': full_prompt}
            ])
            content = response['message']['content']
            
            # 4. Parsing de la réponse (tentative d'extraction JSON ou format structuré)
            detections = []
            
            # Extraction JSON si présent
            json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
            if not json_match:
                json_match = re.search(r'\[\s*{.*}\s*\]', content, re.DOTALL)
                
            if json_match:
                json_str = json_match.group(1) if json_match.lastindex else json_match.group(0)
                try:
                    data = json.loads(json_str)
                    for item in data:
                        start = self.timecode_to_seconds(item.get("timecode_debut", "0"))
                        end = self.timecode_to_seconds(item.get("timecode_fin", "0"))
                        detections.append({
                            "label": item.get("nom", "chronique"),
                            "start": start,
                            "end": end,
                            "detected_at": end, # Approche globale, pas de latence réelle simulée
                            "confidence": 0.9
                        })
                except:
                    pass
            
            # Si pas de JSON, on peut tenter un parsing regex ligne par ligne
            if not detections:
                # Exemple : "Chronique : [Nom] | Début : [00:10] | Fin : [00:20]"
                # Ou juste des lignes de timecodes
                lines = content.split('\n')
                for line in lines:
                    m = re.findall(r'(\d{1,2}:\d{2}(?::\d{2})?(?:[.,]\d+)?)', line)
                    if len(m) >= 2:
                        detections.append({
                            "label": "chronique",
                            "start": self.timecode_to_seconds(m[0]),
                            "end": self.timecode_to_seconds(m[1]),
                            "detected_at": self.timecode_to_seconds(m[1]),
                            "confidence": 0.8
                        })
            
            return detections

        except Exception as e:
            print(f"Error calling LLM: {e}")
            return []
