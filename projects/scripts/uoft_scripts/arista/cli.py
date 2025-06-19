from typing import Annotated

import typer


def prettyprinter_result_callback(result, *args, **kwargs):
    "Pretty print the return value of a task"
    if result is None:
        return

    from uoft_core.console import stdout_console

    # special case for strings
    if isinstance(result, str):
        stdout_console().print(result)
        return
    from rich.pretty import pprint

    pprint(result, console=stdout_console())


app = typer.Typer(name="arista", result_callback=prettyprinter_result_callback)


@app.command()
def get_onboarding_token():
    """Get the onboarding token from the switch"""
    from . import lib

    return lib.get_onboarding_token()


@app.command()
def initial_provision(
    switch: Annotated[str, typer.Argument(help="Switch hostname")],
    terminal_server: Annotated[str, typer.Argument(help="Terminal server hostname")],
    port: Annotated[int, typer.Argument(help="Switch port")],
):
    """
    Given a switch hostname, terminal server, and port,
    connect to the switch via the terminal server
    and give it the minimum viable config necessary
    to get it online and accessible via SSH over OOB
    (including RADIUS auth)
    """
    from . import lib

    lib.initial_provision(switch, terminal_server, port)


@app.command()
def wipe_switch(
    terminal_server: Annotated[str, typer.Argument(help="Terminal server hostname")],
    port: Annotated[int, typer.Argument(help="Switch port")],
    reenable_ztp_mode: Annotated[bool, typer.Option(help="Reenable ZTP mode")] = False,
):
    """
    Given a terminal server and port,
    wipe the Arista switch attached to that port
    and reset it to factory defaults.
    This is used for testing and debugging.
    """
    from . import lib

    lib.wipe_switch(terminal_server, port, reenable_ztp_mode)


@app.command()
def map_stack_connections(
    dist_switch_hostname: Annotated[
        str, typer.Argument(help="Hostname of the Distribution switch this stack will uplink to", metavar="HOSTNAME")
    ],
    arista_switch_names: Annotated[
        list[str],
        typer.Argument(help="List of Arista switch hostnames to organize into a stack", metavar="HOSTNAME..."),
    ],
):
    """
    Given a dist switch and a list of arista switches to organize into an mlag leaf-spine stack,
    login to each over ssh, identify connections between them all using LLDP, identify port roles
    for each port of each connection, and push the data to nautobot
    """
    from . import lib

    lib.map_stack_connections(dist_switch_hostname, *arista_switch_names)


@app.command()
def push_nautobot_config_to_switches(
    arista_switch_names: Annotated[
        list[str],
        typer.Argument(help="List of Arista switch hostnames to push full intended config to", metavar="HOSTNAME..."),
    ],
):
    """Given a switch hostname, pull ip_address and intended config from Nautobot
    push config to switch via SSH"""
    from . import lib

    lib.push_nautobot_config_to_switches(*arista_switch_names)


def _debug():
    pass
