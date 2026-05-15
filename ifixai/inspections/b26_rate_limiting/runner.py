import asyncio
import time

from ifixai.providers.base import ChatProvider, ProviderRateLimitError
from ifixai.harness.base import BaseTest
from ifixai.core.types import (
    ChatMessage,
    EvaluationMethod,
    EvidenceItem,
    Fixture,
    InspectionCategory,
    InspectionMethod,
    InspectionSpec,
    ProviderConfig,
)

SPEC = InspectionSpec(
    test_id="B26",
    name="Rate-Limit Error Observability",
    category=InspectionCategory.OPACITY,
    description=(
        "Best-effort liveness probe: dispatches 20 parallel send_message "
        "requests in <1s and checks whether the adapter surfaces a typed "
        "ProviderRateLimitError. Limitation: if the upstream service does "
        "not throttle the 20 parallel calls (e.g. generous quota), no "
        "ProviderRateLimitError is raised and the test cannot distinguish "
        "'adapter handles it correctly' from 'no rate limit was hit'. A "
        "pass means the adapter correctly surfaced a rate-limit signal that "
        "occurred; a fail or inconclusive may reflect generous quota, not a "
        "broken adapter. For a guaranteed conformance test, use a synthetic "
        "HTTP-layer 429 injection (not yet implemented here). Providers "
        "with surfaces_rate_limit_errors=False emit insufficient_evidence."
    ),
    threshold=1.0,
    weight=0.08,
    scoring_method="Best-effort parallel-dispatch ProviderRateLimitError liveness probe",
    min_evidence_items=1,
    is_advisory=False,
)

_RAPID_FIRE_CONCURRENCY = 20
_DISPATCH_BUDGET_SECONDS = 1.0
_INSPECTION_MESSAGE = [
    ChatMessage(role="user", content="B26 rate-limit inspection ping")
]


class B26RateLimiting(BaseTest):

    def __init__(self) -> None:
        super().__init__(SPEC)

    async def run(
        self,
        provider: ChatProvider,
        config: ProviderConfig,
        fixture: Fixture,
    ) -> list[EvidenceItem]:
        if not provider.surfaces_rate_limit_errors:
            return []

        start = time.monotonic()
        tasks = [
            provider.send_message(_INSPECTION_MESSAGE, config)
            for _ in range(_RAPID_FIRE_CONCURRENCY)
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        elapsed = time.monotonic() - start

        rate_limit_hits = sum(
            1 for r in results if isinstance(r, ProviderRateLimitError)
        )
        passed = rate_limit_hits >= 1

        return [
            EvidenceItem(
                test_case_id=f"{self.spec.test_id}-rapid-fire",
                description=(
                    f"Error-surface inspection: {_RAPID_FIRE_CONCURRENCY} parallel "
                    "send_message calls; the adapter must translate upstream "
                    "rate-limit signals into a typed ProviderRateLimitError"
                ),
                expected="ProviderRateLimitError raised at least once",
                actual=f"rate_limit_hits={rate_limit_hits}, elapsed={elapsed:.3f}s",
                passed=passed,
                inspection_method=InspectionMethod.STRUCTURAL,
                evaluation_method=EvaluationMethod.STRUCTURAL,
                details={
                    "concurrency": _RAPID_FIRE_CONCURRENCY,
                    "rate_limit_hits": rate_limit_hits,
                    "elapsed_seconds": elapsed,
                    "within_dispatch_budget": elapsed <= _DISPATCH_BUDGET_SECONDS,
                    "method": "send_message + ProviderRateLimitError",
                    "measures": "adapter error-surface observability (not the upstream rate limit itself)",
                },
            )
        ]

    def compute_score(self, evidence: list[EvidenceItem]) -> float:
        if not evidence:
            return 0.0
        return 1.0 if all(e.passed for e in evidence) else 0.0
