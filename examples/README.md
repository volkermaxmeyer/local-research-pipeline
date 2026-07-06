# Example output

Both files were produced by the pipeline from the synthetic test interview
in `../test-data/` — no real person was recorded.

- `sample-interview.anon.md` — the transcript after local anonymization
  (spaCy NER). Names, organizations and locations are replaced with
  consistent placeholder tokens.
- `sample-interview.synthesis.md` — the structured 7-section synthesis
  generated locally by `qwen3:8b` via Ollama.

The re-identification map (`_key.json`) that the pipeline also produces
stays on the machine and is deliberately not part of this repository.

Two things worth knowing:

- Placeholder prefixes are German (`Firma` = company, `Ort` = place) —
  the tool was built for German-language research contexts.
- NER quality depends on matching the spaCy model to the transcript
  language. This English example was anonymized with `en_core_web_lg`;
  German transcripts use `de_core_news_lg` (the default).
