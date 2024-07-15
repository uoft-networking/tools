"""
A toolkit for working with SSH. Wrappers, Ansible convenience features, Nornir integration, etc
"""

import typer

from uoft_core import logging
from . import Settings

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