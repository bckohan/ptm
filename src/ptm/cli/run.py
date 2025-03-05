import subprocess
import typing as t

from typer import Argument, Typer
from typing_extensions import Annotated

from ..config import Run
from .args import RunParser, complete_run

app = Typer(help="Run the command in the specified environment.")


@app.command()
def run(
    run: Annotated[
        Run, Argument(parser=RunParser(), shell_complete=complete_run, help="The run i")
    ],
    trailing_args: Annotated[t.List[str], Argument(metavar="--")],
):
    with run.bootstrap():
        subprocess.run(trailing_args, check=True)
