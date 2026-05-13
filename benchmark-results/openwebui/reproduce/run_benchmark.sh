#!/bin/bash
# Open WebUI benchmark: ifixai → shim (port 8090) → OWUI agent layer → OpenRouter.
set -u

: "${OPENROUTER_API_KEY:?OPENROUTER_API_KEY must be exported}"
OWUI_TOKEN="$(cat /tmp/owui-token.txt)"
[ -n "$OWUI_TOKEN" ] || { echo "ERROR: empty OWUI token"; exit 1; }

TESTS="B01 B02 B03 B04 B05 B06 B07 B08 B09 B10 B11 B12 B13 B16 B17 B19 B22 B23 B24 B25 B26 B27 B28 B29 B30 B31 B32"
# Skipped: B14 (judge contract loop), B15/B18/B21 (is_exploratory), B20 (judge prompt bug)

OUT_DIR="./benchmark-results/openwebui-v1"
SUMMARY="$OUT_DIR/summary.txt"
mkdir -p "$OUT_DIR"
: > "$SUMMARY"

echo "===OWUI RUN START $(date '+%H:%M:%S')===" | tee -a "$SUMMARY"
echo "  fixture:    openwebui.yaml" | tee -a "$SUMMARY"
echo "  upstream:   anthropic/claude-sonnet-4.6 (via OWUI agent layer)" | tee -a "$SUMMARY"
echo "  endpoint:   http://127.0.0.1:8090/v1 (shim injects chat_id)" | tee -a "$SUMMARY"
echo "  judges:     openai/gpt-4o + google/gemini-2.5-pro (cross-family ensemble)" | tee -a "$SUMMARY"
echo "  concurrency: 3 (within each test)" | tee -a "$SUMMARY"
echo "  tests:      $(echo $TESTS | wc -w | tr -d ' ') of 32" | tee -a "$SUMMARY"
echo "" | tee -a "$SUMMARY"

for t in $TESTS; do
  echo "===STARTED $t at $(date '+%H:%M:%S')===" | tee -a "$SUMMARY"
  out="$OUT_DIR/$t.log"
  perl -e 'alarm shift; exec @ARGV' 900 \
    .venv/bin/ifixai run \
    --provider http --endpoint http://127.0.0.1:8090/v1 \
    --api-key "$OWUI_TOKEN" --model "anthropic/claude-sonnet-4.6" \
    --fixture ifixai/fixtures/examples/openwebui.yaml \
    --mode standard --test "$t" \
    --eval-mode full \
    --judge-provider openrouter --judge-api-key "$OPENROUTER_API_KEY" --judge-model "openai/gpt-4o" \
    --judge-provider openrouter --judge-api-key "$OPENROUTER_API_KEY" --judge-model "google/gemini-2.5-pro" \
    --concurrency 3 --timeout 240 \
    --name "OpenWebUI" --version "0.9.5-openrouter-claude-sonnet-4.6" \
    --output "$OUT_DIR/$t/" > "$out" 2>&1
  ec=$?
  result_line=$(grep -E "\[[ 0-9]+/[ 0-9]+\] $t" "$out" 2>/dev/null | tail -1)
  contract_errs=$(grep -c "Judge contract error" "$out" 2>/dev/null | head -1)
  echo "===DONE $t at $(date '+%H:%M:%S') exit=$ec contract_errs=$contract_errs result=[$result_line]===" | tee -a "$SUMMARY"
  if [ "$ec" = "127" ] || [ "$ec" = "126" ]; then
    echo "HALT: $t script error" | tee -a "$SUMMARY"; break
  fi
  if grep -q "Connection failed:" "$out" 2>/dev/null; then
    echo "HALT: SUT connection failed on $t" | tee -a "$SUMMARY"; break
  fi
done

echo "===OWUI RUN END $(date '+%H:%M:%S')===" | tee -a "$SUMMARY"
echo "Summary: $SUMMARY"
