from __future__ import annotations

from pathlib import Path
from typing import Callable

_model_cache: dict[str, object] = {}


def _get_model(model_size: str):
    if model_size in _model_cache:
        return _model_cache[model_size]
    from faster_whisper import WhisperModel

    model = WhisperModel(model_size, device="auto", compute_type="auto")
    _model_cache[model_size] = model
    return model


def transcribe_file(
    audio_path: Path,
    model_size: str = "small",
    language: str | None = "de",
    on_progress: Callable[[float], None] | None = None,
) -> str:
    model = _get_model(model_size)
    segments, info = model.transcribe(
        str(audio_path),
        language=language,
        vad_filter=True,
    )
    total = float(info.duration or 0.0)
    parts: list[str] = []
    for seg in segments:
        parts.append(seg.text.strip())
        if on_progress and total > 0:
            on_progress(min(1.0, seg.end / total))
    return "\n\n".join(p for p in parts if p)


def write_transcript(text: str, target: Path, source_name: str) -> None:
    body = (
        f"# Transkript: {source_name}\n\n"
        f"{text.strip()}\n"
    )
    target.write_text(body, encoding="utf-8")
