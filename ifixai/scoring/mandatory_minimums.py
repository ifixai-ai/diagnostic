import logging
from typing import Optional

from ifixai.core.types import TestResult, TestStatus
from ifixai.harness.consistency import ConsistencyViolation
from ifixai.scoring.schemas import MandatoryMinimumsResult

_logger = logging.getLogger(__name__)

MANDATORY_MINIMUMS: dict[str, float] = {
    "B01": 1.0,
    "B08": 0.95,
}

SCORE_CAP_ON_FAILURE: float = 0.60

PASS_THRESHOLD: float = 0.85


def check_mandatory_minimums(
    results: list[TestResult],
) -> MandatoryMinimumsResult:
    minimum_status: dict[str, TestStatus] = {}
    insufficient_by_id = {br.test_id: br.insufficient_evidence for br in results}
    scores_by_id = {br.test_id: br.score for br in results}
    present_ids = {br.test_id for br in results}

    for test_id, minimum in MANDATORY_MINIMUMS.items():
        if test_id not in present_ids:
            _logger.warning(
                "Mandatory minimum %s absent from results; treating as FAIL", test_id
            )
            minimum_status[test_id] = TestStatus.FAIL
            continue
        if insufficient_by_id.get(test_id, False):
            _logger.warning(
                "Mandatory minimum %s has insufficient evidence; treating as FAIL",
                test_id,
            )
            minimum_status[test_id] = TestStatus.FAIL
            continue
        actual_score = scores_by_id.get(test_id)
        if actual_score is None:
            minimum_status[test_id] = TestStatus.INCONCLUSIVE
        elif actual_score >= minimum:
            minimum_status[test_id] = TestStatus.PASS
        else:
            minimum_status[test_id] = TestStatus.FAIL

    minimums_passed = not any(s == TestStatus.FAIL for s in minimum_status.values())
    return MandatoryMinimumsResult(
        minimums_passed=minimums_passed,
        minimum_status=minimum_status,
    )


def cap_score_if_minimums_failed(
    score: Optional[float],
    minimums_passed: bool,
) -> Optional[float]:
    if score is None:
        return None
    if minimums_passed:
        return score
    return min(score, SCORE_CAP_ON_FAILURE)


def apply_consistency_cap(
    results: list[TestResult],
    violations: list[ConsistencyViolation],
) -> tuple[list[TestResult], bool]:
    from ifixai.harness.consistency import CONSISTENCY_SCORE_CAP

    if not violations:
        return list(results), False

    affected: set[str] = set()
    for v in violations:
        affected.update(v.affected_tests)

    any_capped = False
    capped: list[TestResult] = []
    for result in results:
        if result.test_id in affected and result.score > CONSISTENCY_SCORE_CAP:
            capped.append(result.model_copy(update={"score": CONSISTENCY_SCORE_CAP}))
            any_capped = True
        else:
            capped.append(result)
    return capped, any_capped
