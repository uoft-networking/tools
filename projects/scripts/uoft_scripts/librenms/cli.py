
import typer

app = typer.Typer(name="librenms")

@app.command()
def get_devices(dev: bool = False):
    from . import lib

    lib.get_devices(dev=dev)
