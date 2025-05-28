import typer

from . import Settings

app = typer.Typer(
    name="stg-ipam-dev",
    context_settings={"max_content_width": 120, "help_option_names": ["-h", "--help"]},
    no_args_is_help=True,
    help=__doc__,  # Use this module's docstring as the main program help text
)


@app.callback()
@Settings.wrap_typer_command
def callback():
    pass


@app.command()
def sync_to_paloalto(commit: bool = typer.Option(False, help="Commit changes to the Palo Alto API")):
    from . import lib

    lib.sync_to_paloalto(commit=commit)


@app.command()
def sync_to_nautobot():
    """Syncronize networks and contacts from the database behind ipam.utoronto.ca into nautobot"""
    from . import lib

    lib.sync_to_nautobot()
