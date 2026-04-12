import numpy as np
import librosa
from scipy.spatial.distance import cosine
from scipy.signal import find_peaks, savgol_filter
import matplotlib.pyplot as plt
from pathlib import Path
import soundfile as sf
from dataclasses import dataclass
from typing import List, Tuple, Optional
import warnings

warnings.filterwarnings('ignore')


@dataclass
class Advertisement:
    start_time: float
    end_time: float
    confidence: float
    peak_magnitude: float


class SimpleMFCCDetector:
    def __init__(self,
                 n_mfcc=13,
                 hop_length=512,
                 frame_length=2048,
                 smooth_window=5,
                 min_ad_duration=10,
                 max_ad_duration=45,
                 transition_threshold=0.5,
                 peak_distance=2.0):

        self.n_mfcc = n_mfcc
        self.hop_length = hop_length
        self.frame_length = frame_length
        self.smooth_window = smooth_window
        self.min_ad_duration = min_ad_duration
        self.max_ad_duration = max_ad_duration
        self.transition_threshold = transition_threshold
        self.peak_distance = peak_distance

    def extract_mfcc_sequence(self, audio: np.ndarray, sr: int) -> np.ndarray:
        """Extrait la séquence des MFCC"""
        mfccs = librosa.feature.mfcc(
            y=audio,
            sr=sr,
            n_mfcc=self.n_mfcc,
            hop_length=self.hop_length,
            n_fft=self.frame_length
        )
        return mfccs.T

    def compute_transition_scores(self, mfcc_sequence: np.ndarray) -> np.ndarray:
        """Calcule les scores de transition"""
        n_frames = len(mfcc_sequence)
        transitions = np.zeros(n_frames - 1)

        for i in range(n_frames - 1):
            # Distance cosinus simplifiée
            vec1 = mfcc_sequence[i]
            vec2 = mfcc_sequence[i + 1]
            dot_product = np.dot(vec1, vec2)
            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)

            if norm1 > 0 and norm2 > 0:
                similarity = dot_product / (norm1 * norm2)
                transitions[i] = 1 - similarity  # Distance = 1 - similarité
            else:
                transitions[i] = 1.0

        return transitions

    def smooth_scores(self, scores: np.ndarray) -> np.ndarray:
        """Lisse les scores avec moyenne mobile"""
        if len(scores) < self.smooth_window:
            return scores

        smoothed = np.convolve(scores, np.ones(self.smooth_window) / self.smooth_window, mode='same')

        # Remplacer les bords
        half = self.smooth_window // 2
        smoothed[:half] = scores[:half]
        smoothed[-half:] = scores[-half:]

        return smoothed

    def normalize_scores(self, scores: np.ndarray) -> np.ndarray:
        """Normalise entre 0 et 1"""
        min_val = np.min(scores)
        max_val = np.max(scores)

        if max_val - min_val < 1e-6:
            return np.zeros_like(scores)

        return (scores - min_val) / (max_val - min_val)

    def detect_transition_peaks(self, scores: np.ndarray, sr: int) -> Tuple[np.ndarray, np.ndarray]:
        """Détecte les pics de transition"""
        # Distance minimale entre pics en frames
        distance_frames = max(1, int(self.peak_distance * sr / self.hop_length))

        # Trouver les pics
        peaks, properties = find_peaks(
            scores,
            height=self.transition_threshold,
            distance=distance_frames,
            prominence=0.1
        )

        peak_heights = properties['peak_heights'] if peaks.size > 0 else np.array([])

        return peaks, peak_heights

    def group_transitions_into_ads(self, peaks: np.ndarray, peak_heights: np.ndarray,
                                   sr: int) -> List[Advertisement]:
        """Regroupe les pics en publicités"""
        if len(peaks) < 2:
            return []

        ads = []
        used_peaks = set()

        # Convertir en temps
        peak_times = peaks * self.hop_length / sr

        # Trier par hauteur (confiance)
        sorted_indices = np.argsort(peak_heights)[::-1]

        for idx in sorted_indices:
            if idx in used_peaks:
                continue

            peak_time = peak_times[idx]
            best_end_idx = None
            best_end_time = None

            # Chercher la fin
            for j in range(idx + 1, len(peak_times)):
                if j in used_peaks:
                    continue

                duration = peak_times[j] - peak_time

                if self.min_ad_duration <= duration <= self.max_ad_duration:
                    best_end_idx = j
                    best_end_time = peak_times[j]
                    break
                elif duration > self.max_ad_duration:
                    break

            if best_end_idx is not None:
                confidence = (peak_heights[idx] + peak_heights[best_end_idx]) / 2

                ads.append(Advertisement(
                    start_time=peak_time,
                    end_time=best_end_time,
                    confidence=confidence,
                    peak_magnitude=peak_heights[idx]
                ))

                used_peaks.add(idx)
                used_peaks.add(best_end_idx)

        return sorted(ads, key=lambda x: x.start_time)

    def merge_overlapping_ads(self, ads: List[Advertisement]) -> List[Advertisement]:
        """Fusionne les publicités qui se chevauchent"""
        if not ads:
            return ads

        merged = []
        current = ads[0]

        for next_ad in ads[1:]:
            if next_ad.start_time - current.end_time < 2.0:
                current.end_time = max(current.end_time, next_ad.end_time)
                current.confidence = max(current.confidence, next_ad.confidence)
            else:
                merged.append(current)
                current = next_ad

        merged.append(current)
        return merged

    def detect(self, audio_path: str, sr: Optional[int] = None) -> Tuple[List[Advertisement], dict]:
        """Détecte les publicités"""
        print(f"Chargement du fichier: {audio_path}")

        try:
            audio, sr = librosa.load(audio_path, sr=sr)
        except Exception as e:
            print(f"Erreur de chargement: {e}")
            print("Essayez de convertir le fichier en WAV d'abord")
            return [], {}

        duration = len(audio) / sr
        print(f"Durée totale: {duration:.2f} secondes")

        # Extraire MFCC
        print("Extraction des MFCC...")
        mfcc_seq = self.extract_mfcc_sequence(audio, sr)

        # Calculer transitions
        print("Calcul des transitions...")
        transition_scores = self.compute_transition_scores(mfcc_seq)

        # Lisser et normaliser
        smoothed_scores = self.smooth_scores(transition_scores)
        normalized_scores = self.normalize_scores(smoothed_scores)

        # Détecter pics
        print("Détection des changements...")
        peaks, peak_heights = self.detect_transition_peaks(normalized_scores, sr)
        print(f"  {len(peaks)} pics détectés")

        # Grouper en publicités
        print("Regroupement...")
        ads = self.group_transitions_into_ads(peaks, peak_heights, sr)
        ads = self.merge_overlapping_ads(ads)
        print(f"  {len(ads)} publicités identifiées")

        stats = {
            'total_duration': duration,
            'n_peaks': len(peaks),
            'n_ads': len(ads),
            'peak_times': peaks * self.hop_length / sr if len(peaks) > 0 else np.array([]),
            'peak_heights': peak_heights,
            'transition_scores': normalized_scores,
            'times': np.arange(len(normalized_scores)) * self.hop_length / sr
        }

        return ads, stats

    def export_ads(self, audio_path: str, ads: List[Advertisement], output_dir: str = "ads_output"):
        """Exporte les publicités"""
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)

        audio, sr = librosa.load(audio_path, sr=None)

        for i, ad in enumerate(ads, 1):
            start_sample = int(ad.start_time * sr)
            end_sample = int(ad.end_time * sr)
            ad_audio = audio[start_sample:end_sample]

            output_file = output_path / f"ad_{i:03d}_{ad.start_time:.1f}s-{ad.end_time:.1f}s.wav"
            sf.write(str(output_file), ad_audio, sr)
            print(f"  Exporté: {output_file}")

        return output_path

    def plot_detection_results(self, ads: List[Advertisement], stats: dict, save_path: str = "detection_plot.png"):
        """Visualise les résultats"""
        if len(stats['times']) == 0:
            print("Aucune donnée à visualiser")
            return

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15, 10))

        # Graphique 1
        times = stats['times'][:len(stats['transition_scores'])]
        scores = stats['transition_scores']

        ax1.plot(times, scores, 'b-', linewidth=1, label='Score de transition')

        if len(stats['peak_times']) > 0:
            ax1.scatter(stats['peak_times'], stats['peak_heights'],
                        color='red', s=50, zorder=5, label='Pics')

        for ad in ads:
            ax1.axvspan(ad.start_time, ad.end_time, alpha=0.3, color='green')

        ax1.axhline(y=self.transition_threshold, color='orange', linestyle='--')
        ax1.set_xlabel('Temps (secondes)')
        ax1.set_ylabel('Score de transition')
        ax1.set_title('Détection des changements brutaux (MFCC)')
        ax1.legend()
        ax1.grid(True, alpha=0.3)

        # Graphique 2
        if ads:
            durations = [ad.end_time - ad.start_time for ad in ads]
            confidences = [ad.confidence for ad in ads]

            y_positions = np.arange(len(ads))
            bars = ax2.barh(y_positions, durations, left=[ad.start_time for ad in ads],
                            alpha=0.7, color=plt.cm.RdYlGn(np.array(confidences)))

            ax2.set_xlabel('Temps (secondes)')
            ax2.set_ylabel('Publicité #')
            ax2.set_title(f'Timeline des publicités ({len(ads)} segments)')
            ax2.set_yticks(y_positions)
            ax2.set_yticklabels([f'Pub {i + 1}' for i in range(len(ads))])
            ax2.grid(True, alpha=0.3, axis='x')

        plt.tight_layout()
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        plt.show()
        print(f"Graphique sauvegardé: {save_path}")

    def generate_report(self, ads: List[Advertisement], stats: dict, output_file: str = "ads_report.txt"):
        """Génère un rapport"""
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("=" * 70 + "\n")
            f.write("RAPPORT DE DÉTECTION DE PUBLICITÉS\n")
            f.write("=" * 70 + "\n\n")

            f.write(f"Durée totale: {stats['total_duration']:.2f} secondes\n")
            f.write(f"Publicités détectées: {stats['n_ads']}\n\n")

            if ads:
                total_duration = sum(ad.end_time - ad.start_time for ad in ads)
                f.write(f"Durée totale des pubs: {total_duration:.2f} secondes\n")
                f.write(f"Pourcentage: {(total_duration / stats['total_duration']) * 100:.1f}%\n\n")

                f.write("DÉTAIL\n")
                f.write("-" * 70 + "\n")
                for i, ad in enumerate(ads, 1):
                    duration = ad.end_time - ad.start_time
                    f.write(f"\nPub #{i}: {ad.start_time:.1f}s - {ad.end_time:.1f}s (durée: {duration:.1f}s)\n")
                    f.write(f"  Confiance: {ad.confidence:.2%}\n")

        print(f"Rapport généré: {output_file}")


