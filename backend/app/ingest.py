from __future__ import annotations

import re
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader

from app.schemas import BrandingPalette, PdfDocumentMetadata

DEFAULT_BRANDING = BrandingPalette(
    background="#F9FAFB",
    text="#111827",
    secondary="#374151",
    accent="#06B6D4",
)

KNOWN_COMPANY_PALETTES: dict[str, BrandingPalette] = {
    "apple": BrandingPalette(background="#F5F5F7", text="#1D1D1F", secondary="#6E6E73", accent="#0071E3"),
    "tesla": BrandingPalette(background="#F4F4F4", text="#171A20", secondary="#5C5E62", accent="#E82127"),
    "microsoft": BrandingPalette(background="#F3F7FB", text="#1F1F1F", secondary="#5E5E5E", accent="#0078D4"),
    "google": BrandingPalette(background="#F8F9FA", text="#202124", secondary="#5F6368", accent="#1A73E8"),
    "alphabet": BrandingPalette(background="#F8F9FA", text="#202124", secondary="#5F6368", accent="#1A73E8"),
    "amazon": BrandingPalette(background="#F7F8FA", text="#111111", secondary="#4B5563", accent="#FF9900"),
    "meta": BrandingPalette(background="#F6F8FC", text="#1C2B33", secondary="#526471", accent="#0866FF"),
    "netflix": BrandingPalette(background="#141414", text="#FFFFFF", secondary="#D1D5DB", accent="#E50914"),
    "nvidia": BrandingPalette(background="#F3F8E8", text="#1F2937", secondary="#4B5563", accent="#76B900"),
}

PERIOD_PATTERNS = [
    re.compile(r"\b(q[1-4])\s*(?:fy)?\s*(20\d{2})\b", re.IGNORECASE),
    re.compile(r"\b(quarter\s+[1-4])\s+(?:of\s+)?(?:fiscal\s+year\s+)?(20\d{2})\b", re.IGNORECASE),
    re.compile(r"\b(first|second|third|fourth)\s+quarter\s+(?:of\s+)?(?:fiscal\s+year\s+)?(20\d{2})\b", re.IGNORECASE),
]

COMPANY_PATTERNS = [
    re.compile(r"\b([A-Z][A-Za-z&.\-]+(?:\s+[A-Z][A-Za-z&.\-]+){0,3})\s+(?:Inc\.|Corp\.|Corporation|Ltd\.|plc)\b"),
    re.compile(r"\b([A-Z][A-Za-z&.\-]+(?:\s+[A-Z][A-Za-z&.\-]+){0,3})\s+(?:Earnings|Results|Report|Shareholder)\b"),
]


def extract_pdf_text(file_bytes: bytes) -> str:
    reader = PdfReader(BytesIO(file_bytes))
    pages = [(page.extract_text() or "").strip() for page in reader.pages]
    return "\n\n".join(page for page in pages if page).strip()


def extract_pdf_documents(
    uploads: list[tuple[str, bytes]],
) -> tuple[list[PdfDocumentMetadata], str, BrandingPalette, str, str]:
    documents: list[PdfDocumentMetadata] = []
    texts: list[str] = []

    for filename, file_bytes in uploads:
        reader = PdfReader(BytesIO(file_bytes))
        pages = [(page.extract_text() or "").strip() for page in reader.pages]
        text = "\n\n".join(page for page in pages if page).strip()
        texts.append(text)
        company_name = detect_company_name(text=text, filename=filename)
        period_label = detect_period_label(text=text, filename=filename)
        palette = detect_brand_palette(company_name)
        documents.append(
            PdfDocumentMetadata(
                filename=filename,
                company_name=company_name,
                period_label=period_label,
                page_count=max(1, len(reader.pages)),
                palette=palette,
            )
        )

    validate_same_company(documents)
    company_name = documents[0].company_name if documents else "Unknown Company"
    period_label = build_period_label(documents)
    branding = choose_branding_palette(documents)
    combined_text = build_comparison_source_text(documents, texts)
    return documents, combined_text, branding, company_name, period_label


def build_comparison_source_text(documents: list[PdfDocumentMetadata], texts: list[str]) -> str:
    blocks: list[str] = []
    for index, (document, text) in enumerate(zip(documents, texts, strict=True), start=1):
        blocks.append(
            "\n".join(
                [
                    f"=== DOCUMENT {index} ===",
                    f"Filename: {document.filename}",
                    f"Company: {document.company_name}",
                    f"Reporting period: {document.period_label}",
                    "",
                    text,
                ]
            ).strip()
        )
    return "\n\n".join(blocks).strip()


