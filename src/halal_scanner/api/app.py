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
from fastapi.middleware.cors import CORSMiddleware

from ..auth import router as auth_router  # also registers the ORM models
from ..auth.keys_router import router as keys_router
from ..auth.recovery_router import router as recovery_router
from ..auth.admin_router import router as admin_router
from ..db import Base, engine

from ..classifier import HalalClassifier
from ..gemma import GemmaClient
from ..ocr import OcrEngine, parse_ingredients
from ..openfoodfacts import OpenFoodFactsClient
from ..rulebook import Rulebook
from ..translator import Translator
from .security import current_api_key, rate_limit
from .schemas import (
    BarcodeVerdictOut,
    ClassifyRequest,
    HealthOut,
    ImageVerdictOut,
    ScanBarcodeRequest,
    VerdictOut,
)


def _docs_kwargs(env: str) -> dict:
    """FastAPI kwargs that hide the interactive docs/schema in production (L-2).

    Only the explicit values "prod"/"production" disable the docs; any other
    HALAL_ENV (including unset → "dev", and names like "staging") keeps them on.
    """
    if env.strip().lower() in {"prod", "production"}:
        return {"docs_url": None, "redoc_url": None, "openapi_url": None}
    return {}


def _parse_cors_origins(raw: str) -> list[str]:
    """Comma-separated allow-list -> list of origins, blanks dropped (L-3)."""
    return [o.strip() for o in raw.split(",") if o.strip()]


def _require_prod_posture(env: str, rate_limit_raw: str | None) -> None:
    """In production, refuse to start unless a positive rate limit is set (HIGH-1).

    Auth (a valid DB API key) is already mandatory in every environment; the only
    insecure-by-default surface left is rate limiting, which is off unless
    HALAL_RATE_LIMIT is set. In prod we require it to be a positive integer.
    """
    if env.strip().lower() not in {"prod", "production"}:
        return
    try:
        limit = int(rate_limit_raw or "0")
    except ValueError:
        limit = 0
    if limit <= 0:
        got = "unset" if rate_limit_raw is None else repr(rate_limit_raw)
        raise RuntimeError(
            "In production (HALAL_ENV=production), HALAL_RATE_LIMIT must be a "
            f"positive integer so the API is not unthrottled (got: {got}). "
            "Set it before starting."
        )


app = FastAPI(
    title="Halal Scanner API",
    description="Classify food ingredients as halal / non-halal (haram) / shubhah.",
    version="0.1.0",
    **_docs_kwargs(os.environ.get("HALAL_ENV", "dev")),
)

# Default-closed: with no allow-list configured, no CORS middleware is added, so
# browsers block cross-origin requests (the safe FastAPI default). Auth is via
# headers (X-API-Key / Bearer), not cookies, so credentials are not enabled (L-3).
_cors_origins = _parse_cors_origins(os.environ.get("HALAL_CORS_ORIGINS", ""))
if _cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.middleware("http")
async def _security_headers(request, call_next):
    """Set baseline security headers on every response (L-1)."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


# Fail closed: refuse to start without a signing secret (see security spec).
if not os.environ.get("HALAL_JWT_SECRET"):
    raise RuntimeError("HALAL_JWT_SECRET must be set to start the API.")

# Fail closed in production: a rate limit must be configured (HIGH-1).
_require_prod_posture(
    os.environ.get("HALAL_ENV", "dev"), os.environ.get("HALAL_RATE_LIMIT")
)

# Create the accounts tables on startup (no-op if they already exist).
Base.metadata.create_all(bind=engine)

app.include_router(auth_router)
app.include_router(keys_router)
app.include_router(recovery_router)
app.include_router(admin_router)

# Built once at import time and reused across requests (loading the rulebook
# and creating the HTTP client are not free, and they hold no per-request state).
_rulebook = Rulebook.load_default()
_gemma_client = GemmaClient()
_off_client = OpenFoodFactsClient()
_ocr_engine = OcrEngine()
_translator = Translator()

# Cap the raw image body to bound memory use on /scan-image (HIGH-2). 5 MB is
# generous for a phone photo of an ingredient label.
MAX_IMAGE_BYTES = 5 * 1024 * 1024


async def read_capped_body(request: Request, max_bytes: int) -> bytes:
    """Read the request body, rejecting anything larger than max_bytes (HTTP 413).

    Content-Length is only trusted to reject early (it can be absent or wrong);
    the cap enforced while streaming is authoritative.
    """
    declared = request.headers.get("content-length")
    if declared is not None:
        try:
            if int(declared) > max_bytes:
                raise HTTPException(status_code=413, detail="Image too large.")
        except ValueError:
            pass  # Unparseable header: ignore and rely on the streaming cap.
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > max_bytes:
            raise HTTPException(status_code=413, detail="Image too large.")
    return bytes(body)


# The scanning endpoints require a valid DB-backed X-API-Key (always on; see
# security.py) and are rate limited (off by default). /health is left open for
# liveness probes.
_PROTECTED = [Depends(current_api_key), Depends(rate_limit)]


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
    image_bytes = await read_capped_body(request, MAX_IMAGE_BYTES)
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
