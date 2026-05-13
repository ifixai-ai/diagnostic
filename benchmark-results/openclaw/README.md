# OpenClaw — iFixAi benchmark artefacts

Consolidated scorecard for the OpenClaw v2026.5.4 evaluation.

## Files

- [`SCORECARD.md`](SCORECARD.md) — human-readable consolidated scorecard. **Start here.**
- [`SCORECARD.json`](SCORECARD.json) — machine-readable scores, cluster aggregates, per-test status.

## Quick summary

- **Subject:** OpenClaw v2026.5.4, upstream `anthropic/claude-3.5-haiku`, fixture `acme_legal.yaml`.
- **Final score:** 60.0% → Grade D (raw mean 60.7%, capped by B08 mandatory-minimum failure).
- **Coverage:** 22 of 32 tests scored.
- **Cluster averages:** structural 100% / direct policy 100% / adversarial 36.4% / envelope 2.7%.

Full narrative case study: <https://ifixai.ai/docs/diagnostics/openclaw>.
