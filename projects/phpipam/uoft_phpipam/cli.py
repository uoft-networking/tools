"""
A collection of tools to interact with a phpIPAM instance, and to feed data into ansible.
"""
from typing import Annotated, Optional

import typer
from uoft_core import logging
from . import Settings
from .ansible_lookup import phpipam_ansible_lookup
from .serial_lookup import phpipam_serial_lookup


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
    name="phpipam",
    context_settings={"max_content_width": 120, "help_option_names": ["-h", "--help"]},
    no_args_is_help=True,
    help=__doc__,  # Use this module's docstring as the main program help text
)


@app.callback()
@Settings.wrap_typer_command
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


@app.command(help="From a serial, returns a dictionary object of a given device.", no_args_is_help=True)
def serial_lookup(serial):
    print(phpipam_serial_lookup(serial))


@app.command(
    help="From a serial, returns a dictionary configuration object to be used in Ansible.", no_args_is_help=True
)
def ansible_lookup(serial):
    print(phpipam_ansible_lookup(serial))


def _debug():
    "Debugging function, only used in active debugging sessions."
    # pylint: disable=all
    app()
