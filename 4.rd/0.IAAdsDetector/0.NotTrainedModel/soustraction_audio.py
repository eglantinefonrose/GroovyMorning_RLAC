import numpy as np
import soundfile as sf
from pathlib import Path
from scipy.signal import correlate, find_peaks
import sys
import subprocess
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import multiprocessing as mp
from functools import partial
import warnings

warnings.filterwarnings('ignore')


def load_audio_fast(file_path, target_sr=16000, normalize=True):
    """
    Chargement ultra-rapide avec ffmpeg.
    """
    file_path = str(file_path)

    cmd = [
        'ffmpeg', '-i', file_path,
        '-f', 'f32le',
        '-acodec', 'pcm_f32le',
        '-ar', str(target_sr),
        '-ac', '1',
        '-loglevel', 'error',
        '-'
    ]

    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    chunks = []
    while True:
        chunk = process.stdout.read(1024 * 1024 * 4)
        if not chunk:
            break
        chunks.append(chunk)

    process.wait()

    if process.returncode != 0:
        stderr = process.stderr.read().decode()
        raise Exception(f"FFmpeg error: {stderr[:200]}")

    audio = np.frombuffer(b''.join(chunks), dtype=np.float32)

    if normalize and np.max(np.abs(audio)) > 0:
        audio = audio / (np.max(np.abs(audio)) + 1e-8)

    return audio, target_sr


def find_audio_positions_fast(long_audio, short_audio, threshold=0.6):
    """
    Détection rapide avec FFT.
    """
    short_len = len(short_audio)
    long_len = len(long_audio)

    if short_len > long_len:
        return []

    # Corrélation FFT
    correlation = correlate(long_audio, short_audio, mode='valid', method='fft')
    correlation = correlation / (np.max(np.abs(correlation)) + 1e-8)

    # Trouver les pics
    min_distance = int(short_len * 0.5)
    peaks, properties = find_peaks(
        correlation,
        height=threshold,
        distance=min_distance,
        prominence=0.1
    )

    return peaks.tolist()


