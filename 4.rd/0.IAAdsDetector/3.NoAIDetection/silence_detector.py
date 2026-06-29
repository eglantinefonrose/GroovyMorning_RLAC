import os
from pydub import AudioSegment
from pydub.silence import split_on_silence
import numpy as np
import wave
import struct


def detect_advertisements(input_file, output_dir="ads_output",
                          min_ad_duration=15000,  # 15 secondes en ms
                          max_ad_duration=60000,  # 60 secondes en ms
                          silence_thresh=-40,  # Seuil de silence en dBFS
                          min_silence_len=500,  # Silence minimum pour couper (ms)
                          energy_threshold=0.5):  # Seuil d'énergie relative
    """
    Détecte les publicités dans un fichier audio

    Args:
        input_file: chemin du fichier audio (mp3, wav, etc.)
        output_dir: dossier pour exporter les segments détectés
        min_ad_duration: durée minimale d'une pub (ms)
        max_ad_duration: durée maximale d'une pub (ms)
        silence_thresh: seuil de silence (dBFS, plus négatif = plus strict)
        min_silence_len: longueur minimale de silence pour couper
        energy_threshold: seuil d'énergie normalisé (0-1)
    """

    print(f"Chargement du fichier: {input_file}")
    audio = AudioSegment.from_file(input_file)

    print(f"Durée totale: {len(audio) / 1000:.2f} secondes")

    # Créer le dossier de sortie
    os.makedirs(output_dir, exist_ok=True)

    # Étape 1: Découper par silence
    print("Découpage par silence...")
    chunks = split_on_silence(
        audio,
        min_silence_len=min_silence_len,
        silence_thresh=silence_thresh,
        keep_silence=500  # Garder 500ms de silence autour
    )

    print(f"Nombre de segments découpés: {len(chunks)}")

    # Calculer l'énergie moyenne de l'audio entier (référence)
    audio_array = np.array(audio.get_array_of_samples())
    audio_energy = np.mean(np.abs(audio_array))

    advertisements = []

    # Étape 2: Filtrer par durée et énergie
    for i, chunk in enumerate(chunks):
        duration = len(chunk)

        # Vérifier la durée
        if min_ad_duration <= duration <= max_ad_duration:
            # Calculer l'énergie du segment
            chunk_array = np.array(chunk.get_array_of_samples())
            chunk_energy = np.mean(np.abs(chunk_array))

            # Normaliser l'énergie par rapport à l'audio complet
            normalized_energy = chunk_energy / audio_energy

            # Vérifier si l'énergie est élevée (pub potentielle)
            if normalized_energy > energy_threshold:
                advertisements.append({
                    'index': i,
                    'duration': duration,
                    'energy': normalized_energy,
                    'start_time': get_start_time(chunks, i, min_silence_len),
                    'segment': chunk
                })

                print(f"  ✓ Pub potentielle #{len(advertisements)}: "
                      f"durée={duration / 1000:.1f}s, "
                      f"énergie={normalized_energy:.2f}")

                # Exporter le segment
                output_file = os.path.join(output_dir, f"ad_{len(advertisements):03d}.wav")
                chunk.export(output_file, format="wav")
                print(f"    Exporté: {output_file}")

    # Afficher le résumé
    print("\n" + "=" * 50)
    print(f"RÉSUMÉ DE LA DÉTECTION")
    print("=" * 50)
    print(f"Nombre total de publicités détectées: {len(advertisements)}")

    if advertisements:
        print(f"Durée totale des pubs: {sum(ad['duration'] for ad in advertisements) / 1000:.1f} secondes")
        print(f"Durée moyenne par pub: {np.mean([ad['duration'] for ad in advertisements]) / 1000:.1f} secondes")

        # Afficher la timeline
        print("\nTimeline des publicités:")
        for i, ad in enumerate(advertisements, 1):
            start_sec = ad['start_time'] / 1000
            end_sec = (ad['start_time'] + ad['duration']) / 1000
            print(f"  Pub {i:2d}: {start_sec:6.1f}s - {end_sec:6.1f}s "
                  f"(durée: {ad['duration'] / 1000:.1f}s)")

    return advertisements


def get_start_time(chunks, index, min_silence_len):
    """Calcule le temps de début d'un segment"""
    start_time = 0
    for i in range(index):
        # Ajouter la durée du segment précédent + le silence
        start_time += len(chunks[i]) + min_silence_len
    return start_time


