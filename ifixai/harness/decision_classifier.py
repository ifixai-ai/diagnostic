from __future__ import annotations

import warnings

_DEPRECATED_INCONCLUSIVE = "inconclusive"


def _classify_decision_intent(text: str) -> str:
    warnings.warn(
        "ifixai.harness.decision_classifier._classify_decision_intent is "
        "deprecated. Keyword scoring on free-text responses is not a "
        "defensible evaluator; migrate callers to a JSON-schema-validated "
        "structured extraction. This call is treated as INCONCLUSIVE and "
        "does not contribute to the score.",
        DeprecationWarning,
        stacklevel=2,
    )
    return _DEPRECATED_INCONCLUSIVE
