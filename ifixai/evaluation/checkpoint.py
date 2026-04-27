"""Run-level checkpoint + resume (T025).

A run's state (which tests have finished, with what results) is
written to disk after each test completes. If the user re-invokes
the CLI with the same config + seed + corpus versions, we load the
checkpoint, skip tests that already ran, and execute only the rest.

Checkpoint safety:
- Keyed by `run_id` from the manifest. `run_id` is a SHA-256 over every
  field that would invalidate reproducibility (capabilities, seed, corpus
  versions, scoring_logic_version, model, judges, fixture). Two runs with
  incompatible configs get different `run_id`s, so a stale checkpoint can
  never pollute a fresh run.
- Resume only skips tests whose stored result has
  `is_inconclusive=False` and no `error_message`. Everything else is
  re-executed.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from ifixai.evaluation.manifest import RunManifest
from ifixai.types import TestResult

_logger = logging.getLogger(__name__)


def _checkpoint_path(runs_root: Path, run_id: str) -> Path:
    return runs_root / run_id / "checkpoint.json"


def load_checkpoint(runs_root: Path, run_id: str) -> dict[str, TestResult]:
    """Return {test_id: TestResult} from disk, or {} if none."""
    path = _checkpoint_path(runs_root, run_id)
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        _logger.warning("checkpoint unreadable (%s) — starting fresh", exc)
        return {}
    out: dict[str, TestResult] = {}
    for test_id, payload in raw.items():
        try:
            result = TestResult.model_validate(payload)
        except Exception as exc:
            _logger.warning(
                "checkpoint entry for %s rejected (%s) — will re-run",
                test_id, exc,
            )
            continue
        if result.error_message:
            _logger.info("skipping stale errored result for %s", test_id)
            continue
        out[test_id] = result
    return out


def save_checkpoint(
    runs_root: Path,
    run_id: str,
    results: dict[str, TestResult],
) -> Path:
    """Atomically persist {test_id: TestResult} to disk.

    Writes to a sibling `.tmp` file first, then renames — guarantees the
    checkpoint is never half-written if the process is killed mid-write.
    """
    path = _checkpoint_path(runs_root, run_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    payload = {
        test_id: result.model_dump(mode="json")
        for test_id, result in results.items()
    }
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )
    tmp.replace(path)
    return path


def clear_checkpoint(runs_root: Path, run_id: str) -> bool:
    """Remove the checkpoint for a run. Returns True when a file was deleted."""
    path = _checkpoint_path(runs_root, run_id)
    if not path.exists():
        return False
    path.unlink()
    return True


def checkpoint_path(runs_root: Path, run_id: str) -> Path:
    """Public accessor — used by the CLI and by docs to show the user
    WHERE resume state lives so they can inspect / delete it manually."""
    return _checkpoint_path(runs_root, run_id)


def describe_resume(
    runs_root: Path,
    manifest: RunManifest,
    all_test_ids: list[str],
) -> tuple[dict[str, TestResult], list[str]]:
    """Return (cached_results, tests_still_to_run) for a run.

    Used by the CLI to show the user a clear "X of Y tests already
    have results from a previous run with this exact config; resuming
    from the remaining Z" message before doing any work.
    """
    cached = load_checkpoint(runs_root, manifest.run_id)
    remaining = [b for b in all_test_ids if b not in cached]
    return cached, remaining


class BlockedInspectionError(RuntimeError):
    """Raised by preflight when `--eval-mode self` hits a inspection that forbids
    self-judging (e.g. B07, B10, B12, B14, B30).

    The run is aborted before any test executes. The message includes
    the exact test IDs and how to proceed (pass `--skip <ids>` or
    switch to `--eval-mode semantic/full` with an external judge)."""

    def __init__(self, blocked: list[str]) -> None:
        self.blocked = sorted(blocked)
        super().__init__(
            "The following inspections forbid self-judging because they measure "
            "behaviors the model itself is suspected of exhibiting:\n  "
            + ", ".join(self.blocked)
            + "\n\nTo proceed, either:\n"
              "  1. Switch to an external judge, e.g.:\n"
              "     --eval-mode semantic --judge-provider <provider> "
              "--judge-model <model>\n"
              "  2. Skip these inspections: --skip " + ",".join(self.blocked) + "\n"
              "\nAny tests that already completed in a previous run with "
              "the same config are preserved and will be skipped on resume."
        )


def preflight_eval_mode(
    eval_mode: str,
    inspection_specs: list,  # list[InspectionSpec]
    skip: Optional[list[str]] = None,
) -> None:
    """Raise `BlockedInspectionError` if `--eval-mode self` hits a forbidden inspection.

    This is called BEFORE any test runs so the user doesn't wait
    through half a suite before hitting a blocking inspection. The error
    message tells them exactly how to restart via `--skip` and the
    checkpoint layer preserves any work already done under the same
    `run_id`.
    """
    if eval_mode != "self":
        return
    skip_set = set(skip or [])
    blocked = [
        spec.test_id
        for spec in inspection_specs
        if not spec.self_judge_allowed and spec.test_id not in skip_set
    ]
    if blocked:
        raise BlockedInspectionError(blocked)
