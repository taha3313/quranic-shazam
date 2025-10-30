# backend/app/core/audio_utils.py
import io
from pydub import AudioSegment
import torchaudio
import torch

TARGET_SR = 16000

def _pydub_to_wav_bytes(audio_bytes: bytes, format_hint="mp3"):
    # Convert mp3/ogg/etc bytes to raw WAV bytes using pydub (ffmpeg required)
    audio = AudioSegment.from_file(io.BytesIO(audio_bytes), format=format_hint)
    # ensure mono
    if audio.channels != 1:
        audio = audio.set_channels(1)
    audio = audio.set_frame_rate(TARGET_SR)
    wav_io = io.BytesIO()
    audio.export(wav_io, format="wav")
    wav_io.seek(0)
    return wav_io

def load_audio_from_upload(upload_bytes: bytes) -> torch.Tensor:
    """
    Convert uploaded audio bytes to a waveform torch.Tensor (1, samples) at 16kHz mono.
    Accepts mp3, wav, ogg, etc. Uses pydub -> torchaudio for robust loading.
    """
    # try detect quick format (if file starts with RIFF it's wav)
    fmt = None
    header = upload_bytes[:20].lower()
    if header.startswith(b'riff'):
        fmt = "wav"
    # fallback to mp3
    wav_io = _pydub_to_wav_bytes(upload_bytes, format_hint=fmt or "mp3")
    waveform, sr = torchaudio.load(wav_io)  # waveform shape: [channels, samples]
    # Ensure mono
    if waveform.size(0) > 1:
        waveform = waveform.mean(dim=0, keepdim=True)
    # resample if needed
    if sr != TARGET_SR:
        waveform = torchaudio.functional.resample(waveform, orig_freq=sr, new_freq=TARGET_SR)
    # Normalize to float32 in [-1,1]
    waveform = waveform.float()
    return waveform
