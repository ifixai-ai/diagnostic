
from ifixai._version import VERSION as __version__  # noqa: F401
from ifixai.tests.registry import ALL_SPECS
from ifixai.concurrency import ConcurrencyGovernor
from ifixai.fixture_loader import list_fixture_names, load_fixture
from ifixai.judge.config import JudgeConfig
from ifixai.providers.base import ChatProvider
from ifixai.providers.resolver import resolve_provider
from ifixai.reporting.comparison import compare_scorecards as _compare_scorecards
from ifixai.runner import run_all, run_single as _run_single, run_strategic as _run_strategic
from ifixai.types import (
    TestResult,
    InspectionSpec,
    ComparisonReport,
    EvaluationPipelineConfig,
    Fixture,
    ProviderConfig,
    TestRunResult,
)


def _resolve_fixture(fixture: str | Fixture) -> Fixture:
    if isinstance(fixture, Fixture):
        return fixture
    return load_fixture(fixture)


def _build_config(
    provider: str | ChatProvider,
    api_key: str,
    endpoint: str | None,
    model: str | None,
    system_prompt: str | None,
    timeout: int,
    max_retries: int,
    temperature: float = 0.0,
    seed: int | None = None,
) -> ProviderConfig:
    return ProviderConfig(
        provider=provider if isinstance(provider, str) else "custom",
        endpoint=endpoint,
        api_key=api_key,
        model=model,
        system_prompt=system_prompt,
        timeout=timeout,
        max_retries=max_retries,
        temperature=temperature,
        seed=seed,
    )


async def run_inspections(
    provider: str | ChatProvider,
    fixture: str | Fixture = "default",
    api_key: str = "",
    system_name: str = "",
    system_version: str = "1.0",
    endpoint: str | None = None,
    model: str | None = None,
    system_prompt: str | None = None,
    timeout: int = 30,
    max_retries: int = 3,
    progress_callback: object = None,
    pipeline_config: EvaluationPipelineConfig | None = None,
    judge_config: JudgeConfig | None = None,
    governor: "ConcurrencyGovernor | None" = None,
    sut_temperature: float = 0.0,
    sut_seed: int | None = None,
) -> TestRunResult:
    return await run_all(
        provider=resolve_provider(provider),
        config=_build_config(provider, api_key, endpoint, model, system_prompt, timeout, max_retries, sut_temperature, sut_seed),
        fixture=_resolve_fixture(fixture),
        system_name=system_name,
        system_version=system_version,
        progress_callback=progress_callback,
        judge_config=judge_config,
        pipeline_config=pipeline_config,
        governor=governor,
    )


async def run_strategic(
    provider: str | ChatProvider,
    fixture: str | Fixture = "default",
    api_key: str = "",
    system_name: str = "",
    system_version: str = "1.0",
    endpoint: str | None = None,
    model: str | None = None,
    system_prompt: str | None = None,
    timeout: int = 30,
    max_retries: int = 3,
    progress_callback: object = None,
    pipeline_config: EvaluationPipelineConfig | None = None,
    judge_config: JudgeConfig | None = None,
    governor: "ConcurrencyGovernor | None" = None,
    sut_temperature: float = 0.0,
    sut_seed: int | None = None,
) -> TestRunResult:
    return await _run_strategic(
        provider=resolve_provider(provider),
        config=_build_config(provider, api_key, endpoint, model, system_prompt, timeout, max_retries, sut_temperature, sut_seed),
        fixture=_resolve_fixture(fixture),
        system_name=system_name,
        system_version=system_version,
        progress_callback=progress_callback,
        judge_config=judge_config,
        pipeline_config=pipeline_config,
        governor=governor,
    )


async def run_single(
    test_id: str,
    provider: str | ChatProvider,
    fixture: str | Fixture = "default",
    api_key: str = "",
    endpoint: str | None = None,
    model: str | None = None,
    system_prompt: str | None = None,
    timeout: int = 30,
    max_retries: int = 3,
    pipeline_config: EvaluationPipelineConfig | None = None,
    judge_config: JudgeConfig | None = None,
    sut_temperature: float = 0.0,
    sut_seed: int | None = None,
) -> TestResult:
    return await _run_single(
        test_id=test_id,
        provider=resolve_provider(provider),
        config=_build_config(provider, api_key, endpoint, model, system_prompt, timeout, max_retries, sut_temperature, sut_seed),
        fixture=_resolve_fixture(fixture),
        judge_config=judge_config,
        pipeline_config=pipeline_config,
    )


def compare_scorecards(baseline: TestRunResult, enhanced: TestRunResult) -> ComparisonReport:
    return _compare_scorecards(baseline, enhanced)


def list_tests() -> list[InspectionSpec]:
    return list(ALL_SPECS)


def list_fixtures() -> list[str]:
    return list_fixture_names()
