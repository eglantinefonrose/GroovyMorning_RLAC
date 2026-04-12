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
from typing import List, Tuple, Dict, Optional
import warnings
import json
from tqdm import tqdm
import soundfile as sf
import random
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
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"Fichier non trouvé: {file_path}")

        if file_path.suffix == '.json':
            with open(file_path, 'r') as f:
                data = json.load(f)
                if isinstance(data, list):
                    return [(item['start'], item['end']) for item in data]
                elif isinstance(data, dict) and 'ads' in data:
                    return [(ad['start'], ad['end']) for ad in data['ads']]

        elif file_path.suffix == '.csv':
            df = pd.read_csv(file_path)
            if 'start' in df.columns and 'end' in df.columns:
                return [(row['start'], row['end']) for _, row in df.iterrows()]
            elif 'start' in df.columns and 'duration' in df.columns:
                return [(row['start'], row['start'] + row['duration']) for _, row in df.iterrows()]

        else:
            timecodes = []
            with open(file_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    if '-' in line:
                        parts = line.split('-')
                        if len(parts) == 2:
                            start_str = parts[0].strip()
                            end_str = parts[1].strip()
                            start = TimecodeLoader._parse_time(start_str)
                            end = TimecodeLoader._parse_time(end_str)
                            if start is not None and end is not None:
                                timecodes.append((start, end))
                    elif ',' in line:
                        parts = line.split(',')
                        if len(parts) == 2:
                            try:
                                start = float(parts[0].strip())
                                end = float(parts[1].strip())
                                timecodes.append((start, end))
                            except:
                                pass
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
        try:
            if ':' in time_str:
                parts = time_str.split(':')
                if len(parts) == 2:
                    return float(parts[0]) * 60 + float(parts[1])
                elif len(parts) == 3:
                    return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
            return float(time_str)
        except:
            return None

class FeatureExtractor:
    """Extracteur de caractéristiques audio"""

    def __init__(self, sr=22050, n_mfcc=13, hop_length=512, n_fft=2048, n_bands=4):
        self.sr = sr
        self.n_mfcc = n_mfcc
        self.hop_length = hop_length
        self.n_fft = n_fft
        self.n_bands = n_bands

    def extract_features(self, audio: np.ndarray, segment_duration: float = 3.0) -> np.ndarray:
        expected_length = int(segment_duration * self.sr)
        if len(audio) < expected_length:
            audio = np.pad(audio, (0, expected_length - len(audio)))
        else:
            audio = audio[:expected_length]

        features = []
        mfcc = librosa.feature.mfcc(y=audio, sr=self.sr, n_mfcc=self.n_mfcc, hop_length=self.hop_length, n_fft=self.n_fft)
        features.extend(np.mean(mfcc, axis=1))
        features.extend(np.std(mfcc, axis=1))

        stft = np.abs(librosa.stft(audio, hop_length=self.hop_length, n_fft=self.n_fft))
        freqs = librosa.fft_frequencies(sr=self.sr, n_fft=self.n_fft)
        band_edges = np.linspace(0, len(freqs), self.n_bands + 1, dtype=int)
        for i in range(self.n_bands):
            band_energy = np.sum(stft[band_edges[i]:band_edges[i + 1]] ** 2)
            features.append(np.log1p(band_energy))

        zcr = librosa.feature.zero_crossing_rate(audio, hop_length=self.hop_length)
        features.extend([np.mean(zcr), np.std(zcr)])

        rms = librosa.feature.rms(y=audio, hop_length=self.hop_length)[0]
        features.extend([np.mean(rms), np.std(rms), np.max(rms) - np.min(rms)])

        rolloff = librosa.feature.spectral_rolloff(y=audio, sr=self.sr, hop_length=self.hop_length)
        features.extend([np.mean(rolloff), np.std(rolloff)])

        centroid = librosa.feature.spectral_centroid(y=audio, sr=self.sr, hop_length=self.hop_length)
        features.extend([np.mean(centroid), np.std(centroid)])

        bandwidth = librosa.feature.spectral_bandwidth(y=audio, sr=self.sr, hop_length=self.hop_length)
        features.extend([np.mean(bandwidth), np.std(bandwidth)])

        if mfcc.shape[1] > 1:
            mfcc_diff = np.diff(mfcc, axis=1)
            features.extend([np.mean(np.abs(mfcc_diff)), np.std(np.abs(mfcc_diff))])
        else:
            features.extend([0, 0])

        return np.array(features)

    def augment_audio(self, audio: np.ndarray) -> np.ndarray:
        augmentation_type = random.choice(['none', 'speed', 'noise', 'shift'])
        if augmentation_type == 'speed' and random.random() > 0.5:
            speed_factor = random.uniform(0.9, 1.1)
            audio = librosa.effects.time_stretch(audio, rate=speed_factor)
            target = int(3 * self.sr)
            audio = np.pad(audio, (0, max(0, target - len(audio))))[:target]
        elif augmentation_type == 'noise' and random.random() > 0.5:
            audio = audio + np.random.normal(0, 0.005, len(audio))
        elif augmentation_type == 'shift' and random.random() > 0.5:
            shift = int(random.uniform(-0.1, 0.1) * self.sr)
            audio = np.roll(audio, shift)
            if shift > 0: audio[:shift] = 0
            else: audio[shift:] = 0
        return audio

    def get_feature_names(self) -> List[str]:
        names = [f'mfcc_{i}_mean' for i in range(self.n_mfcc)]
        names += [f'mfcc_{i}_std' for i in range(self.n_mfcc)]
        names += [f'band_energy_{i}' for i in range(self.n_bands)]
        names += ['zcr_mean', 'zcr_std', 'rms_mean', 'rms_std', 'rms_range']
        names += ['rolloff_mean', 'rolloff_std', 'centroid_mean', 'centroid_std', 'bandwidth_mean', 'bandwidth_std', 'mfcc_transition_mean', 'mfcc_transition_std']
        return names

class MultiAudioSegmenter:
    def __init__(self, feature_extractor, config: TrainingConfig):
        self.feature_extractor = feature_extractor
        self.config = config

    def extract_ad_segments(self, audio: np.ndarray, sr: int, timecodes: List[Tuple[float, float]], source_name: str = "") -> List[Dict]:
        segments = []
        duration = len(audio) / sr
        segment_samples = int(self.config.segment_duration * sr)
        hop_samples = int(segment_samples / 2)

        for start, end in timecodes:
            start, end = max(0, start), min(duration, end)
            if end - start < self.config.segment_duration: continue
            
            start_sample, end_sample = int(start * sr), int(end * sr)
            for seg_start in range(start_sample, end_sample - segment_samples + 1, hop_samples):
                seg_audio = audio[seg_start:seg_start + segment_samples]
                if np.mean(np.abs(seg_audio)) > self.config.min_segment_energy:
                    segments.append({
                        'audio': seg_audio, 'start': seg_start / sr, 'end': (seg_start / sr) + self.config.segment_duration,
                        'label': 1, 'source': source_name, 'type': 'ad'
                    })
        return segments

    def extract_non_ad_segments(self, audio: np.ndarray, sr: int, ad_timecodes: List[Tuple[float, float]], n_segments: int, source_name: str = "") -> List[Dict]:
        duration = len(audio) / sr
        forbidden = sorted([(max(0, s - self.config.non_ad_min_gap), min(duration, e + self.config.non_ad_min_gap)) for s, e in ad_timecodes])
        merged = []
        for zone in forbidden:
            if not merged or zone[0] > merged[-1][1]: merged.append(list(zone))
            else: merged[-1][1] = max(merged[-1][1], zone[1])

        segments = []
        segment_samples = int(self.config.segment_duration * sr)
        attempts, max_attempts = 0, n_segments * 10
        while len(segments) < n_segments and attempts < max_attempts:
            start_t = random.uniform(0, duration - self.config.segment_duration)
            end_t = start_t + self.config.segment_duration
            if all(not (end_t > z[0] and start_t < z[1]) for z in merged):
                seg_audio = audio[int(start_t * sr):int(start_t * sr) + segment_samples]
                if np.mean(np.abs(seg_audio)) > self.config.min_segment_energy:
                    segments.append({'audio': seg_audio, 'start': start_t, 'end': end_t, 'label': 0, 'source': source_name, 'type': 'non_ad'})
            attempts += 1
        return segments

class AdvertisementClassifier:
    def __init__(self, model_type='random_forest'):
        self.model_type = model_type
        self.feature_extractor = FeatureExtractor()
        self.scaler = StandardScaler()
        self.model = self._create_model()
        self.feature_names = None
        self.training_stats = {}

    def _create_model(self):
        if self.model_type == 'random_forest':
            return RandomForestClassifier(n_estimators=100, max_depth=10, min_samples_split=5, min_samples_leaf=2, random_state=42, n_jobs=-1)
        elif self.model_type == 'svm':
            return SVC(kernel='rbf', C=1.0, probability=True, random_state=42)
        elif self.model_type == 'mlp':
            return MLPClassifier(hidden_layer_sizes=(100, 50), max_iter=500, random_state=42, early_stopping=True)
        raise ValueError(f"Modèle inconnu: {self.model_type}")

    def train_from_multiple_files(self, training_files: List[TrainingFile], config: TrainingConfig = None):
        config = config or TrainingConfig()
        segmenter = MultiAudioSegmenter(self.feature_extractor, config)
        all_ads, all_non_ads, file_stats = [], [], []

        for tf in training_files:
            if not Path(tf.audio_path).exists() or not Path(tf.timecodes_path).exists(): continue
            timecodes = TimecodeLoader.load_timecodes(tf.timecodes_path)
            if not timecodes: continue
            audio, sr = librosa.load(tf.audio_path, sr=self.feature_extractor.sr)
            ads = segmenter.extract_ad_segments(audio, sr, timecodes, tf.name)
            non_ads = segmenter.extract_non_ad_segments(audio, sr, timecodes, int(len(ads) * config.non_ad_ratio), tf.name)
            all_ads.extend(ads)
            all_non_ads.extend(non_ads)
            file_stats.append({'name': tf.name, 'n_ads': len(ads), 'n_non_ads': len(non_ads)})

        if not all_ads: return
        all_segments = all_ads + all_non_ads
        random.shuffle(all_segments)
        
        features, labels = [], []
        for seg in tqdm(all_segments, desc="Extracting features"):
            features.append(self.feature_extractor.extract_features(seg['audio'], config.segment_duration))
            labels.append(seg['label'])
            if config.augment_data and seg['label'] == 1 and random.random() > 0.5:
                features.append(self.feature_extractor.extract_features(self.feature_extractor.augment_audio(seg['audio']), config.segment_duration))
                labels.append(seg['label'])

        self.training_stats = {'n_files': len(training_files), 'file_stats': file_stats, 'segment_duration': config.segment_duration}
        self.train(np.array(features), np.array(labels))

    def train(self, X: np.ndarray, y: np.ndarray, test_size=0.2):
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=test_size, random_state=42, stratify=y)
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)
        self.model.fit(X_train_scaled, y_train)
        self._evaluate(X_test_scaled, y_test)
        self.feature_names = self.feature_extractor.get_feature_names()

    def _evaluate(self, X_test, y_test):
        y_pred = self.model.predict(X_test)
        print("\nPerformance sur le test:")
        print(classification_report(y_test, y_pred, target_names=['Non-pub', 'Pub']))

    def predict_segment(self, audio: np.ndarray, segment_duration: float = 3.0):
        feat = self.feature_extractor.extract_features(audio, segment_duration)
        feat_scaled = self.scaler.transform([feat])
        return self.model.predict(feat_scaled)[0], self.model.predict_proba(feat_scaled)[0][1]

    def detect_ads_in_file(self, audio_path: str, segment_duration: float = 3.0, overlap: float = 1.0, threshold: float = 0.89, extract_ads: bool = True):
        if extract_ads: Path("publicités").mkdir(exist_ok=True)
        audio, sr = librosa.load(audio_path, sr=self.feature_extractor.sr)
        duration = len(audio) / sr
        step = segment_duration - overlap
        n_segments = int((duration - segment_duration) / step) + 1
        
        probs, times = [], []
        for i in tqdm(range(max(0, n_segments)), desc="Analyzing"):
            start_t = i * step
            if (start_t + segment_duration) * sr > len(audio): break
            _, prob = self.predict_segment(audio[int(start_t * sr):int((start_t + segment_duration) * sr)], segment_duration)
            probs.append(prob)
            times.append(start_t)

        smoothed = np.convolve(probs, np.ones(3)/3, mode='same')
        ads, current = [], None
        for i, p in enumerate(smoothed):
            if p >= threshold:
                if current is None: current = {'start': times[i], 'end': times[i] + segment_duration, 'conf': p}
                else: current['end'] = times[i] + segment_duration; current['conf'] = max(current['conf'], p)
            elif current:
                if current['end'] - current['start'] >= 5.0: ads.append(current)
                current = None
        
        merged = self._merge_ads(ads)
        if extract_ads: self._save_ads(audio, sr, merged, audio_path)
        return merged

    def _merge_ads(self, ads, gap=5.0):
        if not ads: return []
        sorted_ads = sorted(ads, key=lambda x: x['start'])
        merged = [sorted_ads[0]]
        for n in sorted_ads[1:]:
            if n['start'] - merged[-1]['end'] <= gap:
                merged[-1]['end'] = max(merged[-1]['end'], n['end'])
                merged[-1]['conf'] = max(merged[-1]['conf'], n['conf'])
            else: merged.append(n)
        return merged

    def _save_ads(self, audio, sr, ads, original_path):
        base = Path(original_path).stem
        for i, ad in enumerate(ads, 1):
            sf.write(f"publicités/{base}_pub_{i:03d}_{int(ad['start'])}s.wav", audio[int(ad['start']*sr):int(ad['end']*sr)], sr)

    def save_model(self, path: str):
        joblib.dump({'model': self.model, 'scaler': self.scaler, 'model_type': self.model_type, 'feature_names': self.feature_names, 'training_stats': self.training_stats}, path)

    def load_model(self, path: str):
        data = joblib.load(path)
        self.model, self.scaler, self.model_type = data['model'], data['scaler'], data['model_type']
        self.feature_names, self.training_stats = data['feature_names'], data.get('training_stats', {})
