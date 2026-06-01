"""FastAPI application exposing the halal classification engine.

Run locally:
    cd halal-scanner
    .venv/Scripts/python -m uvicorn halal_scanner.api.app:app --reload
    # then open http://localhost:8000/docs
"""
from __future__ import annotations

import requests
from fastapi import FastAPI, HTTPException

from ..classifier import HalalClassifier
from ..gemma import GemmaClient
from ..openfoodfacts import OpenFoodFactsClient
from ..rulebook import Rulebook
from .schemas import (
    BarcodeVerdictOut,
    ClassifyRequest,
    HealthOut,
    ScanBarcodeRequest,
    VerdictOut,
)

app = FastAPI(
    title="Halal Scanner API",
    description="Classify food ingredients as halal / non-halal (haram) / shubhah.",
    version="0.1.0",
)

# Built once at import time and reused across requests (loading the rulebook
# and creating the HTTP client are not free, and they hold no per-request state).
_rulebook = Rulebook.load_default()
_gemma_client = GemmaClient()
_off_client = OpenFoodFactsClient()


@app.post("/classify", response_model=VerdictOut)
def classify(req: ClassifyRequest) -> VerdictOut:
    """Classify a list of ingredient strings and return an overall verdict."""
    # Honour the per-request switch: None disables the Gemma fallback entirely,
    # making the call fully deterministic and network-free.
    client = _gemma_client if req.use_gemma else None
    engine = HalalClassifier(_rulebook, gemma_client=client)
    verdict = engine.classify(req.ingredients)
    return VerdictOut.from_verdict(verdict)


@app.post("/scan-barcode", response_model=BarcodeVerdictOut)
def scan_barcode(req: ScanBarcodeRequest) -> BarcodeVerdictOut:
    """Look up a barcode on OpenFoodFacts, then classify its ingredients."""
    product = _off_client.fetch(req.barcode)
    if product is None:
        raise HTTPException(
            status_code=404,
            detail="Product not found or has no ingredient list.",
        )
    client = _gemma_client if req.use_gemma else None
    engine = HalalClassifier(_rulebook, gemma_client=client)
    verdict = engine.classify(product.ingredients)
    return BarcodeVerdictOut.from_verdict_and_product(
        verdict, barcode=product.barcode, product_name=product.name
    )


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
