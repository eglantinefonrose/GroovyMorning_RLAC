# 2. Transcription Generation

Ce dossier contient le script d'automatisation de la transcription audio.

## Script : `prt-generate-transcripts-with-whisper.py`

Ce script sert d'interface (wrapper) pour l'outil `whisper.cpp` afin de traiter massivement les fichiers audio téléchargés.

### Caractéristiques
- **Traitement par lots** : Parcourt récursivement les dossiers de médias.
- **Gestion d'état** : Déplace les fichiers audio vers un dossier `audio-done` une fois la transcription réussie pour éviter de retraiter les mêmes fichiers.
- **Optimisation** : Utilise `whisper-cli` avec des modèles GGML (par défaut `large-v3-turbo`).
- **Fiabilité** : Force la langue en français (`-l fr`) pour éviter les hallucinations de traduction.

## Configuration

Le script possède des chemins par défaut configurés pour l'environnement local, mais ils peuvent être surchargés via les arguments :

| Argument | Description |
|----------|-------------|
| `--media-base-dir` | Répertoire racine des fichiers audio |
| `--transcription-output-dir` | Répertoire où enregistrer les .srt |
| `--whisper-cli-path` | Chemin vers l'exécutable `whisper-cli` |
| `--model-path` | Chemin vers le fichier modèle `.bin` |
| `--no-move-to-done-when-processed` | Désactive le déplacement vers `audio-done` |

## Exemple d'utilisation

```bash
python3 prt-generate-transcripts-with-whisper.py --whisper-cli-path /usr/local/bin/whisper-cli
```

## Dépendances
- `whisper.cpp` compilé et installé (`whisper-cli`).
- Un modèle Whisper compatible (ex: `ggml-large-v3-turbo.bin`).
