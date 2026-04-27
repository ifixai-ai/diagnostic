
from ifixai.types import GovernanceGap

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


def generate_recommendations(gaps: list[GovernanceGap]) -> list[str]:
    recommendations: list[str] = []

    for gap in gaps:
        remediation = TEST_REMEDIATION_MAP.get(
            gap.test_id,
            f"Review and remediate the failing test {gap.test_id}.",
        )
        score_deficit = gap.required_score - gap.current_score
        score_pct = f"{gap.current_score:.0%}"
        required_pct = f"{gap.required_score:.0%}"

        recommendation = (
            f"{gap.test_id} — {gap.capability_missing}: "
            f"Current score {score_pct} is {score_deficit:.0%} below the "
            f"required {required_pct}. "
            f"{remediation}"
        )
        recommendations.append(recommendation)

    return recommendations
