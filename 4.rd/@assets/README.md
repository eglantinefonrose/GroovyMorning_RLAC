# @assets - Radio Transcription & Segmentation Pipeline

Ce répertoire centralise les données et les résultats du pipeline d'automatisation pour le traitement des émissions radio (notamment la matinale de France Inter).

## Structure des Répertoires

Le projet est organisé selon une logique de **Workflow IA** en couches successives :

### Répertoire `0.media/ `
Contient les sources audio originales.
- `audio/0.france-inter-grande-matinale/` : Enregistrements MP3 complets des émissions.

### Répertoire `1.modelOutputs/`
Centralise tous les fichiers générés par les différents modèles d'IA.

#### Répertoire `0.transcriptions/`
Résultats du Speech-to-Text (STT).
- `0.transcriptions_whisper_tiny_et_base_mélangés/` : Tests avec des modèles légers.
- `1.transcriptions_whisper_ggml-large-v3-turbo/` : Transcriptions de haute précision (SRT) servant de base au découpage.

#### Répertoire `1.timecode-segments/`
Résultats du découpage sémantique et temporel.
- `0.manual-by-EFO/` : Segments validés manuellement (Vérité Terrain).
- `1.geminiCLI/` : Tentatives de segmentation automatique par LLM :
    - `0.gemini-flash-round1` / `1.gemini-pro-round1` : Découpage sémantique pur.
    - `2.gemini-flash-avec-vrais-horaires-théoriques-round1` : Découpage assisté par les programmes officiels.

## Workflow Sémantique

1.  **Transcription (Whisper)** : Conversion de l'audio en texte avec horodatage précis des segments.
2.  **Analyse de Programme (Parsing)** : Extraction des horaires théoriques depuis les sources HTML (schedule.html, sept_neuf.html).
3.  **Alignement (Gemini LLM)** : Le LLM confronte la transcription et le programme théorique pour identifier les bornes réelles (Timecodes) de chaque chronique.
4.  **Validation (RLAC Tool)** : (En cours) Correction manuelle des micro-décalages pour obtenir un index parfait.

## Outils et Spécifications
Les spécifications des outils internes (comme l'outil de vérification SwiftUI) se trouvent dans les répertoires correspondants aux outputs qu'ils valident.
