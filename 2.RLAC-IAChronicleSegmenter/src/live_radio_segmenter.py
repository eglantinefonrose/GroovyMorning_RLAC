import numpy as np
import os
import time
import glob
from scipy import signal
import warnings
import requests
import subprocess
import threading
import queue
import whisper
import wave
import unicodedata
from flask import Flask, request, jsonify

warnings.filterwarnings('ignore')

class UnifiedLiveSegmenter:
    def __init__(self, jingles_dir, pipe_path='/tmp/audio_pipe', threshold=0.50, whisper_model="medium"):
        self.sample_rate = 16000
        self.pipe_path = pipe_path
        self.threshold = threshold
        self.chunk_size = 512 # Latence ultra-faible : 32ms
        
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
        print(f"🚀 Chargement Whisper '{whisper_model}'...")
        self.model = whisper.load_model(whisper_model)
        print(f"✅ Système prêt. Chunk: {self.chunk_size} samples")

    def normalize_text(self, text):
        text = text.lower()
        text = unicodedata.normalize('NFD', text).encode('ascii', 'ignore').decode('utf-8')
        return text

    def load_jingles(self, jingles_dir):
        self.jingle_data = {}
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
        if len(self.whisper_audio_accumulated) >= (5 * self.sample_rate * 2):
            start_ts = self.total_samples_processed - (5 * self.sample_rate)
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

    def on_detected(self, item, score=None, exact_time=None):
        time_sec = exact_time if exact_time is not None else (self.total_samples_processed / self.sample_rate)
        # On applique l'offset global au temps du flux pour obtenir le temps "réel" corrigé
        corrected_time = time_sec + self.time_offset
        
        time_str = time.strftime('%H:%M:%S', time.gmtime(corrected_time))
        now_str = time.strftime('%H:%M:%S')
        
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

        print(f"\n\n{'🔥' if item['type']=='jingle' else '✨'} {'='*56}")
        print(f"⭐ DÉBUT DE LA CHRONIQUE : {item['name']}")
        print(f"   Position DÉBUT (corrigée): {time_str} ({corrected_time:.1f}s)")
        print(f"   Détecté à (live)      : {now_str}")
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

        self.current_step += 1
        self.step_just_changed = True
        if self.current_step < len(self.sequence):
            next_it = self.sequence[self.current_step]
            print(f"➡️ Cible suivante : {next_it['name']} ({next_it['type']})")
        else:
            print("🏁 SÉQUENCE TERMINÉE !"); self.running = False

    def transcription_worker(self):
        while self.running:
            try:
                audio_data, start_samples = self.transcription_queue.get(timeout=1)
                if self.current_step >= len(self.sequence) or self.sequence[self.current_step]["type"] != "keyword":
                    continue
                temp_wav = f"/tmp/wh_{int(time.time())}.wav"
                with wave.open(temp_wav, 'wb') as wav:
                    wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(self.sample_rate)
                    wav.writeframes(audio_data)
                result = self.model.transcribe(temp_wav, language="fr", fp16=False)
                text = result["text"].strip()
                os.remove(temp_wav)
                if text:
                    print(f"💬 Transcription: \"{text}\"")
                    if self.normalize_text(self.sequence[self.current_step]["target"]) in self.normalize_text(text):
                        self.on_detected(self.sequence[self.current_step], exact_time=start_samples / self.sample_rate)
            except: continue

    def fast_rolling_energy(self, signal_sq, window_len):
        """Calcul de l'énergie glissante optimisé."""
        cumsum = np.cumsum(np.insert(signal_sq, 0, 0))
        return np.sqrt(cumsum[window_len:] - cumsum[:-window_len])

    def process_audio_chunk(self, chunk, position_in_seconds=None):
        if position_in_seconds is not None:
            # On resynchronise le compteur total sur la position demandée
            self.total_samples_processed = int(position_in_seconds * self.sample_rate)
            
        self.add_to_buffer(chunk)
        if not self.running or self.current_step >= len(self.sequence):
            return

        item = self.sequence[self.current_step]
        
        if item["type"] == "jingle":
            data = self.jingle_data.get(item["target"])
            if data:
                lookback = 20 if self.step_just_changed else 1.5
                search_len = min(int(data["length"] + lookback * self.sample_rate), self.total_samples_processed)
                if search_len >= data["length"]:
                    audio = self.get_latest_audio(search_len)
                    corr = signal.correlate(audio, data["signal"], mode='valid')
                    energy = self.fast_rolling_energy(audio**2, data["length"])
                    score_array = np.abs(corr) / (energy * data["norm"] + 1e-6)
                    score = np.max(score_array)
                    self.step_just_changed = False
                    
                    if score > self.threshold:
                        best_pos = np.argmax(score_array)
                        jingle_start_samples = (self.total_samples_processed - len(audio)) + best_pos
                        exact_time = max(0.0, jingle_start_samples / self.sample_rate)
                        self.on_detected(item, score=score, exact_time=exact_time)
                    elif time.time() - self.last_status_time > 0.25:
                        self.last_status_time = time.time()
                        print(f"\r📡 LIVE | Flux: {self.total_samples_processed/self.sample_rate:5.1f}s | Cible: {item['target'][:15]} | Score: {score:.3f}/{self.threshold}", end="", flush=True)
        
        elif item["type"] == "keyword" and time.time() - self.last_status_time > 0.5:
            self.last_status_time = time.time()
            print(f"\r📡 LIVE | Flux: {self.total_samples_processed/self.sample_rate:5.1f}s | Cible: {item['name']} 🎤", end="", flush=True)

    def find_offset(self, sync_chunk, reported_seconds):
        # sync_chunk est à 4000Hz (2s = 8000 samples)
        # On cherche dans les 60 dernières secondes du sync_buffer
        search_len = min(self.sync_buffer_size, self.total_sync_samples)
        if search_len < len(sync_chunk):
            return 0, 0
            
        search_audio = self.get_latest_sync_audio(search_len)
        
        # Corrélation croisée
        corr = signal.correlate(search_audio, sync_chunk, mode='valid')
        # Énergie pour la normalisation
        # Utilisation d'une version simplifiée pour 4000Hz
        search_energy = np.sqrt(np.convolve(search_audio**2, np.ones(len(sync_chunk)), mode='valid'))
        chunk_norm = np.linalg.norm(sync_chunk)
        
        score_array = np.abs(corr) / (search_energy * chunk_norm + 1e-6)
        best_pos = np.argmax(score_array)
        max_score = score_array[best_pos]
        
        # Position réelle dans le flux sync (échantillons à 4000Hz)
        real_sync_samples = (self.total_sync_samples - search_len) + best_pos
        real_seconds = real_sync_samples / self.sync_sr
        
        # Delta = Temps Master (reported) - Temps Local (real)
        delta = reported_seconds - real_seconds
        return delta, float(max_score)

    def start_api(self):
        app = Flask(__name__)
        
        @app.route('/api/feed_audio', methods=['POST'])
        def feed_audio():
            raw_data = request.get_data()
            if not raw_data:
                return jsonify({"error": "No data"}), 400
            
            # Récupération de la position optionnelle (en secondes)
            pos_sec = request.args.get('positionInSeconds', type=float)
            
            chunk = np.frombuffer(raw_data, dtype=np.int16).astype(np.float32) / 32768.0
            self.process_audio_chunk(chunk, position_in_seconds=pos_sec)
            return jsonify({
                "status": "success",
                "total_samples": self.total_samples_processed,
                "current_time": self.total_samples_processed / self.sample_rate,
                "current_step": self.current_step
            })
        @app.route('/api/get_offset', methods=['POST'])
        def get_offset():
            raw_data = request.get_data()
            pos_sec = request.args.get('positionInSeconds', type=float, default=0.0)
            if not raw_data:
                return jsonify({"error": "No data"}), 400
            
            # On attend du 4000Hz pour la synchro
            chunk = np.frombuffer(raw_data, dtype=np.int16).astype(np.float32) / 32768.0
            delta, score = self.find_offset(chunk, pos_sec)
            
            return jsonify({
                "delta": delta,
                "score": score
            })

        @app.route('/api/status', methods=['GET'])
        def status():
            return jsonify({
                "running": self.running,
                "current_step": self.current_step,
                "total_seconds": self.total_samples_processed / self.sample_rate,
                "last_chronicle": self.last_chronicle_name
            })

        print("📡 API démarrée sur http://localhost:8002")
        app.run(host='0.0.0.0', port=8002, debug=False, use_reloader=False)

    def run(self, simu=True):
        threading.Thread(target=self.transcription_worker, daemon=True).start()
        threading.Thread(target=self.start_api, daemon=True).start()
        
        source = None
        try:
            if simu:
                import stat
                # Créer le pipe s'il n'existe pas
                if not os.path.exists(self.pipe_path):
                    os.mkfifo(self.pipe_path)
                else:
                    # Vérifier si c'est bien un FIFO
                    mode = os.stat(self.pipe_path).st_mode
                    if not stat.S_ISFIFO(mode):
                        os.remove(self.pipe_path)
                        os.mkfifo(self.pipe_path)
                
                print(f"📡 Mode SIMULATION (Pipe: {self.pipe_path})")
                print("⏳ En attente de données dans le pipe... (Lancez votre commande ffmpeg)")
                
                # La boucle de simulation pour permettre de relancer ffmpeg sans couper le segmenter
                while self.running:
                    with open(self.pipe_path, 'rb') as source:
                        print("✅ Flux connecté au pipe.")
                        while self.running:
                            raw = source.read(self.chunk_size * 2)
                            if not raw:
                                print("\n⚠️ Fin du flux dans le pipe. En attente de la prochaine connexion...")
                                break
                            chunk = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
                            self.process_audio_chunk(chunk)
            else:
                stream_url = "http://icecast.radiofrance.fr/franceinter-hifi.aac"
                print(f"📡 Mode LIVE (Stream: {stream_url})")
                cmd = [
                    'ffmpeg', '-i', stream_url,
                    '-f', 's16le', '-ac', '1', '-ar', str(self.sample_rate),
                    '-loglevel', 'quiet', '-'
                ]
                self.process = subprocess.Popen(cmd, stdout=subprocess.PIPE)
                source = self.process.stdout

                print(f"✅ Flux connecté. Analyse en cours...")
                while self.running:
                    raw = source.read(self.chunk_size * 2)
                    if not raw:
                        print("\n⚠️ Fin du flux ou erreur de lecture.")
                        break
                    chunk = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
                    self.process_audio_chunk(chunk)
                
        except KeyboardInterrupt:
            print("\nArrêt manuel.")
        except Exception as e:
            print(f"\n❌ Erreur pendant l'exécution : {e}")
        finally: 
            self.running = False
            if hasattr(self, 'process'):
                self.process.terminate()
            if source and hasattr(source, 'close'):
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
                                      "userId": "testUser",
                                      "nomDeChronique": self.last_chronicle_name,
                                      "realDuration": duration
                                  }, timeout=1)
                    print(f"   [API] Signal de fin envoyé pour '{self.last_chronicle_name}'")
                except: pass

if __name__ == "__main__":
    # On récupère le mode SIMU depuis l'environnement (par défaut False)
    SIMU = os.environ.get("SIMU", "false").lower() == "true"
    
    # Chemin vers les jingles (ajusté pour Docker)
    jingles_path = "/app/assets/jingles_chroniques/jingles_m4a"
    if not os.path.exists(jingles_path):
        jingles_path = "assets/jingles_chroniques/jingles_m4a"
        
    segmenter = UnifiedLiveSegmenter(jingles_path, threshold=0.50)
    segmenter.run(simu=SIMU)
