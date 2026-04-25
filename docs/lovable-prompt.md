# Lovable Prompt — CorpuScan Frontend

> Copy everything between the two `---` lines below and paste it into Lovable as the initial project prompt. The output should be the full CorpuScan frontend ready to wire to the FastAPI backend.

---

Build a React + Vite + Tailwind CSS web app called **CorpuScan**.

## Product

CorpuScan is an AI tool that turns dense quarterly business reports into short, narrated executive explainer videos. Users upload a PDF, paste a URL, or type a query like "Apple Q4 2025 earnings". A FastAPI backend handles all AI agents, voice generation, motion graphics, and video rendering. The frontend's job is to orchestrate the upload, poll a job status endpoint, and play the final video.

## Tech stack — strict

- **React 18** + **TypeScript** (strict mode, no `any`)
- **Vite** (do **not** use Next.js)
- **Tailwind CSS** — only styling system, no other CSS libraries, no CSS modules
- **shadcn/ui** for components (Button, Card, Tabs, Progress, Toast)
- **lucide-react** for icons
- **React Router v6** for navigation
- `fetch` directly for API calls — no axios, no react-query (small custom hooks are fine)
- No state management library — `useState` and Context only

## Backend contract

`VITE_API_BASE_URL` env var points to the FastAPI backend (`http://localhost:8000` in dev).

| Method | Path                       | Description                                                              |
| ------ | -------------------------- | ------------------------------------------------------------------------ |
| `POST` | `/generate`                | `multipart/form-data`: optional `file`, optional `url`, optional `query` → `{ job_id: string }` |
| `GET`  | `/jobs/{job_id}`           | `{ status: "pending"|"running"|"done"|"error", step: string, progress: number, error?: string, video_url?: string }` |
| `GET`  | `/jobs/{job_id}/video`     | Streams the final MP4 — use directly as `<video src>`                    |

`step` from backend is one of: `ingest`, `finance`, `scripter`, `tts`, `hera_plan`, `hera_render`, `compose`, `done`. Map these to the 6 user-facing labels listed below.

## Branding — strict

Configure these as named colors in `tailwind.config.ts`:

| Token       | Hex       | Usage                                              |
| ----------- | --------- | -------------------------------------------------- |
| `primary`   | `#111827` | Headlines, body text, dark surfaces                |
| `secondary` | `#374151` | Sub-headings, muted text                           |
| `accent`    | `#06B6D4` | CTAs, links, progress bars, active states (cyan)   |
| `accent2`   | `#8B5CF6` | Highlights only — used **sparingly** (violet)      |
| `background`| `#F9FAFB` | Page background                                    |
| `surface`   | `#FFFFFF` | Cards, modals, navbar                              |
| `text`      | `#111827` | Default text color                                 |

### Typography

- Sans: **Inter** (Google Fonts) → `font-sans`
- Mono: **JetBrains Mono** (Google Fonts) → `font-mono` for any numeric / data display
- Weights: 400, 500, 600, 700

### Tone & shapes

- Editorial, restrained, financial. Think Financial Times or Bloomberg, not consumer SaaS.
- Generous whitespace.
- Border radius: `rounded-lg` (8px) default, `rounded-2xl` (16px) for hero / large cards.
- `shadow-sm` only — no heavy drop shadows.
- Borders: `border border-gray-200` for low-emphasis dividers.
- **No emojis anywhere in the UI.** No exclamation points in copy. No "Wow" or "Magic".

## Pages

### 1. `/` — Landing page

**Top nav** (sticky, white surface, bottom border `border-gray-200`):
- Left: wordmark **CorpuScan** in `font-semibold text-primary`. No icon.
- Right: single button **Start now** → `/dashboard` (accent background, white text, `rounded-lg px-4 py-2`)

**Hero section** (centered, max-width-4xl, py-24):
- Eyebrow: `AI BRIEFINGS FOR BUSINESS REPORTS` (text-accent, uppercase, tracking-wider, text-xs, font-semibold)
- Headline (`text-5xl md:text-6xl font-bold text-primary leading-tight`):
  > Turn quarterly reports into 2-minute video briefings.
- Sub (`text-xl text-secondary`):
  > Upload a report, get a boardroom-ready explainer video in under 3 minutes.
- Primary CTA: **Start now** (accent bg, white text, `text-lg px-6 py-3 rounded-lg`) → `/dashboard`
- Secondary text link: **See how it works** → smooth-scroll to `#how`

**Trust strip** (small, secondary text, centered, mt-16):
> For investor relations · Finance · Strategy · Internal communications

**"How it works"** section (`id="how"`, py-24):
- Section heading: `How it works` (text-3xl font-semibold text-primary)
- 4 cards in a row (stack on mobile), each on a `bg-surface` card with `border border-gray-200 rounded-2xl p-6`:
  1. **Upload** — Drop a quarterly report PDF, paste a URL, or search a query.
  2. **Extract** — A finance agent finds the signal in the noise.
  3. **Narrate** — A scripter agent writes a 4-scene voiceover.
  4. **Render** — Motion graphics and voice combine into a 2-minute video.
