import numpy as np
import librosa
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.svm import SVC
from sklearn.neural_network import MLPClassifier
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import classification_report, confusion_matrix, roc_curve, auc
from sklearn.preprocessing import StandardScaler
import joblib
from pathlib import Path
import matplotlib.pyplot as plt
import seaborn as sns
from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Optional, Union
import warnings
import json
from tqdm import tqdm
import soundfile as sf
import random
from collections import defaultdict
import os
from datetime import datetime

warnings.filterwarnings('ignore')


@dataclass
class TrainingConfig:
    """Configuration pour l'entraînement"""
    segment_duration: float = 3.0  # Durée des segments en secondes
    non_ad_ratio: float = 2.0  # Ratio non-pubs / pubs (2x plus de non-pubs)
    min_segment_energy: float = 0.01  # Énergie minimale pour ignorer le silence
    augment_data: bool = True  # Augmentation des données
    non_ad_min_gap: float = 5.0  # Distance minimale des zones de pub pour les non-pubs
    use_all_files_for_non_ads: bool = True  # Utiliser tous les fichiers pour les non-pubs


@dataclass
class TrainingFile:
    """Représente un fichier d'entraînement avec ses timecodes"""
    audio_path: str
    timecodes_path: str
    name: str = ""

    def __post_init__(self):
        if not self.name:
            self.name = Path(self.audio_path).stem


