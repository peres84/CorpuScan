# CorpuScan — Build Checklist

Tick boxes as steps complete. Ordered roughly by dependency, but parallel work is fine.

---

## 0. Project setup

- [ ] Create monorepo layout: `/frontend`, `/backend`, `/docs`
- [ ] `git init` and initial commit
- [ ] Root `.gitignore` covering `node_modules/`, `.venv/`, `.env`, `/tmp/`, `*.mp4`, `dist/`, `__pycache__/`
- [ ] Add backend `.env.example` with: `GEMINI_API_KEY`, `TAVILY_API_KEY`, `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID`, `HERA_API_KEY`, `CORS_ORIGINS`

---

## 1. Backend — FastAPI scaffold

- [ ] `cd backend && uv init && uv add fastapi "uvicorn[standard]" pydantic pydantic-settings python-multipart httpx`
- [ ] `uv add --dev ruff pytest pytest-asyncio`
- [ ] `app/main.py` — FastAPI app, CORS for `http://localhost:5173` and Vercel domain
- [ ] `app/config.py` — `Settings` via `pydantic-settings`, loads from `.env`
- [ ] `app/jobs.py` — `JobStore` class wrapping a `dict[str, JobState]` with `create()`, `get()`, `update_step()`, `set_error()`, `set_done()`
- [ ] `app/schemas.py` — pydantic models: `JobStatus`, `JobStep`, `GenerateResponse`, `Scene`, `SentenceTiming`
- [ ] `GET /health` returns `{ "ok": true }`
- [ ] Verify dev server: `uv run uvicorn app.main:app --reload --port 8000`

---

## 2. Backend — input ingestion

- [ ] `uv add pypdf` (or `pdfplumber` if richer extraction needed)
- [ ] `app/ingest.py` — `extract_pdf_text(file_bytes) -> str`
- [ ] `app/integrations/tavily.py` — `search(query) -> list[Result]`, `extract(url) -> str`
- [ ] `POST /generate` accepts `multipart/form-data`: optional `file` (UploadFile), optional `url` (str), optional `query` (str). Validates exactly one is provided.
- [ ] Branch on input type: PDF → extract directly; URL → tavily.extract; query → tavily.search → top result → tavily.extract
- [ ] Return `{ job_id }` immediately; kick off `asyncio.create_task(run_pipeline(job_id, source_text))`
- [ ] Set initial step `ingest` and progress 10%

---

## 3. Backend — Finance Agent

- [ ] `uv add google-genai`
- [ ] `app/integrations/gemini.py` — thin client wrapper (`generate(system, user, model="gemini-2.5-pro")`)
- [ ] `app/agents/finance.py` — load system prompt from `docs/agent-prompts.md`, call Gemini, return Q&A markdown string
- [ ] On entry: `update_step("finance", progress=20)`
- [ ] On exit: store `qa_markdown` in job state

---

## 4. Backend — Scripter Agent

- [ ] `app/agents/scripter.py` — input `qa_markdown`, output validated JSON: `{ title: str, scenes: [{ title, narration }] × 4 }`
- [ ] Force JSON mode (`response_mime_type="application/json"`)
- [ ] Validate exactly 4 scenes, narration 50–100 words each
- [ ] On entry: `update_step("scripter", progress=35)`
- [ ] Store `script` in job state

---

## 5. Backend — ElevenLabs TTS with timestamps

- [ ] `app/integrations/elevenlabs.py` — POST to `/v1/text-to-speech/{voice_id}/with-timestamps`
- [ ] Concatenate 4 scene narrations into one input, separated by clear sentence boundaries (full stop + space)
- [ ] Save audio bytes to `/tmp/{job_id}/voice.mp3`
- [ ] Helper: `compute_sentence_timings(characters, char_start_times, char_end_times) -> list[SentenceTiming]`
- [ ] Map sentences back to their scene index
- [ ] On entry: `update_step("tts", progress=50)`
- [ ] Store `audio_path` and `sentence_timings` in job state

