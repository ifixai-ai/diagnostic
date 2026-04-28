from math import sqrt
from typing import TYPE_CHECKING

from ifixai.core.types import ConfidenceInterval

if TYPE_CHECKING:
    from ifixai.core.types import EvidenceItem

_Z_95 = 1.959963984540054

def z_for_confidence(confidence_level: float) -> float:
    if confidence_level == 0.95:
        return _Z_95
    if confidence_level == 0.99:
        return 2.5758293035489004
    if confidence_level == 0.90:
        return 1.6448536269514722
    raise ValueError(
        f"Unsupported confidence_level={confidence_level}; "
        "supported values are 0.90, 0.95, 0.99"
    )

class ProportionCI:

    def __init__(self, confidence_level: float = 0.95) -> None:
        self._z = z_for_confidence(confidence_level)
        self._confidence_level = confidence_level

    def compute(self, evidence: "list[EvidenceItem]") -> ConfidenceInterval:
        sample_size = len(evidence)

        if sample_size == 0:
            return ConfidenceInterval(
                lower=0.0,
                upper=0.0,
                method="wilson",
                sample_size=0,
                warning="No evidence items to compute CI",
            )

        passed = sum(1 for e in evidence if e.passed)
        lower, upper = wilson_interval(passed, sample_size, self._z)

        warning: str | None = None
        if sample_size < 5:
            warning = f"Small sample size (n={sample_size}); CI is wide"

        return ConfidenceInterval(
            lower=round(lower, 4),
            upper=round(upper, 4),
            method="wilson",
            sample_size=sample_size,
            warning=warning,
        )

def wilson_interval(passed: int, total: int, z: float = _Z_95) -> tuple[float, float]:
    if total == 0:
        return (0.0, 0.0)
    if passed < 0 or passed > total:
        raise ValueError(
            f"Invalid proportion: passed={passed} total={total}"
        )
    p = passed / total
    denom = 1.0 + z * z / total
    centre = (p + z * z / (2.0 * total)) / denom
    half = (z * sqrt(p * (1.0 - p) / total + z * z / (4.0 * total * total))) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))
