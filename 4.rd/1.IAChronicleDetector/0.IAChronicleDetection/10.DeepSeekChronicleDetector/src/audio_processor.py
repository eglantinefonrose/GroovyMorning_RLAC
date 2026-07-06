import subprocess
import os
import tempfile

def accelerate_audio(input_path, speed=1.0):
    """
    Accélère un fichier audio en utilisant ffmpeg.
    Renvoie le chemin vers le fichier temporaire accéléré.
    """
    if speed == 1.0:
        return input_path, False

    # Création d'un fichier temporaire pour l'audio accéléré
    temp_dir = tempfile.gettempdir()
    output_path = os.path.join(temp_dir, f"accel_{speed}_{os.path.basename(input_path)}")
    
    # Construction du filtre atempo (peut être chaîné si speed > 2.0)
    # ffmpeg supporte atempo de 0.5 à 2.0. Pour plus, on chaîne.
    atempo_filters = []
    temp_speed = speed
    while temp_speed > 2.0:
        atempo_filters.append("atempo=2.0")
        temp_speed /= 2.0
    atempo_filters.append(f"atempo={temp_speed}")
    filter_str = ",".join(atempo_filters)

    command = [
        "ffmpeg", "-y", "-i", input_path,
        "-filter:a", filter_str,
        "-vn", # Pas de vidéo
        output_path
    ]

    print(f"[AUDIO] Accélération du flux (x{speed})...")
    try:
        subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        return output_path, True
    except subprocess.CalledProcessError as e:
        print(f"[ERREUR AUDIO] Échec de l'accélération : {e.stderr.decode()}")
        return input_path, False

def map_timestamp(accelerated_time, speed=1.0):
    """Convertit un timestamp du flux accéléré en timestamp original."""
    return accelerated_time * speed

def format_timestamp(seconds):
    """Formate les secondes en HH:MM:SS."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"
