# France Culture Downloader

Ce dossier contient les outils pour récupérer les émissions de la matinale de France Culture.

## Scripts

### `download_franceculture_range.py`
Télécharge l'intégrale de l'émission "Les Matins" (07h00) ainsi que tous ses segments/chroniques pour une plage de dates donnée.

**Utilisation :**
```bash
python download_franceculture_range.py DD-MM-YYYY DD-MM-YYYY
```

**Fonctionnement :**
1. **Scraping de la grille** : Identifie l'ID de l'émission "Les Matins" à 07h00.
2. **Récupération de l'intégrale** : Extrait l'URL MP3 directement depuis la page ou via l'API manifestation.
3. **Extraction des chroniques** : Interroge l'API `loadChroniclesGrid` de Radio France pour lister tous les segments rattachés à l'émission et les télécharge individuellement.
