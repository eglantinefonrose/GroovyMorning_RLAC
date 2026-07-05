import sqlite3
import os
from dotenv import load_dotenv

# Charger les variables d'environnement depuis .env
load_dotenv()

import subprocess
import sys
import time
import threading
import schedule
import requests
from datetime import datetime
from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# Configuration Java Backend
JAVA_BASE_URL = os.environ.get('JAVA_API_URL', 'http://localhost:8080')

def forward_to_java(endpoint, params):
    """Envoie un signal HTTP POST au serveur Java"""
    url = f"{JAVA_BASE_URL}{endpoint}"
    def task():
        try:
            print(f"📡 [Forward] Sending to Java: {url} with {params}")
            requests.post(url, params=params, timeout=2)
        except Exception as e:
            print(f"⚠️ [Forward Error] Could not reach Java backend: {e}")
    
    # On lance l'appel dans un thread pour ne pas bloquer l'API Python
    threading.Thread(target=task, daemon=True).start()

# Configuration SQLite
DB_PATH = os.environ.get('DB_PATH', 'data/master_events.db')

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS master_chronicle_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chronicle_name TEXT,
            event_type TEXT,
            master_timestamp TEXT,
            confidence FLOAT
        )
    """)
    conn.commit()
    conn.close()

def get_db_connection():
    return sqlite3.connect(DB_PATH)

init_db()

def run_segmenter():
    """Lance le segmenter à l'heure programmée"""
    target_date = os.environ.get('TARGET_DATE', 'aujourd\'hui')
    print(f"[{datetime.now()}] Lancement du segmenter (Mode SIMU: {os.environ.get('SIMU', 'false')}, Date: {target_date})...")

    # Tuer l'ancien segmenter s'il tourne
    stop_segmenter()

    # Lancer le nouveau segmenter (dans le dossier src/)
    # On s'assure de passer l'environnement actuel (contenant SIMU=true)
    segmenter_process = subprocess.Popen(
        [sys.executable, "src/live_radio_segmenter.py"],
        env=os.environ.copy()
    )

    print(f"[{datetime.now()}] Segmenter lancé avec PID: {segmenter_process.pid}")

def stop_segmenter():
    """Arrête le segmenter s'il est en cours d'exécution"""
    print(f"[{datetime.now()}] Arrêt du segmenter...")
    subprocess.run(["pkill", "-f", "live_radio_segmenter.py"], stderr=subprocess.DEVNULL)

def scheduler_loop():
    """Boucle infinie pour exécuter les tâches planifiées"""
    print("⏰ [Scheduler] Boucle de planification démarrée.")
    while True:
        schedule.run_pending()
        time.sleep(1)

def update_scheduler(hour, minute):
    """Met à jour l'heure de lancement du segmenter"""
    schedule.clear()
    time_str = f"{int(hour):02d}:{int(minute):02d}"
    schedule.every().day.at(time_str).do(run_segmenter)
    # On garde l'arrêt à 09:10 même si on change l'heure de début
    schedule.every().day.at("09:10").do(stop_segmenter)
    print(f"⏰ [Scheduler] Prochain segmenter programmé à {time_str}")

# Initialisation du scheduler
# Lancement à 06:58 et arrêt à 09:10
schedule.every().day.at("06:58").do(run_segmenter)
schedule.every().day.at("09:10").do(stop_segmenter)

# Lancement du thread scheduler
threading.Thread(target=scheduler_loop, daemon=True).start()

# SI on est en mode SIMU, on lance une première fois immédiatement pour tester
if os.environ.get("SIMU", "").lower() == "true":
    print("🧪 Mode SIMU détecté : Lancement immédiat pour test...")
    run_segmenter()

