# Rebuild Summary

## 1. Hera skill rebuilt as a general guide

`.claude/skills/hera-api/SKILL.md` and the mirror [docs/hera-api.md](docs/hera-api.md) no longer mention CorpuScan. The guide now has two focused halves:

- API mechanics: endpoints, `x-api-key` auth, request/response shapes, the `in-progress | success | failed` status enum, file URL location at `outputs[i].file_url`, a minimal Python client, a `curl` smoke test, and 8 common pitfalls.
- Prompting playbook: the `[from <START>s to <END>s] <action>` syntax, a worked 8-second example, why timings must come from a TTS transcript instead of the source script, a reference Python `slide_chunks(...)` algorithm that targets about 80 characters, visual-primitive selection guidance, the title-intro pattern with ElevenLabs sound generation, and a submission decision checklist.

## 2. Slicer added as deterministic transformation

No new LLM agent was introduced. Slide chunking is a deterministic transformation over ElevenLabs character-level alignment and now lives in [backend/app/integrations/elevenlabs.py](backend/app/integrations/elevenlabs.py) as `compute_slide_chunks_for_scene(...)`.

It now:

- Walks the per-scene character slice.
- Breaks on terminal punctuation once at least 30 characters have accumulated, otherwise on whitespace once 80 characters are reached.
- Emits `SlideChunk(text, start_seconds, end_seconds, char_count)` with scene-relative timings.

This fixes a real bug: the Hera agent had been receiving absolute audio timings, so scenes 2-4 could start at 30s+ instead of 0s for their own clips.

[backend/app/schemas.py](backend/app/schemas.py) now includes a `SlideChunk` model.

## 3. Hera agent rewritten

[backend/app/prompts/hera.yaml](backend/app/prompts/hera.yaml)

- Input is now `slide_chunks`, not `sentence_timings`.
- Output prompt must use bracketed `[from Xs to Ys]` timing, one beat per chunk, covering `[0s, duration_seconds]` contiguously with `0.10s` to `0.30s` cross-fades.
- Includes a worked example showing a brand paragraph plus bracketed beats with overlap.
- Bakes in visual-primitive selection rules such as numbers to count-up and comparisons to bar chart.
- Defines seven explicit timing rules, `T1` through `T7`.

[backend/app/agents/hera.py](backend/app/agents/hera.py)

- `run_hera_agent(scene, slide_chunks_for_scene, gemini_client)` is the new signature.
- `_normalize_hera_spec(...)` now clamps `duration_seconds = ceil(max(slide_chunk.end))`.
- `build_intro_hera_spec(title, duration_seconds=4)` now produces a deterministic title-intro Hera spec: JetBrains Mono `96px`, `#F9FAFB` background, blinking `#06B6D4` cursor, hold, then fade.

## 4. Title intro and typing sound

[backend/app/integrations/elevenlabs.py](backend/app/integrations/elevenlabs.py) now includes `generate_sound_effect(text, duration_seconds, prompt_influence=0.5)` via `POST /v1/sound-generation`.

[backend/app/pipeline.py](backend/app/pipeline.py)

- During TTS, voice TTS and the intro typing sound are fanned out in parallel with `asyncio.gather(...)`.
- After the 4 Hera agent calls, a 5th deterministic intro spec is built and all 5 Hera renders are submitted in parallel.
- All 5 renders are polled until success, then downloaded in order with intro at index 0 and scenes at indices 1-4.

[backend/app/render.py](backend/app/render.py) now exposes `compose(intro_clip_path, intro_sound_path, scene_clip_paths, voice_path, out_path)` and uses ffmpeg's concat filter, which is more tolerant of codec mismatches than the concat demuxer.

```bash
ffmpeg -y -i intro.mp4 -i clip_0.mp4 -i clip_1.mp4 -i clip_2.mp4 -i clip_3.mp4 -i intro_sound.mp3 -i voice.mp3 \
  -filter_complex "[0:v][1:v][2:v][3:v][4:v]concat=n=5:v=1:a=0[v]; [5:a][6:a]concat=n=2:v=0:a=1[a]" \
  -map "[v]" -map "[a]" -c:v libx264 -c:a aac -shortest -pix_fmt yuv420p out.mp4
```

## Verified

- All modules import.
- The slide chunker produces scene-relative timings starting at `0.0s` even when fed absolute-time alignment.
- The intro builder produces a valid Hera spec and passes `validate_hera_spec`.
- The ffmpeg command shape was inspected end-to-end.
