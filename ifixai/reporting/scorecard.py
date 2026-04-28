
import json
from typing import Final

from ifixai.judge.config import JudgeConfig
from ifixai.mappings.loader import load_all_mappings
from ifixai.reporting.grading import GRADE_INTERPRETATIONS
from ifixai.reporting.regulatory import (
    build_framework_section,
    build_regulatory_json_section,
    build_regulatory_summary,
    get_test_regulatory_mappings,
)
from ifixai.core.types import TestResult, RegulatoryFramework, TestRunResult

SELF_JUDGE_BIAS_ADVISORY: Final[str] = (
    "self-judge bias: Standard-mode score not comparable to Full-mode "
    "(same provider judges its own output)"
)

INSUFFICIENT_EVIDENCE_PREFIX: Final[str] = "insufficient evidence: "
EXTRACTION_ERROR_PREFIX: Final[str] = "judge extraction failure: "
EXPLORATORY_INSPECTION_PREFIX: Final[str] = "exploratory inspection (excluded from aggregation): "
ADVISORY_INSPECTION_PREFIX: Final[str] = (
    "advisory inspection (self-report, excluded from aggregation): "
)
ATTESTATION_INSPECTION_PREFIX: Final[str] = (
    "attestation inspection (deployer-attested, not scored): "
)
B22_SKIPPED_MESSAGE: Final[str] = (
    "b22 skipped: SUT non-deterministic (pass --sut-temperature 0 or --sut-seed)"
)
SEED_UNSUPPORTED_PREFIX: Final[str] = (
    "b12 seed accepted but provider cannot honour: "
)


def insufficient_evidence_warnings(
    test_results: list[TestResult],
) -> list[str]:
    messages: list[str] = []
    for br in test_results:
        if not br.insufficient_evidence:
            continue
        floor = br.spec.min_evidence_items if br.spec else 10
        messages.append(
            INSUFFICIENT_EVIDENCE_PREFIX
            + f"{br.test_id} (got {len(br.evidence)}, min {floor})"
        )
    return messages


def exploratory_inspection_warnings(
    test_results: list[TestResult],
) -> list[str]:
    messages: list[str] = []
    for br in test_results:
        if not br.spec or not getattr(br.spec, "is_exploratory", False):
            continue
        messages.append(EXPLORATORY_INSPECTION_PREFIX + br.test_id)
    return messages


def advisory_inspection_warnings(
    test_results: list[TestResult],
) -> list[str]:
    messages: list[str] = []
    for br in test_results:
        if not br.spec or not getattr(br.spec, "is_advisory", False):
            continue
        if not br.evidence:
            continue
        messages.append(ADVISORY_INSPECTION_PREFIX + br.test_id)
    return messages


def attestation_inspection_warnings(
    test_results: list[TestResult],
) -> list[str]:
    messages: list[str] = []
    for br in test_results:
        if not br.spec or not getattr(br.spec, "is_attestation", False):
            continue
        messages.append(ATTESTATION_INSPECTION_PREFIX + br.test_id)
    return messages


def extraction_error_warnings(
    test_results: list[TestResult],
) -> list[str]:
    messages: list[str] = []
    for br in test_results:
        affected = sum(
            1 for ev in br.evidence if ev.extraction_error is not None
        )
        if affected == 0:
            continue
        messages.append(
            EXTRACTION_ERROR_PREFIX
            + f"{br.test_id} ({affected} evidence items affected)"
        )
    return messages


def b22_determinism_warning(
    test_results: list[TestResult],
    sut_temperature: float,
    sut_seed: int | None,
) -> str | None:
    if sut_temperature == 0.0 or sut_seed is not None:
        return None
    b22 = next(
        (br for br in test_results if br.test_id == "B22"),
        None,
    )
    if b22 is None or not b22.insufficient_evidence:
        return None
    return B22_SKIPPED_MESSAGE


def self_judge_bias_applies(
    judge_config: JudgeConfig | None,
    model_provider: str,
) -> bool:
    if judge_config is None:
        return True
    if not judge_config.providers:
        return True
    distinct = {p.provider for p in judge_config.providers}
    return not (len(distinct) >= 2 and model_provider not in distinct)


def scorecard_warnings(
    judge_config: JudgeConfig | None,
    model_provider: str,
    extra: list[str] | None = None,
) -> list[str]:
    warnings: list[str] = list(extra) if extra else []
    if self_judge_bias_applies(judge_config, model_provider):
        if SELF_JUDGE_BIAS_ADVISORY not in warnings:
            warnings.append(SELF_JUDGE_BIAS_ADVISORY)
    return warnings


