"""Reference `ChatProvider` with a partial structural governance surface.

The zero-credentials checkpoint provider: runs the suite end-to-end
without touching a paid LLM endpoint. Implements 11 of 13 governance
hooks; the two unimplemented ones (`apply_override`,
`get_configuration_version`) cause B04 and B11 to emit
`insufficient_evidence`.

Construct with:
    provider = MockGovernanceProvider(
        governance=GovernanceFixture.load("fixtures/governance/mock.yaml"),
        responses={"default": "ACK"},
        default_response="ACK",
    )
"""
from __future__ import annotations

from typing import Optional

from ifixai.providers.base import ChatProvider, ProviderCapability
from ifixai.providers.governance_fixture import GovernanceFixture
from ifixai.providers.governance_mixin import GovernanceMixin
from ifixai.core.types import ChatMessage, ProviderConfig


class MockGovernanceProvider(GovernanceMixin, ChatProvider):
    """In-memory provider with a full structural governance surface."""

    def __init__(
        self,
        governance: GovernanceFixture,
        responses: Optional[dict[str, str]] = None,
        default_response: str = "ACK",
    ) -> None:
        self._governance = governance
        self._responses = responses or {}
        self._default_response = default_response

    async def send_message(
        self,
        messages: list[ChatMessage],
        config: ProviderConfig,
    ) -> str:
        # Deterministic: first matching keyword wins, else default_response.
        # Keeps replies stable across runs so reproducibility tests are meaningful.
        last_user = next(
            (m.content for m in reversed(messages) if m.role == "user"),
            "",
        )
        for keyword, reply in self._responses.items():
            if keyword in last_user:
                return reply
        return self._default_response

    @classmethod
    def capabilities(cls) -> frozenset[ProviderCapability]:
        return frozenset(ProviderCapability)
