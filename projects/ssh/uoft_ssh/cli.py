"""
A toolkit for working with SSH. Wrappers, Ansible convenience features, Nornir integration, etc
"""
from typing import Annotated, Optional

import typer

from uoft_core import logging
from . import Settings


def _version_callback(value: bool):
    if not value:
        return
    from . import __version__
    import sys

    print(
        f"uoft-{Settings.Config.app_name} v{__version__} \nPython {sys.version_info.major}."
        f"{sys.version_info.minor} ({sys.executable}) on {sys.platform}"
    )
    raise typer.Exit()

app = typer.Typer(
    name="ssh",
    context_settings={"max_content_width": 120, "help_option_names": ["-h", "--help"]},
    no_args_is_help=True,
    help=__doc__,  # Use this module's docstring as the main program help text
)

@app.callback()
#@Settings.wrap_typer_command
#TODO: implement support for exploding submodels in Settings.wrap_typer_command
def callback(
    version: Annotated[
        Optional[bool],
        typer.Option("--version", callback=_version_callback, is_eager=True, help="Show version information and exit"),
    ] = None,
    debug: bool = typer.Option(False, help="Turn on debug logging", envvar="DEBUG"),
    trace: bool = typer.Option(False, help="Turn on trace logging. implies --debug", envvar="TRACE"),
):
    log_level = "INFO"
    if debug:
        log_level = "DEBUG"
    logging.basicConfig(level=log_level)

@app.command()
def wrapper():
    # TODO: write and embed an expect script here
    pass

@app.command()
def nornir():
    # TODO: nornir! with napalm!
    pass

def _debug():
    "Debugging function, only used in active debugging sessions."
    # pylint: disable=all
    app()