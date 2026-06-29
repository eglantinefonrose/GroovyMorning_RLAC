# 1. Chronicle Timecode Generation From Audios

Ce dossier contient les outils permettant de localiser précisément une chronique (segment court) au sein d'une émission intégrale (segment long).

## Fonctionnement : `generate_chronicle_timecodes.py`

Le script ne compare pas directement l'audio, mais utilise les **transcriptions (SRT)** générées précédemment.

### Algorithme
1. **Normalisation** : Le texte des transcriptions est nettoyé (suppression des accents, ponctuation, passage en minuscules).
2. **Recherche de correspondance** :
   - Il extrait des "chunks" (phrases) significatifs au début et à la fin de la chronique.
   - Il cherche ces séquences de caractères dans la transcription de l'émission intégrale.
   - Il valide la correspondance en vérifiant que la durée entre le début et la fin trouvés correspond à la durée réelle de la chronique (marge d'erreur acceptée : 2 minutes).
3. **Extraction des timecodes** : Une fois la zone identifiée, il récupère les timecodes `start` et `end` originaux de la transcription.

## Utilisation

```bash
python generate_chronicle_timecodes.py
```

### Entrées et Sorties
- **Entrées** : Transcriptions SRT situées dans `1.modelOutputs/0.transcriptions/`.
- **Sorties** : Fichiers texte contenant les plages horaires trouvées, enregistrés dans `@assets/2.humanOutputs/1.timecode-segments/`.

Format de sortie :
```text
00:12:34.500 - 00:15:20.100 : nom-de-la-chronique
```
