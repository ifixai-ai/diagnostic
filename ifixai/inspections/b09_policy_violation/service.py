from ifixai.core.types import Fixture


class PolicyContextSummary(dict[str, str]):
    pass


def format_policy_context(fixture: Fixture) -> str:
    policy = fixture.policies
    roles = policy.override_allowed_roles
    roles_str = ", ".join(roles) if roles else "(none)"
    return (
        f"Confidence threshold: {policy.confidence_threshold}\n"
        f"Citation required: {policy.citation_required}\n"
        f"Audit logging: {policy.audit_logging}\n"
        f"Override allowed roles: {roles_str}"
    )


def build_policy_context_summary(fixture: Fixture) -> dict[str, str]:
    policy = fixture.policies
    roles = policy.override_allowed_roles
    formatted = format_policy_context(fixture)
    return {
        "confidence_threshold": str(policy.confidence_threshold),
        "citation_required": str(policy.citation_required),
        "audit_logging": policy.audit_logging,
        "override_allowed_roles": ", ".join(roles) if roles else "(none)",
        "formatted_block": formatted,
    }
