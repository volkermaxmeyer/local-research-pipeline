# The product process behind this tool

This document is the curated version of the PRD and eval that drove development. It shows how the tool was scoped, built and verified.

## The problem

UX researchers and service designers work with interview data that has two sensitivity problems at once:

1. **PII in raw audio and transcripts.** Names, companies, places, health or financial details. Cloud transcription services (Otter, Fireflies, Rev) range from borderline to unacceptable under GDPR.
2. **Sensitivity of the synthesis itself.** Even with PII removed, theme clusters, pain points and quotes often contain strategically delicate material: internal stakeholder interviews, failed products, competitive observations.

Existing tools solve one half each. Local transcription exists (MacWhisper). Local LLM synthesis exists as demos. What was missing is a combined, local, end-to-end journey from audio to structured synthesis.

## Who it's for

Researchers and service designers who need to process interviews they are not allowed to upload: NDA material, banking compliance flows, identity verification research. The tool must work for real research sessions, not just demo well.

## Scope decisions

Deliberately in:

- One pipeline, three visible steps: transcribe, anonymize, synthesize
- A mapping viewer so the researcher can inspect the anonymization before trusting it (verify, then synthesize)
- A model picker to trade speed against depth
- Graceful failure when Ollama is not running

Deliberately out:

- Multi-user, auth, hosting. This runs on `localhost` only.
- Speaker diarization, custom word lists, LLM review passes for edge cases
- Batch mode and cross-interview synthesis
- Production-grade error handling, logging, tests

Cutting these kept the build small enough to verify properly. Each exclusion is documented, not forgotten; see the [decision log](decision-log.md).

## Eval-driven development

Before polishing, the app was specified as 12 pass/fail criteria. Each one names how to test it and what counts as passing. Abridged:

| ID | Criterion |
|----|-----------|
| E1 | Header and privacy notice visible on all three steps |
| E2 | Progress indicator marks current, past and future steps correctly |
| E3 | "Continue" is disabled until a file is uploaded |
| E4 | Upload shows file info (icon, name, size) |
| E5 | Whisper settings appear only when audio is present |
| E6 | Anonymization produces the expected output files |
| E7 | Mapping viewer shows entity counts and the JSON mapping |
| E8 | Synthesis step blocks cleanly when Ollama is down |
| E9 | Synthesis produces markdown with the 7 expected sections |
| E10 | Download button delivers the `.synthesis.md` file |
| E11 | "New run" resets state and creates a fresh working folder |
| E12 | No outbound network traffic except `localhost:11434` |

E12 is the criterion that turns the privacy promise into something testable: the claim "nothing leaves your machine" is checked against the code and network behavior, not just asserted in marketing copy.

The first eval run surfaced a UX problem: multi-file upload complicated the flow without serving the core use case. The app was simplified to single-file upload, and the re-run passed 12 of 12.

## What the eval did for the product

Three concrete effects:

1. **It forced testable claims.** "Privacy-first" became E12. "The researcher can verify before trusting" became E7.
2. **It caught scope creep early.** The multi-file feature failed the "does this serve the journey" test and was cut the same day.
3. **It made the model upgrade safe.** When the synthesis models were swapped months later, the same criteria (7 sections, no leaks, E12) verified the change. See the [decision log](decision-log.md).
