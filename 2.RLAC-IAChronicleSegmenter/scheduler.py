import schedule
import time
import subprocess
import os
from dotenv import load_dotenv

# Charger les variables d'environnement depuis .env
load_dotenv()

import sys
from datetime import datetime

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

# Planification à 6h55 chaque jour
schedule.every().day.at("19:48").do(run_segmenter)

# SI on est en mode SIMU, on lance une première fois immédiatement pour tester
if os.environ.get("SIMU", "").lower() == "true":
    print("🧪 Mode SIMU détecté : Lancement immédiat pour test...")
    run_segmenter()

print(f"Scheduler démarré. Le segmenter sera lancé automatiquement à 6h55 chaque jour.")

# Garder le scheduler actif
while True:
    schedule.run_pending()
    time.sleep(1)