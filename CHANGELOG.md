# Changelog

All notable changes to `ifixai` will be recorded here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); this project uses
[SemVer](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Semaphore-based concurrency for B08, B14, B22, B29, B32.** A new `ConcurrencyGovernor` in `ifixai/core/concurrency.py` replaces ad-hoc sequential execution. Default limit is 12 concurrent requests per inspection; configurable via `DEFAULT_INSPECTION_CONCURRENCY`. The governor halves its effective limit on rate-limit responses and recovers gradually.
- **HMAC attestation scaffold.** `ifixai/attestation/` adds an HMAC-SHA256 verifier (`check_attestation`, `check_list_attestation`) wired into the structural hooks of B02, B03, B11, B13, B23, and B25. **The signing side is not yet implemented** — no provider currently populates `signature` or `signed_payload`. Setting `IFIXAI_ATTESTATION_KEY` before providers implement signing will cause all attested inspections to return failed evidence and short-circuit their real checks.
- **Dynamic holdout IDs for B14.** `B14_DEFAULT_SEED` and per-run `b14_seed` pipeline config allow reproducible but varied adversarial-mutation sets across runs.
- **TypedDict returns on governance architecture hooks.** `GovernanceArchitecture` and related structural return types are now fully typed `TypedDict` subclasses, replacing untyped dicts.

### Changed

- **B23 is now a hybrid inspection.** Previously structural-only (audit-trail `rule_applied` check). Now also runs a conversational step asking the provider to articulate active policy versions. Providers whose `get_audit_trail` hook returns `None` still emit `insufficient_evidence`.
- **`mandatory_minimums`: absent and `insufficient_evidence` tests now map to `FAIL`.** Previously both conditions produced `INCONCLUSIVE`. This tightens the mandatory-minimum gate (B01, B08) and means aggregate scores are **not directly comparable with v1.0.0** results.

## [1.0.0] — 2026-04-27

Initial public release.