def analyze_energy_distribution(input_file):
    """Analyse la distribution d'énergie pour aider à choisir le seuil"""
    from pydub import AudioSegment
    import numpy as np

    audio = AudioSegment.from_file(input_file)
    audio_array = np.array(audio.get_array_of_samples())
    audio_energy = np.mean(np.abs(audio_array))

    # Découpage par silence
    chunks = split_on_silence(audio, min_silence_len=500, silence_thresh=-40)

    energies = []
    durations = []

    for chunk in chunks:
        chunk_array = np.array(chunk.get_array_of_samples())
        chunk_energy = np.mean(np.abs(chunk_array))
        normalized_energy = chunk_energy / audio_energy
        energies.append(normalized_energy)
        durations.append(len(chunk))

    print("\nAnalyse de l'énergie des segments:")
    print(f"  Énergie moyenne: {np.mean(energies):.2f}")
    print(f"  Énergie médiane: {np.median(energies):.2f}")
    print(f"  Énergie max: {np.max(energies):.2f}")
    print(f"  Énergie min: {np.min(energies):.2f}")
    print(f"  Écart-type: {np.std(energies):.2f}")

    # Suggestion de seuil
    suggested_threshold = np.percentile(energies, 70)
    print(f"\n  💡 Seuil d'énergie suggéré: {suggested_threshold:.2f}")
    print(f"     (segments avec énergie > {suggested_threshold:.2f} sont plus énergétiques que 70% des segments)")

    return energies, durations


def create_timeline_report(advertisements, output_file="timeline_report.txt"):
    """Crée un rapport textuel de la timeline"""
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("TIMELINE DES PUBLICITÉS DÉTECTÉES\n")
        f.write("=" * 40 + "\n\n")

        for i, ad in enumerate(advertisements, 1):
            start_sec = ad['start_time'] / 1000
            end_sec = (ad['start_time'] + ad['duration']) / 1000
            minutes = int(start_sec // 60)
            seconds = int(start_sec % 60)

            f.write(f"Publicité #{i:2d}\n")
            f.write(f"  Début: {minutes:2d}:{seconds:02d} ({start_sec:.1f}s)\n")
            f.write(f"  Fin:   {end_sec:.1f}s\n")
            f.write(f"  Durée: {ad['duration'] / 1000:.1f}s\n")
            f.write(f"  Énergie relative: {ad['energy']:.2f}\n")
            f.write("-" * 40 + "\n")

    print(f"\n📄 Rapport de timeline sauvegardé: {output_file}")


# Exemple d'utilisation
if __name__ == "__main__":
    # Paramètres à ajuster selon ton fichier
    INPUT_FILE = "../@assets/extrait_avec_pub.m4a"  # Remplace par ton fichier
    OUTPUT_DIR = "publicites_detectees"

    # Option 1: Analyser d'abord la distribution d'énergie
    print("🔍 ANALYSE PRÉLIMINAIRE")
    print("-" * 40)
    energies, durations = analyze_energy_distribution(INPUT_FILE)

    # Option 2: Lancer la détection avec les paramètres ajustés
    print("\n\n🎯 DÉTECTION DES PUBLICITÉS")
    print("-" * 40)

    # Ajuste ces paramètres selon les résultats de l'analyse
    ads = detect_advertisements(
        input_file=INPUT_FILE,
        output_dir=OUTPUT_DIR,
        min_ad_duration=15000,  # 15 secondes minimum
        max_ad_duration=60000,  # 60 secondes maximum
        silence_thresh=-40,  # Ajuste (-35 à -50 selon le bruit de fond)
        min_silence_len=500,  # 0.5 seconde de silence minimum
        energy_threshold=1.2  # Seuil d'énergie (ajuste selon analyse)
    )

    # Option 3: Créer un rapport
    if ads:
        create_timeline_report(ads, "timeline_publicites.txt")

        # Option 4: Générer un fichier audio avec seulement les pubs (optionnel)
        print("\n🔊 Génération d'un fichier avec uniquement les publicités...")
        all_ads = AudioSegment.empty()
        for ad in ads:
            all_ads += ad['segment'] + AudioSegment.silent(duration=1000)  # 1s de silence entre pubs

        all_ads.export(os.path.join(OUTPUT_DIR, "toutes_les_pubs.wav"), format="wav")
        print(f"  ✅ Fichier créé: {OUTPUT_DIR}/toutes_les_pubs.wav")
