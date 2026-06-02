"""Look up a product's ingredients from its barcode via OpenFoodFacts.

This is a data source, not a classifier: it fetches the ingredient text for a
barcode and hands it to the existing engine. Like ``GemmaClient``, it never
raises to the caller — any failure (network, bad JSON, product not found,
no ingredient list) collapses to ``None``.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import quote

import requests

# A real barcode is 6-14 digits. Guard here too (defence in depth): this client
# is reusable and not guaranteed to sit behind the API's schema validation.
_BARCODE_RE = re.compile(r"^[0-9]{6,14}$")


@dataclass
class Product:
    """A product looked up from OpenFoodFacts."""
    barcode: str
    name: str
    ingredients: list[str]
    raw_text: str


def split_ingredients(text: str) -> list[str]:
    """Split an ingredient label into individual strings.

    Deliberately simple — comma-separated, trimmed, empties dropped. The
    engine's normalizer cleans each piece further during classification.
    """
    return [part.strip() for part in text.split(",") if part.strip()]


class OpenFoodFactsClient:
    """Fetches product ingredients from the OpenFoodFacts API. Never raises."""

    def __init__(
        self,
        host: str = "https://world.openfoodfacts.org",
        timeout: int = 10,
    ):
        self.host = host
        self.timeout = timeout

    def fetch(self, barcode: str) -> Product | None:
        """Return a Product for the barcode, or None on any failure."""
        if not _BARCODE_RE.match(barcode):
            return None
        try:
            resp = requests.get(
                f"{self.host}/api/v2/product/{quote(barcode, safe='')}.json",
                timeout=self.timeout,
                allow_redirects=False,
            )
            resp.raise_for_status()
            payload = resp.json()
            # status == 1 means "product found"; 0 means not found.
            if payload.get("status") != 1:
                return None
            product = payload.get("product") or {}
            raw_text = str(product.get("ingredients_text", "")).strip()
            ingredients = split_ingredients(raw_text)
            if not ingredients:
                return None
        except Exception:
            return None
        return Product(
            barcode=barcode,
            name=str(product.get("product_name", "")).strip(),
            ingredients=ingredients,
            raw_text=raw_text,
        )
