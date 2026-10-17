# Production deployment

The React frontend is served by nginx, which forwards `/api/` to the Python
backend. Both recognition modes use the same HTTPS origin, including microphone
recording. Never build a public deployment with a localhost API URL.

Run `docker compose up -d --build` on the selected backend host. The stack binds
only to loopback: frontend on port 8080 and backend on port 8000. Put an HTTPS
reverse proxy or Cloudflare Tunnel in front of `http://localhost:8080`.

The backend image includes the reciter embeddings, display names, and Quran
corpus. Model downloads happen on first use and persist in Docker volumes. Allow
outbound access to Hugging Face for those initial downloads. First recognition
requests can take longer while models load.

Before declaring deployment healthy, verify `/api/health` reports 20 reciters,
submit real recordings to `/api/identify_reciter` and
`/api/identify_verse_progressive`, and test recording in an HTTPS browser.

Cloudflare static hosting alone cannot run this Python inference backend. Cloudflare
Containers requires a paid Workers plan. A tunnel to a local machine only stays
available while that machine and its connector are running.

The lightweight backend uses ONNX Runtime and faster-whisper. Export the reciter
artifact before building, as described in [onnx-deployment.md](onnx-deployment.md).
