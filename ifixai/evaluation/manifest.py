

import hashlib
import json
import re
import secrets
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator

from ifixai.evaluation.types import ModelDescriptor
from ifixai.core.types import RunMode

_SHA256_HEX_RE = re.compile(r"^[0-9a-f]{64}$")
_ZERO_SHA256 = "0" * 64


class RunManifest(BaseModel):

    model_config = {"protected_namespaces": ()}

    run_id: str
    timestamp: str
    mode: RunMode
    model_under_test: ModelDescriptor
    judge_models: list[ModelDescriptor] = Field(default_factory=list)
    judge_temperature: float = Field(default=0.0)
    judge_identity: ModelDescriptor | None = Field(default=None)
    normalizer_version: str
    test_versions: dict[str, str]
    rubric_hashes: dict[str, str] = Field(default_factory=dict)
    fixture_digest: str
    governance_fixture_digest: str | None = None
    governance_source: str | None = None
    seed: int | None = None
    mode_filter: list[str] = Field(default_factory=list)
    strict_structured: bool = False
    b12_seed: int = Field(default=20260422, ge=0)
    b14_seed: int = Field(default=20260422, ge=0)
    b28_seed: int = Field(default=20260422, ge=0)
    b30_seed: int = Field(default=20260422, ge=0)
    sut_temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    sut_seed: int | None = Field(default=None)
    effective_sut_temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    effective_sut_seed: int | None = Field(default=None)
    seed_supported_by_provider: bool = Field(default=True)
    run_nonce: str = Field(default="")
    attestation_key_fingerprint: str | None = None
    holdout_seed: int | None = None
    holdout_ids: dict[str, str] = Field(default_factory=dict)

    @field_validator("fixture_digest")
    @classmethod
    def _validate_fixture_digest(cls, value: str) -> str:
        if not _SHA256_HEX_RE.match(value):
            raise ValueError(
                f"fixture_digest must be a 64-char lowercase sha256 hex string; got {value!r}"
            )
        if value == _ZERO_SHA256:
            raise ValueError(
                "fixture_digest must not be the all-zero sentinel; compute via "
                "ifixai.utils.fixture_digest.compute_fixture_digest()"
            )
        return value


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def compute_run_id(manifest_fields: dict[str, Any]) -> str:
    payload = {
        k: v for k, v in manifest_fields.items()
        if k != "timestamp" and k != "run_id"
    }
    canonical = _canonical_json(payload)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def build_manifest(
    mode: RunMode,
    model_under_test: ModelDescriptor,
    judge_models: list[ModelDescriptor],
    normalizer_version: str,
    test_versions: dict[str, str],
    rubric_hashes: dict[str, str],
    fixture_digest: str,
    governance_fixture_digest: str | None = None,
    governance_source: str | None = None,
    seed: int | None = None,
    mode_filter: list[str] | None = None,
    strict_structured: bool = False,
    judge_temperature: float = 0.0,
    judge_identity: ModelDescriptor | None = None,
    b12_seed: int = 20260422,
    b14_seed: int = 20260422,
    b28_seed: int = 20260422,
    b30_seed: int = 20260422,
    sut_temperature: float = 0.0,
    sut_seed: int | None = None,
    effective_sut_temperature: float = 0.0,
    effective_sut_seed: int | None = None,
    seed_supported_by_provider: bool = True,
    timestamp: str | None = None,
    attestation_key_fingerprint: str | None = None,
    holdout_seed: int | None = None,
    holdout_ids: dict[str, str] | None = None,
) -> RunManifest:
    if judge_models and model_under_test.model_id in {j.model_id for j in judge_models}:
        raise ValueError(
            "model_under_test must not appear in judge_models — "
            "self-judging is signaled by an empty judge_models list."
        )
    payload = {
        "mode": mode.value,
        "model_under_test": model_under_test.model_dump(),
        "judge_models": [j.model_dump() for j in judge_models],
        "judge_temperature": judge_temperature,
        "judge_identity": judge_identity.model_dump() if judge_identity else None,
        "normalizer_version": normalizer_version,
        "test_versions": test_versions,
        "rubric_hashes": rubric_hashes,
        "fixture_digest": fixture_digest,
        "governance_fixture_digest": governance_fixture_digest,
        "governance_source": governance_source,
        "seed": seed,
        "mode_filter": mode_filter or [],
        "strict_structured": strict_structured,
        "b12_seed": b12_seed,
        "b14_seed": b14_seed,
        "b28_seed": b28_seed,
        "b30_seed": b30_seed,
        "sut_temperature": sut_temperature,
        "sut_seed": sut_seed,
        "effective_sut_temperature": effective_sut_temperature,
        "effective_sut_seed": effective_sut_seed,
        "seed_supported_by_provider": seed_supported_by_provider,
    }
    run_nonce = secrets.token_hex(16)
    run_id = compute_run_id(payload)
    return RunManifest(
        run_id=run_id,
        timestamp=timestamp or datetime.utcnow().isoformat(timespec="seconds") + "Z",
        run_nonce=run_nonce,
        attestation_key_fingerprint=attestation_key_fingerprint,
        holdout_seed=holdout_seed,
        holdout_ids=holdout_ids or {},
        mode=mode,
        model_under_test=model_under_test,
        judge_models=judge_models,
        judge_temperature=judge_temperature,
        judge_identity=judge_identity,
        normalizer_version=normalizer_version,
        test_versions=test_versions,
        rubric_hashes=rubric_hashes,
        fixture_digest=fixture_digest,
        governance_fixture_digest=governance_fixture_digest,
        governance_source=governance_source,
        seed=seed,
        mode_filter=mode_filter or [],
        strict_structured=strict_structured,
        b12_seed=b12_seed,
        b14_seed=b14_seed,
        b28_seed=b28_seed,
        b30_seed=b30_seed,
        sut_temperature=sut_temperature,
        sut_seed=sut_seed,
        effective_sut_temperature=effective_sut_temperature,
        effective_sut_seed=effective_sut_seed,
        seed_supported_by_provider=seed_supported_by_provider,
    )


def verify_run_id(manifest: RunManifest) -> bool:
    payload = manifest.model_dump(mode="json", exclude={"run_id", "timestamp"})
    expected = compute_run_id(payload)
    return manifest.run_id == expected


def write_manifest(manifest: RunManifest, base_dir: Path) -> Path:
    run_dir = base_dir / manifest.run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    out_path = run_dir / "manifest.json"
    out_path.write_text(
        json.dumps(manifest.model_dump(mode="json"), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return out_path
