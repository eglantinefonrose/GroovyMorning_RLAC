import re
import json
import subprocess
from typing import List, Dict, Tuple
import time


class LLMAdDetector:
    """Détecteur de publicités avec Ollama - Version corrigée"""

    def __init__(self, model_name: str = "mistral"):
        self.model_name = model_name
        self.ollama_available = False
        self.check_ollama()

    def check_ollama(self):
        """Vérifie et démarre Ollama si nécessaire"""
        import subprocess
        import socket

        # Vérifie si Ollama est en cours d'exécution
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('127.0.0.1', 11434))
        sock.close()

        if result != 0:
            print("\n⚠️ Ollama n'est pas démarré!")
            print("\nDémarrage d'Ollama...")
            try:
                # Démarre Ollama en arrière-plan
                subprocess.Popen(["ollama", "serve"],
                                 stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
                time.sleep(3)  # Attend le démarrage
                print("✅ Ollama démarré")
            except FileNotFoundError:
                print("\n❌ Ollama n'est pas installé!")
                print("\n📥 Installation d'Ollama:")
                print("   curl -fsSL https://ollama.com/install.sh | sh")
                print("   ollama pull mistral")
                return False

        # Vérifie si le modèle existe
        try:
            result = subprocess.run(["ollama", "list"],
                                    capture_output=True,
                                    text=True)
            if self.model_name not in result.stdout:
                print(f"\n⚠️ Modèle '{self.model_name}' non trouvé!")
                print(f"\n📥 Téléchargement du modèle {self.model_name}...")
                subprocess.run(["ollama", "pull", self.model_name])
                print(f"✅ Modèle {self.model_name} téléchargé")
        except:
            pass

        self.ollama_available = True
        return True

    def parse_srt(self, file_path: str) -> List[Dict]:
        """Parse un fichier SRT"""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Pattern SRT
        pattern = r'(\d+)\n(\d{2}:\d{2}:\d{2}),(\d{3}) --> (\d{2}:\d{2}:\d{2}),(\d{3})\n(.*?)(?=\n\d+\n|\Z)'
        matches = re.findall(pattern, content, re.DOTALL)

        segments = []
        for match in matches:
            num, start_hms, start_ms, end_hms, end_ms, text = match
            text = ' '.join(text.strip().split('\n'))
            text = re.sub(r'<[^>]+>', '', text)

            if text.strip():  # Ignore les segments vides
                segments.append({
                    'id': int(num),
                    'start': f"{start_hms}.{start_ms}",
                    'end': f"{end_hms}.{end_ms}",
                    'text': text
                })

        print(f"📄 Fichier parsé: {len(segments)} segments")
        return segments

    def call_ollama(self, prompt: str) -> str:
        """Appelle Ollama avec subprocess (plus fiable que l'API HTTP)"""
        try:
            # Utilise la commande ollama run
            cmd = ["ollama", "run", self.model_name]
            process = subprocess.Popen(cmd,
                                       stdin=subprocess.PIPE,
                                       stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE,
                                       text=True)

            stdout, stderr = process.communicate(input=prompt, timeout=60)

            if process.returncode == 0:
                return stdout
            else:
                print(f"❌ Erreur Ollama: {stderr}")
                return ""

        except subprocess.TimeoutExpired:
            print("⚠️ Temps d'attente dépassé")
            process.kill()
            return ""
        except Exception as e:
            print(f"❌ Erreur: {e}")
            return ""

    def detect_ads_with_llm(self, segments: List[Dict]) -> List[Dict]:
        """Détecte les publicités avec le LLM"""
        if not self.ollama_available:
            print("❌ Ollama non disponible")
            return []

        print(f"\n🤖 Analyse avec {self.model_name}...")

        # Prépare la transcription (format compact pour économiser les tokens)
        transcript_lines = []
        for seg in segments:
            transcript_lines.append(f"[{seg['start']}] {seg['text']}")

        full_transcript = "\n".join(transcript_lines)

        # Prompt optimisé
        prompt = f"""Analyse cette transcription radio et identifie les segments publicitaires.

Transcription:
{full_transcript}

Tâche: Retourne UNIQUEMENT une liste JSON des publicités trouvées.
Format: {{"ads": [{{"start": "timestamp", "end": "timestamp"}}]}}

Règles: Une publicité contient des promotions, offres spéciales, appels à l'action, 
ou des mots comme "offre", "promotion", "réduction", "gratuit", "exclusif", "code promo".

Si aucune publicité: {{"ads": []}}

Ne retourne que le JSON, rien d'autre."""

        print("   Analyse en cours (cela peut prendre 20-30 secondes)...")
        response = self.call_ollama(prompt)

        # Extrait le JSON
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group())
                return data.get('ads', [])
            except json.JSONDecodeError as e:
                print(f"⚠️ Erreur parsing JSON: {e}")
                return []

        print("⚠️ Aucune réponse JSON valide")
        return []

    def detect_with_keywords_fallback(self, segments: List[Dict]) -> List[Dict]:
        """Méthode de secours basée sur mots-clés (si LLM non dispo)"""
        ad_keywords = [
            'offre', 'promotion', 'réduction', 'gratuit', 'exclusif',
            'profitez', 'maintenant', 'limitée', 'remise', 'code promo',
            'bon plan', 'occasion unique', 'ne ratez pas', 'vente flash',
            'économisez', 'livraison', 'commandez', 'abonnez-vous'
        ]

        ads = []
        for seg in segments:
            text_lower = seg['text'].lower()
            if any(keyword in text_lower for keyword in ad_keywords):
                ads.append({
                    'start': seg['start'],
                    'end': seg['end']
                })

        return ads

    def merge_ads(self, ads: List[Dict], gap_seconds: float = 10.0) -> List[Dict]:
        """Fusionne les publicités consécutives"""
        if not ads:
            return []

        def to_seconds(timestamp: str) -> float:
            parts = timestamp.split(':')
            if len(parts) == 3:
                sec_parts = parts[2].split('.')
                seconds = int(sec_parts[0])
                ms = int(sec_parts[1]) if len(sec_parts) > 1 else 0
                return int(parts[0]) * 3600 + int(parts[1]) * 60 + seconds + ms / 1000
            return 0

        # Trie par timestamp
        ads_sorted = sorted(ads, key=lambda x: to_seconds(x['start']))

        merged = []
        current = ads_sorted[0].copy()

        for ad in ads_sorted[1:]:
            current_end = to_seconds(current['end'])
            next_start = to_seconds(ad['start'])

            if next_start - current_end <= gap_seconds:
                current['end'] = ad['end']
            else:
                merged.append(current)
                current = ad.copy()

        merged.append(current)
        return merged

    def print_results(self, ads: List[Dict]):
        """Affiche les résultats"""
        if not ads:
            print("\n❌ Aucune publicité détectée")
            return

        print("\n" + "=" * 80)
        print(f"📢 {len(ads)} plage(s) publicitaire(s) détectée(s):")
        print("=" * 80)

        total_duration = 0
        for i, ad in enumerate(ads, 1):
            def to_seconds(t):
                parts = t.split(':')
                sec_parts = parts[2].split('.')
                return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(sec_parts[0]) + (
                    int(sec_parts[1]) if len(sec_parts) > 1 else 0) / 1000

            duration = to_seconds(ad['end']) - to_seconds(ad['start'])
            total_duration += duration

            print(f"\n{i}. ⏰ {ad['start']} → {ad['end']}")
            print(f"   📏 Durée: {duration:.1f} secondes")

        print("\n" + "=" * 80)
        print(f"📊 Durée totale: {total_duration:.1f} secondes ({total_duration / 60:.1f} minutes)")

    def export_results(self, ads: List[Dict], filename: str = "publicites.json"):
        """Exporte les résultats"""
        output = {
            'method': f'LLM ({self.model_name})',
            'total_ads': len(ads),
            'ads': ads
        }
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        print(f"\n💾 Résultats exportés dans {filename}")


