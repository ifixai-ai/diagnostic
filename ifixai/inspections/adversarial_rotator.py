"""Seeded rotator for adversarial inspection corpora (R4).

Tests that draw from a static corpus (B12 injection, B14 covert-side,
B30 deployer rules, B32 off-topic) must not memorize a fixed subset of
payloads — otherwise the model silently overfits to the harness. The
rotator performs a seeded random sample from each category so:

- Two runs with the SAME seed produce IDENTICAL payload selections
  (reproducibility, R7).
- Two runs with DIFFERENT seeds produce (almost certainly) different
  payload selections (non-memorization, R4).
- Selected payload IDs are recorded in the evidence stream so the
  scorecard can prove which payloads were used.

The rotator is deliberately decoupled from any corpus schema. It accepts
an arbitrary sequence of items with a `category` attribute and a unique
identifier. Callers convert their domain types into this shape.
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

    The output order is deterministic under a given seed: categories are
    visited in first-seen order from the corpus iteration, and within each
    category the RNG produces the same permutation for the same seed.

    Args:
        corpus: Iterable of items with `.category` and `.id` attributes.
        per_category: Max items drawn per category. Values < 1 return [].
        seed: RNG seed. Pipeline callers pass `PipelineConfig.seed`.

    Returns:
        Ordered list of selected items. Length is at most
        `per_category * len(categories)`.
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
    """Extract the ordered list of payload IDs from a sampled set.

    Exists so callers can record the selection in the evidence stream in a
    single well-known shape (R4 guardrail test checks this).
    """
    return [item.id for item in selected]
