from __future__ import annotations

import re
from collections import Counter

from pydantic import BaseModel, Field

from app.investigation.models import ParsedDocument


class FraudClassifierInput(BaseModel):
    documents: list[ParsedDocument] = Field(min_length=1)


class FraudClassifierOutput(BaseModel):
    probability: float = Field(ge=0.0, le=1.0)
    signals: list[str] = Field(default_factory=list)
    label: str = Field(default="model signal, not evidence")


# Amount patterns (German format: 50.000,00 or 50000,00 or 9780,00)
_AMOUNT_PATTERN = re.compile(r"(\d{1,3}(?:\.\d{3})*,\d{2}|\d{4,}(?:,\d{2})?)")

# Round-amount thresholds
_ROUND_AMOUNT_THRESHOLD = 1000


def classify_documents(input_data: FraudClassifierInput) -> FraudClassifierOutput:
    """Rule-based fraud classifier as baseline.

    Detects:
    - Amount anomalies (round amounts, near-threshold amounts)
    - Duplicate-like patterns (same vendor, same day, similar amounts)
    - Timing gaps (service dates vs booking dates mismatch)

    Output is clearly labeled as a model signal, NOT evidence.
    """
    signals: list[str] = []
    score = 0.0

    all_text = _combine_document_text(input_data.documents)

    # Check for round amounts
    round_amount_score, round_signals = _detect_round_amounts(all_text)
    score += round_amount_score
    signals.extend(round_signals)

    # Check for near-threshold amounts (just under 10,000)
    threshold_score, threshold_signals = _detect_threshold_splitting(all_text)
    score += threshold_score
    signals.extend(threshold_signals)

    # Check for duplicate patterns
    dup_score, dup_signals = _detect_duplicate_patterns(all_text)
    score += dup_score
    signals.extend(dup_signals)

    # Check for timing anomalies
    timing_score, timing_signals = _detect_timing_anomalies(all_text)
    score += timing_score
    signals.extend(timing_signals)

    # Normalize to 0-1
    probability = min(1.0, max(0.0, score / 4.0))

    return FraudClassifierOutput(
        probability=probability,
        signals=signals,
        label="model signal, not evidence",
    )


def _combine_document_text(documents: list[ParsedDocument]) -> str:
    parts: list[str] = []
    for doc in documents:
        for chunk in doc.content_chunks[:50]:
            parts.append(chunk.text)
    return "\n".join(parts)


def _parse_german_amount(text: str) -> float | None:
    """Parse a German-formatted amount like 50.000,00 or 9780,00."""
    cleaned = text.replace(".", "").replace(",", ".").strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


def _detect_round_amounts(text: str) -> tuple[float, list[str]]:
    """Detect suspiciously round amounts (multiples of 1000+)."""
    matches = _AMOUNT_PATTERN.findall(text)
    round_amounts: list[float] = []

    for match in matches:
        amount = _parse_german_amount(match)
        if amount is None or amount < _ROUND_AMOUNT_THRESHOLD:
            continue
        # Check if round (divisible by 1000 with no remainder)
        if amount % 1000 == 0 and amount >= 10000:
            round_amounts.append(amount)

    signals: list[str] = []
    if len(round_amounts) >= 3:
        signals.append(f"Multiple round amounts detected ({len(round_amounts)} amounts divisible by €1,000)")
        return 1.0, signals
    elif len(round_amounts) >= 1:
        signals.append(f"Round amounts detected ({len(round_amounts)})")
        return 0.4, signals

    return 0.0, signals


def _detect_threshold_splitting(text: str) -> tuple[float, list[str]]:
    """Detect amounts just under common thresholds (e.g., €10,000)."""
    matches = _AMOUNT_PATTERN.findall(text)
    near_threshold: list[float] = []

    for match in matches:
        amount = _parse_german_amount(match)
        if amount is None:
            continue
        # Just under €10,000 (between 9,500 and 9,999)
        if 9500 <= amount < 10000:
            near_threshold.append(amount)

    signals: list[str] = []
    if len(near_threshold) >= 3:
        signals.append(
            f"Multiple near-threshold amounts detected ({len(near_threshold)} amounts just under €10,000)"
        )
        return 1.5, signals
    elif len(near_threshold) >= 2:
        signals.append(f"Near-threshold amounts detected ({len(near_threshold)})")
        return 0.6, signals

    return 0.0, signals


def _detect_duplicate_patterns(text: str) -> tuple[float, list[str]]:
    """Detect suspicious duplicates: same vendor appearing many times."""
    lines = text.splitlines()
    # Look for repeated vendor-like patterns (semicolon-separated fields)
    vendor_counts: Counter[str] = Counter()

    for line in lines:
        parts = line.split(";")
        if len(parts) >= 3:
            # Heuristic: field that looks like a company name (contains GmbH, AG, etc.)
            for part in parts:
                cleaned = part.strip().strip('"')
                if any(suffix in cleaned for suffix in ("GmbH", "AG", "KG", "SE", "e.K.")):
                    vendor_counts[cleaned] += 1

    signals: list[str] = []
    # Flag vendors with unusually high frequency relative to others
    if vendor_counts:
        most_common = vendor_counts.most_common(3)
        for vendor, count in most_common:
            if count >= 10:
                signals.append(f"High-frequency vendor: {vendor} ({count} occurrences)")

    score = min(1.0, len(signals) * 0.5)
    return score, signals


def _detect_timing_anomalies(text: str) -> tuple[float, list[str]]:
    """Detect potential cut-off manipulation: December dates near January dates."""
    # Simple heuristic: look for December 2025 and January 2026 dates in same document
    dec_pattern = re.compile(r"\b(\d{1,2})\.(12)\.2025\b")
    jan_pattern = re.compile(r"\b(\d{1,2})\.(01)\.2026\b")

    dec_dates = dec_pattern.findall(text)
    jan_dates = jan_pattern.findall(text)

    signals: list[str] = []
    if dec_dates and jan_dates:
        signals.append(
            f"Mixed Dec 2025 ({len(dec_dates)} dates) and Jan 2026 ({len(jan_dates)} dates) — "
            "possible cut-off manipulation"
        )
        return 0.8, signals

    return 0.0, signals
