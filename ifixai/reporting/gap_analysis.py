
from ifixai.mappings.loader import get_mappings_for_test, load_all_mappings
from ifixai.core.types import TestResult, GovernanceGap, RegulatoryFramework

TEST_CAPABILITY_MAP: dict[str, str] = {
    "B01": "Tool Authorization Control",
    "B02": "Non-LLM Governance Layer",
    "B03": "Audit Trail Coverage",
    "B04": "Deterministic Override Mechanism",
    "B05": "Source Provenance Tracking",
    "B06": "Uncertainty Signalling",
    "B07": "Hallucination Prevention",
    "B08": "Privilege Escalation Prevention",
    "B09": "Policy Violation Detection",
    "B10": "Evaluation Consistency",
    "B11": "System Controllability",
    "B12": "Prompt Injection Defence",
    "B13": "Plan Propagation Traceability",
    "B14": "Covert Side-Task Detection",
    "B15": "Long-Horizon Policy Adherence",
    "B16": "Silent Failure Reporting",
    "B17": "Cross-System Fact Consistency",
    "B18": "Goal Stability Maintenance",
    "B19": "Context Accuracy Retention",
    "B20": "Instruction Adherence Enforcement",
    "B21": "Cross-Turn Objective Persistence",
    "B22": "Decision Reproducibility",
    "B23": "Policy Version Traceability",
    "B24": "Risk Scoring Capability",
    "B25": "Regulatory Compliance Readiness",
    "B26": "Rate Limiting Enforcement",
    "B27": "Cross-Session Memory Integrity",
    "B28": "Training Data Contamination Barrier",
    "B29": "Prompt Sensitivity Consistency",
}

TEST_REMEDIATION_MAP: dict[str, str] = {
    "B01": (
        "Implement a deterministic authorization layer that validates "
        "every tool invocation against role-based permissions before execution."
    ),
    "B02": (
        "Introduce a dedicated non-LLM governance component that enforces "
        "policy decisions independently of the language model."
    ),
    "B03": (
        "Ensure every governance decision produces a timestamped audit "
        "record with the rule applied and supporting evidence."
    ),
    "B04": (
        "Add deterministic override controls that bypass LLM judgment "
        "for critical governance decisions and include override tokens."
    ),
    "B05": (
        "Attach verifiable source citations to all responses so claims "
        "can be traced back to their origin documents."
    ),
    "B06": (
        "Add explicit uncertainty signals to low-confidence responses "
        "so consumers can distinguish confident from tentative answers."
    ),
    "B07": (
        "Implement output validation that cross-checks generated content "
        "against provided sources to detect and suppress hallucinations."
    ),
    "B08": (
        "Add privilege boundary enforcement that blocks any attempt to "
        "authorize tools beyond a user's assigned role permissions."
    ),
    "B09": (
        "Implement policy violation detection that evaluates requests "
        "against organizational governance rules before processing."
    ),
    "B10": (
        "Ensure governance decisions are deterministic by removing "
        "non-deterministic factors from the decision pipeline."
    ),
    "B11": (
        "Provide runtime governance configuration controls that allow "
        "operators to adjust policy enforcement without redeployment."
    ),
    "B12": (
        "Implement prompt injection detection that identifies and blocks "
        "attempts to override governance instructions via crafted inputs."
    ),
    "B13": (
        "Maintain a traceable audit trail for multi-step request processing "
        "with entries for each intermediate step."
    ),
    "B14": (
        "Add covert task detection that identifies and rejects hidden "
        "objectives embedded within otherwise legitimate requests."
    ),
    "B15": (
        "Ensure governance policy adherence remains stable across "
        "extended multi-turn interaction sequences."
    ),
    "B16": (
        "Replace silent failure modes with explicit error reporting "
        "so every failure produces an observable signal."
    ),
    "B17": (
        "Ensure identical factual queries produce consistent answers "
        "across repeated invocations."
    ),
    "B18": (
        "Implement goal tracking that detects and prevents drift from "
        "stated objectives to undeclared goals across turns."
    ),
    "B19": (
        "Ensure context facts provided earlier in an interaction are "
        "accurately retained and recalled in subsequent responses."
    ),
    "B20": (
        "Implement instruction adherence validation that verifies "
        "responses follow explicit instructions without deviation."
    ),
    "B21": (
        "Add cross-turn objective verification to ensure stated goals "
        "persist across multi-turn interactions without being dropped."
    ),
    "B22": (
        "Ensure identical inputs always produce identical governance "
        "decisions through fully deterministic processing."
    ),
    "B23": (
        "Include policy version references in all audit trail entries "
        "so decisions can be traced to the exact rules applied."
    ),
    "B24": (
        "Implement risk scoring that assigns appropriate risk levels "
        "to requests based on content and context analysis."
    ),
    "B25": (
        "Align system architecture and audit capabilities with "
        "applicable regulatory compliance frameworks."
    ),
    "B26": (
        "Implement rate limiting controls that prevent resource "
        "exhaustion and enforce usage boundaries."
    ),
    "B27": (
        "Enforce strict user session isolation to prevent cross-user "
        "context leakage between concurrent sessions."
    ),
    "B28": (
        "Implement data protection barriers and documentation that "
        "prevent training data contamination of governance decisions."
    ),
    "B29": (
        "Ensure semantically equivalent requests phrased differently "
        "produce consistent governance outcomes."
    ),
}

def identify_gaps(
    results: list[TestResult],
    frameworks: dict[str, RegulatoryFramework] | None = None,
) -> list[GovernanceGap]:
    if frameworks is None:
        frameworks = load_all_mappings()

    gaps: list[GovernanceGap] = []

    for result in sorted(results, key=lambda r: r.test_id):
        if result.passing:
            continue

        capability = TEST_CAPABILITY_MAP.get(
            result.test_id,
            f"Unknown Capability ({result.test_id})",
        )
        base_remediation = TEST_REMEDIATION_MAP.get(
            result.test_id,
            f"Review and remediate the failing test {result.test_id}.",
        )

        reg_refs = get_mappings_for_test(result.test_id, frameworks)
        remediation = _enrich_remediation(base_remediation, reg_refs)

        deficit = result.threshold - result.score
        priority = "high" if deficit > 0.5 else ("medium" if deficit > 0.2 else "low")

        gaps.append(
            GovernanceGap(
                test_id=result.test_id,
                test_name=result.name,
                category=result.category,
                current_score=result.score,
                required_score=result.threshold,
                gap_description=f"{capability} — scored {result.score:.0%} against {result.threshold:.0%} threshold",
                capability_missing=capability,
                remediation=remediation,
                priority=priority,
                regulatory_references=reg_refs,
            )
        )

    return gaps

def _enrich_remediation(
    base_text: str,
    mappings: list,
) -> str:
    if not mappings:
        return base_text

    seen: set[str] = set()
    refs: list[str] = []
    for m in mappings:
        key = f"{m.framework} {m.control_id}"
        if key not in seen:
            seen.add(key)
            refs.append(f"{m.framework} {m.control_id} ({m.control_name})")

    ref_text = "; ".join(refs)
    return f"{base_text} [Regulatory: {ref_text}]"
