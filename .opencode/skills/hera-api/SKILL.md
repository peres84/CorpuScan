---
name: hera-api
description: Use this skill when integrating the Hera Motion API (https://api.hera.video/v1) — building API clients to submit/poll/download motion-graphics videos, OR writing high-quality prompts for Hera. Covers the full REST surface, request/response shapes, status semantics, common pitfalls, and a prompting playbook with the bracketed-timing syntax that produces frame-accurate animations. Pair with TTS character-level alignment (e.g. ElevenLabs `with-timestamps`) when the video must lip-sync to a voice-over.
---

# Hera Motion API — integration & prompting guide

The Hera Motion API generates motion-graphics videos from a **single text
prompt** plus an output configuration. There is no JSON timeline, no
per-element schema, no scene graph — the prompt is the program.

This skill has two halves:

1. **API mechanics** — endpoints, auth, request/response, polling, errors.
2. **Prompting playbook** — the bracketed-timing syntax that produces
   frame-accurate motion graphics, plus how to derive timings from a TTS
   transcript when the video has voice-over.

Hera docs index: <https://docs.hera.video/llms.txt>

---

# Part 1 — API mechanics

## Endpoints (base URL `https://api.hera.video/v1`)

| Method | Path                  | Purpose                              |
| ------ | --------------------- | ------------------------------------ |
| POST   | `/videos`             | Submit a generation job (async).     |
| GET    | `/videos/{video_id}`  | Poll status + collect file URLs.     |

**Auth:** every request carries `x-api-key: <YOUR_API_KEY>`.
Not `Authorization: Bearer …` — that is a common mistake.

## POST `/videos` — request body

```json
{
  "prompt": "<the entire motion-graphics description>",
  "duration_seconds": 30,
  "outputs": [
    { "format": "mp4", "aspect_ratio": "16:9", "fps": "30", "resolution": "1080p" }
  ]
}
```

### Required
- `prompt` (string).
- `outputs` (array, 1–10 entries).

### Optional (most clients can ignore these)
- `duration_seconds` — int 1–60. Always set explicitly; defaulting is fragile.
- `reference_image_url` (string) or `reference_image_urls` (array, ≤5).
- `reference_video_url` (string).
- `style_id` (string) — apply a saved Hera style.
- `parent_video_id` (string) — iterate on a previous render or template.
- `assets` (array of `{type: "image"|"video"|"audio"|"font"|"csv", url}`).
  Upload local files first via `POST /files`.

### Output enums

| Field          | Allowed values                                  |
| -------------- | ----------------------------------------------- |
| `format`       | `mp4` `prores` `webm` `gif`                     |
| `aspect_ratio` | `16:9` `9:16` `1:1` `4:5`                       |
| `fps`          | `"24"` `"25"` `"30"` `"60"` (strings, not ints) |
| `resolution`   | `360p` `480p` `720p` `1080p` `4k`               |

> **`fps` is a string.** `"fps": 30` will be rejected with a 4xx.

### Response

```json
{ "video_id": "vid_abcde12345", "project_url": "https://app.hera.video/..." }
```

## GET `/videos/{video_id}` — response

```json
{
  "video_id": "vid_abcde12345",
  "project_url": "https://app.hera.video/...",
  "status": "in-progress" | "success" | "failed",
  "outputs": [
    {
      "status": "in-progress" | "success" | "failed",
      "file_url": "https://cdn.hera.video/...mp4" | null,
      "config": { "format": "mp4", "aspect_ratio": "16:9", "fps": "30", "resolution": "1080p" },
      "error": "<message if status=failed>"
    }
  ]
}
```

### Status semantics

- `in-progress` — keep polling. Renders typically take 30–120s per clip.
- `success` — files at `outputs[i].file_url` are downloadable directly.
- `failed` — surface `outputs[i].error`. Do NOT auto-retry; the failure is
  almost always a prompt issue, not transient.

`404` returns `{ "error": "Video/job not found" }`.

## Minimal client (Python, httpx)

```python
import httpx

class HeraClient:
    def __init__(self, api_key: str, base_url: str = "https://api.hera.video/v1"):
        self._h = {"x-api-key": api_key, "Content-Type": "application/json"}
        self._base = base_url.rstrip("/")

    async def submit(self, body: dict) -> str:
        async with httpx.AsyncClient(timeout=60) as c:
            r = await c.post(f"{self._base}/videos", json=body, headers=self._h)
            r.raise_for_status()
        return r.json()["video_id"]

    async def poll(self, video_id: str) -> dict:
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.get(f"{self._base}/videos/{video_id}", headers=self._h)
            r.raise_for_status()
        return r.json()

    async def download(self, url: str) -> bytes:
        # Restrict to https:// to avoid SSRF if URL comes from an untrusted source.
        assert url.lower().startswith("https://"), "Hera download URL must be https://"
        async with httpx.AsyncClient(timeout=120, follow_redirects=False) as c:
            r = await c.get(url)
            r.raise_for_status()
        return r.content
```

## Quick verification

```bash
curl -X POST https://api.hera.video/v1/videos \
  -H "x-api-key: $HERA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "A 5-second kinetic-typography card on a solid white background that types the words \"hello world\" in black Inter 96px, then fades.",
    "duration_seconds": 5,
    "outputs": [{"format":"mp4","aspect_ratio":"16:9","fps":"30","resolution":"1080p"}]
  }'

# then, with the returned video_id:
curl https://api.hera.video/v1/videos/$VIDEO_ID -H "x-api-key: $HERA_API_KEY"
```

## Common pitfalls

1. **`fps` as int** — must be string. `"30"` ✓, `30` ✗.
2. **Wrong auth header** — `x-api-key`, NOT `Authorization: Bearer`.
3. **Wrong endpoint root** — `/videos`, NOT `/renders`, `/jobs`, or `/generate`.
4. **Wrong status values** — enum is `in-progress | success | failed`,
   NOT `done`, `completed`, `succeeded`, `running`.
5. **Looking for top-level `video_url`** — file URLs live under
   `outputs[i].file_url`, not at the top of the response.
6. **Polling too aggressively** — every 3s is plenty; every 0.5s burns
   quota and gets rate-limited.
7. **Treating `failed` as transient** — re-submitting the same prompt will
   fail again. Inspect `outputs[i].error` and fix the prompt.
8. **Missing `outputs`** — the field is required even though the values are
   nearly always the same `mp4 / 16:9 / 30 / 1080p`.

---

# Part 2 — Prompting playbook

Hera renders what your prompt describes. The single highest-leverage rule:

> **Specify exact timings using bracketed timing tags, not natural-language
> "first … then … finally".**

The model honors `[from 0.0s to 3.4s]` literally. It interprets "first some
text appears, then a chart slides in" loosely.

## The bracketed-timing syntax

Open every visual beat with a tag of the form:

```text
[from <START>s to <END>s] <action>
```

Where `<START>` and `<END>` are decimals in seconds (one decimal is enough,
two is overkill). The action describes what appears, where, in what color,
typeface, size, and with what animation.

A complete prompt is a short paragraph of brand/setup constraints followed
by a sequence of these bracketed beats covering `[0s, duration_seconds]`
contiguously (no gaps, optionally a 0.1–0.3s overlap during transitions).

### A worked 8-second example

```text
An 8-second motion graphic on a solid #F9FAFB background, 1920x1080 at 30fps.
Palette: #111827 (text), #374151 (secondary), #06B6D4 (accent), #F9FAFB (bg).
Typography: Inter for text, JetBrains Mono for raw numerics. Editorial
restraint — no shadows, no gradients, no decorative imagery.

[from 0.0s to 0.6s] kinetic-text title "Q3 Headline" writes word-by-word
at top center (x=960 y=200) in Inter 700 56px #111827, with a 6px #06B6D4
underline drawing in 0.4s after the title lands.

[from 0.6s to 3.4s] over the spoken line "Revenue grew 12 percent to about
94.9 billion dollars." A JetBrains Mono number counts from $0.0B to $94.9B
at center (x=960 y=520), 144px #111827, count duration 2.4s easeOutQuart.
Below it, a 40px Inter 600 caption "Revenue, +12% YoY" in #374151 reveals
word-by-word starting at 0.8s (0.06s per word). Both fade out together
over 0.30s starting at 3.1s.

[from 3.4s to 5.2s] a 720x180 callout box scale-ins at center (x=960 y=540)
over 0.40s easeOutCubic. Border #06B6D4, fill #F9FAFB. Inside, "Driver"
label in #374151 28px Inter 600 above "Services" value in #111827 56px
Inter 700. Fade out 0.30s starting at 4.9s.

[from 5.2s to 7.6s] a two-bar chart (1100x420 centered at x=960 y=600)
animates with bars drawing up over 0.80s easeOutQuart with a 0.12s
stagger. Bars labeled "FY24" (#374151) and "FY25" (#06B6D4 highlighted),
both equal height. Y-axis label "Hardware revenue (indexed)" 22px Inter.
Fade out 0.30s at the end.

No gaps to black; at most three on-screen elements at any moment;
final frame holds at 7.6s, scene ends at 8.0s.
```

## What every bracketed beat should specify

For each beat, decide and write down:

1. **The time window** — `[from Xs to Ys]`.
2. **The visual element** — what appears (one of: kinetic text, number
   count-up, simple bar/line chart, callout box, accent underline, divider).
3. **The position & size** — pixel coordinates (`x=960 y=540`) and size
   (`720x180`). Hera understands center-anchored coordinates well.
4. **The style** — color (always a hex), font family, weight, size in px.
5. **The entry animation** — type (write-on / fade / slide / scale / draw /
   count-up), duration in seconds, easing (linear, easeOutQuad, easeOutCubic,
   easeOutQuart, easeInOutSine).
6. **The exit** — fade duration and the second it begins. Or "hold" if it
   carries into the next beat.

Don't say "fancy animation" or "beautiful chart". Specify mechanics.

## Why the timings have to be precise (and where to get them)

If your video has a voice-over, the timings cannot be guessed. A sentence
that you estimate at "about 3 seconds" in the script may actually take
2.78s or 3.41s when spoken — and a 200ms drift makes a kinetic-text
animation land on the wrong word.

The fix: drive the bracketed timings from the **TTS transcript**, not the
script. Most modern TTS APIs (e.g. ElevenLabs `text-to-speech/{voice_id}/with-timestamps`)
return character-level alignment:

```json
{
  "characters": ["R", "e", "v", "e", "n", "u", "e", " ", "g"],
  "character_start_times_seconds": [0.00, 0.04, 0.08, 0.13, 0.18, 0.22, 0.26, 0.30, 0.32],
  "character_end_times_seconds": [0.04, 0.08, 0.13, 0.18, 0.22, 0.26, 0.30, 0.32, 0.36]
}
```

You then **chunk** that character stream into "slides" — pieces of text
that should appear together on screen — and read off the exact start/end
seconds of each chunk.

### Slide-chunking rule of thumb

- **Target ~80 characters per slide.** That's roughly one short sentence
  or a comfortable kinetic-text row.
- **Prefer breaking on terminal punctuation** (`.`, `!`, `?`) once you've
  accumulated at least ~30 characters. This keeps slides aligned to
  natural pauses.
- **Otherwise break at the first whitespace** after you've crossed the
  max-char threshold — never break mid-word.
- **Each slide's `start`** is the start time of its first non-space character.
  **Each slide's `end`** is the end time of its last non-space character.

A reference implementation (deterministic, no LLM):

```python
def slide_chunks(characters, start_times, end_times, *, max_chars=80, min_chars=30):
    chunks: list[dict] = []
    buf, buf_start, buf_end = [], None, None
    for ch, s, e in zip(characters, start_times, end_times):
        if buf_start is None and not ch.isspace():
            buf_start = s
        buf.append(ch)
        if not ch.isspace():
            buf_end = e
        text = "".join(buf).strip()
        if (ch in ".!?" and len(text) >= min_chars) or (len(text) >= max_chars and ch.isspace()):
            chunks.append({"text": text, "start": round(buf_start, 3), "end": round(buf_end, 3)})
            buf, buf_start, buf_end = [], None, None
    text = "".join(buf).strip()
    if text and buf_start is not None:
        chunks.append({"text": text, "start": round(buf_start, 3), "end": round(buf_end, 3)})
    return chunks
```

Once you have slide chunks, the prompt-writing step is mechanical: one
bracketed beat per chunk, picking a visual primitive that fits the
content (number → count-up; comparison → bar chart; trend → line chart;
hero phrase → kinetic text; qualifier → callout).

## Visual primitives that work well in Hera prompts

These are the primitives Hera renders most reliably when you describe
them precisely:

- **Kinetic typography** — text writes/fades/scales in word-by-word or
  character-by-character. Specify cadence (`0.06s per word`, `0.04s per char`).
- **Number count-up** — counts from `start_value` to `end_value` with a
  duration and easing. Always for spoken figures.
- **Bar chart** — up to 6 vertical bars, one optionally highlighted in
  the accent color. Specify bar values, axis label, draw duration, stagger.
- **Line chart** — single series with an end-dot, stroke draws over a
  duration. Good for trend sentences.
- **Callout box** — small bordered box with label + value. Good for
  qualifiers ("Driver: Services", "Risk: FX").
- **Accent underline** — thin stroke under a previous text element to
  emphasize a phrase. Specify the target text and stroke thickness.
- **Divider** — thin horizontal line as a beat separator. Use sparingly.

Avoid: emojis, stock images, gradients, parallax, depth-of-field,
camera moves, lens flares, particle effects. They produce inconsistent
results and don't suit editorial register.

## Title intros & sound design

A common pattern: open the video with a typing-effect title card and
a typewriter sound effect, before the voice-over begins.

### The title-card prompt

```text
A 4-second motion graphic on a solid #F9FAFB background, 1920x1080 at 30fps.

[from 0.0s to 3.0s] typewriter typing animation of "<TITLE TEXT>", centered
(x=960 y=540), JetBrains Mono 96px in #111827. Type one character every
0.06s with a hard cursor cadence. A blinking "|" cursor in #06B6D4
follows the last typed character (blink cycle 0.5s on, 0.5s off).

[from 3.0s to 4.0s] hold the typed text. Cursor continues to blink.
Fade the entire scene out over the last 0.30s.
```

`duration_seconds: 4`. Short, punchy.

### The matching sound effect (e.g. ElevenLabs `/v1/sound-generation`)

```json
{
  "text": "vintage mechanical typewriter typing sound, rhythmic, no music, no voice",
  "duration_seconds": 4,
  "prompt_influence": 0.5
}
```

`POST https://api.elevenlabs.io/v1/sound-generation` with the
`xi-api-key` header. Returns binary MP3.

In the final mux, prepend the title clip + typewriter audio in front of
the voice-over scenes.

## Editorial register defaults (a good starting palette)

When a project doesn't have brand guidelines yet, this palette is a
safe editorial default:

```text
text       #111827   (large numbers, headlines)
secondary  #374151   (axis labels, sub-text)
accent     #06B6D4   (highlight bars, underlines, the active series)
background #F9FAFB   (solid; no gradients)
fonts      Inter for text; JetBrains Mono for raw numerics
sizes      headline 84–112px, sub 36–48px, body 28–32px, axis 22px
```

Override per-brand. The point of including a palette explicitly in EVERY
Hera prompt is: without it, Hera will pick its own colors and fonts and
the result will look like a consumer marketing video, not a financial
briefing.

---

## Decision checklist before you submit

- [ ] Prompt opens with one paragraph of brand/setup constraints (palette, typography, register).
- [ ] Every visible second of the video is covered by exactly one bracketed beat.
- [ ] Every spoken figure is visualized as a count-up or chart (not as plain text).
- [ ] `duration_seconds` equals the end time of the last beat.
- [ ] `outputs[]` is non-empty; `fps` is a string.
- [ ] No emoji, no decorative imagery, no gradients in the prompt.
- [ ] If voice-over is in play, the bracketed timings come from a TTS transcript, not from the script word counts.
