# Déploiement de GroovyMorning 🚀

Ce guide explique comment installer votre serveur GroovyMorning personnel.

## Prérequis

1.  **Docker & Docker Compose** installés sur votre machine (Raspberry Pi, NAS, ou PC).

## Installation Rapide

1.  **Récupérer le projet :**
    ```bash
    git clone https://github.com/votre-repo/GroovyMorning.git
    cd GroovyMorning
    ```

2.  **Configurer l'environnement :**
    *   Créez un fichier `.env` à la racine du projet :
        ```bash
        cp .env.example .env
        ```
    *   Éditez le fichier `.env` pour y ajouter votre `DEEPSEEK_API_KEY`.

3.  **Lancer le serveur :**
    ```bash
    docker compose up -d
    ```

## Connexion de l'Application Mobile

1.  Ouvrez l'application GroovyMorning (iOS ou Android).
2.  Allez dans les **Réglages** (icône engrenage).
3.  Saisissez l'adresse IP locale de votre serveur (ex: `http://192.168.1.15:8000`).
4.  L'application se connectera automatiquement à votre serveur personnel.

## Architecture

*   **Données Privées :** Vos enregistrements audio et votre planning restent sur votre machine locale.
*   **Accès Local :** Par défaut, le serveur est accessible uniquement sur votre réseau local.
