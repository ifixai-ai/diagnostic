import asyncio
import json
import logging
from typing import TYPE_CHECKING, Final, Literal

from pydantic import BaseModel, Field

from ifixai.judge.evaluator import EnsembleJudgeEvaluator, JudgeEvaluator
from ifixai.core.types import ChatMessage

if TYPE_CHECKING:
    from ifixai.core.types import ExpectedClaim

logger = logging.getLogger(__name__)

AtomicMode = Literal["grounding", "attribution"]

# Per-call timeout for atomic-claims judge requests. Mirrors the analytic-judge
# `_JUDGE_TIMEOUT` so a hung upstream cannot stall an entire benchmark via the
# provider's much-larger HTTP default (~5 min).
_ATOMIC_JUDGE_TIMEOUT: Final[float] = 60.0

# Output token ceiling for atomic-claims judge calls. Caps generation cost on
# verbose fixtures while leaving headroom for ~15 atomic claims at typical
# verbosity. Forward-direction guardrail — the previous path inherited no
# `max_tokens`, so the judge could spend up to the model's default ceiling.
_ATOMIC_MAX_TOKENS: Final[int] = 1024

# Bounded retry for atomic judge calls: first attempt + 1 retry. Recovers
# from transient parse failures (markdown fence, trailing prose, wrapper
# variations) and one-off provider hiccups without the analytic-judge path's
# heavier 5-attempt budget. Keeps worst-case latency at ~2 × timeout.
_ATOMIC_MAX_ATTEMPTS: Final[int] = 2

# Wrapper-key aliases accepted by the Postel atomic parser. Ordered: strict
# bare-list parse runs first; only if that fails do we try the whole-object
# wrapper-key path. "claims" is preferred for symmetry with our AtomicClaim
# domain term; the others cover common LLM variations.
_ATOMIC_LIST_KEY_ALIASES: Final[tuple[str, ...]] = (
    "claims",
    "results",
    "verdicts",
    "scores",
    "evaluations",
    "dimensions",
)


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


async def _send_atomic(
    evaluator: JudgeEvaluator,
    messages: list[ChatMessage],
) -> str:
    """Send a single atomic-judge request with bounded timeout and capped
    output tokens. Raises whatever ``send_message`` raises plus
    ``asyncio.TimeoutError`` on deadline expiry.
    """
    capped_config = evaluator._provider_config.model_copy(
        update={"max_tokens": _ATOMIC_MAX_TOKENS}
    )
    return await asyncio.wait_for(
        evaluator._provider.send_message(messages, capped_config),
        timeout=_ATOMIC_JUDGE_TIMEOUT,
    )


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
    last_error = ""
    for attempt in range(1, _ATOMIC_MAX_ATTEMPTS + 1):
        try:
            raw = await _send_atomic(evaluator, messages)
        except asyncio.TimeoutError:
            last_error = f"judge call timed out after {_ATOMIC_JUDGE_TIMEOUT}s"
            logger.warning(
                "Atomic judge attempt %d/%d timed out",
                attempt,
                _ATOMIC_MAX_ATTEMPTS,
            )
            continue
        except Exception as exc:
            last_error = f"judge call failed: {exc}"
            logger.warning(
                "Atomic judge attempt %d/%d failed: %s",
                attempt,
                _ATOMIC_MAX_ATTEMPTS,
                exc,
            )
            continue
        score = _parse_atomic_response(raw, mode)
        if not score.error:
            return score
        last_error = score.error
        logger.warning(
            "Atomic judge attempt %d/%d parse failed: %s",
            attempt,
            _ATOMIC_MAX_ATTEMPTS,
            score.error,
        )
    return AtomicScore(mode=mode, error=last_error or "judge call failed")


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


def _extract_claim_list(raw: str) -> list:
    """Postel-layer extractor for the atomic-claims response payload.

    Strict happy path stays first: find the outermost ``[...]`` and parse it
    as a list. Only if that fails do we attempt a whole-JSON-object parse and
    look for a list under any of the wrapper-key aliases. Strict prompt,
    generous parser — mirrors the Phase 1 Postel layer in the analytic-judge
    path without changing the prompt itself.

    Raises ``ValueError`` when no list can be recovered.
    """
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        inner = lines[1:] if len(lines) > 1 else lines
        if inner and inner[-1].strip() == "```":
            inner = inner[:-1]
        text = "\n".join(inner)

    # Strict path: outermost [...] (preserved happy-path behaviour).
    bracket_start = text.find("[")
    bracket_end = text.rfind("]")
    if bracket_start != -1 and bracket_end > bracket_start:
        try:
            data = json.loads(text[bracket_start:bracket_end + 1])
            if isinstance(data, list):
                return data
        except (ValueError, json.JSONDecodeError):
            pass  # fall through to wrapper-key path

    # Wrapper-key path: whole-object parse, look for an aliased list field.
    brace_start = text.find("{")
    brace_end = text.rfind("}")
    if brace_start != -1 and brace_end > brace_start:
        try:
            data = json.loads(text[brace_start:brace_end + 1])
        except (ValueError, json.JSONDecodeError) as exc:
            raise ValueError(f"no valid JSON object or array: {exc}") from exc
        if isinstance(data, dict):
            for alias in _ATOMIC_LIST_KEY_ALIASES:
                candidate = data.get(alias)
                if isinstance(candidate, list):
                    return candidate

    raise ValueError("no claim list found in judge response")


def _parse_atomic_response(raw: str, mode: AtomicMode) -> AtomicScore:
    try:
        data = _extract_claim_list(raw)
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
        return _parse_ground_truth_response(raw, expected_claims)

    # Single-judge path: bounded retry + timeout + capped max_tokens for
    # symmetry with the no-ground-truth atomic path. Recovers from one-off
    # provider hiccups and recoverable parse failures.
    last_error = ""
    for attempt in range(1, _ATOMIC_MAX_ATTEMPTS + 1):
        try:
            raw = await _send_atomic(judge, messages)
        except asyncio.TimeoutError:
            last_error = f"judge call timed out after {_ATOMIC_JUDGE_TIMEOUT}s"
            logger.warning(
                "Ground-truth judge attempt %d/%d timed out",
                attempt,
                _ATOMIC_MAX_ATTEMPTS,
            )
            continue
        except Exception as exc:
            last_error = f"judge call failed: {exc}"
            logger.warning(
                "Ground-truth judge attempt %d/%d failed: %s",
                attempt,
                _ATOMIC_MAX_ATTEMPTS,
                exc,
            )
            continue
        score = _parse_ground_truth_response(raw, expected_claims)
        if not score.error:
            return score
        last_error = score.error
        logger.warning(
            "Ground-truth judge attempt %d/%d parse failed: %s",
            attempt,
            _ATOMIC_MAX_ATTEMPTS,
            score.error,
        )
    return AtomicScore(mode="grounding", error=last_error or "judge call failed")


async def _call_single_evaluator(
    messages: list[ChatMessage],
    evaluator: JudgeEvaluator,
) -> str:
    """Ensemble worker: single send with timeout + capped max_tokens. No
    retry here — the ensemble itself provides parallel redundancy."""
    return await _send_atomic(evaluator, messages)


def _parse_ground_truth_response(
    raw: str,
    expected_claims: "list[ExpectedClaim]",
) -> AtomicScore:
    try:
        data = _extract_claim_list(raw)
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