- Each card has a small accent-colored numeral `01` / `02` / `03` / `04` above its title in `font-mono text-accent text-sm`.

**Bottom CTA** (centered, py-16):
- Surface card with **Start now** button.

**Footer** (centered, py-8, text-xs text-secondary):
> CorpuScan · Built at BigTech Berlin Hackathon 2026

### 2. `/dashboard` — Generate page

- Top nav (same as landing).
- Centered card: `max-w-2xl mx-auto bg-surface rounded-2xl shadow-sm p-8 mt-12`
- Card heading: **Generate a briefing video** (text-2xl font-semibold text-primary)
- Card sub: `Choose how you want to provide the report.` (text-secondary mt-1)

**Tab group** using shadcn `Tabs` (3 tabs):

1. **Upload PDF**
   - Drag-and-drop dropzone (`border-2 border-dashed border-gray-300 rounded-lg p-12 text-center`, hover state: `border-accent bg-accent/5`)
   - Accepts `.pdf` only
   - Shows filename + file size when chosen
   - "Remove" link to clear

2. **From URL**
   - Single text input, full width, `placeholder="https://investor.apple.com/...10-Q.pdf"`
   - Validates `https://` prefix

3. **Search**
   - Single text input, full width, `placeholder="Apple Q4 2025 earnings"`
   - Helper text below: `We'll find and read the most relevant report.`

Below tabs:
- Large **Generate video** button (accent bg, full width, `text-lg py-3 rounded-lg`, disabled until input is valid).
- On click: call `POST /generate` with `multipart/form-data`. On success, navigate to `/dashboard/job/:jobId`.

Optional: small text link below the button: `Try a sample report` — submits a hardcoded URL or a built-in sample.

### 3. `/dashboard/job/:jobId` — Progress / result page

- Top nav (same).
- Centered card, same style as dashboard.
- Polls `GET /jobs/:jobId` every 1500ms while `status !== "done" && status !== "error"`.

**While generating** (`status === "pending" | "running"`):
- Heading: **Generating your briefing**
- Sub: `This usually takes 1 to 3 minutes.` (text-secondary)
- **Pipeline indicator** — vertical list of 6 steps, each row: `[indicator] [label] [optional spinner]`
  - Indicator states: pending = `bg-gray-200` empty circle · running = pulsing accent dot · done = accent checkmark
  - 6 labels (map backend `step` → label):
    | Backend step              | UI label                  |
    | ------------------------- | ------------------------- |
    | `ingest`                  | Reading source material   |
    | `finance`                 | Extracting key facts      |
    | `scripter`                | Writing voiceover script  |
    | `tts`                     | Recording narration       |
    | `hera_plan`, `hera_render`| Generating motion graphics |
    | `compose`                 | Rendering final video     |
- Progress bar (full width, `bg-gray-200`, fill `bg-accent`, `rounded-full h-2`) — value from `progress` (0–100).
- Cancel link below: navigates back to `/dashboard`.

**When done** (`status === "done"`):
- Replace card with `<video controls src={video_url} className="w-full rounded-lg" />`
- Below: two buttons in a row:
  - **Download MP4** (accent bg, white text)
  - **Generate another** (outline: `border border-gray-300 text-primary`) → `/dashboard`

**When error** (`status === "error"`):
- Red banner (`bg-red-50 border border-red-200 text-red-900 p-4 rounded-lg`) with the `error` message
- **Try again** button → `/dashboard`

## Components to build

Under `src/components/`:
- `Nav.tsx`
- `Hero.tsx`
- `HowItWorks.tsx`
- `BottomCta.tsx`
- `Footer.tsx`
- `GenerateForm.tsx` — the tabbed input
- `Dropzone.tsx`
- `JobProgress.tsx` — the 6-step indicator + progress bar
- `JobResult.tsx` — video player + download / regenerate buttons
- `ErrorBanner.tsx`

Under `src/hooks/`:
- `useGenerate.ts` — `mutate({ file?, url?, query? }) → { jobId }`
- `useJobStatus.ts` — `(jobId) → { status, step, progress, error?, videoUrl? }`, polls every 1500ms

Under `src/lib/`:
- `api.ts` — typed wrappers around the 3 endpoints, reads `VITE_API_BASE_URL`

Under `src/pages/`:
- `Landing.tsx`
- `Dashboard.tsx`
- `JobPage.tsx`

## Quality bar

- Mobile responsive (single column under `md`)
- Keyboard accessible (visible focus rings in accent color)
- Loading and empty states for everything
- The whole app should feel like a tool a CFO would use, not a consumer app
- No emojis. No marketing fluff. Editorial copy, short sentences.

---
