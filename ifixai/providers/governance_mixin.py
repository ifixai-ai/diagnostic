"""Shared structural-method implementation for ChatProvider subclasses.

`GovernanceMixin` reads every structural-method result from an in-memory
`GovernanceFixture`. Both `MockGovernanceProvider` and `OpenAIProvider`
compose it so tests hit a **real** structural surface instead of
asking the LLM to self-report its own governance (R2).

The mixin is test-aware: callers pass the `test_id` via the
ambient `config.model_extra` field (pydantic's escape hatch), which lets
the pipeline wire per-test overrides without changing every
structural-method signature.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from ifixai.providers.governance_fixture import GovernanceFixture, PoliciesBlock
from ifixai.types import (
    AuditRecord,
    Permission,
    ProviderConfig,
    Role,
    ToolInfo,
    ToolInvocationResult,
)


def _test_id(config: ProviderConfig) -> Optional[str]:
    """Extract the test id the pipeline annotated on the config.

    The pipeline sets `config.model_extra['test_id']` immediately
    before calling a structural method so per-test overrides apply.
    Providers outside the pipeline just get the base policies block.
    """
    extra = getattr(config, "model_extra", None) or {}
    bid = extra.get("test_id")
    return bid if isinstance(bid, str) else None


class GovernanceMixin:
    """Drops structural-method implementations onto a `ChatProvider`.

    Subclasses MUST set `self._governance: GovernanceFixture | None` in
    their constructor. When it is `None`, every structural method returns
    `None`, preserving the contract that the pipeline marks the inspection
    `INCONCLUSIVE(structural_capability_missing)` rather than silently
    falling back to LLM self-report.
    """

    _governance: Optional[GovernanceFixture]

    def _policies(self, config: ProviderConfig) -> Optional[PoliciesBlock]:
        if self._governance is None:
            return None
        return self._governance.policies_for(_test_id(config))

    async def list_tools(
        self, config: ProviderConfig
    ) -> list[ToolInfo] | None:
        if self._governance is None:
            return None
        return [
            ToolInfo(
                tool_id=t.tool_id,
                name=t.name,
                description=t.description,
                parameters=t.parameters,
                risk_level=t.risk_level,
            )
            for t in self._governance.tools
        ]

    async def authorize_tool(
        self,
        tool_id: str,
        user_role: str,
        config: ProviderConfig,
    ) -> ToolInvocationResult | None:
        policies = self._policies(config)
        if policies is None:
            return None
        matching = next(
            (r for r in policies.authorization if r.role == user_role), None
        )
        if matching is None:
            return ToolInvocationResult(
                authorized=False,
                executed=False,
                result=None,
                error=policies.override.deny_message,
                policy_rule=f"no_rule_for_role:{user_role}",
            )
        allowed = "*" in matching.tools or tool_id in matching.tools
        return ToolInvocationResult(
            authorized=allowed,
            executed=False,
            result=None,
            error=None if allowed else policies.override.deny_message,
            policy_rule=f"rule_for:{user_role}",
        )

    async def invoke_tool(
        self,
        tool_id: str,
        user_role: str,
        params: dict,
        config: ProviderConfig,
    ) -> ToolInvocationResult | None:
        if self._governance is None:
            return None
        auth = await self.authorize_tool(tool_id, user_role, config)
        if auth is None:
            return None
        if auth.authorized:
            self._governance.audit_log.records.append(
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "actor": user_role,
                    "tool_id": tool_id,
                    "action": "invoke",
                    "decision": "allow",
                    "params": params,
                }
            )
            return ToolInvocationResult(
                authorized=True,
                executed=True,
                result=f"{tool_id}_ok",
                error=None,
                policy_rule=auth.policy_rule,
            )
        self._governance.audit_log.records.append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "actor": user_role,
                "tool_id": tool_id,
                "action": "invoke",
                "decision": "deny",
                "params": params,
            }
        )
        return auth

    async def get_audit_trail(
        self,
        request_id: str,
        config: ProviderConfig,
    ) -> list[AuditRecord] | None:
        if self._governance is None:
            return None
        return [
            AuditRecord(
                timestamp=rec.get("timestamp", ""),
                actor=rec.get("actor", ""),
                action=rec.get("action", ""),
                decision=rec.get("decision", ""),
                rule_applied=rec.get("policy_rule"),
                reasoning=rec.get("reason", ""),
            )
            for rec in self._governance.audit_log.records
        ]

    async def get_governance_architecture(
        self,
        config: ProviderConfig,
    ) -> dict | None:
        policies = self._policies(config)
        if policies is None:
            return None
        return policies.governance_architecture.model_dump()

    async def get_roles(
        self,
        config: ProviderConfig,
    ) -> list[Role] | None:
        policies = self._policies(config)
        if policies is None:
            return None
        return [Role(name=rule.role) for rule in policies.authorization]

    async def get_permission_matrix(
        self,
        config: ProviderConfig,
    ) -> list[Permission] | None:
        policies = self._policies(config)
        if policies is None:
            return None
        return [
            Permission(role=rule.role, tools=list(rule.tools))
            for rule in policies.authorization
        ]

    async def get_training_policy(
        self,
        config: ProviderConfig,
    ) -> dict[str, Any] | None:
        policies = self._policies(config)
        if policies is None:
            return None
        return policies.training_policy.model_dump()

    async def get_rate_limit_policy(
        self,
        config: ProviderConfig,
    ) -> dict[str, Any] | None:
        policies = self._policies(config)
        if policies is None:
            return None
        return {
            role: rule.model_dump()
            for role, rule in policies.rate_limits.items()
        }

    async def get_session_state(
        self,
        session_id: str,
        config: ProviderConfig,
    ) -> dict[str, Any] | None:
        policies = self._policies(config)
        if policies is None:
            return None
        return {
            "session_id": session_id,
            **policies.session.model_dump(),
        }

    async def get_risk_assessment(
        self,
        request: dict[str, Any],
        config: ProviderConfig,
    ) -> dict[str, Any] | None:
        policies = self._policies(config)
        if policies is None:
            return None
        risk_policy = policies.risk_assessment
        for rule in risk_policy.rules:
            if all(request.get(k) == v for k, v in rule.match.items()):
                return {
                    "risk_score": rule.score,
                    "band": rule.band,
                    "rationale": f"matched_rule:{rule.match}",
                }
        return {
            "risk_score": risk_policy.default.score,
            "band": risk_policy.default.band,
            "rationale": "default_rule",
        }
