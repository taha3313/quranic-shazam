# Browser check — 2026-09-17

App opened and tested in the Codex in-app browser at http://localhost:5173.
Backend runs on http://127.0.0.1:8000.

Verified through the rendered UI and actual backend:
- Upload real Ghamdi 55_14.wav: correctly displays Saad Al-Ghamdi.
- Upload Alafasy Rahman 55:59 alone: uncertain, equal-score refrain candidates,
  and a message requesting additional context.
- Upload concatenated real 55:59-60 recordings: correctly displays 55:59-60.
- Audio player switches Play/Pause and plays the uploaded recording.
- Verse microphone recording starts, submits cumulative browser MediaRecorder
  snapshots, stops manually, releases controls, and completes successful API
  responses. Background input stayed uncertain.
- Live reciter microphone initially showed a decode error; fixed recognized
  WebM streams to decode cumulatively and wait for an incomplete header.
  Frontend waits for the WebSocket before recording, preserving the first
  container chunk. Retest streams through actual ECAPA inference without
  the prior UI error, and manual stop resets the controls.
- A malformed .wav upload shows a useful decode error and remains recoverable.
- Health reports ok with 20 reciters; the UI and API remain responsive.

69 backend tests passed; changed backend modules lint clean; frontend build
passed. Browser console had no application errors during successful flows.
Layout inspected at the default narrow in-app browser width.

Limitations: known recitation was tested through uploads. No controlled Quran
performance was spoken into the physical microphone, so live recognition
accuracy and automatic stop-on-confidence were not validated in this browser
session. One-minute verse recording timeout was covered by tests, not a full
one-minute browser recording. These checks do not establish all-device or
production deployment correctness.

Servers are left running, and the browser remains on the verified verse result.
