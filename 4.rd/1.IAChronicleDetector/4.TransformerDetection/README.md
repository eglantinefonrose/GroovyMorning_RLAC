# Transformer Chronicle Detector

Ce projet utilise un modèle CamemBERT (BERT pour le français) pour détecter les chroniques dans les transcriptions d'émissions de radio.

## Installation

Assurez-vous d'avoir `uv` installé, ou utilisez `pip` :

```bash
pip install -r requirements.txt
# Ou via uv
uv sync
```

## Entraînement

Pour entraîner le modèle avec les données présentes dans `@assets` :

```bash
python train.py
```

Le modèle sera sauvegardé dans le dossier `models/camembert_chronicle`.

## Détection (Prédiction)

Pour lancer la détection sur une nouvelle transcription au format `.srt` :

```bash
python predict.py ../../@assets/1.modelOutputs/0.transcriptions/1.transcriptions_whisper_ggml-large-v3-turbo/26811-06.04.2026-ITEMA_24466243-2026F10761S0096-NET_MFI_8F75AA4E-79C7-4CF3-A0B7-2D7EBC1FB5B5-22-534f5f6ae83fc95044c42304b90ca1f7_transcription.srt
```

## Structure du projet

- `train.py` : Script d'entraînement.
- `predict.py` : Script de détection.
- `src/dataset.py` : Gestionnaire de données PyTorch avec fenêtre contextuelle.
- `src/utils.py` : Utilitaires pour le parsing des fichiers SRT et des timecodes.
- `models/` : Dossier où le modèle entraîné est stocké.

## Résultats
Les frontières entre les chroniques sont parfaitement détectées, mais des fois une chronique en contient deux.