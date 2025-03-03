from typer import Context, Typer, progressbar

from ..config import Config

app = Typer(help="Generate the test environments.")


@app.command()
def generate(ctx: Context):
    cfg: Config = ctx.obj["config"]
    with progressbar(cfg.environments.items(), label="Processing items") as progress:
        for env_name, env in progress:
            env.generate()
