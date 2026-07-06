from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

_nlp_cache: dict[str, object] = {}

LABEL_TO_CATEGORY = {
    "PER": "persons",
    "PERSON": "persons",
    "ORG": "orgs",
    "LOC": "locations",
    "GPE": "locations",
}

CATEGORY_TO_PREFIX = {
    "persons": "Person",
    "orgs": "Firma",
    "locations": "Ort",
}


@dataclass
class AnonResult:
    text: str
    new_entities: int
    used_entities: int


def _get_nlp(model_name: str = "de_core_news_lg"):
    if model_name in _nlp_cache:
        return _nlp_cache[model_name]
    import spacy

    nlp = spacy.load(model_name)
    _nlp_cache[model_name] = nlp
    return nlp


def _next_token(mapping: dict, category: str) -> str:
    n = len(mapping[category]) + 1
    return f"[{CATEGORY_TO_PREFIX[category]}_{n}]"


def _canonical(text: str) -> str:
    return " ".join(text.split())


def anonymize_text(text: str, mapping: dict, model_name: str = "de_core_news_lg") -> AnonResult:
    nlp = _get_nlp(model_name)
    doc = nlp(text)

    spans = []
    for ent in doc.ents:
        category = LABEL_TO_CATEGORY.get(ent.label_)
        if not category:
            continue
        spans.append((ent.start_char, ent.end_char, category, _canonical(ent.text)))

    # remove overlapping (keep longer); spaCy usually non-overlapping but be safe
    spans.sort(key=lambda s: (s[0], -(s[1] - s[0])))
    pruned: list[tuple[int, int, str, str]] = []
    last_end = -1
    for s in spans:
        if s[0] < last_end:
            continue
        pruned.append(s)
        last_end = s[1]

    new_count = 0
    used_count = 0
    # apply from end to start so offsets stay valid
    out = text
    for start, end, category, surface in reversed(pruned):
        bucket = mapping[category]
        if surface in bucket:
            token = bucket[surface]
            used_count += 1
        else:
            token = _next_token(mapping, category)
            bucket[surface] = token
            new_count += 1
        out = out[:start] + token + out[end:]

    return AnonResult(text=out, new_entities=new_count, used_entities=used_count)


def anonymize_file(source: Path, target: Path, mapping: dict, model_name: str = "de_core_news_lg") -> AnonResult:
    text = source.read_text(encoding="utf-8")
    result = anonymize_text(text, mapping, model_name=model_name)
    target.write_text(result.text, encoding="utf-8")
    return result
