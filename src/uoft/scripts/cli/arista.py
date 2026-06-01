import typing as t

import typer
from nornir.core.exceptions import NornirExecutionError


def prettyprinter_result_callback(result, *args, **kwargs):
    "Pretty print the return value of a task"
    if result is None:
        return

    from uoft.core.console import stdout_console

    # special case for strings
    if isinstance(result, str):
        stdout_console().print(result)
        return
    from rich.pretty import pprint

    pprint(result, console=stdout_console())


app = typer.Typer(name="arista", result_callback=prettyprinter_result_callback, no_args_is_help=True)


@app.command()
def onboard_into_cvp(
    switch: t.Annotated[str, typer.Argument(help="Switch hostname")],
    oob: t.Annotated[bool, typer.Option(help="configure switch to talk to CVP over OOB management VRF")] = True,
):
    """Take a configured, SSH-accessible Arista switch
    and onboard it into CVP using a CVP onboarding token
    """
    from ..arista import lib

    return lib.onboard_into_cvp(switch_name=switch, oob=oob)


@app.command()
def initial_provision(
    switch: t.Annotated[str, typer.Argument(help="Switch hostname")],
    terminal_server: t.Annotated[str, typer.Argument(help="Terminal server hostname")],
    port: t.Annotated[int, typer.Argument(help="Switch port")],
    airconsole: t.Annotated[bool, typer.Option(help="Use Airconsole terminal server type")] = False,
):
    """
    Given a switch hostname, terminal server, and port,
    connect to the switch via the terminal server
    and give it the minimum viable config necessary
    to get it online and accessible via SSH over OOB
    (including RADIUS auth)
    """
    from ..arista import lib

    terminal_server_type = "airconsole" if airconsole else "tripplite"

    lib.initial_provision(switch, terminal_server, port, terminal_server_type)


@app.command()
def wipe_switch(
    terminal_server: t.Annotated[str, typer.Argument(help="Terminal server hostname")],
    port: t.Annotated[int, typer.Argument(help="Switch port")],
    reenable_ztp_mode: t.Annotated[bool, typer.Option(help="Reenable ZTP mode")] = False,
    airconsole: t.Annotated[bool, typer.Option(help="Use Airconsole terminal server type")] = False,
):
    """
    Given a terminal server and port,
    wipe the Arista switch attached to that port
    and reset it to factory defaults.
    This is used for testing and debugging.
    """
    from ..arista import lib

    terminal_server_type = "airconsole" if airconsole else "tripplite"

    lib.wipe_switch(terminal_server, port, reenable_ztp_mode, terminal_server_type)


@app.command()
def map_stack_connections(
    dist_switch_hostname: t.Annotated[
        str, typer.Argument(help="Hostname of the Distribution switch this stack will uplink to", metavar="HOSTNAME")
    ],
    arista_switch_names: t.Annotated[
        list[str],
        typer.Argument(help="List of Arista switch hostnames to organize into a stack", metavar="HOSTNAME..."),
    ],
    dist_lag_number: t.Annotated[  # pyright: ignore[reportRedeclaration]
        int | None,
        typer.Option(
            help="Port channel number to use for the dist switch downlink to the spine switches. "
            "If 'auto', will find the next available port channel number.",
        ),
    ] = None,
):
    """
    Given a dist switch and a list of arista switches to organize into an mlag leaf-spine stack,
    login to each over ssh, identify connections between them all using LLDP, identify port roles
    for each port of each connection, and push the data to nautobot
    """
    if len(arista_switch_names) < 2:
        typer.echo("You must provide at least two Arista switch hostnames to form a stack.", err=True)
        raise typer.Exit(code=1)
    from ..arista import lib

    if dist_lag_number is None:
        dist_lag_number: str = "auto"

    lib.map_stack_connections(dist_switch_hostname, *arista_switch_names, dist_lag_number=dist_lag_number)


@app.command()
def push_nautobot_config_to_switches(
    arista_switch_names: t.Annotated[
        list[str],
        typer.Argument(help="List of Arista switch hostnames to push full intended config to", metavar="HOSTNAME..."),
    ],
):
    """Given a switch hostname, pull ip_address and intended config from Nautobot
    push config to switch via SSH"""
    from ..arista import lib

    try:
        lib.push_nautobot_config_to_switches(*arista_switch_names)
    except NornirExecutionError as e:
        typer.echo(f"Error pushing config: {e}", err=True)
        raise typer.Exit(code=1)


@app.command()
def breakout_interfaces(
    switch_name: t.Annotated[str, typer.Argument(help="Switch hostname", metavar="SWITCH")],
    interface_name: t.Annotated[
        str,
        typer.Argument(
            help="Name of interface to break out, e.g. 'Ethernet97/1' or 'Ethernet98/1'. "
            "This interface must already exist in Nautobot.",
            metavar="INTERFACE",
        ),
    ],
):
    """
    Given a switch name and an interface to breakout,
    update the switch's interfaces in nautobot to reflect the breakout

    ie, if you run `uoft-scripts arista breakout-interface a1-ach1-arista Ethernet97/1`, This script will:
    - connect to Nautobot
    - find Ethernet97/1, set its type to SFP28 (25GE),
    - create Ethernet97/2, Ethernet97/3, Ethernet97/4 with type SFP28 (25GE),
    """

    from ..arista import lib

    lib.breakout_interface(switch_name, interface_name)


def _debug():
    pass
