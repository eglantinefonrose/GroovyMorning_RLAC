# Spécification Fonctionnelle - GMFM Radio France (Android)

L'application Android "GMFM Radio France Demo" doit être une réplique exacte de la version iOS, tant au niveau du design que des fonctionnalités. Voici la spécification technique et fonctionnelle détaillée pour le développement.

---

## 1. Architecture Technique Recommandée
- **Langage** : Kotlin
- **UI Framework** : Jetpack Compose (pour correspondre à SwiftUI)
- **Gestion d'état** : ViewModel avec StateFlow/SharedFlow
- **Navigation** : Jetpack Compose Navigation
- **Lecture Audio** : Media3 / ExoPlayer (support HLS/M3U8 requis)
- **Réseau** : Retrofit + OkHttp
- **Chargement d'images** : Coil
- **Injection de dépendances** : Hilt ou Koin

## 2. Thème et Design (AppTheme)
L'application utilise un **thème sombre permanent**.
- **Couleurs de base** :
    - Fond : `#000000` (Noir)
    - Cartes : `#1A1A1A` (Gris foncé)
    - Texte principal : `#FFFFFF` (Blanc)
    - Texte secondaire : `#808080` (Gris)
- **Couleurs de stations** :
    - France Inter : `#E2001A`
    - France Info : `#FFD000`
    - France Culture : `#75338E`
    - France Musique : `#E5007D`

## 3. Écrans et Navigation

### 3.1. Splash Screen
- **Visuel** : Image plein écran (`SplashImage`).
- **Comportement** : Affichage pendant 2.5 secondes, suivi d'une transition en fondu (0.5s) vers l'écran principal.

### 3.2. Navigation Principale (MainTabView)
Une `NavigationBar` en bas avec 5 onglets :
1. **Accueil** (`house.fill`)
2. **Musique** (`music.note`)
3. **Directs** (`antenna.radiowaves.left.and.right`)
4. **Recherche** (`magnifyingglass`)
5. **Bibliothèque** (`person.crop.circle`)

*Note : Un interrupteur "Simu" (Simulator Mode) doit être présent en superposition en haut à droite pour basculer entre `localhost` et l'IP personnalisée.*

### 3.3. Écran Accueil (HomeView)
- **En-tête** : Titre "Bonjour" en gras (Style `DisplaySmall`) et icône de réglages (gear) en haut à droite.
- **Contenu** :
    - Carrousel de contenus à la une (horizontal).
    - Cartes avec coins arrondis (24dp), titre gras, sous-texte (émission + durée) et bouton "Écouter" en forme de capsule.
    - Skeleton loading au démarrage (1.5s).

### 3.4. Écran Directs (LiveView)
- **Titre** : "Directs".
- **Carte Station (France Inter)** :
    - Fond rouge Inter.
    - Logo de la station en haut à droite.
    - Image de l'animateur dans un cercle avec bordure translucide.
    - Titre de l'émission actuelle.
    - Bouton principal "Écouter" (Blanc, texte Noir, Capsule).
    - Deux boutons secondaires en bas : "Contact" et "Grille" (Fond noir translucide).
- **Interactions** : Le bouton "Grille" navigue vers l'écran de programmation. Support du "Pull-to-refresh".

### 3.5. Lecteur Plein Écran (PlayerView)
- **Ouverture** : S'affiche en mode `fullScreenCover`.
- **Composants** :
    - Bouton de fermeture (X) en bas de l'écran.
    - Carte supérieure avec logo France Inter.
    - Carte centrale rouge contenant :
        - Image de l'émission ("ZOOM ZOOM ZEN").
        - Titre de la chronique actuelle.
        - Slider de progression personnalisé (blanc).
        - Contrôles : Précédent, Retour 15s, Lecture/Pause, Avance 30s, Suivant.
        - "Tool Pill" en bas de carte : Minuteur de sommeil, Vitesse (x1), Haut-parleur, Liste.
    - Liste des "Chroniques du jour" sous la carte rouge.
    - Bouton "Clock" pour ouvrir les réglages de l'heure d'enregistrement (Picker Heure/Minute).

### 3.6. Grille des Programmes (ScheduleView)
- **Fonctionnalité** : Liste verticale des chroniques.
- **Réordonnancement** : Support du "Drag and Drop" pour changer l'ordre des chroniques.
- **Validation** : Bouton "Programmer" en bas qui envoie l'ordre au serveur via API.

## 4. Logique Audio (AudioPlayerManager)
- **Flux** : Support des manifests `.m3u8` (HLS).
- **Parsing** : Implémenter une logique de parsing M3U8 pour calculer la durée totale et gérer les segments.
- **Contrôles précis** :
    - Seeking fluide avec mise en cache du buffer.
    - Support du "Background Playback" via MediaSession.
    - Gestion du buffering avec indicateur de chargement.

## 5. API et Données (APIService)
Endpoints à implémenter :
- `GET /api/findTodayFolder?userId=8dcb13c3` : Récupère le dossier du jour.
- `GET /api/getUserChronicles?userId=8dcb13c3` : Récupère la liste des chroniques.
- `POST /api/addChronicle` : Ajoute une chronique à la programmation.
- `DELETE /api/removeChronicles` : Réinitialise la liste.
- `POST /api/setUserBaseTime` : Définit l'heure de début de l'enregistrement.
- `GET /api/getUserBaseTime` : Récupère l'heure configurée.
