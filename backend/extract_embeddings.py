import os
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
import torch
import numpy as np
import torchaudio
from speechbrain.pretrained import EncoderClassifier
from tqdm import tqdm
import io
import subprocess

# -----------------------------
# CONFIG
# -----------------------------
DATASET_DIR = "data/recitations_clips"
OUTPUT_PATH = "data/reciters_embeddings.npy"

# -----------------------------
# LOAD PRETRAINED SPEAKER EMBEDDING MODEL
# -----------------------------
device = "cuda" if torch.cuda.is_available() else "cpu"
model = EncoderClassifier.from_hparams(
    source="speechbrain/spkrec-ecapa-voxceleb",
    run_opts={"device": device}
)

# -----------------------------
# HELPER FUNCTIONS
# -----------------------------
def load_audio(file_path, target_sr=16000):
    waveform, sr = torchaudio.load(file_path)
    if waveform.shape[0] > 1:  # convert to mono
        waveform = torch.mean(waveform, dim=0, keepdim=True)
    if sr != target_sr:
        waveform = torchaudio.functional.resample(waveform, sr, target_sr)
    return waveform

def compute_embedding(file_path):
    waveform = load_audio(file_path)
    embedding = model.encode_batch(waveform).squeeze().detach().cpu().numpy()
    return embedding


def compute_embedding_live(file_path):
    # Load audio
    waveform, sr = torchaudio.load(file_path)

    # Convert to mono if needed
    if waveform.shape[0] > 1:
        waveform = torch.mean(waveform, dim=0, keepdim=True)

    # Resample to 16 kHz (SpeechBrain models expect 16k)
    if sr != 16000:
        resampler = torchaudio.transforms.Resample(sr, 16000)
        waveform = resampler(waveform)

    # Prevent tiny/silent chunks from breaking embeddings
    if waveform.numel() < 16000:      # less than 1 second
        # Pad with small random noise to avoid crashes
        pad_len = 16000 - waveform.numel()
        pad = 0.0001 * torch.randn(1, pad_len)
        waveform = torch.cat([waveform, pad], dim=1)

    # Compute embedding
    emb = model.encode_batch(waveform).squeeze().detach().cpu().numpy()

    return emb



def extract_embedding(waveform, sr):
    """Compute embedding from waveform tensor."""
    # Example:
    # emb = model.encode_batch(waveform).squeeze().detach().cpu().numpy()
    # return emb

    # ---- REMOVE THIS WHEN YOU ADD YOUR MODEL ----
    # placeholder dummy embedding (128 dims)
    return np.random.rand(128)
    # ------------------------------------------------


# ----------------------------------------------------
# Helper: decode webm/opus chunks using FFmpeg
# ----------------------------------------------------
def decode_opus_webm(audio_bytes):
    """Decode browser MediaRecorder WebM/Opus audio into PCM."""
    process = subprocess.Popen(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel", "error",
            "-f", "webm",
            "-i", "pipe:0",
            "-ac", "1",
            "-ar", "16000",
            "-f", "wav",
            "pipe:1",
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    try:
        out, err = process.communicate(input=audio_bytes, timeout=2)
    except subprocess.TimeoutExpired:
        process.kill()
        return None

    if not out:
        return None

    try:
        waveform, sr = torchaudio.load(io.BytesIO(out))
        return waveform, sr
    except:
        return None



def compute_embedding_chunk(chunk_bytes):
    decoded = decode_opus_webm(chunk_bytes)
    if decoded is None:
        return None

    waveform, sr = decoded

    # Avoid too-short chunks (<0.2 s)
    if waveform.shape[1] < 2000:
        return None

    return extract_embedding(waveform, sr)
# -----------------------------
# MAIN LOOP (RUN ONLY WHEN EXECUTED DIRECTLY)
# -----------------------------
if __name__ == "__main__":
    reciters_embeddings = {}

    for reciter_name in os.listdir(DATASET_DIR):
        reciter_dir = os.path.join(DATASET_DIR, reciter_name)
        if not os.path.isdir(reciter_dir):
            continue

        print(f"\nProcessing reciter: {reciter_name}")
        embeddings_list = []

        for audio_file in tqdm(os.listdir(reciter_dir)):
            file_path = os.path.join(reciter_dir, audio_file)
            try:
                emb = compute_embedding(file_path)
                embeddings_list.append(emb)
            except Exception as e:
                print(f"❌ Failed to process {audio_file}: {e}")

        if embeddings_list:
            reciters_embeddings[reciter_name] = np.mean(embeddings_list, axis=0)
            print(f"✅ {len(embeddings_list)} embeddings processed for {reciter_name}")

    np.save(OUTPUT_PATH, reciters_embeddings)
    print(f"\n✅ All reciter embeddings saved to {OUTPUT_PATH}")
