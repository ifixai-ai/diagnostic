# Changelog

All notable changes to `ifixai` will be recorded here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); this project uses
[SemVer](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Provider replay protection.** Every run now generates a `run_nonce` (16 lowercase hex chars) via `secrets.token_hex(8)`. The nonce is appended to the SUT system prompt as `[run_id: <nonce>]`, so a hostile provider that caches `(prompt_hash) → canned reply` under deterministic mode (`temperature=0`, fixed seed) cannot match across runs. The nonce participates in `run_id` computation, so two default runs with otherwise identical inputs now produce different `run_id`s. Pass `--run-nonce <16-hex>` to pin the value for exact replay. New `ChatProvider.replay_protected` class attribute (default `True`) lets providers self-report.
- **Manifest schema v2.** `RunManifest.schema_version` is now recorded explicitly. v1 manifests (pre-H4) load through a back-compat path (`load_manifest()`) that emits a `DeprecationWarning` and synthesises `run_nonce=""`; `verify_run_id()` is version-aware so legacy `run_id`s still verify.
- **Semaphore-based concurrency for B08, B14, B22, B29, B32.** A new `ConcurrencyGovernor` in `ifixai/core/concurrency.py` replaces ad-hoc sequential execution. Default limit is 12 concurrent requests per inspection; configurable via `DEFAULT_INSPECTION_CONCURRENCY`. The governor halves its effective limit on rate-limit responses and recovers gradually.
- **HMAC attestation scaffold.** `ifixai/attestation/` adds an HMAC-SHA256 verifier (`check_attestation`, `check_list_attestation`) wired into the structural hooks of B02, B03, B11, B13, B23, and B25. **The signing side is not yet implemented** — no provider currently populates `signature` or `signed_payload`. Setting `IFIXAI_ATTESTATION_KEY` before providers implement signing will cause all attested inspections to return failed evidence and short-circuit their real checks.
- **Dynamic holdout IDs for B14.** `B14_DEFAULT_SEED` and per-run `b14_seed` pipeline config allow reproducible but varied adversarial-mutation sets across runs.
- **TypedDict returns on governance architecture hooks.** `GovernanceArchitecture` and related structural return types are now fully typed `TypedDict` subclasses, replacing untyped dicts.

### Changed

- **B23 is now a hybrid inspection.** Previously structural-only (audit-trail `rule_applied` check). Now also runs a conversational step asking the provider to articulate active policy versions. Providers whose `get_audit_trail` hook returns `None` still emit `insufficient_evidence`.
- **`mandatory_minimums`: absent and `insufficient_evidence` tests now map to `FAIL`.** Previously both conditions produced `INCONCLUSIVE`. This tightens the mandatory-minimum gate (B01, B08) and means aggregate scores are **not directly comparable with v1.0.0** results.

## [1.0.0] — 2026-04-27

Initial public release.
