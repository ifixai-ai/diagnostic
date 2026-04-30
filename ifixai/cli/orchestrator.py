import os
import sys
import threading
from collections import Counter

import click

from ifixai.api import run_inspections, run_single, run_strategic
from ifixai.core.concurrency import ConcurrencyGovernor
from ifixai.core.fixture_loader import load_fixture
from ifixai.harness.registry import ALL_SPECS, SPEC_BY_ID
from ifixai.judge.config import JudgeConfig, JudgeProviderSpec
from ifixai.providers.resolver import (
    _PROVIDER_CREDENTIAL_ENV_VARS,
    detect_available_credentials,
    select_cross_provider_judge,
)
from ifixai.scoring.category_weights import STRATEGIC_TEST_IDS
from ifixai.core.types import (
    TestResult,
    TestRunResult,
    EvaluationMethod,
    EvaluationPipelineConfig,
    InspectionCategory,
)


def _lookup_env_api_key(provider_name: str) -> str | None:
    env_vars = _PROVIDER_CREDENTIAL_ENV_VARS.get(provider_name.lower(), ())
    for var in env_vars:
        value = os.environ.get(var)
        if value:
            return value
    return None


def _resolve_standard_eval_mode(
    sut_provider: str | None,
    judge_provider: tuple[str, ...],
    sut_api_key: str | None = None,
) -> tuple[str, str | None]:
    if judge_provider:
        return "semantic", None
    sut_name = (sut_provider or "").lower()
    available = detect_available_credentials(os.environ)
    if sut_name and sut_name not in available and sut_api_key:
        available = [sut_name] + available
    distinct = [p for p in available if p != sut_name]
    if distinct:
        chosen = select_cross_provider_judge(sut_name, available)
        if chosen is not None:
            return "semantic", chosen
    if not available:
        click.echo(
            click.style(
                "Error: no provider credentials found in the environment.\n"
                "Set at least one of OPENAI_API_KEY, ANTHROPIC_API_KEY, "
                "GEMINI_API_KEY, AZURE_OPENAI_API_KEY, OPENROUTER_API_KEY, "
                "HUGGINGFACE_API_TOKEN, or AWS credentials (for bedrock).",
                fg="red",
            ),
            err=True,
        )
        sys.exit(2)
    click.echo(
        click.style(
            "Error: Standard mode needs a second distinct-provider credential to "
            "avoid self-judge. Either set a second provider key (e.g. "
            "ANTHROPIC_API_KEY alongside OPENAI_API_KEY), or pass --eval-mode self "
            "to opt into the biased self-judge path explicitly.",
            fg="red",
        ),
        err=True,
    )
    sys.exit(2)


def _resolve_judge_label(eval_mode: str, judge_provider: tuple[str, ...]) -> str:
    if eval_mode == "self":
        return "self"
    if eval_mode == "deterministic":
        return "(none)"
    if len(judge_provider) >= 2:
        return f"ensemble({len(judge_provider)})"
    if len(judge_provider) == 1:
        return judge_provider[0]
    return "(unconfigured)"


def _eval_mode_declaration(
    eval_mode: str,
    sut_provider: str | None,
    judge_providers: tuple[str, ...],
    judge_models: tuple[str, ...],
) -> str:
    if eval_mode == "self":
        return (
            "Evaluation mode: self "
            f"(system-under-test '{sut_provider}' acts as its own judge -- "
            "Standard mode default)"
        )
    if eval_mode == "deterministic":
        return (
            "Evaluation mode: deterministic "
            "(structural inspections only -- text-fallback tests will be inconclusive)"
        )
    if eval_mode == "semantic":
        judge_id = judge_providers[0] if judge_providers else "(none)"
        model = f"/{judge_models[0]}" if judge_models else ""
        return f"Evaluation mode: semantic (judge: {judge_id}{model})"
    if eval_mode == "full":
        judges = "+".join(judge_providers) if judge_providers else "(none)"
        return f"Evaluation mode: full (ensemble: {judges})"
    return f"Evaluation mode: {eval_mode}"


def _build_judge_config(
    eval_mode: str,
    sut_provider: str | None,
    sut_api_key: str,
    sut_model: str | None,
    judge_providers: tuple[str, ...],
    judge_api_keys: tuple[str, ...],
    judge_models: tuple[str, ...],
    max_calls: int,
    timeout: int,
) -> JudgeConfig | None:
    if eval_mode == "deterministic":
        return None
    if eval_mode == "self":
        return JudgeConfig(
            provider=sut_provider or "",
            api_key=sut_api_key,
            model=sut_model,
            max_calls_per_run=max_calls,
            timeout=timeout,
        )
    if eval_mode in ("single", "semantic"):
        return JudgeConfig(
            provider=judge_providers[0],
            api_key=judge_api_keys[0] if judge_api_keys else "",
            model=judge_models[0] if judge_models else None,
            max_calls_per_run=max_calls,
            timeout=timeout,
        )
    if eval_mode == "full":
        specs = [
            JudgeProviderSpec(
                provider=p,
                api_key=judge_api_keys[i] if i < len(judge_api_keys) else "",
                model=judge_models[i] if i < len(judge_models) else None,
            )
            for i, p in enumerate(judge_providers)
        ]
        return JudgeConfig(
            providers=specs,
            max_calls_per_run=max_calls,
            timeout=timeout,
        )
    return None


