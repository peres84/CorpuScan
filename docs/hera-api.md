# Hera Motion API — quick reference

This is the same content as the Claude skill at
[`.claude/skills/hera-api/SKILL.md`](../.claude/skills/hera-api/SKILL.md);
keep them in sync. Both files are general guides — not specific to any
particular project.

The Hera Motion API generates motion-graphics videos from a single text
prompt. There is no JSON timeline; the prompt is the program.

Hera docs index: <https://docs.hera.video/llms.txt>

---

## Endpoints (`https://api.hera.video/v1`)

| Method | Path                  | Purpose                              |
| ------ | --------------------- | ------------------------------------ |
| POST   | `/videos`             | Submit a generation job (async).     |
| GET    | `/videos/{video_id}`  | Poll status + collect file URLs.     |

**Auth:** `x-api-key: <YOUR_API_KEY>` on every request.

## Submit body

```json
{
  "prompt": "<the entire motion-graphics description>",
  "duration_seconds": 30,
  "outputs": [
    { "format": "mp4", "aspect_ratio": "16:9", "fps": "30", "resolution": "1080p" }
  ]
}
```

- `prompt` and `outputs` are required.
- `duration_seconds`: int 1–60 (set explicitly).
- `outputs[].fps` is a STRING (`"30"`, not `30`).
- Optional: `reference_image_url(s)`, `reference_video_url`, `style_id`, `parent_video_id`, `assets`.

Response: `{ "video_id": "...", "project_url": "..." }`.

## Poll response

```json
{
  "video_id": "...",
  "status": "in-progress" | "success" | "failed",
  "outputs": [
    {
      "status": "in-progress" | "success" | "failed",
      "file_url": "https://...mp4" | null,
      "config": {...},
      "error": "<if failed>"
    }
  ]
}
```

File URL lives at `outputs[i].file_url`. Status enum is `in-progress | success | failed` (NOT `done` / `completed`).

---

## Prompting — the bracketed-timing syntax

Open every visual beat with `[from <START>s to <END>s] <action>`:

```
A 5-second motion graphic on a solid white background, 1920x1080 at 30fps.

[from 0.0s to 1.5s] kinetic typography "Hello World" centered, Inter 96px
black, types in word-by-word over 0.5s easeOutQuad.

[from 1.5s to 3.0s] hold the title. A 6px black underline draws under
"World" over 0.3s easeOutCubic.

[from 3.0s to 5.0s] fade out over 0.5s; final 1.5s holds on a clean
background.
```

`duration_seconds: 5`. Total beats cover `[0s, 5s]` contiguously.

**Why brackets, not natural language?** The renderer honors `[from 0.0s to 3.4s]`
literally; it interprets "first … then …" loosely.

---

## Driving timings from a TTS transcript

If the video has voice-over, do NOT estimate timings from script word
counts. Use character-level alignment from your TTS provider (e.g.
ElevenLabs `text-to-speech/{voice_id}/with-timestamps`):

```json
{
  "characters": ["H","e","l","l","o", ...],
  "character_start_times_seconds": [0.00, 0.04, 0.08, 0.13, 0.18, ...],
  "character_end_times_seconds":   [0.04, 0.08, 0.13, 0.18, 0.22, ...]
}
```

Group characters into ~80-char "slide chunks" (break on `.!?` once
≥30 chars, else on whitespace once ≥80 chars). Each chunk's start =
first non-space char's start time; end = last non-space char's end time.

Then write one bracketed beat per chunk with that chunk's exact
start/end, and pick a visual primitive that fits its content:

| Content                 | Primitive               |
| ----------------------- | ----------------------- |
| Spoken figure / number  | Number count-up         |
| Comparison (2–6 things) | Bar chart               |
| Trend over time         | Line chart              |
| Hero phrase             | Kinetic typography      |
| Qualifier / risk note   | Callout box             |
| Phrase to emphasize     | Accent underline        |

---

## Title intro pattern

Open with a typing-effect title card + matching typewriter sound effect:

**Hera prompt** (`duration_seconds: 4`):
```
A 4-second motion graphic on a solid #F9FAFB background, 1920x1080 at 30fps.
[from 0.0s to 3.0s] typewriter typing animation of "<TITLE>", centered
(x=960 y=540), JetBrains Mono 96px #111827. Type cadence 0.06s/char.
Blinking "|" cursor in #06B6D4 follows.
[from 3.0s to 4.0s] hold and fade out over the last 0.3s.
```

**ElevenLabs sound** (`POST /v1/sound-generation`):
```json
{
  "text": "vintage mechanical typewriter typing sound, rhythmic, no music, no voice",
  "duration_seconds": 4,
  "prompt_influence": 0.5
}
```

Mux: prepend the title clip + typewriter MP3 in front of the voice-over scenes.

---

## Pitfalls

1. `fps` is a STRING (`"30"`, not `30`).
2. Auth header is `x-api-key`, NOT `Authorization: Bearer`.
3. Endpoints are `/videos` and `/videos/{video_id}` — NOT `/renders`.
4. Status enum is `in-progress | success | failed` — NOT `done` / `completed`.
5. File URL lives in `outputs[i].file_url`.
6. Renders take 30–120s. Poll every 3s, not faster.
7. `failed` is usually a prompt problem. Surface the error; don't auto-retry.
8. Always emit `outputs[]` — required even though it's almost always the same `mp4 / 16:9 / "30" / 1080p`.
