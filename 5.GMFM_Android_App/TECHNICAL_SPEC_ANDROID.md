# Spécification Technique - Application Android GMFM

Cette spécification détaille l'architecture et le fonctionnement de l'application Android **GroovyMorning (GMFM)** située dans le dossier `5.GMFM_Android_App`.

---

## 1. Vue d'ensemble

L'application est conçue pour permettre aux utilisateurs d'écouter les chroniques de France Inter de manière personnalisée, en recalibrant les flux audio en fonction de leur heure de réveil.

- **Architecture** : MVVM (Model-View-ViewModel) avec Jetpack Compose pour l'interface utilisateur.
- **Injection de Dépendances** : Hilt (Dagger).
- **Navigation** : Navigation Compose (système de routes déclaratives).
- **Gestion Audio** : Media3 (ExoPlayer + MediaSession) pour le support HLS et le contrôle en arrière-plan.
- **SDK** : 
    - `minSdk` : 26 (Android 8.0)
    - `targetSdk` : 34 (Android 14)
- **Module Gradle** : Unique module `:app`.

---

## 2. Écrans et flux utilisateur

### Flux de navigation principal
1.  **SplashScreen** (`SplashScreen.kt`) : Écran de démarrage affichant le logo. Redirige vers `MainScreen`.
2.  **OnboardingCarousel** (`OnboardingCarousel.kt`) : Affiché lors de la première visite ou via l'icône d'aide. Présente les fonctionnalités.
3.  **MainScreen** (`MainScreen.kt`) : Conteneur principal gérant la barre de navigation basse et les overlays (Player, Dialogues).

### Écrans (Views)
-   **HomeView** (`HomeView.kt`) :
    -   **Rôle** : Tableau de bord d'accueil.
    -   **Données** : Liste "À la une" des chroniques.
    -   **Actions** : Lancement rapide d'une chronique, accès aux réglages.
-   **LiveView** (`LiveView.kt`) :
    -   **Rôle** : Accès aux directs et à la liste complète des chroniques détectées.
    -   **Données** : Carte "France Inter" pour le direct, liste verticale des chroniques avec état de lecture.
    -   **Navigation** : Vers `ScheduleView` (Grille).
-   **ScheduleView** (`ScheduleView.kt`) :
    -   **Rôle** : Personnalisation de l'ordre de passage.
    -   **Actions** : Réorganisation des chroniques (monter/descendre), sauvegarde de la programmation via le bouton "Programmer".
-   **PlayerView** (`PlayerView.kt`) :
    -   **Rôle** : Lecteur plein écran (overlay animé).
    -   **Actions** : Play/Pause, Skip, sélection de chronique, fermeture.
-   **MiniPlayer** (intégré à `MainScreen.kt`) :
    -   **Rôle** : Barre de contrôle persistante en bas de l'écran quand un audio est actif mais le player plein écran fermé.

---

## 3. Modèles de données

Les modèles sont situés dans le package `com.gmfm.radiofrance.model`.

-   **Chronicle** (`Chronicle.kt`) :
    -   `title` : Titre de la chronique (ex: "La revue de presse").
    -   `startTime` / `endTime` : Timecodes relatifs (en secondes) par rapport à l'heure de début d'enregistrement.
    -   `duration` : Calculé dynamiquement (`endTime - startTime`).
    -   `imageUrl` : URL de l'image (optionnel).
-   **ChroniclesResponse** (`ChroniclesResponse.kt`) :
    -   `chronicles` : Liste d'objets `Chronicle`.
    -   `updated` : Flag indiquant si la grille a été mise à jour côté serveur.
-   **UserConfig** (`UserConfig.kt`) :
    -   Contient `baseHour` et `baseMinute` configurés par l'utilisateur.
-   **PreferencesManager** (`PreferencesManager.kt`) :
    -   Gère la persistance locale simple (ex: `isFirstVisit`) via SharedPreferences.

---

## 4. Communication réseau

L'application communique avec un serveur API (généralement le module Python `2.RLAC-IAChronicleSegmenter`).

-   **Base URL** : Configurable dans les réglages de l'app (par défaut `http://192.168.1.85:8100/`).
-   **Service API** (`APIService.kt`) :
    -   `GET /api/findTodayFolder` : Récupère le nom du dossier du jour (format date).
    -   `GET /api/getUserBaseTime` : Récupère l'heure de réveil configurée.
    -   `GET /api/getUserChronicles` : Récupère la liste des chroniques détectées pour l'utilisateur `8dcb13c3`.
    -   `POST /api/addChronicle` : Ajoute une chronique à la programmation.
    -   `DELETE /api/removeChronicles` : Supprime la programmation actuelle pour réinitialisation.
    -   `POST /api/setUserBaseTime` : Met à jour l'heure de réveil.

### Gestion Audio
L'audio est servi via des flux **HLS (.m3u8)**. L'URL est construite dynamiquement dans `MainScreen.kt` :
`base_url / folder_name / cleaned_title / cleaned_title.m3u8`

---

## 5. Règles métier côté client

-   **Nettoyage des titres** : Pour correspondre aux fichiers sur le serveur, les titres sont normalisés (suppression des accents, remplacement des caractères spéciaux par `_`) avant de construire l'URL HLS.
-   **Logique de programmation** : Lors du clic sur "Programmer", l'application vide d'abord la liste côté serveur (`DELETE`), puis itère sur la liste locale pour envoyer chaque chronique (`POST`) dans l'ordre choisi.
-   **Calcul des heures** : Les heures affichées sont calculées en ajoutant l'offset `startTime` de la chronique à l'heure de base (`baseHour`/`baseMinute`) configurée.
-   **Mode Simulation** : Présent dans le `MainViewModel`, permet de forcer l'IP locale pour les tests.

---

## 6. Dépendances externes

-   **Retrofit & OkHttp** : Client HTTP et parsing JSON.
-   **Coil** : Chargement asynchrone des images.
-   **Media3** : Lecture audio HLS et gestion de la session multimédia Android.
-   **Dagger Hilt** : Injection de dépendances pour les ViewModels et services.
-   **Jetpack Compose Material3** : Composants UI modernes.

---

## 7. Code mort / suspect

| Élément | Type | Preuve / Raison |
| :--- | :--- | :--- |
| `ChronicleRequest.kt` | Modèle | Jamais importé ou utilisé dans `APIService` (qui utilise des `@Query` individuels). |
| Logs "GMFM_BOOT" | Code | Présents dans `MainActivity.onCreate`, traces de debug persistantes qui devraient être supprimées en production. |
| `ScheduleView.kt:102` | Logique | `val displayTime = chronicle.getFormattedTime(7, 0)` utilise des valeurs en dur au lieu de `baseHour`/`baseMinute` du ViewModel. |
| `MainViewModel.isSimuMode` | Feature | Semble redondant avec la gestion manuelle de l'IP serveur, utilisé de manière inconsistante. |
| Ressources XML | UI | Comme l'app est en Compose, de nombreux fichiers dans `res/layout` (si présents) ou styles anciens pourraient être inutilisés (à vérifier via inspection Android Studio). |

---
*Fichiers consultés : `APIService.kt`, `MainViewModel.kt`, `MainScreen.kt`, `ScheduleView.kt`, `Chronicle.kt`, `build.gradle.kts`.*