def detect_company_name(*, text: str, filename: str) -> str:
    head = " ".join(text.splitlines()[:20]).strip()
    combined = f"{filename} {head}".lower()
    for known_name in KNOWN_COMPANY_PALETTES:
        if known_name in combined:
            return normalize_company_name(known_name.title())
    for pattern in COMPANY_PATTERNS:
        match = pattern.search(head)
        if match:
            return normalize_company_name(match.group(1))

    stem = Path(filename).stem.replace("_", " ").replace("-", " ").strip()
    for token in stem.split():
        if token.isalpha() and len(token) > 2:
            return normalize_company_name(token)
    return "Unknown Company"


def normalize_company_name(value: str) -> str:
    cleaned = re.sub(r"\s+", " ", value).strip(" -_:,.")
    return cleaned or "Unknown Company"


def detect_period_label(*, text: str, filename: str) -> str:
    head = " ".join(text.splitlines()[:40])
    combined = f"{filename} {head}"
    for pattern in PERIOD_PATTERNS:
        match = pattern.search(combined)
        if not match:
            continue
        quarter = normalize_period_quarter(match.group(1))
        year = match.group(2)
        return f"{quarter} {year}"
    return "Current Period"


def normalize_period_quarter(value: str) -> str:
    lowered = value.lower().strip()
    mapping = {
        "q1": "Q1",
        "q2": "Q2",
        "q3": "Q3",
        "q4": "Q4",
        "quarter 1": "Q1",
        "quarter 2": "Q2",
        "quarter 3": "Q3",
        "quarter 4": "Q4",
        "first": "Q1",
        "second": "Q2",
        "third": "Q3",
        "fourth": "Q4",
    }
    return mapping.get(lowered, value.upper())


def detect_brand_palette(company_name: str) -> BrandingPalette:
    key = company_name.lower()
    for known_name, palette in KNOWN_COMPANY_PALETTES.items():
        if known_name in key:
            return ensure_accessible_palette(palette)
    return DEFAULT_BRANDING


def choose_branding_palette(documents: list[PdfDocumentMetadata]) -> BrandingPalette:
    if not documents:
        return DEFAULT_BRANDING
    preferred = documents[0].palette
    return ensure_accessible_palette(preferred)


def ensure_accessible_palette(palette: BrandingPalette) -> BrandingPalette:
    bg_is_dark = relative_luminance(palette.background) < 0.35
    text_default = "#FFFFFF" if bg_is_dark else "#111827"
    secondary_default = "#D1D5DB" if bg_is_dark else "#374151"
    text = palette.text if contrast_ratio(palette.background, palette.text) >= 4.5 else text_default
    secondary = (
        palette.secondary
        if contrast_ratio(palette.background, palette.secondary) >= 3.5
        else secondary_default
    )
    accent = palette.accent if contrast_ratio(palette.background, palette.accent) >= 2.5 else "#06B6D4"
    return BrandingPalette(
        background=palette.background,
        text=text,
        secondary=secondary,
        accent=accent,
    )


def build_period_label(documents: list[PdfDocumentMetadata]) -> str:
    unique_periods = list(dict.fromkeys(document.period_label for document in documents))
    if not unique_periods:
        return "Current Period"
    if len(unique_periods) == 1:
        return unique_periods[0]
    return " vs ".join(unique_periods)


def validate_same_company(documents: list[PdfDocumentMetadata]) -> None:
    company_names = {document.company_name.lower() for document in documents}
    if len(company_names) > 1:
        raise ValueError("PDF comparison mode currently supports reports from a single company only.")


def hex_to_rgb(value: str) -> tuple[float, float, float]:
    hex_value = value.lstrip("#")
    if len(hex_value) != 6:
        raise ValueError(f"Invalid hex color: {value}")
    red = int(hex_value[0:2], 16) / 255
    green = int(hex_value[2:4], 16) / 255
    blue = int(hex_value[4:6], 16) / 255
    return red, green, blue


def relative_luminance(value: str) -> float:
    def channel_luminance(channel: float) -> float:
        if channel <= 0.03928:
            return channel / 12.92
        return ((channel + 0.055) / 1.055) ** 2.4

    red, green, blue = hex_to_rgb(value)
    return (
        0.2126 * channel_luminance(red)
        + 0.7152 * channel_luminance(green)
        + 0.0722 * channel_luminance(blue)
    )


def contrast_ratio(color_a: str, color_b: str) -> float:
    lum_a = relative_luminance(color_a)
    lum_b = relative_luminance(color_b)
    lighter = max(lum_a, lum_b)
    darker = min(lum_a, lum_b)
    return (lighter + 0.05) / (darker + 0.05)
