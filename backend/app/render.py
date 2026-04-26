from __future__ import annotations

import subprocess
from pathlib import Path


def compose(
    *,
    intro_clip_path: str,
    intro_sound_path: str,
    scene_clip_paths: list[str],
    voice_path: str,
    out_path: str,
) -> None:
    """Stitch [intro_clip + scene_clips...] video with [intro_sound + voice]
    audio into one MP4. Uses ffmpeg's concat filter (re-encodes), which is
    more lenient than the concat demuxer when input clips have slightly
    different codecs / framerates."""
    if not scene_clip_paths:
        raise ValueError("No scene clip paths provided for composition.")

    out_file = Path(out_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    video_inputs = [intro_clip_path, *scene_clip_paths]
    audio_inputs = [intro_sound_path, voice_path]
    n_video = len(video_inputs)
    n_audio = len(audio_inputs)

    video_chain = "".join(f"[{i}:v]" for i in range(n_video))
    audio_chain = "".join(f"[{n_video + j}:a]" for j in range(n_audio))
    filter_complex = (
        f"{video_chain}concat=n={n_video}:v=1:a=0[v];"
        f"{audio_chain}concat=n={n_audio}:v=0:a=1[a]"
    )

    command: list[str] = ["ffmpeg", "-y"]
    for path in video_inputs:
        command.extend(["-i", path])
    for path in audio_inputs:
        command.extend(["-i", path])
    command.extend(
        [
            "-filter_complex",
            filter_complex,
            "-map",
            "[v]",
            "-map",
            "[a]",
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            "-shortest",
            "-pix_fmt",
            "yuv420p",
            out_path,
        ]
    )
    subprocess.run(command, check=True, capture_output=True)
