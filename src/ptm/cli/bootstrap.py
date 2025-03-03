from typer import Typer

app = Typer(help="Bootstrap the selected environment.")


@app.command()
def bootstrap():
    pass
