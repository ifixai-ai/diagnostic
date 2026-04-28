"""Seeded rotator for adversarial inspection corpora.

Tests that draw from a static corpus must not memorize a fixed subset of
payloads — otherwise the model silently overfits to the harness. The
rotator performs a seeded random sample from each category so the same
seed produces an identical selection (reproducibility) and different
seeds produce different selections (non-memorization). Selected payload
IDs are recorded in the evidence stream.
"""
from __future__ import annotations

import random
from collections import defaultdict
from collections.abc import Iterable, Sequence
from typing import Protocol, TypeVar


class _Categorized(Protocol):
    category: str
    id: str


T = TypeVar("T", bound=_Categorized)


def sample(
    corpus: Iterable[T],
    per_category: int,
    seed: int,
) -> list[T]:
    """Sample up to `per_category` items from each category in `corpus`.

    Order is deterministic under a given seed: categories are visited in
    first-seen order from corpus iteration, and within each category the
    RNG produces the same permutation for the same seed.
    """
    if per_category < 1:
        return []

    by_cat: dict[str, list[T]] = defaultdict(list)
    cat_order: list[str] = []
    for item in corpus:
        if item.category not in by_cat:
            cat_order.append(item.category)
        by_cat[item.category].append(item)

    rng = random.Random(seed)
    out: list[T] = []
    for cat in cat_order:
        items = list(by_cat[cat])
        rng.shuffle(items)
        out.extend(items[:per_category])
    return out


def selected_ids(selected: Sequence[_Categorized]) -> list[str]:
    return [item.id for item in selected]
