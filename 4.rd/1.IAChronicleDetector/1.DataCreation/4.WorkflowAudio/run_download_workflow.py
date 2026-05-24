import os
import sys
import subprocess
import argparse
from datetime import datetime
from pathlib import Path

def run_script(script_path, start_date, end_date):
    """Exécute un script de téléchargement avec la plage de dates."""
    print(f"\n" + "="*60)
    print(f"🚀 LANCEMENT : {script_path.name}")
    print(f"="*60)
    
    # On s'assure d'être dans le dossier du script pour qu'il trouve ses chemins relatifs
    script_dir = script_path.parent
    script_name = script_path.name
    
    try:
        subprocess.run(
            [sys.executable, script_name, start_date, end_date],
            cwd=script_dir,
            check=True
        )
    except subprocess.CalledProcessError as e:
        print(f"❌ Erreur lors de l'exécution de {script_name} : {e}")
    except Exception as e:
        print(f"❌ Erreur inattendue : {e}")

def main():
    parser = argparse.ArgumentParser(description="Automatisation du téléchargement pour toutes les radios.")
    parser.add_argument("start", help="Date de début (DD-MM-YYYY)", type=str)
    parser.add_argument("end", help="Date de fin (DD-MM-YYYY)", nargs="?", type=str)
    
    args = parser.parse_args()
    
    start_date = args.start
    end_date = args.end if args.end else args.start
    
    # Validation basique du format de date
    try:
        datetime.strptime(start_date, "%d-%m-%Y")
        datetime.strptime(end_date, "%d-%m-%Y")
    except ValueError:
        print("❌ Format de date invalide. Utilisez DD-MM-YYYY (ex: 20-05-2026)")
        sys.exit(1)

    # Racine du projet (on remonte d'un niveau depuis 4.WorkflowAudio)
    root_dir = Path(__file__).parent.parent
    download_root = root_dir / "0.DownloadChroniquesAndFullRadioProgramAutomaticly"
    
    scripts = [
        download_root / "france-inter" / "download_franceinter_range.py",
        download_root / "france-info" / "download_franceinfo_range.py",
        download_root / "france-culture" / "download_franceculture_range.py",
        download_root / "rtl" / "download_rtl_range.py",
    ]
    
    print(f"--- WORKFLOW TÉLÉCHARGEMENT GLOBAL ---")
    print(f"Plage : {start_date} au {end_date}")
    print(f"Radios : France Inter, France Info, France Culture, RTL")
    print("-" * 40)

    for script in scripts:
        if script.exists():
            run_script(script, start_date, end_date)
        else:
            print(f"⚠️ Script non trouvé : {script}")

    print(f"\n" + "="*60)
    print(f"✅ WORKFLOW TÉLÉCHARGEMENT TERMINÉ")
    print(f"="*60)

if __name__ == "__main__":
    main()
