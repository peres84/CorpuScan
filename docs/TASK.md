# CorpuScan — Build Checklist

Tick boxes as steps complete. Ordered roughly by dependency, but parallel work is fine.

---

## 0. Project setup

- [x] Create monorepo layout: `/frontend`, `/backend`, `/docs`
- [x] `git init` and initial commit
- [x] Root `.gitignore` covering `node_modules/`, `.venv/`, `.env`, `/tmp/`, `*.mp4`, `dist/`, `__pycache__/`
- [x] Add backend `.env.example` with: `GEMINI_API_KEY`, `TAVILY_API_KEY`, `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID`, `HERA_API_KEY`, `CORS_ORIGINS`

---

## 1. Backend — FastAPI scaffold

- [x] `cd backend && uv init && uv add fastapi "uvicorn[standard]" pydantic pydantic-settings python-multipart httpx`
- [x] `uv add --dev ruff pytest pytest-asyncio`
- [x] `app/main.py` — FastAPI app, CORS for `http://localhost:5173` and Vercel domain
- [x] `app/config.py` — `Settings` via `pydantic-settings`, loads from `.env`
- [x] `app/jobs.py` — `JobStore` class wrapping a `dict[str, JobState]` with `create()`, `get()`, `update_step()`, `set_error()`, `set_done()`
- [x] `app/schemas.py` — pydantic models: `JobStatus`, `JobStep`, `GenerateResponse`, `Scene`, `SentenceTiming`
- [x] `GET /health` returns `{ "ok": true }`
- [x] Verify dev server: `uv run uvicorn app.main:app --reload --port 8000`

---

## 2. Backend — input ingestion

- [x] `uv add pypdf` (or `pdfplumber` if richer extraction needed)
- [x] `app/ingest.py` — `extract_pdf_text(file_bytes) -> str`
- [x] `app/integrations/tavily.py` — `search(query) -> list[Result]`, `extract(url) -> str`
- [x] `POST /generate` accepts `multipart/form-data`: optional `file` (UploadFile), optional `url` (str), optional `query` (str). Validates exactly one is provided.
- [x] Branch on input type: PDF → extract directly; URL → tavily.extract; query → tavily.search → top result → tavily.extract
- [x] Return `{ job_id }` immediately; kick off `asyncio.create_task(run_pipeline(job_id, source_text))`
- [x] Set initial step `ingest` and progress 10%

---

## 3. Backend — Finance Agent

- [x] `uv add google-genai`
- [x] `app/integrations/gemini.py` — thin client wrapper (`generate(system, user, model="gemini-2.5-pro")`)
- [x] `app/agents/finance.py` — load system prompt from `docs/agent-prompts.md`, call Gemini, return Q&A markdown string
- [x] On entry: `update_step("finance", progress=20)`
- [x] On exit: store `qa_markdown` in job state

---

## 4. Backend — Scripter Agent

- [x] `app/agents/scripter.py` — input `qa_markdown`, output validated JSON: `{ title: str, scenes: [{ title, narration }] × 4 }`
- [x] Force JSON mode (`response_mime_type="application/json"`)
- [x] Validate exactly 4 scenes, narration 50–100 words each
- [x] On entry: `update_step("scripter", progress=35)`
- [x] Store `script` in job state

---

## 5. Backend — ElevenLabs TTS with timestamps

- [x] `app/integrations/elevenlabs.py` — POST to `/v1/text-to-speech/{voice_id}/with-timestamps`
- [x] Concatenate 4 scene narrations into one input, separated by clear sentence boundaries (full stop + space)
- [x] Save audio bytes to `/tmp/{job_id}/voice.mp3`
- [x] Helper: `compute_sentence_timings(characters, char_start_times, char_end_times) -> list[SentenceTiming]`
- [x] Map sentences back to their scene index
- [x] On entry: `update_step("tts", progress=50)`
- [x] Store `audio_path` and `sentence_timings` in job state

---

## 6. Backend — Hera Agent (×4 in parallel)

- [x] `app/agents/hera.py` — for one scene: input `(scene, sentence_timings_for_scene)`, output Hera JSON dict
- [x] System prompt enforces brand colors and animation primitives
- [x] Run all 4 in parallel: `await asyncio.gather(*[hera_agent(s, t) for s, t in zip(scenes, timings)])`
- [x] Validate each returned JSON has required top-level keys
- [x] On entry: `update_step("hera_plan", progress=65)`
- [x] Store `scene_specs: list[dict]` in job state

---

## 7. Backend — Hera API render (×4 in parallel)

