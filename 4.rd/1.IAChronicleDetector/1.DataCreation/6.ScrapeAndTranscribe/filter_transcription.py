#!/usr/bin/env python3
import os
import re
import argparse
from pathlib import Path

def normalize_text(t):
    """Normalize text for better matching: lowercase and remove non-alphanumeric chars."""
    return re.sub(r'[^a-z0-9 ]', '', t.lower()).strip()

def find_subsequence(seq, target, min_match=6):
    """
    Finds the starting index of 'seq' within 'target'.
    'seq' and 'target' are lists of words.
    """
    n = len(seq)
    # Try to match a window of words from the beginning of the snippet
    # We try different lengths from 15 down to min_match
    for k in range(min(n, 15), min_match - 1, -1):
        sub = seq[:k]
        sub_norm = [normalize_text(w) for w in sub]
        for i in range(len(target) - k + 1):
            target_sub_norm = [normalize_text(w) for w in target[i:i+k]]
            if target_sub_norm == sub_norm:
                return i
    return -1

def filter_transcription(full_txt_path, snippets_dir, output_path):
    full_txt_path = Path(full_txt_path)
    snippets_dir = Path(snippets_dir)
    
    if not full_txt_path.exists():
        print(f"❌ Full transcription file not found: {full_txt_path}")
        return

    if not snippets_dir.exists():
        print(f"❌ Snippets directory not found: {snippets_dir}")
        return

    print(f"📖 Reading full transcription: {full_txt_path.name}")
    with open(full_txt_path, 'r', encoding='utf-8') as f:
        full_content = f.read()
    
    full_words = full_content.split()
    if not full_words:
        print("⚠️ Full transcription is empty.")
        return

    # Group start and end snippets by chronicle name
    # We expect files like 'name_start.txt' and 'name_end.txt'
    snippets = {}
    for f in snippets_dir.rglob("*.txt"):
        name = f.stem.replace("_start", "").replace("_end", "")
        if name not in snippets:
            snippets[name] = {"start": None, "end": None}
        
        with open(f, 'r', encoding='utf-8') as fobj:
            content = fobj.read()
            if "_start" in f.stem:
                snippets[name]["start"] = content
            elif "_end" in f.stem:
                snippets[name]["end"] = content

    print(f"🔍 Found {len(snippets)} potential chronicles to match.")
    
    segments = []
    for name, data in snippets.items():
        start_txt = data["start"]
        end_txt = data["end"]
        
        if not start_txt and not end_txt:
            continue
            
        s_idx = -1
        if start_txt:
            s_idx = find_subsequence(start_txt.split(), full_words)
            
        e_idx = -1
        if end_txt:
            # Search for end snippet starting from the start index if found
            search_base = full_words[s_idx:] if s_idx != -1 else full_words
            e_rel_idx = find_subsequence(end_txt.split(), search_base)
            if e_rel_idx != -1:
                # End index is approximately after the matched end snippet
                e_idx = (s_idx if s_idx != -1 else 0) + e_rel_idx + len(end_txt.split()[:10])

        if s_idx != -1 or e_idx != -1:
            # Heuristic: if one bound is missing, use a 10min window (approx 1500 words)
            start_final = s_idx if s_idx != -1 else max(0, e_idx - 1500)
            end_final = e_idx if e_idx != -1 else min(len(full_words), start_final + 1500)
            segments.append((start_final, end_final))
            status = "both bounds" if (s_idx != -1 and e_idx != -1) else ("start only" if s_idx != -1 else "end only")
            print(f"   ✅ Matched: {name} ({status})")
        else:
            print(f"   ⚠️ Could not match: {name}")

    if not segments:
        print("❌ No segments could be matched. Output will not be created.")
        return

    # Sort and merge overlapping segments
    segments.sort()
    merged = []
    if segments:
        curr_start, curr_end = segments[0]
        for next_start, next_end in segments[1:]:
            if next_start <= curr_end:
                curr_end = max(curr_end, next_end)
            else:
                merged.append((curr_start, curr_end))
                curr_start, curr_end = next_start, next_end
        merged.append((curr_start, curr_end))

    # Reconstruct filtered text
    keep_indices = set()
    for start, end in merged:
        # Add 5 words padding for safety
        for i in range(max(0, start - 5), min(len(full_words), end + 5)):
            keep_indices.add(i)
    
    filtered_words = []
    last_idx = -1
    for i in sorted(list(keep_indices)):
        if last_idx != -1 and i > last_idx + 1:
            filtered_words.append("\n\n--- [TRUNCATED] ---\n\n")
        filtered_words.append(full_words[i])
        last_idx = i
        
    with open(output_path, "w", encoding="utf-8") as out:
        out.write(" ".join(filtered_words))
    
    print(f"\n✨ Success! Filtered transcription saved to: {output_path}")

def main():
    parser = argparse.ArgumentParser(description="Filters a full transcription to keep only segments matching chronicle snippets.")
    parser.add_argument("full_text", help="Path to the full transcription .txt file")
    parser.add_argument("snippets_dir", help="Directory containing chronicle snippets (_start.txt and _end.txt)")
    parser.add_argument("-o", "--output", help="Path for the output filtered file (default: input_filtered.txt)")
    
    args = parser.parse_args()
    
    output = args.output
    if not output:
        p = Path(args.full_text)
        output = p.parent / f"{p.stem}_filtered{p.suffix}"
        
    filter_transcription(args.full_text, args.snippets_dir, output)

if __name__ == "__main__":
    main()
