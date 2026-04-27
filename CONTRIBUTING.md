# Contributing to ifixai

Thanks for considering a contribution. This guide covers the mechanics of adding inspections, fixtures, providers, and running the test suite. For the behavioural contract (what the project expects from the code you write), see the root `CLAUDE.md` if it exists plus `.claude/rules/common/*.md` in the repository.

## Environment setup

```bash
git clone <your-fork-url> ifixai
cd ifixai
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pre-commit install
```

The `pre-commit install` step wires up local hooks (`gitleaks`, `ruff`, a `.env` guard, and a sanitizer regex for known-internal identifiers). Run them on demand with `pre-commit run --all-files`.

Verify:

```bash
ruff check ifixai tests
python -m pytest --cov=ifixai --cov-report=term
```

The coverage floor is declared in `.github/workflows/ci.yml`. The policy is simple: the floor is pinned at `floor(current_baseline) - 2` percentage points so a flaky test cannot accidentally erode coverage, and is ratcheted upward when a sustained improvement lands. Drop-below fails CI.

## Adding a test (inspection)

Each inspection is one file under `ifixai/tests/bNN_short_name.py`. The minimum contract:

1. Declare the `SPEC` — a `InspectionSpec` instance with `test_id`, `name`, `category` (one of the five `InspectionCategory` values), `description`, `threshold`, `weight`, `scoring_method`, and optional `is_strategic` / `is_mandatory_minimum` flags.
2. Implement a subclass of `BaseTest` (from `ifixai.tests.base`). Override `run()` to produce a list of `EvidenceItem`s. Use `self.pipeline.evaluate(...)` to get a pass/fail from the configured judge.
3. Declare `required_fixture_keys: frozenset[str]` on the subclass listing every fixture key the inspection's templates reference. The fixture loader validates this at load time; inspections that reference keys the fixture doesn't provide fail fast with an actionable error.
4. Render every prompt through `ifixai.utils.template_renderer.render(template, context)`. Direct `str.format(...)` or f-string interpolation on fixture values is forbidden — it silently leaks `{placeholder}` literals to the model when a key is missing.
5. Register the inspection in `ifixai/tests/registry.py` (import + add to `ALL_SPECS` + `create_inspection` switch).
6. Update `ifixai/scoring/category_weights.py` only if the inspection belongs to the strategic set.

### Inspection testing

Every inspection should have a companion test under `tests/test_bNN_*.py` covering at least:

- `test_{inspection}_spec_invariants_unchanged` — asserts immutable fields (id, category, threshold, weight, strategic-ness).
- Happy-path evidence generation against a fixture.
- Failure path (provider error, empty response, malformed output).

## Authoring a fixture

Fixtures are YAML files under `ifixai/fixtures/`. Validate against `ifixai/fixtures/schema.json`. A fixture MUST supply every key listed in the union of every registered inspection's `required_fixture_keys`.

The `x-placeholders` section of the schema (lint-only) enumerates the placeholder keys any inspection may reference. Keep it in sync when you add a inspection that references a new key.

Three example fixtures live under `ifixai/fixtures/examples/`. Copy one as a starting point.

## Registering a new provider

Providers implement the `ChatProvider` protocol from `ifixai/providers/base.py`. Steps:

1. Create `ifixai/providers/<your_provider>.py` implementing at minimum `send_message` — other capability methods may raise `NotImplementedError` if the provider does not expose them.
2. Register the provider string in `ifixai/providers/resolver.py`.
3. Add an optional dependency extra in `pyproject.toml` under `[project.optional-dependencies]` so users install only what they need.
4. Do not swallow exceptions silently. If the provider has idiomatic error types, translate them into `ProviderError` (or a subclass).
5. Add `tests/test_<your_provider>.py` with stub / mock coverage.

## Running tests locally

```bash
# full suite
python -m pytest

# one module
python -m pytest tests/test_your_thing.py

# with coverage
python -m pytest --cov=ifixai --cov-report=term-missing

# ruff
ruff check ifixai tests

# type check
mypy ifixai

# security scan
bandit -r ifixai -ll
```

## Commit conventions

Follow the Conventional Commits-style prefixes used by this project:

- `feat:` new user-visible feature
- `fix:` bug fix
- `refactor:` behaviour-preserving change
- `docs:` documentation only
- `test:` test-only changes
- `chore:` tooling / housekeeping
- `perf:` performance improvement
- `ci:` CI configuration

Keep commits small and atomic. Include a test with every `fix:` or `feat:` that changes observable behaviour.

## Pull requests

- Target branch: `main`.
- Include a test plan in the PR body.
- Confirm `ruff`, `pytest`, and `bandit` all pass locally before requesting review. `mypy` is advisory (run it locally if you touched typed surfaces, but it is not a CI gate).
- For any inspection / fixture / provider change, paste one worked example scorecard snippet (JSON or Markdown) into the PR body. The `ifixai-results/` directory is gitignored and cannot be updated as part of a PR.

## Where to ask

Open a GitHub issue on the repository for questions, bug reports, or feature proposals. For security-sensitive reports see `SECURITY.md`.
