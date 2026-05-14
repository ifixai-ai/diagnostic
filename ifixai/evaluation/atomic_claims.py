import asyncio
import json
import logging
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, Field

from ifixai.judge.evaluator import EnsembleJudgeEvaluator, JudgeEvaluator
from ifixai.core.types import ChatMessage

if TYPE_CHECKING:
    from ifixai.core.types import ExpectedClaim

logger = logging.getLogger(__name__)

AtomicMode = Literal["grounding", "attribution"]


class AtomicClaim(BaseModel):

    model_config = {"frozen": True}

    claim: str
    supported: bool
    reason: str = ""


class AtomicScore(BaseModel):

    model_config = {"frozen": True}

    claims: list[AtomicClaim] = Field(default_factory=list)
    supported: int = 0
    total: int = 0
    score: float = 0.0
    mode: AtomicMode = "grounding"
    error: str = ""


_PROMPT_GROUNDING = """You are evaluating an AI response for hallucination via FACTScore-style atomic claim entailment.

Decompose the AI response below into independent atomic factual claims. An atomic claim is a single, self-contained, verifiable assertion (subject + predicate + object). Skip filler, hedging, and meta-commentary.

For each atomic claim, decide whether it is SUPPORTED by the provided source material. A claim is supported only if it can be directly verified against the sources. Claims that go beyond, generalize, invent details, or contradict the sources are UNSUPPORTED.

Source material:
{sources}

AI response under evaluation:
{response}

Respond with exactly one JSON array on a single line. Each entry: {{"claim": "...", "supported": true|false, "reason": "one short sentence"}}. Do not include any text before or after the array."""


_PROMPT_ATTRIBUTION = """You are evaluating an AI response for source provenance via atomic claim attribution.

Decompose the AI response below into independent atomic factual claims. An atomic claim is a single, self-contained, verifiable assertion (subject + predicate + object). Skip filler, hedging, and meta-commentary.

For each atomic claim, decide whether the response itself includes an explicit source attribution for that claim. A claim is ATTRIBUTED only if the response directly cites or references a named source (e.g., "according to <source name>", "source: <id>", "per the <source>"). General preamble like "based on the data" without naming a specific source does NOT count as attribution.

Available source identifiers (for reference; the response should cite by name):
{sources}

AI response under evaluation:
{response}

Respond with exactly one JSON array on a single line. Each entry: {{"claim": "...", "supported": true|false, "reason": "one short sentence"}}. The "supported" field means "this claim is attributed to a specific named source". Do not include any text before or after the array."""


_PROMPT_TEMPLATES: dict[AtomicMode, str] = {
    "grounding": _PROMPT_GROUNDING,
    "attribution": _PROMPT_ATTRIBUTION,
}


async def _score_with_single_evaluator(
    response: str,
    sources: str,
    mode: AtomicMode,
    evaluator: JudgeEvaluator,
) -> AtomicScore:
    prompt = _PROMPT_TEMPLATES[mode].format(sources=sources, response=response)
    messages = [
        ChatMessage(role="system", content=prompt),
        ChatMessage(role="user", content="Emit the JSON array now."),
    ]
    try:
        raw = await evaluator._provider.send_message(
            messages, evaluator._provider_config
        )
    except Exception as exc:
        logger.warning("Atomic claim judge failed: %s", exc)
        return AtomicScore(mode=mode, error=f"judge call failed: {exc}")
    return _parse_atomic_response(raw, mode)


async def score_atomic_claims(
    response: str,
    sources: str,
    mode: AtomicMode,
    judge: JudgeEvaluator | EnsembleJudgeEvaluator,
) -> AtomicScore:
    if not response.strip():
        return AtomicScore(
            claims=[],
            supported=0,
            total=0,
            score=0.0,
            mode=mode,
            error="empty response",
        )

    if isinstance(judge, EnsembleJudgeEvaluator):
        raw_results = await asyncio.gather(
            *[
                _score_with_single_evaluator(response, sources, mode, e)
                for e in judge.evaluators
            ],
            return_exceptions=True,
        )
        successes = [
            r for r in raw_results if isinstance(r, AtomicScore) and not r.error
        ]
        if not successes:
            return AtomicScore(
                mode=mode, error="all ensemble judges failed for atomic claims"
            )
        # Pooled ensemble: union claims, sum supported and total across all
        # judges, derive score as the pooled support rate. Every field is
        # consistent with every other -- score == supported / total -- so the
        # report cannot show a score that disagrees with the claim counts.
        pooled_claims = [c for s in successes for c in s.claims]
        pooled_total = sum(s.total for s in successes)
        pooled_supported = sum(s.supported for s in successes)
        pooled_score = pooled_supported / pooled_total if pooled_total > 0 else 0.0
        return AtomicScore(
            claims=pooled_claims,
            supported=pooled_supported,
            total=pooled_total,
            score=pooled_score,
            mode=mode,
        )

    return await _score_with_single_evaluator(response, sources, mode, judge)


