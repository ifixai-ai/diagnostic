# Open WebUI — iFixAi benchmark artefacts

Consolidated scorecard for the Open WebUI v0.9.5 evaluation.

## Files

- [`SCORECARD.md`](SCORECARD.md) — human-readable consolidated scorecard. **Start here.**
- [`SCORECARD.json`](SCORECARD.json) — machine-readable scores, cluster aggregates, per-test status.
- [`reproduce/`](reproduce/) — reproduction kit: the `chat_id` shim, Open WebUI launcher, and benchmark loop. Open WebUI's `/api/chat/completions` requires a non-standard `chat_id` field that standard OpenAI clients don't send, so reproduction needs the shim.

## Quick summary

- **Subject:** Open WebUI v0.9.5, upstream `anthropic/claude-sonnet-4.6` via OpenRouter.
- **Final score:** 36.3% → Grade F.
- **Mandatory minimums:** B01 PASS (100%), B08 INCONCLUSIVE (57 judge contract errors → wall timeout).
- **Coverage:** 24 of 32 tests scored.
- **Cluster averages:** structural 100% / direct policy 0% / adversarial 24.1% / envelope 0%.

Full narrative case study with the OpenClaw head-to-head: <https://ifixai.ai/docs/diagnostics/openwebui>.
