from __future__ import annotations

import subprocess
import time
from datetime import datetime
from pathlib import Path

import streamlit as st

from pipeline import anonymize, io_utils, transcribe
from pipeline.synthesize import (
    DEFAULT_NUM_CTX,
    check_ollama_available,
    estimate_tokens,
    list_models,
    load_system_prompt,
    synthesis_path,
    synthesize_file,
)

st.set_page_config(page_title="Local Research Pipeline", page_icon="🔒", layout="centered")

WHISPER_MODELS = ["tiny", "base", "small", "medium", "large-v3"]
LANG_CHOICES = {"English": "en", "German": "de", "Auto-detect": None}

REPO_ROOT = Path(__file__).resolve().parent
SYNTH_MODELS = [
    ("qwen3:8b", "best quality (~60s)"),
    ("gemma3:4b", "fast (~20s)"),
    ("llama3.1:8b", "legacy (~45s)"),
    ("gemma2:2b", "legacy fast (~15s)"),
]
RUNS_BASE = Path.home() / "Documents" / "local-research-pipeline"

UPLOAD_TYPES = [
    "mp3", "m4a", "wav", "flac", "ogg", "mp4", "mov", "webm",
    "md", "txt",
]


# ────────────────────────────────────────────────────────────────────────────
# State + helpers
# ────────────────────────────────────────────────────────────────────────────


def _open_in_finder(path: Path) -> None:
    try:
        subprocess.run(["open", str(path)], check=False)
    except Exception:
        pass


def _format_counts(mapping: dict) -> str:
    p = len(mapping.get("persons", {}))
    o = len(mapping.get("orgs", {}))
    l = len(mapping.get("locations", {}))
    return f"{p} people · {o} orgs · {l} locations"


def _init_state() -> None:
    st.session_state.setdefault("wizard_step", 1)
    st.session_state.setdefault("run_dir", None)


def _get_run_dir() -> Path:
    """Return (and create on demand) the per-run working directory."""
    if st.session_state.get("run_dir"):
        return Path(st.session_state["run_dir"])
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    d = RUNS_BASE / stamp
    d.mkdir(parents=True, exist_ok=True)
    st.session_state["run_dir"] = str(d)
    return d


def _save_uploads(uploaded_files: list, target_dir: Path) -> list[Path]:
    saved: list[Path] = []
    for uf in uploaded_files:
        out = target_dir / uf.name
        out.write_bytes(uf.getbuffer())
        saved.append(out)
    return saved


def _reset_run() -> None:
    """Clear all run-scoped state. Working folder on disk stays put."""
    for k in ("run_dir", "last_run", "last_synthesis", "uploads"):
        st.session_state.pop(k, None)
    st.session_state["wizard_step"] = 1


def _goto(step: int) -> None:
    st.session_state["wizard_step"] = step
    st.rerun()


# ────────────────────────────────────────────────────────────────────────────
# Top-of-page chrome
# ────────────────────────────────────────────────────────────────────────────


def header():
    st.title("Local Research Pipeline")
    st.caption(
        "Audio or text in → anonymized → structured synthesis. "
        "All offline, nothing leaves your Mac."
    )
    st.info(
        "ℹ️ Processed locally. No data has left this machine.",
        icon=None,
    )


def progress_bar():
    step = st.session_state.get("wizard_step", 1)
    labels = ["1 · Upload", "2 · Anonymize", "3 · Synthesize"]
    cols = st.columns(3)
    for i, (col, label) in enumerate(zip(cols, labels), start=1):
        if i < step:
            col.markdown(f"✓ {label}")
        elif i == step:
            col.markdown(f"**→ {label}**")
        else:
            col.markdown(f":gray[{label}]")
    st.divider()


# ────────────────────────────────────────────────────────────────────────────
# Step 1 · Upload
# ────────────────────────────────────────────────────────────────────────────


def step1_upload():
    st.subheader("Step 1 · Upload file")
    st.markdown(
        "Audio files (`.mp3`, `.m4a`, `.wav`, …) are transcribed locally. "
        "Text files (`.md`, `.txt`) are anonymized directly."
    )

    uploaded = st.file_uploader(
        "Choose a file",
        type=UPLOAD_TYPES,
        accept_multiple_files=False,
        key="uploads",
    )

    if uploaded:
        icon = "🎙" if uploaded.name.split(".")[-1].lower() not in {"md", "txt"} else "📄"
        st.success(f"{icon}  `{uploaded.name}`  · {uploaded.size / 1024:.0f} KB")

    st.markdown("")
    cols = st.columns([1, 1])
    with cols[1]:
        if st.button(
            "Continue to Step 2 →",
            type="primary",
            disabled=uploaded is None,
            use_container_width=True,
        ):
            run_dir = _get_run_dir()
            _save_uploads([uploaded], run_dir)
            _goto(2)


# ────────────────────────────────────────────────────────────────────────────
# Step 2 · Anonymize
# ────────────────────────────────────────────────────────────────────────────


