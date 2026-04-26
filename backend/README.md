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
│   │   ├── elevenlabs.py    # ElevenLabsClient — TTS with timestamps + sound effects
│   │   ├── hera.py          # HeraClient — submit / poll / download Hera renders
│   │   └── tavily.py        # TavilyClient — web search + URL content extraction
│   │
│   └── prompts/
│       ├── finance.yaml     # System prompt + user template for the Finance agent
│       ├── scripter.yaml    # System prompt + user template for the Scripter agent
│       └── hera.yaml        # System prompt + user template for the Hera agent
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
| `ELEVENLABS_API_KEY` | Yes | ElevenLabs API key |
| `ELEVENLABS_VOICE_ID` | Yes | ElevenLabs voice ID to use for narration |
| `HERA_API_KEY` | Yes | Hera Motion API key |
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
