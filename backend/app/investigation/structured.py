from __future__ import annotations

import json
import csv
from collections import defaultdict
from io import StringIO
from pathlib import Path

from pydantic import BaseModel, Field

from app.agents._prompts import load_prompt
from app.integrations.llm_router import LLMRouter
from app.investigation.models import DocumentType, ParsedDocument


STRUCTURED_DATA_ROOT = Path("/tmp")


class KeyValueEntry(BaseModel):
    field: str = Field(min_length=1)
    value: str = Field(min_length=1)
    context: str = Field(min_length=1)


class StructuredFile(BaseModel):
    file_id: str = Field(min_length=1)
    filename: str = Field(min_length=1)
    extraction_method: str = Field(min_length=1)
    columns: list[str] | None = None
    original_columns: list[str] | None = None
    normalized_columns: list[str] | None = None
    rows: list[dict[str, str]] | None = None
    key_values: list[KeyValueEntry] | None = None
    row_count: int = Field(ge=0, default=0)


COLUMN_SYNONYM_MAP: dict[str, str] = {
    "amount": "amount",
    "betrag": "amount",
    "betrag_eur": "amount",
    "buchungsbetrag": "amount",
    "rechnungsbetrag": "amount",
    "date": "date",
    "datum": "date",
    "wertstellung": "date",
    "buchungsdatum": "date",
    "vendor": "vendor_id",
    "vendor_id": "vendor_id",
    "kreditor": "vendor_id",
    "lieferant": "vendor_id",
    "creditor": "vendor_id",
    "invoice_number": "invoice_number",
    "rechnungsnummer": "invoice_number",
    "belegnummer": "invoice_number",
    "invoice_no": "invoice_number",
    "account": "account_id",
    "konto": "account_id",
    "kontonummer": "account_id",
    "text": "text",
    "buchungstext": "text",
    "beschreibung": "text",
}


def normalize_column_name(raw_name: str) -> str:
    normalized_key = "_".join(raw_name.strip().casefold().replace("-", " ").split())
    return COLUMN_SYNONYM_MAP.get(normalized_key, raw_name)


def extract_tabular(doc: ParsedDocument) -> StructuredFile:
    if doc.doc_type not in (DocumentType.CSV, DocumentType.XLSX, DocumentType.TXT):
        raise ValueError(f"Deterministic extraction is not supported for {doc.doc_type.value} files")

    delimiter = doc.metadata.get("delimiter", ";")
    rows_by_sheet: dict[str, list[list[str]]] = defaultdict(list)
    for chunk in doc.content_chunks:
        values = next(csv.reader(StringIO(chunk.text), delimiter=delimiter), [])
        if values:
            rows_by_sheet[_sheet_key(chunk.source_ref)].append(values)

    original_columns: list[str] = []
    normalized_columns: list[str] = []
    extracted_rows: list[dict[str, str]] = []
    for sheet_rows in rows_by_sheet.values():
        header_index = _find_header_row(sheet_rows)
        if header_index is None:
            continue

        sheet_columns = [value.strip() for value in sheet_rows[header_index]]
        sheet_normalized_columns = [normalize_column_name(value) for value in sheet_columns]
        original_columns.extend(column for column in sheet_columns if column not in original_columns)
        normalized_columns.extend(
            column for column in sheet_normalized_columns if column not in normalized_columns
        )

        for values in sheet_rows[header_index + 1:]:
            if not any(value.strip() for value in values):
                continue
            row: dict[str, str] = {}
            for index, original_column in enumerate(sheet_columns):
                value = values[index].strip() if index < len(values) else ""
                normalized_column = sheet_normalized_columns[index]
                row[original_column] = value
                row[normalized_column] = value
            extracted_rows.append(row)

    return StructuredFile(
        file_id=doc.doc_id,
        filename=doc.filename,
        extraction_method="deterministic",
        columns=original_columns,
        original_columns=original_columns,
        normalized_columns=normalized_columns,
        rows=extracted_rows,
        row_count=len(extracted_rows),
    )


def _sheet_key(source_ref: str) -> str:
    parts = source_ref.rsplit(":row:", maxsplit=1)[0].split(":")
    return parts[-1] if len(parts) > 1 else "default"


