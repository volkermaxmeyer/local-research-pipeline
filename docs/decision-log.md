# Decision log

Key decisions with reasoning and evidence. Format: context, decision, why, evidence.

## 1. Local-only architecture

**Context:** The entire use case is research material that must not leave the machine. A single hidden cloud call would invalidate the product promise.

**Decision:** Every processing step runs locally. The synthesis layer talks to Ollama over HTTP using only the Python standard library (`urllib`), no HTTP client dependencies.

**Why:** Zero external dependencies in the synthesis layer means anyone auditing the code can confirm there is no hidden cloud client. Cloud LLMs were rejected outright: even providers with no-training policies are off-limits for NDA material and compliance interviews.

**Evidence:** Eval criterion E12 verifies that the only outbound connection during synthesis is `localhost:11434`.

## 2. Model baseline 2024, measured upgrade 2026

**Context:** The pipeline launched with `llama3.1:8b` (thorough) and `gemma2:2b` (fast). By mid-2026 both were two model generations old.

**Decision:** Upgrade to `qwen3:8b` as the new default and `gemma3:4b` as the fast option. Keep the old models selectable for comparison. Qwen3's thinking mode is disabled via `think: false` so reasoning traces never leak into the synthesis output.

**Why:** Qwen3 8B became the consensus choice for the 8 GB class in 2026, with better instruction-following on the synthesis rubrics. The upgrade was only made after both new models passed the same checks the originals had to pass.

**Evidence:** Both new models produce all 7 required sections on the test interview. No thinking-trace leaks in the qwen3 output.

## 3. Regurgitation re-test before trusting the fast tier

**Context:** A prior study for this pipeline found that `gemma2:2b` copied verbatim transcript passages into its synthesis instead of generalizing (few-shot regurgitation). That made the fast tier unsafe for real use.

**Decision:** Before promoting `gemma3:4b` to the fast slot, re-measure the failure mode instead of assuming the new generation fixed it.

**Why:** A known failure gets a regression test, not a hope. The test: sample 120-character blocks from the source transcript and count how many appear verbatim in the synthesis.

**Evidence:** 0 of 14 sampled blocks appeared in the gemma3 output. The failure mode did not reproduce, so the fast tier is usable again.

## 4. Context window 8k → 16k, plus an overflow warning

**Context:** Ollama truncates the start of the prompt silently when input exceeds `num_ctx`. A real 60-minute interview is roughly 10,000+ tokens. With the original 8,192-token window, the synthesis would quietly ignore the beginning of the interview, and nobody would notice.

**Decision:** Double `num_ctx` to 16,384 and estimate token count before synthesis. If the transcript plus system prompt approaches the limit, the UI warns before the run starts.

**Why:** Silent truncation is the worst failure class in a research tool: the output looks complete and is wrong. A visible warning turns a silent data-quality bug into an informed user decision.

**Evidence:** Warning triggers on transcripts above roughly 14k estimated tokens; the 3-minute test interview stays far below it.

## 5. NER model must match the transcript language

**Context:** The anonymizer used the German spaCy model for everything. On the English test interview it missed the participant's name repeatedly while over-tagging filler words as organizations. The core privacy feature looked broken in exactly the file a first-time user would try.

**Decision:** Pick the spaCy model by the selected transcript language: English uses `en_core_web_lg`, German and auto-detect use `de_core_news_lg`.

**Why:** NER quality collapses across languages. A privacy tool that visibly fails at its core job on the demo path loses trust it cannot win back in a README.

**Evidence:** Re-running the English test transcript with the matched model caught every occurrence of the participant's name.

## 6. Deliberate out-of-scope

**Context:** Prototype with a one-person build budget and a clear core journey.

**Decision:** Speaker diarization, custom word lists, batch mode, cross-interview synthesis, CI and tests stay out. A known spaCy weakness (NER trained on properly-cased text struggles with lowercase Whisper output) is documented as a finding rather than patched with a preprocessing step.

**Why:** Every one of these would grow the surface area faster than it grows the core value: one interview in, one trustworthy synthesis out. Documenting a limitation honestly beats half-fixing it.

**Evidence:** The scope list in [product-process.md](product-process.md) and the "Known limits" section of the README match; nothing is silently missing.