def step2_anonymize():
    st.subheader("Step 2 · Anonymization")

    run_dir = _get_run_dir()
    d = io_utils.discover(run_dir)
    if d.total == 0:
        st.warning("No files found. Go back and upload files.")
        if st.button("← Back"):
            _goto(1)
        return

    cols = st.columns(2)
    cols[0].metric("Audio files", len(d.audio))
    cols[1].metric("Text files", len(d.text))

    with st.expander(f"File list ({d.total})", expanded=False):
        for f in d.audio:
            st.markdown(f"🎙  `{f.name}`")
        for f in d.text:
            st.markdown(f"📄  `{f.name}`")

    # Settings — only relevant if audio is present
    if d.audio:
        st.markdown("**Transcription settings**")
        s_cols = st.columns(2)
        with s_cols[0]:
            model_size = st.selectbox(
                "Whisper model",
                options=WHISPER_MODELS,
                index=WHISPER_MODELS.index("small"),
                help="Larger = more accurate but slower. `small` is enough for clear recordings.",
            )
        with s_cols[1]:
            lang_label = st.selectbox(
                "Language", options=list(LANG_CHOICES.keys()), index=0
            )
        language = LANG_CHOICES[lang_label]
    else:
        model_size, language = "small", None

    last_run = st.session_state.get("last_run")
    if not last_run:
        st.markdown("")
        nav = st.columns([1, 1])
        with nav[0]:
            if st.button("← Back", use_container_width=True):
                _goto(1)
        with nav[1]:
            if st.button(
                "Start anonymization",
                type="primary",
                use_container_width=True,
            ):
                st.session_state.pop("last_synthesis", None)
                run_pipeline(run_dir, d, model_size, language)
                st.rerun()
        return

    # Last run exists — show results
    paths: io_utils.Paths = last_run["paths"]
    mapping = last_run["mapping"]
    sample = last_run["sample"]

    st.success("✓ Anonymization complete")
    st.caption(f"Mapping: {_format_counts(mapping)}")

    if sample:
        name, text = sample
        with st.expander(f"Sample: {name}", expanded=True):
            preview = text[:1500] + ("\n\n… [truncated]" if len(text) > 1500 else "")
            st.markdown(preview)

    with st.expander("🔒 Show mapping (local, never leaves your Mac)", expanded=False):
        st.warning(
            "The mapping is the key to re-identification. "
            "Keep `_key.json` local and don't share it."
        )
        st.json(mapping)

    if st.button("📂  Open output folder"):
        _open_in_finder(paths.output_dir)

    st.markdown("")
    nav = st.columns([1, 1])
    with nav[0]:
        if st.button("← Back", use_container_width=True):
            _goto(1)
    with nav[1]:
        if st.button(
            "Continue to Step 3 →",
            type="primary",
            use_container_width=True,
        ):
            _goto(3)


def run_pipeline(folder: Path, d: io_utils.Discovery, model_size: str, language: str | None):
    paths = io_utils.resolve_paths(folder)
    io_utils.ensure_dirs(paths)
    mapping = io_utils.load_key(paths.key_file)

    # NER quality depends on matching the spaCy model to the transcript
    # language: English → en model, German/Auto-detect → de model (default).
    spacy_model = "en_core_web_lg" if language == "en" else "de_core_news_lg"

    log = st.container()
    progress = st.progress(0, text="Starting…")

    total_steps = len(d.audio) + d.total
    step = 0
    transcribed_paths: list[Path] = []

    for audio in d.audio:
        raw_target = io_utils.raw_transcript_path(paths, audio)
        if raw_target.exists():
            log.markdown(f"⏭  Transcript exists, skipped: `{audio.name}`")
        else:
            log.markdown(f"🎙  Transcribing `{audio.name}` …")
            t0 = time.time()
            try:
                text = transcribe.transcribe_file(
                    audio,
                    model_size=model_size,
                    language=language,
                )
                transcribe.write_transcript(text, raw_target, audio.name)
                log.markdown(f"    ✓ done in {time.time()-t0:.0f}s")
            except Exception as e:
                log.error(f"Error in {audio.name}: {e}")
                continue
        transcribed_paths.append(raw_target)
        step += 1
        progress.progress(step / total_steps, text=f"Transcribed: {audio.name}")

    sources = transcribed_paths + d.text
    if sources:
        log.markdown(f"🔒  Anonymizing {len(sources)} file(s)…")

    sample_preview: tuple[str, str] | None = None
    for src in sources:
        target = io_utils.anon_path(paths, src)
        try:
            result = anonymize.anonymize_file(src, target, mapping, model_name=spacy_model)
            log.markdown(
                f"    ✓ `{src.name}` → `{target.name}`  "
                f"({result.new_entities} new, {result.used_entities} reused)"
            )
            if sample_preview is None:
                sample_preview = (target.name, target.read_text(encoding="utf-8"))
        except Exception as e:
            log.error(f"Error in {src.name}: {e}")
        step += 1
        progress.progress(min(1.0, step / total_steps), text=f"Anonymized: {src.name}")

    io_utils.save_key(paths.key_file, mapping)
    progress.progress(1.0, text="Done")

    st.session_state["last_run"] = {
        "folder": str(folder),
        "paths": paths,
        "mapping": mapping,
        "sample": sample_preview,
    }


