from getpass import getpass
import os, sys
import traceback
from typing import Optional
import json
from subprocess import CalledProcessError

from uoft_core import shell

from . import config
from . import bluecat as bluecat_
from uoft_core.aruba import ArubaRESTAPIClient

import typer
from loguru import logger
import ldap3

app = typer.Typer(name="uoft_scripts")
collect = typer.Typer()
aruba = typer.Typer()
ldap = typer.Typer()
app.add_typer(collect, name="collect", no_args_is_help=True)
app.add_typer(aruba, name="aruba")
app.add_typer(ldap, name="ldap")


def version_callback(value: bool):
    if value:
        from . import __version__  # noqa
        from sys import version_info as v, platform, executable  # noqa

        print(
            f"uoft_scripts v{__version__} \nPython {v.major}.{v.minor} ({executable}) on {platform}"
        )
        raise typer.Exit()


@app.callback(
    context_settings={"max_content_width": 120, "help_option_names": ["-h", "--help"]}
)
def callback(
    debug: bool = typer.Option(False, help="Turn on debug logging"),
    trace: bool = typer.Option(False, help="Turn on trace logging. implies --debug"),
    version: Optional[bool] = typer.Option(  # pylint: disable=unused-argument
        None,
        "--version",
        callback=version_callback,
        help="Show version information and exit",
    ),
):
    """
    Alex Tremblay's assorted scripts
    """

    log_level = "INFO"
    if debug:
        log_level = "DEBUG"
    if trace:
        log_level = "TRACE"
    config.util.logging.enable()
    config.util.logging.add_stderr_rich_sink(log_level)
    config.util.logging.add_syslog_sink()


@aruba.callback()
def aruba_callback(
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


@aruba.command()
def stm_blacklist_get(ctx: typer.Context):
    controller1, controller2, username, password = ctx.obj

    with ArubaRESTAPIClient(controller1, username, password) as c:
        d1 = c.stm_blacklist_get()

    with ArubaRESTAPIClient(controller2, username, password) as c:
        d2 = c.stm_blacklist_get()

    res = d1 + d2
    print(json.dumps(res, indent=4))


@aruba.command()
def stm_blacklist_remove(ctx: typer.Context, mac_address: str):

    controller1, controller2, username, password = ctx.obj

    with ArubaRESTAPIClient(controller1, username, password) as c:
        c.stm_blacklist_remove(mac_address)

    with ArubaRESTAPIClient(controller2, username, password) as c:
        c.stm_blacklist_remove(mac_address)
        c.controller.write_memory()

    print("Done!")


@collect.command()
def bluecat():
    """
    Collect bluecat data
    """

    bluecat_.collect()


@ldap.command()
def user(
    name: str,
):
    pw, bind_dn, host, users_base_dn, groups_base_dn = shell(
        "pass utsc/nautobot-ldap"
    ).splitlines()
    server = ldap3.Server(host, get_info=ldap3.ALL)
    conn = ldap3.Connection(server, bind_dn, pw, auto_bind=True)  # type: ignore
    conn.search(users_base_dn, f"(name={name})", attributes=ldap3.ALL_ATTRIBUTES)
    print(conn.entries)


@ldap.command()
def group(name: Optional[str] = "", attributes: str = "cn,name,member,objectClass"):
    if attributes == "ALL":
        attrs = ldap3.ALL_ATTRIBUTES
    else:
        attrs = attributes.split(",")
    pw, bind_dn, host, users_base_dn, groups_base_dn = shell(
        "pass utsc/nautobot-ldap"
    ).splitlines()
    server = ldap3.Server(host, get_info=ldap3.ALL)
    conn = ldap3.Connection(server, bind_dn, pw, auto_bind=True)  # type: ignore
    conn.search(groups_base_dn, f"(name={name}*)", attributes=attrs)
    for entry in conn.entries:
        print(entry)


def cli():
    try:
        # CLI code goes here
        app()
    except KeyboardInterrupt:
        print("Aborted!")
        sys.exit()
    except Exception as e:  # pylint: disable=broad-except
        # wrap exceptions so that only the message is printed to stderr, stacktrace printed to log
        logger.error(e)
        logger.debug(traceback.format_exc())


if __name__ == "__main__":

    if os.environ.get("PYDEBUG"):
        # Debug code goes here
        def dothething():
            class Context:
                obj: tuple

            controller1 = "aruba-7240xm-01.netmgmt.utsc.utoronto.ca:4343"
            controller2 = "aruba-7240xm-01.netmgmt.utsc.utoronto.ca:4343"
            username = "apiadmin"
            password = shell("pass aruba-api").splitlines()[0]
            ctx = Context()
            ctx.obj = (controller1, controller2, username, password)

            with ArubaRESTAPIClient(controller1, username, password) as c:
                d1 = c.showcommand_raw("show log user all").text

            print(d1)

        dothething()
        sys.exit()
    cli()
