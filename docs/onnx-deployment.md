# Lightweight inference migration

The serving path uses NumPy/SciPy + soundfile/FFmpeg for decoding, ONNX Runtime
for ECAPA speaker embeddings, and faster-whisper/CTranslate2 for Quranic ASR.
PyTorch, torchaudio, and SpeechBrain are export-only dependencies.

## Reproduce the model

From `backend/`:

```
uv sync --group export
uv run --group export python -m scripts.export_reciter_onnx
```

The model is generated at `data/models/reciter.onnx` (ignored by Git), with
metadata alongside it. Include the generated ONNX file when building the backend
Docker image. Keep `reciters_embeddings.npy` unchanged: the exported float32
model produces vectors in the same embedding space. No quantization is enabled
without a separate accuracy comparison.

The graph includes the original mel filterbank, sentence mean normalization,
and ECAPA network. The STFT is implemented outside the graph with the original
400-point periodic Hamming window, constant centered padding, 160-sample hop,
and power spectrum. Audio is mono float32 at 16 kHz; sub-second clips retain the
existing tiny-noise padding policy. NumPy implements the same six-lobe Hann-windowed sinc resampling filter as
torchaudio for standard sample rates. Unusual coprime rates use SciPy's
polyphase resampler to avoid allocating excessive filter matrices.

## Serving

```
uv sync --no-dev --no-group export
OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 uv run --no-dev --no-group export uvicorn app.main:app --host 0.0.0.0 --port 8000
```

`QD_RECITER_ONNX_PATH` selects an explicit artifact. Missing models produce a
503 response with an export instruction. The model loads lazily unless
`QD_WARM_MODEL=true`. `QD_INFERENCE_THREADS=2` bounds both ONNX Runtime and
faster-whisper CPU pools. Reciter and verse inference share one execution slot,
including WebSocket reciter calls, to bound concurrent activation memory. Use one server worker for a small machine: each process
would otherwise load its own models. Model downloads for ASR still require
outbound network access on first use.

## Validation gate

Compare vectors, all database scores, top-1/top-3 ordering, confidence decisions,
latency, and fresh-process peak RSS against the original SpeechBrain model on
real clips across all 20 reciters and several input lengths/formats. Existing
local dataset clips establish conversion parity, not held-out product accuracy.
Measure the combined reciter + ASR process as well as reciter-only memory before
choosing a hosting tier. A smaller package does not prove 512 MB will suffice.

## Measured local results

The checked report is in `backend/data/eval_reports/onnx-parity/summary.json`.
The 63 probes cover all 20 reciters at 1, 5, and 10 seconds, plus three
30-second inputs constructed by repeating real audio. The reference uses the
original torchaudio resampler; the candidate uses NumPy. Both use two inference
threads. Timing reflects this shared local machine, not a hosting SLA.

| Measurement | Original SpeechBrain | ONNX Runtime |
| --- | ---: | ---: |
| Fresh-process reciter peak RSS | 1,008 MiB | 622 MiB |
| Median warm embedding time | 1.84 s | 0.80 s |
| Top-1 / top-3 order / confidence decisions preserved | Reference | 63 / 63 each |

Minimum vector cosine similarity was 0.99999999990; the largest database score
change was 0.00000243. This is conversion parity on the existing dataset, not a
new held-out accuracy benchmark. The original embedding database is unchanged.

A separate fresh process sent real API requests for 10- and 30-second reciter
recordings and two ayah recordings, using both models, with peak RSS of 626 MiB.
A real recitation transcoded to browser-style WebM/Opus also returned the
expected reciter through the API. Neither process imported torch, torchaudio,
or speechbrain. These observations rule out a 512 MB hosting budget for the
full app; 1 GB is a candidate for further load testing, not a certified limit.
The ASR examples preserve the existing uncertainty behavior; HTTP 200 is not a
claim that every ayah sample has a confident transcription.

A container smoke test with a hard 1 GiB memory limit and two CPUs processed
a 30-second reciter recording and a 20-second ayah recording. Peak cgroup
memory was 630.6 MiB; there were no memory-limit or OOM events. This check used
the runtime base image with the application and clean environment mounted
read-only. It is a bounded smoke test, not a concurrent production load test.
See `container-limit.json` for responses and counters.

The final self-contained image also passed the same 1 GiB / two-CPU smoke test
without mounting application code or a development environment. Only the
read-only ASR model download cache was mounted. Peak container memory was
618.2 MiB with zero OOM events. The runtime
has no torch, torchaudio, or speechbrain packages available to import. See
`packaged-container.json` for the exact image ID and responses. The model
download cache avoids measuring network download time in this smoke test.

For the opt-in allocator/model-cache profile and hard 512 MiB validation, see
[memory-512.md](memory-512.md). Docker defaults to that profile; direct Python
execution retains the previous caching behavior unless QD_LOW_MEMORY is set.