def main():
    filename = "10241-01.12.2025-ITEMA_24328152-2025F10761S0335-NET_MFI_9428D60B-C293-49F7-9A16-1289E7C0CC0D-22-525c32bf42fbeb1c5500fbe2a353095f_transcription.srt"

    print("=" * 80)
    print("🤖 DÉTECTEUR DE PUBLICITÉS AVEC LLM LOCAL")
    print("=" * 80)

    try:
        # Initialise le détecteur
        detector = LLMAdDetector(model_name="mistral")

        # Parse le fichier
        print(f"\n📂 Chargement: {filename}")
        segments = detector.parse_srt(filename)

        if not segments:
            print("❌ Aucun segment trouvé")
            return

        print(f"\n📝 Transcription chargée: {len(segments)} segments")
        print(f"   Premier segment: {segments[0]['text'][:50]}...")

        # Demande quelle méthode utiliser
        print("\n🔍 Méthodes disponibles:")
        print("   1. LLM (Mistral) - Plus intelligent mais plus lent")
        print("   2. Mots-clés - Plus rapide, sans installation")

        choice = input("\nChoisis une méthode (1-2, défaut=2): ").strip()

        if choice == "1":
            # Méthode LLM
            ads = detector.detect_ads_with_llm(segments)
            if not ads:
                print("\n⚠️ Le LLM n'a rien détecté, utilisation de la méthode mots-clés...")
                ads = detector.detect_with_keywords_fallback(segments)
        else:
            # Méthode mots-clés (recommandée pour commencer)
            print("\n🔍 Utilisation de la méthode par mots-clés...")
            ads = detector.detect_with_keywords_fallback(segments)

        # Fusionne les publicités adjacentes
        if ads:
            ads = detector.merge_ads(ads)

        # Affiche les résultats
        detector.print_results(ads)

        # Exporte
        if ads:
            detector.export_results(ads)

            # Export timestamps simples
            with open("timestamps_publicites.txt", "w", encoding='utf-8') as f:
                f.write("TIMESTAMPS DES PUBLICITÉS\n")
                f.write("=" * 30 + "\n\n")
                for i, ad in enumerate(ads, 1):
                    f.write(f"{i}. {ad['start']} --> {ad['end']}\n")
            print("💾 Timestamps exportés dans timestamps_publicites.txt")
        else:
            print("\n💡 Aucune publicité détectée. Vérifie que le fichier contient bien des publicités.")
            print("   Pour tester, assure-toi que la transcription a des mots comme 'offre', 'promotion', etc.")

    except FileNotFoundError:
        print(f"\n❌ Fichier non trouvé: {filename}")
        print("   Vérifie que le fichier existe dans le répertoire courant")
    except Exception as e:
        print(f"\n❌ Erreur: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()