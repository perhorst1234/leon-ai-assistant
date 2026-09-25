"""Small, local-only sensitivity classifier for model routing.

This is intentionally conservative: it never sends text to a classifier or
provider. A sensitive turn is forced to the loopback M40 route by policy.
"""
from __future__ import annotations

import re


_SENSITIVE_TERMS = re.compile(
    r"\b(?:seks|sex|seksueel|sexual|sensueel|sensual|erotisch|erotic|"
    r"porno|porn|naakt|nude|nsfw|intiem|intimate|intimiteit|intimacy|"
    r"geil|horny|masturbat(?:ie|ion)|orgasme|orgasm)\b",
    re.IGNORECASE,
)


def classify_prompt(text: str) -> dict[str, object]:
    """Return a bounded routing classification without retaining the text."""
    if not isinstance(text, str):
        return {"category": "normal", "local_only": False}
    match = _SENSITIVE_TERMS.search(text)
    if match:
        return {"category": "sexual", "local_only": True}
    return {"category": "normal", "local_only": False}

