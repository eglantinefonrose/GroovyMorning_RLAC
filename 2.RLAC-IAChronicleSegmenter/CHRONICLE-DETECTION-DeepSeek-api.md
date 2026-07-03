# Détection des Chroniques via l'API DeepSeek

Cette approche utilise l'intelligence artificielle (DeepSeek) pour détecter les lancements de chroniques à partir de la transcription en temps réel du flux radio.

## Fonctionnement

Contrairement à l'approche classique basée sur la corrélation acoustique de jingles ou la détection de mots-clés simples, cette méthode analyse le **contexte sémantique** des propos tenus à l'antenne.

### 1. Récupération de la Grille (Scraping)
Le système interroge dynamiquement le site de France Inter pour récupérer la liste des chroniques prévues pour la journée. Cela permet d'avoir une liste de cibles à jour sans intervention manuelle.

### 2. Analyse via DeepSeek
Le flux audio est transcrit par Whisper. Les phrases obtenues sont envoyées à l'API DeepSeek avec un "System Prompt" spécifique qui lui demande de distinguer :
- Les **annonces/teasing** ("Tout à l'heure à 8h20 nous recevrons...") qu'il faut ignorer.
- Les **lancements réels** ("Il est 8h20, l'invité de 8h20 est...") qu'il faut détecter.

### 3. Validation par Planning Théorique (Check Schedule)
Pour éviter les faux positifs (par exemple, si une chronique est mentionnée dans une discussion), une logique de validation compare la détection de l'IA avec l'horaire théorique :
- Une détection est rejetée si elle survient trop tôt par rapport à l'heure prévue (> 5 minutes).
- Une détection est rejetée si elle concerne une chronique déjà passée (respect de l'ordre chronologique).

## Avantages
- **Flexibilité** : Fonctionne même si les jingles changent ou si l'animateur lance la chronique différemment.
- **Maintenance réduite** : Pas besoin de maintenir une bibliothèque de jingles audio.
- **Contexte** : Capable de comprendre que "Le journal de 8h" n'a pas commencé juste parce que le mot "journal" a été prononcé.

## Configuration
Pour activer ce mode, le serveur doit être lancé avec la variable d'environnement `DETECTION_MODE=deepseek`.
La clé API doit être fournie via `DEEPSEEK_API_KEY`.
