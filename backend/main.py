"""
FastAPI app entry point. Run from inside backend/:

    uvicorn main:app --reload --port 8000

Then open http://localhost:8000 — the frontend is served as static files and
calls the /api/* routes on the same origin, so there's no CORS setup needed
for the demo, though CORS is left open below in case anyone runs the
frontend from a different port during development.
"""
import os

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from routes import accusation, case as case_routes, clues, session as session_routes, speech, suspects

app = FastAPI(title="The Interrogation Room")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(case_routes.router, prefix="/api")
app.include_router(suspects.router, prefix="/api")
app.include_router(clues.router, prefix="/api")
app.include_router(accusation.router, prefix="/api")
app.include_router(session_routes.router, prefix="/api")
app.include_router(speech.router, prefix="/api")

_frontend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend")
app.mount("/", StaticFiles(directory=_frontend_dir, html=True), name="frontend")