class TimecodeLoader:
    """Charge les timecodes depuis différents formats de fichiers"""

    @staticmethod
    def load_timecodes(file_path: str) -> List[Tuple[float, float]]:
        """
        Charge les timecodes depuis un fichier.

        Formats supportés:
        - CSV: start,end ou start,duration
        - TXT: "MM:SS - MM:SS" ou "MM:SS.mmm - MM:SS.mmm"
        - JSON: [{"start": 0, "end": 10}, ...]
        """
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"Fichier non trouvé: {file_path}")

        # JSON
        if file_path.suffix == '.json':
            with open(file_path, 'r') as f:
                data = json.load(f)
                if isinstance(data, list):
                    return [(item['start'], item['end']) for item in data]
                elif isinstance(data, dict) and 'ads' in data:
                    return [(ad['start'], ad['end']) for ad in data['ads']]

        # CSV
        elif file_path.suffix == '.csv':
            df = pd.read_csv(file_path)
            if 'start' in df.columns and 'end' in df.columns:
                return [(row['start'], row['end']) for _, row in df.iterrows()]
            elif 'start' in df.columns and 'duration' in df.columns:
                return [(row['start'], row['start'] + row['duration']) for _, row in df.iterrows()]

        # TXT - Format texte
        else:
            timecodes = []
            with open(file_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue

                    # Format: "MM:SS - MM:SS" ou "MM:SS.mmm - MM:SS.mmm"
                    if '-' in line:
                        parts = line.split('-')
                        if len(parts) == 2:
                            start_str = parts[0].strip()
                            end_str = parts[1].strip()
                            start = TimecodeLoader._parse_time(start_str)
                            end = TimecodeLoader._parse_time(end_str)
                            if start is not None and end is not None:
                                timecodes.append((start, end))

                    # Format: "start,end" ou "start duration"
                    elif ',' in line:
                        parts = line.split(',')
                        if len(parts) == 2:
                            try:
                                start = float(parts[0].strip())
                                end = float(parts[1].strip())
                                timecodes.append((start, end))
                            except:
                                pass

            # Si on n'a rien trouvé, essayer le format "start end"
            if not timecodes:
                with open(file_path, 'r') as f:
                    for line in f:
                        parts = line.strip().split()
                        if len(parts) >= 2:
                            try:
                                start = float(parts[0])
                                end = float(parts[1])
                                timecodes.append((start, end))
                            except:
                                pass

        return timecodes

    @staticmethod
    def _parse_time(time_str: str) -> Optional[float]:
        """Convertit un format MM:SS.mmm ou HH:MM:SS en secondes"""
        try:
            if ':' in time_str:
                parts = time_str.split(':')
                if len(parts) == 2:
                    minutes = float(parts[0])
                    seconds = float(parts[1])
                    return minutes * 60 + seconds
                elif len(parts) == 3:
                    hours = float(parts[0])
                    minutes = float(parts[1])
                    seconds = float(parts[2])
                    return hours * 3600 + minutes * 60 + seconds
            else:
                return float(time_str)
        except:
            return None


class MultiAudioSegmenter:
    """Segmente plusieurs fichiers audio à partir de leurs timecodes"""

    def __init__(self, feature_extractor, config: TrainingConfig):
        self.feature_extractor = feature_extractor
        self.config = config

    def extract_ad_segments(self, audio: np.ndarray, sr: int,
                            timecodes: List[Tuple[float, float]],
                            source_name: str = "") -> List[Dict]:
        """
        Extrait les segments correspondant aux publicités (classe 1)
        """
        segments = []
        duration = len(audio) / sr

        for start, end in timecodes:
            start = max(0, start)
            end = min(duration, end)

            if end - start < self.config.segment_duration:
                continue

            segment_samples = int(self.config.segment_duration * sr)
            hop_samples = int(self.config.segment_duration * sr / 2)

            start_sample = int(start * sr)
            end_sample = int(end * sr)

            for seg_start in range(start_sample, end_sample - segment_samples + 1, hop_samples):
                seg_start_time = seg_start / sr
                seg_end_time = seg_start_time + self.config.segment_duration

                if seg_end_time <= end:
                    segment_audio = audio[seg_start:seg_start + segment_samples]
                    energy = np.mean(np.abs(segment_audio))

                    if energy > self.config.min_segment_energy:
                        segments.append({
                            'audio': segment_audio,
                            'start': seg_start_time,
                            'end': seg_end_time,
                            'label': 1,
                            'source': source_name,
                            'type': 'ad'
                        })

        return segments

    def extract_non_ad_segments(self, audio: np.ndarray, sr: int,
                                ad_timecodes: List[Tuple[float, float]],
                                n_segments: int,
                                source_name: str = "") -> List[Dict]:
        """
        Extrait des segments aléatoires hors des zones de publicités (classe 0)
        """
        duration = len(audio) / sr

        # Créer les zones interdites
        forbidden_zones = []
        for start, end in ad_timecodes:
            forbidden_zones.append((
                max(0, start - self.config.non_ad_min_gap),
                min(duration, end + self.config.non_ad_min_gap)
            ))

        # Fusionner les zones qui se chevauchent
        forbidden_zones.sort()
        merged_zones = []
        for zone in forbidden_zones:
            if not merged_zones or zone[0] > merged_zones[-1][1]:
                merged_zones.append(list(zone))
            else:
                merged_zones[-1][1] = max(merged_zones[-1][1], zone[1])

        # Calculer la durée disponible
        available_duration = duration
        for start, end in merged_zones:
            available_duration -= (end - start)

        if available_duration <= 0:
            return []

        max_segments = int(available_duration / self.config.segment_duration)
        n_segments = min(n_segments, max_segments)

        segments = []
        attempts = 0
        max_attempts = n_segments * 10

        segment_samples = int(self.config.segment_duration * sr)

        while len(segments) < n_segments and attempts < max_attempts:
            start_time = random.uniform(0, duration - self.config.segment_duration)
            end_time = start_time + self.config.segment_duration

            is_valid = True
            for start, end in merged_zones:
                if not (end_time <= start or start_time >= end):
                    is_valid = False
                    break

            if is_valid:
                start_sample = int(start_time * sr)
                segment_audio = audio[start_sample:start_sample + segment_samples]
                energy = np.mean(np.abs(segment_audio))

                if energy > self.config.min_segment_energy:
                    segments.append({
                        'audio': segment_audio,
                        'start': start_time,
                        'end': end_time,
                        'label': 0,
                        'source': source_name,
                        'type': 'non_ad'
                    })

            attempts += 1

        return segments


class FeatureExtractor:
    """Extracteur de caractéristiques audio"""

    def __init__(self,
                 sr=22050,
                 n_mfcc=13,
                 hop_length=512,
                 n_fft=2048,
                 n_bands=4):

        self.sr = sr
        self.n_mfcc = n_mfcc
        self.hop_length = hop_length
        self.n_fft = n_fft
        self.n_bands = n_bands

    def extract_features(self, audio: np.ndarray, segment_duration: float = 3.0) -> np.ndarray:
        """Extrait les caractéristiques d'un segment audio"""

        expected_length = int(segment_duration * self.sr)
        if len(audio) < expected_length:
            audio = np.pad(audio, (0, expected_length - len(audio)))
        else:
            audio = audio[:expected_length]

        features = []

        # 1. MFCC
        mfcc = librosa.feature.mfcc(y=audio, sr=self.sr, n_mfcc=self.n_mfcc,
                                    hop_length=self.hop_length, n_fft=self.n_fft)
        mfcc_mean = np.mean(mfcc, axis=1)
        mfcc_std = np.std(mfcc, axis=1)
        features.extend(mfcc_mean)
        features.extend(mfcc_std)

        # 2. Énergie par bande
        stft = np.abs(librosa.stft(audio, hop_length=self.hop_length, n_fft=self.n_fft))
        freqs = librosa.fft_frequencies(sr=self.sr, n_fft=self.n_fft)
        band_edges = np.linspace(0, len(freqs), self.n_bands + 1, dtype=int)

        for i in range(self.n_bands):
            band_energy = np.sum(stft[band_edges[i]:band_edges[i + 1]] ** 2)
            features.append(np.log1p(band_energy))

        # 3. Zero-crossing rate
        zcr = librosa.feature.zero_crossing_rate(audio, hop_length=self.hop_length)
        features.append(np.mean(zcr))
        features.append(np.std(zcr))

        # 4. RMS
        rms = librosa.feature.rms(y=audio, hop_length=self.hop_length)[0]
        features.append(np.mean(rms))
        features.append(np.std(rms))
        features.append(np.max(rms) - np.min(rms))

        # 5. Spectral features
        rolloff = librosa.feature.spectral_rolloff(y=audio, sr=self.sr, hop_length=self.hop_length)
        features.append(np.mean(rolloff))
        features.append(np.std(rolloff))

        centroid = librosa.feature.spectral_centroid(y=audio, sr=self.sr, hop_length=self.hop_length)
        features.append(np.mean(centroid))
        features.append(np.std(centroid))

        bandwidth = librosa.feature.spectral_bandwidth(y=audio, sr=self.sr, hop_length=self.hop_length)
        features.append(np.mean(bandwidth))
        features.append(np.std(bandwidth))

        # 6. Transition features
        if mfcc.shape[1] > 1:
            mfcc_diff = np.diff(mfcc, axis=1)
            features.append(np.mean(np.abs(mfcc_diff)))
            features.append(np.std(np.abs(mfcc_diff)))
        else:
            features.extend([0, 0])

        return np.array(features)

    def augment_audio(self, audio: np.ndarray) -> np.ndarray:
        """Augmentation des données"""

        augmentation_type = random.choice(['none', 'speed', 'noise', 'shift'])

        if augmentation_type == 'speed' and random.random() > 0.5:
            speed_factor = random.uniform(0.9, 1.1)
            audio = librosa.effects.time_stretch(audio, rate=speed_factor)
            if len(audio) < int(3 * self.sr):
                audio = np.pad(audio, (0, int(3 * self.sr) - len(audio)))
            else:
                audio = audio[:int(3 * self.sr)]

        elif augmentation_type == 'noise' and random.random() > 0.5:
            noise = np.random.normal(0, 0.005, len(audio))
            audio = audio + noise

        elif augmentation_type == 'shift' and random.random() > 0.5:
            shift = int(random.uniform(-0.1, 0.1) * self.sr)
            audio = np.roll(audio, shift)
            if shift > 0:
                audio[:shift] = 0
            else:
                audio[shift:] = 0

        return audio

    def get_feature_names(self) -> List[str]:
        """Retourne les noms des caractéristiques"""
        names = []
        for i in range(self.n_mfcc):
            names.append(f'mfcc_{i}_mean')
        for i in range(self.n_mfcc):
            names.append(f'mfcc_{i}_std')
        for i in range(self.n_bands):
            names.append(f'band_energy_{i}')
        names.extend(['zcr_mean', 'zcr_std', 'rms_mean', 'rms_std', 'rms_range'])
        names.extend(['rolloff_mean', 'rolloff_std', 'centroid_mean', 'centroid_std',
                      'bandwidth_mean', 'bandwidth_std', 'mfcc_transition_mean', 'mfcc_transition_std'])
        return names


class AdvertisementClassifier:
    """Classifieur pour détecter les publicités"""

    def __init__(self, model_type='random_forest'):
        self.model_type = model_type
        self.feature_extractor = FeatureExtractor()
        self.scaler = StandardScaler()
        self.model = self._create_model()
        self.feature_names = None
        self.training_stats = {}

    def _create_model(self):
        """Crée le modèle selon le type choisi"""
        if self.model_type == 'random_forest':
            return RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
                min_samples_split=5,
                min_samples_leaf=2,
                random_state=42,
                n_jobs=-1
            )
        elif self.model_type == 'svm':
            return SVC(
                kernel='rbf',
                C=1.0,
                gamma='auto',
                probability=True,
                random_state=42
            )
        elif self.model_type == 'mlp':
            return MLPClassifier(
                hidden_layer_sizes=(100, 50),
                activation='relu',
                max_iter=500,
                random_state=42,
                early_stopping=True
            )
        else:
            raise ValueError(f"Modèle inconnu: {self.model_type}")

    def train_from_multiple_files(self, training_files: List[TrainingFile],
                                  config: TrainingConfig = None) -> None:
        """
        Entraîne le modèle à partir de plusieurs fichiers audio et leurs timecodes

        Args:
            training_files: Liste d'objets TrainingFile
            config: Configuration d'entraînement
        """

        if config is None:
            config = TrainingConfig()

        print("\n" + "=" * 70)
        print("ENTRAÎNEMENT À PARTIR DE PLUSIEURS FICHIERS AUDIO")
        print("=" * 70)

        print(f"\n📁 {len(training_files)} fichier(s) à traiter")

        segmenter = MultiAudioSegmenter(self.feature_extractor, config)
        all_ad_segments = []
        all_non_ad_segments = []

        # Stocker les stats par fichier
        file_stats = []

        for tf in training_files:
            print(f"\n{'=' * 50}")
            print(f"📻 Traitement: {tf.name}")
            print(f"   Audio: {tf.audio_path}")
            print(f"   Timecodes: {tf.timecodes_path}")

            # Vérifier l'existence des fichiers
            if not Path(tf.audio_path).exists():
                print(f"   ❌ Fichier audio non trouvé: {tf.audio_path}")
                continue

            if not Path(tf.timecodes_path).exists():
                print(f"   ❌ Fichier timecodes non trouvé: {tf.timecodes_path}")
                continue

            # Charger les timecodes
            timecodes = TimecodeLoader.load_timecodes(tf.timecodes_path)
            print(f"   📋 {len(timecodes)} plages de publicités trouvées")

            if not timecodes:
                print(f"   ⚠️ Aucun timecode valide, fichier ignoré")
                continue

            # Afficher un aperçu des timecodes
            for i, (start, end) in enumerate(timecodes[:3], 1):
                print(f"      Pub {i}: {start:.1f}s - {end:.1f}s (durée: {end - start:.1f}s)")
            if len(timecodes) > 3:
                print(f"      ... et {len(timecodes) - 3} autres")

            # Charger l'audio
            audio, sr = librosa.load(tf.audio_path, sr=self.feature_extractor.sr)
            duration = len(audio) / sr
            print(f"   🎵 Durée: {duration:.2f}s ({duration / 60:.2f} min)")

            # Extraire les segments de publicités
            ad_segments = segmenter.extract_ad_segments(audio, sr, timecodes, tf.name)
            print(f"   ✅ Publicités: {len(ad_segments)} segments extraits")

            # Extraire les segments non-publicités
            target_non_ad = int(len(ad_segments) * config.non_ad_ratio)
            non_ad_segments = segmenter.extract_non_ad_segments(audio, sr, timecodes, target_non_ad, tf.name)
            print(f"   ✅ Non-publicités: {len(non_ad_segments)} segments extraits (objectif: {target_non_ad})")

            all_ad_segments.extend(ad_segments)
            all_non_ad_segments.extend(non_ad_segments)

            file_stats.append({
                'name': tf.name,
                'duration': duration,
                'n_timecodes': len(timecodes),
                'n_ad_segments': len(ad_segments),
                'n_non_ad_segments': len(non_ad_segments)
            })

        if not all_ad_segments:
            print("\n❌ Aucun segment de publicité extrait!")
            return

        print("\n" + "=" * 70)
        print("📊 RÉSUMÉ PAR FICHIER")
        print("=" * 70)

        for stat in file_stats:
            print(f"\n📻 {stat['name']}")
            print(f"   Durée: {stat['duration']:.1f}s")
            print(f"   Timecodes: {stat['n_timecodes']}")
            print(f"   Segments pubs: {stat['n_ad_segments']}")
            print(f"   Segments non-pubs: {stat['n_non_ad_segments']}")

        # Combiner et équilibrer
        print("\n" + "=" * 70)
        print("🔄 PRÉPARATION FINALE DES DONNÉES")
        print("=" * 70)

        all_segments = all_ad_segments + all_non_ad_segments
        random.shuffle(all_segments)

        print(f"\nTotal segments: {len(all_segments)}")
        print(f"  - Publicités: {len(all_ad_segments)}")
        print(f"  - Non-publicités: {len(all_non_ad_segments)}")

        # Extraction des caractéristiques
        print("\n🔄 Extraction des caractéristiques...")
        features = []
        labels = []
        sources = []

        for segment in tqdm(all_segments):
            audio_seg = segment['audio']

            # Version originale
            feat = self.feature_extractor.extract_features(audio_seg, config.segment_duration)
            features.append(feat)
            labels.append(segment['label'])
            sources.append(segment['source'])

            # Augmentation pour les publicités
            if config.augment_data and segment['label'] == 1 and random.random() > 0.5:
                augmented_audio = self.feature_extractor.augment_audio(audio_seg)
                feat_aug = self.feature_extractor.extract_features(augmented_audio, config.segment_duration)
                features.append(feat_aug)
                labels.append(segment['label'])
                sources.append(segment['source'] + "_augmented")

        X = np.array(features)
        y = np.array(labels)

        print(f"\n✅ Caractéristiques extraites:")
        print(f"   - Total: {X.shape[0]} segments")
        print(f"   - Dimensions: {X.shape[1]}")
        print(f"   - Publicités: {np.sum(y == 1)}")
        print(f"   - Non-publicités: {np.sum(y == 0)}")

        # Sauvegarder les stats
        self.training_stats = {
            'n_files': len(training_files),
            'file_stats': file_stats,
            'total_segments': len(all_segments),
            'n_ad_segments': len(all_ad_segments),
            'n_non_ad_segments': len(all_non_ad_segments),
            'augmentation_used': config.augment_data,
            'segment_duration': config.segment_duration
        }

        # Entraîner le modèle
        self.train(X, y, test_size=0.2)

    def train(self, X: np.ndarray, y: np.ndarray, test_size=0.2) -> None:
        """Entraîne le classifieur"""

        print(f"\n🚀 Entraînement du modèle {self.model_type}...")

        # Split train/test
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=42, stratify=y
        )

        # Normalisation
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)

        # Entraînement
        self.model.fit(X_train_scaled, y_train)

        # Évaluation
        self._evaluate_model(X_train_scaled, y_train, X_test_scaled, y_test)

        # Cross-validation
        cv_scores = cross_val_score(self.model, X_train_scaled, y_train, cv=5)
        print(f"\n📊 Cross-validation (5 folds): {cv_scores.mean():.3f} (+/- {cv_scores.std() * 2:.3f})")

        self.feature_names = self.feature_extractor.get_feature_names()

    def _evaluate_model(self, X_train, y_train, X_test, y_test):
        """Évalue le modèle"""

        y_train_pred = self.model.predict(X_train)
        y_test_pred = self.model.predict(X_test)
        y_test_proba = self.model.predict_proba(X_test)[:, 1]

        print("\n📈 Performance sur l'entraînement:")
        print(classification_report(y_train, y_train_pred,
                                    target_names=['Non-pub', 'Pub']))

        print("\n📈 Performance sur le test:")
        print(classification_report(y_test, y_test_pred,
                                    target_names=['Non-pub', 'Pub']))

        # Matrice de confusion
        cm = confusion_matrix(y_test, y_test_pred)
        fpr, tpr, _ = roc_curve(y_test, y_test_proba)
        roc_auc = auc(fpr, tpr)

        # Visualisation
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

        sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', ax=ax1,
                    xticklabels=['Non-pub', 'Pub'],
                    yticklabels=['Non-pub', 'Pub'])
        ax1.set_title('Matrice de confusion')
        ax1.set_xlabel('Prédit')
        ax1.set_ylabel('Réel')

        ax2.plot(fpr, tpr, label=f'ROC (AUC = {roc_auc:.3f})')
        ax2.plot([0, 1], [0, 1], 'k--')
        ax2.set_xlabel('Taux faux positifs')
        ax2.set_ylabel('Taux vrais positifs')
        ax2.set_title('Courbe ROC')
        ax2.legend()
        ax2.grid(True, alpha=0.3)

        plt.tight_layout()
        plt.savefig('model_evaluation.png', dpi=150)
        plt.show()

        print(f"\n📊 AUC-ROC: {roc_auc:.3f}")

    def predict_segment(self, audio: np.ndarray, segment_duration: float = 3.0) -> Tuple[int, float]:
        """Prédit si un segment audio est une publicité"""

        features = self.feature_extractor.extract_features(audio, segment_duration)
        features_scaled = self.scaler.transform([features])

        prediction = self.model.predict(features_scaled)[0]
        probability = self.model.predict_proba(features_scaled)[0][1]

        return prediction, probability

    def detect_ads_in_file(self, audio_path: str,
                           segment_duration: float = 3.0,
                           overlap: float = 1.0,
                           probability_threshold: float = 0.89,  # Changé à 0.89
                           verbose: bool = True,
                           extract_ads: bool = True) -> List[Dict]:
        """Détecte les publicités dans un fichier audio complet"""

        # Créer le dossier publicités si nécessaire
        if extract_ads:
            ads_dir = Path("publicités")
            ads_dir.mkdir(exist_ok=True)
            print(f"\n📁 Dossier 'publicités' prêt (dans: {ads_dir.absolute()})")

        if verbose:
            print(f"\n🔍 Analyse du fichier: {audio_path}")

        audio, sr = librosa.load(audio_path, sr=self.feature_extractor.sr)
        duration = len(audio) / sr

        if verbose:
            print(f"  Durée totale: {duration:.2f} secondes ({duration / 60:.2f} minutes)")
            print(f"  Seuil de détection: {probability_threshold:.0%}")

        step = segment_duration - overlap
        n_segments = int((duration - segment_duration) / step) + 1

        predictions = []
        probabilities = []
        times = []

        if verbose:
            print(f"  Analyse de {n_segments} segments...")

        for i in tqdm(range(max(0, n_segments)), disable=not verbose):
            start_time = i * step
            end_time = start_time + segment_duration

            start_sample = int(start_time * sr)
            end_sample = int(end_time * sr)

            if end_sample > len(audio):
                break

            segment = audio[start_sample:end_sample]
            pred, prob = self.predict_segment(segment, segment_duration)

            predictions.append(pred)
            probabilities.append(prob)
            times.append(start_time)

        # Lisser les prédictions
        smoothed_probs = np.convolve(probabilities, np.ones(3) / 3, mode='same')

        # Regrouper les segments consécutifs avec seuil à 0.89
        ads = []
        current_ad = None

        for i, prob in enumerate(smoothed_probs):
            if prob >= probability_threshold:
                if current_ad is None:
                    current_ad = {
                        'start': times[i],
                        'end': times[i] + segment_duration,
                        'confidence': prob,
                        'peak_confidence': prob
                    }
                else:
                    current_ad['end'] = times[i] + segment_duration
                    current_ad['confidence'] = max(current_ad['confidence'], prob)
                    current_ad['peak_confidence'] = max(current_ad['peak_confidence'], prob)
            else:
                if current_ad is not None:
                    # Vérifier la durée minimale
                    if current_ad['end'] - current_ad['start'] >= 5.0:
                        ads.append(current_ad)
                    current_ad = None

        if current_ad is not None and current_ad['end'] - current_ad['start'] >= 5.0:
            ads.append(current_ad)

        # Rassembler les publicités séparées de moins de 5 secondes
        merged_ads = self._merge_close_ads(ads, gap_threshold=5.0)

        if verbose and len(merged_ads) != len(ads):
            print(f"\n  🔄 {len(ads)} publicités initiales → {len(merged_ads)} après fusion (seuil 5s)")

        # Extraire et sauvegarder les publicités
        if extract_ads and merged_ads:
            self._extract_and_save_ads(audio, sr, merged_ads, audio_path, ads_dir)

        # Afficher les résultats
        self._print_detection_results(merged_ads, duration)

        if verbose:
            print(f"\n  ✅ {len(merged_ads)} publicités détectées")

        # Visualisation
        if verbose:
            self._plot_detection_results(times, probabilities, smoothed_probs, merged_ads, duration,
                                         probability_threshold)

        return merged_ads

    def _merge_close_ads(self, ads: List[Dict], gap_threshold: float = 5.0) -> List[Dict]:
        """Fusionne les publicités séparées de moins de gap_threshold secondes"""

        if not ads:
            return []

        # Trier par temps de début
        sorted_ads = sorted(ads, key=lambda x: x['start'])
        merged = []
        current = sorted_ads[0].copy()

        for next_ad in sorted_ads[1:]:
            gap = next_ad['start'] - current['end']

            if gap <= gap_threshold:
                # Fusionner
                current['end'] = max(current['end'], next_ad['end'])
                current['confidence'] = max(current['confidence'], next_ad['confidence'])
                current['peak_confidence'] = max(current['peak_confidence'], next_ad['peak_confidence'])
            else:
                # Pas de fusion
                merged.append(current)
                current = next_ad.copy()

        merged.append(current)
        return merged

    def _extract_and_save_ads(self, audio: np.ndarray, sr: int,
                              ads: List[Dict], original_audio_path: str,
                              output_dir: Path):
        """Extrait et sauvegarde les publicités dans des fichiers audio"""

        # Nom de base du fichier original (sans extension)
        base_name = Path(original_audio_path).stem

        print("\n" + "=" * 70)
        print("💾 EXTRACTION DES PUBLICITÉS")
        print("=" * 70)

        for i, ad in enumerate(ads, 1):
            # Calculer les échantillons
            start_sample = int(ad['start'] * sr)
            end_sample = int(ad['end'] * sr)

            # Extraire le segment
            ad_audio = audio[start_sample:end_sample]

            # Nom du fichier
            ad_filename = f"{base_name}_pub_{i:03d}_{ad['start']:.0f}s-{ad['end']:.0f}s.wav"
            ad_path = output_dir / ad_filename

            # Sauvegarder
            sf.write(ad_path, ad_audio, sr)

            # Calculer la durée
            duration = ad['end'] - ad['start']

            print(f"\n  📼 Publicité #{i}:")
            print(f"     Fichier: {ad_filename}")
            print(f"     Durée: {duration:.1f}s")
            print(f"     Timecode: {self._format_time(ad['start'])} → {self._format_time(ad['end'])}")
            print(f"     Confiance: {ad['confidence']:.1%}")
            print(f"     Taille: {len(ad_audio)} échantillons")

        print(f"\n✅ {len(ads)} publicités extraites dans: {output_dir}/")

    def _print_detection_results(self, ads: List[Dict], total_duration: float):
        """Affiche les résultats de détection"""

        print("\n" + "=" * 70)
        print("📋 RÉSULTATS DE LA DÉTECTION - TIMECODES PRÉCIS")
        print("=" * 70)

        if not ads:
            print("\n❌ Aucune publicité détectée")
            return

        print(f"\n📊 Statistiques générales:")
        print(f"   - Durée totale: {self._format_time(total_duration)}")
        print(f"   - Publicités détectées: {len(ads)}")

        total_ad_duration = sum(ad['end'] - ad['start'] for ad in ads)
        print(f"   - Durée totale des pubs: {self._format_time(total_ad_duration)}")
        print(f"   - Pourcentage: {(total_ad_duration / total_duration) * 100:.1f}%")

        # Statistiques supplémentaires
        avg_confidence = np.mean([ad['confidence'] for ad in ads])
        avg_duration = total_ad_duration / len(ads)
        print(f"   - Confiance moyenne: {avg_confidence:.1%}")
        print(f"   - Durée moyenne par pub: {avg_duration:.1f}s")

        print("\n" + "=" * 70)
        print("TIMECODES DÉTAILLÉS")
        print("=" * 70)

        for i, ad in enumerate(ads, 1):
            duration = ad['end'] - ad['start']
            print(f"\n🎯 Publicité #{i}")
            print(f"   Début : {self._format_time(ad['start'])}  ({ad['start']:.3f}s)")
            print(f"   Fin    : {self._format_time(ad['end'])}  ({ad['end']:.3f}s)")
            print(f"   Durée  : {duration:.1f}s")
            print(f"   Confiance : {ad['confidence']:.1%} (max: {ad['peak_confidence']:.1%})")

        # Sauvegarde
        self._save_timecodes_to_file(ads, total_duration)

    def _format_time(self, seconds: float) -> str:
        """Formate un temps en MM:SS.mmm"""
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        ms = int((seconds % 1) * 1000)
        return f"{minutes:02d}:{secs:02d}.{ms:03d}"

    def _save_timecodes_to_file(self, ads: List[Dict], total_duration: float,
                                filename: str = "timecodes_detection.txt"):
        """Sauvegarde les timecodes"""

        with open(filename, 'w', encoding='utf-8') as f:
            f.write("=" * 70 + "\n")
            f.write("TIMECODES DES PUBLICITÉS DÉTECTÉES\n")
            f.write("=" * 70 + "\n\n")
            f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Durée totale: {self._format_time(total_duration)}\n")
            f.write(f"Nombre de publicités: {len(ads)}\n\n")

            for i, ad in enumerate(ads, 1):
                f.write(f"Publicité #{i:2d}:\n")
                f.write(f"  Début: {self._format_time(ad['start'])}\n")
                f.write(f"  Fin:   {self._format_time(ad['end'])}\n")
                f.write(f"  Durée: {ad['end'] - ad['start']:.1f}s\n")
                f.write(f"  Confiance: {ad['confidence']:.1%}\n\n")

            # Format CSV
            f.write("\n" + "=" * 70 + "\n")
            f.write("FORMAT CSV\n")
            f.write("=" * 70 + "\n")
            f.write("start_seconds,end_seconds,duration_seconds,confidence,start_formatted,end_formatted\n")
            for ad in ads:
                f.write(
                    f"{ad['start']:.3f},{ad['end']:.3f},{ad['end'] - ad['start']:.3f},{ad['confidence']:.3f},{self._format_time(ad['start'])},{self._format_time(ad['end'])}\n")

        print(f"\n💾 Timecodes sauvegardés dans: {filename}")

    def _plot_detection_results(self, times, probabilities, smoothed_probs, ads, duration, threshold=0.89):
        """Visualise les résultats"""

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15, 10))

        ax1.plot(times, probabilities, 'b-', alpha=0.5, linewidth=0.5, label='Probabilité brute')
        ax1.plot(times, smoothed_probs, 'r-', linewidth=2, label='Probabilité lissée')
        ax1.axhline(y=threshold, color='green', linestyle='--', label=f'Seuil ({threshold:.0%})')
        ax1.set_xlabel('Temps (secondes)')
        ax1.set_ylabel('Probabilité')
        ax1.set_title('Détection des publicités')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        ax1.set_ylim([0, 1])

        if ads:
            for ad in ads:
                ax2.axvspan(ad['start'], ad['end'], alpha=0.3, color='red')
                ax2.text(ad['start'] + (ad['end'] - ad['start']) / 2, 0.5,
                         f"Pub\n{ad['end'] - ad['start']:.1f}s",
                         ha='center', va='center', fontsize=8)

        ax2.set_xlim([0, duration])
        ax2.set_ylim([0, 1])
        ax2.set_xlabel('Temps (secondes)')
        ax2.set_title('Timeline des publicités')
        ax2.grid(True, alpha=0.3)

        plt.tight_layout()
        plt.savefig('detection_results.png', dpi=150)
        plt.show()

    def save_model(self, path: str):
        """Sauvegarde le modèle"""
        model_data = {
            'model': self.model,
            'scaler': self.scaler,
            'model_type': self.model_type,
            'feature_names': self.feature_names,
            'training_stats': self.training_stats
        }
        joblib.dump(model_data, path)
        print(f"💾 Modèle sauvegardé: {path}")

    def load_model(self, path: str):
        """Charge un modèle sauvegardé"""
        model_data = joblib.load(path)
        self.model = model_data['model']
        self.scaler = model_data['scaler']
        self.model_type = model_data['model_type']
        self.feature_names = model_data['feature_names']
        self.training_stats = model_data.get('training_stats', {})
        print(f"📂 Modèle chargé: {path}")
        if self.training_stats:
            print(f"   Entraîné sur {self.training_stats.get('n_files', 0)} fichier(s)")