def generate_json_report(result: TestRunResult) -> str:
    frameworks = load_all_mappings()

    report = {
        "metadata": build_metadata_section(result, frameworks),
        "overall": build_overall_section(result),
        "warnings": list(result.warnings),
        "category_scores": build_category_scores_section(result),
        "mandatory_minimums": build_mandatory_minimums_section(result),
        "test_results": build_test_results_section(result, frameworks),
        "gaps": build_gaps_section(result),
        "recommendations": result.recommendations,
        "regulatory": build_regulatory_json_section(result, frameworks),
    }

    return json.dumps(report, indent=2, ensure_ascii=False)

def generate_markdown_report(result: TestRunResult) -> str:
    frameworks = load_all_mappings()

    sections = [
        render_header(result),
        render_summary(result),
        render_category_table(result),
        render_mandatory_minimums(result),
        render_test_table(result),
        render_advisory_section(result),
        render_exploratory_section(result),
        render_attestation_section(result),
        render_gap_analysis(result),
        render_regulatory_compliance(result, frameworks),
        render_recommendations(result),
        render_evidence_appendix(result),
        render_footer(result),
    ]

    return "\n\n".join(s for s in sections if s) + "\n"

def build_metadata_section(
    result: TestRunResult,
    frameworks: dict[str, RegulatoryFramework] | None = None,
) -> dict[str, object]:
    meta: dict[str, object] = {
        "system_name": result.system_name,
        "system_version": result.system_version,
        "provider": result.provider,
        "fixture_name": result.fixture_name,
        "evaluation_date": result.evaluation_date.isoformat(),
        "specification_version": result.specification_version,
        "run_mode": result.run_mode,
    }
    if result.judge_stats is not None:
        meta["judge_stats"] = result.judge_stats
    if frameworks:
        meta["regulatory_frameworks"] = [
            {"name": fw.framework, "version": fw.version}
            for fw in frameworks.values()
        ]
    return meta

def build_overall_section(result: TestRunResult) -> dict[str, object]:
    overall = result.overall_score
    section: dict[str, object] = {
        "score": None if overall is None else round(overall, 4),
        "score_pct": "n/a" if overall is None else f"{overall:.1%}",
        "grade": result.grade.value,
        "grade_interpretation": GRADE_INTERPRETATIONS[result.grade],
        "strategic_score": round(result.strategic_score, 4),
        "strategic_score_pct": f"{result.strategic_score:.1%}",
        "passed": result.passed,
        "mandatory_minimums_passed": result.mandatory_minimums_passed,
    }
    if result.overall_score_before_cap is not None:
        section["score_before_cap"] = round(result.overall_score_before_cap, 4)
        cap_bound = (
            result.overall_score is not None
            and result.overall_score_before_cap > result.overall_score
        )
        section["cap_applied"] = cap_bound
    return section

def build_category_scores_section(
    result: TestRunResult,
) -> list[dict[str, object]]:
    return [
        {
            "category": cs.category.value,
            "score": None if cs.score is None else round(cs.score, 4),
            "score_pct": "n/a" if cs.score is None else f"{cs.score:.1%}",
            "weight": cs.weight,
            "test_count": len(cs.test_ids),
            "test_ids": cs.test_ids,
        }
        for cs in result.category_scores
    ]

def build_mandatory_minimums_section(
    result: TestRunResult,
) -> dict[str, object]:
    return {
        "all_passed": result.mandatory_minimums_passed,
        "per_test": result.mandatory_minimum_status,
    }

