

import logging
from typing import TYPE_CHECKING

from ifixai.evaluation.analytic_judge import (
    JudgeCommunicationError,
    JudgeContractError,
    JudgeExtractionError,
)
from ifixai.evaluation.atomic_claims import (
    AtomicMode,
    AtomicScore,
    score_atomic_claims,
)
from ifixai.evaluation.response_classifier import ResponseClass, classify_response
from ifixai.core.types import (
    AnalyticRubric,
    EvaluationCriteria,
    EvaluationMethod,
    EvaluationPipelineConfig,
    JudgeErrorKind,
    PipelineResult,
    ReferenceResponse,
)

if TYPE_CHECKING:
    from ifixai.evaluation.analytic_judge import AnalyticRubricJudge, EnsembleAnalyticRubricJudge

_logger = logging.getLogger(__name__)

class EvaluationPipeline:

    def __init__(
        self,
        config: EvaluationPipelineConfig,
        judge: "AnalyticRubricJudge | EnsembleAnalyticRubricJudge | None" = None,
    ) -> None:
        self._config = config
        self._judge = judge
        self._judge_calls_used = 0

    @property
    def judge_calls_used(self) -> int:
        return self._judge_calls_used

    async def evaluate(
        self,
        response: str,
        criteria: EvaluationCriteria,
        rubric: AnalyticRubric | None = None,
        references: list[ReferenceResponse] | None = None,
        context: str = "",
    ) -> PipelineResult:
        if self._judge is not None and rubric is not None:
            if (
                self._config.judge_max_calls > 0
                and self._judge_calls_used >= self._config.judge_max_calls
            ):
                _logger.warning(
                    "Judge budget exhausted (%d/%d calls used)",
                    self._judge_calls_used,
                    self._config.judge_max_calls,
                )
                return PipelineResult(
                    passed=False,
                    evaluation_result="inconclusive: judge budget exhausted",
                    evaluation_method=EvaluationMethod.JUDGE,
                )

            try:
                rubric_verdict = await self._judge.evaluate_with_rubric(
                    response, rubric, context
                )
                self._judge_calls_used += 1
                return PipelineResult(
                    passed=rubric_verdict.passed,
                    evaluation_result=f"judge: {rubric_verdict.verdict} (weighted_score={rubric_verdict.weighted_score:.2f})",
                    evaluation_method=EvaluationMethod.JUDGE,
                    dimension_scores=rubric_verdict.dimension_scores,
                    rubric_verdict=rubric_verdict,
                )
            except JudgeCommunicationError as exc:
                _logger.exception("Judge communication error")
                self._judge_calls_used += 1
                return PipelineResult(
                    passed=False,
                    evaluation_result=f"extraction_error: communication: {exc}",
                    evaluation_method=EvaluationMethod.JUDGE,
                    extraction_error=JudgeErrorKind.COMMUNICATION,
                )
            except JudgeExtractionError as exc:
                _logger.error("Judge extraction error: %s", exc)
                self._judge_calls_used += 1
                return PipelineResult(
                    passed=False,
                    evaluation_result=f"extraction_error: extraction: {exc}",
                    evaluation_method=EvaluationMethod.JUDGE,
                    extraction_error=JudgeErrorKind.EXTRACTION,
                )
            except JudgeContractError as exc:
                _logger.error("Judge contract error: %s", exc)
                self._judge_calls_used += 1
                return PipelineResult(
                    passed=False,
                    evaluation_result=f"extraction_error: contract: {exc}",
                    evaluation_method=EvaluationMethod.JUDGE,
                    extraction_error=JudgeErrorKind.CONTRACT,
                )

        return PipelineResult(
            passed=False,
            evaluation_result="inconclusive: no judge configured (regex scoring removed)",
            evaluation_method=EvaluationMethod.JUDGE,
        )

    async def classify(self, response: str, query: str) -> ResponseClass | None:
        if self._judge is None:
            return None
        if (
            self._config.judge_max_calls > 0
            and self._judge_calls_used >= self._config.judge_max_calls
        ):
            _logger.warning(
                "Judge budget exhausted (%d/%d calls used) — classify skipped",
                self._judge_calls_used,
                self._config.judge_max_calls,
            )
            return None
        self._judge_calls_used += 1
        return await classify_response(
            response_text=response,
            query=query,
            judge_provider=self._judge._judge._provider,
            judge_config=self._judge._judge._provider_config,
        )

    async def evaluate_atomic(
        self,
        response: str,
        sources: str,
        mode: AtomicMode,
    ) -> AtomicScore | None:
        if self._judge is None:
            return None
        if (
            self._config.judge_max_calls > 0
            and self._judge_calls_used >= self._config.judge_max_calls
        ):
            _logger.warning(
                "Judge budget exhausted (%d/%d calls used) — atomic skipped",
                self._judge_calls_used,
                self._config.judge_max_calls,
            )
            return None
        self._judge_calls_used += 1
        from ifixai.evaluation.analytic_judge import EnsembleAnalyticRubricJudge
        judge_arg = (
            self._judge._ensemble
            if isinstance(self._judge, EnsembleAnalyticRubricJudge)
            else self._judge._judge
        )
        return await score_atomic_claims(
            response=response,
            sources=sources,
            mode=mode,
            judge=judge_arg,
        )