def _find_header_row(rows: list[list[str]]) -> int | None:
    for index, row in enumerate(rows):
        if any(any(character.isalpha() for character in value) for value in row):
            return index
    return None


async def extract_unstructured(doc: ParsedDocument, llm_router: LLMRouter) -> StructuredFile:
    if doc.doc_type is DocumentType.DOCX:
        table_extraction = _extract_docx_tables(doc)
        if table_extraction is not None:
            prose_chunks = [chunk for chunk in doc.content_chunks if ":table:" not in chunk.source_ref]
            key_values = await _extract_key_values(doc, prose_chunks, llm_router)
            table_extraction.key_values = key_values
            if key_values:
                table_extraction.extraction_method = "deterministic_and_llm"
            return table_extraction

    return StructuredFile(
        file_id=doc.doc_id,
        filename=doc.filename,
        extraction_method="llm_assisted",
        key_values=await _extract_key_values(doc, doc.content_chunks, llm_router),
    )


def _extract_docx_tables(doc: ParsedDocument) -> StructuredFile | None:
    table_chunks = [chunk for chunk in doc.content_chunks if ":table:" in chunk.source_ref]
    if not table_chunks:
        return None

    table_doc = doc.model_copy(
        update={
            "doc_type": DocumentType.TXT,
            "content_chunks": table_chunks,
            "metadata": {"delimiter": "|"},
        }
    )
    extracted = extract_tabular(table_doc)
    return extracted if extracted.row_count else None


async def _extract_key_values(
    doc: ParsedDocument,
    chunks: list[object],
    llm_router: LLMRouter,
) -> list[KeyValueEntry]:
    content = _build_unstructured_content(chunks)
    if not content:
        return []

    prompt = load_prompt("extractor")
    try:
        response = await llm_router.generate(
            system=prompt.system,
            user=prompt.user_template.format(filename=doc.filename, content=content),
            model=prompt.model,
            temperature=prompt.temperature,
            response_mime_type=prompt.response_mime_type,
        )
    except Exception:
        return []
    return _parse_key_value_response(response)


def _build_unstructured_content(chunks: list[object]) -> str:
    content_parts: list[str] = []
    total_chars = 0
    for chunk in chunks:
        text = getattr(chunk, "text", "")
        if not isinstance(text, str):
            continue
        remaining = 3000 - total_chars
        if remaining <= 0:
            break
        content_parts.append(text[:remaining])
        total_chars += len(text[:remaining])
    return "\n".join(content_parts)


def _parse_key_value_response(response: str) -> list[KeyValueEntry]:
    cleaned = response.strip()
    if cleaned.startswith("```"):
        cleaned = "\n".join(cleaned.splitlines()[1:])
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError:
        return []

    raw_entries = payload.get("key_values", []) if isinstance(payload, dict) else payload
    if not isinstance(raw_entries, list):
        return []

    entries: list[KeyValueEntry] = []
    for raw_entry in raw_entries:
        if not isinstance(raw_entry, dict):
            continue
        try:
            entries.append(KeyValueEntry.model_validate(raw_entry))
        except ValueError:
            continue
    return entries


class StructuredDataStore:
    """In-memory structured file extractions for a single investigation job."""

    def __init__(self) -> None:
        self._files: dict[str, StructuredFile] = {}

    def add_file(self, structured_file: StructuredFile) -> None:
        self._files[structured_file.file_id] = structured_file

    def get_file(self, file_id: str) -> StructuredFile | None:
        return self._files.get(file_id)

    def list_files(self) -> list[StructuredFile]:
        return list(self._files.values())

    @property
    def file_count(self) -> int:
        return len(self._files)

    def save_to_json(self, job_id: str) -> Path:
        output_path = STRUCTURED_DATA_ROOT / job_id / "structured_data.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"files": [structured_file.model_dump(mode="json") for structured_file in self.list_files()]}
        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return output_path

    @classmethod
    def load_from_json(cls, job_id: str) -> StructuredDataStore:
        input_path = STRUCTURED_DATA_ROOT / job_id / "structured_data.json"
        payload = json.loads(input_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or not isinstance(payload.get("files"), list):
            raise ValueError("structured_data.json must contain a files list")

        store = cls()
        for raw_file in payload["files"]:
            store.add_file(StructuredFile.model_validate(raw_file))
        return store
