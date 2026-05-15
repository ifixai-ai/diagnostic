# Evaluating autonomous agent runtimes

This guide shows how to use iFixAi for general-purpose agent runtimes: systems
that can call tools, retrieve memory/RAG context, update durable state, or
trigger external side effects.

The goal is not to certify that an agent is "safe" in the abstract. The goal is
to turn vague runtime risks into repeatable fixtures that can be run before
increasing autonomy, enabling new tools, or shipping a runtime change.

## Why agent runtimes need a dedicated fixture

A chat model and an agent runtime fail differently.

A plain model can hallucinate or refuse incorrectly. An agent runtime can also:

- treat retrieved memory as an instruction;
- escalate privileges through tool calls;
- leak context across users, sessions, tenants, or agent profiles;
- claim a task is complete without audit evidence;
- trigger external/public/economic actions without approval;
- confuse a generated human-facing mirror with the source of truth;
- lose provenance when summarizing retrieved state.

Those risks map especially well to these iFixAi inspections:

- **B03 Auditability Coverage** — completion must leave evidence.
- **B05 Source Provenance Coverage** — retrieved facts need source/freshness.
- **B08 Privilege Escalation Detection** — high-risk tools need authorization.
- **B12 Prompt Injection Blocking** — retrieved text cannot override policy.
- **B27 In-Context Session Isolation** — private context must not cross users.
- **B28 RAG Context Integrity** — facts and embedded instructions must be separated.
- **B31 Escalation Correctness** — risky actions need routing and audit chain.

## Included example fixture

The repository includes an illustrative fixture:

```bash
ifixai validate ifixai/fixtures/examples/agent_runtime_assistant.yaml
```

Run it against a provider in the same way as other fixtures:

```bash
ifixai run \
  --provider mock \
  --api-key not-used \
  --eval-mode self \
  --fixture ifixai/fixtures/examples/agent_runtime_assistant.yaml
```

For a real agent endpoint, use the provider wiring that matches your runtime.
The fixture is intentionally vendor-neutral: it models roles, tools, approvals,
RAG/memory sources, sensitive data classes, and escalation triggers rather than
any one company's internal operating model.

## Interpreting results

Do not treat one scorecard as a certificate.

A useful agent-runtime scorecard should answer:

1. Which high-risk actions were blocked without explicit approval?
2. Did retrieved memory/RAG context preserve provenance?
3. Did the agent ignore embedded instructions inside retrieved content?
4. Did completion claims include auditable evidence?
5. Did private session/user context remain isolated?
6. Did escalation decisions identify the approver path and rule applied?

A low score usually means one of two things:

- the runtime lacks a deterministic governance layer; or
- the fixture does not yet expose the runtime's actual governance hooks.

Both are actionable, but they are different. Fix the runtime when behavior is
unsafe; fix the fixture/provider wiring when iFixAi lacks enough evidence.

## Recommended adoption loop

1. Start from `ifixai/fixtures/examples/agent_runtime_assistant.yaml`.
2. Rename roles, tools, data sources, and approval paths to match your runtime.
3. Add high-risk actions that your agent can actually perform.
4. Add prompt-injection and retrieved-memory cases from your real environment.
5. Run iFixAi before enabling new tools or increasing autonomy.
6. Convert every failure into one of:
   - a runtime guardrail change;
   - a provider/governance hook improvement;
   - a fixture correction;
   - a documented acceptance of residual risk.
7. Re-run and store the scorecard as release evidence.

## Minimum bar before increasing autonomy

Before an agent receives broader permissions, it should demonstrate:

- no high-risk tool call without approval;
- no retrieved-memory instruction execution;
- no cross-session private data disclosure;
- no completion claim without audit evidence;
- source/freshness visible for retrieved facts;
- explicit escalation for public, economic, legal, credential, deployment, or
  irreversible actions.

## Fixture design notes

The example fixture uses:

- `roles` to separate normal users, approvers, operators, and untrusted external
  requesters;
- `tools` to classify read, write, infrastructure, and credential/deployment
  capabilities;
- `permissions` and `governance.policies.authorization` to model who may call
  which tools;
- `high_risk_actions` and `escalation_triggers` to drive risk and escalation
  inspections;
- `sensitive_data_classes` to make session-isolation and policy-violation tests
  concrete;
- `seed_audit_records` so policy-version and auditability checks have stable
  evidence independent of run order.

Keep fixtures concrete. "Act safely" is too vague; "do not deploy production
changes without an approver artifact" is testable.
