"""Reference `ChatProvider` with a partial structural governance surface.

`MockGovernanceProvider` is the zero-credentials checkpoint provider: it
runs the suite end-to-end without touching a paid LLM endpoint. It
declares every `ProviderCapability` and implements the 11 governance
hooks needed by most structural inspections, but it does NOT yet implement
`apply_override` or `get_configuration_version`, so B04 (Deterministic
Override) and B11 (System Controllability) emit `insufficient_evidence`
against this mock. Expected scored coverage is 30 of 32 inspections — see
the README's "How Many Inspections Score?" table.

Construct with:
    provider = MockGovernanceProvider(
        governance=GovernanceFixture.load("fixtures/governance/mock.yaml"),
        responses={"default": "ACK"},           # keyword -> canned reply
        default_response="ACK",
    )
"""
from __future__ import annotations

from typing import Optional

from ifixai.providers.base import ChatProvider, ProviderCapability
from ifixai.providers.governance_fixture import GovernanceFixture
from ifixai.providers.governance_mixin import GovernanceMixin
from ifixai.types import ChatMessage, ProviderConfig


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
        # Deterministic keyword router — first matching keyword wins, else
        # default_response. Keeps `send_message` stable across runs so
        # reproducibility tests (B22) stay meaningful.
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
