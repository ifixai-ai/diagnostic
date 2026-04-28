

import json
import logging
from typing import Literal

from pydantic import BaseModel, Field

from ifixai.judge.evaluator import EnsembleJudgeEvaluator, JudgeEvaluator
from ifixai.core.types import ChatMessage

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

    inner_judge = (
        judge.evaluators[0]
        if isinstance(judge, EnsembleJudgeEvaluator)
        else judge
    )
    provider = inner_judge._provider
    provider_config = inner_judge._provider_config

    prompt = _PROMPT_TEMPLATES[mode].format(sources=sources, response=response)
    messages = [
        ChatMessage(role="system", content=prompt),
        ChatMessage(role="user", content="Emit the JSON array now."),
    ]

    try:
        raw = await provider.send_message(messages, provider_config)
    except Exception as exc:
        logger.warning("Atomic claim judge failed: %s", exc)
        return AtomicScore(mode=mode, error=f"judge call failed: {exc}")

    return _parse_atomic_response(raw, mode)


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
        claims.append(
            AtomicClaim(claim=text, supported=supported, reason=reason)
        )

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
