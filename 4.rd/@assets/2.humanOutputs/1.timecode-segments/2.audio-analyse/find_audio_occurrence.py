import sys
import os
import numpy as np
import librosa
from scipy import signal
import datetime

def format_time(seconds):
    """Convertit des secondes en format HH:MM:SS.mmm"""
    td = datetime.timedelta(seconds=seconds)
    total_seconds = td.total_seconds()
    hours = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)
    secs = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"

def find_audio_match(needle_path, haystack_path):
    # On utilise un taux d'échantillonnage réduit pour accélérer le calcul
    # tout en gardant assez de détails pour une signature unique
    sr = 16000 
    
    print(f"[*] Chargement de l'extrait (needle) : {os.path.basename(needle_path)}")
    y_needle, _ = librosa.load(needle_path, sr=sr, mono=True)
    
    print(f"[*] Chargement de l'audio complet (haystack) : {os.path.basename(haystack_path)}")
    y_haystack, _ = librosa.load(haystack_path, sr=sr, mono=True)

    # Normalisation pour que la recherche soit indépendante du volume
    y_needle = (y_needle - np.mean(y_needle)) / (np.std(y_needle) + 1e-9)
    y_haystack = (y_haystack - np.mean(y_haystack)) / (np.std(y_haystack) + 1e-9)

    print("[*] Recherche de la correspondance (Analyse FFT)...")
    
    # La corrélation croisée via FFT est extrêmement rapide même sur de longs fichiers
    # On inverse l'extrait (y_needle[::-1]) pour transformer la convolution en corrélation
    correlation = signal.fftconvolve(y_haystack, y_needle[::-1], mode='valid')
    
    # L'index du pic maximum dans le résultat de la corrélation
    peak_index = np.argmax(correlation)
    
    start_time = peak_index / sr
    duration = len(y_needle) / sr
    end_time = start_time + duration
    
    return start_time, end_time

def main():
    if len(sys.argv) < 3:
        print("\nUsage:")
        print("  python find_audio_occurrence.py <extrait.mp3> <audio_complet.mp3>")
        print("\nExemple:")
        print("  python find_audio_occurrence.py ../../../0.media/audio/2.rtl-matin/13-04-2026/chroniques/angle-eco.mp3 ../../../0.media/audio/2.rtl-matin/13-04-2026/13-04-2026.mp3\n")
        sys.exit(1)

    needle = sys.argv[1]
    haystack = sys.argv[2]

    if not os.path.exists(needle) or not os.path.exists(haystack):
        print("Erreur : L'un des fichiers audio est introuvable.")
        sys.exit(1)

    try:
        start, end = find_audio_match(needle, haystack)
        
        print("\n" + "="*40)
        print("   CORRESPONDANCE TROUVÉE")
        print("="*40)
        print(f"Début : {format_time(start)}")
        print(f"Fin   : {format_time(end)}")
        print(f"Durée : {end - start:.3f} secondes")
        print("="*40 + "\n")
        
    except Exception as e:
        print(f"Erreur lors de l'analyse : {e}")

if __name__ == "__main__":
    main()
