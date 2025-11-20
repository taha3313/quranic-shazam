from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import reciter

app = FastAPI(title="Quranic Shazam - Reciter Identifier")

# Allowed frontend URLs
origins = [
    "http://localhost:5173",   # Vite dev server
    "http://127.0.0.1:5173",
    "*",  # Allow all (optional, only for debugging)
]

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,         # domains allowed
    allow_credentials=True,
    allow_methods=["*"],           # GET, POST, etc.
    allow_headers=["*"],           # Content-Type, etc.
)

# Routes
app.include_router(reciter.router)
