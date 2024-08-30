"""
CLI and API to manage a Bluecat instance
"""

import sys
from pathlib import Path
from csv import DictReader, Sniffer
from typing import Annotated, Optional

import typer
from uoft_core import logging
from uoft_core.console import console

from . import Settings

logger = logging.getLogger(__name__)

DEBUG_MODE = False


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
    name="bluecat",
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
    global DEBUG_MODE
    log_level = "INFO"
    if debug:
        log_level = "DEBUG"
        DEBUG_MODE = True
    if trace:
        log_level = "TRACE"
        DEBUG_MODE = True
    logging.basicConfig(level=log_level)


@app.command()
def get_all_prefixes():
    with Settings.from_cache().alt_api_connection() as api:
        blocks = api.get('/blocks').json()['data']
        nets = api.get('/networks').json()['data']
    con = console()
    con.print(blocks)
    con.print(nets)

@app.command()
def register_ips_from_file(
    filename: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        resolve_path=True,
        allow_dash=True,
    ),
):
    if filename.name == "-":
        file = sys.stdin.readlines()
    else:
        file = filename.open().readlines()
    dialect = Sniffer().sniff(file[0])  # figure out if the file is a csv, or a tsv, or whatever
    reader = DictReader(file, dialect=dialect)

    api = Settings.from_cache().get_api_connection()
    conf_id = api.configuration_id
    for row in reader:
        mac = row["mac-address"]
        ip = row["ipv4"]
        res = api.get_ipv4_address(ip, configuration_id=conf_id)
        if res:
            logger.info(f"IP {ip} already registered to Bluecat Object ID: {res['id']}")
            continue
        res = api.assign_ipv4_address(ip, mac, row["hostname"], configuration_id=conf_id)
        logger.success(f"Registered MAC {mac} with address {ip} to Bluecat Object ID: {res}")


def cli():
    try:
        # CLI code goes here
        app()
    except KeyboardInterrupt:
        print("Aborted!")
        sys.exit()
    except Exception as e:
        if DEBUG_MODE:
            raise
        logger.error(e)
        sys.exit(1)

def _debug():
    "Debugging function, only used in active debugging sessions."
    # pylint: disable=all
    app()
