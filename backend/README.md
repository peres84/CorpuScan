# CorpuScan Backend

FastAPI backend that turns a quarterly report (PDF, URL, or search query) into a 2-minute executive video briefing. It orchestrates three AI agents, text-to-speech synthesis, AI-generated motion graphics, and a final ffmpeg composition pass — all in a single async pipeline.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Web framework | FastAPI + Uvicorn |
| Language | Python 3.12+ |
| AI / LLM | Google Gemini 2.5 Pro (`google-genai`) |
| TTS + Sound FX | ElevenLabs (`eleven_multilingual_v2`) |
| Motion graphics | Hera Motion API |
| Web search / extract | Tavily |
| PDF parsing | pypdf |
| HTTP client | httpx (async everywhere) |
| Config / validation | Pydantic v2 + pydantic-settings |
| Video composition | ffmpeg (system binary) |
| Package manager | uv |
| Linter / formatter | ruff |
| Test runner | pytest + pytest-asyncio |

---

## Folder Structure

```
backend/
├── app/
│   ├── main.py              # FastAPI app, routes, lifespan, middleware
│   ├── pipeline.py          # End-to-end async pipeline (orchestrates all stages)
│   ├── jobs.py              # In-memory JobStore + JobRecord dataclass
│   ├── schemas.py           # Pydantic models: JobStatus, Script, Scene, SlideChunk, …
│   ├── config.py            # Settings loaded from .env via pydantic-settings
│   ├── ingest.py            # PDF text extraction (pypdf)
│   ├── render.py            # ffmpeg composition (intro + scenes + audio → final.mp4)
│   ├── logging_utils.py     # Coloured stage tags for structured log output
│   │
│   ├── agents/
│   │   ├── finance.py       # Finance agent: extracts key facts from source text
│   │   ├── scripter.py      # Scripter agent: turns facts into a 4-scene JSON script
│   │   ├── hera.py          # Hera agent: converts each scene into a Hera motion spec
│   │   └── _prompts.py      # YAML prompt loader (cached with lru_cache)
│   │
│   ├── integrations/
│   │   ├── gemini.py        # GeminiClient — async wrapper around google-genai
│   │   ├── openai.py        # OpenAIClient — async OpenAI chat completions
│   │   ├── llm_router.py    # LLMRouter — OpenAI primary, Gemini fallback
│   │   ├── elevenlabs.py    # ElevenLabsClient — TTS with timestamps + sound effects
│   │   ├── hera.py          # HeraClient — submit / poll / download Hera renders
│   │   └── tavily.py        # TavilyClient — web search + URL content extraction
│   │
│   ├── investigation/
│   │   ├── __init__.py
│   │   ├── models.py        # ParsedDocument, ContentChunk, DocumentType
│   │   ├── parsers.py       # TXT, PDF, XLSX, CSV, DOCX, GDPdU index.xml parsers
│   │   ├── chunker.py       # Content chunking with overlap
│   │   ├── scanner.py       # Recursive directory scanner
│   │   ├── evidence_store.py # EvidenceStore, Finding, Entity, EvidenceReference
│   │   ├── entities.py      # LLM-powered entity extraction
│   │   ├── graph.py         # DocumentGraph — nodes + edges via shared entities
│   │   ├── agent.py         # InvestigationAgent — DFS over document graph
│   │   ├── buffer.py        # InvestigationBufferRow, InvestigationState
│   │   ├── pipeline.py      # Investigation pipeline orchestration + job store
│   │   ├── prioritization.py # Document priority scoring + smart start selection
│   │   ├── report.py        # ReportGenerator + InvestigationReport model
│   │   ├── classifier.py    # Rule-based fraud signal classifier
│   │   └── routes.py        # FastAPI investigation endpoints
│   │
│   └── prompts/
│       ├── finance.yaml     # System prompt + user template for the Finance agent
│       ├── scripter.yaml    # System prompt + user template for the Scripter agent
│       ├── hera.yaml        # System prompt + user template for the Hera agent
│       ├── investigator.yaml # System prompt for the Investigation agent
│       └── report_generator.yaml # System prompt for report generation
│
├── tests/
│   ├── test_parsers.py              # Document parsing tests
│   ├── test_llm_router.py           # LLM router + OpenAI client tests
│   ├── test_evidence_store.py       # Evidence store + graph + entity extraction
│   ├── test_investigation_agent.py  # DFS agent tests
│   ├── test_investigation_pipeline.py # Full pipeline tests
│   ├── test_investigation_api.py    # API endpoint tests
│   ├── test_report_generation.py    # Report generation tests
│   ├── test_prioritization.py       # Document prioritization tests
│   ├── test_classifier.py           # Fraud classifier tests
│   └── test_integration_fraud_detection.py # End-to-end fraud detection
│
├── src/corpuscan_backend/   # Package entry point (uv_build)
├── .env                     # Local secrets (git-ignored)
├── .env.example             # Template — copy to .env and fill in keys
├── logging.yaml             # Python logging config (dictConfig format)
├── pyproject.toml           # Project metadata + dependencies
├── requirements.txt         # Pinned requirements (generated from uv.lock)
├── Dockerfile               # Container image definition
└── uv.lock                  # Locked dependency tree
```