def find_audio_positions_multiresolution(long_audio, short_audio, threshold=0.6):
    """
    Détection multi-résolution pour très longs fichiers.
    """
    short_len = len(short_audio)
    long_len = len(long_audio)

    if long_len > 2_000_000:  # Plus de 2 millions d'échantillons
        # Niveau 1: sous-échantillonnage
        down_factor = 8
        long_down = long_audio[::down_factor]
        short_down = short_audio[::down_factor]

        # Détection rapide
        correlation_fast = correlate(long_down, short_down, mode='valid', method='fft')
        correlation_fast = correlation_fast / (np.max(np.abs(correlation_fast)) + 1e-8)

        candidates = find_peaks(correlation_fast, height=threshold - 0.1, distance=len(short_down) // 2)[0]

        if len(candidates) == 0:
            return []

        # Niveau 2: affinage local
        refined_peaks = []
        window_size = len(short_audio) * 2

        for candidate in candidates:
            approx_pos = candidate * down_factor
            start = max(0, approx_pos - window_size)
            end = min(long_len, approx_pos + window_size)

            if end - start > len(short_audio):
                local_block = long_audio[start:end]
                local_corr = correlate(local_block, short_audio, mode='valid', method='fft')
                local_corr = local_corr / (np.max(np.abs(local_corr)) + 1e-8)

                local_peaks = find_peaks(local_corr, height=threshold, distance=len(short_audio) // 2)[0]

                for local_peak in local_peaks:
                    refined_peaks.append(start + local_peak)

        return refined_peaks
    else:
        return find_audio_positions_fast(long_audio, short_audio, threshold)


def search_single_audio(short_path, long_audio, sr, threshold):
    """
    Fonction wrapper pour la recherche d'un seul audio (utilisable par multiprocessing).
    """
    try:
        short_audio, _ = load_audio_fast(short_path, target_sr=sr)
        positions = find_audio_positions_multiresolution(long_audio, short_audio, threshold)
        return short_path, positions, len(short_audio)
    except Exception as e:
        return short_path, [], 0


def find_all_audios_parallel(long_audio, short_audios, sr, threshold=0.6, n_workers=None):
    """
    Recherche parallèle de tous les petits audios.
    """
    if n_workers is None:
        n_workers = min(mp.cpu_count(), 4)  # Limiter à 4 pour éviter trop de mémoire

    print(f"   🚀 Utilisation de {n_workers} processeurs en parallèle")

    # Créer une fonction partielle avec les paramètres fixes
    search_func = partial(search_single_audio, long_audio=long_audio, sr=sr, threshold=threshold)

    all_positions = []
    short_durations = []
    found_count = 0

    # Utiliser ThreadPoolExecutor au lieu de ProcessPoolExecutor (évite pickle)
    with ThreadPoolExecutor(max_workers=n_workers) as executor:
        results = list(executor.map(search_func, short_audios))

    for short_path, positions, duration in results:
        name = Path(short_path).name
        if positions:
            print(f"   ✓ {name}: {len(positions)} position(s)")
            for pos in positions:
                all_positions.append(pos)
            found_count += 1
            short_durations.append(duration)
        else:
            print(f"   ✗ {name}: non trouvé")

    print(f"   📊 Trouvés: {found_count}/{len(short_audios)}")

    return all_positions, short_durations


def extract_complement_segments_optimized(long_audio, positions, short_duration_samples, margin_samples=500):
    """
    Extraction optimisée des segments complémentaires.
    """
    if not positions:
        return [(0, len(long_audio))]

    positions = np.array(sorted(positions))
    ends = positions + short_duration_samples

    # Fusionner les segments chevauchants
    merged_starts = []
    merged_ends = []

    current_start = positions[0]
    current_end = ends[0]

    for i in range(1, len(positions)):
        if positions[i] - current_end <= margin_samples * 2:
            current_end = max(current_end, ends[i])
        else:
            merged_starts.append(current_start)
            merged_ends.append(current_end)
            current_start = positions[i]
            current_end = ends[i]

    merged_starts.append(current_start)
    merged_ends.append(current_end)

    # Extraire les compléments
    segments = []
    current_pos = 0

    for start, end in zip(merged_starts, merged_ends):
        start_margin = max(0, start - margin_samples)
        end_margin = min(len(long_audio), end + margin_samples)

        if current_pos < start_margin:
            segments.append((current_pos, start_margin))

        current_pos = end_margin

    if current_pos < len(long_audio):
        segments.append((current_pos, len(long_audio)))

    return segments


def save_audio_segments(audio, segments, output_dir, original_filename, sr):
    """Sauvegarde chaque segment."""
    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True, parents=True)

    saved_files = []
    for i, (start, end) in enumerate(segments):
        segment = audio[start:end]
        min_duration = sr * 0.5
        if len(segment) >= min_duration:
            output_file = output_dir / f"{original_filename}_complement_{i + 1}.wav"
            sf.write(output_file, segment.astype(np.float32), sr)
            saved_files.append(str(output_file))
            print(f"  → {output_file.name} ({len(segment) / sr:.1f}s)")

    return saved_files


def process_audio_subtraction_fast(long_audio_path, short_audios_paths, output_dir="output", threshold=0.55,
                                   n_workers=None):
    """
    Version ultra-rapide du traitement.
    """
    print(f"\n🔍 Chargement du long audio...")
    print(f"   📁 {Path(long_audio_path).name}")

    try:
        # Réduire la fréquence pour économiser la mémoire
        long_audio, sr = load_audio_fast(long_audio_path, target_sr=16000)
        duration = len(long_audio) / sr
        memory_mb = len(long_audio) * 4 / 1024 / 1024
        print(f"   ✅ {duration:.1f}s ({duration / 60:.1f} min) - {sr}Hz")
        print(f"   💾 {memory_mb:.1f} MB en mémoire")
    except Exception as e:
        print(f"   ❌ Erreur: {e}")
        return []

    print(f"\n🔎 Recherche des {len(short_audios_paths)} extraits...")
    all_positions, short_durations = find_all_audios_parallel(
        long_audio, short_audios_paths, sr, threshold, n_workers
    )

    if not all_positions:
        print("\n⚠️  Aucun extrait trouvé !")
        print("   Conseils: baisse le seuil (0.4-0.5) ou vérifie les fichiers")
        return []

    short_duration_samples = max(short_durations) if short_durations else 0

    print(f"\n✂️  Extraction des compléments...")
    complement_segments = extract_complement_segments_optimized(
        long_audio, all_positions, short_duration_samples, margin_samples=500
    )

    print(f"\n💾 Sauvegarde...")
    original_name = Path(long_audio_path).stem
    saved_files = save_audio_segments(
        long_audio, complement_segments, output_dir, original_name, sr
    )

    total_complement = sum((end - start) / sr for start, end in complement_segments)
    total_original = len(long_audio) / sr

    print(f"\n✅ Terminé!")
    print(f"   🎯 {len(all_positions)} extrait(s) trouvé(s)")
    print(f"   📁 {len(saved_files)} fichiers dans '{output_dir}'")
    print(f"   ⏱️  {total_complement:.1f}s conservés ({total_complement / total_original * 100:.1f}%)")

    return saved_files


# Exécution
if __name__ == "__main__":
    import time
    import os

    # Chemins (à ajuster)
    LONG_AUDIO = "home/raws/10241-01-12-2025-ITEMA_24328152-2025F10761S0335-NET_MFI_9428D60B-C293-49F7-9A16-1289E7C0CC0D-22-525c32bf42fbeb1c5500fbe2a353095f.mp3"

    SHORT_AUDIOS_DIR = "home/raws/01-12-2025"
    SHORT_AUDIOS = [
        f"{SHORT_AUDIOS_DIR}/{name}" for name in [
            "7h30.mp3", "7h50.mp3", "80_secondes.mp3", "bertrand_chameroy.mp3",
            "charline.mp3", "daphne_burki.mp3", "debat.mp3", "edito_eco.mp3",
            "edito_politique.mp3", "geopo.mp3", "grand_portrait.mp3",
            "grand_reportage.mp3", "invite_8h20.mp3", "journal_7h.mp3",
            "journal_8h.mp3", "journal_9h.mp3", "mag_vie_culturelle.mp3",
            "mag_vie_quotidienne.mp3", "meteo.mp3", "monde_nouveau.mp3",
            "musicaline.mp3", "nora_hamadi.mp3", "sophia_aram.mp3"
        ]
    ]

    OUTPUT_DIR = "resultat_complements"
    THRESHOLD = 0.55
    N_WORKERS = 2  # Réduire à 2 pour économiser la mémoire

    # Vérification
    if not Path(LONG_AUDIO).exists():
        print(f"❌ Fichier long introuvable: {LONG_AUDIO}")
        print(f"   Répertoire courant: {os.getcwd()}")
        sys.exit(1)

    # Vérifier l'espace disque
    import shutil

    free_gb = shutil.disk_usage("/").free / (1024 ** 3)
    print(f"💾 Espace disque disponible: {free_gb:.1f} GB")

    if free_gb < 2:
        print("⚠️  Espace disque faible! Libère au moins 2-3 Go")
        response = input("   Continuer? (o/N): ")
        if response.lower() != 'o':
            sys.exit(1)

    print(f"\n🚀 Démarrage du traitement")
    print(f"🎯 {len(SHORT_AUDIOS)} extraits à chercher")
    print(f"⚙️  Seuil: {THRESHOLD}")

    start_time = time.time()
    result = process_audio_subtraction_fast(
        LONG_AUDIO, SHORT_AUDIOS, OUTPUT_DIR, THRESHOLD, N_WORKERS
    )
    elapsed = time.time() - start_time

    if result:
        print(f"\n⏱️  Temps total: {elapsed:.1f} secondes")
        print(f"\n📁 Résultats dans: {OUTPUT_DIR}")
    else:
        print(f"\n❌ Échec du traitement")