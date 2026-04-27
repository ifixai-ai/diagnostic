# Reproducibility

`ifixai` records every run against a content-addressed manifest (`runs/<run_id>/manifest.json`) that captures the exact inputs to the score so an auditor can reproduce the run later. This document specifies how the manifest's content-addressability works, what it does and does not guarantee, and how to replay a run.

## The fixture digest

The manifest's `fixture_digest` field is a SHA-256 hex string (64 characters, lowercase) computed over the canonicalised YAML content of the fixture used for the run. It is NOT the hash of the raw bytes — YAML comments and whitespace do not affect it. The canonicalisation is:

1. Read the fixture file as UTF-8.
2. Parse it via `yaml.safe_load` (discards comments, normalises whitespace).
3. Recursively sort dictionary keys at every nesting level. List order is preserved.
4. Serialise via `json.dumps(..., sort_keys=True, separators=(",", ":"), ensure_ascii=False)`.
5. Encode UTF-8 and take `hashlib.sha256(...).hexdigest()`.

This produces a digest that is:

- Stable across YAML comment edits.
- Stable across YAML whitespace and key-order edits.
- Stable across equivalent scalar representations (e.g. `1` and `1.0` are still distinct scalars since we do not canonicalise number types beyond what `yaml.safe_load` returns).
- Sensitive to list order, since lists in our fixtures are semantically ordered (e.g. step sequences).
- Sensitive to any value change.

The algorithm is pinned. Any future change is a breaking change to the manifest format and requires a new schema version.

The all-zero sentinel (`"0" * 64`) is rejected at model-validation time and by a CI guardrail (`tests/test_manifest_digest.py`). If you see it in a manifest, that manifest is not reproducible — regenerate.

## The run ID

`run_id` is a 16-char sha256 hex of the manifest's canonicalised payload, excluding `run_id` itself and `timestamp`. Two runs with identical inputs produce the same `run_id`. This is what makes the manifest "content-addressed".

## Masked non-deterministic fields

Byte-identity across replay assertions excludes the following fields, which are expected to differ between runs and are not load-bearing for the score:

- `manifest.timestamp`
- `scorecard.generated_at`
- `scorecard.runtime_seconds`
- Per-inspection `latency_ms`, `started_at`, `completed_at`

## What reproducibility does NOT promise

- **Network-dependent scores are not reproducible against live providers.** LLMs are non-deterministic; two runs against the same provider with the same inputs produce different outputs. To verify bit-identical replay you need a deterministic provider (see `tests/fixtures/`).
- **Reproducibility is conditional on the judge set.** Changing the judge provider or judge model changes the manifest and therefore the `run_id`, even if the model-under-test's outputs are identical.
- **Rubric hashes, test versions, and the normaliser version are all pinned.** Any upgrade of any of these produces a new `run_id`; this is intentional — it forces auditors to notice the upgrade.

## Replaying a run

There is no dedicated `replay` CLI command. The internal API supports it directly:

```python
from ifixai.evaluation.manifest import RunManifest, verify_run_id
from ifixai.utils.fixture_digest import verify_fixture_digest

manifest = RunManifest.model_validate_json(open("runs/<run_id>/manifest.json").read())
assert verify_run_id(manifest), "manifest has been tampered with"
assert verify_fixture_digest(fixture_path, manifest.fixture_digest), "fixture has been edited"
```

With a deterministic provider that returns a pre-recorded response table (see `tests/fixtures/deterministic_provider.py`), re-running against the same manifest produces a byte-identical scorecard modulo the masked fields listed above.

A dedicated replay CLI is planned for a future minor version.
