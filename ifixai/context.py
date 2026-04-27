

import click

from ifixai.types import ContextProfile, IndustryContext, UseCase

INDUSTRY_OPTIONS: dict[str, IndustryContext] = {
    "1": IndustryContext(
        name="Healthcare",
        id="healthcare",
        regulations=["HIPAA", "FDA", "HITECH"],
        risks=["patient_data_exposure", "misdiagnosis", "treatment_recommendation"],
    ),
    "2": IndustryContext(
        name="Financial Services",
        id="financial",
        regulations=["SEC", "MiFID II", "PCI-DSS", "SOX"],
        risks=["unauthorized_transactions", "data_leakage", "market_manipulation"],
    ),
    "3": IndustryContext(
        name="Legal",
        id="legal",
        regulations=["Bar Association", "AML", "Data Protection"],
        risks=["privilege_breach", "misrepresentation", "unauthorized_advice"],
    ),
    "4": IndustryContext(
        name="Government",
        id="government",
        regulations=["FedRAMP", "FISMA", "NIST"],
        risks=["classified_data_exposure", "policy_violation", "unauthorized_access"],
    ),
    "5": IndustryContext(
        name="Enterprise / Tech",
        id="enterprise",
        regulations=["SOC2", "GDPR", "CCPA"],
        risks=["ip_leakage", "access_control_bypass", "data_breach"],
    ),
    "6": IndustryContext(
        name="Other / General",
        id="other",
        regulations=["GDPR", "SOC2"],
        risks=["data_leakage", "unauthorized_access"],
    ),
}

USE_CASE_OPTIONS: dict[str, UseCase] = {
    "1": UseCase(
        name="Customer-facing chatbot",
        id="chatbot",
        inspection_focus=["injection", "hallucination", "data_leakage"],
    ),
    "2": UseCase(
        name="Internal copilot",
        id="copilot",
        inspection_focus=["access_control", "role_enforcement", "audit"],
    ),
    "3": UseCase(
        name="RAG pipeline",
        id="rag",
        inspection_focus=["provenance", "citation", "data_access_control"],
    ),
    "4": UseCase(
        name="Autonomous agent",
        id="agent",
        inspection_focus=["tool_governance", "escalation", "containment"],
    ),
    "5": UseCase(
        name="Data analysis",
        id="data_analysis",
        inspection_focus=["output_accuracy", "source_attribution"],
    ),
    "6": UseCase(
        name="Code generation",
        id="code_generation",
        inspection_focus=["code_injection", "deployment_controls"],
    ),
}

SENSITIVE_DATA_OPTIONS = ["pii", "financial", "health", "legal", "ip"]

def collect_context(system_name: str = "", system_version: str = "1.0") -> ContextProfile:
    click.echo()
    click.echo(click.style("Step 2 — Context Gathering", bold=True))
    click.echo("Quick questions so ifixai sends the right test scenarios.\n")

    click.echo("Industry context:")
    for key, ctx in INDUSTRY_OPTIONS.items():
        click.echo(f"  [{key}] {ctx.name}")
    industry_choice = click.prompt("Select industry", default="6")
    industry = INDUSTRY_OPTIONS.get(industry_choice, INDUSTRY_OPTIONS["6"])

    click.echo("\nUse case type:")
    for key, uc in USE_CASE_OPTIONS.items():
        click.echo(f"  [{key}] {uc.name}")
    use_case_choice = click.prompt("Select use case", default="1")
    use_case = USE_CASE_OPTIONS.get(use_case_choice, USE_CASE_OPTIONS["1"])

    click.echo(f"\nSensitive data types (available: {', '.join(SENSITIVE_DATA_OPTIONS)}):")
    sensitive_input = click.prompt(
        "Select (comma-separated, or 'none')",
        default="none",
    )
    if sensitive_input.strip().lower() == "none":
        sensitive_data: list[str] = []
    else:
        sensitive_data = [
            s.strip().lower()
            for s in sensitive_input.split(",")
            if s.strip().lower() in SENSITIVE_DATA_OPTIONS
        ]

    roles_input = click.prompt(
        "\nUser roles in your system (comma-separated, min 1)",
        default="user,admin",
    )
    user_types = [r.strip() for r in roles_input.split(",") if r.strip()]
    while not user_types:
        click.echo(click.style("At least 1 role required.", fg="red"))
        roles_input = click.prompt("Roles (comma-separated)")
        user_types = [r.strip() for r in roles_input.split(",") if r.strip()]

    actions_input = click.prompt(
        "\nActions/tools your AI can perform (comma-separated, min 1)",
    )
    actions = [a.strip() for a in actions_input.split(",") if a.strip()]
    while not actions:
        click.echo(click.style("At least 1 action required.", fg="red"))
        actions_input = click.prompt("Actions (comma-separated)")
        actions = [a.strip() for a in actions_input.split(",") if a.strip()]

    if not system_name:
        system_name = click.prompt("\nSystem name", default="My AI Assistant")

    return ContextProfile(
        industry=industry,
        use_case=use_case,
        system_name=system_name,
        system_version=system_version,
        user_types=user_types,
        actions=actions,
        sensitive_data=sensitive_data,
    )
