# 0. Download Chroniques and Full Radio Program Automatically

Ce dossier contient des scripts spécialisés pour le téléchargement automatique des émissions de radio et de leurs chroniques respectives.

## Contenu

Le dossier est organisé par station de radio :
- **france-culture** : Téléchargement de la matinale "Les Matins" et de ses segments.
- **france-info** : Récupération du "6/9" et des chroniques associées.
- **france-inter** : Téléchargement de la matinale via les flux RSS.
- **rtl** : Récupération des flux Audiomeans pour RTL Matin et les chroniques de Laurent Gerra, Philippe Caverivière, etc.

## Utilisation générale

La plupart des scripts s'utilisent avec une plage de dates en argument.

### Radio France (Inter, Info, Culture)
```bash
python download_franceculture_range.py 01-04-2026 15-04-2026
```
Les scripts Radio France utilisent souvent une combinaison de :
1. Scraping de la grille des programmes pour trouver les IDs des émissions.
2. Appels aux APIs internes (`/api/v1/player/manifestations`).
3. Téléchargement direct des fichiers MP3.

### RTL
```bash
python3 download_rtl_range.py 01-04-2026 15-04-2026
```
Le script RTL utilise les flux RSS d'Audiomeans. Il identifie les chroniques via l'auteur (tags iTunes) ou des mots-clés dans les titres.

## Organisation des sorties
Les fichiers sont téléchargés dans une structure de type :
`@assets/0.media/audio/{station}/{date}/`
- L'intégrale est à la racine du dossier date.
- Les chroniques sont placées dans un sous-dossier `chroniques/`.