---

## 6. Backend — Hera Agent (×4 in parallel)

- [ ] `app/agents/hera.py` — for one scene: input `(scene, sentence_timings_for_scene)`, output Hera JSON dict
- [ ] System prompt enforces brand colors and animation primitives
- [ ] Run all 4 in parallel: `await asyncio.gather(*[hera_agent(s, t) for s, t in zip(scenes, timings)])`
- [ ] Validate each returned JSON has required top-level keys
- [ ] On entry: `update_step("hera_plan", progress=65)`
- [ ] Store `scene_specs: list[dict]` in job state

---

## 7. Backend — Hera API render (×4 in parallel)

- [ ] `app/integrations/hera.py` — `submit(spec) -> hera_job_id`, `poll(hera_job_id) -> {status, video_url?}`, `download(url) -> bytes`
- [ ] Submit all 4 in parallel
- [ ] Poll loop: every 3s, all 4 in parallel; exit when all 4 are `done`; timeout at 4 min
- [ ] Download each MP4 to `/tmp/{job_id}/clip_{i}.mp4`
- [ ] On entry: `update_step("hera_render", progress=75)`
- [ ] Update `progress` incrementally as each clip finishes (75 → 90)

---

## 8. Backend — ffmpeg compose

- [ ] `app/render.py` — `compose(clip_paths, audio_path, out_path)` calls ffmpeg via `subprocess`
- [ ] Command: concat 4 clips → overlay `voice.mp3` → output H.264 + AAC, `-shortest`, `-pix_fmt yuv420p`
- [ ] Output to `/tmp/{job_id}/final.mp4`
- [ ] On entry: `update_step("compose", progress=92)`
- [ ] On success: `set_done(video_url=f"/jobs/{job_id}/video")`

---

## 9. Backend — status & download endpoints

- [ ] `GET /jobs/{job_id}` returns `JobStatus` JSON
- [ ] `GET /jobs/{job_id}/video` streams `/tmp/{job_id}/final.mp4` with `media_type="video/mp4"`
- [ ] Wrap `run_pipeline` in try/except: on any failure, `set_error(message)`, never crash the worker
- [ ] Add `Content-Disposition: attachment` header on the video endpoint when `?download=1`

---

## 10. Backend — production polish

- [ ] `Dockerfile`: `python:3.12-slim` base, `apt install ffmpeg`, copy + `uv sync --frozen`
- [ ] `app/main.py` — startup / shutdown hooks for cleanup of stale `/tmp/{job_id}/` (older than 30 min)
- [ ] Global request timeout middleware (defensive)
- [ ] Structured logging (`uvicorn --log-config`)

---

## 11. Frontend — Lovable build

- [ ] Open Lovable, paste `docs/lovable-prompt.md` verbatim into a new project
- [ ] Verify output uses Vite + React + TS + Tailwind only (reject if Lovable picks Next.js)
- [ ] Pull generated repo locally to `/frontend`
- [ ] `pnpm install`
- [ ] Add `.env.local` with `VITE_API_BASE_URL=http://localhost:8000`
- [ ] Confirm `tailwind.config.ts` has the brand colors as named tokens
- [ ] Confirm Inter + JetBrains Mono are loaded

---

## 12. Frontend — wiring

- [ ] `src/lib/api.ts` — typed wrappers for `POST /generate`, `GET /jobs/:id`, video URL builder
- [ ] `src/hooks/useGenerate.ts` — mutation-style hook: `mutate({ file?, url?, query? }) → { jobId }`
- [ ] `src/hooks/useJobStatus.ts` — polls `GET /jobs/:id` every 1500ms while `status !== "done" && status !== "error"`
- [ ] `JobProgress.tsx` — maps backend `step` to one of 6 user-facing labels with visual indicators
- [ ] `JobResult.tsx` — `<video>` + Download + "Generate another" buttons
- [ ] Error banner component for failure states

---

## 13. End-to-end test

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
