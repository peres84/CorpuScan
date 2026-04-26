# Agent System Prompts — moved

The system prompts for the in-product AI agents (Finance, Scripter, Hera)
have moved out of this Markdown file and into structured YAML, colocated
with the backend code that consumes them.

## New location

```
backend/app/prompts/
├── finance.yaml      ← Finance Agent (Gemini 2.5 Pro)
├── scripter.yaml     ← Scripter Agent (Gemini 2.5 Pro)
└── hera.yaml         ← Hera Agent (Gemini 2.5 Pro, ×4 in parallel)
```

Each YAML file declares:

| Field                | Purpose                                                |
| -------------------- | ------------------------------------------------------ |
| `model`              | Gemini model id                                        |
| `temperature`        | Generation temperature                                 |
| `response_mime_type` | `application/json` for Scripter & Hera, null otherwise |
| `system`             | Full system prompt (multi-line literal)                |
| `user_template`      | User message template with `{placeholders}`            |

Loaded by `backend/app/agents/_prompts.py` via `pyyaml`.

## Why the move

- **Single source of truth.** Prompts live next to the code that loads them;
  no regex-parsing of Markdown headings.
- **Per-agent files.** Easier review, smaller diffs, no `## 1.`-style
  ordering coupling.
- **Structured config.** Model, temperature, and response MIME type live with
  the prompt instead of being scattered across Python kwargs.
- **Editing surface for non-engineers.** Prompts can be tuned without
  touching Python.

## Pipeline notes (unchanged)

- **Finance → Scripter** is sequential: Scripter needs the full Q&A.
- **Scripter → TTS** is sequential: TTS needs the concatenated narration.
- **TTS → Hera Agent ×4** is sequential, then the 4 Hera Agent calls run in
  parallel: each only needs its own scene + the timings of the sentences
  in that scene.
- **Hera Agent → Hera API** is parallel: 4 submissions, then poll all 4
  until ready.
- **Hera clips + voice → ffmpeg** is the final sequential step.

For sentence-to-scene mapping, the backend tracks which character offsets
in the concatenated narration belong to which scene (it built the
concatenation), so the per-scene `sentence_timings` slice is computed
deterministically without asking the model.
