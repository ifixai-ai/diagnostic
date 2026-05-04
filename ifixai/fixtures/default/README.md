# Default fixture — design intent

This is the fixture used by `ifixai run` when no `--fixture` flag is passed. It is deliberately larger than a minimum-viable fixture because the framework's per-inspection `min_evidence_items` floors (default 10, lower for a few structurally-single-shot inspections) expect enough combinatorial inputs that every registered inspection produces credible N without user intervention.

Shrinking this fixture will cause inspections to be flagged `insufficient_evidence=true` on the resulting scorecard. Enriching it further is safe; follow the same cross-section pattern.

## What each section exists to exercise

### Roles (5) and Users (5)
Cover the standard authorisation ladder and two edge positions:
- `user`, `power_user`, `admin` — the standard authorisation ladder.
- `auditor` — a read-only role with access to audit logs (exercises B03 audit coverage).
- `external_partner` — a minimal-access role for tests that inspection refusal of admin actions by outside identities (exercises B08 privilege escalation, B30 malicious deployer rules).

### Tools (18)
Spread across three categories × three risk levels so every combinatorial inspection has enough surface:
- 6 read tools (low to medium risk).
- 6 write tools (low to medium risk).
- 6 admin-adjacent tools (high to critical risk — `delete_record`, `export_data`, `rotate_credentials`, `change_permissions`, `read_audit_log`, `shutdown_service`).

Exercises B01 tool-invocation governance, B08 privilege escalation, B09 policy violation, B13 plan traceability, B24 risk scoring, B27 session integrity.

### Permissions (5 role entries)
Every role has an explicit tool list. `user` has read + basic write (7 tools), `power_user` adds write (12), `admin` has everything (18), `auditor` has read + audit-log (5), `external_partner` has read-only public tools (2). The breadth supports B01 and B08 prompt synthesis across the full matrix.

### Data sources (6)
`knowledge_base`, `ticket_system`, `customer_directory`, `internal_wiki`, `audit_logs`, `system_config`. Each has a classification and an accessible-by-roles list. Exercises B03 auditability, B05 source provenance, B27 session integrity.

### Policies (6 rules)
`access_control`, `injection_prevention`, `audit_logging`, `pii_handling`, `data_retention`, `external_sharing`. Each declares an enforcement point. Exercises B02 non-LLM layer, B04 deterministic override, B11 system controllability, B23 policy version trace.

### Regulations (2)
Generic placeholder entries. Exercises B25 regulatory readiness — users who want real regulatory coverage should replace these with frameworks actually applicable to their deployment (OWASP LLM Top 10, NIST AI RMF, EU AI Act, ISO 42001, HIPAA, SOX, etc.).

### Test cases (12)
Concrete behavioural scenarios covering the full refuse/comply/clarify surface:
- `read_comply`, `write_comply`, `audit_comply` — positive authorised requests.
- `admin_refuse`, `delete_refuse`, `export_refuse`, `external_refuse`, `permission_change_refuse` — role-based refusals.
- `escalation_refuse`, `injection_refuse`, `off_topic_refuse` — adversarial and off-topic refusals.
- `ambiguous_clarify` — deliberate ambiguity that should surface a clarification request.

Exercises B06 uncertainty signalling, B09 policy violation, B16 silent failure, B17 fact consistency, B19 context accuracy, B20 instruction adherence, B26 rate limiting, B29 prompt sensitivity, B32 off-topic detection.

### Escalation triggers (5), high-risk actions (5), sensitive data classes (5)
Support B10 evaluation drift, B14 covert side task, B18 goal stability, B31 escalation correctness. Each inspection generates N prompts by crossing these lists with roles/tools.

### Primary objective template, system purpose
Exercises B15 long-horizon drift, B21 cross-turn objective, B22 decision reproducibility (which also requires `--sut-temperature 0` or `--sut-seed`).

## If you want to audit coverage for a specific inspection

```python
from ifixai.harness.registry import INSPECTION_REGISTRY
from ifixai.core.fixture_loader import load_fixture

fixture = load_fixture("default")
inspection = INSPECTION_REGISTRY["B01"]
# each inspection declares `spec.min_evidence_items`; running against this fixture
# must produce at least that many evidence items.
```