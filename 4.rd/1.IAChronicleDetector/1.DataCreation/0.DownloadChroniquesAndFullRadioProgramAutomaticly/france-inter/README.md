# France Inter Downloader

Ce dossier contient les outils pour récupérer la matinale de France Inter via ses flux RSS.

## Scripts

### `download_franceinter_range.py`
Télécharge les émissions "Le 6/7", "La grande matinale" et "Le Mag" pour une plage de dates donnée.

**Utilisation :**
```bash
python download_franceinter_range.py DATE_DEBUT [DATE_FIN]
```

## Fonctionnement
1. **Détection RSS** : Scrape les pages de concepts pour trouver l'URL du flux RSS (`rssFeed`).
2. **Filtrage temporel** : Ne conserve que les items publiés entre 06h00 et 10h00.
3. **Distinction Intégrale/Chronique** : 
   - Les fichiers de plus de 30 minutes ou contenant des mots-clés spécifiques ("Le 7/9", "Le 6/9") sont considérés comme des **intégrales**.
   - Les segments plus courts sont classés comme **chroniques**.
4. **Sortie** : Organise les fichiers par heure de diffusion (ex: `[08h20]_Le_billet.mp3`).
