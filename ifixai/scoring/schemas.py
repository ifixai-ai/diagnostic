from typing import TypedDict

from ifixai.core.types import TestStatus


class MandatoryMinimumsResult(TypedDict):
    minimums_passed: bool
    minimum_status: dict[str, TestStatus]
