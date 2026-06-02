"""Pluggable email delivery with a default no-network console backend.

Mirrors the OCR/Gemma backends: the default never touches the network — it just
records and logs messages — so the app and tests work with no email provider.
A real backend (SMTP, Resend, ...) can be injected later.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable

logger = logging.getLogger(__name__)


@dataclass
class EmailMessage:
    to: str
    subject: str
    body: str


EmailBackend = Callable[[EmailMessage], None]


def _console_backend(msg: EmailMessage) -> None:
    logger.info("EMAIL to=%s subject=%s body=%s", msg.to, msg.subject, msg.body)


class Emailer:
    """Sends email via a backend; keeps an in-memory outbox. Never raises."""

    def __init__(self, backend: EmailBackend | None = None):
        self._backend = backend or _console_backend
        self.outbox: list[EmailMessage] = []

    def send(self, to: str, subject: str, body: str) -> None:
        msg = EmailMessage(to=to, subject=subject, body=body)
        self.outbox.append(msg)
        try:
            self._backend(msg)
        except Exception:
            logger.exception("Email backend failed for %s", to)


# One shared instance the recovery service uses; tests may read its outbox.
emailer = Emailer()
