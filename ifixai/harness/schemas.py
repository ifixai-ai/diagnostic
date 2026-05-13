from typing import TypedDict


class EvaluationOutcome(TypedDict):
    passed: bool
    reason: str
