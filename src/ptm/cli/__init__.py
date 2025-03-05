import typing as t
from pathlib import Path

from typer import Context, Option, Typer, echo
from typing_extensions import Annotated

from .. import __version__
from ..config import Config, initialize
from . import bootstrap, check, generate, run, table

app = Typer(pretty_exceptions_show_locals=False)

app.add_typer(generate.app)
app.add_typer(table.app)
app.add_typer(check.app)
app.add_typer(bootstrap.app)
app.add_typer(run.app)


def init_config(ctx: Context, _, value: t.Optional[Path]):
    ctx.ensure_object(dict)
    ctx.obj["config_path"] = value
    ctx.obj["config"] = initialize(value)
    return value


@app.callback()
def callback(
    ctx: Context,
    config: Annotated[
        t.Optional[Path],
        Option(
            "--config",
            "-c",
            callback=init_config,
            is_eager=True,
            help="Path to the pyproject.toml file.",
        ),
    ] = None,
):
    assert isinstance(ctx.obj["config"], Config)
    assert config is ctx.obj["config_path"]


@app.command()
def version():
    """Show the uv_matrix version."""
    echo(f"{__version__}")
