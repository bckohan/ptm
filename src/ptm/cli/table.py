from typer import Typer

app = Typer(help="Show or output tabular renderings of the strategy matrix.")


@app.command()
def table():
    """Generate the table."""
    pass
