from typing import TypedDict

from ifixai.core.types import TestResult


class ResumeState(TypedDict):
    cached: dict[str, TestResult]
    remaining: list[str]


class WilsonInterval(TypedDict):
    lower: float
    upper: float
