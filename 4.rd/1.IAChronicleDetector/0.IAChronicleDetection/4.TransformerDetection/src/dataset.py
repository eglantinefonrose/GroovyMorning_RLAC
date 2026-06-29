import torch
from torch.utils.data import Dataset
from typing import List, Dict, Optional
import os
from .utils import load_transcription, load_timecodes, label_segments
from tqdm import tqdm

class ChronicleDataset(Dataset):
    def __init__(self, srt_files: List[str], tc_files: List[str], tokenizer, max_length: int = 256, window_size: int = 1):
        self.samples = []
        
        tc_map = {}
        for tc_file in tc_files:
            # On récupère le début du nom de fichier (avant les suffixes de type _transcription ou _timecode)
            base = os.path.basename(tc_file).split('_')[0]
            tc_map[base] = tc_file
            
        print("Pré-traitement des fichiers et tokenization...")
        for srt_file in tqdm(srt_files, desc="Chargement des fichiers"):
            base = os.path.basename(srt_file).split('_')[0]
            if base in tc_map:
                segments = load_transcription(srt_file)
                tc_list = load_timecodes(tc_map[base])
                labels = label_segments(segments, tc_list)
                
                texts = []
                for i in range(len(segments)):
                    start_idx = max(0, i - window_size)
                    end_idx = min(len(segments), i + window_size + 1)
                    context_texts = [segments[j]['text'] for j in range(start_idx, end_idx)]
                    texts.append(" [SEP] ".join(context_texts))
                
                # Tokenization par batch pour aller plus vite
                encodings = tokenizer(
                    texts,
                    add_special_tokens=True,
                    max_length=max_length,
                    padding='max_length',
                    truncation=True,
                    return_tensors='pt'
                )
                
                for i in range(len(texts)):
                    self.samples.append({
                        'input_ids': encodings['input_ids'][i],
                        'attention_mask': encodings['attention_mask'][i],
                        'label': labels[i]
                    })
        print(f"Dataset créé avec {len(self.samples)} segments.")

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        sample = self.samples[idx]
        return {
            'input_ids': sample['input_ids'],
            'attention_mask': sample['attention_mask'],
            'labels': torch.tensor(sample['label'], dtype=torch.long)
        }
