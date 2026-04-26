# CorpuScan Frontend

React + Vite SPA that lets users submit a quarterly report (PDF upload, URL, or search query) and watch the backend pipeline turn it into a 2-minute executive video briefing. The UI polls the backend for job progress and streams the final MP4 when ready.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Framework | React 18 |
| Build tool | Vite 5 (SWC) |
| Language | TypeScript 5 (`strict: true`) |
| Styling | Tailwind CSS v3 |
| Component library | shadcn/ui (Radix UI primitives) |
| Routing | React Router v6 |
| Server state | TanStack Query v5 |
| Animations | Framer Motion |
| Forms | React Hook Form + Zod |
| Icons | Lucide React |
| Toasts | Sonner |
| Theme | Custom CSS variables (light + dark) |
| Package manager | pnpm (or bun) |
| Test runner | Vitest + Testing Library |
| Linter | ESLint 9 + typescript-eslint |

---

## Folder Structure

```
frontend/
├── index.html                  # HTML shell — fonts, meta tags, OG tags
├── src/
│   ├── main.tsx                # React root mount
│   ├── App.tsx                 # Router, providers (QueryClient, Theme, Tooltip, Toaster)
│   ├── index.css               # Tailwind directives + full CSS variable design system
│   ├── App.css                 # Vite default (mostly unused)
│   ├── vite-env.d.ts           # Vite env type declarations
│   │
│   ├── pages/
│   │   ├── Index.tsx           # Route "/" — re-exports Landing
│   │   ├── Landing.tsx         # Marketing landing page (Nav + Hero + HowItWorks + BottomCta + Footer)
│   │   ├── Dashboard.tsx       # Route "/dashboard" — GenerateForm
│   │   ├── JobPage.tsx         # Route "/dashboard/job/:jobId" — progress + result + error
│   │   └── NotFound.tsx        # Catch-all 404
│   │
│   ├── components/
│   │   ├── Nav.tsx             # Sticky top nav with logo + ThemeToggle + CTA
│   │   ├── Hero.tsx            # Landing hero section with InfiniteGrid background
│   │   ├── HowItWorks.tsx      # 4-step pipeline explainer with dismissable PromoCards
│   │   ├── BottomCta.tsx       # Landing page bottom call-to-action
│   │   ├── Footer.tsx          # Site footer
│   │   ├── GenerateForm.tsx    # Tabbed form: Upload PDF / From URL / Search query
│   │   ├── Dropzone.tsx        # Drag-and-drop PDF file picker
│   │   ├── JobProgress.tsx     # Step-by-step pipeline progress list + progress bar
│   │   ├── JobResult.tsx       # Video player + Download MP4 + Generate another
│   │   ├── ErrorBanner.tsx     # Red alert banner for API/pipeline errors
│   │   ├── InfiniteGrid.tsx    # Animated SVG grid with cursor-reveal accent layer
│   │   ├── NavLink.tsx         # Styled router link helper
│   │   ├── ThemeProvider.tsx   # Light/dark theme context (localStorage + prefers-color-scheme)
│   │   ├── ThemeToggle.tsx     # Sun/moon icon button
│   │   └── ui/                 # shadcn/ui primitives (accordion, button, dialog, tabs, …)
│   │
│   ├── hooks/
│   │   ├── useGenerate.ts      # POST /generate — returns { mutate, loading, error }
│   │   ├── useJobStatus.ts     # Polls GET /jobs/:id every 1.5 s until done or error
│   │   ├── use-mobile.tsx      # Breakpoint hook (≤768 px = mobile)
│   │   └── use-toast.ts        # Imperative toast helper (shadcn)
│   │
│   ├── lib/
│   │   ├── api.ts              # All fetch calls + TypeScript types for backend responses
│   │   └── utils.ts            # cn() — clsx + tailwind-merge helper
│   │
│   └── test/
│       ├── example.test.ts     # Vitest smoke test
│       └── setup.ts            # Testing Library jest-dom matchers
│
├── public/
│   ├── favicon.ico
│   ├── placeholder.svg
│   └── robots.txt
│
├── .env.local                  # Local env (git-ignored) — set VITE_API_BASE_URL
├── components.json             # shadcn/ui config
├── eslint.config.js            # ESLint flat config
├── postcss.config.js           # PostCSS (Tailwind + Autoprefixer)
├── package.json
└── vite.config.ts              # Vite config (SWC, path alias @/)
```

---

## Pages & Routes

| Route | Page | Description |
|---|---|---|
| `/` | `Landing` | Marketing page — hero, how it works, CTA |
| `/dashboard` | `Dashboard` | Generate form — upload / URL / search |
| `/dashboard/job/:jobId` | `JobPage` | Live progress polling, video result, error state |
| `*` | `NotFound` | 404 fallback |

---

## Data Flow

```
User submits form (GenerateForm)
        │
        ▼
useGenerate → POST /generate → { job_id }
        │
        ▼
navigate to /dashboard/job/:jobId
        │
        ▼
useJobStatus → polls GET /jobs/:id every 1.5 s
        │
        ├── status: pending / running → JobProgress (step list + progress bar)
        ├── status: done             → JobResult (video player + download)
        └── status: error            → ErrorBanner
```

The frontend never talks to Gemini, ElevenLabs, Hera, or Tavily directly. All third-party calls go through the backend.

---

## Design System

All colors are defined as CSS custom properties in `src/index.css` and consumed via Tailwind. The palette is editorial and financial — no gradients, no decorative imagery.

| Token | Light | Dark | Usage |
|---|---|---|---|
| `--background` | `#F9FAFB` | near-black | Page background |
| `--surface` | `#FFFFFF` | dark card | Cards, nav |
| `--primary` | `#111827` | light gray | Headings, body text |
| `--secondary` | `#374151` | mid gray | Subtext, labels |
| `--accent` | `#06B6D4` (cyan) | brighter cyan | CTAs, focus rings, progress |
| `--accent2` | `#8B5CF6` (violet) | violet | Sparingly |
| `--border` | `gray-200` | dark gray | Dividers, input borders |

Fonts loaded from Google Fonts: **Inter** (UI) and **JetBrains Mono** (code, labels, progress counters).

---

## Setup

### Prerequisites

- Node.js 18+
- pnpm (recommended) or bun

### Install & configure

```bash
cd frontend
pnpm install
echo "VITE_API_BASE_URL=http://localhost:8000" > .env.local
```

### Run dev server

```bash
pnpm dev
```

Runs on `http://localhost:8080` (configured in `vite.config.ts`).

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `VITE_API_BASE_URL` | `http://localhost:8000` | Backend base URL. Override for staging/production. |

---

## Critical Commands

```bash
# Start dev server (port 8080)
pnpm dev

# Production build → dist/
pnpm build

# Preview production build locally
pnpm preview

# Lint
pnpm lint

# Run tests (single pass)
pnpm test

# Run tests in watch mode
pnpm test:watch
```

---

## Adding shadcn/ui Components

The project uses shadcn/ui. To add a new primitive:

```bash
pnpm dlx shadcn@latest add <component-name>
```

Components are written to `src/components/ui/` and are fully owned — edit them freely.

---

## Code Conventions

- `strict: true` TypeScript — no `any`
- Tailwind utility classes only — no custom CSS files, no CSS modules
- Component files PascalCase (`Hero.tsx`, `JobProgress.tsx`)
- Hooks under `src/hooks/`, components under `src/components/`, pages under `src/pages/`
- `fetch` directly — no axios, no react-query for data fetching (TanStack Query is available but polling is done manually in `useJobStatus`)
- No global state library — `useState` + Context is enough
- Comments only when the *why* is non-obvious