def build_test_results_section(
    result: TestRunResult,
    frameworks: dict[str, RegulatoryFramework] | None = None,
) -> list[dict[str, object]]:
    items = []
    for br in result.test_results:
        evidence_list = []
        for ev in br.evidence:
            ev_dict: dict[str, object] = {
                "test_case_id": ev.test_case_id,
                "description": ev.description,
                "prompt_sent": ev.prompt_sent,
                "expected": ev.expected or ev.expected_behavior,
                "actual": ev.actual_response or ev.actual,
                "evaluation_result": ev.evaluation_result,
                "passed": ev.passed,
                "inspection_method": ev.inspection_method.value,
                "evaluation_method": ev.evaluation_method.value,
            }
            if ev.dimension_scores:
                ev_dict["dimension_scores"] = [
                    {
                        "dimension_name": ds.dimension_name,
                        "passed": ds.passed,
                        "reasoning": ds.reasoning,
                        "confidence": ds.confidence,
                        "is_mandatory": ds.is_mandatory,
                    }
                    for ds in ev.dimension_scores
                ]
            if ev.rubric_verdict:
                ev_dict["rubric_verdict"] = {
                    "weighted_score": ev.rubric_verdict.weighted_score,
                    "mandatory_veto": ev.rubric_verdict.mandatory_veto,
                    "passed": ev.rubric_verdict.passed,
                    "verdict": ev.rubric_verdict.verdict,
                }
            evidence_list.append(ev_dict)

        br_dict: dict[str, object] = {
            "test_id": br.test_id,
            "name": br.name,
            "category": br.category.value,
            "score": round(br.score, 4),
            "score_pct": f"{br.score:.1%}",
            "threshold": br.threshold,
            "passing": br.passing,
            "evidence_count": len(br.evidence),
            "evidence": evidence_list,
            "duration_ms": round(br.duration_ms, 1),
            "error": br.error,
            "regulatory_mappings": get_test_regulatory_mappings(
                br.test_id, frameworks
            ),
        }
        if br.confidence_interval:
            br_dict["confidence_interval"] = {
                "lower": br.confidence_interval.lower,
                "upper": br.confidence_interval.upper,
                "method": br.confidence_interval.method,
                "sample_size": br.confidence_interval.sample_size,
                "warning": br.confidence_interval.warning,
            }
        if br.evaluation_mode:
            br_dict["evaluation_mode"] = br.evaluation_mode.value
        if br.judge_calls_used:
            br_dict["judge_calls_used"] = br.judge_calls_used
        items.append(br_dict)
    return items

def build_gaps_section(result: TestRunResult) -> list[dict[str, object]]:
    return [
        {
            "test_id": gap.test_id,
            "test_name": gap.test_name,
            "current_score": round(gap.current_score, 4),
            "required_score": gap.required_score,
            "capability_missing": gap.capability_missing,
            "remediation": gap.remediation,
        }
        for gap in result.gaps
    ]

def render_header(result: TestRunResult) -> str:
    eval_mode = "deterministic"
    for br in result.test_results:
        if br.evaluation_mode:
            eval_mode = br.evaluation_mode.value
            break

    header = (
        f"# ifixai Scorecard — {result.system_name} v{result.system_version}\n\n"
        f"**Specification Version:** {result.specification_version}  \n"
        f"**Provider:** {result.provider}  \n"
        f"**Fixture:** {result.fixture_name}  \n"
        f"**Evaluation Date:** {result.evaluation_date.strftime('%Y-%m-%d %H:%M UTC')}  \n"
        f"**Run Mode:** {result.run_mode}  \n"
        f"**Evaluation Mode:** {eval_mode}"
    )
    return header

def render_summary(result: TestRunResult) -> str:
    grade_text = GRADE_INTERPRETATIONS[result.grade]
    minimums_status = "PASS" if result.mandatory_minimums_passed else "FAIL"
    verdict = "PASS" if result.passed else "FAIL"
    overall_display = (
        "n/a (insufficient evidence)" if result.overall_score is None
        else f"{result.overall_score:.1%}"
    )

    return (
        f"## Overall Score\n\n"
        f"| Metric | Value |\n"
        f"|---|---|\n"
        f"| **Overall Score** | {overall_display} |\n"
        f"| **Grade** | {result.grade.value} |\n"
        f"| **Verdict** | {verdict} |\n"
        f"| **Strategic Score** | {result.strategic_score:.1%} |\n"
        f"| **Mandatory Minimums** | {minimums_status} |\n\n"
        f"> {grade_text}"
    )

def render_category_table(result: TestRunResult) -> str:
    lines = [
        "## Category Scores\n",
        "| Category | Score | Tests |",
        "|---|---|---|",
    ]

    for cs in result.category_scores:
        test_count = len(cs.test_ids)
        score_display = "n/a" if cs.score is None else f"{cs.score:.1%}"
        lines.append(
            f"| {cs.category.value} | {score_display} | {test_count} |"
        )

    return "\n".join(lines)

def render_mandatory_minimums(result: TestRunResult) -> str:
    if not result.mandatory_minimum_status:
        return "## Mandatory Minimums\n\nNo mandatory minimums defined."

    lines = [
        "## Mandatory Minimums\n",
        "| Test | Status |",
        "|---|---|",
    ]

    for test_id, passed in sorted(result.mandatory_minimum_status.items()):
        status = "PASS" if passed else "**FAIL**"
        lines.append(f"| {test_id} | {status} |")

    return "\n".join(lines)

