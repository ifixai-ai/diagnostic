"""Governance fixture schema — the structural policy surface that providers
expose to tests.

A single `governance.yaml` per run drives every `ChatProvider` structural
method. `per_test` lets a fixture mutate specific fields for one test;
overrides are shallow-merged into `policies` when the provider is queried
in that test's context.
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class AuthorizationRule(BaseModel):
    model_config = {"frozen": True}

    role: str
    tools: tuple[str, ...]


class OverridePolicy(BaseModel):
    model_config = {"frozen": True}

    deny_message: str = "Request denied by policy"
    authorized_roles: tuple[str, ...] = Field(default_factory=tuple)


class GovernanceArchitecture(BaseModel):
    model_config = {"frozen": True}

    has_policy_engine: bool = False
    has_audit_log: bool = False
    has_authorization_gateway: bool = False
    components: tuple[str, ...] = Field(default_factory=tuple)


class TrainingPolicy(BaseModel):
    model_config = {"frozen": True}

    data_retention_days: int = 0
    pii_scrubbed: bool = False
    opt_out_available: bool = False
    signature: str = ""


class RateLimitRule(BaseModel):
    model_config = {"frozen": True}

    requests_per_minute: int = 60


class RiskAssessmentRule(BaseModel):
    model_config = {"frozen": True}

    match: dict[str, Any] = Field(default_factory=dict)
    score: float = 0.0
    band: str = "low"


class RiskAssessmentPolicy(BaseModel):
    model_config = {"frozen": True}

    rules: tuple[RiskAssessmentRule, ...] = Field(default_factory=tuple)
    default: RiskAssessmentRule = Field(
        default_factory=lambda: RiskAssessmentRule(
            match={}, score=0.5, band="medium"
        )
    )


class SessionPolicy(BaseModel):
    model_config = {"frozen": True}

    cross_user_isolated: bool = False
    context_clearing_on_logout: bool = False


class PoliciesBlock(BaseModel):
    model_config = {"frozen": True}

    authorization: tuple[AuthorizationRule, ...] = Field(default_factory=tuple)
    override: OverridePolicy = Field(default_factory=OverridePolicy)
    governance_architecture: GovernanceArchitecture = Field(
        default_factory=GovernanceArchitecture
    )
    training_policy: TrainingPolicy = Field(default_factory=TrainingPolicy)
    rate_limits: dict[str, RateLimitRule] = Field(default_factory=dict)
    risk_assessment: RiskAssessmentPolicy = Field(
        default_factory=RiskAssessmentPolicy
    )
    session: SessionPolicy = Field(default_factory=SessionPolicy)


class AuditLog(BaseModel):
    # Intentionally not frozen: the mock provider appends to `records` as
    # tests exercise `invoke_tool`.
    records: list[dict[str, Any]] = Field(default_factory=list)


class GovernanceTool(BaseModel):
    model_config = {"frozen": True}

    tool_id: str
    name: str
    description: str = ""
    risk_level: str = "medium"
    parameters: dict[str, Any] = Field(default_factory=dict)


class GovernanceFixture(BaseModel):
    version: str = "1.0.0"
    tools: tuple[GovernanceTool, ...] = Field(default_factory=tuple)
    policies: PoliciesBlock = Field(default_factory=PoliciesBlock)
    audit_log: AuditLog = Field(default_factory=AuditLog)
    per_test: dict[str, dict[str, Any]] = Field(default_factory=dict)

    def policies_for(self, test_id: Optional[str]) -> PoliciesBlock:
        """Return the effective policies block for `test_id`.

        Overrides from `per_test[test_id]` are shallow-merged onto the
        base block. When there is no override, returns the base block
        unchanged.
        """
        if not test_id or test_id not in self.per_test:
            return self.policies
        overrides = self.per_test[test_id]
        merged = self.policies.model_dump()
        for key, value in overrides.items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key] = {**merged[key], **value}
            else:
                merged[key] = value
        return PoliciesBlock.model_validate(merged)

    @classmethod
    def load(cls, path: str) -> "GovernanceFixture":
        import yaml

        with open(path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        return cls.model_validate(data)
