import sys

import click

from ifixai._version import VERSION
from ifixai.cli.init import init
from ifixai.cli.run import run
from ifixai.cli.list_cmd import list_group
from ifixai.cli.validate import validate
from ifixai.cli.compare import compare


@click.group()
@click.version_option(version=VERSION, prog_name="ifixai")
def ifixai_cli() -> None:
    pass


ifixai_cli.add_command(init)
ifixai_cli.add_command(run)
ifixai_cli.add_command(list_group, name="list")
ifixai_cli.add_command(validate)
ifixai_cli.add_command(compare)


def _ensure_utf8_stdout() -> None:
    if sys.platform != "win32":
        return
    import io
    def _fix(stream):  # noqa: E306
        enc = getattr(stream, "encoding", "") or ""
        if enc.lower().replace("-", "") == "utf8":
            return stream
        buf = getattr(stream, "buffer", None)
        if buf is None:
            return stream
        return io.TextIOWrapper(buf, encoding="utf-8", errors="replace")
    sys.stdout = _fix(sys.stdout)
    sys.stderr = _fix(sys.stderr)


def main() -> None:
    _ensure_utf8_stdout()
    ifixai_cli()


if __name__ == "__main__":
    main()
