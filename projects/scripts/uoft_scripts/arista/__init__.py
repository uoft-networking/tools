from typing import Annotated
from uoft_core import BaseSettings, SecretStr

import typer


class Settings(BaseSettings):
    cvp_token: SecretStr

    class Config(BaseSettings.Config):
        app_name = "arista"


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
def onboard_via_terminal_server(
    switch: Annotated[str, typer.Argument(help="Switch hostname")],
    terminal_server: Annotated[str, typer.Argument(help="Terminal server hostname")],
    port: Annotated[int, typer.Argument(help="Switch port")],
):
    "Setup an Arista switch for onboarding"
    from . import onboarding

    onboarding.onboard_via_terminal_server(switch, terminal_server, port)


@app.command()
def wipe_switch(
    terminal_server: Annotated[str, typer.Argument(help="Terminal server hostname")],
    port: Annotated[int, typer.Argument(help="Switch port")],
    reenable_ztp_mode: Annotated[bool, typer.Option(help="Reenable ZTP mode")] = False,
):
    "Wipe an Arista switch and reset it to factory defaults"
    from . import onboarding

    onboarding.wipe_switch(terminal_server, port, reenable_ztp_mode)


@app.command()
def push_nautobot_config_to_switch(
    switch: Annotated[str, typer.Argument(help="Switch hostname")],
):
    """Given a switch hostname, pull ip_address and intended config from Nautobot
    push config to switch via SSH"""
    from . import onboarding

    onboarding.push_nautobot_config_to_switch(switch)


def _debug():
    push_nautobot_config_to_switch('a1-ev0c-arista')
