from pathlib import Path

from ifixai.core.fixture_loader import load_fixture, validate_fixture


AGENT_RUNTIME_FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "ifixai"
    / "fixtures"
    / "examples"
    / "agent_runtime_assistant.yaml"
)


def test_agent_runtime_fixture_is_valid_and_loadable() -> None:
    assert validate_fixture(AGENT_RUNTIME_FIXTURE) == []

    fixture = load_fixture(AGENT_RUNTIME_FIXTURE)

    assert fixture.metadata.domain == "agent_runtime"
    assert fixture.system_purpose
    assert "execute irreversible external actions" in fixture.high_risk_actions
    assert "retrieved_memory_or_tool_output" in fixture.sensitive_data_classes
    assert fixture.governance is not None


def test_agent_runtime_fixture_targets_core_agent_risks() -> None:
    fixture = load_fixture(AGENT_RUNTIME_FIXTURE)
    covered = {case.test.removeprefix("SSCI-") for case in fixture.test_cases}

    assert {
        "B03",  # auditability
        "B05",  # source provenance
        "B08",  # privilege escalation
        "B12",  # prompt injection
        "B27",  # session isolation
        "B28",  # RAG/context integrity
        "B31",  # escalation correctness
    }.issubset(covered)
