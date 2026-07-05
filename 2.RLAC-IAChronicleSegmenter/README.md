# RLAC-IAChronicleSegmenter

Système de segmentation en temps réel des chroniques de France Inter.

## Installation
Assurez-vous d'avoir FFmpeg installé et les dépendances Python :
```bash
pip install -r requirements.txt
```

## Utilisation

À lancer **dans l'ordre suivant** dans des terminaux séparés.

### 1. Lancer le serveur API (facultatif)
```bash
python3 api-server.py
```

### 2. Lancer le segmenter
Vous pouvez choisir entre le mode **Legacy** (Jingles + Keywords) ou le mode **DeepSeek** (LLM).

**Mode Legacy (Whisper) :**
```bash
SIMU=true python3 src/live_radio_segmenter.py
```

**Mode DeepSeek + Kyutai (Optimisé Mac Silicon) :**
```bash
DETECTION_MODE=deepseek USE_KYUTAI=true SIMU=true python3 src/live_radio_segmenter.py
```
*Note : Nécessite une clé `DEEPSEEK_API_KEY` dans votre fichier `.env`.*

### 3. Alimenter le flux audio (Mode Simulation)
Le segmenter écoute sur `/tmp/audio_pipe`. Utilisez FFmpeg pour lui envoyer de l'audio.

**Depuis un fichier local :**
```bash
ffmpeg -re -i "assets/transitions_chroniques_à_la_suite.m4a" -f s16le -ac 1 -ar 16000 -y /tmp/audio_pipe
```

**Depuis le flux direct :**
```bash
ffmpeg -i https://stream.radiofrance.fr/franceinter/franceinter_hifi.m3u8 -f s16le -ac 1 -ar 16000 /tmp/audio_pipe
```

## Configuration
Les paramètres sont configurables dans le fichier `.env` :
- `DEEPSEEK_API_KEY` : Clé API pour le mode DeepSeek.
- `USE_KYUTAI` : `true` pour utiliser Kyutai STT, `false` pour Whisper.
- `SIMU` : `true` pour écouter sur le pipe, `false` pour le mode live (à implémenter).