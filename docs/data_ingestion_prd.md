# PRD — Structured Data Extraction Layer

## Overview

Add a structured extraction layer to the document ingestion pipeline. Every uploaded file gets a normalized table representation alongside its raw content. This structured form accelerates downstream consumers (Cognee, the Investigation Agent, and future ML models) and gives auditors a clean tabular view of each file.

---

## Problem

Currently, all documents enter the system as raw text chunks. The LLM receives thousands of characters and must figure out what's a vendor, what's an amount, and what's a date — every single time. This is wasteful:

- CSV/XLSX files already have columns but they're flattened into text
- PDFs and DOCX contain key data points buried in prose
- The same concept appears under different column names across files (e.g., "BETRAG", "AMOUNT", "Rechnungsbetrag")
- Cognee and the LLM process raw text when structured data would be faster and cheaper
- Users cannot quickly scan the contents of a file without reading the raw dump

---

## Goals

- Extract structured data (amounts, dates, vendors, accounts, invoice numbers) from every file
- Preserve the original raw content alongside the structured version
- Provide a per-file toggle in the frontend: "Raw" vs "Table" view
- Speed up Cognee ingestion by feeding it structured fields
- Give the LLM both a structured summary and the raw text (separately)
- Enable future ML preprocessing without re-parsing files

---

## Non-Goals

- No database — structured data is stored as JSON in `/tmp/{job_id}/`
- No schema enforcement across files — each file gets its own column set
- No manual column mapping UI — normalization is automatic (hybrid approach)
- Not replacing the existing raw parser — this is additive

---

## Extraction Strategy: Hybrid

### Tier 1 — Deterministic (CSV, XLSX, TXT with delimiters)

Files that are already tabular:

- Take existing columns as-is
- Auto-detect headers from the first row
- Preserve original column names
- Normalize common synonyms (e.g., "BETRAG_EUR" → amount, "DATUM" → date) via a mapping table
- Output: rows as JSON objects with original + normalized keys

No LLM needed. Pure programmatic extraction.

### Tier 2 — LLM-Assisted (PDF, DOCX, unstructured TXT)

Files that contain prose, mixed content, or non-obvious structure:

- Send a representative sample (first 3000 chars) to the LLM
- Ask it to identify: what structured data points exist? What are the key fields?
- LLM returns a proposed schema (e.g., `[{field: "threshold_amount", value: "€10,000"}, ...]`)
- For PDFs/DOCX: extract key-value pairs (amounts, dates, thresholds, vendor names, regulatory limits)
- Paragraphs and narrative text stay as raw content — not forced into columns

The LLM decides what's extractable and what should remain as prose.

### Column Normalization

Different files may use different names for the same concept:

| File A column | File B column | Normalized name |
|---|---|---|
| BETRAG_EUR | BUCHUNGSBETRAG | amount |
| DATUM | WERTSTELLUNG | date |
| KREDITOR | LIEFERANT | vendor_id |
| RECHNUNGSNUMMER | BELEGNUMMER | invoice_number |

A deterministic mapping handles known synonyms. For unknowns, the LLM suggests the best normalized name.

---

## Storage

Structured data is stored per-investigation as a JSON file:

```
/tmp/{job_id}/structured_data.json
```

Schema:

```json
{
  "files": [
    {
      "file_id": "abc123",
      "filename": "Lieferantenbuchungen.txt",
      "extraction_method": "deterministic",
      "columns": ["vendor_id", "date", "amount", "invoice_number", "text"],
      "rows": [
        {"vendor_id": "209101", "date": "15.06.2025", "amount": "50000,00", "invoice_number": "ER900850", "text": "Beratungsleistungen"},
        ...
      ],
      "key_values": null
    },
    {
      "file_id": "def456",
      "filename": "Pruefungsplanung_JET_2025.docx",
      "extraction_method": "llm_assisted",
      "columns": null,
      "rows": null,
      "key_values": [
        {"field": "payment_threshold", "value": "€10,000", "context": "Two-signature rule for payments above this amount"},
        {"field": "audit_period", "value": "2025", "context": "Fiscal year under review"},
        {"field": "materiality", "value": "€50,000", "context": "Planning materiality for the engagement"}
      ]
    }
  ]
}
```

Two output modes per file:
- **Tabular files**: `columns` + `rows` (array of objects)
- **Prose files**: `key_values` (array of extracted data points with context)

---

## Pipeline Integration

### Current flow:

```
Upload → Parse → Chunks → Entity Extraction → Investigation
```

### New flow:

```
Upload → Parse → Structured Extraction → Chunks + Structured Data → Entity Extraction → Investigation
```

The structured data:
- Gets saved to JSON immediately after parsing
- Is passed to Cognee alongside raw text (enriched ingestion)
- Is available to the LLM as a "data summary" section in the investigation prompt
- Is served to the frontend via a new API endpoint

---

## API Changes

### `GET /investigations/{id}/files/{file_id}/structured`

Returns the structured representation of a single file.

Response for tabular files:
```json
{
  "file_id": "abc123",
  "filename": "Lieferantenbuchungen.txt",
  "extraction_method": "deterministic",
  "columns": ["vendor_id", "date", "amount", "invoice_number", "text"],
  "rows": [...],
  "row_count": 450
}
```

Response for prose files:
```json
{
  "file_id": "def456",
  "filename": "Pruefungsplanung_JET_2025.docx",
  "extraction_method": "llm_assisted",
  "key_values": [
    {"field": "payment_threshold", "value": "€10,000", "context": "Two-signature rule"}
  ]
}
```

### `GET /investigations/{id}/files/{file_id}/raw`

Returns the original raw content (existing chunks joined).

---

## Frontend Changes

In the investigation results, each file in the Investigation Steps tab gets a toggle:

```
[Raw] [Table]
```

- **Raw**: Shows the original text content (existing behavior)
- **Table**: Shows the structured extraction
  - For tabular files: renders an HTML table with columns and rows (paginated if large)
  - For prose files: renders a key-value list (field → value + context)

The toggle is per-file, allowing the user to switch back and forth.

---

## Benefits for Downstream Consumers

### Cognee
- Receives structured fields → builds more precise entity nodes
- Relationships are clearer when extracted from normalized columns vs. raw text

### Investigation Agent
- Gets a "structured summary" section in the prompt alongside raw content
- Can reference specific row numbers more accurately
- Flagged entries map directly to structured row data

### Future ML Model
- Structured JSON is directly usable as training features
- No re-parsing needed — just read the JSON
- Column normalization means features are consistent across files

### Quarterly Report Analysis (Video Mode)
- PDF extraction benefits from key-value extraction (revenue, EPS, growth %)
- Finance Agent gets cleaner input → better fact extraction

---

## Scope Boundaries

| In scope | Out of scope |
|---|---|
| CSV/XLSX/TXT: take columns as-is | Cross-file joins or relational queries |
| PDF/DOCX: LLM extracts key data points | Manual schema editing by user |
| Normalize common column synonyms | Persistent storage beyond /tmp |
| Per-file raw/table toggle in frontend | Full spreadsheet editing UI |
| JSON storage in /tmp/{job_id}/ | Database tables |
| Serve structured data via API | Real-time streaming of extraction |

---

## Architecture Constraints

Inherits all existing project constraints:
- No database — JSON file in `/tmp/{job_id}/`
- No persistent storage — lost on restart (acceptable for MVP)
- Single process — extraction runs in the same async pipeline
- In-memory job state — structured data reference stored in job record
