import numpy as np
import os
import time
from dotenv import load_dotenv

# Charger les variables d'environnement depuis .env
load_dotenv()

from scipy import signal
import warnings
import requests
import subprocess
import threading
import queue
import whisper
import unicodedata
from datetime import datetime

# Nouveaux imports pour DeepSeek
try:
    from src.scraper import get_chroniques
    from src.deepseek_detector import DeepSeekDetector
    from src.transcriber import Transcriber
except ImportError:
    from scraper import get_chroniques
    from deepseek_detector import DeepSeekDetector
    from transcriber import Transcriber

warnings.filterwarnings('ignore')

class UnifiedLiveSegmenter:
    def __init__(self, jingles_dir, pipe_path='/tmp/audio_pipe', threshold=0.50, whisper_model="medium", detection_mode="legacy"):
        self.sample_rate = 16000
        self.pipe_path = pipe_path
        self.threshold = threshold
        self.chunk_size = 512 # Latence ultra-faible : 32ms
        self.detection_mode = detection_mode
        
        self.sequence = [
            {"type": "jingle", "name": "journal de 7h", "target": "grande_matinale_jingle_7h.m4a"},
            {"type": "keyword", "name": "Les 80 secondes", "target": "80 secondes"},
            {"type": "jingle",  "name": "Le grand reportage", "target": "grande_matinale_jingle_7h16.m4a"},
            {"type": "jingle",  "name": "Edito media", "target": "grande_matinale_jingle_7h20.m4a"},
            {"type": "jingle",  "name": "Musicaline", "target": "grande_matinale_jingle_7h23.m4a"},
            {"type": "keyword", "name": "Meteo", "target": "météo"},
            {"type": "jingle",  "name": "Le journal de 7h30", "target": "grande_matinale_jingle_7h30.m4a"},
            {"type": "jingle",  "name": "Edito politique", "target": "grande_matinale_jingle_7h43.m4a"},
            {"type": "keyword", "name": "Edito eco", "target": "édito éco"},
            {"type": "jingle",  "name": "L’invite de 7h50", "target": "grande_matinale_jingle_7h50.m4a"}
        ]

        # Initialisation DeepSeek si nécessaire (Déplacée dans run() pour un chargement à l'heure H)
        self.deepseek_detector = None
        
        if self.detection_mode == "legacy":
            print("📻 Mode DETECTION: Legacy (Jingles + Keywords)")

        self.current_step = 0
        self.step_just_changed = True
        
        self.max_history_seconds = 60
        self.buffer_size = self.max_history_seconds * self.sample_rate
        self.audio_buffer = np.zeros(self.buffer_size, dtype=np.float32)
        self.buffer_index = 0
        
        # Buffer dédié à la synchronisation (plus léger : 4000Hz)
        self.sync_sr = 4000
        self.sync_buffer_size = self.max_history_seconds * self.sync_sr
        self.sync_buffer = np.zeros(self.sync_buffer_size, dtype=np.float32)
        self.sync_buffer_index = 0
        self.total_sync_samples = 0
        
        self.transcription_queue = queue.Queue()
        self.whisper_audio_accumulated = bytearray()
        
        self.total_samples_processed = 0
        self.running = True
        
        self.last_chronicle_name = None
        self.last_chronicle_start_time = None
        self.last_status_time = 0
        self.time_offset = 0.0 # Décalage temporel global (delta)
        
        self.load_jingles(jingles_dir)
        
        # Initialisation du moteur de transcription (Kyutai ou Whisper)
        self.use_kyutai = os.environ.get("USE_KYUTAI", "true").lower() == "true"
        provider = os.environ.get("TRANSCRIPTION_PROVIDER", "kyutai_stt" if self.use_kyutai else "whisper")
        
        print(f"🚀 Initialisation du transcripteur (Provider: {provider})...")
        self.transcriber = Transcriber(model_size=whisper_model, provider=provider)
        
        print(f"✅ Système prêt. Chunk: {self.chunk_size} samples")

    def normalize_text(self, text):
        text = text.lower()
        text = unicodedata.normalize('NFD', text).encode('ascii', 'ignore').decode('utf-8')
        return text

    def load_jingles(self, jingles_dir):
        self.jingle_data = {}
        # On ne charge les jingles que si on est en mode legacy ou si on en a besoin
        if self.detection_mode != "legacy":
            return
            
        print(f"📁 Chargement des jingles...")
        required = set(item["target"] for item in self.sequence if item["type"] == "jingle")
        for name in required:
            path = os.path.join(jingles_dir, name)
            try:
                cmd = ['ffmpeg', '-i', path, '-ar', str(self.sample_rate), '-ac', '1', '-f', 's16le', '-loglevel', 'error', '-']
                out, _ = subprocess.Popen(cmd, stdout=subprocess.PIPE).communicate()
                jingle = np.frombuffer(out, dtype=np.int16).astype(np.float32) / 32768.0
                jingle /= (np.max(np.abs(jingle)) + 1e-6)
                self.jingle_data[name] = {"signal": jingle, "length": len(jingle), "norm": np.linalg.norm(jingle)}
                print(f"  ✅ {name}")
            except: print(f"  ❌ Erreur {name}")

    def add_to_buffer(self, chunk):
        n = len(chunk)
        if self.buffer_index + n <= self.buffer_size:
            self.audio_buffer[self.buffer_index:self.buffer_index + n] = chunk
            self.buffer_index = (self.buffer_index + n) % self.buffer_size
        else:
            part = self.buffer_size - self.buffer_index
            self.audio_buffer[self.buffer_index:] = chunk[:part]
            self.audio_buffer[:n-part] = chunk[part:]
            self.buffer_index = n-part
        self.total_samples_processed += n
        
        # Alimenter le sync_buffer (sous-échantillonnage simple par décimation)
        factor = self.sample_rate // self.sync_sr
        sync_chunk = chunk[::factor]
        ns = len(sync_chunk)
        if self.sync_buffer_index + ns <= self.sync_buffer_size:
            self.sync_buffer[self.sync_buffer_index:self.sync_buffer_index + ns] = sync_chunk
            self.sync_buffer_index = (self.sync_buffer_index + ns) % self.sync_buffer_size
        else:
            part = self.sync_buffer_size - self.sync_buffer_index
            self.sync_buffer[self.sync_buffer_index:] = sync_chunk[:part]
            self.sync_buffer[:ns-part] = sync_chunk[part:]
            self.sync_buffer_index = ns-part
        self.total_sync_samples += ns
        
        pcm_chunk = (chunk * 32768).astype(np.int16).tobytes()
        self.whisper_audio_accumulated.extend(pcm_chunk)
        
        # On envoie l'audio vers la file d'attente de transcription par plus petits blocs (ex: 0.5s)
        # pour permettre une plus grande réactivité du flux continu
        accumulation_limit = 0.5
        
        if len(self.whisper_audio_accumulated) >= (accumulation_limit * self.sample_rate * 2):
            start_ts = self.total_samples_processed - (accumulation_limit * self.sample_rate)
            # print(f"📦 [Audio] Chunk de 0.5s envoyé")
            self.transcription_queue.put((bytes(self.whisper_audio_accumulated), start_ts))
            self.whisper_audio_accumulated = bytearray()

    def get_latest_audio(self, length):
        length = int(length)
        if self.buffer_index >= length:
            return self.audio_buffer[self.buffer_index-length:self.buffer_index]
        return np.concatenate((self.audio_buffer[-(length-self.buffer_index):], self.audio_buffer[:self.buffer_index]))

    def get_latest_sync_audio(self, length):
        length = int(length)
        if self.sync_buffer_index >= length:
            return self.sync_buffer[self.sync_buffer_index-length:self.sync_buffer_index]
        return np.concatenate((self.sync_buffer[-(length-self.sync_buffer_index):], self.sync_buffer[:self.sync_buffer_index]))

    def on_detected(self, item, score=None, exact_time=None, trigger_text=None):
        time_sec = exact_time if exact_time is not None else (self.total_samples_processed / self.sample_rate)
        # On applique l'offset global au temps du flux pour obtenir le temps "réel" corrigé
        corrected_time = time_sec + self.time_offset
        
        time_str = time.strftime('%H:%M:%S', time.gmtime(corrected_time))
        now_str = datetime.now().strftime("%H:%M:%S")
        
        # Envoi du signal de FIN pour la chronique qui vient de se terminer
        if self.last_chronicle_name:
            prev_name = self.last_chronicle_name
            duration = time_sec - self.last_chronicle_start_time
            print(f"\n🔚 FIN DE LA CHRONIQUE : {prev_name}")
            print(f"   Position FIN (corrigée): {time_str} ({corrected_time:.1f}s)")
            print(f"   Durée totale          : {duration:.1f}s")
            
            def call_api_end():
                try:
                    python_api_url = os.environ.get('PYTHON_API_URL', 'http://localhost:8001')
                    url = f"{python_api_url}/api/realChronicleEndTime"
                    params = {
                        "userId": "master",
                        "nomDeChronique": prev_name,
                        "realDuration": duration,
                        "endTime": int(corrected_time)
                    }
                    requests.post(url, params=params, timeout=1)
                    print(f"   [API] Signal de fin envoyé pour '{prev_name}'")
                except Exception as e:
                    print(f"   [API ERROR] Signal de fin : {e}")
            threading.Thread(target=call_api_end, daemon=True).start()

        print(f"\n\n{'🔥' if item.get('type')=='jingle' else '✨'} {'='*56}")
        print(f"⭐ DÉBUT DE LA CHRONIQUE : {item['name']}")
        print(f"   Position DÉBUT (corrigée): {time_str} ({corrected_time:.1f}s)")
        print(f"   Détecté à (live)      : {now_str}")
        if trigger_text:
            print(f"   Phrase déclencheur    : \"{trigger_text}\"")
        if score: print(f"   Score : {score:.4f}")
        print(f"{'='*60}\n")
        
        # Envoi du signal de DÉBUT pour la chronique actuelle
        def call_api_start():
            try:
                python_api_url = os.environ.get('PYTHON_API_URL', 'http://localhost:8001')
                url = f"{python_api_url}/api/realChronicleStartTime"
                params = {
                    "userId": "master",
                    "nomDeChronique": item['name'],
                    "startTime": int(corrected_time),
                    "confidence": float(score) if score else 1.0
                }
                requests.post(url, params=params, timeout=1)
                print(f"   [API] Signal de début envoyé pour '{item['name']}'")
            except Exception as e:
                print(f"   [API ERROR] Signal de début : {e}")
        threading.Thread(target=call_api_start, daemon=True).start()

        # Mise à jour pour la prochaine détection
        self.last_chronicle_name = item['name']
        self.last_chronicle_start_time = time_sec

        if self.detection_mode == "legacy":
            self.current_step += 1
            self.step_just_changed = True
            if self.current_step < len(self.sequence):
                next_it = self.sequence[self.current_step]
                print(f"➡️ Cible suivante : {next_it['name']} ({next_it['type']})")
            else:
                print("🏁 SÉQUENCE TERMINÉE !"); self.running = False

    def transcription_worker(self):
        print(f"🧵 Worker transcription démarré (Mode CONTINU, Provider: {self.transcriber.provider})")
        
        def audio_stream_generator():
            """Générateur qui puise dans la queue de transcription"""
            while self.running:
                try:
                    audio_bytes, start_samples = self.transcription_queue.get(timeout=1)
                    audio_np = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
                    yield audio_np
                except queue.Empty:
                    continue

        try:
            # On lance le flux de transcription continu
            for segment in self.transcriber.stream_transcribe(audio_stream_generator()):
                text = segment.get("text", "").strip()
                if not text:
                    continue
                
                # Le temps actuel est approximatif en mode continu, on utilise le compteur global
                current_time_sec = self.total_samples_processed / self.sample_rate
                print(f"💬 Transcription (CONTINUE): \"{text}\"")
                
                if self.detection_mode == "deepseek" and self.deepseek_detector:
                    # Analyse via DeepSeek
                    res = self.deepseek_detector.analyze_sentence(text, self.context_buffer, current_time_sec=current_time_sec)
                    if res.get("detecte"):
                        chronicle_name = res.get("chronique")
                        self.on_detected({"name": chronicle_name, "type": "ai"}, exact_time=current_time_sec, trigger_text=text)
                    
                    # Mise à jour du buffer de contexte
                    self.context_buffer.append(text)
                    if len(self.context_buffer) > self.max_context:
                        self.context_buffer.pop(0)
                        
                elif self.detection_mode == "legacy":
                    if self.current_step < len(self.sequence) and self.sequence[self.current_step]["type"] == "keyword":
                        target = self.normalize_text(self.sequence[self.current_step]["target"])
                        if target in self.normalize_text(text):
                            self.on_detected(self.sequence[self.current_step], exact_time=current_time_sec, trigger_text=text)

        except Exception as e:
            print(f"❌ Erreur critique dans le worker de transcription continue: {e}")
            import traceback
            traceback.print_exc()

    def fast_rolling_energy(self, signal_sq, window_len):
        """Calcul de l'énergie glissante optimisé."""
        cumsum = np.cumsum(np.insert(signal_sq, 0, 0))
        return np.sqrt(cumsum[window_len:] - cumsum[:-window_len])

    def process_audio_chunk(self, chunk, position_in_seconds=None):
        if position_in_seconds is not None:
            # On resynchronise le compteur total sur la position demandée
            self.total_samples_processed = int(position_in_seconds * self.sample_rate)
            
        self.add_to_buffer(chunk)
        if not self.running:
            return

        # En mode legacy, on fait la corrélation jingle
        if self.detection_mode == "legacy" and self.current_step < len(self.sequence):
            item = self.sequence[self.current_step]
            
            if item["type"] == "jingle":
                data = self.jingle_data.get(item["target"])
                if data:
                    lookback = 20 if self.step_just_changed else 1.5
                    search_len = min(int(data["length"] + lookback * self.sample_rate), self.total_samples_processed)
                    if search_len >= data["length"]:
                        audio = self.get_latest_audio(search_len)
                        corr = signal.correlate(audio, data["signal"], mode='valid')
                        
                        energy_audio = self.fast_rolling_energy(audio**2, data["length"])
                        norm_corr = corr / (energy_audio * data["norm"] + 1e-6)
                        score = np.max(norm_corr)
                        
                        if score > self.threshold:
                            delay_samples = len(norm_corr) - 1 - np.argmax(norm_corr)
                            detection_time = (self.total_samples_processed - delay_samples - data["length"]) / self.sample_rate
                            self.on_detected(item, score=score, exact_time=detection_time)
                            self.step_just_changed = True
                        else:
                            self.step_just_changed = False

    def run(self, simu=False):
        # Initialisation du détecteur DeepSeek (chargement de la grille) juste avant de démarrer
        if self.detection_mode == "deepseek":
            print("🤖 Mode DETECTION: DeepSeek API")
            api_key = os.environ.get("DEEPSEEK_API_KEY")
            if not api_key:
                print("⚠️ [DeepSeek] DEEPSEEK_API_KEY manquante. Repli sur le mode legacy.")
                self.detection_mode = "legacy"
            else:
                target_date = os.environ.get("TARGET_DATE")
                if target_date:
                    print(f"🔍 Récupération de la grille pour le {target_date}...")
                else:
                    print("🔍 Récupération de la grille du jour...")
                
                schedule_data = get_chroniques(target_date)
                if schedule_data:
                    print(f"✅ {len(schedule_data)} chroniques trouvées :")
                    for item in schedule_data:
                        print(f"   - {item.get('time')} : {item.get('title')}")
                else:
                    print("⚠️ Aucune chronique trouvée dans la grille.")
                
                self.deepseek_detector = DeepSeekDetector(api_key, schedule=schedule_data, is_simulation=os.environ.get("SIMU", "false").lower() == "true")
                self.context_buffer = []
                self.max_context = 5
        
        if self.detection_mode == "legacy":
            print("📻 Mode DETECTION: Legacy (Jingles + Keywords)")

        # Lancement du worker de transcription
        threading.Thread(target=self.transcription_worker, daemon=True).start()
        
        source = None
        self.process = None # Processus ffmpeg pour le live
        try:
            if simu:
                print(f"📁 Mode SIMULATION : écoute sur {self.pipe_path}")
                
                # S'assurer que le pipe est bien un FIFO
                if os.path.exists(self.pipe_path):
                    import stat
                    if not stat.S_ISFIFO(os.stat(self.pipe_path).st_mode):
                        print(f"⚠️ {self.pipe_path} n'est pas un FIFO, suppression...")
                        os.remove(self.pipe_path)
                        os.mkfifo(self.pipe_path)
                    else:
                        print(f"✅ FIFO existant détecté sur {self.pipe_path}")
                else:
                    print(f"🔨 Création du FIFO {self.pipe_path}")
                    os.mkfifo(self.pipe_path)
                
                print(f"⏳ Attente d'un flux sur le pipe...")
                source = open(self.pipe_path, 'rb')
                print(f"🚀 Pipe ouvert, début de la lecture.")
            else:
                print("🎤 Mode LIVE : écoute sur le flux radio France Inter")
                stream_url = "https://stream.radiofrance.fr/franceinter/franceinter_hifi.m3u8"
                cmd = [
                    'ffmpeg',
                    '-i', stream_url,
                    '-f', 's16le',
                    '-ac', '1',
                    '-ar', str(self.sample_rate),
                    '-loglevel', 'error',
                    '-'
                ]
                self.process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
                source = self.process.stdout

            while self.running:
                raw_data = source.read(self.chunk_size * 2)
                if not raw_data:
                    if simu:
                        time.sleep(0.01)
                        continue
                    else:
                        print("⚠️ Fin du flux live ou erreur ffmpeg.")
                        break
                
                # Heartbeat toutes les ~10 secondes
                if self.total_samples_processed % (self.sample_rate * 10) < self.chunk_size:
                    print(f"💓 [Heartbeat] Lecture audio en cours... (Total: {self.total_samples_processed / self.sample_rate:.1f}s)")

                chunk = np.frombuffer(raw_data, dtype=np.int16).astype(np.float32) / 32768.0
                if len(chunk) > 0:
                    self.process_audio_chunk(chunk)
                
        except KeyboardInterrupt:
            print("\nArrêt manuel.")
        except Exception as e:
            print(f"\n❌ Erreur pendant l'exécution : {e}")
        finally: 
            self.running = False
            if self.process:
                print("🧹 Arrêt du processus ffmpeg...")
                self.process.terminate()
                try:
                    self.process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self.process.kill()
            
            if source and hasattr(source, 'close') and simu: # On ne ferme stdout que si c'est un fichier
                source.close()
            
            if self.last_chronicle_name:
                total_sec = self.total_samples_processed / self.sample_rate
                duration = total_sec - self.last_chronicle_start_time
                time_str = time.strftime('%H:%M:%S', time.gmtime(total_sec))
                print(f"\n🔚 FIN DE LA CHRONIQUE FINALE : {self.last_chronicle_name}")
                print(f"   Position FIN (flux)   : {time_str} ({total_sec:.1f}s)")
                print(f"   Durée totale          : {duration:.1f}s")
                
                # Signal de fin final pour l'API
                try:
                    python_api_url = os.environ.get('PYTHON_API_URL', 'http://localhost:8001')
                    requests.post(f"{python_api_url}/api/realChronicleEndTime", 
                                  params={
                                      "userId": "master",
                                      "nomDeChronique": self.last_chronicle_name,
                                      "realDuration": duration,
                                      "endTime": int(total_sec)
                                  }, timeout=1)
                    print(f"   [API] Signal de fin envoyé pour '{self.last_chronicle_name}'")
                except: pass

if __name__ == "__main__":
    # On récupère le mode SIMU depuis l'environnement (par défaut False)
    SIMU = os.environ.get("SIMU", "false").lower() == "true"
    
    # Mode de détection (legacy ou deepseek)
    DETECTION_MODE = os.environ.get("DETECTION_MODE", "legacy").lower()
    
    # Chemin vers les jingles (ajusté pour Docker)
    jingles_path = "/app/assets/jingles_chroniques/jingles_m4a"
    if not os.path.exists(jingles_path):
        jingles_path = "assets/jingles_chroniques/jingles_m4a"
        
    segmenter = UnifiedLiveSegmenter(jingles_path, threshold=0.50, detection_mode=DETECTION_MODE)
    segmenter.run(simu=SIMU)