def _print_inconclusive_summary(result: TestRunResult) -> None:
    inconclusive_count = 0
    inconclusive_tests: set[str] = set()
    by_category: Counter[str] = Counter()

    for br in result.test_results:
        for evidence in br.evidence:
            if evidence.evaluation_method == EvaluationMethod.JUDGE:
                inconclusive_count += 1
                inconclusive_tests.add(br.test_id)
                by_category[br.category.value] += 1

    if inconclusive_count == 0:
        click.echo(click.style("Inconclusive: 0 evidence items.", fg="green"))
    else:
        breakdown = ", ".join(f"{cat}={n}" for cat, n in by_category.most_common())
        click.echo(
            click.style(
                f"Inconclusive: {inconclusive_count} evidence items across "
                f"{len(inconclusive_tests)} tests ({breakdown})",
                fg="yellow",
            )
        )


def _print_insufficient_evidence_summary(result: TestRunResult) -> None:
    insufficient = [br for br in result.test_results if br.insufficient_evidence]
    total = len(result.test_results)
    if not insufficient:
        click.echo(
            click.style(
                f"All {total} tests produced sufficient evidence to be scored.",
                fg="green",
            )
        )
        return
    inspection_ids = ", ".join(sorted(br.test_id for br in insufficient))
    click.echo(
        click.style(
            f"{len(insufficient)} out of {total} tests had insufficient evidence "
            f"to be scored ({inspection_ids}). The remaining tests were scored but "
            f"may still be below threshold -- see the per-category bars above. "
            f"Wrap your provider in a governance layer or run with ≥2 provider "
            f"credentials. See docs/methodology.md.",
            fg="yellow",
        )
    )


_CATEGORY_BAR_COLOR: dict[str, str] = {
    InspectionCategory.FABRICATION.value:      "\033[91m",  # bright red
    InspectionCategory.MANIPULATION.value:     "\033[91m",  # bright red
    InspectionCategory.DECEPTION.value:        "\033[95m",  # bright magenta
    InspectionCategory.UNPREDICTABILITY.value: "\033[93m",  # bright yellow
    InspectionCategory.OPACITY.value:          "\033[94m",  # bright blue
}
_RESET  = "\033[0m"
_RED    = "\033[91m"
_GREEN  = "\033[92m"
_YELLOW = "\033[93m"
_DIM    = "\033[2m"
_BOLD   = "\033[1m"
_SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]


class BenchmarkProgressDisplay:
    """Live animated display: pre-prints all benchmarks then updates in-place."""

    def __init__(self, tests: list[tuple[str, str]]) -> None:
        self._tests = tests  # [(test_id, name), ...]
        self._results: dict[str, TestResult] = {}
        self._frame_idx = 0
        self._lock = threading.Lock()
        self._done = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        for test_id, name in self._tests:
            sys.stdout.write(f"  {_YELLOW}⠋{_RESET} {_DIM}{test_id}{_RESET} {name}\n")
        sys.stdout.flush()
        self._thread = threading.Thread(target=self._animate, daemon=True)
        self._thread.start()

    def update(self, test_id: str, index: int, total: int, result: TestResult) -> None:
        with self._lock:
            self._results[test_id] = result

    def stop(self) -> None:
        self._done.set()
        if self._thread:
            self._thread.join(timeout=2.0)
        self._redraw(final=True)

    def _animate(self) -> None:
        while not self._done.wait(timeout=0.1):
            self._frame_idx = (self._frame_idx + 1) % len(_SPINNER_FRAMES)
            self._redraw()

    def _build_lines(self, final: bool = False) -> list[str]:
        lines: list[str] = []
        with self._lock:
            frame = _SPINNER_FRAMES[self._frame_idx]
            for test_id, name in self._tests:
                if test_id in self._results:
                    result = self._results[test_id]
                    if result.passing:
                        icon   = f"{_GREEN}✓{_RESET}"
                        status = f"{_GREEN}PASS{_RESET}"
                    else:
                        icon   = f"{_RED}✗{_RESET}"
                        status = f"{_RED}FAIL{_RESET}"
                    lines.append(
                        f"  {icon} {_BOLD}{test_id}{_RESET} {name} "
                        f"... {status} ({result.score:.0%})"
                    )
                else:
                    spinner = "·" if final else frame
                    lines.append(
                        f"  {_YELLOW}{spinner}{_RESET} {_DIM}{test_id}{_RESET} {name}"
                    )
        return lines

    def _redraw(self, final: bool = False) -> None:
        n = len(self._tests)
        if n == 0:
            return
        lines = self._build_lines(final=final)
        sys.stdout.write(f"\033[{n}A")
        for line in lines:
            sys.stdout.write(f"\r\033[K{line}\n")
        sys.stdout.flush()


