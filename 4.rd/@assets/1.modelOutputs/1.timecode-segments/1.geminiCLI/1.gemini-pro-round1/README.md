
# 0.gemini-flash-round1

## Intro

Nouvelle tentative en utilisant Gemini 3.1 Pro

## Prompts

Analyse d'un point de vue sémantique le fichier `1.modelOutputs/0.transcriptions/1.transcriptions_whisper_ggml-large-v3-turbo/06_04_2026.srt`.
C'est les deux heures de transcription de la grande matinale de France Inter
Cette matinale est découpée en chronique, en section de pubs, en journaux d'informations.
Est-ce que tu peux me trouver les Timecode qui correspondent à ces différentes chroniques.

Pour t'aider tu peux trouver la liste des chroniques et leurs horaires théorique à cette URL: https://www.radiofrance.fr/franceinter/grille-programmes?date=06-04-2026. Il faut aller chercher dans la section sept-neuf. Stocke ces horaires dans `06_04_2026_timecode_chronique_THEORITICAL.txt`

Met le résultat dans un fichier `06_04_2026_timecode_chronique.txt`

Stocke les résultats dans `1.modelOutputs/1.timecode-segments/1.geminiCLI/1.gemini-pro-round1`

## Conclusion

C'est encore plus pourri que la tentative précédente. Très très mauvaise récupération des horaires théoriques