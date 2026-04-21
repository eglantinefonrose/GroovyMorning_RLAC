# Téléchargement automatique des émissions de France Info

Ce dossier contient les outils nécessaires pour automatiser la récupération des émissions et chroniques de la matinale de France Info (Le 6/9).

## Fonctionnement de `download_franceinfo_range.py`

Le script `download_franceinfo_range.py` permet de télécharger l'intégrale et les chroniques sur une plage de dates donnée, en ignorant automatiquement les week-ends.

### Stratégie de récupération

Le programme utilise une stratégie hybride pour maximiser le nombre de chroniques récupérées :

1.  **Extraction de la Grille** : Pour chaque date, le script accède à la grille des programmes de France Info pour identifier l'identifiant unique (UUID) du bloc "Le 6/9".
2.  **Appel API Chroniques** : Il interroge l'API interne de Radio France pour obtenir la liste de tous les segments (chroniques, journaux, fils info) rattachés à cette émission.
3.  **Détection Hybride des Audios** :
    *   **Méthode Podcast** : Pour les chroniques officielles, il visite la page de l'émission pour en extraire le lien MP3 direct.
    *   **Méthode Manifestation (Orphelins)** : Pour les segments qui n'ont pas de page web dédiée (comme le "Fil info", la météo ou certains journaux), le script utilise l'API de manifestation interne (`/api/v1/manifestations/`) en testant les UUIDs et les identifiants techniques (ITEMA) trouvés dans les données de la grille.

### Utilisation

```bash
python3 download_franceinfo_range.py DD-MM-YYYY DD-MM-YYYY
```

Exemple pour récupérer la semaine du 13 au 17 avril 2026 :
```bash
python3 download_franceinfo_range.py 13-04-2026 17-04-2026
```

### Organisation des fichiers

Les fichiers sont téléchargés dans l'arborescence suivante :
`@assets/0.media/audio/3.franceinfo-matin/[DATE]/`
-   `[DATE].mp3` : L'intégrale de la matinale.
-   `chroniques/` : Dossier contenant chaque segment individuel nommé selon son titre (ex: `le-fil-info-a-6h20.mp3`, `le-vrai-ou-faux.mp3`).

## Amélioration de la détection

Contrairement aux versions précédentes qui ne récupéraient que 12 chroniques sur 23, cette version "agressive" tente de résoudre chaque identifiant technique présent dans le flux de données Radio France pour minimiser les manques et fournir un jeu de données complet pour l'entraînement.

### Détection partielle des segments
Dans le cas des émissions de France Info, il ne semble pas possible de récupérer toutes les chroniques du matin (12 sur 23 chroniques).  
On considère donc uniquement les 12 chroniques disponibles au téléchargement, et on adapte la transcription et les timecodes des chroniques pour l'entraînement.