def _is_advisory_result(br: TestResult) -> bool:
    return bool(br.spec and getattr(br.spec, "is_advisory", False))


def _is_exploratory_result(br: TestResult) -> bool:
    return bool(br.spec and getattr(br.spec, "is_exploratory", False))


def _is_attestation_result(br: TestResult) -> bool:
    return bool(br.spec and getattr(br.spec, "is_attestation", False))


def _format_method_mix(br: TestResult) -> str:
    if not br.evidence:
        return "—"
    counts: dict[str, int] = {}
    for ev in br.evidence:
        method = ev.evaluation_method.value
        counts[method] = counts.get(method, 0) + 1
    parts = [f"{n}× {m}" for m, n in sorted(counts.items())]
    return ", ".join(parts)


def render_test_table(result: TestRunResult) -> str:
    scored = [
        br for br in result.test_results
        if not _is_advisory_result(br)
        and not _is_exploratory_result(br)
        and not _is_attestation_result(br)
    ]

    lines = [
        "## Test Results\n",
        "| ID | Name | Score | Threshold | Method | Status |",
        "|---|---|---|---|---|---|",
    ]

    for br in scored:
        status = "PASS" if br.passing else "**FAIL**"
        if br.error:
            status = "**ERROR**"
        score_display = f"{br.score:.1%}"
        if br.confidence_interval:
            score_display += f" [{br.confidence_interval.lower:.2f}, {br.confidence_interval.upper:.2f}]"
        method_mix = _format_method_mix(br)
        lines.append(
            f"| {br.test_id} | {br.name} | {score_display} "
            f"| {br.threshold:.0%} | {method_mix} | {status} |"
        )

    has_dimensions = any(
        ev.rubric_verdict is not None
        for br in result.test_results
        for ev in br.evidence
    )
    if has_dimensions:
        lines.append("")
        lines.append("### Dimension Breakdown\n")
        for br in result.test_results:
            for ev in br.evidence:
                if ev.rubric_verdict and ev.dimension_scores:
                    lines.append(f"**{br.test_id}** — {ev.description}\n")
                    for ds in ev.dimension_scores:
                        status_icon = "PASS" if ds.passed else "**FAIL**"
                        mandatory_tag = " (mandatory)" if ds.is_mandatory else ""
                        lines.append(
                            f"- [{status_icon}] {ds.dimension_name}{mandatory_tag}: {ds.reasoning}"
                        )
                    rv = ev.rubric_verdict
                    veto_note = " | Mandatory veto: YES" if rv.mandatory_veto else ""
                    lines.append(
                        f"- Weighted score: {rv.weighted_score:.2f} | Verdict: {rv.verdict}{veto_note}\n"
                    )

    total_judge_calls = sum(br.judge_calls_used for br in result.test_results)
    if total_judge_calls > 0:
        lines.append("")
        lines.append(f"**Judge calls used**: {total_judge_calls}")

    return "\n".join(lines)


def render_advisory_section(result: TestRunResult) -> str:
    advisory = [
        br for br in result.test_results
        if _is_advisory_result(br) and br.evidence
    ]
    if not advisory:
        return ""

    lines = [
        "## Advisory Indicators (self-report)\n",
        (
            "These inspections fall back to model self-report when the system under "
            "test does not expose the required structural hook. Scores are "
            "informational only and are **excluded from category and overall "
            "aggregation**."
        ),
        "",
        "| ID | Name | Raw Score | Evidence | Method |",
        "|---|---|---|---|---|",
    ]
    for br in sorted(advisory, key=lambda b: b.test_id):
        method_mix = _format_method_mix(br)
        lines.append(
            f"| {br.test_id} | {br.name} | {br.score:.1%} "
            f"| {len(br.evidence)} | {method_mix} |"
        )
    return "\n".join(lines)


def render_exploratory_section(result: TestRunResult) -> str:
    exploratory = [
        br for br in result.test_results
        if _is_exploratory_result(br) and br.evidence
    ]
    if not exploratory:
        return ""

    lines = [
        "## Exploratory Inspections (not scored)\n",
        (
            "These inspections produce signal at small N and are labelled "
            "exploratory until evidence counts reach a threshold for "
            "statistical inference. Scores are **excluded from aggregation** "
            "and shown here for informational purposes only."
        ),
        "",
        "| ID | Name | Raw Score | Evidence Count |",
        "|---|---|---|---|",
    ]
    for br in sorted(exploratory, key=lambda b: b.test_id):
        lines.append(
            f"| {br.test_id} | {br.name} | {br.score:.1%} "
            f"| {len(br.evidence)} |"
        )
    return "\n".join(lines)


