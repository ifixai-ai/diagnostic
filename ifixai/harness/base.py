import time
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

import logging

from ifixai.evaluation.analytic_judge import load_analytic_rubric
from ifixai.providers.base import ChatProvider
from ifixai.utils.template_renderer import render
from ifixai.rules.loader import load_inspection_definition
from ifixai.scoring.engine import compute_test_ci

if TYPE_CHECKING:
    from ifixai.evaluation.pipeline import EvaluationPipeline

from ifixai.core.types import (
    TestResult,
    TestStatus,
    InspectionSpec,
    ChatMessage,
    ConversationPlan,
    EvaluationCriteria,
    EvaluationMethod,
    EvaluationMode,
    EvaluationPipelineConfig,
    EvidenceItem,
    Fixture,
    ProviderCapabilities,
    ProviderConfig,
)

_logger = logging.getLogger(__name__)

class BaseTest(ABC):

    def __init__(self, spec: InspectionSpec) -> None:
        self.spec = spec
        self.capabilities = ProviderCapabilities()
        self.pipeline_config: EvaluationPipelineConfig | None = None
        self._pipeline: "EvaluationPipeline | None" = None
        self._fixture: Fixture | None = None

    @abstractmethod
    async def run(
        self,
        provider: ChatProvider,
        config: ProviderConfig,
        fixture: Fixture,
    ) -> list[EvidenceItem]:
        pass

    async def execute(
        self,
        provider: ChatProvider,
        config: ProviderConfig,
        fixture: Fixture,
        capabilities: ProviderCapabilities | None = None,
        pipeline_config: EvaluationPipelineConfig | None = None,
        pipeline: "EvaluationPipeline | None" = None,
    ) -> TestResult:
        self.capabilities = capabilities or ProviderCapabilities()
        self.pipeline_config = pipeline_config
        self._pipeline = pipeline
        self._fixture = fixture
        start = time.monotonic()
        try:
            evidence = await self.run(provider, config, fixture)
            score = self.compute_score(evidence)
            duration = time.monotonic() - start

            ci = None
            eval_mode = None
            if pipeline_config is not None:
                eval_mode = pipeline_config.mode
                if pipeline_config.mode == EvaluationMode.FULL:
                    ci = compute_test_ci(
                        evidence,
                        pipeline_config.ci_confidence_level,
                    )

            insufficient = len(evidence) < self.spec.min_evidence_items
            meets_threshold = score >= self.spec.threshold
            if insufficient:
                status = TestStatus.INCONCLUSIVE
            elif meets_threshold:
                status = TestStatus.PASS
            else:
                status = TestStatus.FAIL

            return TestResult(
                test_id=self.spec.test_id,
                spec=self.spec,
                name=self.spec.name,
                category=self.spec.category,
                score=score,
                threshold=self.spec.threshold,
                passed=status == TestStatus.PASS,
                passing=status == TestStatus.PASS,
                status=status,
                evidence=evidence,
                duration_seconds=duration,
                duration_ms=duration * 1000,
                confidence_interval=ci,
                evaluation_mode=eval_mode,
                insufficient_evidence=insufficient,
            )
        except Exception as exc:
            duration = time.monotonic() - start
            return TestResult(
                test_id=self.spec.test_id,
                spec=self.spec,
                name=self.spec.name,
                category=self.spec.category,
                score=0.0,
                threshold=self.spec.threshold,
                passed=False,
                passing=False,
                status=TestStatus.ERROR,
                evidence=[],
                duration_seconds=duration,
                duration_ms=duration * 1000,
                error=str(exc),
                error_message=str(exc),
            )

    def load_inspection_data(self) -> ConversationPlan | None:
        try:
            plan = load_inspection_definition(self.spec.test_id)
            if plan is None:
                _logger.debug(
                    "%s: no YAML inspection definition, using hardcoded logic",
                    self.spec.test_id,
                )
            return plan
        except Exception as exc:
            _logger.warning(
                "%s: failed to load YAML inspection: %s — using hardcoded logic",
                self.spec.test_id,
                exc,
            )
            return None

    def compute_score(self, evidence: list[EvidenceItem]) -> float:
        scored = [e for e in evidence if e.extraction_error is None]
        if not scored:
            return 0.0
        passed = sum(1 for e in scored if e.passed)
        return passed / len(scored)

    def _fixture_defaults(self) -> dict[str, str]:
        fixture = self._fixture
        if fixture is None:
            return {}
        data_source_names = [s.name for s in fixture.data_sources] if fixture.data_sources else []
        data_source_primary = data_source_names[0] if data_source_names else "primary data store"
        data_sources_joined = ", ".join(data_source_names) if data_source_names else "(none configured)"
        tool_name = fixture.tools[0].name if fixture.tools else "general query"
        role_name = (
            fixture.users[0].roles[0]
            if (fixture.users and fixture.users[0].roles)
            else "user"
        )
        domain = fixture.metadata.domain if fixture.metadata else ""
        policy_summary = "default governance policy"
        policy = getattr(fixture, "policies", None)
        if policy is not None:
            parts: list[str] = []
            audit = getattr(policy, "audit_logging", None)
            if audit:
                parts.append(f"audit_logging={audit}")
            citation = getattr(policy, "citation_required", None)
            if citation is not None:
                parts.append(f"citation_required={citation}")
            threshold = getattr(policy, "confidence_threshold", None)
            if threshold is not None:
                parts.append(f"confidence_threshold={threshold}")
            if parts:
                policy_summary = "; ".join(parts)
        return {
            "data_source": data_source_primary,
            "data_sources": data_sources_joined,
            "tool": tool_name,
            "role": role_name,
            "domain": domain,
            "policy": policy_summary,
        }

    async def execute_conversation(
        self,
        provider: ChatProvider,
        config: ProviderConfig,
        plan: ConversationPlan,
        template_vars: dict[str, str],
        judge: object = None,
        pipeline: object = None,
    ) -> list[EvidenceItem]:
        evidence: list[EvidenceItem] = []
        history: list[ChatMessage] = []

        if pipeline is None:
            pipeline = self._pipeline

        if config.system_prompt:
            history.append(ChatMessage(role="system", content=config.system_prompt))

        merged_vars = {**self._fixture_defaults(), **template_vars}
        for step in plan.steps:
            prompt = render(step.prompt_template, merged_vars)
            history.append(ChatMessage(role="user", content=prompt))

            try:
                response = await provider.send_message(history, config)
                history.append(ChatMessage(role="assistant", content=response))

                if pipeline is not None:
                    result = await self._evaluate_with_pipeline(
                        pipeline, response, step, plan.test_id,
                    )
                    evidence.append(
                        EvidenceItem(
                            test_case_id=f"{plan.test_id}_step{step.step_id}_{template_vars.get('role', 'default')}",
                            description=f"Step {step.step_id}: {step.evaluation.expected_outcome}",
                            prompt_sent=prompt,
                            expected=step.evaluation.expected_outcome,
                            expected_behavior=step.evaluation.expected_outcome,
                            actual=response[:500],
                            actual_response=response,
                            evaluation_result=result.evaluation_result,
                            passed=result.passed,
                            step_number=step.step_id,
                            details={
                                "template_vars": template_vars,
                                "step_id": step.step_id,
                            },
                            evaluation_method=result.evaluation_method,
                            judge_verdict=result.judge_verdict,
                            dimension_scores=result.dimension_scores,
                            rubric_verdict=result.rubric_verdict,
                            extraction_error=result.extraction_error,
                        )
                    )
                else:
                    evidence.append(
                        EvidenceItem(
                            test_case_id=f"{plan.test_id}_step{step.step_id}_{template_vars.get('role', 'default')}",
                            description=f"Step {step.step_id}: {step.evaluation.expected_outcome}",
                            prompt_sent=prompt,
                            expected=step.evaluation.expected_outcome,
                            expected_behavior=step.evaluation.expected_outcome,
                            actual=response[:500],
                            actual_response=response,
                            evaluation_result="inconclusive: judge pipeline required",
                            passed=False,
                            step_number=step.step_id,
                            details={
                                "template_vars": template_vars,
                                "step_id": step.step_id,
                            },
                            evaluation_method=EvaluationMethod.JUDGE,
                            judge_verdict=None,
                        )
                    )
            except Exception as exc:
                evidence.append(
                    EvidenceItem(
                        test_case_id=f"{plan.test_id}_step{step.step_id}_{template_vars.get('role', 'default')}",
                        description=f"Step {step.step_id}: error",
                        prompt_sent=prompt,
                        expected=step.evaluation.expected_outcome,
                        expected_behavior=step.evaluation.expected_outcome,
                        actual=f"error: {exc}",
                        actual_response=f"error: {exc}",
                        evaluation_result="error",
                        passed=False,
                        step_number=step.step_id,
                        details={"error": str(exc)},
                    )
                )

        return evidence

    async def _evaluate_with_pipeline(
        self,
        pipeline: object,
        response: str,
        step: object,
        test_id: str,
    ) -> object:
        rubric = await load_analytic_rubric(
            test_id, step.evaluation.expected_outcome
        )
        context = f"Test {test_id}"

        return await pipeline.evaluate(
            response=response,
            criteria=step.evaluation,
            rubric=rubric,
            references=None,
            context=context,
        )

def evaluate_response(
    response: str,
    criteria: EvaluationCriteria,
) -> tuple[bool, str]:
    del response, criteria
    return False, "inconclusive: regex scoring removed (use EvaluationPipeline)"


async def send_single_turn(
    provider: ChatProvider,
    config: ProviderConfig,
    prompt: str,
) -> str:
    history: list[ChatMessage] = []
    if config.system_prompt:
        history.append(ChatMessage(role="system", content=config.system_prompt))
    history.append(ChatMessage(role="user", content=prompt))
    return await provider.send_message(history, config)
