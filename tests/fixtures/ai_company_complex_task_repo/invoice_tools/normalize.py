from __future__ import annotations

import re


def normalize_amount_to_cents(raw: str) -> int:
    text = raw.strip()
    if not text:
        raise ValueError("empty amount")

    negative = text.startswith("-")
    cleaned = text.replace("$", "").replace(",", "").replace(" ", "")
    cleaned = cleaned.replace("(", "").replace(")", "")
    if negative:
        cleaned = cleaned[1:]

    if not re.search(r"\d", cleaned):
        raise ValueError("no numeric content")

    value = float(cleaned)
    cents = int(round(value * 100))
    return -cents if negative else cents
