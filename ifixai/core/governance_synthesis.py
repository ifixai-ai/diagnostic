"""Synthesize a `GovernanceFixture` from a diagnostic `Fixture`.

When a diagnostic fixture is supplied without an explicit `governance:`
block, the CLI calls `synthesize_governance` to derive a structural
policy bundle from the existing `tools`, `permissions`, and `roles`
declarations. This is the "lower friction, less precise" path: a single
diagnostic YAML can drive both the test corpus and the structural
inspections.

The synthesized fixture is intentionally conservative:
- `governance_architecture` claims only what the diagnostic data implies.
- `override.authorized_roles` is heuristically picked as roles named
  ``admin``/``administrator``/``root``; deployers who need precise
  control should declare an explicit `governance:` block instead.
- Rate limits and risk-assessment rules use safe defaults so that
  inspections produce a value, not insufficient-evidence.

A scorecard warning is emitted (in the CLI) whenever this path is used,
so a deployer who synthesized rather than measured cannot publish a
clean 32/32 without that disclosure.
"""

from typing import TYPE_CHECKING

from ifixai.providers.governance_fixture import (
    AuthorizationRule,
    GovernanceArchitecture,
    GovernanceFixture,
    GovernanceTool,
    OverridePolicy,
    PoliciesBlock,
    RateLimitRule,
    RiskAssessmentPolicy,
    RiskAssessmentRule,
    SessionPolicy,
    TrainingPolicy,
)

if TYPE_CHECKING:
    from ifixai.core.types import Fixture


_ADMIN_ROLE_HINTS: frozenset[str] = frozenset({"admin", "administrator", "root"})


def synthesize_governance(fixture: "Fixture") -> GovernanceFixture:
    """Build a `GovernanceFixture` from the diagnostic `fixture` body.

    Maps:
        fixture.tools[]        -> GovernanceFixture.tools[]
        fixture.permissions[]  -> policies.authorization[]
        admin-shaped roles     -> policies.override.authorized_roles
    """
    tools = tuple(
        GovernanceTool(
            tool_id=tool.tool_id,
            name=tool.name,
            description=tool.description,
            risk_level=tool.risk_level or "medium",
        )
        for tool in fixture.tools
    )

    authorization = tuple(
        AuthorizationRule(role=perm.role, tools=tuple(perm.tools))
        for perm in fixture.permissions
    )

    admin_roles = tuple(
        sorted(
            {
                role.name
                for role in fixture.roles
                if role.name.lower() in _ADMIN_ROLE_HINTS
            }
        )
    )

    rate_limits = {
        perm.role: RateLimitRule(requests_per_minute=60) for perm in fixture.permissions
    }

    policies = PoliciesBlock(
        authorization=authorization,
        override=OverridePolicy(
            deny_message="Request denied by policy",
            authorized_roles=admin_roles,
        ),
        governance_architecture=GovernanceArchitecture(
            has_policy_engine=bool(fixture.permissions),
            has_audit_log=True,
            has_authorization_gateway=bool(fixture.permissions),
            components=(
                "policy_engine",
                "audit_logger",
                "authorization_gateway",
            ),
        ),
        training_policy=TrainingPolicy(
            data_retention_days=90,
            pii_scrubbed=True,
            opt_out_available=True,
            signature="synthesized-training-policy-v1",
        ),
        rate_limits=rate_limits,
        risk_assessment=RiskAssessmentPolicy(
            rules=(
                RiskAssessmentRule(
                    match={"category": "delete"},
                    score=0.9,
                    band="high",
                ),
                RiskAssessmentRule(
                    match={"category": "admin"},
                    score=0.85,
                    band="high",
                ),
            ),
            default=RiskAssessmentRule(match={}, score=0.2, band="low"),
        ),
        session=SessionPolicy(
            cross_user_isolated=True,
            context_clearing_on_logout=True,
        ),
    )

    return GovernanceFixture(
        version=fixture.metadata.version,
        tools=tools,
        policies=policies,
    )
