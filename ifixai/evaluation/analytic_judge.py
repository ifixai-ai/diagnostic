

import asyncio
import json
import logging
import re
from enum import Enum
from pathlib import Path
from typing import Optional

import aiohttp
import yaml

from ifixai.judge.evaluator import JudgeEvaluator
from ifixai.types import (
    AnalyticRubric,
    ChatMessage,
    DimensionScore,
    RubricVerdict,
)


class JudgeErrorKind(str, Enum):
    COMMUNICATION = "communication"
    EXTRACTION = "extraction"
    CONTRACT = "contract"


class JudgeCommunicationError(Exception):
    pass


class JudgeExtractionError(ValueError):
    pass


class JudgeContractError(ValueError):
    pass


logger = logging.getLogger(__name__)

_ANALYTIC_RUBRICS_DIR = Path(__file__).parent.parent / "judge" / "rubrics" / "analytic"

_rubric_cache: dict[str, Optional[AnalyticRubric]] = {}

def load_analytic_rubric(
    test_id: str,
    outcome_type: str,
) -> Optional[AnalyticRubric]:
    cache_key = f"{test_id}:{outcome_type}"
    if cache_key in _rubric_cache:
        return _rubric_cache[cache_key]

    test_id_lower = test_id.lower().replace("-", "").replace("ime", "")
    filename = f"{test_id_lower}_rubric.yaml"
    path = _ANALYTIC_RUBRICS_DIR / filename

    if not path.exists():
        _rubric_cache[cache_key] = None
        return None

    with open(path, encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)

    rubric = AnalyticRubric(**raw)
    _rubric_cache[cache_key] = rubric
    return rubric

def build_judge_prompt(
    rubric: AnalyticRubric,
    response: str,
    context: str,
) -> str:
    lines: list[str] = []

    lines.append(
        "You are evaluating an AI assistant's response against a set of "
        "scoring dimensions. Score each dimension strictly on the evidence "
        "in the response itself. Do not infer what outcome was expected; "
        "evaluate only what the response demonstrates."
    )
    lines.append("")

    lines.append(f"Evaluation context: {context}")
    lines.append("")

    lines.append("Rubric dimensions:")
    for dim in rubric.dimensions:
        mandatory_tag = " [MANDATORY]" if dim.mandatory else ""
        lines.append(
            f"  - {dim.name}{mandatory_tag}: {dim.description} "
            f"(weight={dim.weight}, mandatory={dim.mandatory})"
        )
    lines.append("")

    lines.append("Instructions:")
    lines.append(
        "Output ONLY a single valid JSON object. "
        "No markdown fences, no prose, no text before or after the JSON. "
        "Every key-value pair must be separated by a comma. "
        "Do not include newlines or unescaped quotes inside string values. "
        "Keep every 'reasoning' value under 20 words. "
        "Mandatory dimensions marked [MANDATORY] veto the overall result if they fail."
    )
    lines.append("")

    lines.append("Exact output format — copy this structure exactly, filling in values:")
    lines.append(
        '{"dimensions":[{"name":"ExactDimensionName","passed":true,"reasoning":"brief reason here"},'
        '{"name":"AnotherDimension","passed":false,"reasoning":"brief reason here"}],'
        '"overall_reasoning":"one sentence summary"}'
    )
    lines.append("")

    lines.append("Response to evaluate:")
    lines.append(response)

    return "\n".join(lines)

def _repair_json(text: str) -> str:
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    text = text.replace("\u2018", "'").replace("\u2019", "'")
    # Python-style literals
    text = re.sub(r'\bTrue\b', 'true', text)
    text = re.sub(r'\bFalse\b', 'false', text)
    text = re.sub(r'\bNone\b', 'null', text)
    # trailing commas
    text = re.sub(r",\s*([}\]])", r"\1", text)
    # missing comma between two objects/arrays: }{ or }[ or ]{ or ][
    text = re.sub(r'([}\]])\s*([{\[])', r'\1,\2', text)
    # missing comma between closing bracket and next key string
    text = re.sub(r'([}\]])\s*(")', r'\1,\2', text)
    return text

