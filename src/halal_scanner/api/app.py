"""FastAPI application exposing the halal classification engine.

Run locally:
    cd halal-scanner
    .venv/Scripts/python -m uvicorn halal_scanner.api.app:app --reload
    # then open http://localhost:8000/docs
"""
from __future__ import annotations

import requests
from fastapi import FastAPI

from ..classifier import HalalClassifier
from ..gemma import GemmaClient
from ..rulebook import Rulebook
from .schemas import ClassifyRequest, HealthOut, VerdictOut

app = FastAPI(
    title="Halal Scanner API",
    description="Classify food ingredients as halal / non-halal (haram) / shubhah.",
    version="0.1.0",
)

# Built once at import time and reused across requests (loading the rulebook
# and creating the HTTP client are not free, and they hold no per-request state).
_rulebook = Rulebook.load_default()
_gemma_client = GemmaClient()


@app.post("/classify", response_model=VerdictOut)
def classify(req: ClassifyRequest) -> VerdictOut:
    """Classify a list of ingredient strings and return an overall verdict."""
    # Honour the per-request switch: None disables the Gemma fallback entirely,
    # making the call fully deterministic and network-free.
    client = _gemma_client if req.use_gemma else None
    engine = HalalClassifier(_rulebook, gemma_client=client)
    verdict = engine.classify(req.ingredients)
    return VerdictOut.from_verdict(verdict)


@app.get("/health", response_model=HealthOut)
def health() -> HealthOut:
    """Liveness check, including whether the Ollama server is reachable."""
    return HealthOut(status="ok", ollama_available=_ollama_available())


def _ollama_available() -> bool:
    """Short-timeout probe of the Ollama server. Never raises."""
    try:
        resp = requests.get(f"{_gemma_client.host}/api/tags", timeout=2)
        return resp.status_code == 200
    except Exception:
        return False
