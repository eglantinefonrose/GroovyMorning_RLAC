from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit
import psycopg2
import psycopg2.extras
import os
import subprocess
import sys
import time
import threading
import schedule
from datetime import datetime

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# Configuration base de données
DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'localhost'),
    'port': os.environ.get('DB_PORT', '5432'),
    'database': os.environ.get('DB_NAME', 'radiodb'),
    'user': os.environ.get('DB_USER', 'radiouser'),
    'password': os.environ.get('DB_PASSWORD', 'radiopass')
}

def get_db_connection():
    return psycopg2.connect(**DB_CONFIG)

def run_segmenter():
    """Lance le segmenter à l'heure programmée"""
    print(f"[{datetime.now()}] Lancement du segmenter (Mode SIMU: {os.environ.get('SIMU', 'false')})...")

    # Tuer l'ancien segmenter s'il tourne
    subprocess.run(["pkill", "-f", "live_radio_segmenter.py"], stderr=subprocess.DEVNULL)

    # Lancer le nouveau segmenter (dans le dossier src/)
    # On s'assure de passer l'environnement actuel (contenant SIMU=true)
    segmenter_process = subprocess.Popen(
        [sys.executable, "src/live_radio_segmenter.py"],
        env=os.environ.copy()
    )

    print(f"[{datetime.now()}] Segmenter lancé avec PID: {segmenter_process.pid}")

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
    print(f"⏰ [Scheduler] Prochain segmenter programmé à {time_str}")

# Initialisation du scheduler
# Par défaut à 09:30 comme dans l'ancien scheduler.py
schedule.every().day.at("09:30").do(run_segmenter)

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
# ... (rest of the file)

    data = request.args
    user_id = data.get('userId')
    chronicle_name = data.get('nomDeChronique')
    start_time = data.get('startTime')
    delta = data.get('deltaStartTimeInSeconds')
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO chronicle_events (user_id, chronicle_name, event_type, timestamp, delta)
            VALUES (%s, %s, 'start', %s, %s)
        """, (user_id, chronicle_name, start_time, delta))
        conn.commit()
        cur.close()
        conn.close()
        print(f"💾 [DB] Start event saved for {chronicle_name}")
    except Exception as e:
        print(f"⚠️ [DB Error] Could not save start event: {e}")
    
    # WebSocket emit (toujours exécuté même si la DB échoue)
    event_data = {
        'userId': user_id,
        'nomDeChronique': chronicle_name,
        'deltaStartTimeInSeconds': int(delta) if delta and (isinstance(delta, int) or delta.isdigit()) else delta
    }
    print(f"🚀 [Python API] Emitting START via WebSocket: {event_data}")
    socketio.emit('chronicle_start', event_data)
    
    return jsonify({"status": "success"})

@app.route('/api/realChronicleEndTime', methods=['POST'])
def chronicle_end():
    """Reçoit la fin d'une chronique du segmenter"""
    data = request.args
    user_id = data.get('userId')
    chronicle_name = data.get('nomDeChronique')
    duration = data.get('realDuration')
    end_time = data.get('endTime')
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO chronicle_events (user_id, chronicle_name, event_type, timestamp, duration)
            VALUES (%s, %s, 'end', %s, %s)
        """, (user_id, chronicle_name, end_time, duration))
        conn.commit()
        cur.close()
        conn.close()
        print(f"💾 [DB] End event saved for {chronicle_name}")
    except Exception as e:
        print(f"⚠️ [DB Error] Could not save end event: {e}")
    
    # WebSocket emit
    event_data = {
        'userId': user_id,
        'nomDeChronique': chronicle_name,
        'realDuration': duration
    }
    print(f"🚀 [Python API] Emitting END via WebSocket: {event_data}")
    socketio.emit('chronicle_end', event_data)
    
    return jsonify({"status": "success"})

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