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

## 2. Design System

Cette section détaille les tokens de configuration et les composants visuels extraits directement du code source. Les valeurs doivent être respectées à l'identique pour garantir la cohérence visuelle.

### 2.1. Palette de couleurs
L'application utilise un thème sombre permanent (`DarkColorScheme`). Les couleurs des stations de Radio France sont utilisées comme accents.

**Fichier : `com/gmfm/radiofrance/ui/theme/Theme.kt`**
```kotlin
val Black = Color(0xFF000000)
val DarkGray = Color(0xFF1A1A1A)
val Gray = Color(0xFF808080)
val White = Color(0xFFFFFFFF)

val FranceInter = Color(0xFFE2001A)
val FranceInfo = Color(0xFFFFD000)
val FranceCulture = Color(0xFF75338E)
val FranceMusique = Color(0xFFE5007D)

private val DarkColorScheme = darkColorScheme(
    primary = White,
    secondary = Gray,
    background = Black,
    surface = DarkGray,
    onPrimary = Black,
    onSecondary = White,
    onBackground = White,
    onSurface = White
)
```

### 2.2. Typographie
L'application s'appuie sur les styles Material3 avec des poids et tailles spécifiques pour structurer l'information.

**Fichier : `com/gmfm/radiofrance/ui/theme/Type.kt` (ou équivalent via MaterialTheme)**
- **Grands titres :** `MaterialTheme.typography.displaySmall` + `FontWeight.Bold` (Bonjour, Directs).
- **Titres de sections :** `MaterialTheme.typography.titleLarge` + `FontWeight.Bold` (À la une, Chroniques).
- **Titres d'items :** `MaterialTheme.typography.bodyLarge` ou `MaterialTheme.typography.titleMedium` + `FontWeight.Bold`.
- **Légendes / Durées :** `MaterialTheme.typography.bodySmall`, couleur `Color.Gray`.
- **Badges / MiniPlayer :** `MaterialTheme.typography.labelSmall`.

### 2.3. Formes et espacements (Shapes & Spacing)
L'interface privilégie des arrondis prononcés pour un aspect moderne.

**Rayons de coins (Shapes) :**
- **Cartes & Overlays :** `RoundedCornerShape(24.dp)`
- **MiniPlayer & Items de liste :** `RoundedCornerShape(16.dp)`
- **Thumbnails & Images :** `RoundedCornerShape(12.dp)` ou `8.dp`
- **Boutons :** `RoundedCornerShape(50)` (Style pilule)

**Espacements récurrents :**
- **Marges écrans :** `16.dp` ou `20.dp`
- **Gutter entre titres et contenu :** `24.dp`
- **Espacement entre items :** `16.dp`

### 2.4. Composants réutilisables custom

#### `MiniPlayer`
*Barre de lecture persistante au-dessus de la BottomBar.*
- **Conteneur :** `Surface` avec `FranceInter` color, height `64.dp`, shape `16.dp`, elevation `8.dp`.
- **Interaction :** `clickable` pour ouvrir le `PlayerView`.

#### `FeaturedCard`
*Utilisé pour le carrousel horizontal de l'accueil.*
- **Dimensions :** width `280.dp`.
- **Style :** `Card` avec background `0xFF1A1A1A` (DarkGray), shape `24.dp`.

#### `FranceInterCard`
*Composant héroïque de l'écran Direct.*
- **Style :** `Card` avec background `FranceInter`, shape `24.dp`.
- **Contenu :** Avatar circulaire (`CircleShape`) avec bordure blanche 2dp (alpha 0.5), logo Radio.

#### `LiveChronicleItem`
*Item de liste pour les chroniques.*
- **États :** Bordure de `1.dp` couleur `FranceInter` si en lecture. Opacité réduite (`Color.Gray`) si le contenu est indisponible.

### 2.5. Animations et transitions
- **Apparition du Player :** `AnimatedVisibility` avec `slideInVertically(initialOffsetY = { it })` (glissement depuis le bas).
- **Transitions d'écran :** Transition en fondu de `500ms` via `tween` (notamment sur le Splash).
- **Onboarding :** Glissement horizontal fluide entre les pages via `HorizontalPager` et `animateScrollToPage`.

### 2.6. Références Visuelles (Screenshots)
Les captures d'écran de référence se trouvent dans le dossier `app_screens_screenshots/`.

| Écran / Composant | Fichier PNG |
| :--- | :--- |
| Splash Screen | `SplashScreen.png` |
| Accueil (Home) | `HomeView.png` |
| Directs (Live) | `LiveView.png` |
| Mini Player | `MiniPlayer.png` |
| Lecteur (Player) | `PlayerView.png` |
| Grille (Schedule) | `ScheduleView.png` |
| Onboarding | *Non disponible* |

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
