"""Translate ingredient text to English via the local Ollama/Gemma server.

The rulebook is keyed in English, so a foreign-language label must be translated
before classification. Like ``GemmaClient``, this never raises to the caller: on
any failure it returns the **original** text, so the pipeline degrades to
classifying the untranslated string rather than erroring.
"""
from __future__ import annotations

import requests

_PROMPT = (
    "Translate the following food ingredient text to English. "
    "Respond with ONLY the English translation, no commentary, no quotes.\n"
    "Text: {text}"
)


class Translator:
    """Translates text to English using a local Ollama server. Never raises."""

    def __init__(
        self,
        host: str = "http://localhost:11434",
        model: str = "gemma4:latest",
        timeout: int = 30,
    ):
        self.host = host
        self.model = model
        self.timeout = timeout

    def to_english(self, text: str) -> str:
        """Return the English translation, or the original text on any failure."""
        if not text or not text.strip():
            return text
        try:
            resp = requests.post(
                f"{self.host}/api/generate",
                json={
                    "model": self.model,
                    "prompt": _PROMPT.format(text=text),
                    "stream": False,
                },
                timeout=self.timeout,
            )
            resp.raise_for_status()
            translated = str(resp.json()["response"]).strip()
        except Exception:
            return text
        # An empty model response is useless — fall back to the original.
        return translated or text
