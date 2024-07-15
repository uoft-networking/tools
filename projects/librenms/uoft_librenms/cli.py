"""
API Wrapper and (hopefully soon) CLI interface for the LibreNMS REST API
"""

import typer

from . import Settings
from uoft_core import logging


app = typer.Typer(
    name="librenms",
    context_settings={"max_content_width": 120, "help_option_names": ["-h", "--help"]},
    no_args_is_help=True,
    help=__doc__,  # Use this module's docstring as the main program help text
)

@app.callback()
#@Settings.wrap_typer_command
#TODO: implement click paramtype support for Settings AnyHttpUrl
def callback(
    debug: bool = typer.Option(False, help="Turn on debug logging", envvar="DEBUG"),
    trace: bool = typer.Option(False, help="Turn on trace logging. implies --debug", envvar="TRACE"),
):
    log_level = "INFO"
    if debug:
        log_level = "DEBUG"
    logging.basicConfig(level=log_level)

# Be sure to replace the below example commands with your own
@app.command()
def example_subcommand1(arg1: str, arg2: str, option1: bool = typer.Option(False, help="An example option")):
    print(arg1, arg2, option1)

@app.command()
def another_exampple_subcommand(arg1: str, arg2: str, option1: bool = typer.Option(False, help="An example option")):
    print(arg1, arg2, option1)

def _debug():
    "Debugging function, only used in active debugging sessions."
    # pylint: disable=all
    app()
