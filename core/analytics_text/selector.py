from __future__ import annotations

import hashlib
from collections.abc import Sequence

from .models import GenerationState, PhraseVariant


def deterministic_index(length: int, key: str) -> int:
    if length <= 0:
        raise ValueError("Cannot choose from an empty collection")
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return int(digest[:16], 16) % length


def choose_variant(
    variants: Sequence[PhraseVariant],
    *,
    key: str,
    state: GenerationState,
) -> PhraseVariant:
    if not variants:
        raise ValueError("No phrase variants available")
    unused = [item for item in variants if item.id not in state.used_phrase_ids]
    pool = unused or list(variants)
    tracked = ("рівень виконання", "загальний результат", "показник", "становить", "зафіксовано", "потребує уваги")
    scored = []
    for item in pool:
        lowered = item.template.lower()
        score = sum(state.used_lemmas.get(lemma, 0) for lemma in tracked if lemma in lowered)
        scored.append((score, item))
    min_score = min(score for score, _ in scored)
    best_pool = [item for score, item in scored if score == min_score]
    selected = best_pool[deterministic_index(len(best_pool), key)]
    state.used_phrase_ids.add(selected.id)
    lowered = selected.template.lower()
    for lemma in tracked:
        if lemma in lowered:
            state.used_lemmas[lemma] = state.used_lemmas.get(lemma, 0) + 1
    return selected