@app.route('/api/updateSchedulerTime', methods=['POST'])
def api_update_scheduler_time():
    """Met à jour l'heure du scheduler via API"""
    data = request.args
    hour = data.get('hour')
    minute = data.get('minute')

    if hour is None or minute is None:
        return jsonify({"status": "error", "message": "Paramètres 'hour' et 'minute' requis"}), 400

    try:
        update_scheduler(hour, minute)
        return jsonify({
            "status": "success", 
            "message": f"Scheduler mis à jour pour {int(hour):02d}:{int(minute):02d}"
        })
    except Exception as e:
        print(f"⚠️ [Scheduler Error] {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/realChronicleStartTime', methods=['POST'])
def chronicle_start():
    data = request.args
    user_id = data.get('userId', 'unknown')
    chronicle_name = data.get('nomDeChronique')
    start_time = data.get('startTime')
    confidence = data.get('confidence', 1.0)
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO master_chronicle_events (chronicle_name, event_type, master_timestamp, confidence)
            VALUES (?, 'start', ?, ?)
        """, (chronicle_name, start_time, confidence))
        conn.commit()
        conn.close()
        print(f"💾 [DB] Master Start event saved for {chronicle_name}")
    except Exception as e:
        print(f"⚠️ [DB Error] Could not save master start event: {e}")
    
    # WebSocket emit (Broadcast à tous)
    event_data = {
        'userId': user_id, # Gardé pour le log client, mais sera ignoré par le Java si pas concerné
        'nomDeChronique': chronicle_name,
        'masterTimestamp': start_time
    }
    print(f"🚀 [Python API] Broadcasting START via WebSocket: {event_data}")
    socketio.emit('chronicle_start', event_data)
    
    # Forward au Java via HTTP
    forward_to_java("/api/realChronicleStartTime", {
        "userId": user_id,
        "nomDeChronique": chronicle_name,
        "startTime": start_time,
        "confidence": confidence
    })
    
    return jsonify({"status": "success"})

@app.route('/api/realChronicleEndTime', methods=['POST'])
def chronicle_end():
    data = request.args
    user_id = data.get('userId', 'unknown')
    chronicle_name = data.get('nomDeChronique')
    duration = data.get('realDuration')
    end_time = data.get('endTime')
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO master_chronicle_events (chronicle_name, event_type, master_timestamp)
            VALUES (?, 'end', ?)
        """, (chronicle_name, end_time))
        conn.commit()
        conn.close()
        print(f"💾 [DB] Master End event saved for {chronicle_name}")
    except Exception as e:
        print(f"⚠️ [DB Error] Could not save master end event: {e}")
    
    # WebSocket emit
    event_data = {
        'userId': user_id,
        'nomDeChronique': chronicle_name,
        'realDuration': duration,
        'masterTimestamp': end_time
    }
    print(f"🚀 [Python API] Broadcasting END via WebSocket: {event_data}")
    socketio.emit('chronicle_end', event_data)
    
    # Forward au Java via HTTP
    forward_to_java("/api/realChronicleEndTime", {
        "userId": user_id,
        "nomDeChronique": chronicle_name,
        "realDuration": duration,
        "endTime": end_time
    })
    
    return jsonify({"status": "success"})

@app.route('/api/sync_offset', methods=['POST'])
def sync_offset():
    """
    Reçoit un chunk audio (fingerprint) et renvoie le delta par rapport au flux maître.
    On redirige vers le segmenter qui maintient le flux en mémoire.
    """
    import requests
    try:
        # On passe simplement la requête au segmenter qui tourne sur le port 8002
        # C'est lui qui a la "mémoire" du flux audio récent
        segmenter_url = "http://localhost:8002/api/get_offset"
        resp = requests.post(
            segmenter_url, 
            params=request.args, 
            data=request.get_data(),
            timeout=5
        )
        return (resp.content, resp.status_code, resp.headers.items())
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/status', methods=['GET'])
def status():
    """Endpoint de statut"""
    return jsonify({
        "status": "running",
        "timestamp": datetime.now().isoformat()
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8001))
    socketio.run(app, host='0.0.0.0', port=port, debug=False, allow_unsafe_werkzeug=True)