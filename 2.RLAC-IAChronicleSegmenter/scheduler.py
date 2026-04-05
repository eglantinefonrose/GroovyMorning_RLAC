import schedule
import time
import subprocess
import os
import sys
from datetime import datetime

def run_segmenter():
    """Lance le segmenter à l'heure programmée"""
    print(f"[{datetime.now()}] Lancement du segmenter...")
    
    # Tuer l'ancien segmenter s'il tourne
    subprocess.run(["pkill", "-f", "live_radio_segmenter.py"], stderr=subprocess.DEVNULL)
    
    # Lancer le nouveau segmenter (dans le dossier src/)
    segmenter_process = subprocess.Popen(
        [sys.executable, "src/live_radio_segmenter.py"]
    )
    
    print(f"[{datetime.now()}] Segmenter lancé avec PID: {segmenter_process.pid}")

# Planification à 6h55 chaque jour
schedule.every().day.at("18:27").do(run_segmenter)

print(f"Scheduler démarré. Le segmenter sera lancé à 6h55 chaque jour.")

# Garder le scheduler actif
while True:
    schedule.run_pending()
    time.sleep(1)