---

## Pipeline Overview

```
Input (PDF / URL / query)
        │
        ▼
   [INGEST]  extract_pdf_text  /  Tavily search+extract
        │
        ▼
  [FINANCE]  Gemini → markdown Q&A list (top 6–10 facts)
        │
        ▼
 [SCRIPTER]  Gemini → JSON { title, scenes[4] }
        │
        ▼
    [TTS]    ElevenLabs → voice MP3 + char-level timestamps
             ElevenLabs → intro typing sound effect  (parallel)
        │
        ▼
[HERA PLAN]  Gemini × 4 (one per scene) → Hera motion specs  (parallel)
        │
        ▼
[HERA RENDER] Hera API × 5 (intro + 4 scenes) → MP4 clips  (parallel, with retry)
        │
        ▼
 [COMPOSE]   ffmpeg concat filter → final.mp4
        │
        ▼
   /jobs/{id}/video  (streamed to browser)
```

Job state is held in an in-memory `JobStore` (a plain `dict`). There is no database, no queue, and no persistent file storage — intermediate files live in `/tmp/{job_id}/` and are cleaned up on startup and after 30 minutes.

---

## Setup

### Prerequisites

- Python 3.12+
- [`uv`](https://docs.astral.sh/uv/) — fast Python package manager
- `ffmpeg` on your `PATH`

```bash
# macOS
brew install ffmpeg

# Debian / Ubuntu
apt install ffmpeg
```

### Install & configure

```bash
cd backend
uv sync
cp .env.example .env
# Open .env and fill in all five keys (see Environment Variables below)
```

### Run

```bash
uv run uvicorn app.main:app --reload --port 8000
```

The API will be available at `http://localhost:8000`.

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GEMINI_API_KEY` | Yes | Google AI Studio key |
| `TAVILY_API_KEY` | Yes | Tavily search/extract key |
| `ELEVENLABS_API_KEY` | Video mode | ElevenLabs API key |
| `ELEVENLABS_VOICE_ID` | Video mode | ElevenLabs voice ID to use for narration |
| `HERA_API_KEY` | Video mode | Hera Motion API key |
| `OPENAI_KEY` | Investigation mode | OpenAI API key (primary LLM for investigation) |
| `OPENAI_MODEL` | No | OpenAI model name. Defaults to `gpt-4o` |
| `COGNEE_ENABLED` | No | Enable Cognee knowledge memory layer (default: `false`) |
| `COGNEE_STORAGE_PATH` | No | Local storage for Cognee data (default: `/tmp/cognee`) |
| `COGNEE_MODEL` | No | LLM model for Cognee entity extraction (default: `gpt-4o`) |
| `HERA_BASE_URL` | No | Defaults to `https://api.hera.video/v1` |
| `HERA_RENDER_TIMEOUT_SECONDS` | No | Defaults to `240` |
| `HERA_RENDER_RETRY_ATTEMPTS` | No | Defaults to `2` |
| `HERA_POLL_INTERVAL_SECONDS` | No | Defaults to `3.0` |
| `CORS_ORIGINS` | No | Comma-separated allowed origins. Defaults to localhost:5173 and localhost:8080 |

---

## API Endpoints

### `GET /health`
Returns `{"ok": true}`. Use for liveness checks.

### `POST /generate`
Accepts `multipart/form-data`. Provide **exactly one** of:

| Field | Type | Description |
|---|---|---|
| `file` | File | PDF upload (max 25 MB) |
| `url` | string | URL to extract content from |
| `query` | string | Search query — Tavily finds and extracts the top result |

Returns `{"job_id": "<uuid>"}` immediately. The pipeline runs in the background.

### `GET /jobs/{job_id}`
Poll for job status. Returns a `JobStatus` object:

```json
{
  "status": "running",
  "step": "hera_render",
  "progress": 80,
  "error": null,
  "video_url": null,
  "hera_completed_clips": 2,
  "hera_total_clips": 4,
  "hera_attempt": 1,
  "hera_max_attempts": 2
}
```

`status` values: `pending` | `running` | `done` | `error`  
`step` values: `ingest` → `finance` → `scripter` → `tts` → `hera_plan` → `hera_render` → `compose` → `done`

### `GET /jobs/{job_id}/video`
Streams the final MP4. Add `?download=1` to trigger a file download instead of inline playback.

---

### Investigation Endpoints

### `POST /investigate`
Accepts `multipart/form-data`. Upload multiple financial documents for AI-driven investigation.

| Field | Type | Description |
|---|---|---|
| `files` | File[] | One or more documents (CSV, TXT, XLSX, PDF, DOCX, XML). Max 50 files, 50 MB each. |
| `priority_doc_ids` | string (optional) | Comma-separated doc IDs to prioritize |

Returns `{"job_id": "<uuid>"}`. The investigation pipeline runs in the background.

### `GET /investigations/{id}`
Poll investigation status:

```json
{
  "status": "running",
  "step": "investigate",
  "progress": 65,
  "error": null
}
```

`status`: `pending` | `running` | `done` | `error`  
`step`: `parse` → `build_graph` → `investigate` → `report` → `done`

### `GET /investigations/{id}/findings`
Returns findings with evidence references:

```json
[
  {
    "finding_id": "f001",
    "finding_text": "Suspicious round amounts to vendor 209101",
    "evidence": [{"doc_id": "...", "location": "row:45", "passage": "...", "confidence": 0.85}],
    "fraud_likelihood": 0.92
  }
]
```

### `GET /investigations/{id}/buffer`
Returns the step-by-step investigation history (each document analyzed).

### `GET /investigations/{id}/evidence/{finding_id}`
Returns detailed evidence for a specific finding.

### `GET /investigations/{id}/report`
Returns the full structured report (only available when status is `done`).

---

## Critical Commands

```bash
# Start dev server
uv run uvicorn app.main:app --reload --port 8000

# Lint
uv run ruff check

# Format
uv run ruff format

# Run tests
uv run pytest

# Add a dependency
uv add <package>

# Sync dependencies after pulling
uv sync
```

---

## Editing Agent Prompts

All three agent prompts live in `app/prompts/` as YAML files. Edit the YAML — do not touch the Python agent files for prompt changes.

Each YAML declares:

```yaml
model: gemini-2.5-pro
temperature: 0.2
response_mime_type: application/json   # omit for plain text
system: |
  <system prompt>
user_template: |
  <user message with {placeholders}>
```

Prompts are loaded once at startup and cached. Restart the server after editing them.

---

## Docker

```bash
# Build
docker build -t corpuscan-backend .

# Run (pass your .env file)
docker run --env-file .env -p 8000:8000 corpuscan-backend
```

---

## Architecture Constraints (MVP)

These are intentional — do not work around them:

- **No database** — job state is an in-memory dict; it resets on restart.
- **No queue** — pipelines run via `asyncio.create_task`; only one job runs at a time.
- **No persistent storage** — files live in `/tmp/{job_id}/`; cleaned up after 30 min.
- **No auth** — public demo endpoint.
- **No frontend-to-third-party calls** — all API keys stay server-side.