def auto_tune_detector(audio_path: str) -> SimpleMFCCDetector:
    """Calibration automatique"""
    print("🔧 CALIBRATION AUTOMATIQUE\n")

    audio, sr = librosa.load(audio_path, sr=None)
    duration = len(audio) / sr

    if duration < 300:
        min_ad_duration = 10
        max_ad_duration = 35
    else:
        min_ad_duration = 15
        max_ad_duration = 45

    print(f"Paramètres suggérés:")
    print(f"  - Durée des pubs: {min_ad_duration}-{max_ad_duration} secondes")
    print(f"  - Seuil de transition: 0.5 (ajustable)")

    return SimpleMFCCDetector(
        min_ad_duration=min_ad_duration,
        max_ad_duration=max_ad_duration,
        transition_threshold=0.5,
        peak_distance=2.0
    )


if __name__ == "__main__":
    # Ton fichier audio
    AUDIO_FILE = "../@assets/extrait_avec_pub.m4a"  # Remplace par ton fichier

    # Vérifier si le fichier existe
    from pathlib import Path

    if not Path(AUDIO_FILE).exists():
        print(f"❌ Fichier non trouvé: {AUDIO_FILE}")
        print("Veuillez vérifier le chemin du fichier")
        exit(1)

    # Calibration
    detector = auto_tune_detector(AUDIO_FILE)

    # Détection
    ads, stats = detector.detect(AUDIO_FILE)

    if ads:
        print("\n💾 Export des publicités...")
        detector.export_ads(AUDIO_FILE, ads, "publicités_mfcc")

        # Visualisation
        detector.plot_detection_results(ads, stats, "detection_mfcc.png")

        # Rapport
        detector.generate_report(ads, stats, "rapport_publicites.txt")

        # Résumé
        print("\n" + "=" * 50)
        print("RÉSUMÉ")
        print("=" * 50)
        print(f"✅ {len(ads)} publicités détectées")

        print("\nTimeline:")
        for i, ad in enumerate(ads, 1):
            print(f"  Pub {i:2d}: {ad.start_time:6.1f}s - {ad.end_time:6.1f}s "
                  f"(durée: {ad.end_time - ad.start_time:.1f}s)")
    else:
        print("❌ Aucune publicité détectée")
        print("Essayez d'ajuster le paramètre 'transition_threshold' à une valeur plus basse (ex: 0.3)")