# Système de Découpage Dynamique Intelligent (RLAC)

Ce document explique le fonctionnement technique de la méthode de capture et de découpage des chroniques radio mise en œuvre dans ce serveur.

## Architecture "Master & Abonnés"

Le système repose sur un flux d'enregistrement unique, fragmenté en temps réel, qui sert de source à plusieurs tâches de distribution.

### 1. Le Flux Master (Référentiel Temporel)
Dès la première notification de début de chronique, un processus FFmpeg unique est lancé :
* **Localisation** : `media/continuous/`
* **Format** : HLS (fMP4) avec des segments de **1 seconde**.
* **Horodatage** : Le serveur capture l'heure système précise (`continuousStartTime`) au millième de seconde près au lancement du flux.
* **Calcul** : Chaque segment `N` possède un instant T théorique calculé : `T = continuousStartTime + (N * 1000ms)`.

### 2. Distribution par Liens Physiques (Hard Links)
Chaque chronique active possède sa propre tâche de surveillance. Plutôt que de copier les fichiers, le système utilise des **liens physiques** :
* **Efficacité** : Aucun coût CPU ou disque supplémentaire pour la duplication.
* **Temps Réel** : Dès qu'un segment est écrit par FFmpeg dans le dossier master, il est instantanément lié dans le dossier de la chronique correspondante si son horodatage correspond à la fenêtre de diffusion.

### 3. Logique de Découpage Dynamique

La précision du système repose sur sa capacité à ajuster la collection de segments "a posteriori" :

#### A. Phase d'Accumulation
Tant que la notification `EndTime` n'est pas reçue, la tâche de la chronique accumule tous les segments produits par le Master à partir de son `startTime`. Elle ne sait pas encore quand s'arrêter, donc elle "écoute" en continu.

#### B. Phase de Tronquage (Correction Rétroactive)
Lors de la réception de la requête `realChronicleEndTime` avec le paramètre `realDuration` :
1. **Calcul de la fin réelle** : `HeureFinRéelle = HeureDébut + realDuration`.
2. **Filtrage** : La tâche analyse tous les segments liés. Tout segment commençant après `HeureFinRéelle` est immédiatement supprimé du dossier de la chronique et retiré de son manifeste `.m3u8`.
3. **Transition Parfaite** : Cette `HeureFinRéelle` devient l'heure de début exacte de la chronique suivante.

### 4. Avantages du Système
* **Précision chirurgicale** : Découpe à la seconde près, indépendamment de la latence du réseau ou du délai des notifications API.
* **Zéro Perte** : Le flux master étant continu, il n'y a aucun trou entre deux chroniques, même si FFmpeg devait redémarrer.
* **Continuité du début** : En cas de chevauchement (un segment contenant la fin d'une chronique et le début de la suivante), le segment est présent dans les deux dossiers, garantissant que le début de la chronique suivante n'est jamais tronqué.
* **Gestion des ressources** : FFmpeg est automatiquement tué dès qu'aucune chronique n'est en attente ou lors de l'arrêt du serveur Gradle.

---
*Ce système assure une organisation stricte des dossiers (`media/userID_...`) tout en garantissant une expérience d'écoute fluide et complète pour l'utilisateur final.*
