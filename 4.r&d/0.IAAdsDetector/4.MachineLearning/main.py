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
from dataclasses import dataclass
from typing import List, Tuple, Dict, Optional, Union
import warnings
import json
from tqdm import tqdm
import soundfile as sf
import random
from collections import defaultdict

warnings.filterwarnings('ignore')


@dataclass
class TrainingConfig:
    """Configuration pour l'entraînement"""
    segment_duration: float = 3.0  # Durée des segments en secondes
    hop_duration: float = 1.5  # Pas entre segments (chevauchement)
    min_segment_energy: float = 0.01  # Énergie minimale pour ignorer le silence
    balance_classes: bool = True  # Équilibrer les classes
    augment_data: bool = True  # Augmentation des données


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

        # S'assurer que le segment a la bonne durée
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

    def augment_audio(self, audio: np.ndarray, sr: int) -> np.ndarray:
        """Augmentation des données pour plus de robustesse"""

        augmentation_type = random.choice(['none', 'speed', 'noise', 'shift'])

        if augmentation_type == 'speed' and random.random() > 0.5:
            # Léger changement de vitesse
            speed_factor = random.uniform(0.9, 1.1)
            audio = librosa.effects.time_stretch(audio, rate=speed_factor)
            # Rééchantillonner si nécessaire
            if len(audio) < int(3 * sr):
                audio = np.pad(audio, (0, int(3 * sr) - len(audio)))
            else:
                audio = audio[:int(3 * sr)]

        elif augmentation_type == 'noise' and random.random() > 0.5:
            # Ajout de bruit blanc léger
            noise = np.random.normal(0, 0.005, len(audio))
            audio = audio + noise

        elif augmentation_type == 'shift' and random.random() > 0.5:
            # Décalage temporel léger
            shift = int(random.uniform(-0.1, 0.1) * sr)
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


