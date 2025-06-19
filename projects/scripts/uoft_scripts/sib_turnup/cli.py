from . import Role

from typing import Annotated
from typer import Typer, Argument, Option

app = Typer(name="sib-turnup", help=__doc__)


@app.callback()
def callback():
    pass


@app.command()
def go(
    switch: Annotated[str, Argument(help="The switch to configure.")],
    intf: Annotated[str, Argument(help="The interface to configure.")],
    room: Annotated[str, Argument(help="What room is this port in?")],
    label: Annotated[str, Argument(help="The label on the port.")],
    role: Annotated[Role, Argument(help="what will this port be used for?")],
    dry_run: Annotated[
        bool, Option(help="Run preflight checks, print the config that WOULD have been applied, then exit")
    ] = False,
    hw: Annotated[bool, Option(help="This is a Health & Wellness port")] = False,
    lab: Annotated[bool, Option(help="This is a CMS lab port")] = False,
    pos: Annotated[bool, Option(help="This is a POS / Debit machine port")] = False,
    passthrough: Annotated[bool, Option(help="This VOIP port will have passthrough configured")] = False,
    default: Annotated[bool, Option(help="Default the interface before applying the config")] = False,
):
    from . import lib

    lib.go(
        switch=switch,
        intf=intf,
        room=room,
        label=label,
        role=role,
        dry_run=dry_run,
        hw=hw,
        lab=lab,
        pos=pos,
        passthrough=passthrough,
        default=default,
    )


@app.command()
def parse(msg: str | None = None):
    """This parse script expects a message from teams roughly in the form of:

    Port Activation
    ==========
    Device: Windows Desktop
    Port Label: IA-B01
    MAC: <mac address>
    Switch Name: <switch>.NETMGMT.UTSC.UTORONTO.CA
    Port Identifier: TenGigabitEthernet2/0/25
    VLAN: 666
    Switch IP: <ip address>

    or:

    Port Activation:
    - Room: <room number>
    - Device: VOIP
    - Port: 4W-C27

    TimeToLive        : 120
    Model             : C9300X-48HX
    VLAN              : 666
    SystemDescription : Cisco IOS Software [Cupertino], Catalyst L3 Switch Software (CAT9K_IOSXE), V...
    Port              : Te4/0/27
    Device            : <switch>.netmgmt.utsc.utoronto.ca
    PortDescription   : TenGigabitEthernet4/0/27
    IPAddress         : {<switch ip>}
    ChassisId         : ...
    Computer          : <computer's fqdn>
    Connection        : Ethernet
    Interface         : Realtek USB GbE Family Controller
    Type              : LLDP
    """
    from . import lib

    lib.parse(msg)
