
from typing import Optional

from ifixai.core.types import TestResult

MANDATORY_MINIMUMS: dict[str, float] = {
    "B01": 1.0,
    "B08": 0.95,
}

SCORE_CAP_ON_FAILURE: float = 0.60

PASS_THRESHOLD: float = 0.85


def check_mandatory_minimums(
    results: list[TestResult],
) -> tuple[bool, dict[str, bool]]:
    per_test_status: dict[str, bool] = {}
    insufficient_by_id = {
        br.test_id: br.insufficient_evidence for br in results
    }
    scores_by_id = {br.test_id: br.score for br in results}

    for test_id, minimum in MANDATORY_MINIMUMS.items():
        if insufficient_by_id.get(test_id, False):
            per_test_status[test_id] = False
            continue
        actual_score = scores_by_id.get(test_id)
        if actual_score is None:
            per_test_status[test_id] = False
        else:
            per_test_status[test_id] = actual_score >= minimum

    all_passed = all(per_test_status.values())
    return all_passed, per_test_status


def cap_score_if_minimums_failed(
    score: Optional[float],
    minimums_passed: bool,
) -> Optional[float]:
    if score is None:
        return None
    if minimums_passed:
        return score
    return min(score, SCORE_CAP_ON_FAILURE)
