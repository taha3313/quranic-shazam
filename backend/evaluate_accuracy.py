import os
import io
import requests
import numpy as np
from tqdm import tqdm
from pydub import AudioSegment
from random import sample
from identify_reciter import identify_reciter

# -----------------------------
# CONFIG
# -----------------------------
TEST_RECITER = "husary"
TEST_RECITER_CODE = "ar.husary"

NUM_SURAHS = 5            # number of random surahs to test
CLIP_DURATION_MS = 10000  # 10 seconds
OVERLAP_MS = 5000         # 50% overlap
BASE_URL = "https://cdn.islamic.network/quran/audio/128"

TEMP_DIR = "data/test_clips"
os.makedirs(TEMP_DIR, exist_ok=True)

# -----------------------------
# FUNCTIONS
# -----------------------------
def download_surah(reciter_code, surah_number):
    url = f"{BASE_URL}/{reciter_code}/{surah_number}.mp3"
    response = requests.get(url, stream=True, timeout=15)
    response.raise_for_status()
    return response.content

def split_into_clips(audio_bytes, clip_duration_ms=10000, overlap_ms=5000):
    audio = AudioSegment.from_file(io.BytesIO(audio_bytes), format="mp3")
    clips = []
    start = 0
    while start < len(audio):
        end = start + clip_duration_ms
        clip = audio[start:end]
        if len(clip) > 1000:
            clips.append(clip)
        start += clip_duration_ms - overlap_ms
    return clips

def save_clips(clips, reciter_name, surah_number):
    reciter_dir = os.path.join(TEMP_DIR, reciter_name)
    os.makedirs(reciter_dir, exist_ok=True)
    paths = []
    for idx, clip in enumerate(clips, start=1):
        path = os.path.join(reciter_dir, f"{surah_number}_{idx}.wav")
        clip.export(path, format="wav")
        paths.append(path)
    return paths

# -----------------------------
# MAIN EVALUATION
# -----------------------------
if __name__ == "__main__":
    all_clips = []

    print(f"\n🎧 Fetching random surahs for {TEST_RECITER}...")
    surahs = sample(range(1, 115), NUM_SURAHS)

    for surah_number in surahs:
        try:
            print(f"Downloading surah {surah_number}...")
            audio_bytes = download_surah(TEST_RECITER_CODE, surah_number)
            clips = split_into_clips(audio_bytes, CLIP_DURATION_MS, OVERLAP_MS)
            clip_paths = save_clips(clips, TEST_RECITER, surah_number)
            all_clips.extend(clip_paths)
            print(f"✅ {len(clips)} clips saved for surah {surah_number}")
        except Exception as e:
            print(f"❌ Failed surah {surah_number}: {e}")

    print(f"\n🔍 Evaluating {len(all_clips)} clips...")
    correct = 0

    for clip_path in tqdm(all_clips):
        try:
            matches = identify_reciter(clip_path, top_k=1)
            predicted, score = matches[0]
            if predicted.lower() == TEST_RECITER:
                correct += 1
        except Exception as e:
            print(f"❌ Error processing {clip_path}: {e}")

    accuracy = correct / len(all_clips) if all_clips else 0
    print(f"\n✅ Accuracy for {TEST_RECITER}: {accuracy*100:.2f}% ({correct}/{len(all_clips)})")
