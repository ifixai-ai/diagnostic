import click

from ifixai.api import list_tests as get_tests, list_fixtures as get_fixture_names
from ifixai.core.fixture_loader import load_fixture


@click.group("list")
def list_group() -> None:
    pass


@list_group.command("tests")
@click.option(
    "--verbose", "-v",
    is_flag=True,
    default=False,
    help="Include test descriptions.",
)
def list_tests(verbose: bool) -> None:

    specs = get_tests()

    click.echo()
    click.echo(click.style(f"ifixai ({len(specs)})", bold=True))
    click.echo()

    if verbose:
        header = f"{'ID':<12} {'Name':<35} {'Category':<20} {'Threshold':>9}  Description"
        click.echo(header)
        click.echo("-" * len(header) + "-" * 40)
    else:
        header = f"{'ID':<12} {'Name':<35} {'Category':<20} {'Threshold':>9}"
        click.echo(header)
        click.echo("-" * len(header))

    for spec in specs:
        category_short = _short_category(spec.category.value)
        threshold_display = f"{spec.threshold:.0%}"
        strategic_marker = " *" if spec.is_strategic else ""

        line = f"{spec.test_id:<12} {spec.name:<35} {category_short:<20} {threshold_display:>9}{strategic_marker}"

        if verbose:
            line += f"  {spec.description}"

        click.echo(line)

    click.echo()
    click.echo(click.style("* = Strategic test (Top 8)", dim=True))
    click.echo()


@list_group.command("fixtures")
def list_fixtures() -> None:

    names = get_fixture_names()

    click.echo()
    click.echo(click.style("ifixai Fixtures", bold=True))
    click.echo()

    header = f"{'Name':<20} {'Domain':<30}"
    click.echo(header)
    click.echo("-" * len(header))

    for name in names:
        domain = _load_fixture_domain(name)
        click.echo(f"{name:<20} {domain:<30}")

    click.echo()
    click.echo(f"{len(names)} fixture(s) available.")
    click.echo()


def _short_category(full_category: str) -> str:
    return full_category.title()


def _load_fixture_domain(name: str) -> str:
    try:
        fixture = load_fixture(name)
        return fixture.metadata.domain or fixture.metadata.name
    except Exception:
        return name
