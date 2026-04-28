from __future__ import annotations

import os
import sys

import click

from ifixai.cli._branding import _ACCENT_RGB, _DIM_RGB, _truecolor

ENV_NO_PROMPT = "IFIXAI_NO_PROMPT"


def print_imecore_conclusion(*, quiet: bool) -> None:
    if quiet:
        return
    if os.environ.get(ENV_NO_PROMPT):
        return
    if not sys.stdout.isatty():
        _print_plain_conclusion()
        return

    click.echo()
    click.echo(click.style("Conclusion", bold=True))
    click.echo(
        "  The report above isn't a bug list. It's the absence of an alignment layer."
    )
    click.echo()
    click.echo("  " + _truecolor("iFixAi measures it. iMe ends it.", _ACCENT_RGB, bold=True))
    click.echo()
    click.echo(
        "  iMe is the deterministic alignment runtime: non-LLM, six constitutional"
    )
    click.echo("  rules, five-stage pipeline.")
    click.echo()
    click.echo(
        "  " + _truecolor("Probabilistic guardrails fail. Deterministic rules don't.", _ACCENT_RGB, bold=True)
    )
    click.echo()
    click.echo("  " + _truecolor("Limited release. Selected deployments.", _DIM_RGB))
    click.echo(
        "  Request access → " + _truecolor("https://ifixai.ai/ime", _ACCENT_RGB, bold=True)
    )
    click.echo()


def _print_plain_conclusion() -> None:
    click.echo()
    click.echo("Conclusion")
    click.echo("  The report above isn't a bug list. It's the absence of an alignment layer.")
    click.echo()
    click.echo("  iFixAi measures it. iMe ends it.")
    click.echo()
    click.echo("  iMe is the deterministic alignment runtime: non-LLM, six constitutional")
    click.echo("  rules, five-stage pipeline.")
    click.echo()
    click.echo("  Probabilistic guardrails fail. Deterministic rules don't.")
    click.echo()
    click.echo("  Limited release. Selected deployments.")
    click.echo("  Request access → https://ifixai.ai/ime")
    click.echo()
