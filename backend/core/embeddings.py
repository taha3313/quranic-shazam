# backend/app/core/embeddings.py
from speechbrain.pretrained import EncoderClassifier
import numpy as np
import torch

# load once on import
print("Loading speaker embedding model (this may take a bit)...")
model = EncoderClassifier.from_hparams(source="speechbrain/spkrec-ecapa-voxceleb", savedir="tmp_speechbrain_ecapa")
model.device = "cuda" if torch.cuda.is_available() else "cpu"
print("Model loaded. Device:", model.device)

def get_embedding(waveform):
    """
    waveform: torch.Tensor shape [1, samples] (mono)
    returns: 1D numpy array
    """
    # speechbrain expects shape [batch, time] or [channels, time]? encode_batch handles batches.
    # Ensure batch dimension:
    if waveform.dim() == 1:
        waveform = waveform.unsqueeze(0)
    # Move to cpu/cuda as model expects
    if torch.cuda.is_available():
        waveform = waveform.to("cuda")
    with torch.no_grad():
        emb = model.encode_batch(waveform).squeeze().cpu().numpy()
    return emb

def load_reference_embeddings(path="app/data/reciters_embeddings.npy"):
    db = np.load(path, allow_pickle=True).item()
    return db
