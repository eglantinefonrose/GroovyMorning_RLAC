import adetector as adt
import sys
import os


def detecter_publicites(fichier_audio, seuil=0.85, fenetre=10):
    """
    Détecte les publicités dans un fichier audio.

    Args:
        fichier_audio (str): Chemin vers le fichier audio
        seuil (float): Seuil de confiance pour la détection (défaut: 0.85)
        fenetre (int): Taille de la fenêtre pour la moyenne mobile (défaut: 10)

    Returns:
        tuple: (timestamps, probabilites) - timestamps et probabilités associées
    """

    # Vérifier que le fichier existe
    if not os.path.exists(fichier_audio):
        print(f"❌ Erreur : Le fichier '{fichier_audio}' n'existe pas.")
        return None, None

    print(f"🔍 Analyse du fichier : {fichier_audio}")
    print(f"📊 Seuil de détection : {seuil}")
    print("-" * 50)

    # Étape 1 : Extraire les caractéristiques audio (MFCC)
    print("⏳ Extraction des caractéristiques audio...")
    X = adt.core.audio2features(fichier_audio)

    # Étape 2 : Détecter les publicités
    print("⏳ Détection des publicités en cours...")
    timestamps, probabilites = adt.core.find_ads(
        X,
        T=seuil,  # seuil de confiance
        n=fenetre,  # taille de la fenêtre pour moyenne mobile
        show=False  # mettre True pour voir le graphique
    )

    return timestamps, probabilites


def afficher_resultats(timestamps, probabilites):
    """Affiche les résultats de détection."""

    if timestamps is None or len(timestamps) == 0:
        print("\n📭 Aucune publicité détectée dans cet audio.")
        return

    print("\n" + "=" * 50)
    print(f"✅ {len(timestamps)} publicité(s) détectée(s) :")
    print("=" * 50)

    for i, (ts, prob) in enumerate(zip(timestamps, probabilites), 1):
        # Convertir les secondes en format MM:SS
        minutes = int(ts // 60)
        secondes = int(ts % 60)

        print(f"  {i}. Timestamp : {minutes:02d}:{secondes:02d}  |  Confiance : {prob:.1%}")

    print("=" * 50)

    # Statistiques
    confiance_moyenne = sum(probabilites) / len(probabilites)
    print(f"\n📈 Statistiques :")
    print(f"   - Nombre de détections : {len(timestamps)}")
    print(f"   - Confiance moyenne : {confiance_moyenne:.1%}")
    print(f"   - Confiance max : {max(probabilites):.1%}")


def main():
    """Fonction principale."""

    # Vérifier les arguments
    if len(sys.argv) < 2:
        print("Usage: python detect_ads.py <fichier_audio> [seuil] [fenetre]")
        print("\nExemples:")
        print("  python detect_ads.py radio.mp3")
        print("  python detect_ads.py radio.mp3 0.80 15")
        print("\nParamètres:")
        print("  seuil   : seuil de confiance (0.7 à 0.95, défaut: 0.85)")
        print("  fenetre : taille de moyenne mobile (défaut: 10)")
        sys.exit(1)

    # Récupérer les paramètres
    fichier_audio = sys.argv[1]
    seuil = float(sys.argv[2]) if len(sys.argv) > 2 else 0.85
    fenetre = int(sys.argv[3]) if len(sys.argv) > 3 else 10

    # Lancer la détection
    timestamps, probabilites = detecter_publicites(fichier_audio, seuil, fenetre)

    # Afficher les résultats
    afficher_resultats(timestamps, probabilites)


if __name__ == "__main__":
    main()