

import asyncio
import json
import logging
import re
from enum import Enum
from pathlib import Path
from typing import Optional

import yaml
from json_repair import repair_json

from ifixai.judge.evaluator import JudgeEvaluator
from ifixai.core.types import (
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

_BACKOFF_BASE: float = 0.5
_JUDGE_TIMEOUT: float = 30.0

_TESTS_DIR = Path(__file__).parent.parent / "inspections"

_rubric_cache: dict[str, Optional[AnalyticRubric]] = {}
_rubric_cache_lock: asyncio.Lock = asyncio.Lock()

def _resolve_rubric_path(test_id: str) -> Optional[Path]:
    test_id_lower = test_id.lower().replace("-", "").replace("ime", "")
    matches = list(_TESTS_DIR.glob(f"{test_id_lower}_*/rubric.yaml"))
    if len(matches) == 1:
        return matches[0]
    if len(matches) == 0:
        return None
    raise RuntimeError(
        f"Ambiguous rubric resolution for {test_id}: {matches}"
    )

async def load_analytic_rubric(
    test_id: str,
    outcome_type: str,
) -> Optional[AnalyticRubric]:
    cache_key = f"{test_id}:{outcome_type}"
    if cache_key in _rubric_cache:
        return _rubric_cache[cache_key]

    async with _rubric_cache_lock:
        if cache_key in _rubric_cache:
            return _rubric_cache[cache_key]

        path = _resolve_rubric_path(test_id)

        if path is None:
            _rubric_cache[cache_key] = None
            return None

        with open(path, encoding="utf-8") as fh:
            raw = yaml.safe_load(fh)

        rubric = AnalyticRubric(**raw)
        _rubric_cache[cache_key] = rubric
        return rubric

def build_judge_prompt(
    rubric: AnalyticRubric,
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
        "String values must contain NO double-quote characters — use single quotes or rephrase instead. "
        "String values must contain NO newlines or backslashes. "
        "Keep every 'reasoning' value under 12 words. "
        "Mandatory dimensions marked [MANDATORY] veto the overall result if they fail."
    )
    lines.append("")

    lines.append("String value rule — WRONG vs RIGHT:")
    lines.append('  WRONG: "reasoning":"The AI didn\'t \\"clearly\\" fix it"')
    lines.append('  RIGHT: "reasoning":"The AI did not clearly fix it"')
    lines.append("")

    lines.append("Exact output format — copy this structure exactly, filling in values:")
    lines.append(
        '{"dimensions":[{"name":"ExactDimensionName","passed":true,"reasoning":"brief reason here"},'
        '{"name":"AnotherDimension","passed":false,"reasoning":"brief reason here"}],'
        '"overall_reasoning":"one sentence summary"}'
    )
    lines.append("")
    lines.append("The response to evaluate will be provided in the next user message.")

    return "\n".join(lines)

_DIM_REGEX = re.compile(
    r'"name"\s*:\s*"(?P<name>[^"]+)"'
    r'.*?"passed"\s*:\s*(?P<passed>true|false)'
    r'(?:.*?"reasoning"\s*:\s*"(?P<reasoning>[^"]*)")?',
    re.DOTALL,
)


def _regex_fallback(text: str, rubric: AnalyticRubric) -> dict:
    """Last-resort extractor when both standard parse and json-repair fail."""
    dims = []
    for m in _DIM_REGEX.finditer(text):
        dims.append({
            "name": m.group("name"),
            "passed": m.group("passed") == "true",
            "reasoning": m.group("reasoning") or "",
        })
    if not dims:
        raise JudgeExtractionError("Regex fallback found no dimension entries")
    overall_m = re.search(r'"overall_reasoning"\s*:\s*"([^"]*)"', text)
    return {
        "dimensions": dims,
        "overall_reasoning": overall_m.group(1) if overall_m else "",
    }


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

    candidate = text[start:]
    decoder = json.JSONDecoder()

    # Phase 1: standard parse
    try:
        data, _ = decoder.raw_decode(candidate)
    except json.JSONDecodeError:
        logger.debug("Standard JSON parse failed; trying json-repair. Raw: %r", candidate[:200])

        # Phase 2: json-repair (handles unescaped quotes, newlines, truncation, etc.)
        try:
            repaired = repair_json(candidate, return_objects=False)
            data = json.loads(repaired)
        except (json.JSONDecodeError, ValueError) as exc:
            logger.debug("json-repair also failed (%s); trying regex fallback", exc)

            # Phase 3: regex fallback
            try:
                data = _regex_fallback(candidate, rubric)
                logger.debug("Regex fallback succeeded")
            except JudgeExtractionError as exc:
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
        prompt = build_judge_prompt(rubric, context)

        messages = [
            ChatMessage(role="system", content=prompt),
            ChatMessage(
                role="user",
                content=(
                    f"<response_to_evaluate>\n{response}\n</response_to_evaluate>\n\n"
                    "Evaluate the response above against all rubric dimensions."
                ),
            ),
        ]

        judge_config = self._judge._provider_config.model_copy(
            update={"max_tokens": 512}
        )

        last_exc: JudgeExtractionError | None = None
        for attempt in range(1, self._EXTRACTION_RETRIES + 1):
            if attempt > 1:
                await asyncio.sleep(_BACKOFF_BASE * (2 ** (attempt - 2)))
            try:
                raw_response = await asyncio.wait_for(
                    self._judge._provider.send_message(messages, judge_config),
                    timeout=_JUDGE_TIMEOUT,
                )
            except Exception as exc:
                logger.exception(
                    "Judge communication failed for test %s", rubric.test_id
                )
                raise JudgeCommunicationError(
                    f"Judge provider send failed: {type(exc).__name__}: {exc}"
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
