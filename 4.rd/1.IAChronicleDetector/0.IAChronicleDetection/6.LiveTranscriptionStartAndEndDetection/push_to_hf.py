import os
from transformers import CamembertForSequenceClassification, CamembertTokenizer
from huggingface_hub import HfApi, add_collection_item

# --- Configuration ---
MODEL_PATH = "./camembert_chronicle_start"
HF_REPO_NAME = "eglantinefonrose/camembert-chronicle-start-detection"
HF_COLLECTION_SLUG = "eglantinefonrose/rlac-radio-live-a-la-carte-69dbc4adbaf921268f565853" # Basé sur train_camembert.py

def push_to_hub():
    print(f"Chargement du modèle et du tokenizer depuis {MODEL_PATH}...")
    
    # Chargement
    model = CamembertForSequenceClassification.from_pretrained(MODEL_PATH)
    tokenizer = CamembertTokenizer.from_pretrained(MODEL_PATH)
    
    print(f"Poussée du modèle vers {HF_REPO_NAME}...")
    
    # Publication du modèle et du tokenizer
    # Note: Assurez-vous d'être connecté avec `huggingface-cli login` ou d'avoir HF_TOKEN dans l'env
    model.push_to_hub(HF_REPO_NAME)
    tokenizer.push_to_hub(HF_REPO_NAME)
    
    print("Modèle et tokenizer poussés avec succès !")
    
    # Ajout à la collection
    try:
        print(f"Ajout du modèle à la collection : {HF_COLLECTION_SLUG}")
        add_collection_item(
            collection_slug=HF_COLLECTION_SLUG,
            item_id=HF_REPO_NAME,
            item_type="model",
            exists_ok=True
        )
        print("Modèle ajouté à la collection avec succès !")
    except Exception as e:
        print(f"Erreur lors de l'ajout à la collection : {e}")
        print("Note : Vérifiez que le slug de la collection est correct et que vous avez les droits.")

if __name__ == "__main__":
    push_to_hub()