def create_timecode_template():
    """Crée un fichier template pour les timecodes"""

    template = """# Fichier de timecodes pour les publicités
# Format: début fin (en secondes) OU MM:SS - MM:SS
# Les lignes commençant par # sont ignorées

# Exemples:
# 123.5 145.2
# 02:03.5 - 02:25.2
# 5:30 - 6:15

# Ajoute ici tes timecodes (un par ligne):
"""

    with open("timecodes_template.txt", "w", encoding='utf-8') as f:
        f.write(template)

    print("📄 Template créé: timecodes_template.txt")


def create_config_file():
    """Crée un fichier de configuration pour l'entraînement multi-fichiers"""

    config_example = """# Fichier de configuration pour l'entraînement multi-fichiers
# Format: chemin_audio|chemin_timecodes|nom_optionnel

# Exemples:
# emission1.mp3|timecodes1.txt|Emission Lundi
# emission2.wav|timecodes2.csv|Emission Mardi
# /chemin/complet/emission3.mp3|/autre/chemin/timecodes3.txt

# Ajoute une ligne par fichier audio:
"""

    with open("training_config.txt", "w", encoding='utf-8') as f:
        f.write(config_example)

    print("📄 Fichier de configuration créé: training_config.txt")


def main_training_from_multiple_files():
    """Pipeline d'entraînement à partir de plusieurs fichiers"""

    print("=" * 70)
    print("ENTRAÎNEMENT À PARTIR DE PLUSIEURS FICHIERS AUDIO")
    print("=" * 70)

    print("\n📋 Options d'entrée:")
    print("  1. Fichier de configuration (recommandé pour >2 fichiers)")
    print("  2. Saisie interactive (pour 1-2 fichiers)")

    choice = input("\nChoix (1-2, défaut=1): ").strip() or "1"

    training_files = []

    if choice == "1":
        config_file = input("Fichier de configuration (défaut=training_config.txt): ").strip()
        if not config_file:
            config_file = "training_config.txt"

        if not Path(config_file).exists():
            print(f"⚠️ Fichier non trouvé: {config_file}")
            create = input("Créer un fichier template? (o/n): ").strip().lower()
            if create == 'o':
                create_config_file()
                print("\n📝 Édite le fichier 'training_config.txt' avec tes fichiers")
                print("   Puis relance le programme")
            return

        # Lire le fichier de configuration
        with open(config_file, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue

                parts = line.split('|')
                if len(parts) >= 2:
                    audio_path = parts[0].strip()
                    timecodes_path = parts[1].strip()
                    name = parts[2].strip() if len(parts) >= 3 else f"Fichier_{line_num}"

                    training_files.append(TrainingFile(audio_path, timecodes_path, name))

        if not training_files:
            print("❌ Aucun fichier valide trouvé dans la configuration")
            return

    else:  # Mode interactif
        n_files = int(input("Nombre de fichiers à utiliser: "))

        for i in range(n_files):
            print(f"\n--- Fichier #{i + 1} ---")
            audio_path = input(f"  Chemin du fichier audio: ").strip()
            timecodes_path = input(f"  Chemin du fichier de timecodes: ").strip()
            name = input(f"  Nom (optionnel, Enter pour auto): ").strip()

            if not name:
                name = Path(audio_path).stem

            training_files.append(TrainingFile(audio_path, timecodes_path, name))

    # Afficher la liste des fichiers
    print("\n" + "=" * 70)
    print("📁 FICHIERS À TRAITER")
    print("=" * 70)
    for tf in training_files:
        print(f"\n📻 {tf.name}")
        print(f"   Audio: {tf.audio_path}")
        print(f"   Timecodes: {tf.timecodes_path}")

    # Configuration
    print("\n⚙️ Configuration de l'entraînement:")
    segment_duration = float(input("Durée des segments (secondes, défaut=3): ") or "3")
    non_ad_ratio = float(input("Ratio non-pubs/pubs (défaut=2): ") or "2")
    augment = input("Augmentation des données? (o/n, défaut=o): ").strip().lower() != 'n'

    config = TrainingConfig(
        segment_duration=segment_duration,
        non_ad_ratio=non_ad_ratio,
        augment_data=augment
    )

    # Modèle
    print("\n🤖 Choix du modèle:")
    print("  1. Random Forest (recommandé, rapide)")
    print("  2. SVM (précis mais plus lent)")
    print("  3. MLP (réseau de neurones)")
    model_choice = input("Choix (1-3, défaut=1): ").strip() or "1"
    model_map = {'1': 'random_forest', '2': 'svm', '3': 'mlp'}
    model_type = model_map.get(model_choice, 'random_forest')

    # Entraînement
    classifier = AdvertisementClassifier(model_type=model_type)
    classifier.train_from_multiple_files(training_files, config)

    # Sauvegarde
    save = input("\n💾 Sauvegarder le modèle? (o/n, défaut=o): ").strip().lower() != 'n'
    if save:
        model_name = input("Nom du modèle (défaut=rlac-audio-segmenter-chroniques_model.pkl): ").strip() or "rlac-audio-segmenter-chroniques_model.pkl"
        classifier.save_model(model_name)

    # Test
    test = input("\n🎵 Tester sur un fichier audio? (o/n): ").strip().lower()
    if test == 'o':
        test_file = input("Fichier audio à analyser: ").strip()
        if Path(test_file).exists():
            extract = input("Extraire les publicités dans un dossier? (o/n, défaut=o): ").strip().lower() != 'n'
            classifier.detect_ads_in_file(test_file, extract_ads=extract)
        else:
            print(f"❌ Fichier non trouvé: {test_file}")

    print("\n✅ Entraînement terminé!")


def quick_detection(model_path: str, audio_file: str, extract_ads: bool = True):
    """Détection rapide avec un modèle pré-entraîné"""

    classifier = AdvertisementClassifier()
    classifier.load_model(model_path)
    ads = classifier.detect_ads_in_file(audio_file, verbose=True, extract_ads=extract_ads)
    return ads


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == '--quick':
        if len(sys.argv) >= 4:
            extract = True
            if len(sys.argv) >= 5 and sys.argv[4].lower() == '--no-extract':
                extract = False
            quick_detection(sys.argv[2], sys.argv[3], extract_ads=extract)
        else:
            print("Usage: python main.py --quick <model.pkl> <audio.mp3> [--no-extract]")
    else:
        main_training_from_multiple_files()