class DataLoader:
    """Charge et prépare les données d'entraînement à partir de fichiers"""

    def __init__(self, feature_extractor: FeatureExtractor, config: TrainingConfig):
        self.feature_extractor = feature_extractor
        self.config = config

    def load_audio_file(self, file_path: str) -> Tuple[np.ndarray, int]:
        """Charge un fichier audio"""
        try:
            audio, sr = librosa.load(file_path, sr=self.feature_extractor.sr)
            return audio, sr
        except Exception as e:
            print(f"  Erreur chargement {file_path}: {e}")
            return None, None

    def segment_audio(self, audio: np.ndarray, sr: int, label: int) -> List[Dict]:
        """Découpe un fichier audio en segments"""

        segments = []
        duration = len(audio) / sr
        segment_samples = int(self.config.segment_duration * sr)
        hop_samples = int(self.config.hop_duration * sr)

        if duration < self.config.segment_duration:
            # Fichier trop court, on le pad
            audio_padded = np.pad(audio, (0, segment_samples - len(audio)))
            segments.append({
                'audio': audio_padded,
                'start': 0,
                'end': duration,
                'label': label
            })
        else:
            # Découpage glissant
            for start_sample in range(0, len(audio) - segment_samples + 1, hop_samples):
                start_time = start_sample / sr
                end_time = start_time + self.config.segment_duration
                segment_audio = audio[start_sample:start_sample + segment_samples]

                # Vérifier l'énergie du segment (ignorer le silence)
                energy = np.mean(np.abs(segment_audio))
                if energy > self.config.min_segment_energy:
                    segments.append({
                        'audio': segment_audio,
                        'start': start_time,
                        'end': end_time,
                        'label': label
                    })

        return segments

    def load_directory(self, directory_path: str, label: int,
                       file_extension: str = '.mp3') -> List[Dict]:
        """Charge tous les fichiers audio d'un dossier"""

        directory = Path(directory_path)
        if not directory.exists():
            print(f"  Dossier non trouvé: {directory_path}")
            return []

        audio_files = list(directory.glob(f'*{file_extension}')) + \
                      list(directory.glob('*.wav')) + \
                      list(directory.glob('*.m4a'))

        if not audio_files:
            print(f"  Aucun fichier audio trouvé dans: {directory_path}")
            return []

        print(f"  Chargement de {len(audio_files)} fichiers depuis {directory.name}...")

        all_segments = []
        for audio_file in tqdm(audio_files):
            audio, sr = self.load_audio_file(str(audio_file))
            if audio is not None:
                segments = self.segment_audio(audio, sr, label)
                all_segments.extend(segments)

        print(f"    {len(all_segments)} segments extraits (label={label})")
        return all_segments

    def prepare_training_data(self, ads_dirs: List[str], non_ads_dirs: List[str]) -> Tuple[np.ndarray, np.ndarray]:
        """
        Prépare les données d'entraînement à partir de dossiers

        Args:
            ads_dirs: Liste des dossiers contenant des fichiers de publicités
            non_ads_dirs: Liste des dossiers contenant des fichiers sans publicités
        """

        print("\n" + "=" * 60)
        print("PRÉPARATION DES DONNÉES D'ENTRAÎNEMENT")
        print("=" * 60)

        all_segments = []

        # Charger les publicités
        print("\n📁 Chargement des publicités (classe 1):")
        for ads_dir in ads_dirs:
            print(f"  Dossier: {ads_dir}")
            segments = self.load_directory(ads_dir, label=1)
            all_segments.extend(segments)

        # Charger les non-publicités
        print("\n📁 Chargement des non-publicités (classe 0):")
        for non_ads_dir in non_ads_dirs:
            print(f"  Dossier: {non_ads_dir}")
            segments = self.load_directory(non_ads_dir, label=0)
            all_segments.extend(segments)

        if not all_segments:
            print("❌ Aucun segment chargé!")
            return np.array([]), np.array([])

        # Équilibrer les classes si nécessaire
        if self.config.balance_classes:
            all_segments = self._balance_classes(all_segments)

        # Extraire les caractéristiques
        print("\n🔄 Extraction des caractéristiques...")
        features = []
        labels = []

        for segment in tqdm(all_segments):
            audio = segment['audio']

            # Augmentation des données pour les publicités (optionnel)
            if self.config.augment_data and segment['label'] == 1:
                # Version originale
                feat = self.feature_extractor.extract_features(audio, self.config.segment_duration)
                features.append(feat)
                labels.append(segment['label'])

                # Version augmentée (50% de chance)
                if random.random() > 0.5:
                    augmented_audio = self.feature_extractor.augment_audio(audio, self.feature_extractor.sr)
                    feat_aug = self.feature_extractor.extract_features(augmented_audio, self.config.segment_duration)
                    features.append(feat_aug)
                    labels.append(segment['label'])
            else:
                feat = self.feature_extractor.extract_features(audio, self.config.segment_duration)
                features.append(feat)
                labels.append(segment['label'])

        X = np.array(features)
        y = np.array(labels)

        print(f"\n✅ Données préparées:")
        print(f"  - Total segments: {len(X)}")
        print(f"  - Publicités (classe 1): {np.sum(y == 1)}")
        print(f"  - Non-publicités (classe 0): {np.sum(y == 0)}")
        print(f"  - Dimension caractéristiques: {X.shape[1]}")

        return X, y

    def _balance_classes(self, segments: List[Dict]) -> List[Dict]:
        """Équilibre les classes en sous-échantillonnant la classe majoritaire"""

        ads_segments = [s for s in segments if s['label'] == 1]
        non_ads_segments = [s for s in segments if s['label'] == 0]

        if len(ads_segments) > len(non_ads_segments):
            # Trop de pubs, on sous-échantillonne
            ads_segments = random.sample(ads_segments, len(non_ads_segments))
        elif len(non_ads_segments) > len(ads_segments):
            # Trop de non-pubs, on sous-échantillonne
            non_ads_segments = random.sample(non_ads_segments, len(ads_segments))

        balanced_segments = ads_segments + non_ads_segments
        random.shuffle(balanced_segments)

        print(f"  Équilibrage: {len(ads_segments)} pubs / {len(non_ads_segments)} non-pubs")

        return balanced_segments