# ────────────────────────────────────────────────────────────────────────────
# Step 3 · Synthesize
# ────────────────────────────────────────────────────────────────────────────


def _list_anon_files(output_dir: Path) -> list[Path]:
    return sorted(output_dir.glob("*.anon.md"))


def _run_synthesis(anon_file: Path, model: str) -> None:
    system_prompt = load_system_prompt(REPO_ROOT)
    target = synthesis_path(anon_file)
    result = synthesize_file(
        anon_file, system_prompt=system_prompt, target=target, model=model
    )
    st.session_state["last_synthesis"] = {
        "model": result.model,
        "source": str(anon_file),
        "target": str(target),
        "text": result.text,
    }


def step3_synthesize():
    st.subheader("Step 3 · Synthesis")

    last_run = st.session_state.get("last_run")
    if not last_run:
        st.warning("No anonymization has run yet. Go back to Step 2.")
        if st.button("← Back"):
            _goto(2)
        return

    paths: io_utils.Paths = last_run["paths"]

    if not check_ollama_available():
        st.warning(
            "Ollama service not reachable.\n\n"
            "Start it with:  `brew services start ollama`"
        )
        if st.button("🔁 Re-check status"):
            st.rerun()
        if st.button("← Back"):
            _goto(2)
        return

    last_synth = st.session_state.get("last_synthesis")

    if not last_synth:
        anon_files = _list_anon_files(paths.output_dir)
        if not anon_files:
            st.info("No anonymized files found in the output folder.")
            if st.button("← Back"):
                _goto(2)
            return

        available_models = set(list_models())
        cols = st.columns(2)
        with cols[0]:
            model_choice = st.radio(
                "Model",
                options=[m for m, _ in SYNTH_MODELS],
                format_func=lambda m: f"{m} — {dict(SYNTH_MODELS)[m]}",
                index=0,
                help="Qwen3 gives the best synthesis quality, Gemma3 runs faster. All run locally via Ollama.",
            )
        with cols[1]:
            source_choice = st.selectbox(
                "Anonymized transcript",
                options=anon_files,
                format_func=lambda p: p.name,
            )

        if available_models and model_choice not in available_models:
            st.error(
                f"Model `{model_choice}` is not pulled locally. "
                f"Available: {', '.join(sorted(available_models)) or '–'}\n\n"
                f"Pull with: `ollama pull {model_choice}`"
            )
            return

        # Warn if transcript + system prompt likely exceed the context window
        # (Ollama truncates the prompt start silently — the synthesis would
        # miss the beginning of the interview).
        est = estimate_tokens(
            load_system_prompt(REPO_ROOT)
            + source_choice.read_text(encoding="utf-8")
        )
        output_reserve = 2048
        if est > DEFAULT_NUM_CTX - output_reserve:
            st.warning(
                f"⚠️ This transcript is long (~{est:,} tokens estimated). "
                f"The context window is {DEFAULT_NUM_CTX:,} tokens — the start "
                f"of the interview may get cut off silently. Consider "
                f"splitting the transcript into parts."
            )

        nav = st.columns([1, 1])
        with nav[0]:
            if st.button("← Back", use_container_width=True):
                _goto(2)
        with nav[1]:
            if st.button(
                "Start synthesis",
                type="primary",
                use_container_width=True,
            ):
                with st.spinner(f"Synthesizing with {model_choice} …"):
                    try:
                        _run_synthesis(source_choice, model_choice)
                    except Exception as e:
                        st.error(f"Synthesis failed: {e}")
                        return
                st.rerun()
        return

    # Synthesis available — show output
    st.success(f"✓ Synthesis complete · Model: `{last_synth['model']}`")
    target_path = Path(last_synth["target"])

    st.markdown(last_synth["text"])

    cols = st.columns(3)
    with cols[0]:
        st.download_button(
            "📥 Synthesis (Markdown)",
            data=last_synth["text"].encode("utf-8"),
            file_name=target_path.name,
            mime="text/markdown",
            use_container_width=True,
        )
    with cols[1]:
        if st.button("🔄 Different synthesis", use_container_width=True):
            st.session_state.pop("last_synthesis", None)
            st.rerun()
    with cols[2]:
        if st.button("✨ New run", use_container_width=True):
            _reset_run()
            st.rerun()


# ────────────────────────────────────────────────────────────────────────────
# Main dispatcher
# ────────────────────────────────────────────────────────────────────────────


def main():
    _init_state()
    header()
    progress_bar()

    step = st.session_state.get("wizard_step", 1)
    if step == 1:
        step1_upload()
    elif step == 2:
        step2_anonymize()
    elif step == 3:
        step3_synthesize()
    else:
        st.error("Unknown wizard step.")
        if st.button("Reset"):
            _reset_run()
            st.rerun()

    run_dir = st.session_state.get("run_dir")
    if run_dir:
        st.divider()
        st.caption(f"Working folder: `{run_dir}`")


if __name__ == "__main__":
    main()
