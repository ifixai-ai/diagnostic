import pytest
from ifixai.scoring.engine import (
    compute_category_score,
    compute_overall_score,
    compute_test_score,
)
from ifixai.core.types import (
    EvidenceItem,
    InspectionCategory,
    TestResult,
)


def _evidence(passed: bool) -> EvidenceItem:
    return EvidenceItem(
        test_case_id="tc",
        description="test",
        prompt_sent="prompt",
        expected="yes",
        expected_behavior="yes",
        actual="yes" if passed else "no",
        actual_response="yes" if passed else "no",
        evaluation_result="pass" if passed else "fail",
        passed=passed,
    )


def _make_result(
    test_id: str,
    score: float,
    category: InspectionCategory = InspectionCategory.FABRICATION,
    insufficient: bool = False,
) -> TestResult:
    return TestResult(
        test_id=test_id,
        name=test_id,
        category=category,
        score=score,
        threshold=0.85,
        passed=score >= 0.85,
        passing=score >= 0.85,
        evidence=[],
        insufficient_evidence=insufficient,
    )


class TestComputeTestScore:
    def test_all_pass(self):
        items = [_evidence(True), _evidence(True)]
        assert compute_test_score(items) == 1.0

    def test_half_pass(self):
        items = [_evidence(True), _evidence(False)]
        assert compute_test_score(items) == 0.5

    def test_empty(self):
        assert compute_test_score([]) == 0.0


class TestComputeCategoryScore:
    def test_basic_weighted_average(self):
        results = [
            _make_result("B01", 1.0, InspectionCategory.FABRICATION),
            _make_result("B02", 0.5, InspectionCategory.FABRICATION),
        ]
        weights = {"B01": 1.0, "B02": 1.0}
        category_weights = {InspectionCategory.FABRICATION: 0.3}
        cs = compute_category_score(results, InspectionCategory.FABRICATION, weights, category_weights)
        assert cs.score == pytest.approx(0.75)
        assert cs.test_count == 2

    def test_empty_category_returns_none(self):
        cs = compute_category_score(
            [], InspectionCategory.FABRICATION, {}, {InspectionCategory.FABRICATION: 0.3}
        )
        assert cs.score is None
        assert cs.test_count == 0

    def test_insufficient_evidence_excluded(self):
        results = [
            _make_result("B01", 1.0, InspectionCategory.FABRICATION),
            _make_result("B02", 0.0, InspectionCategory.FABRICATION, insufficient=True),
        ]
        weights = {"B01": 1.0, "B02": 1.0}
        cs = compute_category_score(
            results, InspectionCategory.FABRICATION, weights, {InspectionCategory.FABRICATION: 0.3}
        )
        assert cs.score == pytest.approx(1.0)
        assert cs.test_count == 1


class TestComputeOverallScore:
    def test_weighted_average_across_categories(self):
        from ifixai.core.types import CategoryScore
        cat_scores = [
            CategoryScore(
                category=InspectionCategory.FABRICATION,
                score=1.0,
                weight=0.5,
                test_count=1,
                tests_passed=1,
                test_ids=["B01"],
            ),
            CategoryScore(
                category=InspectionCategory.MANIPULATION,
                score=0.5,
                weight=0.5,
                test_count=1,
                tests_passed=0,
                test_ids=["B07"],
            ),
        ]
        weights = {
            InspectionCategory.FABRICATION: 0.5,
            InspectionCategory.MANIPULATION: 0.5,
        }
        result = compute_overall_score(cat_scores, weights)
        assert result == pytest.approx(0.75)

    def test_none_scores_excluded(self):
        from ifixai.core.types import CategoryScore
        cat_scores = [
            CategoryScore(
                category=InspectionCategory.FABRICATION,
                score=1.0,
                weight=0.5,
                test_count=1,
                tests_passed=1,
                test_ids=["B01"],
            ),
            CategoryScore(
                category=InspectionCategory.MANIPULATION,
                score=None,
                weight=0.5,
                test_count=0,
                tests_passed=0,
                test_ids=[],
            ),
        ]
        weights = {
            InspectionCategory.FABRICATION: 0.5,
            InspectionCategory.MANIPULATION: 0.5,
        }
        result = compute_overall_score(cat_scores, weights)
        assert result == pytest.approx(1.0)

    def test_all_none_returns_none(self):
        from ifixai.core.types import CategoryScore
        cat_scores = [
            CategoryScore(
                category=InspectionCategory.FABRICATION,
                score=None,
                weight=0.5,
                test_count=0,
                tests_passed=0,
                test_ids=[],
            ),
        ]
        result = compute_overall_score(cat_scores, {InspectionCategory.FABRICATION: 0.5})
        assert result is None
