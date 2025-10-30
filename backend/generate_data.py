import os
import requests
import io
from tqdm import tqdm
from pydub import AudioSegment
from random import sample
from concurrent.futures import ThreadPoolExecutor, as_completed

# -----------------------------
# CONFIG
# -----------------------------
NUM_SURAHS = 10           # number of random surahs per reciter
CLIP_DURATION_MS = 10000  # 10 seconds
OVERLAP_MS = 5000         # 50% overlap
BASE_URL = "https://cdn.islamic.network/quran/audio/128"
DATASET_DIR = "data/recitations_clips"
MAX_THREADS = 8           # parallel downloads
os.makedirs(DATASET_DIR, exist_ok=True)

# List of known reciters with CDN server names
RECITERS = {
    "alafasy": "ar.alafasy",
    "husary": "ar.husary",
    "minshawi": "ar.minshawi",
}

# -----------------------------
# FUNCTIONS
# -----------------------------
def surah_exists(reciter_code, surah_number):
    """Check if the surah mp3 exists on the CDN"""
    url = f"{BASE_URL}/{reciter_code}/{surah_number}.mp3"
    try:
        resp = requests.head(url, timeout=10)
        return resp.status_code == 200
    except:
        return False

def download_surah(reciter_code, surah_number):
    """Download one surah from CDN"""
    url = f"{BASE_URL}/{reciter_code}/{surah_number}.mp3"
    resp = requests.get(url, stream=True, timeout=15)
    resp.raise_for_status()
    return resp.content

def split_into_clips(audio_bytes, clip_duration_ms=10000, overlap_ms=5000):
    """Split audio bytes into overlapping clips"""
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
    """Save clips to disk"""
    reciter_dir = os.path.join(DATASET_DIR, reciter_name)
    os.makedirs(reciter_dir, exist_ok=True)
    for idx, clip in enumerate(clips, start=1):
        path = os.path.join(reciter_dir, f"{surah_number}_{idx}.wav")
        clip.export(path, format="wav")

def process_surah(reciter_name, reciter_code, surah_number):
    """Download a surah, split into clips, save to disk"""
    try:
        audio_bytes = download_surah(reciter_code, surah_number)
        clips = split_into_clips(audio_bytes, CLIP_DURATION_MS, OVERLAP_MS)
        save_clips(clips, reciter_name, surah_number)
        return f"✅ {len(clips)} clips saved for {reciter_name} surah {surah_number}"
    except Exception as e:
        return f"❌ Failed {reciter_name} surah {surah_number}: {e}"

# -----------------------------
# MAIN
# -----------------------------
if __name__ == "__main__":
    print(f"Found {len(RECITERS)} reciters.\n")

    for reciter_name, reciter_code in RECITERS.items():
        print(f"\n📖 Processing reciter: {reciter_name}")

        # Determine which surahs exist for this reciter
        available_surahs = [s for s in range(1, 115) if surah_exists(reciter_code, s)]
        if not available_surahs:
            print(f"⚠️ No surahs available for {reciter_name}, skipping...")
            continue

        surahs_to_download = sample(available_surahs, min(NUM_SURAHS, len(available_surahs)))

        with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
            futures = [
                executor.submit(process_surah, reciter_name, reciter_code, surah)
                for surah in surahs_to_download
            ]
            for future in tqdm(as_completed(futures), total=len(futures)):
                print(future.result())
