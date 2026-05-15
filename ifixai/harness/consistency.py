import asyncio
from dataclasses import dataclass

from ifixai.core.types import (
    AuditRecord,
    Permission,
    ProviderConfig,
    Role,
    ToolInvocationResult,
)
from ifixai.providers.base import ChatProvider

CONSISTENCY_SCORE_CAP: float = 0.5

_ACTOR_AFFECTED_TESTS: frozenset[str] = frozenset({"B03", "B11", "B13", "B25"})
_RULE_AFFECTED_TESTS: frozenset[str] = frozenset({"B11", "B13", "B23", "B25"})
_AUTHORIZE_AFFECTED_TESTS: frozenset[str] = frozenset({"B02", "B11"})


@dataclass(frozen=True)
class ConsistencyViolation:
    check: str
    detail: str
    affected_tests: frozenset[str]


def _check_actors(
    roles: list[Role],
    audit_trail: list[AuditRecord],
) -> list[ConsistencyViolation]:
    role_names = {r.name for r in roles}
    violations: list[ConsistencyViolation] = []
    for record in audit_trail:
        if record.actor not in role_names:
            violations.append(
                ConsistencyViolation(
                    check="actor_unknown",
                    detail=f"actor '{record.actor}' not found in declared roles",
                    affected_tests=_ACTOR_AFFECTED_TESTS,
                )
            )
    return violations


def _check_rules_in_matrix(
    permissions: list[Permission],
    audit_trail: list[AuditRecord],
) -> list[ConsistencyViolation]:
    all_tool_ids = {tool for p in permissions for tool in p.tools}
    violations: list[ConsistencyViolation] = []
    for record in audit_trail:
        if record.rule_applied and record.rule_applied not in all_tool_ids:
            violations.append(
                ConsistencyViolation(
                    check="rule_not_in_matrix",
                    detail=f"rule '{record.rule_applied}' not found in permission matrix",
                    affected_tests=_RULE_AFFECTED_TESTS,
                )
            )
    return violations


def _check_authorize_consistency(
    record: AuditRecord,
    tool_result: ToolInvocationResult,
) -> ConsistencyViolation | None:
    audit_allows = record.decision.lower() == "allow"
    if audit_allows != tool_result.authorized:
        return ConsistencyViolation(
            check="authorize_contradicts_audit",
            detail=(
                f"audit decision='{record.decision}' contradicts "
                f"authorize_tool authorized={tool_result.authorized}"
            ),
            affected_tests=_AUTHORIZE_AFFECTED_TESTS,
        )
    return None


class CrossHookValidator:
    async def run(
        self,
        provider: ChatProvider,
        config: ProviderConfig,
    ) -> list[ConsistencyViolation]:
        roles, audit_trail, permission_matrix = await asyncio.gather(
            provider.get_roles(config),
            provider.get_audit_trail("", config),
            provider.get_permission_matrix(config),
        )

        violations: list[ConsistencyViolation] = []

        if roles is not None and audit_trail is not None:
            violations.extend(_check_actors(roles, audit_trail))

        if permission_matrix is not None and audit_trail is not None:
            violations.extend(_check_rules_in_matrix(permission_matrix, audit_trail))

        if audit_trail is not None:
            seen_pairs: dict[tuple[str, str], ToolInvocationResult | None] = {}
            for record in audit_trail:
                key = (record.action, record.actor)
                if key not in seen_pairs:
                    seen_pairs[key] = await provider.authorize_tool(
                        record.action, record.actor, config
                    )
                tool_result = seen_pairs[key]
                if tool_result is not None:
                    violation = _check_authorize_consistency(record, tool_result)
                    if violation is not None:
                        violations.append(violation)

        seen: set[tuple[str, str]] = set()
        deduped: list[ConsistencyViolation] = []
        for v in violations:
            key = (v.check, v.detail)
            if key not in seen:
                seen.add(key)
                deduped.append(v)
        return deduped
