# Inspection → scoring category

This table is the **human-readable mirror** of the only authoritative assignment: `InspectionSpec.category` on each inspection’s `SPEC` in `ifixai/inspections/b<NN>_<slug>/runner.py`, aggregated via `ifixai.harness.registry.ALL_SPECS`.

Regulatory mapping files under `ifixai/mappings/` (OWASP LLM Top 10, NIST AI RMF, etc.) describe **framework control coverage**, not this five-bucket rollup. Do not use them to infer `FABRICATION` / `MANIPULATION` / `DECEPTION` / `UNPREDICTABILITY` / `OPACITY`.

| ID | Category |
|----|----------|
| B01 | FABRICATION |
| B02 | FABRICATION |
| B03 | FABRICATION |
| B04 | FABRICATION |
| B05 | FABRICATION |
| B06 | FABRICATION |
| B07 | MANIPULATION |
| B08 | MANIPULATION |
| B09 | MANIPULATION |
| B10 | DECEPTION |
| B11 | MANIPULATION |
| B12 | MANIPULATION |
| B13 | MANIPULATION |
| B14 | DECEPTION |
| B15 | DECEPTION |
| B16 | DECEPTION |
| B17 | DECEPTION |
| B18 | DECEPTION |
| B19 | UNPREDICTABILITY |
| B20 | UNPREDICTABILITY |
| B21 | UNPREDICTABILITY |
| B22 | UNPREDICTABILITY |
| B23 | UNPREDICTABILITY |
| B24 | OPACITY |
| B25 | OPACITY |
| B26 | OPACITY |
| B27 | OPACITY |
| B28 | MANIPULATION |
| B29 | OPACITY |
| B30 | MANIPULATION |
| B31 | OPACITY |
| B32 | OPACITY |

CI enforces that this table matches `ALL_SPECS` (`tests/test_inspection_categories_doc.py`).

## Website parity (W1)

Use this block as a **paired website** backlog item so marketing UI and the open-source diagnostic stay aligned.

**Title:** Align public site inspection pillars with repo `InspectionSpec.category` (B10, B30, B31, B32 + full 32)

**Problem:** The site’s five-bucket grouping for inspections must match the diagnostic’s scoring rollup. Any mismatch for B10, B30, B31, B32 (or any other ID) confuses readers comparing the site to a scorecard or this repo.

**Source of truth:** `ifixai/inspections/b<NN>_<slug>/runner.py` (`SPEC.category`) and this file’s table.

**Acceptance criteria:**

- [ ] For every `B01`–`B32`, the site’s pillar label matches the **Category** column above.
- [ ] Copy that describes “what we test” does not imply a different pillar for B10, B30, B31, or B32 than the table.
- [ ] Linked release note or changelog entry references this doc path after merge.

**Links:** Repository `docs/inspection_categories.md`; optional deep link to category weights in `docs/scoring.md`.
