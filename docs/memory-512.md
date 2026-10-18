# 512 MiB deployment profile

Goal: test both existing recognition models under a hard 512 MiB limit without
quantizing weights, truncating recordings further, or changing confidence gates.

The low-memory profile (`QD_LOW_MEMORY=true`) keeps a model loaded only for the
current request, while holding the shared inference slot. The model stays loaded
across ASR windows within one progressive request, then is released. Subsequent
requests reload model weights. This also clears ONNX session caches that grow
when successive requests use different input lengths.

Native allocator memory is returned after inference, after loading a model,
and after eviction using garbage collection and glibc `malloc_trim` where
available. Linux container settings retain two native threads and limit glibc
allocator caching:

```
QD_LOW_MEMORY=true
QD_INFERENCE_THREADS=2
OPENBLAS_NUM_THREADS=2
OMP_NUM_THREADS=2
MALLOC_ARENA_MAX=2
MALLOC_MMAP_THRESHOLD_=131072
MALLOC_TRIM_THRESHOLD_=131072
```

These allocator settings must be present at process startup. Other platforms
that do not expose `malloc_trim` only use garbage collection and model eviction;
they have not been validated against the Linux container memory limit.

Validation must include real 30-second reciter inputs, the verse listen limit,
WebM input, repeated requests, switching between recognizers, and overlapping
requests under a hard limit with swap disabled. Check cgroup peak memory and OOM
events, score/ordering/confidence parity, and transcript/match parity against
the previous runtime. A short sample fitting in memory is not sufficient proof.

The low-memory profile admits at most two active recognition HTTP requests,
with HTTP 503 and Retry-After for excess work. Admission happens before multipart
parsing and lasts through response delivery, so idle keep-alive connections do
not consume this budget. Health checks remain available. Model execution stays
serialized. This prevents an unbounded queue of decoded uploads. The HTTP
recognition routes decode only their existing 30/20/60-second audio windows,
with a small resampling lookahead, rather than allocating the full recording
and trimming it afterwards.

For ordinary multipart uploads, Starlette's parsed file size is checked before
reading. The handler reads the file once and closes the spooled upload before
inference, avoiding a temporary second in-memory copy of large recordings.

## Measured result

The packaged image was tested with one CPU, a hard 512 MiB memory limit, and
swap disabled. All 63 reciter inputs retained the same top-three ordering and
confidence decisions with zero score drift. The 20-second and full 60-second
progressive ayah responses, both WebM routes, and three overlapping request
pairs matched the previous container runtime. The full test suite passed.

A 22.4 MB upload containing 700 seconds of audio returned the same reciter
ranking while decoding only the existing 30-second limit. Its container peak
was 462.6 MiB, with no memory-limit or OOM events. During the full progressive
ASR matrix, the cgroup peak counter reached the 512 MiB ceiling, but the
container stayed healthy and reported zero OOM kills. This confirms the tested
request set fits at 512 MiB, with limited headroom during ASR. See
`../backend/data/eval_reports/memory-512/` for the image identity, responses,
resource counters, and source hash.

The tradeoff is a model reload on each recognition request. Progressive ASR
windows within a single request still share one loaded model.
