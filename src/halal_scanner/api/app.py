"""FastAPI application exposing the halal classification engine.

Run locally:
    cd halal-scanner
    .venv/Scripts/python -m uvicorn halal_scanner.api.app:app --reload
    # then open http://localhost:8000/docs
"""
from __future__ import annotations

import os

import requests
from fastapi import Depends, FastAPI, HTTPException, Request

from ..auth import router as auth_router  # also registers the ORM models
from ..auth.keys_router import router as keys_router
from ..auth.recovery_router import router as recovery_router
from ..db import Base, engine

from ..classifier import HalalClassifier
from ..gemma import GemmaClient
from ..ocr import OcrEngine, parse_ingredients
from ..openfoodfacts import OpenFoodFactsClient
from ..rulebook import Rulebook
from ..translator import Translator
from .security import rate_limit, require_api_key
from .schemas import (
    BarcodeVerdictOut,
    ClassifyRequest,
    HealthOut,
    ImageVerdictOut,
    ScanBarcodeRequest,
    VerdictOut,
)

app = FastAPI(
    title="Halal Scanner API",
    description="Classify food ingredients as halal / non-halal (haram) / shubhah.",
    version="0.1.0",
)


# Fail closed: refuse to start without a signing secret (see security spec).
if not os.environ.get("HALAL_JWT_SECRET"):
    raise RuntimeError("HALAL_JWT_SECRET must be set to start the API.")

# Create the accounts tables on startup (no-op if they already exist).
Base.metadata.create_all(bind=engine)

app.include_router(auth_router)
app.include_router(keys_router)
app.include_router(recovery_router)

# Built once at import time and reused across requests (loading the rulebook
# and creating the HTTP client are not free, and they hold no per-request state).
_rulebook = Rulebook.load_default()
_gemma_client = GemmaClient()
_off_client = OpenFoodFactsClient()
_ocr_engine = OcrEngine()
_translator = Translator()


# The scanning endpoints require a valid DB-backed X-API-Key (always on; see
# security.py) and are rate limited (off by default). /health is left open for
# liveness probes.
_PROTECTED = [Depends(require_api_key), Depends(rate_limit)]


def _translate_all(ingredients: list[str], enabled: bool) -> list[str]:
    """Translate each ingredient to English when enabled; otherwise pass through."""
    if not enabled:
        return ingredients
    return [_translator.to_english(item) for item in ingredients]


@app.post("/classify", response_model=VerdictOut, dependencies=_PROTECTED)
def classify(req: ClassifyRequest) -> VerdictOut:
    """Classify a list of ingredient strings and return an overall verdict."""
    # Honour the per-request switch: None disables the Gemma fallback entirely,
    # making the call fully deterministic and network-free.
    client = _gemma_client if req.use_gemma else None
    engine = HalalClassifier(_rulebook, gemma_client=client)
    ingredients = _translate_all(req.ingredients, req.translate)
    verdict = engine.classify(ingredients)
    return VerdictOut.from_verdict(verdict)


@app.post("/scan-barcode", response_model=BarcodeVerdictOut, dependencies=_PROTECTED)
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
    ingredients = _translate_all(product.ingredients, req.translate)
    verdict = engine.classify(ingredients)
    return BarcodeVerdictOut.from_verdict_and_product(
        verdict, barcode=product.barcode, product_name=product.name
    )


@app.post("/scan-image", response_model=ImageVerdictOut, dependencies=_PROTECTED)
async def scan_image(
    request: Request, use_gemma: bool = True, translate: bool = False
) -> ImageVerdictOut:
    """OCR a label image (sent as the raw request body), then classify it."""
    image_bytes = await request.body()
    text = _ocr_engine.extract_text(image_bytes)
    ingredients = parse_ingredients(text)
    if not ingredients:
        raise HTTPException(
            status_code=422,
            detail="Could not read any text from the image.",
        )
    client = _gemma_client if use_gemma else None
    engine = HalalClassifier(_rulebook, gemma_client=client)
    ingredients = _translate_all(ingredients, translate)
    verdict = engine.classify(ingredients)
    return ImageVerdictOut.from_verdict_and_text(verdict, extracted_text=text)


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
