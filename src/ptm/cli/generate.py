import typing as t
from itertools import chain
from pprint import pprint

from typer import Context, Typer

from ..config import Config
from .args import Environments, Runs, Tags

app = Typer(help="Generate the test environments.")


@app.command()
def generate(
    ctx: Context,
    runs: Runs = None,
    envs: Environments = [],
    tags: Tags = [],
):
    cfg: Config = ctx.obj["config"]
    run_table: t.Dict[str, int] = {}
    if not runs:
        runs = (
            chain.from_iterable(env.runs(tags=set(tags)) for env in envs)  # type: ignore
            if envs
            else cfg.runs(tags=set(tags))
        )
    for run in runs or []:
        run.generate()
        run_table.setdefault(run.group.env.name, 0)
        run_table[run.group.env.name] += 1
    pprint(run_table)
