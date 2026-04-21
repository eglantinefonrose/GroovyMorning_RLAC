import os
import argparse
from huggingface_hub import snapshot_download

def pull_assets_from_hf(repo_id: str, srt_dest: str, tc_dest: str, token: str = None):
    """
    Télécharge les transcriptions et les timecodes depuis Hugging Face.
    """
    print(f"Téléchargement du dataset {repo_id} depuis Hugging Face...")
    
    # On télécharge tout le repo dans un dossier temporaire
    download_path = snapshot_download(
        repo_id=repo_id,
        repo_type="dataset",
        token=token
    )

    # On déplace ou on s'assure que les dossiers sont aux bons endroits
    import shutil
    
    # 1. Transcriptions
    hf_trans_dir = os.path.join(download_path, "transcriptions")
    if os.path.exists(hf_trans_dir):
        os.makedirs(os.path.dirname(srt_dest), exist_ok=True)
        if os.path.exists(srt_dest):
            shutil.rmtree(srt_dest)
        shutil.copytree(hf_trans_dir, srt_dest)
        print(f"Transcriptions (SRT) prêtes dans : {srt_dest}")
    
    # 2. Timecodes
    hf_tc_dir = os.path.join(download_path, "timecodes")
    if os.path.exists(hf_tc_dir):
        os.makedirs(os.path.dirname(tc_dest), exist_ok=True)
        if os.path.exists(tc_dest):
            shutil.rmtree(tc_dest)
        shutil.copytree(hf_tc_dir, tc_dest)
        print(f"Timecodes (TC) prêts dans : {tc_dest}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Télécharge les dossiers d'assets depuis Hugging Face")
    parser.add_argument("repo_id", help="ID du dépôt HF (ex: username/rlac-assets)")
    parser.add_argument("--srt_dest", default="../../@assets/1.modelOutputs/0.transcriptions/1.transcriptions_whisper_ggml-large-v3-turbo", help="Destination des SRT")
    parser.add_argument("--tc_dest", default="../../@assets/1.modelOutputs/1.timecode-segments/1.geminiCLI/2.gemini-flash-avec-vrais-horaires-théoriques/2.round3", help="Destination des TC")
    parser.add_argument("--token", help="Jeton Hugging Face (optionnel si déjà logué)")

    args = parser.parse_args()

    # Correction des chemins relatifs
    base_dir = os.path.dirname(os.path.abspath(__file__))
    srt_path = os.path.join(base_dir, args.srt_dest) if not os.path.isabs(args.srt_dest) else args.srt_dest
    tc_path = os.path.join(base_dir, args.tc_dest) if not os.path.isabs(args.tc_dest) else args.tc_dest

    pull_assets_from_hf(args.repo_id, srt_path, tc_path, args.token)
