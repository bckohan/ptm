from typer import Typer

app = Typer(help="Validate the uv_matrix configuration.")


@app.command()
def check():
    """Check the uv_matrix configuration."""
    pass
