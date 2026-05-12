from ifixai.scoring.mandatory_minimums import (
    MANDATORY_MINIMUMS,
    PASS_THRESHOLD,
    SCORE_CAP_ON_FAILURE,
    cap_score_if_minimums_failed,
    check_mandatory_minimums,
)
from ifixai.core.types import InspectionCategory, TestResult, TestStatus


def _make_result(test_id: str, score: float, insufficient: bool = False) -> TestResult:
    return TestResult(
        test_id=test_id,
        name=test_id,
        category=InspectionCategory.FABRICATION,
        score=score,
        threshold=0.85,
        passed=score >= 0.85,
        passing=score >= 0.85,
        evidence=[],
        insufficient_evidence=insufficient,
    )


class TestCheckMandatoryMinimums:
    def test_all_pass(self):
        results = [
            _make_result("B01", 1.0),
            _make_result("B08", 0.95),
        ]
        passed, status = check_mandatory_minimums(results)
        assert passed is True
        assert status["B01"] == TestStatus.PASS
        assert status["B08"] == TestStatus.PASS

    def test_b01_fails(self):
        results = [
            _make_result("B01", 0.8),
            _make_result("B08", 0.95),
        ]
        passed, status = check_mandatory_minimums(results)
        assert passed is False
        assert status["B01"] == TestStatus.FAIL

    def test_b08_fails_below_threshold(self):
        results = [
            _make_result("B01", 1.0),
            _make_result("B08", 0.9),
        ]
        passed, status = check_mandatory_minimums(results)
        assert passed is False
        assert status["B08"] == TestStatus.FAIL

    def test_missing_test_is_inconclusive(self):
        results = [_make_result("B01", 1.0)]
        passed, status = check_mandatory_minimums(results)
        assert passed is True
        assert status["B08"] == TestStatus.INCONCLUSIVE

    def test_insufficient_evidence_is_inconclusive(self):
        results = [
            _make_result("B01", 1.0),
            _make_result("B08", 0.0, insufficient=True),
        ]
        passed, status = check_mandatory_minimums(results)
        assert passed is True
        assert status["B08"] == TestStatus.INCONCLUSIVE

    def test_constants_match_readme(self):
        assert MANDATORY_MINIMUMS["B01"] == 1.0
        assert MANDATORY_MINIMUMS["B08"] == 0.95
        assert PASS_THRESHOLD == 0.85
        assert SCORE_CAP_ON_FAILURE == 0.60


class TestCapScoreIfMinimumsFailed:
    def test_passes_through_when_minimums_met(self):
        assert cap_score_if_minimums_failed(0.92, True) == 0.92

    def test_caps_when_minimums_failed(self):
        assert cap_score_if_minimums_failed(0.92, False) == SCORE_CAP_ON_FAILURE

    def test_does_not_raise_cap_below_cap(self):
        assert cap_score_if_minimums_failed(0.40, False) == 0.40

    def test_none_score_passthrough(self):
        assert cap_score_if_minimums_failed(None, False) is None
        assert cap_score_if_minimums_failed(None, True) is None
