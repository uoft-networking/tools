"""
A collection of tools to interact with a phpIPAM instance, and to feed data into ansible.
"""

import typer
from uoft_core import logging
from . import Settings
from .ansible_lookup import phpipam_ansible_lookup
from .serial_lookup import phpipam_serial_lookup


app = typer.Typer(
    name="phpipam",
    context_settings={"max_content_width": 120, "help_option_names": ["-h", "--help"]},
    no_args_is_help=True,
    help=__doc__,  # Use this module's docstring as the main program help text
)


@app.callback()
@Settings.wrap_typer_command
def callback(
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
