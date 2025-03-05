import subprocess
import typing as t
from itertools import chain
from platform import platform

from typer import Argument, Context, Option, Typer
from typing_extensions import Annotated

from ..config import Config, Run
from .args import Environments, RunParser, Tags, complete_run

app = Typer(help="Run the command in the specified environment.")


@app.command()
def run(
    ctx: Context,
    trailing_args: Annotated[t.List[str], Argument(metavar="--")],
    runs: Annotated[
        t.Optional[t.List[Run]],
        Option(
            "--run",
            "-r",
            parser=RunParser(),
            shell_complete=complete_run,
            help="The run identifier.",
        ),
    ] = [],
    envs: Environments = [],
    tags: Tags = [],
):
    cfg: Config = ctx.obj["config"]
    if not runs:
        runs = (
            chain.from_iterable(env.runs(tags=set(tags)) for env in envs)  # type: ignore
            if envs
            else cfg.runs(tags=set(tags))
        )
    for run in runs or []:
        with run.bootstrap():
            source = f"source {(run.venv / 'bin' / 'activate')}"
            if platform() == "Windows":
                source = f"{(run.venv / 'bin' / 'activate.bat')}"
            subprocess.run(
                f"{source} && {' '.join(trailing_args)}",
                shell=True,
                check=True,
            )
