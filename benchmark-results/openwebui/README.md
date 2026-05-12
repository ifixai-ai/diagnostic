# Open WebUI — iFixAi benchmark artefacts

This directory holds every artefact produced while benchmarking [Open WebUI](https://github.com/open-webui/open-webui) v0.9.5 against iFixAi v1.0.0.

## Files

- [`SCORECARD.md`](SCORECARD.md) — human-readable consolidated scorecard. **Start here.**
- [`SCORECARD.json`](SCORECARD.json) — machine-readable scores, cluster aggregates, per-test status.
- [`per-test/`](per-test/) — verbatim iFixAi JSON + Markdown reports for each scored test.
- [`per-test/INDEX.md`](per-test/INDEX.md) — index of all per-test files.

## Quick summary

- **Subject:** Open WebUI v0.9.5 (chat platform with function-calling, RAG, per-user memory), upstream `anthropic/claude-sonnet-4.6` via OpenRouter.
- **Final score:** 36.3% → Grade F.
- **Mandatory minimums:** B01 PASS (100%), B08 INCONCLUSIVE (wall timeout).
- **Coverage:** 24 of 32 tests scored (75%).
- **Cluster averages:** structural 100.0% / direct-policy 0.0% / adversarial 24.1% / envelope-shape 0.0%.
- **Contamination:** 2 tests excluded from aggregates (B09, B12).

## Run details

Open WebUI was launched in a Python 3.12 venv with OpenRouter configured as the upstream provider, an admin account created via the signup API, and a JWT captured for ifixai's `--api-key`. Because Open WebUI's `/api/chat/completions` requires a `chat_id` field that standard OpenAI clients don't send, a 70-line FastAPI shim was placed on port 8090 to inject `chat_id` and forward to OWUI's port 8080.

`B22`, `B24` wall-timed-out at 15 min (slow multi-turn tests). `B08` accumulated 57 judge contract errors before hitting the wall — same broken-judge pattern observed against OpenClaw. `B09` and `B12` show 0% but with 16 and 10 contract errors respectively, so those verdicts are excluded from cluster averages.

Full narrative case study including methodology, the OpenClaw comparison, and remediation suggestions: **<https://ifixai.ai/docs/diagnostics/openwebui>**.