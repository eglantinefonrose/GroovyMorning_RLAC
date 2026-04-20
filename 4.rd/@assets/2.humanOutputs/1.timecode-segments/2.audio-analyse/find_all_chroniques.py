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

def find_audio_match(y_needle, y_haystack_norm, sr):
    """
    Trouve la meilleure correspondance de y_needle dans y_haystack_norm.
    Utilise la corrélation croisée via FFT pour l'alignement global,
    puis affine les bornes en vérifiant la similarité locale.
    """
    # Normalisation du needle
    y_needle_norm = (y_needle - np.mean(y_needle)) / (np.std(y_needle) + 1e-9)
    
    # 1. Alignement global via corrélation FFT
    correlation = signal.fftconvolve(y_haystack_norm, y_needle_norm[::-1], mode='full')
    peak_index = np.argmax(correlation)
    
    # Offset : index dans le haystack où le début du needle est aligné
    offset = peak_index - len(y_needle_norm) + 1
    
    # 2. Affinement des bornes (recherche de la portion réellement présente)
    # On découpe le needle en blocs pour vérifier la corrélation locale
    win_size = int(sr * 0.2)  # Fenêtres de 200ms
    if win_size == 0: win_size = 1
    
    num_wins = len(y_needle) // win_size
    similarities = []
    
    for i in range(num_wins):
        start_n = i * win_size
        end_n = start_n + win_size
        
        start_h = offset + start_n
        end_h = start_h + win_size
        
        # Si le bloc est hors des limites du haystack, similarity = 0
        if start_h < 0 or end_h > len(y_haystack_norm):
            similarities.append(0)
            continue
            
        # Calcul de la corrélation locale sur ce bloc
        chunk_n = y_needle_norm[start_n:end_n]
        chunk_h = y_haystack_norm[start_h:end_h]
        
        # Corrélation de Pearson simplifiée (les chunks sont déjà +/- centrés)
        corr = np.sum(chunk_n * chunk_h) / (np.sqrt(np.sum(chunk_n**2) * np.sum(chunk_h**2)) + 1e-9)
        similarities.append(corr)
        
    similarities = np.array(similarities)
    
    # On cherche le bloc contigu le plus large au-dessus d'un seuil
    # Seuil de corrélation locale (0.3 est assez bas mais robuste aux bruits/différences mineures)
    threshold = 0.25
    matches = similarities > threshold
    
    if not np.any(matches):
        # Si aucun bloc ne dépasse le seuil, on renvoie le résultat de l'alignement global
        # mais recadré (comportement par défaut précédent)
        return offset / sr, (offset + len(y_needle)) / sr

    # Trouver le premier et le dernier bloc qui match
    # Pour être robuste, on peut chercher la "plus grande zone" de blocs True
    # Ici on prend simplement du premier au dernier pour couvrir la "portion"
    first_match_idx = np.where(matches)[0][0]
    last_match_idx = np.where(matches)[0][-1]
    
    # Calcul des nouveaux timecodes
    start_time = (offset + first_match_idx * win_size) / sr
    end_time = (offset + (last_match_idx + 1) * win_size) / sr
    
    return start_time, end_time

def main():
    if len(sys.argv) < 3:
        print("\nUsage:")
        print("python find_all_chroniques.py ../../../0.media/audio/2.rtl-matin/13-04-2026/chroniques ../../../0.media/audio/2.rtl-matin/13-04-2026/13-04-2026.mp3")
        sys.exit(1)

    chroniques_dir = sys.argv[1]
    haystack_path = sys.argv[2]

    if not os.path.isdir(chroniques_dir):
        print(f"Erreur : '{chroniques_dir}' n'est pas un dossier.")
        sys.exit(1)
    if not os.path.exists(haystack_path):
        print(f"Erreur : '{haystack_path}' est introuvable.")
        sys.exit(1)

    # Taux d'échantillonnage réduit pour accélérer le calcul (16kHz est suffisant pour des signatures audio)
    sr = 16000 
    
    print(f"[*] Chargement de l'audio complet (haystack) : {os.path.basename(haystack_path)}")
    try:
        # On charge tout en mémoire pour éviter de relire le gros fichier pour chaque chronique
        y_haystack, _ = librosa.load(haystack_path, sr=sr, mono=True)
    except Exception as e:
        print(f"Erreur lors du chargement du fichier complet : {e}")
        sys.exit(1)

    print("[*] Normalisation de l'audio complet...")
    y_haystack_norm = (y_haystack - np.mean(y_haystack)) / (np.std(y_haystack) + 1e-9)
    haystack_duration = len(y_haystack) / sr

    results = []
    audio_extensions = ('.mp3', '.m4a', '.wav', '.flac', '.ogg')
    
    # Liste et tri des fichiers dans le dossier des chroniques
    files_to_process = sorted([f for f in os.listdir(chroniques_dir) if f.lower().endswith(audio_extensions)])
    
    if not files_to_process:
        print(f"Aucun fichier audio trouvé dans {chroniques_dir}")
        sys.exit(0)

    print(f"[*] Début de l'analyse de {len(files_to_process)} fichiers...")

    for filename in files_to_process:
        needle_path = os.path.join(chroniques_dir, filename)
        print(f"    - Analyse de : {filename}")
        
        try:
            # Chargement de la chronique
            y_needle, _ = librosa.load(needle_path, sr=sr, mono=True)
            
            # Recherche de la correspondance
            start, end = find_audio_match(y_needle, y_haystack_norm, sr)
            
            # On recadre les timecodes s'ils sortent des limites du haystack (cas de portion partielle)
            actual_start = max(0, start)
            actual_end = min(haystack_duration, end)
            
            results.append({
                'start': actual_start,
                'end': actual_end,
                'name': filename
            })
            print(f"      => Trouvé : {format_time(actual_start)} - {format_time(actual_end)}")
            
        except Exception as e:
            print(f"      [!] Erreur sur {filename} : {e}")

    # Trier les résultats par temps de début pour plus de clarté
    results.sort(key=lambda x: x['start'])

    # Préparation du fichier de sortie
    haystack_basename = os.path.splitext(os.path.basename(haystack_path))[0]
    output_filename = f"timecode_chroniques_{haystack_basename}.txt"
    # On écrit le fichier dans le même dossier que le script
    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), output_filename)

    print(f"[*] Écriture des résultats dans {output_filename}...")
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            for res in results:
                # Syntaxe demandée : [timecode début] - [timecode fin] Nom du fichier
                line = f"[{format_time(res['start'])}] - [{format_time(res['end'])}] {res['name']}"
                f.write(line + "\n")
        print(f"[*] Terminé avec succès. Fichier généré : {output_path}")
    except Exception as e:
        print(f"Erreur lors de l'écriture du fichier : {e}")

if __name__ == "__main__":
    main()
