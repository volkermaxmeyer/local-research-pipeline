"""Local LLM synthesis via Ollama HTTP API.

The synthesis step takes an anonymized transcript and a system prompt
(the v2 synthesis framework) and returns a structured 7-section
markdown synthesis from a locally-running Ollama model.

Ollama must be running as a service on `localhost:11434`.
Models supported out of the box: `qwen3:8b` (default), `gemma3:4b`,
plus legacy `llama3.1:8b` and `gemma2:2b`.

All calls are stdlib-only (urllib) — no external Python dependencies.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

DEFAULT_HOST = "http://localhost:11434"
DEFAULT_MODEL = "qwen3:8b"
DEFAULT_TIMEOUT = 600
DEFAULT_TEMPERATURE = 0.3
DEFAULT_NUM_CTX = 16384

# Models that emit thinking traces by default; we disable that for synthesis
THINKING_MODEL_PREFIXES = ("qwen3",)


@dataclass
class SynthResult:
    text: str
    model: str
    source_path: Path


def check_ollama_available(host: str = DEFAULT_HOST, timeout: float = 2.0) -> bool:
    """Return True if the Ollama service is reachable."""
    try:
        with urllib.request.urlopen(f"{host}/api/tags", timeout=timeout) as r:
            return r.status == 200
    except (urllib.error.URLError, TimeoutError, ConnectionError):
        return False


def list_models(host: str = DEFAULT_HOST, timeout: float = 2.0) -> list[str]:
    """Return the list of locally-pulled Ollama model names. Empty list on failure."""
    try:
        with urllib.request.urlopen(f"{host}/api/tags", timeout=timeout) as r:
            data = json.loads(r.read())
    except (urllib.error.URLError, TimeoutError, ConnectionError, json.JSONDecodeError):
        return []
    return [m.get("name", "") for m in data.get("models", []) if m.get("name")]


def synthesize(
    transcript: str,
    system_prompt: str,
    model: str = DEFAULT_MODEL,
    host: str = DEFAULT_HOST,
    timeout: int = DEFAULT_TIMEOUT,
) -> str:
    """Call Ollama with system + user prompt, return the raw response text."""
    payload = {
        "model": model,
        "system": system_prompt,
        "prompt": transcript,
        "stream": False,
        "options": {"temperature": DEFAULT_TEMPERATURE, "num_ctx": DEFAULT_NUM_CTX},
    }
    if model.startswith(THINKING_MODEL_PREFIXES):
        payload["think"] = False
    req = urllib.request.Request(
        f"{host}/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read())
    return data["response"]


def synthesize_file(
    anonymized_file: Path,
    system_prompt: str,
    target: Path,
    model: str = DEFAULT_MODEL,
    host: str = DEFAULT_HOST,
    timeout: int = DEFAULT_TIMEOUT,
) -> SynthResult:
    """Read an anonymized transcript, synthesize, write target, return result."""
    transcript = anonymized_file.read_text(encoding="utf-8")
    text = synthesize(transcript, system_prompt, model=model, host=host, timeout=timeout)
    target.write_text(text, encoding="utf-8")
    return SynthResult(text=text, model=model, source_path=anonymized_file)


def estimate_tokens(text: str) -> int:
    """Rough token estimate (conservative: ~3 chars per token for German)."""
    return len(text) // 3


def load_system_prompt(repo_root: Path) -> str:
    """Load the synthesis system prompt bundled in the repo."""
    return (repo_root / "prompts" / "synthesis-v2.md").read_text(encoding="utf-8")


def synthesis_path(anonymized_file: Path) -> Path:
    """Derive the synthesis output path from the anonymized file path.

    Example: output/sarah-interview.anon.md -> output/sarah-interview.synthesis.md
    """
    stem = anonymized_file.name
    if stem.endswith(".anon.md"):
        base = stem[: -len(".anon.md")]
    else:
        base = anonymized_file.stem
    return anonymized_file.parent / f"{base}.synthesis.md"
