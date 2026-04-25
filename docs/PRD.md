# CorpusScan — Product Requirements Document

## Problem

Quarterly reports, investor updates, and board memos are dense and routinely unread. Decision-makers, IR teams, and analysts skim 60-page PDFs hunting for the 5 numbers that actually matter. The signal is buried, and the medium (PDF) is the wrong fit for how executives consume information today.

## Solution

An AI analyst-producer that ingests a business document and produces a 1–2 minute narrated explainer video. The product makes the editorial decisions an analyst would: what matters, what to skip, what story to tell, what numbers to surface.

## What the AI is actually doing

- Finding the signal in noisy documents
- Deciding the storyline
- Choosing which numbers matter
- Simplifying charts and tables into plain English
- Turning each insight into a scene with motion graphics and narration

## Target users

- **Investor relations teams** — turning quarterly disclosures into shareholder-friendly briefings
- **Founders & finance teams** — packaging investor updates
- **Internal communications teams** — translating board memos for a wider audience
- **Strategy & analyst teams** — fast comprehension of competitor filings

## Core flow

1. **Landing page** (`/`) — value prop, one CTA: **Start now**. No signup.
2. **Dashboard** (`/dashboard`) — three input modes (tabbed):
   - Upload a PDF
   - Paste a URL — Tavily fetches and extracts the page
   - Type a query like "Apple Q4 2025 earnings" — Tavily searches, picks the top result, extracts it
3. **Generation** (`/dashboard/job/:jobId`) — single-page progress view. User sees a 6-step pipeline indicator with the active step pulsing. ~60–180s total.
4. **Result** — embedded `<video>` player + **Download MP4** button.

## Pipeline (in-product AI)

| #   | Stage           | Tool                        | Input                      | Output                                    |
| --- | --------------- | --------------------------- | -------------------------- | ----------------------------------------- |
| 1   | Ingest          | `pypdf` / `pdfplumber` + Tavily | PDF / URL / query     | Cleaned plain text                        |
| 2   | Finance Agent   | Gemini 2.5 Pro              | Plain text                 | Markdown Q&A list (6–10 entries)          |
| 3   | Scripter Agent  | Gemini 2.5 Pro              | Q&A markdown               | JSON: `{ title, scenes: [4× {title, narration}] }` |
| 4   | Voiceover       | ElevenLabs TTS w/ timestamps | Concatenated narration    | `voice.mp3` + character-level timings     |
| 5   | Hera Agent ×4   | Gemini 2.5 Pro (parallel)   | Scene + sentence timings   | Hera-format animation JSON                |
| 6   | Render scenes   | Hera API (parallel submit + poll) | 4× JSON              | 4× MP4 clips                              |
| 7   | Compose         | ffmpeg                      | 4× clips + voice.mp3       | `final.mp4`                               |
| 8   | Deliver         | FastAPI streaming response  | `final.mp4`                | Browser playback + download               |

Detailed system prompts: [docs/agent-prompts.md](docs/agent-prompts.md).

## Backend API contract

| Method | Path                       | Description                                                              |
| ------ | -------------------------- | ------------------------------------------------------------------------ |
| `POST` | `/generate`                | `multipart/form-data`: `file?`, `url?`, `query?` → `{ job_id }`          |
| `GET`  | `/jobs/{job_id}`           | `{ status, step, progress (0-100), error?, video_url? }`                 |
| `GET`  | `/jobs/{job_id}/video`     | Streams the final MP4                                                    |
| `GET`  | `/health`                  | Liveness check                                                           |

`status` values: `pending` · `running` · `done` · `error`
`step` values: `ingest` · `finance` · `scripter` · `tts` · `hera_plan` · `hera_render` · `compose` · `done`

## Non-goals (MVP)

- User accounts / auth
- Saved video history or library
- Custom voice cloning
- Multi-language output
- Live editing of the generated video
- Whitelabel / enterprise features
- Mobile-first design (responsive is enough; the user is on a laptop)
- Payment / billing
- Analytics

## Constraints

- Total wall-clock time from upload to playable video: **< 3 minutes**
- Final video length: **≤ 2 minutes** (4 scenes × ~30s)
- Backend = single FastAPI process. No DB, no queue, no Redis.
- All third-party API keys server-side only.
- Frontend uses React + Vite + Tailwind, no other CSS frameworks.

## Branding

See [docs/branding.md](docs/branding.md). Color tokens, typography, voice. Strict adherence — this product visually reads as a tool a CFO would use.

## Success metric (demo)

> Upload Apple's Q4 2025 10-Q PDF → get a 2-minute explainer video that correctly identifies the top 6 financial talking points, in under 3 minutes wall-clock.

## Out-of-scope risks (acknowledged but not addressed)

- Hera schema may evolve — Hera Agent prompt may need adjustment
- Long PDFs (>80k tokens) may exceed Gemini context — chunk-and-summarize is a v2 problem
- ElevenLabs timing precision varies by voice — pick a stable voice for demo
- ffmpeg availability on the host (must be in Docker base image / Railway buildpack)