- [x] `app/integrations/hera.py` — `submit(spec) -> hera_job_id`, `poll(hera_job_id) -> {status, video_url?}`, `download(url) -> bytes`
- [x] Submit all 4 in parallel
- [x] Poll loop: every 3s, all 4 in parallel; exit when all 4 are `done`; timeout at 4 min
- [x] Make Hera timeout / retry behavior configurable via backend env
- [x] Download each MP4 to `/tmp/{job_id}/clip_{i}.mp4`
- [x] On entry: `update_step("hera_render", progress=75)`
- [x] Update `progress` incrementally as each clip finishes (75 → 90)

---

## 8. Backend — ffmpeg compose

- [x] `app/render.py` — `compose(clip_paths, audio_path, out_path)` calls ffmpeg via `subprocess`
- [x] Command: concat 4 clips → overlay `voice.mp3` → output H.264 + AAC, `-shortest`, `-pix_fmt yuv420p`
- [x] Output to `/tmp/{job_id}/final.mp4`
- [x] On entry: `update_step("compose", progress=92)`
- [x] On success: `set_done(video_url=f"/jobs/{job_id}/video")`

---

## 9. Backend — status & download endpoints

- [x] `GET /jobs/{job_id}` returns `JobStatus` JSON
- [x] `GET /jobs/{job_id}/video` streams `/tmp/{job_id}/final.mp4` with `media_type="video/mp4"`
- [x] Wrap `run_pipeline` in try/except: on any failure, `set_error(message)`, never crash the worker
- [x] Add `Content-Disposition: attachment` header on the video endpoint when `?download=1`

---

## 10. Backend — production polish

- [x] `Dockerfile`: `python:3.12-slim` base, `apt install ffmpeg`, copy + `uv sync --frozen`
- [x] Backend container packaging excludes local secrets and caches via `.dockerignore`
- [x] `app/main.py` — startup / shutdown hooks for cleanup of stale `/tmp/{job_id}/` (older than 30 min)
- [x] Global request timeout middleware (defensive)
- [x] Structured logging (`uvicorn --log-config`)
- [x] Fail fast with a clear error when `ffmpeg` is unavailable locally, before starting a new generation job

---

## 11. Frontend — Lovable build

- [x] Open Lovable, paste `docs/lovable-prompt.md` verbatim into a new project
- [x] Verify output uses Vite + React + TS + Tailwind only (reject if Lovable picks Next.js)
- [x] Pull generated repo locally to `/frontend`
- [x] `pnpm install`
- [x] Add `.env.local` with `VITE_API_BASE_URL=http://localhost:8000`
- [x] Confirm `tailwind.config.ts` has the brand colors as named tokens
- [x] Confirm Inter + JetBrains Mono are loaded

---

## 12. Frontend — wiring

- [x] `src/lib/api.ts` — typed wrappers for `POST /generate`, `GET /jobs/:id`, video URL builder
- [x] `src/hooks/useGenerate.ts` — mutation-style hook: `mutate({ file?, url?, query? }) → { jobId }`
- [x] `src/hooks/useJobStatus.ts` — polls `GET /jobs/:id` every 1500ms while `status !== "done" && status !== "error"`
- [x] `JobProgress.tsx` — maps backend `step` to one of 6 user-facing labels with visual indicators
- [x] Show live Hera render clip count in the frontend progress UI
- [x] `JobResult.tsx` — `<video>` + Download + "Generate another" buttons
- [x] Error banner component for failure states

---

## 13. End-to-end test

- [x] Add PDF comparison mode (1–4 PDFs), PDF-only templates, auto-branding overlays, and `16:9` / `9:16` output selection
- [ ] Run backend + frontend locally
- [ ] Upload a real quarterly report PDF (e.g. Apple 10-Q)
- [ ] Watch all 6 steps tick through
- [ ] Final video plays in the browser
- [ ] Total wall-clock time < 3 minutes
- [ ] MP4 download works

---

## 14. Deploy

- [ ] Backend: deploy Dockerfile to Railway or Fly. Set all env vars in dashboard.
- [ ] Confirm `https://<backend>.railway.app/health` returns 200
- [ ] Frontend: push repo to GitHub → import to Vercel → set `VITE_API_BASE_URL` to backend URL
- [ ] Update backend `CORS_ORIGINS` to include the Vercel domain
- [ ] Smoke test: full E2E from production frontend

---

## 15. Demo prep

- [ ] Pre-load a sample quarterly report — add "Try a sample report" link on the dashboard that submits the demo PDF
- [ ] Record a fallback demo video in case of API outage during the live demo
- [ ] Write a 60-second pitch
- [ ] Rehearse the full upload-to-playback flow on the demo machine