def render_attestation_section(result: TestRunResult) -> str:
    attestation = [
        br for br in result.test_results
        if _is_attestation_result(br)
    ]
    if not attestation:
        return ""

    lines = [
        "## Deployer Attestations (not scored)\n",
        (
            "These inspections cannot be measured from a black-box interface. "
            "The deployer attests to the governance control in the fixture; "
            "the attestation text is recorded here for audit and is "
            "**not scored**. An empty attestation is recorded as "
            "`not attested`."
        ),
        "",
        "| ID | Name | Attestation |",
        "|---|---|---|",
    ]
    for br in sorted(attestation, key=lambda b: b.test_id):
        recorded = "not attested"
        if br.evidence:
            first = br.evidence[0]
            recorded = first.actual or "not attested"
        lines.append(
            f"| {br.test_id} | {br.name} | {recorded} |"
        )
    return "\n".join(lines)


def render_gap_analysis(result: TestRunResult) -> str:
    if not result.gaps:
        return (
            "## Gap Analysis\n\n"
            "No governance gaps identified. All tests meet "
            "their required thresholds."
        )

    lines = [
        "## Gap Analysis\n",
        f"{len(result.gaps)} governance gap(s) identified:\n",
    ]

    for gap in result.gaps:
        deficit = gap.required_score - gap.current_score
        lines.append(
            f"### {gap.test_id} — {gap.capability_missing}\n"
        )
        lines.append(
            f"- **Current Score:** {gap.current_score:.1%}\n"
            f"- **Required Score:** {gap.required_score:.0%}\n"
            f"- **Deficit:** {deficit:.1%}\n"
            f"- **Remediation:** {gap.remediation}"
        )

    return "\n".join(lines)

def render_recommendations(result: TestRunResult) -> str:
    if not result.recommendations:
        return "## Recommendations\n\nNo recommendations — all tests passed."

    lines = ["## Recommendations\n"]

    for idx, recommendation in enumerate(result.recommendations, start=1):
        lines.append(f"{idx}. {recommendation}")

    return "\n".join(lines)

def render_regulatory_compliance(
    result: TestRunResult,
    frameworks: dict[str, RegulatoryFramework] | None = None,
) -> str:
    if frameworks is None:
        frameworks = load_all_mappings()

    summary = build_regulatory_summary(result, frameworks)
    if not summary:
        return "## Regulatory Compliance\n\nNo regulatory framework mappings available."

    lines = [
        "## Regulatory Compliance Summary\n",
        "| Framework | Version | Tests Mapped | Passing | Coverage |",
        "|---|---|---|---|---|",
    ]

    for item in summary:
        lines.append(
            f"| {item['name']} | {item['version']} "
            f"| {item['tests_mapped']} | {item['tests_passing']} "
            f"| {item['coverage_pct']} |"
        )

    if result.gaps:
        for fw_name in frameworks:
            section = build_framework_section(result, fw_name, frameworks)
            lines.append("")
            lines.append(section)

    return "\n".join(lines)

def render_evidence_appendix(result: TestRunResult) -> str:
    lines = ["## Evidence Appendix\n"]
    has_evidence = False

    for br in result.test_results:
        if not br.evidence:
            continue
        has_evidence = True
        status = "PASS" if br.passing else "FAIL"
        lines.append(f"### {br.test_id} — {br.name} ({status})\n")

        for ev in br.evidence:
            prompt_display = ev.prompt_sent[:200] + "..." if len(ev.prompt_sent) > 200 else ev.prompt_sent
            actual_display = ev.actual_response or ev.actual
            if len(actual_display) > 200:
                actual_display = actual_display[:200] + "..."
            ev_status = "PASS" if ev.passed else "FAIL"

            lines.append(
                f"- **{ev.test_case_id}** [{ev_status}]: "
                f"{ev.description}\n"
                f"  - Prompt: `{prompt_display}`\n"
                f"  - Expected: {ev.expected or ev.expected_behavior}\n"
                f"  - Actual: `{actual_display}`\n"
                f"  - Evaluation: {ev.evaluation_result}"
            )

        lines.append("")

    if not has_evidence:
        lines.append("No evidence items recorded.")

    return "\n".join(lines)

def render_footer(result: TestRunResult) -> str:
    return "\n".join([
        "---",
        f"*Report generated for ifixai v{result.specification_version}.*",
    ])
