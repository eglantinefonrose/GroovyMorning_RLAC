import argparse
import sys
import subprocess
from datetime import datetime
from pathlib import Path

def run_step(script_path, args, description):
    """Exécute un script avec ses arguments."""
    print(f"\n" + "█"*60)
    print(f" ETAPE : {description}")
    print(f" Script: {script_path.name}")
    print(f" args  : {' '.join(args)}")
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

def parse_date(date_str):
    """Tente de parser la date dans les deux formats courants."""
    for fmt in ("%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None

def main():
    parser = argparse.ArgumentParser(description="Orchestrateur complet : Téléchargement + Génération Timecodes + Trimming.")
    parser.add_argument("radio", help="Nom de la radio (ex: rtl, france-inter, france-info, france-culture)")
    parser.add_argument("date", help="Date cible (YYYY-MM-DD ou DD-MM-YYYY)")
    parser.add_argument("--force", help="Forcer le re-traitement même si déjà fait", action="store_true")
    parser.add_argument("--dry-run", help="Mode dry-run (ne modifie rien)", action="store_true")
    parser.add_argument("--skip-download", help="Sauter l'étape de téléchargement", action="store_true")
    
    args = parser.parse_args()
    
    # Validation et conversion de la date
    dt = parse_date(args.date)
    if not dt:
        print(f"❌ Format de date invalide : {args.date}. Utilisez YYYY-MM-DD ou DD-MM-YYYY.")
        sys.exit(1)
        
    date_iso = dt.strftime("%Y-%m-%d")
    date_dmy = dt.strftime("%d-%m-%Y")

    workflow_dir = Path(__file__).parent
    download_script = workflow_dir / "run_download_workflow.py"
    timecode_script = workflow_dir / "generate_timecodes_by_comparison.py"
    trimming_script = workflow_dir / "run_audio_workflow.py"

    print(f"╔" + "═"*58 + "╗")
    print(f"║ JOURNEY : FULL AUDIO WORKFLOW                           ║")
    print(f"╠" + "═"*58 + "╣")
    print(f"║ Radio   : {args.radio:45} ║")
    print(f"║ Date    : {date_iso:45} ║")
    print(f"╚" + "═"*58 + "╝")

    # Étape 1 : Téléchargement
    if not args.skip_download:
        # run_download_workflow attend DD-MM-YYYY
        download_args = [date_dmy, date_dmy, "--radio", args.radio]
        if not run_step(download_script, download_args, "Téléchargement des médias"):
            print("\n⚠️  Le téléchargement a échoué. Tentative de poursuite...")
    else:
        print("\n⏭️  Etape Téléchargement sautée.")

    # Étape 2 : Génération des Timecodes
    # generate_timecodes_by_comparison attend --radio et --date (YYYY-MM-DD)
    tc_args = ["--radio", args.radio, "--date", date_iso]
    if not run_step(timecode_script, tc_args, "Génération des timecodes par comparaison audio"):
        print("\n❌ La génération des timecodes a échoué. Arrêt du workflow.")
        sys.exit(1)

    # Étape 3 : Trimming (Découpage et export)
    # run_audio_workflow attend --radio et --date (YYYY-MM-DD)
    trim_args = ["--radio", args.radio, "--date", date_iso]
    if args.force:
        trim_args.append("--force")
    if args.dry_run:
        trim_args.append("--dry-run")
        
    success_trim = run_step(trimming_script, trim_args, "Trimming et export des segments")

    print(f"\n" + "="*60)
    if success_trim:
        print(f"✨ WORKFLOW COMPLET TERMINÉ AVEC SUCCÈS")
        print(f"   Date : {date_iso}")
        print(f"   Radio: {args.radio}")
    else:
        print(f"⚠️  WORKFLOW TERMINÉ AVEC CERTAINES ERREURS (Trimming)")
    print("="*60)

if __name__ == "__main__":
    main()
