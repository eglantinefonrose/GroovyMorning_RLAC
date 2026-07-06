import os
import sys
import json
import numpy as np
import soundfile as sf
import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler

# Ensure src can be imported
sys.path.append(os.path.join(os.getcwd(), 'src'))
from logic import FeatureExtractor, ChronicleClassifier

def run_test():
    print("=== Démarrage des Tests pour l'analyse en live ===")
    
    # 1. Générer un fichier audio de synthèse (15 secondes à 22050 Hz)
    sr = 22050
    duration = 15.0
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    # Mélange de fréquences pour que l'extracteur de features ne plante pas
    audio = np.sin(2 * np.pi * 440 * t) * 0.3 + np.sin(2 * np.pi * 880 * t) * 0.2
    mock_audio_path = "mock_audio.wav"
    sf.write(mock_audio_path, audio, sr)
    print(f"✅ Fichier audio de synthèse créé : {mock_audio_path} ({duration}s)")

    # 2. Créer et enregistrer un modèle minimaliste / fictif (mock)
    mock_model_path = "models/mock_model.pkl"
    os.makedirs("models", exist_ok=True)
    
    # Notre extracteur génère 43 features. Générons 10 échantillons bidon.
    X_dummy = np.random.rand(10, 43)
    y_dummy = np.array([0, 1, 0, 1, 0, 1, 0, 1, 0, 1]) # Classes binaires
    
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_dummy)
    
    model = RandomForestClassifier(n_estimators=5, max_depth=3, random_state=42)
    model.fit(X_scaled, y_dummy)
    
    joblib.dump({
        'model': model,
        'scaler': scaler,
        'model_type': 'random_forest',
        'feature_names': FeatureExtractor().get_feature_names(),
        'training_stats': {'test': True}
    }, mock_model_path)
    print(f"✅ Modèle fictif sauvegardé dans : {mock_model_path}")

    # 3. Exécuter l'évaluation de qualité avec simulation live
    # On importe directement les fonctions pour un test plus précis et robuste
    from evaluate_quality import simulate_live_inference
    
    json_output_path = "test_live_detections.json"
    if os.path.exists(json_output_path):
        os.remove(json_output_path)

    # On utilise un seuil très bas (0.1) pour forcer une détection sur notre audio de synthèse
    print("🚀 Lancement de la simulation live...")
    segments = simulate_live_inference(
        model_path=mock_model_path,
        audio_path=mock_audio_path,
        threshold=0.1,
        segment_duration=3.0,
        step=2.0,
        acceleration=0.0, # Pas d'attente réelle pour aller très vite
        transcribe=False,
        json_output=json_output_path
    )

    print(f"✅ Simulation terminée. Segments retournés : {len(segments)}")

    # 4. Vérifier la création du fichier JSON et valider son format
    assert os.path.exists(json_output_path), "Erreur : Le fichier JSON de détection n'a pas été créé !"
    print(f"✅ Fichier JSON de détection bien généré : {json_output_path}")

    with open(json_output_path, 'r', encoding='utf-8') as f:
        detections = json.load(f)

    print(f"🔍 Contenu du fichier JSON : {json.dumps(detections, indent=2)}")

    assert isinstance(detections, list), "Erreur : Les détections devraient être une liste !"
    assert len(detections) > 0, "Erreur : Aucune chronique n'a été détectée !"

    for idx, det in enumerate(detections):
        print(f"👉 Validation du segment #{idx+1} :")
        for key in ["label", "start", "end", "detected_at", "confidence"]:
            assert key in det, f"Erreur : Clé '{key}' manquante dans la détection !"
            print(f"   - Clé '{key}' présente avec la valeur : {det[key]}")
        
        assert isinstance(det["label"], str), "Erreur : 'label' doit être une chaîne !"
        assert isinstance(det["start"], (int, float)), "Erreur : 'start' doit être un nombre !"
        assert isinstance(det["end"], (int, float)), "Erreur : 'end' doit être un nombre !"
        assert isinstance(det["detected_at"], (int, float)), "Erreur : 'detected_at' doit être un nombre !"
        assert isinstance(det["confidence"], (int, float)), "Erreur : 'confidence' doit être un nombre !"
        
        # Vérification logique des valeurs de temps
        assert det["end"] > det["start"], f"Erreur : Le temps de fin ({det['end']}) doit être après le début ({det['start']}) !"
        assert det["detected_at"] >= det["end"] or np.isclose(det["detected_at"], det["end"], atol=1.0), (
            f"Erreur : Le temps de détection ({det['detected_at']}) doit être cohérent avec la fin ({det['end']}) !"
        )

    print("\n🎉 TOUS LES TESTS SONT PASSÉS AVEC SUCCÈS ! LA DÉTECTION LIVE ET L'ÉCRITURE JSON FONCTIONNENT PARFAITEMENT ! 🎉")

    # 5. Nettoyage des fichiers générés pour le test
    if os.path.exists(mock_audio_path):
        os.remove(mock_audio_path)
    if os.path.exists(mock_model_path):
        os.remove(mock_model_path)
    if os.path.exists(json_output_path):
        os.remove(json_output_path)
    print("🧹 Nettoyage des fichiers temporaires de test effectué.")

if __name__ == "__main__":
    run_test()
