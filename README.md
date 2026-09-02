# Quranic Shazam

A lightweight audio recognition project that identifies the reciter of a Quranic recitation by comparing embeddings against a precomputed library of known reciter voice profiles.

This project combines:

- a FastAPI backend for audio upload and live recognition
- a React + Vite frontend for user interaction
- a SpeechBrain-based embedding pipeline for speaker-style recognition
- dataset generation and evaluation scripts for building and validating the model

---

## Project Features

### 1. Reciter identification from uploaded audio

The backend exposes a POST endpoint at `/identify_reciter` that accepts an uploaded audio file and returns the most likely reciter matches ranked by similarity score.

### 2. Live microphone recognition

The frontend can record audio from the browser microphone and stream it to a WebSocket endpoint at `/live_reciter`. The backend computes a sliding-window embedding and sends the best matches while the user is speaking.

### 3. Embedding-based matching

The system uses speaker embeddings from a pretrained SpeechBrain model. Each reciter has a representative embedding vector, and similarity is computed using cosine distance.

### 4. Reciter dataset pipeline

The project includes a dataset generation script that downloads Quran recitation clips from a public CDN, splits them into overlapping snippets, and stores them by reciter.

### 5. Accuracy evaluation tooling

A dedicated evaluation script tests the identification model against known reciter clips and reports accuracy percentages.

### 6. Modern web interface

The frontend is built with React and Tailwind styling, giving users a simple upload flow, live recording mode, and result rendering for matched reciters.

---

## Architecture Overview

The project is organized into two main parts:

### Backend

The backend is written in Python and runs with FastAPI.

Key files:

- [backend/main.py](backend/main.py): app bootstrap, CORS config, and route registration
- [backend/app/routes/reciter.py](backend/app/routes/reciter.py): handles uploaded audio recognition requests
- [backend/app/routes/live_reciter.py](backend/app/routes/live_reciter.py): WebSocket endpoint for real-time recognition
- [backend/extract_embeddings.py](backend/extract_embeddings.py): loads the pretrained embedding model, computes embeddings, and generates reciter vectors
- [backend/generate_data.py](backend/generate_data.py): downloads and preprocesses recitation clips
- [backend/evaluate_accuracy.py](backend/evaluate_accuracy.py): measures recognition performance on test clips
- [backend/identify_reciter.py](backend/identify_reciter.py): utility script for direct reciter matching from a single file

#### Backend flow

1. Audio is received either as a file upload or via a live microphone stream.
2. The audio is normalized and converted to the required sample rate.
3. The embedding model generates a vector representation of the voice pattern.
4. The vector is compared against stored reciter embeddings using cosine similarity.
5. The top-k most similar reciters are returned to the client.

### Frontend

The frontend is built with React and Vite.

Key files:

- [frontend/src/App.jsx](frontend/src/App.jsx): main app shell and page layout
- [frontend/src/components/IdentificationForm/index.jsx](frontend/src/components/IdentificationForm/index.jsx): upload form, recording controls, and API integration
- [frontend/src/components/Result/index.jsx](frontend/src/components/Result/index.jsx): result visualization
- [frontend/src/index.css](frontend/src/index.css): styling and visual theme

The frontend interacts with the backend through:

- `POST http://127.0.0.1:8000/identify_reciter`
- `WebSocket ws://127.0.0.1:8000/live_reciter`

---

## Data and Model Pipeline

### Data source

The system uses Quran recitation audio from a public Islamic audio CDN. The dataset script downloads surah files by reciter and splits them into overlapping clips.

### Storage layout

The project expects data under:

- [backend/data](backend/data): generated audio data and embedding cache
- [backend/data/recitations_clips](backend/data/recitations_clips): per-reciter clip folders
- [backend/data/reciters_embeddings.npy](backend/data/reciters_embeddings.npy): final averaged embeddngs per reciter

### Embedding model

The project uses the SpeechBrain ECAPA-TDNN-style speaker recognition pipeline, which is well suited for voice identity tasks and works with Quran reciter style identification.

---

## Typical Workflow

### A. Prepare the dataset

From the backend folder, run:

```bash
python generate_data.py
```

This downloads a set of recitation clips and stores them by reciter.

### B. Generate reciter embedding profiles

```bash
python extract_embeddings.py
```

This computes an embedding for each reciter and saves them to `data/reciters_embeddings.npy`.

### C. Start the backend API

```bash
cd backend
uvicorn main:app --reload
```

### D. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

Then open the Vite app in the browser, usually at:

```text
http://localhost:5173
```

---

## API Endpoints

### POST /identify_reciter

Uploads a single audio file and returns the top matching reciters.

Example response:

```json
{
  "matches": [
    { "reciter": "alafasy", "score": 0.92 },
    { "reciter": "husary", "score": 0.87 },
    { "reciter": "minshawi", "score": 0.81 }
  ]
}
```

### WebSocket /live_reciter

Streams chunks of recording audio from the browser and emits live reciter predictions.

---

## Dependencies

### Backend

The Python dependencies are listed in [backend/requirements.txt](backend/requirements.txt), including:

- FastAPI
- Uvicorn
- SpeechBrain
- NumPy
- PyDub
- Requests
- TQDM

### Frontend

The frontend dependencies are managed through [frontend/package.json](frontend/package.json), including:

- React
- Vite
- TailwindCSS
- react-h5-audio-player

---

## Project Strengths

- Simple, modular architecture
- Easy front-end/back-end separation
- Real-time audio recognition capability
- Reusable pipeline for dataset generation and evaluation
- Clear extension point for improving the embedding model or matching logic

---

## Possible Enhancements

- add a larger and more diverse reciter dataset
- improve model accuracy with a classification head or fine-tuning step
- optimize live recognition latency and smoothing logic
- add audio preprocessing for noise reduction and silence trimming
- persist embeddings in a more structured format or database

---

## Summary

Quranic Shazam is a full-stack audio recognition project that identifies the reciter of Quranic recitation using voice embeddings and similarity scoring. It combines a modern web UI with a machine learning pipeline and a practical dataset-generation workflow, making it useful both as a demo application and as a foundation for further research or product development.
