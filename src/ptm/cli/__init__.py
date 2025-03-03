import typing as t
from pathlib import Path

from typer import Context, Option, Typer, echo
from typing_extensions import Annotated

from .. import __version__
from ..config import initialize
from . import bootstrap, check, generate, table

app = Typer()

app.add_typer(generate.app)
app.add_typer(table.app)
app.add_typer(check.app)
app.add_typer(bootstrap.app)


@app.callback()
def callback(
    ctx: Context,
    config: Annotated[
        t.Optional[Path],
        Option("--config", "-c", help="Path to the pyproject.toml file."),
    ] = None,
):
    ctx.ensure_object(dict)
    ctx.obj["config"] = initialize(config)
    initialize(config)


@app.command()
def version():
    """Show the uv_matrix version."""
    echo(f"{__version__}")
