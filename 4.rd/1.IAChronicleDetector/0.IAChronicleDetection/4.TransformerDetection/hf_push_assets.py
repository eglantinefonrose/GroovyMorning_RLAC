import os
import argparse
from huggingface_hub import HfApi, create_repo

def push_assets_to_hf(repo_id: str, srt_dir: str, tc_dir: str, token: str = None):
    """
    Pousse les dossiers de SRT et de TC vers un dépôt Hugging Face Dataset.
    """
    api = HfApi(token=token)
    
    # Création du dépôt s'il n'existe pas (type dataset)
    try:
        create_repo(repo_id=repo_id, repo_type="dataset", exist_ok=True)
        print(f"Dépôt {repo_id} prêt.")
    except Exception as e:
        print(f"Erreur lors de la préparation du dépôt : {e}")
        return

    print(f"Début de l'upload des SRT depuis {srt_dir}...")
    api.upload_folder(
        folder_path=srt_dir,
        path_in_repo="transcriptions",
        repo_id=repo_id,
        repo_type="dataset",
    )

    print(f"Début de l'upload des TC depuis {tc_dir}...")
    api.upload_folder(
        folder_path=tc_dir,
        path_in_repo="timecodes",
        repo_id=repo_id,
        repo_type="dataset",
    )

    print(f"\nSuccès ! Les assets sont disponibles sur : https://huggingface.co/datasets/{repo_id}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pousse les dossiers d'assets vers Hugging Face")
    parser.add_argument("repo_id", help="ID du dépôt HF (ex: username/rlac-assets)")
    parser.add_argument("--srt_dir", default="../../@assets/1.modelOutputs/0.transcriptions/1.transcriptions_whisper_ggml-large-v3-turbo", help="Dossier des SRT")
    parser.add_argument("--tc_dir", default="../../@assets/1.modelOutputs/1.timecode-segments/1.geminiCLI/2.gemini-flash-avec-vrais-horaires-théoriques/2.round3", help="Dossier des TC")
    parser.add_argument("--token", help="Jeton Hugging Face (optionnel si déjà logué)")
    
    args = parser.parse_args()
    
    # Correction des chemins relatifs par rapport au root du projet si nécessaire
    base_dir = os.path.dirname(os.path.abspath(__file__))
    # On gère si les dossiers sont hors du projet (../../..@assets)
    srt_path = os.path.join(base_dir, args.srt_dir) if not os.path.isabs(args.srt_dir) else args.srt_dir
    tc_path = os.path.join(base_dir, args.tc_dir) if not os.path.isabs(args.tc_dir) else args.tc_dir

    if not os.path.exists(srt_path) or not os.path.exists(tc_path):
        print(f"Erreur : Un des dossiers est introuvable.\nSRT: {srt_path}\nTC: {tc_path}")
    else:
        push_assets_to_hf(args.repo_id, srt_path, tc_path, args.token)
