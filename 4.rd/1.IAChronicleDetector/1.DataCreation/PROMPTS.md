Est-ce que tu peux me dire si le programme permet de traiter un ensemble de morceaux.
 - J'ai une hiérarchie de chroniques stockées dans `@assets/0.media/audio`.
 - Et j'ai des transcriptions stockées `@assets/1.modelOutputs/0.transcriptions/[N].transcriptions_<MODELNAME>`

Fais en sorte que je puisse lancer le script `prt-generate-transcripts-with-kyutai_stt_2.6b_fr.py` sur l'ensemble des morceaux qui
sont dans le path fournis (par exemple `@assets/0.media.audio`) et que ça stocke le résultat dans `@assets/1.modelOutputs/0.transcriptions/2.transcriptions_kyutai_stt_2.6b_fr`.


```
% tree -L 4 -d @assets
@assets
├── 0.media
│   ├── audio
│   │   ├── 1.rtl-matin
│   │   │   ├── 06-04-2026
│   │   │   ├── 07-04-2026
│   │   │   ├── 08-04-2026
│   │   │   ├── 13-04-2026
│   │   │   ├── 14-04-2026
│   │   │   ├── 15-04-2026
│   │   │   ├── 16-04-2026
│   │   │   ├── 17-04-2026
│   │   │   ├── 20-04-2026
│   │   │   ├── 21-04-2026
│   │   │   ├── 22-04-2026
│   │   │   └── 23-04-2026
│   │   ├── 2.franceinfo-matin
│   │   │   ├── 01-01-2026
│   │   │   ├── 01-04-2026
│   │   │   ├── [...]
│   │   │   ├── 30-04-2026
│   │   │   └── 31-03-2026
│   │   ├── 3.franceculture-matin
│   │   │   ├── 01-04-2026
│   │   │   ├── 01-05-2026
│   │   │   ├── [...]
│   │   │   ├── 29-04-2026
│   │   │   └── 30-04-2026
│   │   ├── 4.franceculture-matin
│   │   │   └── 02-03-2026
│   │   ├── 4.franceinter-matin
│   │   │   ├── 01-04-2026
│   │   │   ├── 02-02-2026
│   │   │   ├── [...]
│   │   │   ├── 30-04-2026
│   │   │   └── 31-03-2026
│   │   └── 5.rtl-matin
│   │       ├── 01-04-2026
│   │       ├── 01-05-2026
│   │       ├── [...]
│   │       ├── 30-04-2026
│   │       └── 31-03-2026
│   └── audio-done
│       ├── 1.rtl-matin
│       │   ├── 06-04-2026
│       │   ├── 07-04-2026
│       │   ├── 14-04-2026
│       │   ├── 17-04-2026
│       │   ├── 21-04-2026
│       │   └── 22-04-2026
│       ├── 2.franceinfo-matin
│       ├── 3.franceculture-matin
│       └── 4.franceinter-matin
├── 1.modelOutputs
│   ├── 0.transcriptions
│   │   ├── 0.transcriptions_whisper_tiny_et_base_mélangés
│   │   └── 1.transcriptions_whisper_ggml-large-v3-turbo
│   │       ├── 1.rtl-matin
│   │       ├── 2.franceinfo-matin
│   │       ├── 3.franceculture-matin
│   │       ├── 4.franceinter-matin
│   │       └── @misc
│   └── 1.timecode-segments
│       └── 1.geminiCLI
│           ├── 0.gemini-flash
│           ├── 1.gemini-pro
│           ├── 2.gemini-flash-avec-vrais-horaires-théoriques
│           └── 3.detection-avec-transcription-de-chaque-chronique
└── 2.humanOutputs
    └── 1.timecode-segments
        ├── 0.manual-by-EFO
        │   └── timecodes_files
        ├── 1.automatic-from-chronique-transcription
        └── 2.audio-analyse
            ├── __pycache__
            └── timecode_chroniques

362 directories
```

---

Quand je traite une grosse hiérarchie de fichiers, le traitement peut être long et je voudrais avoir une visualisation de la progression. Fais en sorte que le script commence par scanner l'ensemble des fichiers qui vont être traités en regardant leur taille et modifier le script pour qu'il affiche un indicateur de progression pendant que les transcriptions ont lieu. Essaye de faire une estimation du temps restant en fonction du temps déjà écoulé (bien sûr, au départ, cette estimation sera non définie et elle ne pourra être affinée qu'au bout d'un certain temps).

---

Ça bugge
```
📦 Chargement des bibliothèques AI (torch, transformers)...
🖥️  Utilisation du device: mps
📥 Chargement du modèle kyutai/stt-1b-en_fr...
Warning: You are sending unauthenticated requests to the HF Hub. Please set a HF_TOKEN to enable higher rate limits and faster downloads.
❌ Erreur lors du chargement du modèle: Can't load feature extractor for 'kyutai/stt-1b-en_fr'. If you were trying to load it from 'https://huggingface.co/models', make sure you don't have a local directory with the same name. Otherwise, make sure 'kyutai/stt-1b-en_fr' is the correct path to a directory containing a preprocessor_config.json file
```
