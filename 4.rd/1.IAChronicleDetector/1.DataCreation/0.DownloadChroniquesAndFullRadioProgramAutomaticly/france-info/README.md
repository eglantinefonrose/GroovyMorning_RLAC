# France Info Downloader

Ce dossier contient les outils pour récupérer les émissions de la matinale de France Info.

## Scripts

### `download_franceinfo_range.py`
Script principal pour télécharger les émissions (intégrales et chroniques) sur une période donnée.

**Utilisation :**
```bash
python download_franceinfo_range.py DD-MM-YYYY DD-MM-YYYY
```

### `download_franceinfo_6_9.py`
Variante focalisée spécifiquement sur le bloc "6/9". Elle identifie le segment de 06h00 comme étant l'intégrale de référence.

## Particularités
- **Identification par UUID** : Utilise les identifiants uniques de Radio France trouvés dans le code source de la grille des programmes.
- **API Manifestation** : Tente plusieurs points d'entrée API (`/api/v1/manifestations/` et `/api/v1/player/manifestations/`) pour garantir la récupération du lien MP3.
- **Normalisation** : Renomme l'intégrale de 06h00 avec la date du jour (`JJ-MM-AAAA.mp3`) pour faciliter l'alignement ultérieur.