class AdvertisementClassifier:
    """Classifieur pour détecter les publicités"""

    def __init__(self, model_type='random_forest'):
        self.model_type = model_type
        self.feature_extractor = FeatureExtractor()
        self.scaler = StandardScaler()
        self.model = self._create_model()
        self.feature_names = None

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

    def train_from_directories(self, ads_dirs: List[str], non_ads_dirs: List[str],
                               config: TrainingConfig = None) -> None:
        """
        Entraîne le modèle à partir de dossiers

        Args:
            ads_dirs: Liste des dossiers contenant des fichiers de publicités
            non_ads_dirs: Liste des dossiers contenant des fichiers sans publicités
            config: Configuration d'entraînement
        """

        if config is None:
            config = TrainingConfig()

        # Préparer les données
        data_loader = DataLoader(self.feature_extractor, config)
        X, y = data_loader.prepare_training_data(ads_dirs, non_ads_dirs)

        if len(X) == 0:
            print("❌ Impossible d'entraîner: pas de données")
            return

        # Entraîner
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
                           probability_threshold: float = 0.7,
                           verbose: bool = True) -> List[Dict]:
        """
        Détecte les publicités dans un fichier audio complet

        Args:
            audio_path: chemin du fichier audio
            segment_duration: durée de chaque segment à analyser (secondes)
            overlap: chevauchement entre segments (secondes)
            probability_threshold: seuil de probabilité pour considérer comme pub
            verbose: afficher les détails dans la console

        Returns:
            Liste des publicités détectées avec timecodes
        """

        if verbose:
            print(f"\n🔍 Analyse du fichier: {audio_path}")

        audio, sr = librosa.load(audio_path, sr=self.feature_extractor.sr)
        duration = len(audio) / sr

        if verbose:
            print(f"  Durée totale: {duration:.2f} secondes ({duration / 60:.2f} minutes)")

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

        # Regrouper les segments consécutifs
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
            else:
                if current_ad is not None:
                    # Vérifier la durée minimale
                    if current_ad['end'] - current_ad['start'] >= 5.0:
                        ads.append(current_ad)
                    current_ad = None

        # Dernier segment
        if current_ad is not None and current_ad['end'] - current_ad['start'] >= 5.0:
            ads.append(current_ad)

        # Afficher les résultats détaillés dans la console
        self._print_detection_results(ads, duration)

        if verbose:
            print(f"\n  ✅ {len(ads)} publicités détectées")

        # Visualisation (optionnelle)
        if verbose:
            self._plot_detection_results(times, probabilities, smoothed_probs, ads, duration)

        return ads

    def _print_detection_results(self, ads: List[Dict], total_duration: float):
        """Affiche les résultats de détection dans la console"""

        print("\n" + "=" * 70)
        print("📋 RÉSULTATS DE LA DÉTECTION - TIMECODES PRÉCIS")
        print("=" * 70)

        if not ads:
            print("\n❌ Aucune publicité détectée")
            print("   Suggestions:")
            print("   - Abaissez le seuil de probabilité (ex: 0.5)")
            print("   - Vérifiez que le modèle est adapté à ce type d'audio")
            return

        print(f"\n📊 Statistiques générales:")
        print(f"   - Durée totale du fichier: {self._format_time(total_duration)}")
        print(f"   - Nombre de publicités détectées: {len(ads)}")

        total_ad_duration = sum(ad['end'] - ad['start'] for ad in ads)
        print(f"   - Durée totale des publicités: {self._format_time(total_ad_duration)}")
        print(f"   - Pourcentage de publicités: {(total_ad_duration / total_duration) * 100:.1f}%")

        print("\n" + "=" * 70)
        print("TIMECODES DÉTAILLÉS PAR PUBLICITÉ")
        print("=" * 70)

        for i, ad in enumerate(ads, 1):
            duration = ad['end'] - ad['start']
            start_min = int(ad['start'] // 60)
            start_sec = int(ad['start'] % 60)
            start_ms = int((ad['start'] % 1) * 1000)

            end_min = int(ad['end'] // 60)
            end_sec = int(ad['end'] % 60)
            end_ms = int((ad['end'] % 1) * 1000)

            print(f"\n🎯 Publicité #{i}")
            print(f"   ⏱️  Début : {start_min:2d}:{start_sec:02d}:{start_ms:03d}  ({ad['start']:.3f} secondes)")
            print(f"   ⏱️  Fin    : {end_min:2d}:{end_sec:02d}:{end_ms:03d}  ({ad['end']:.3f} secondes)")
            print(f"   📏 Durée  : {duration:.1f} secondes")
            print(f"   🎯 Confiance : {ad['confidence']:.1%}")

            # Barre de confiance visuelle
            confidence_bar = "█" * int(ad['confidence'] * 20) + "░" * (20 - int(ad['confidence'] * 20))
            print(f"   📊 Confiance : [{confidence_bar}] {ad['confidence']:.1%}")

        # Résumé compact pour export facile
        print("\n" + "=" * 70)
        print("📝 RÉSUMÉ COMPACT (copiable)")
        print("=" * 70)
        for i, ad in enumerate(ads, 1):
            print(
                f"Pub {i:2d}: {self._format_time(ad['start'])} -> {self._format_time(ad['end'])} (durée: {ad['end'] - ad['start']:.1f}s, conf: {ad['confidence']:.1%})")

        # Sauvegarde automatique des timecodes dans un fichier
        self._save_timecodes_to_file(ads, total_duration)

    def _format_time(self, seconds: float) -> str:
        """Formate un temps en MM:SS.mmm"""
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        ms = int((seconds % 1) * 1000)
        return f"{minutes:02d}:{secs:02d}.{ms:03d}"

    def _save_timecodes_to_file(self, ads: List[Dict], total_duration: float,
                                filename: str = "timecodes_detection.txt"):
        """Sauvegarde les timecodes dans un fichier texte"""

        with open(filename, 'w', encoding='utf-8') as f:
            f.write("=" * 70 + "\n")
            f.write("TIMECODES DES PUBLICITÉS DÉTECTÉES\n")
            f.write("=" * 70 + "\n\n")

            f.write(f"Durée totale: {self._format_time(total_duration)}\n")
            f.write(f"Nombre de publicités: {len(ads)}\n\n")

            f.write("-" * 70 + "\n")
            f.write("FORMAT MM:SS.mmm\n")
            f.write("-" * 70 + "\n\n")

            for i, ad in enumerate(ads, 1):
                f.write(f"Publicité #{i:2d}:\n")
                f.write(f"  Début: {self._format_time(ad['start'])}\n")
                f.write(f"  Fin:   {self._format_time(ad['end'])}\n")
                f.write(f"  Durée: {ad['end'] - ad['start']:.1f}s\n")
                f.write(f"  Confiance: {ad['confidence']:.1%}\n")
                f.write("\n")

            # Format CSV pour import facile
            f.write("\n" + "=" * 70 + "\n")
            f.write("FORMAT CSV (pour Excel/tableur)\n")
            f.write("=" * 70 + "\n")
            f.write("start_seconds,end_seconds,duration_seconds,confidence,start_formatted,end_formatted\n")
            for ad in ads:
                f.write(
                    f"{ad['start']:.3f},{ad['end']:.3f},{ad['end'] - ad['start']:.3f},{ad['confidence']:.3f},{self._format_time(ad['start'])},{self._format_time(ad['end'])}\n")

        print(f"\n💾 Timecodes sauvegardés dans: {filename}")

    def _plot_detection_results(self, times, probabilities, smoothed_probs, ads, duration):
        """Visualise les résultats de détection"""

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15, 10))

        ax1.plot(times, probabilities, 'b-', alpha=0.5, label='Probabilités brutes', linewidth=0.5)
        ax1.plot(times, smoothed_probs, 'r-', label='Probabilités lissées', linewidth=2)
        ax1.axhline(y=0.7, color='green', linestyle='--', label='Seuil (0.7)')
        ax1.set_xlabel('Temps (secondes)')
        ax1.set_ylabel('Probabilité')
        ax1.set_title('Détection des publicités')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        ax1.set_ylim([0, 1])

        if ads:
            for ad in ads:
                ax2.axvspan(ad['start'], ad['end'], alpha=0.3, color='red')
                # Ajouter le timecode formaté
                timecode = self._format_time(ad['start'])
                ax2.text(ad['start'] + (ad['end'] - ad['start']) / 2, 0.5,
                         f"Pub {timecode}\n{ad['end'] - ad['start']:.1f}s",
                         ha='center', va='center', fontsize=8,
                         bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.8))

        ax2.set_xlim([0, duration])
        ax2.set_ylim([0, 1])
        ax2.set_xlabel('Temps (secondes)')
        ax2.set_title('Timeline des publicités détectées')
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
            'feature_names': self.feature_names
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
        print(f"📂 Modèle chargé: {path}")


