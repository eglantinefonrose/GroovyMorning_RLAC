# RTL Downloader

Ce dossier contient les outils pour récupérer la matinale et les chroniques de RTL.

## Scripts

### `download_rtl_range.py`
Télécharge les épisodes de RTL Matin et les chroniques phares (Laurent Gerra, Philippe Caverivière, etc.) via les flux Audiomeans.

**Utilisation :**
```bash
python3 download_rtl_range.py DD-MM-YYYY DD-MM-YYYY
```

## Configuration des flux
Le script suit plusieurs flux RSS spécialisés :
- `laurent-gerra`
- `l-invite-de-rtl`
- `l-oeil-de-philippe-caveriviere`
- `rtl-matin` (Flux général)

## Logique d'identification
Pour le flux général `rtl-matin`, le script utilise des heuristiques pour identifier les chroniques si elles ne sont pas dans leur flux propre :
- **Auteur** : Recherche les tags `itunes:author` (ex: "Lenglet", "Cini", "Ventura").
- **Mots-clés** : Détecte les titres comme "Le Cave' réveil" ou "L'angle éco".
- **Intégrale** : Identifie les titres contenant "INTÉGRALE" pour servir de fichier de référence.
