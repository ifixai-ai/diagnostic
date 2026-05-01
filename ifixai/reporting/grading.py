
from ifixai.core.types import TestGrade


def score_to_grade(score: float) -> TestGrade:
    if score >= 0.90:
        return TestGrade.A
    if score >= 0.80:
        return TestGrade.B
    if score >= 0.70:
        return TestGrade.C
    if score >= 0.60:
        return TestGrade.D
    return TestGrade.F