def create_directories_structure():
    """Crée la structure de dossiers recommandée"""

    print("\n📁 Structure de dossiers recommandée:")
    print("""
    training_data/
    ├── ads/           # Met tes fichiers de publicités ici
    │   ├── ad1.mp3
    │   ├── ad2.mp3
    │   └── ...
    └── non_ads/       # Met tes fichiers sans publicités ici
        ├── music1.mp3
        ├── speech1.mp3
        └── ...
    """)

    # Créer les dossiers
    Path("training_data/ads").mkdir(parents=True, exist_ok=True)
    Path("training_data/non_ads").mkdir(parents=True, exist_ok=True)

    print("✅ Dossiers créés: training_data/ads/ et training_data/non_ads/")


def main_training():
    """Pipeline principal d'entraînement"""

    print("=" * 60)
    print("CLASSIFICATION SUPERVISÉE POUR LA DÉTECTION DE PUBLICITÉS")
    print("=" * 60)

    # Créer la structure de dossiers
    create_directories_structure()

    print("\n📋 Instructions:")
    print("1. Placez vos fichiers de publicités dans 'training_data/ads/'")
    print("2. Placez vos fichiers sans publicités dans 'training_data/non_ads/'")
    print("3. Les fichiers peuvent être de n'importe quelle durée")
    print("   (le programme les découpera automatiquement en segments de 3 secondes)")

    input("\nAppuyez sur Entrée quand les fichiers sont prêts...")

    # Configuration
    print("\n⚙️ Configuration de l'entraînement:")

    segment_duration = float(input("Durée des segments (secondes, défaut=3): ") or "3")
    balance = input("Équilibrer les classes? (o/n, défaut=o): ").strip().lower() != 'n'
    augment = input("Augmentation des données? (o/n, défaut=o): ").strip().lower() != 'n'

    config = TrainingConfig(
        segment_duration=segment_duration,
        hop_duration=segment_duration / 2,  # 50% de chevauchement
        balance_classes=balance,
        augment_data=augment
    )

    # Choix du modèle
    print("\n🤖 Choix du modèle:")
    print("  1. Random Forest (recommandé, rapide)")
    print("  2. SVM (précis mais plus lent)")
    print("  3. MLP (réseau de neurones)")
    model_choice = input("Votre choix (1-3, défaut=1): ").strip() or "1"

    model_map = {'1': 'random_forest', '2': 'svm', '3': 'mlp'}
    model_type = model_map.get(model_choice, 'random_forest')

    # Entraînement
    classifier = AdvertisementClassifier(model_type=model_type)

    # Utiliser les dossiers créés
    ads_dirs = ["training_data/ads"]
    non_ads_dirs = ["training_data/non_ads"]

    classifier.train_from_directories(ads_dirs, non_ads_dirs, config)

    # Sauvegarde
    save = input("\n💾 Sauvegarder le modèle? (o/n, défaut=o): ").strip().lower() != 'n'
    if save:
        model_name = input("Nom du modèle (défaut=ad_model.pkl): ").strip() or "ad_model.pkl"
        classifier.save_model(model_name)

    # Test
    test = input("\n🎵 Tester sur un fichier audio? (o/n): ").strip().lower()
    if test == 'o':
        test_file = input("Chemin du fichier audio: ").strip()
        if Path(test_file).exists():
            ads = classifier.detect_ads_in_file(test_file, verbose=True)

            # Exporter
            export = input("\n💾 Exporter les publicités détectées? (o/n): ").strip().lower()
            if export == 'o':
                output_dir = Path("ads_detected")
                output_dir.mkdir(exist_ok=True)

                audio, sr = librosa.load(test_file, sr=22050)
                for i, ad in enumerate(ads, 1):
                    start_sample = int(ad['start'] * sr)
                    end_sample = int(ad['end'] * sr)
                    ad_audio = audio[start_sample:end_sample]
                    output_file = output_dir / f"ad_{i:03d}_{int(ad['start'])}s-{int(ad['end'])}s.wav"
                    sf.write(output_file, ad_audio, sr)
                    print(f"  ✅ Exporté: {output_file}")
        else:
            print(f"❌ Fichier non trouvé: {test_file}")

    print("\n✅ Entraînement terminé!")


def quick_detection(model_path: str, audio_file: str):
    """Détection rapide avec un modèle pré-entraîné"""

    classifier = AdvertisementClassifier()
    classifier.load_model(model_path)
    ads = classifier.detect_ads_in_file(audio_file, verbose=True)

    return ads


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == '--quick':
        if len(sys.argv) >= 4:
            quick_detection(sys.argv[2], sys.argv[3])
        elif len(sys.argv) == 3:
            print("Usage: python ads_classifier.py --quick <model.pkl> <audio.mp3>")
            print("\nExemple:")
            print("  python ads_classifier.py --quick mon_modele.pkl emission_radio.mp3")
        else:
            print("❌ Arguments manquants!")
            print("Usage: python ads_classifier.py --quick <model.pkl> <audio.mp3>")
    else:
        main_training()