import argparse
import sys
import subprocess
from datetime import datetime
from pathlib import Path

def run_step(script_path, args):
    """Exécute un script avec ses arguments."""
    print(f"\n" + "█"*60)
    print(f" ETAPE : {script_path.name}")
    print(f"█"*60)
    
    try:
        subprocess.run(
            [sys.executable, str(script_path)] + args,
            check=True
        )
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Erreur lors de l'exécution de {script_path.name} : {e}")
        return False
    except Exception as e:
        print(f"❌ Erreur inattendue : {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Orchestrateur complet : Téléchargement + Trimming.")
    parser.add_argument("start", help="Date de début (DD-MM-YYYY)", type=str)
    parser.add_argument("end", help="Date de fin (DD-MM-YYYY)", nargs="?", type=str)
    parser.add_argument("--force", help="Forcer le re-trimming même si déjà fait", action="store_true")
    parser.add_argument("--dry-run", help="Mode dry-run pour le trimming", action="store_true")
    
    args = parser.parse_args()
    
    start_str = args.start
    end_str = args.end if args.end else args.start
    
    # Validation et conversion des dates
    try:
        start_dt = datetime.strptime(start_str, "%d-%m-%Y")
        end_dt = datetime.strptime(end_str, "%d-%m-%Y")
    except ValueError:
        print("❌ Format de date invalide. Utilisez DD-MM-YYYY (ex: 20-05-2026)")
        sys.exit(1)
        
    # Dates au format YYYY-MM-DD pour le script de trimming
    start_iso = start_dt.strftime("%Y-%m-%d")
    end_iso = end_dt.strftime("%Y-%m-%d")

    workflow_dir = Path(__file__).parent
    download_script = workflow_dir / "run_download_workflow.py"
    trimming_script = workflow_dir / "run_audio_workflow.py"

    print(f"╔" + "═"*58 + "╗")
    print(f"║ JOURNEY : FULL AUDIO WORKFLOW                           ║")
    print(f"╠" + "═"*58 + "╣")
    print(f"║ Période : {start_str} au {end_str}                     ║")
    print(f"╚" + "═"*58 + "╝")

    # Étape 1 : Téléchargement
    # run_download_workflow attend DD-MM-YYYY
    success = run_step(download_script, [start_str, end_str])
    
    if not success:
        print("\n⚠️  Le téléchargement a rencontré des erreurs. Tentative de poursuite avec le trimming...")

    # Étape 2 : Trimming
    # run_audio_workflow attend --start YYYY-MM-DD --end YYYY-MM-DD
    trim_args = ["--start", start_iso, "--end", end_iso]
    if args.force:
        trim_args.append("--force")
    if args.dry_run:
        trim_args.append("--dry-run")
        
    success_trim = run_step(trimming_script, trim_args)

    print(f"\n" + "="*60)
    if success_trim:
        print(f"✨ WORKFLOW COMPLET TERMINÉ AVEC SUCCÈS")
    else:
        print(f"⚠️  WORKFLOW TERMINÉ AVEC CERTAINES ERREURS")
    print("="*60)

if __name__ == "__main__":
    main()