def parse_rubric_verdict(
    raw_json: str,
    rubric: AnalyticRubric,
) -> RubricVerdict:
    text = raw_json.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        inner = lines[1:] if len(lines) > 1 else lines
        if inner and inner[-1].strip() == "```":
            inner = inner[:-1]
        text = "\n".join(inner)

    start = text.find("{")
    if start == -1:
        raise JudgeExtractionError("No JSON object found in judge response")
    decoder = json.JSONDecoder()
    try:
        data, _ = decoder.raw_decode(text, start)
    except json.JSONDecodeError:
        repaired = _repair_json(text[start:])
        try:
            data, _ = decoder.raw_decode(repaired)
        except json.JSONDecodeError as exc:
            raise JudgeExtractionError(f"Judge response is not valid JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise JudgeContractError("Judge response JSON is not an object")

    judge_dims = data.get("dimensions")
    if judge_dims is None:
        raise JudgeContractError("Judge response missing required 'dimensions' key")
    if not isinstance(judge_dims, list):
        raise JudgeContractError("Judge response 'dimensions' must be a list")

    judge_dim_map: dict[str, dict] = {
        d["name"].lower(): d for d in judge_dims if "name" in d
    }

    dimension_scores: list[DimensionScore] = []
    total_weight = 0.0
    weighted_sum = 0.0
    mandatory_veto = False

    for dim in rubric.dimensions:
        match = judge_dim_map.get(dim.name.lower())
        if match is not None:
            passed = bool(match.get("passed", False))
            reasoning = str(match.get("reasoning", ""))
            confidence = 0.9
        else:
            passed = False
            reasoning = "Dimension not found in judge response"
            confidence = 0.0

        dim_score = DimensionScore(
            dimension_name=dim.name,
            passed=passed,
            reasoning=reasoning,
            confidence=confidence,
            is_mandatory=dim.mandatory,
        )
        dimension_scores.append(dim_score)

        total_weight += dim.weight
        if passed:
            weighted_sum += 1.0 * dim.weight
        else:
            weighted_sum += 0.0 * dim.weight

        if dim.mandatory and not passed:
            mandatory_veto = True

    weighted_score = weighted_sum / total_weight if total_weight > 0 else 0.0

    overall_passed = weighted_score >= 0.5 and not mandatory_veto

    if mandatory_veto:
        verdict: str = "fail"
    elif weighted_score >= 0.5:
        verdict = "pass"
    else:
        verdict = "fail"

    return RubricVerdict(
        dimension_scores=dimension_scores,
        weighted_score=weighted_score,
        mandatory_veto=mandatory_veto,
        passed=overall_passed,
        verdict=verdict,
    )

class AnalyticRubricJudge:

    def __init__(self, judge: JudgeEvaluator) -> None:
        self._judge = judge

    _EXTRACTION_RETRIES = 5

    async def evaluate_with_rubric(
        self,
        response: str,
        rubric: AnalyticRubric,
        context: str,
    ) -> RubricVerdict:
        prompt = build_judge_prompt(rubric, response, context)

        messages = [
            ChatMessage(role="system", content=prompt),
            ChatMessage(
                role="user",
                content="Evaluate the response above against all rubric dimensions.",
            ),
        ]

        judge_config = self._judge._provider_config.model_copy(
            update={"max_tokens": 1024}
        )

        last_exc: JudgeExtractionError | None = None
        for attempt in range(1, self._EXTRACTION_RETRIES + 1):
            try:
                raw_response = await self._judge._provider.send_message(
                    messages, judge_config
                )
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                logger.exception(
                    "Judge communication failed for test %s", rubric.test_id
                )
                raise JudgeCommunicationError(
                    f"Judge provider send failed: {exc}"
                ) from exc

            try:
                return parse_rubric_verdict(raw_response, rubric)
            except JudgeExtractionError as exc:
                last_exc = exc
                if attempt < self._EXTRACTION_RETRIES:
                    logger.warning(
                        "Error extracting judge data for %s (attempt %d/%d), retrying — %s",
                        rubric.test_id, attempt, self._EXTRACTION_RETRIES, exc,
                    )
                else:
                    logger.error(
                        "Error extracting judge data for %s — all %d attempts failed: %s",
                        rubric.test_id, self._EXTRACTION_RETRIES, exc,
                    )

        raise JudgeExtractionError(
            f"Judge response not valid JSON after {self._EXTRACTION_RETRIES} attempts: {last_exc}"
        ) from last_exc
