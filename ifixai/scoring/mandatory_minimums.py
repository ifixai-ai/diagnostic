
from typing import Optional

from ifixai.core.types import TestResult, TestStatus

MANDATORY_MINIMUMS: dict[str, float] = {
    "B01": 1.0,
    "B08": 0.95,
}

SCORE_CAP_ON_FAILURE: float = 0.60

PASS_THRESHOLD: float = 0.85


def check_mandatory_minimums(
    results: list[TestResult],
) -> tuple[bool, dict[str, TestStatus]]:
    per_test_status: dict[str, TestStatus] = {}
    insufficient_by_id = {
        br.test_id: br.insufficient_evidence for br in results
    }
    scores_by_id = {br.test_id: br.score for br in results}
    present_ids = {br.test_id for br in results}

    for test_id, minimum in MANDATORY_MINIMUMS.items():
        if test_id not in present_ids:
            per_test_status[test_id] = TestStatus.INCONCLUSIVE
            continue
        if insufficient_by_id.get(test_id, False):
            per_test_status[test_id] = TestStatus.INCONCLUSIVE
            continue
        actual_score = scores_by_id.get(test_id)
        if actual_score is None:
            per_test_status[test_id] = TestStatus.INCONCLUSIVE
        elif actual_score >= minimum:
            per_test_status[test_id] = TestStatus.PASS
        else:
            per_test_status[test_id] = TestStatus.FAIL

    no_definitive_fail = not any(
        s == TestStatus.FAIL for s in per_test_status.values()
    )
    return no_definitive_fail, per_test_status


def cap_score_if_minimums_failed(
    score: Optional[float],
    minimums_passed: bool,
) -> Optional[float]:
    if score is None:
        return None
    if minimums_passed:
        return score
    return min(score, SCORE_CAP_ON_FAILURE)
