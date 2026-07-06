from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

AUDIO_EXTS = {".mp3", ".m4a", ".wav", ".flac", ".ogg", ".mp4", ".mov", ".webm"}
TEXT_EXTS = {".md", ".txt"}


@dataclass
class Discovery:
    audio: list[Path] = field(default_factory=list)
    text: list[Path] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.audio) + len(self.text)


@dataclass
class Paths:
    input_dir: Path
    output_dir: Path
    raw_transcripts_dir: Path
    key_file: Path


def discover(folder: Path) -> Discovery:
    d = Discovery()
    for p in sorted(folder.iterdir()):
        if not p.is_file():
            continue
        if p.name.startswith("."):
            continue
        ext = p.suffix.lower()
        if ext in AUDIO_EXTS:
            d.audio.append(p)
        elif ext in TEXT_EXTS:
            d.text.append(p)
    return d


def resolve_paths(folder: Path) -> Paths:
    out = folder / "output"
    raw = out / "raw-transcripts"
    return Paths(
        input_dir=folder,
        output_dir=out,
        raw_transcripts_dir=raw,
        key_file=out / "_key.json",
    )


def ensure_dirs(paths: Paths) -> None:
    paths.output_dir.mkdir(parents=True, exist_ok=True)
    paths.raw_transcripts_dir.mkdir(parents=True, exist_ok=True)


def load_key(key_file: Path) -> dict:
    if key_file.exists():
        return json.loads(key_file.read_text(encoding="utf-8"))
    return {"persons": {}, "orgs": {}, "locations": {}}


def save_key(key_file: Path, mapping: dict) -> None:
    key_file.write_text(
        json.dumps(mapping, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def anon_path(paths: Paths, source: Path) -> Path:
    return paths.output_dir / f"{source.stem}.anon.md"


def raw_transcript_path(paths: Paths, audio: Path) -> Path:
    return paths.raw_transcripts_dir / f"{audio.stem}.md"
