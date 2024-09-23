#!/usr/bin/env python3
"Quick and dirty script to turn up a port on a switch in SIB."

from enum import Enum
from typing import Annotated

from uoft_core import lst, txt
from uoft_core import logging
from uoft_ssh import Settings
from typer import Typer, Argument, Option
from netmiko import ConnectHandler

app = Typer(name="sib-turnup", help=__doc__)
logger = logging.getLogger(__name__)


class Role(str, Enum):
    voip = "voip"
    desktop = "desktop"
    printer = "printer"


base_config = lst("""
    switchport mode access
    switchport port-security violation restrict
    switchport port-security aging time 1
    switchport port-security aging type inactivity
    switchport port-security
    ip arp inspection limit rate 50
    load-interval 30
    storm-control broadcast level pps 1k
    storm-control multicast level pps 1k
    storm-control action trap
    spanning-tree portfast
    spanning-tree bpduguard enable
    ip verify source
    ip dhcp snooping limit rate 15
    """)

conf = {
    Role.voip: lst("""
        switchport voice vlan 305
        switchport port-security maximum 2
        switchport port-security maximum 1 vlan access
        auto qos voip cisco-phone
        """),  #
    Role.desktop: lst("""
        switchport host
        power inline never
        switchport port-security maximum 1
        switchport access vlan 100
        """),
    Role.printer: lst("""
        switchport access vlan 240
        power inline never
        """),
}


def is_port_unconfigured(confs: str) -> bool:
    # strip all lines preceding the interface config
    confs = confs.partition("interface")[2]

    # strip all lines following the interface config
    confs = confs.partition("end")[0]

    # convert to list
    conf = confs.splitlines()

    # drop interface line
    conf.pop(0)

    # strip whitespace from each line
    conf = [line.strip() for line in conf]

    unconfigured = lst("""
        switchport access vlan 666
        switchport mode access
        load-interval 30
        spanning-tree portfast
        """)

    return conf == unconfigured


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
        bool, Option(help="Run preflight checks, print the config the WOULD have been applied, then exit")
    ] = False,
    hw: Annotated[bool, Option(help="This is a Health & Wellness port")] = False,
    lab: Annotated[bool, Option(help="This is a CMS lab port")] = False,
    pos: Annotated[bool, Option(help="This is a POS / Debit machine port")] = False,
    passthrough: Annotated[bool, Option(help="This VOIP port will have passthrough configured")] = False,
    default: Annotated[bool, Option(help="Default the interface before applying the config")] = False,
):
    logger.info(f"Turning up {intf} on {switch}")
    s = Settings.from_cache()
    with logging.Context(f"netmiko[{switch}]"):
        ssh = ConnectHandler(
            device_type="cisco_ios",
            host=switch,
            username=s.personal.username,
            password=s.personal.password.get_secret_value(),
        )
    logger.info(f"Running command: show run int {intf}")
    current_conf = ssh.send_command(f"show run int {intf}")
    current_conf = current_conf.partition("!")[2]
    print(current_conf)
    logger.info(f"Running comand: show lldp neighbors {intf}")
    print(ssh.send_command(f"show lldp neighbors {intf}"))
    floor, _, port = label.partition("-")
    desc = f"{floor}-{room}-{port}"

    # hw, lab, and pos are mutually exclusive
    if sum([hw, lab, pos]) > 1:
        raise ValueError("Only one of --hw, --lab, or --pos can be specified")
    if hw:
        desc += "-H&W"
    if lab:
        desc += "-CMS-LAB"
    if pos:
        desc += "-POS"
    config = [
        f"interface {intf}",
        f"description [--{desc}--]",
        *base_config,
        *conf[role],
    ]
    if default:
        config.insert(0, f"default interface {intf}")
    if passthrough and role == Role.voip:
        if hw:
            config.append("switchport access vlan 150")
        else:
            config.append("switchport access vlan 100")
    elif hw and role == Role.desktop:
        config.append("switchport access vlan 150")
    elif lab and role == Role.desktop:
        config.append("switchport access vlan 130")
    elif pos and role == Role.desktop:
        config.append("switchport access vlan 230")
    if dry_run:
        logger.info("Dry run, not applying configuration.")
        print(*config, sep="\n")
        return
    if is_port_unconfigured(current_conf):
        logger.success("Port is unconfigured, applying configuration.")
    elif not input("Proceed? [y/N] ").lower().startswith("y"):
        print("Aborted.")
        return
    print(ssh.send_config_set(config))
    logger.info("Running command: write memory")
    print(ssh.send_command("write memory"))


@app.command()
def parse(msg: str | None = None):
    """This parse scrip expects a message from teams roughly in the form of:

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
    import re
    import sys

    p = Settings._prompt()

    if not msg:
        print("Paste the message from teams here, then press Enter followed by Ctrl-D", file=sys.stderr)
        msg = sys.stdin.read()
    assert msg, "No message provided"
    if switch := re.search(r"(\S+).netmgmt.utsc.utoronto.ca", msg, re.I):
        switch = switch.group(1).lower()
    else:
        switch = p.get_string("switch", None)
    if intf := re.search(r"(Te|TenGigabitEthernet)\d/\d/\d+", msg):
        intf = intf.group(0)
    else:
        intf = p.get_string("interface", None)
    if room := re.search(r"Room:? ?(IA.?)?(\d+)", msg, re.I):
        room = room.group(2)
    else:
        room = p.get_string("room", None)
    if label := re.search(r"(Port|Label|Port Label): ?(\S+)", msg):
        label = label.group(2)
    else:
        label = p.get_string("label", None)
    if role_str := re.search(r"Device: ?(.*)", msg):
        role_str = role_str.group(1)
    else:
        role_str = ""
    if re.search(r"(VOIP|Phone)", role_str, re.I):
        role = Role.voip
    elif re.search(r"(Desktop|Computer|Dell AIO|Laptop|Docking Station|Debit Machine|POS|TCard)", role_str, re.I):
        role = Role.desktop
    elif re.search(r"(Printer|Copier)", role_str, re.I):
        role = Role.printer
    else:
        role_name = p.get_from_choices("role", ["voip", "desktop", "printer"], None)
        role = Role(role_name)
    if re.search(r"(H&W|Health ?& ?Wellness)", msg, re.I):
        hw = " --hw"
    else:
        hw = ""
    if re.search(r"((CMS ?)?LAB)", label, re.I):
        lab = " --lab"
    else:
        lab = ""
    if re.search(r"(POS|Debit Machine|TCard)", role_str, re.I):
        pos = " --pos"
    else:
        pos = ""
    if re.search(r"Pass-?Through", msg, re.I):
        passthrough = " --passthrough"
    else:
        passthrough = ""

    cmd = f"uoft-scripts sib-turnup go {switch} {intf} {room} {label} {role} {hw}{lab}{pos}{passthrough}"
    cmd = p.get_string("cmd", None, cmd)
    import subprocess

    subprocess.run(cmd, shell=True)


if __name__ == "__main__":
    app()
