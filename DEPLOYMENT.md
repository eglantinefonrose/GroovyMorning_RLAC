# Déploiement de GroovyMorning 🚀

Ce guide explique comment installer votre serveur GroovyMorning personnel et configurer l'accès à distance sécurisé.

## Prérequis

1.  **Docker & Docker Compose** installés sur votre machine (Raspberry Pi, NAS, ou PC).
2.  Un compte **Cloudflare** (gratuit) pour l'accès à distance.

## Installation Rapide

1.  **Récupérer le projet :**
    ```bash
    git clone https://github.com/votre-repo/GroovyMorning.git
    cd GroovyMorning
    ```

2.  **Configurer l'accès à distance :**
    *   Allez sur le [Dashboard Cloudflare Zero Trust](https://one.dash.cloudflare.com/).
    *   Créez un nouveau **Tunnel** (Networks > Tunnels).
    *   Choisissez un nom (ex: `groovy-home`) et enregistrez-le.
    *   Copiez le **Token** fourni.
    *   Créez un fichier `.env` à la racine du projet :
        ```bash
        cp .env.example .env
        ```
    *   Collez votre jeton dans le fichier `.env` : `TUNNEL_TOKEN=votre_jeton_ici`.

3.  **Lancer le serveur :**
    ```bash
    docker-compose up -d
    ```

## Configuration du Tunnel (Côté Cloudflare)

Dans l'onglet **Public Hostname** de votre tunnel sur Cloudflare :
*   **Subdomain :** `morning` (ou ce que vous voulez)
*   **Domain :** `votre-domaine.com`
*   **Service Type :** `HTTP`
*   **URL :** `java-backend:8000`

## Connexion de l'Application Mobile

1.  Ouvrez l'application GroovyMorning (iOS ou Android).
2.  Allez dans les **Réglages** (icône engrenage).
3.  Saisissez votre URL publique : `https://morning.votre-domaine.com`.
4.  L'application se connectera automatiquement à votre serveur personnel, récupérera son identifiant unique et synchronisera vos chroniques.

## Architecture de Sécurité

*   **Zéro Port Ouvert :** Vous n'avez pas besoin de toucher aux réglages de votre box internet.
*   **HTTPS :** Toutes les communications entre votre téléphone et votre maison sont cryptées.
*   **Données Privées :** Vos enregistrements audio et votre planning restent sur votre machine.
