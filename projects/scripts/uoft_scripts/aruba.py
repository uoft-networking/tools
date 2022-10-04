# This module has been moved to the uoft_core package.
# It is being re-exported here for backwards compatability
from uoft_core.aruba import *   # type: ignore pylint: disable=wildcard-import,unused-wildcard-import
from uoft_core import shell, CalledProcessError
import json
from getpass import getpass

import typer
from loguru import logger


app = typer.Typer(
    name="aruba",
    context_settings={"max_content_width": 120, "help_option_names": ["-h", "--help"]},
    no_args_is_help=True,
    help=__doc__,  # Use this module's docstring as the main program help text
)


@app.callback()
def _(
    ctx: typer.Context,
    controller1: str = typer.Option("aruba-7240xm-01.netmgmt.utsc.utoronto.ca:4343"),
    controller2: str = typer.Option("aruba-7240xm-01.netmgmt.utsc.utoronto.ca:4343"),
    username: str = typer.Option("apiadmin"),
    password: str = typer.Option(None),
):

    if not password:
        try:
            password = shell("pass aruba-api").splitlines()[0]
        except (
            CalledProcessError,
            IndexError,
        ):
            logger.warning(
                "Executed command `pass aruba-api` failed, prompting for password manually"
            )
            password = getpass("Aruba API Password: ")
    ctx.obj = (controller1, controller2, username, password)


@app.command()
def stm_blacklist_get(ctx: typer.Context):
    controller1, controller2, username, password = ctx.obj

    with ArubaRESTAPIClient(controller1, username, password) as c:
        d1 = c.stm_blacklist_get()

    with ArubaRESTAPIClient(controller2, username, password) as c:
        d2 = c.stm_blacklist_get()

    res = d1 + d2
    print(json.dumps(res, indent=4))


@app.command()
def stm_blacklist_remove(ctx: typer.Context, mac_address: str):

    controller1, controller2, username, password = ctx.obj

    with ArubaRESTAPIClient(controller1, username, password) as c:
        c.stm_blacklist_remove(mac_address)

    with ArubaRESTAPIClient(controller2, username, password) as c:
        c.stm_blacklist_remove(mac_address)
        c.controller.write_memory()

    print("Done!")
