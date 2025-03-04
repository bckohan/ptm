import typing as t
from pprint import pprint

from typer import Context, Option, Typer, progressbar
from typing_extensions import Annotated

from ..config import Config

app = Typer(help="Generate the test environments.")


@app.command()
def generate(
    ctx: Context,
    envs: Annotated[
        t.List[str], Option("--env", "-e", help="Generate only the given environments.")
    ] = [],
    tags: Annotated[
        t.List[str], Option("--tags", "-t", help="Generate only the given tagged runs.")
    ] = [],
):
    cfg: Config = ctx.obj["config"]
    run_table = {}
    with progressbar(
        cfg.generate(environments=envs, tags=tags), label="Generating Runs"
    ) as progress:
        for run in progress:
            run_table.setdefault(run.group.env.name, 0)
            run_table[run.group.env.name] += 1
    pprint(run_table)
