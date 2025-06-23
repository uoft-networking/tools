"""
CLI and API to manage a Bluecat instance
"""

import sys
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
    with Settings.from_cache().get_api_connection() as api:
        blocks = api.get("/blocks").json()["data"]
        nets = api.get("/networks").json()["data"]
    con = console()
    con.print(blocks)
    con.print(nets)


@app.command()
def add_or_update_ip(
    ip: Annotated[str, typer.Argument(help="IP address (CIDR notation) to add or update")],
    hostname: Annotated[str, typer.Argument(help="Hostname to add or update")],
):
    from ipaddress import ip_interface

    try:
        ip_cidr = ip_interface(ip)
    except ValueError as e:
        logger.error(f"Invalid IP address: {ip}. Error: {e}")
        sys.exit(1)
    with Settings.from_cache().get_api_connection() as api:
        pass
        net = api.find_parent_network(str(ip_cidr.ip))

        # create address if it does not exist

        # create or update host record linked to the IP address

        # netmgmt_zone = api.get_container_default_zones(net["id"], "networks")[0]
        # if existing_record := api.get(
        #     f'/zones/{netmgmt_zone["id"]}/resourceRecords', params={"name": hostname}
        # ).json()["data"]:
        #     existing_record = existing_record[0]
        #     if existing_record["type"] == "A":
        #         logger.info(f"Updating existing A record for {hostname} to {ip_cidr}")
        #         api.update_resource_record(existing_record["id"], ip_cidr, netmgmt_zone["id"])
        #     else:
        #         logger.error(f"Existing record for {hostname} is not an A record. Skipping update.")


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
    # app()
    add_or_update_ip("192.168.64.7/22", "a1-ev0c-arista")
