from typing import Annotated

import typer



def prettyprinter_result_callback(result, *args, **kwargs):
    "Pretty print the return value of a task"
    if result is None:
        return

    from uoft_core.console import console

    # special case for strings
    if isinstance(result, str):
        console().print(result)
        return
    from rich.pretty import pprint

    pprint(result, console=console())


app = typer.Typer(name="arista", result_callback=prettyprinter_result_callback)

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
    from . import arista

    arista.initial_provision(switch, terminal_server, port)




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
    from . import arista

    arista.wipe_switch(terminal_server, port, reenable_ztp_mode)


@app.command()
def push_nautobot_config_to_switch(
    switch: Annotated[str, typer.Argument(help="Switch hostname")],
):
    """Given a switch hostname, pull ip_address and intended config from Nautobot
    push config to switch via SSH"""
    from . import arista

    arista.push_nautobot_config_to_switch(switch)


def _debug():
    push_nautobot_config_to_switch('a1-ev0c-arista')