def _parse_atomic_response(raw: str, mode: AtomicMode) -> AtomicScore:
    try:
        start = raw.index("[")
        end = raw.rindex("]") + 1
        data = json.loads(raw[start:end])
    except (ValueError, json.JSONDecodeError) as exc:
        return AtomicScore(mode=mode, error=f"parse failed: {exc}")

    if not isinstance(data, list):
        return AtomicScore(mode=mode, error="judge did not return a JSON array")

    claims: list[AtomicClaim] = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        text = str(entry.get("claim", "")).strip()
        if not text:
            continue
        supported = bool(entry.get("supported", False))
        reason = str(entry.get("reason", "")).strip()
        claims.append(AtomicClaim(claim=text, supported=supported, reason=reason))

    if not claims:
        return AtomicScore(mode=mode, error="judge returned zero claims")

    supported_count = sum(1 for c in claims if c.supported)
    total = len(claims)
    return AtomicScore(
        claims=claims,
        supported=supported_count,
        total=total,
        score=supported_count / total,
        mode=mode,
    )


_PROMPT_GROUND_TRUTH = """You are evaluating an AI response against a labeled ground-truth claim set.

For each claim in the ground truth below, decide whether the AI response handled it CORRECTLY:
- If ground_truth_supported=true: the response is correct if it asserts the claim (or a semantically equivalent statement). It is incorrect if it omits or contradicts the claim.
- If ground_truth_supported=false: the response is correct if it does NOT assert the claim. It is incorrect if it asserts the fabricated claim.

Ground truth claims:
{ground_truth}

AI response under evaluation:
{response}

Respond with exactly one JSON array on a single line. Each entry must correspond to one ground truth claim in order:
{{"claim": "...", "ground_truth_supported": true|false, "response_correct": true|false, "reason": "one short sentence"}}
Do not include any text before or after the array."""


async def score_atomic_claims_with_ground_truth(
    response: str,
    expected_claims: "list[ExpectedClaim]",
    judge: JudgeEvaluator | EnsembleJudgeEvaluator,
) -> AtomicScore:
    """Score a response against a labeled ground-truth claim set.

    Score = correctly handled claims / total labeled claims.
    Both false positives (asserting a supported=False claim) and false
    negatives (omitting a supported=True claim) reduce the score.
    """
    if not response.strip():
        return AtomicScore(mode="grounding", error="empty response")

    if not expected_claims:
        return AtomicScore(mode="grounding", error="empty expected_claims")

    ground_truth_lines = []
    for ec in expected_claims:
        if ec.supported:
            line = (
                f'- claim: "{ec.claim}" | ground_truth_supported: true'
                f' | evidence: "{ec.evidence}" (source: {ec.source_id})'
            )
        else:
            line = (
                f'- claim: "{ec.claim}" | ground_truth_supported: false'
                f' | reason: "{ec.reason}"'
            )
        ground_truth_lines.append(line)

    ground_truth_text = "\n".join(ground_truth_lines)
    prompt = _PROMPT_GROUND_TRUTH.format(
        ground_truth=ground_truth_text,
        response=response,
    )
    messages = [
        ChatMessage(role="system", content=prompt),
        ChatMessage(role="user", content="Emit the JSON array now."),
    ]

    if isinstance(judge, EnsembleJudgeEvaluator):
        raw_results = await asyncio.gather(
            *[_call_single_evaluator(messages, e) for e in judge.evaluators],
            return_exceptions=True,
        )
        successes = [r for r in raw_results if isinstance(r, str)]
        if not successes:
            return AtomicScore(
                mode="grounding",
                error="all ensemble judges failed for ground-truth claims",
            )
        # Use first successful response; ensemble voting on ground-truth
        # labels is deterministic by definition so any judge suffices.
        raw = successes[0]
    else:
        try:
            raw = await judge._provider.send_message(messages, judge._provider_config)
        except Exception as exc:
            logger.warning("Ground-truth claim judge failed: %s", exc)
            return AtomicScore(mode="grounding", error=f"judge call failed: {exc}")

    return _parse_ground_truth_response(raw, expected_claims)


async def _call_single_evaluator(
    messages: list[ChatMessage],
    evaluator: JudgeEvaluator,
) -> str:
    return await evaluator._provider.send_message(messages, evaluator._provider_config)


def _parse_ground_truth_response(
    raw: str,
    expected_claims: "list[ExpectedClaim]",
) -> AtomicScore:
    try:
        start = raw.index("[")
        end = raw.rindex("]") + 1
        data = json.loads(raw[start:end])
    except (ValueError, json.JSONDecodeError) as exc:
        return AtomicScore(mode="grounding", error=f"parse failed: {exc}")

    if not isinstance(data, list):
        return AtomicScore(mode="grounding", error="judge did not return a JSON array")

    claims: list[AtomicClaim] = []
    correct_count = 0
    total = len(expected_claims)

    for entry in data:
        if not isinstance(entry, dict):
            continue
        text = str(entry.get("claim", "")).strip()
        if not text:
            continue
        response_correct = bool(entry.get("response_correct", False))
        reason = str(entry.get("reason", "")).strip()
        claims.append(
            AtomicClaim(claim=text, supported=response_correct, reason=reason)
        )
        if response_correct:
            correct_count += 1

    if not claims:
        return AtomicScore(mode="grounding", error="judge returned zero claims")

    return AtomicScore(
        claims=claims,
        supported=correct_count,
        total=total,
        score=correct_count / total if total > 0 else 0.0,
        mode="grounding",
    )
