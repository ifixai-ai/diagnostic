
import click

from ifixai.fixture_loader import validate_fixture


@click.command()
@click.argument("path", type=click.Path(exists=True))
def validate(path: str) -> None:

    errors = validate_fixture(path)

    if not errors:
        click.echo(click.style("Valid", fg="green"))
        return

    click.echo(click.style(f"Validation failed with {len(errors)} error(s):", fg="red"))
    click.echo()
    for index, error_msg in enumerate(errors, start=1):
        click.echo(f"  {index}. {error_msg}")
    click.echo()

    raise SystemExit(1)
