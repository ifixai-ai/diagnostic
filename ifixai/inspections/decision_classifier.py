"""Deprecated decision-intent classifier (T025).

The old keyword-scoring implementation was the canonical example of
R10/R11 violation — counting keyword hits in free text and calling the
result a "decision classification" is precisely the sort of theatrical
scoring the reliability platform is meant to replace.

This shim emits a `DeprecationWarning` on every call and returns a
sentinel value that maps cleanly onto `EvaluationMethod.INCONCLUSIVE`.
Callers MUST migrate to a structured-output path (Mode A in
`contracts/evaluation-pipeline.contract.md`):

    - Ask the model for a JSON `{"decision": "allow"|"deny"}` envelope.
    - Validate against `jsonschema`.
    - On parse failure, mark the evidence item `INCONCLUSIVE` with
      `inconclusive_reason="judge_parse_error"`.

The shim is intentionally noisy so that any test still calling
into it fails its own `INCONCLUSIVE` ratio gate, surfacing the
regression at the run level (R8/R10).
"""
from __future__ import annotations

import warnings

# Literal sentinel used by the shim. Maps to
# `InconclusiveReasonCode == "self_report_not_verifiable"` in the
# scoring engine.
_DEPRECATED_INCONCLUSIVE = "inconclusive"


def _classify_decision_intent(text: str) -> str:
    """DEPRECATED. Returns ``"inconclusive"`` and emits a warning.

    Do not add new call-sites. Existing call-sites MUST migrate to a
    JSON-schema-validated structured extraction (Mode A). Keyword scoring
    on free-text responses is forbidden by R10.
    """
    warnings.warn(
        "ifixai.inspections.decision_classifier._classify_decision_intent is "
        "deprecated: keyword scoring on free-text responses is not a "
        "defensible evaluator (R10). Migrate the caller to a "
        "JSON-schema-validated structured extraction. This call is being "
        "treated as INCONCLUSIVE and will not contribute to the score.",
        DeprecationWarning,
        stacklevel=2,
    )
    return _DEPRECATED_INCONCLUSIVE
