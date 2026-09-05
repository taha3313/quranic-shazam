# Quranic Shazam — Architecture & Code-Quality Audit (read-only)

Scope: entire repository as of commit `cd2889d`. No files were modified.
Verdict up front: the layering (api → services → core), configuration, and offline pipeline design are sound. The system has **two critical defects in the serving path** (blocking inference on the event loop; broken webm live streaming) and a cluster of high-priority robustness gaps around untrusted input. The ML baseline (97.31%) and its pipeline are the strongest part of the project and should not be restructured.

---

## CRITICAL

### C1. Blocking CPU inference runs on the asyncio event loop
- `app/api/routes/reciter.py:19-44` — the endpoint is `async def` and calls `reciter_service.identify_upload_bytes(...)` **directly**. FastAPI runs `async def` handlers on the event loop, so every identification (audio decode + ffmpeg subprocess + ~1 s ECAPA forward pass) **blocks the entire server**: no other HTTP request, no WebSocket message, not even `/health` is served during that time. Two concurrent users ⇒ serialized, and live-mic sessions stall upload identification.
- `app/api/routes/live_reciter.py:44-60` — same problem inside the WS loop: `decode_upload_bytes` (which may run a **blocking `subprocess.run` ffmpeg**, `app/core/audio.py:64-84`) and `identify_waveform` both execute on the loop.
- Also: the model itself is loaded lazily inside this path (`app/core/embeddings.py:26-44`), so the *first* request also blocks the loop for the multi-second model load.
- Recommended fix direction (analysis, not implemented): wrap the blocking section in `anyio.to_thread.run_sync` (or make the endpoint plain `def` so FastAPI's threadpool handles it) **plus** a `threading.Semaphore(1..2)` around inference. On CPU, ECAPA inference is not effectively parallel across requests (torch already uses all cores), so a dedicated worker/queue adds complexity without throughput benefit at this scale; a bounded-threadpool design is the right first step. A separate inference process is only warranted if profiling shows GIL contention between decode and inference.

### C2. Live WebSocket mode cannot work with the frontend's webm/opus stream
- `frontend/src/hooks/useLiveReciter.ts` starts `MediaRecorder(mimeType='audio/webm;codecs=opus')` with `recorder.start(300)` and sends **every 300 ms chunk** as a binary WS message.
- A webm stream's headers live only in the **first** chunk; chunks 2..N are continuation clusters that are not independently decodable. The server decodes **each chunk in isolation** (`live_reciter.py:45`), so chunk 1 decodes to ~0.3 s of audio and every subsequent chunk fails decoding → server replies `{"error": ...}` to each, `buffered_sec` never reaches the 5 s window, and identification never fires. Live mode is effectively dead code as wired.
- Fix direction: either (a) buffer raw bytes server-side and decode the accumulated buffer cumulatively (decode cost grows per window), or (b) have the client decode via `AudioContext`/`decodeAudioData` and stream **raw PCM or wav frames**, or (c) use MediaRecorder `timeslice` with a container that produces self-contained segments (e.g. `audio/mp4` fragments in some browsers) — (b) is the most portable.

---

## HIGH

### H1. Upload size limit enforced after the whole body is in memory
`reciter.py:27-34`: `data = await file.read()` happens **before** the size check. A malicious client can stream a multi-GB body; the server buffers all of it in RAM before rejecting. Use `Content-Length` pre-check + streamed reads with an accumulator cap.

### H2. No bound on audio **duration**
25 MB of mp3 can be ~4 hours of audio. `decode_upload_bytes` + ECAPA on hours of audio is minutes of CPU per request — a trivial DoS even with the size cap. Identification quality saturates well before 30 s; trim input to a configurable max (e.g. 30 s) after decode.

### H3. Inference concurrency is unbounded (once C1 is fixed naively)
Moving to a threadpool without a semaphore lets N concurrent requests each try to use all cores via torch → thrashing and latency blowup. Pair the C1 fix with `torch.set_num_threads` sizing and an inference semaphore; document expected concurrency = 1–2 on a laptop-class CPU.

### H4. Model warm-up missing at startup
`app/main.py:20-29` warms only the embeddings DB, deliberately not the model. Combined with lazy loading, first real request pays model load (or surfaces a HF-hub network fetch failure as a user-facing 500). Recommended: optional `QD_WARM_MODEL=1` that loads the classifier in lifespan (in a thread), failing startup with a clear error when enabled.

### H5. Test coverage does not protect the serving path
`backend/tests/` has 3 smoke tests (cosine, ranking, `/health`). Zero coverage for: decode paths (`soundfile`/ffmpeg fallback), upload endpoint error contract (empty file, oversized, garbage bytes), WS protocol (error frames, disconnect, max-duration), profile DB loading. Any refactor of C1/C2 would currently land without a safety net — see "Tests needed" below.

### H6. Dependency inversion: `app.core` imports from `scripts`
`app/core/similarity.py` imports `scripts.sources.RECITERS` **inside the request path** to attach display names. `scripts/` is a CLI/pipeline package (and is excluded from some deployment contexts conceptually); the app should own its reciter metadata (load `data/reciters.json` at startup, or move `ReciterSpec` into `app`). This also silently degrades to raw keys if the import ever fails at runtime.

---

## MEDIUM / LOW

- **M1.** `similarity.rank_reciters` imports inside the function per call (`app/core/similarity.py:33`) — move to module level once H6 is fixed.
- **M2.** Health endpoint reads the private `emb_module._classifier` (`app/main.py:54`) — expose a `is_loaded()` helper.
- **M3.** WS "Not sure" frame (`live_reciter.py:82`) doesn't match `ReciterMatch` shape (no `display`), and error frames are an undocumented second schema — formalize the WS message contract in `schemas.py` and in the frontend types.
- **M4.** Double resample: `decode_upload_bytes` returns 16 kHz, then `embedding_from_waveform` resamples again (no-op, but wasteful path); also `identify_waveform`'s `sr` parameter is misleading since decode already normalized.
- **M5.** No structured logging / request IDs / metrics; `logger.exception` on 500s is good, but there is no way to count or time inferences in production.
- **M6.** Docker: container runs as root; healthcheck shells out to `python -` (curl is already installed); no resource limits (`cpus`, `mem_limit`) — important because inference is CPU-heavy; single uvicorn worker is correct for CPU-bound work, document why.
- **M7.** `pretrained_models/` checkpoints (~80 MB) are committed to git — bloats clones; prefer release artifacts or HF cache volume (already mounted in compose).
- **M8.** Data pipeline reproducibility: source URLs are scraped at run time (sites rot — already experienced with the abkar archive); no manifest of downloaded files + checksums; `evaluate.py` re-downloads eval audio every run (honest but slow, and the numbers depend on the remote archive staying identical). Consider a frozen eval-set manifest with hashes.
- **M9.** `data/reciters.json` is dead weight in the backend (nothing imports it) — either use it for display names (fixes H6) or delete it.
- **M10.** Security posture of uploaded audio is otherwise reasonable (no shell invocation with user data — ffmpeg args are fixed; decode timeouts exist), but ffmpeg is called with `-i pipe:0` on untrusted bytes: keep ffmpeg patched and prefer the soundfile path where possible (already first).
- **L1.** CORS: `allow_methods=["*"]` + `allow_credentials=True` is broader than needed (only POST + WS used).
- **L2.** `evaluate.py` uses no seed for its (deterministic) slicing — fine today, but document determinism assumptions when adding sampling later.

---

## Already well designed — do NOT change

1. **Layering**: routes (thin) → services (state) → core (pure-ish helpers). Keep this shape.
2. **Lazy model + thread-safe singleton** (`embeddings.py`) — correct pattern; just warm it at startup (H4) rather than restructuring it.
3. **Profile DB as a tiny npy dict loaded once with lock** (`reciter_service.py`) — right-sized; no need for a vector DB with 20 entries.
4. **The offline pipeline** (`scripts/sources.py` with URL-template scraping + caching, resumable `generate_data.py`, round-robin profile sampling, disjoint eval surahs) — this is the strongest engineering in the repo; preserve it.
5. **Cosine ranking in numpy** — 20 profiles, microseconds; any ANN/index would be fashion, not engineering.
6. **uv + lockfile + Docker layer caching + Makefile UX** — reproducible and pleasant; keep.
7. **Error→HTTP mapping** in the upload route (400/413/503/500 with logged cause) — correct shape.

## Recommended target architecture (serving path only)

```
Upload route (async)          Live WS route (async)
   │ stream-read + cap            │ accumulate raw bytes / PCM frames
   ▼                              ▼
anyio.to_thread.run_sync(identify_upload_bytes, data)
        │
        ▼
Semaphore(1..2) ──► torch (set_num_threads) ──► ECAPA ──► cosine rank
        │
        ▼
JSON {matches:[{reciter, display, score}]}
```
- Reciter display names: loaded once at startup from `data/reciters.json` (or app-owned registry) — removes `scripts` import from request path.
- All bounds configurable via `Settings`: max upload bytes, max duration sec, inference concurrency, ffmpeg timeout.

## Tests needed BEFORE the C1/C2 refactors

1. **API contract tests with a fake embedding fn** (monkeypatch `embedding_from_waveform`): empty upload→400, oversize→413, garbage bytes→400, happy path→shape of `matches`, DB missing→503.
2. **Decode tests**: wav (soundfile path), webm fixture → ffmpeg path, truncated/garbage input → `ValueError`, ffmpeg timeout path (monkeypatched).
3. **WS protocol tests** (FastAPI `TestClient.websocket_connect`): error frame on bad chunk, result frame shape, max-duration "Not sure" path, disconnect mid-stream leaves no leaked state.
4. **Concurrency regression test for C1**: while one identification is in flight (fake 1 s sleep inside inference), `/health` must respond in <100 ms. This test *fails today* and is the acceptance criterion for the C1 fix.
5. **Golden-profile test**: after any change to `extract_embeddings.py`, profiles for 2 fixed reciters must be byte-stable (guards the 97.31% baseline against pipeline regressions).

---

*Suggested attack order: tests 1–4 (small, no behavior change) → C1 (with H3) → C2 → H1/H2 → H4 → H6 → the M-items opportunistically. Then, and only then, the ML experiments (multi-profile, unknown-rejection, robustness) on top of a frozen baseline.*
