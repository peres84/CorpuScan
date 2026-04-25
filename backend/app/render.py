from __future__ import annotations

import subprocess
from pathlib import Path


def compose(clip_paths: list[str], audio_path: str, out_path: str) -> None:
    if not clip_paths:
        raise ValueError("No clip paths provided for composition.")

    out_file = Path(out_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    concat_file = out_file.parent / "concat.txt"
    concat_file.write_text(
        "\n".join(f"file '{Path(clip).as_posix()}'" for clip in clip_paths),
        encoding="utf-8",
    )

    command = [
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_file),
        "-i",
        audio_path,
        "-c:v",
        "libx264",
        "-c:a",
        "aac",
        "-shortest",
        "-pix_fmt",
        "yuv420p",
        out_path,
    ]
    subprocess.run(command, check=True, capture_output=True)
