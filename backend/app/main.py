from fastapi import FastAPI
from app.routes import reciter

app = FastAPI(title="Quranic Shazam - Reciter Identifier")
app.include_router(reciter.router)