def _print_category_summary(result: TestRunResult) -> None:
    if not result.category_scores:
        return
    bar_width = 22
    click.echo()
    for cs in result.category_scores:
        color = _CATEGORY_BAR_COLOR.get(cs.category.value, "\033[96m")
        bar = color + ("█" * bar_width) + _RESET
        failed = cs.test_count - cs.tests_passed
        count_str = f"{cs.test_count}/{cs.test_count}"
        if cs.test_count == 0:
            fail_str = f"{_DIM}— no scored tests{_RESET}"
        elif failed > 0:
            fail_str = f"{_RED}× {failed} failed{_RESET}"
        else:
            fail_str = f"{_GREEN}✓ all passed{_RESET}"
        name = cs.category.value.ljust(16)
        click.echo(f"  {name} [{bar}]  {count_str:>5}  {fail_str}")
    click.echo()


def _progress_callback_plain(
    bid: str,
    index: int,
    total: int,
    bench_result: TestResult,
) -> None:
    """Fallback used when stdout is not a TTY (e.g. piped/redirected)."""
    status_label = (
        click.style("PASS", fg="green")
        if bench_result.passing
        else click.style("FAIL", fg="red")
    )
    click.echo(
        f"  [{index}/{total}] {bid} {bench_result.name} ... "
        f"{status_label} ({bench_result.score:.0%})"
    )


def _build_display_tests(
    strategic: bool,
    test_id: str | None,
) -> list[tuple[str, str]]:
    if test_id:
        uid = test_id.upper()
        spec = SPEC_BY_ID.get(uid)
        return [(uid, spec.name if spec else uid)]  # type: ignore[union-attr]
    if strategic:
        strategic_set = set(STRATEGIC_TEST_IDS)
        return [(s.test_id, s.name) for s in ALL_SPECS if s.test_id in strategic_set]
    return [(s.test_id, s.name) for s in ALL_SPECS]


async def execute_tests(
    provider: str,
    api_key: str,
    fixture: str,
    endpoint: str | None,
    model: str | None,
    system_prompt: str | None,
    strategic: bool,
    test_id: str | None,
    timeout: int,
    system_name: str,
    system_version: str,
    pipeline_config: EvaluationPipelineConfig | None = None,
    judge_config: JudgeConfig | None = None,
    governor: ConcurrencyGovernor | None = None,
    sut_temperature: float = 0.0,
    sut_seed: int | None = None,
    self_judged: bool = False,
    progress_callback=None,
) -> TestRunResult | None:

    try:
        loaded_fixture = load_fixture(fixture)
    except FileNotFoundError as exc:
        click.echo(click.style(f"Fixture error: {exc}", fg="red"))
        return None

    use_display = progress_callback is None and sys.stdout.isatty()
    display: BenchmarkProgressDisplay | None = None

    if use_display:
        display = BenchmarkProgressDisplay(_build_display_tests(strategic, test_id))
        display.start()
        effective_callback = display.update
    else:
        effective_callback = progress_callback or _progress_callback_plain

    try:
        if test_id:
            single_result = await run_single(
                test_id=test_id,
                provider=provider,
                api_key=api_key,
                fixture=fixture,
                endpoint=endpoint,
                model=model,
                system_prompt=system_prompt,
                timeout=timeout,
                pipeline_config=pipeline_config,
                judge_config=judge_config,
                sut_temperature=sut_temperature,
                sut_seed=sut_seed,
            )
            if display:
                display.update(test_id, 1, 1, single_result)
            else:
                status_label = (
                    click.style("PASS", fg="green")
                    if single_result.passing
                    else click.style("FAIL", fg="red")
                )
                click.echo(
                    f"  [1/1] {test_id} {single_result.name} ... "
                    f"{status_label} ({single_result.score:.0%})"
                )
            return TestRunResult(
                system_name=system_name,
                system_version=system_version,
                provider=provider,
                fixture_name=loaded_fixture.metadata.name,
                overall_score=single_result.score,
                strategic_score=single_result.score,
                test_results=[single_result],
                run_mode="single",
            )

        if strategic:
            strategic_result = await run_strategic(
                provider=provider,
                api_key=api_key,
                fixture=fixture,
                system_name=system_name,
                system_version=system_version,
                endpoint=endpoint,
                model=model,
                system_prompt=system_prompt,
                timeout=timeout,
                progress_callback=effective_callback,
                pipeline_config=pipeline_config,
                judge_config=judge_config,
                governor=governor,
                sut_temperature=sut_temperature,
                sut_seed=sut_seed,
            )
            strategic_result.self_judged = self_judged
            return strategic_result

        inspections_result = await run_inspections(
            provider=provider,
            api_key=api_key,
            fixture=fixture,
            system_name=system_name,
            system_version=system_version,
            endpoint=endpoint,
            model=model,
            system_prompt=system_prompt,
            timeout=timeout,
            progress_callback=effective_callback,
            pipeline_config=pipeline_config,
            judge_config=judge_config,
            governor=governor,
            sut_temperature=sut_temperature,
            sut_seed=sut_seed,
        )
        inspections_result.self_judged = self_judged
        return inspections_result

    except Exception as exc:
        click.echo(click.style(f"Test execution failed: {exc}", fg="red"))
        return None

    finally:
        if display:
            display.stop()
