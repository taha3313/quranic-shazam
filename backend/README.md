# Backend — Quranic Shazam

FastAPI service for reciter identification. See the root README for full docs.

```bash
make backend-export  # one-time ONNX artifact generation
make backend-install # runtime + dev tools; no PyTorch
make backend-dev     # http://localhost:8000, health at /health
make backend-test
```

Serving uses ONNX Runtime for ECAPA and faster-whisper for ayah recognition.
PyTorch and SpeechBrain are only needed by the export/comparison tools. See
[lightweight deployment and validation](../docs/onnx-deployment.md).
