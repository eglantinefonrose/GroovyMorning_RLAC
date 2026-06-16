# GMFM Radio France Demo (Android)

Cette application est une réplique fidèle de la spécification GMFM pour Android.

## Fonctionnalités implémentées
- **Thème Sombre Permanent** : Utilisation des couleurs spécifiées (Noir, Gris foncé, France Inter Rouge).
- **Splash Screen** : Affichage pendant 2.5s avec transition en fondu.
- **Navigation Principale** : 5 onglets (Accueil, Musique, Directs, Recherche, Bibliothèque).
- **Écran Accueil** : "Bonjour", carrousel de contenus, et skeleton loading (1.5s).
- **Écran Directs** : Carte France Inter avec boutons Contact et Grille.
- **Lecteur Plein Écran** : Overlay animé avec contrôles de lecture, slider et "Tool Pill".
- **Grille des Programmes** : Liste des chroniques avec bouton "Programmer".
- **Mode Simu** : Toggle en haut à droite pour basculer les paramètres serveurs.
- **Réglages IP** : Bouton de réglages sur l'écran d'accueil pour configurer l'adresse IP du serveur custom.
- **Architecture** : MVVM, Hilt (DI), Jetpack Compose, Media3 (Audio), Retrofit (API).

## Comment lancer l'application
1. Ouvrez **Android Studio**.
2. Choisissez **"Open"** et sélectionnez le dossier racine du projet.
3. Attendez la synchronisation de Gradle.
4. Sélectionnez un émulateur (par exemple, Pixel 6 avec API 34).
5. Cliquez sur le bouton **Run** (Triangle vert).

## Structure du Projet
- `ui/theme` : Définition des couleurs et du thème Material3.
- `ui/screens` : Composants Compose pour chaque écran.
- `ui/navigation` : Gestion des routes et de la barre de navigation.
- `audio` : Service de lecture basé sur Media3.
- `api` : Interface Retrofit pour les appels serveurs.
