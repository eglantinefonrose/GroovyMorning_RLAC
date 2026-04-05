from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit
import psycopg2
import psycopg2.extras
import os
from datetime import datetime

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='gevent')

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

@app.route('/api/realChronicleStartTime', methods=['POST'])
def chronicle_start():
    """Reçoit le début d'une chronique du segmenter"""
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