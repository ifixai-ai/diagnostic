

from dataclasses import dataclass, field

import click

from ifixai.discovery import generate_test_cases
from ifixai.types import (
    DataSource,
    Fixture,
    FixtureMetadata,
    Permission,
    Policy,
    Role,
    Tool,
)

RISK_LEVELS = ["low", "medium", "high", "critical"]
TOOL_CATEGORIES = ["read", "write", "delete", "infrastructure", "audit"]

@dataclass
class WizardOutput:

    roles: list[dict[str, str]] = field(default_factory=list)
    tools: list[dict[str, str]] = field(default_factory=list)
    permissions: dict[str, list[str]] = field(default_factory=dict)
    policies: dict[str, str] = field(default_factory=dict)

def run_wizard() -> WizardOutput:
    output = WizardOutput()

    click.echo()
    click.echo(click.style("Full Wizard — Define Your System", bold=True))
    click.echo()

    click.echo(click.style("Step 1/4: Define Roles", bold=True))
    click.echo("Add roles that interact with your AI system.\n")
    while True:
        name = click.prompt("Role name (or 'done' to finish)")
        if name.strip().lower() == "done":
            if not output.roles:
                click.echo(click.style("At least 1 role required.", fg="red"))
                continue
            break
        description = click.prompt("  Description", default="")
        level = click.prompt(
            "  Trust level",
            type=click.Choice(["low", "medium", "high", "admin"], case_sensitive=False),
            default="medium",
        )
        output.roles.append({"name": name.strip(), "description": description, "level": level})
        click.echo(click.style(f"  Added role: {name}", fg="green"))
    click.echo()

    click.echo(click.style("Step 2/4: Define Tools", bold=True))
    click.echo("Add tools/actions available in your system.\n")
    while True:
        name = click.prompt("Tool name (or 'done' to finish)")
        if name.strip().lower() == "done":
            if not output.tools:
                click.echo(click.style("At least 1 tool required.", fg="red"))
                continue
            break
        category = click.prompt(
            "  Category",
            type=click.Choice(TOOL_CATEGORIES, case_sensitive=False),
            default="read",
        )
        risk = click.prompt(
            "  Risk level",
            type=click.Choice(RISK_LEVELS, case_sensitive=False),
            default="medium",
        )
        output.tools.append({"name": name.strip(), "category": category, "risk_level": risk})
        click.echo(click.style(f"  Added tool: {name}", fg="green"))
    click.echo()

    click.echo(click.style("Step 3/4: Define Permission Matrix", bold=True))
    click.echo("For each role, select which tools are allowed.\n")
    tool_names = [t["name"] for t in output.tools]
    for role_info in output.roles:
        role_name = role_info["name"]
        click.echo(f"Role: {click.style(role_name, bold=True)}")
        click.echo(f"  Available tools: {', '.join(tool_names)}")
        allowed_input = click.prompt(
            f"  Allowed tools for '{role_name}' (comma-separated, or 'all')",
            default="all" if "admin" in role_name.lower() else "",
        )
        if allowed_input.strip().lower() == "all":
            output.permissions[role_name] = tool_names[:]
        else:
            output.permissions[role_name] = [
                t.strip() for t in allowed_input.split(",") if t.strip() in tool_names
            ]
        click.echo(click.style(
            f"  {role_name}: {len(output.permissions[role_name])}/{len(tool_names)} tools allowed",
            fg="green",
        ))
    click.echo()

    click.echo(click.style("Step 4/4: Define Policies", bold=True))
    output.policies["escalation"] = click.prompt(
        "Escalation rule (e.g., 'deny and alert on critical tool attempts')",
        default="deny and log",
    )
    output.policies["data_access"] = click.prompt(
        "Data access rule (e.g., 'PII requires admin role')",
        default="enforce role-based data access",
    )
    click.echo()

    return output

def generate_fixture_from_wizard(
    wizard: WizardOutput,
    system_name: str = "My AI Assistant",
) -> Fixture:
    roles = [
        Role(
            name=r["name"],
            role_id=r["name"].lower().replace(" ", "_"),
            description=r.get("description", ""),
            level=r.get("level", "medium"),
        )
        for r in wizard.roles
    ]

    tools = [
        Tool(
            tool_id=t["name"].lower().replace(" ", "_"),
            name=t["name"],
            category=t.get("category", "read"),
            risk_level=t.get("risk_level", "medium"),
            description=f"Tool: {t['name']}",
        )
        for t in wizard.tools
    ]

    permissions = [
        Permission(
            role=role_name,
            tools=[
                t.lower().replace(" ", "_") for t in allowed_tools
            ],
        )
        for role_name, allowed_tools in wizard.permissions.items()
    ]

    test_cases = generate_test_cases(roles, permissions, tools)

    override_roles = [
        r["name"] for r in wizard.roles
        if r.get("level") in ("high", "admin")
    ]

    return Fixture(
        metadata=FixtureMetadata(
            name=system_name,
            version="1.0",
            domain="custom",
            description="Generated by ifixai Full Wizard",
        ),
        roles=roles,
        tools=tools,
        permissions=permissions,
        data_sources=[
            DataSource(
                source_id="knowledge_base",
                name="Knowledge Base",
                classification="internal",
            ),
        ],
        policies=Policy(
            override_allowed_roles=override_roles,
        ),
        test_cases=test_cases,
    )
