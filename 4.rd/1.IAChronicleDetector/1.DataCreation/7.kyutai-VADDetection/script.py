#!/usr/bin/env python3
"""
Transcrit un fichier audio avec Kyutai STT (modèle 1B en_fr) et exporte
texte + timestamps mot-par-mot + marqueurs de silence (VAD sémantique)
dans un fichier .txt créé au même niveau que ce script.

Usage :
    python transcrire_emission.py chemin/vers/emission.mp3
"""

import json
import subprocess
import sys
from pathlib import Path

# --- Configuration ---------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
STT_BINARY = SCRIPT_DIR / "delayed-streams-modeling" / "stt-rs" / "target" / "release" / "kyutai-stt-rs"
SILENCE_THRESHOLD_S = 1.5  # au-delà, on flague comme rupture potentielle (chronique/jingle)


def run_kyutai_stt(audio_path: Path) -> str:
    """Lance le binaire Rust Kyutai STT avec timestamps + VAD, retourne stdout brut."""
    if not STT_BINARY.exists():
        sys.exit(
            f"Binaire introuvable : {STT_BINARY}\n"
            "Compile-le avec :\n"
            "  git clone https://github.com/kyutai-labs/delayed-streams-modeling\n"
            "  cd delayed-streams-modeling/stt-rs && cargo build --release"
        )
    cmd = [str(STT_BINARY), str(audio_path), "--timestamps", "--vad", "--cpu"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        sys.exit(f"Erreur lors de la transcription :\n{result.stderr}")
    return result.stdout


def parse_output(raw_output: str):
    """
    Tente de parser la sortie en lignes JSON du type {"word": .., "start": .., "end": ..}.
    Si une ligne n'a pas ce format, elle est conservée brute pour ne rien perdre.
    """
    words = []
    for line in raw_output.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
            word = data.get("word") or data.get("text")
            if word is not None:
                words.append({
                    "word": word,
                    "start": data.get("start"),
                    "end": data.get("end"),
                })
                continue
        except json.JSONDecodeError:
            pass
        words.append({"raw": line})
    return words


def build_report(words, raw_output: str) -> str:
    lines = ["=== TRANSCRIPTION KYUTAI STT — texte, timestamps, silences ===\n"]
    full_text = []
    prev_end = None

    for w in words:
        if "word" in w and w.get("start") is not None:
            start, end, word = w["start"], w["end"], w["word"]
            full_text.append(word)

            silence_marker = ""
            if prev_end is not None:
                gap = start - prev_end
                if gap >= SILENCE_THRESHOLD_S:
                    silence_marker = f"   <<< SILENCE {gap:.2f}s (rupture possible) >>>"

            lines.append(f"[{start:7.2f}s -> {end:7.2f}s] {word}{silence_marker}")

            prev_end = end

    lines.append("\n=== TEXTE COMPLET ===\n")
    lines.append(" ".join(full_text) if full_text else "(aucun mot structuré détecté — voir sortie brute ci-dessous)")

    lines.append("\n\n=== SORTIE BRUTE DU MODÈLE (référence / debug) ===\n")
    lines.append(raw_output)

    return "\n".join(lines)


def main():
    if len(sys.argv) != 2:
        sys.exit("Usage : python transcrire_emission.py chemin/vers/audio.mp3")

    audio_path = Path(sys.argv[1]).resolve()
    if not audio_path.exists():
        sys.exit(f"Fichier audio introuvable : {audio_path}")

    print(f"Transcription de {audio_path.name} en cours...")
    raw_output = run_kyutai_stt(audio_path)
    words = parse_output(raw_output)
    report = build_report(words, raw_output)

    output_path = SCRIPT_DIR / f"{audio_path.stem}_transcription.txt"
    output_path.write_text(report, encoding="utf-8")

    print(f"✔ Transcription enregistrée dans : {output_path}")


if __name__ == "__main__":
    main()