# OpenClaw — iFixAi benchmark artefacts

This directory holds every artefact produced while benchmarking [OpenClaw](https://openclaw.ai) v2026.5.4 against iFixAi v1.0.0.

## Files

- [`SCORECARD.md`](SCORECARD.md) — human-readable consolidated scorecard. **Start here.**
- [`SCORECARD.json`](SCORECARD.json) — machine-readable scores, cluster aggregates, per-test status.
- [`per-test/`](per-test/) — verbatim ifixai JSON + Markdown reports for each scored test. Each filename follows `BXX-<fixture-suffix>.{json,md}`.
- [`per-test/INDEX.md`](per-test/INDEX.md) — index of all per-test files.

## Quick summary

- **Subject:** OpenClaw v2026.5.4, upstream `anthropic/claude-3.5-haiku`, fixture `acme_legal.yaml`.
- **Overall score (capped):** 60.0% → Grade D.
- **Mandatory minimums:** B01 PASS (100%), B08 FAIL (37%) → triggered the 60% overall cap.
- **Coverage:** 22 of 32 tests scored (68%).
- **Cluster averages:** structural 100.0% / direct-policy 100.0% / adversarial 36.4% / envelope-shape 2.7%.

## Run details

The primary scorecard combines three back-to-back loops on the `acme_legal.yaml` fixture:

1. **Full sweep, 2-judge ensemble** (gpt-4o + claude-sonnet-4.6) — B01–B13.
2. **Curated, single-judge** (gpt-4o) — B16, B17, B19.
3. **Gap-fill, single-judge** (gpt-4o) — B24, B26–B28, B31, B32.

`B22` and `B30` wall-timed-out at the 15-minute per-test budget. `B14`, `B15`, `B18`, `B20`, `B21` are skipped (judge contract loop, exploratory-by-design, or known iFixAi rubric bug).

Cross-fixture stress-tests against `software_engineering.yaml` (haiku upstream), `openclaw.yaml` (custom hand-authored fixture + haiku) and `openclaw_strict.yaml` (custom strict-policy fixture + claude-sonnet-4.6) are included in the [`SCORECARD.md`](SCORECARD.md) cross-fixture table.

Full narrative case study including methodology rebuild, cluster analysis, and iFixAi-bug discoveries: **<https://ifixai.ai/docs/diagnostics/openclaw>**.