#!/usr/bin/env -S uv run --script

# /// script
# requires-python = ">=3.10, <3.11"
# dependencies = [
#     "uoft-core @ file:///Users/alex/uoft_core-2025.2.dev68+g5681129b.d20251020-py3-none-any.whl",
#     "scapy",
#     "debugpy",
#     "pynautobot",
#     "questionary",
#     "typer",
# ]
# ///
"""
This is the UTSC port activation tool.

This script listens for LLDP packets on specified network interfaces to determine
the connected switch and port. It then collects additional information from the user
and triggers a Nautobot job to activate the port accordingly.
"""

import os
import sys
from pathlib import Path
from platform import platform
import re
import subprocess
from datetime import datetime
from typing import TypedDict
import time

from scapy.all import sniff, conf, Packet
from scapy.interfaces import NetworkInterface
from scapy.contrib import lldp
import typer
from questionary import text, select, password, confirm
from pynautobot import api, RequestError
from pynautobot.models.extras import Jobs
from rich.progress import Progress

from uoft.core import logging, console

NAUTOBOT_URL = "https://engine.netmgmt.utsc.utoronto.ca"

app = typer.Typer(
    name="port-activation",
    help=__doc__,  # Use this module's docstring as the main program help text
)

logger = logging.getLogger(__name__)


# FIXME: this function is duplicated from uoft_scripts/__init__.py
# once we have pants-based packaging sorted, we should be able to import this
# from there instead of maintaining a duplicate copy
def interface_name_normalize(intf_name: str) -> str:
    """
    Normalizes network interface names to their full canonical forms.

    This function converts common shorthand interface names (e.g., "Et99", "Te1/0/1")
    to their full names (e.g., "Ethernet99", "TenGigabitEthernet1/0/1") for consistency,
    such as when performing lookups in systems like Nautobot. The normalization is
    idempotent and avoids transforming already normalized names (e.g., "Ethernet99"
    remains unchanged).

    Supported shorthand expansions:
        - "Et" → "Ethernet"
        - "Fo" → "FortyGigabitEthernet"
        - "Te" → "TenGigabitEthernet"
        - "Gi" → "GigabitEthernet"
        - "Fa" → "FastEthernet"
        - "Po" → "Port-Channel"
        - "Lo" → "Loopback"
        - "Ma" → "Management"

    Args:
        intf_name (str): The interface name to normalize.

    Returns:
        str: The normalized, full interface name.
    """
    # This would be so much simpler to implement with a regex,
    # but i think there'd be a heavier performance cost
    match intf_name[:2]:
        case "Et" if not intf_name[:3] == "Eth":
            return intf_name.replace("Et", "Ethernet", 1)
        case "Fo" if not intf_name[:3] == "For":
            return intf_name.replace("Fo", "FortyGigabitEthernet", 1)
        case "Te" if not intf_name[:3] == "Ten":
            return intf_name.replace("Te", "TenGigabitEthernet", 1)
        case "Gi" if not intf_name[:3] == "Gig":
            return intf_name.replace("Gi", "GigabitEthernet", 1)
        case "Fa" if not intf_name[:3] == "Fas":
            return intf_name.replace("Fa", "FastEthernet", 1)
        case "Po" if not intf_name[:3] == "Por":
            return intf_name.replace("Po", "Port-Channel", 1)
        case "Lo" if not intf_name[:3] == "Loo":
            return intf_name.replace("Lo", "Loopback", 1)
        case "Ma" if not intf_name[:3] == "Man":
            return intf_name.replace("Ma", "Management", 1)
        case _:
            # If the interface name is already in its full form, return it as is
            # This is idempotent, so calling this function on an already normalized name will not change it
            return intf_name


def get_or_update_intfs_list(interface: str | None = None) -> list[NetworkInterface]:
    if interface:
        if interface not in conf.ifaces:
            raise ValueError(f"Interface {interface} not found on this system")
        return [conf.ifaces[interface]]

    # if macos:
    if platform().startswith("macOS"):
        # On MacOS, interface selection is easy. We just parse the output of `ifconfig`
        # and look for `enX` interfaces that have `1000baseT` in their media type field
        intfs = []
        ifconfig_output = subprocess.run(
            ["ifconfig"], capture_output=True, text=True, check=True
        ).stdout
        for intf_block in re.split(r"\n(?!\t)", ifconfig_output, flags=re.MULTILINE):
            if "media: " not in intf_block or "1000baseT" not in intf_block:
                continue
            intf_name, _, intf_block = intf_block.partition(":")
            intfs.append(conf.ifaces[intf_name])
        return intfs
    else:
        raise NotImplementedError("This script currently only supports MacOS")
    # s = Settings.from_cache()
    # choices = []
    # all_intfs = []
    # for i in conf.ifaces.values():
    #     choices.append(Choice(f"{i.name}: {i.description}", i.name))
    #     all_intfs.append(i.name)
    # if s.target_intfs == '' or s.all_intfs == '':
    #     print("In order for this program to run correctly, it needs to monitor a specific interface for LLDP packets")
    #     s.target_intfs = checkbox("Please select all ethernet interfaces in your system", choices).unsafe_ask()
    #     s.all_intfs = all_intfs
    #     s.interactive_save_config()
    # elif set(s.all_intfs) != set(all_intfs):
    #     print("The list of network adapters in your system appears to have changed since you last ran this program")
    #     s.target_intfs = checkbox("Please select all ethernet interfaces in your system", choices).unsafe_ask()
    #     s.all_intfs = all_intfs
    #     s.interactive_save_config()
    # return [i for i in conf.ifaces.values() if i.name in s.target_intfs]


class LLDPData(TypedDict):
    switch: str
    port: str
    port_desc: str
    packet: Packet


def get_lldp_data(intfs: list[NetworkInterface]) -> LLDPData:
    logger.info("Please plug in network cable now if it's not already plugged in.")
    logger.info("Listening for LLDP packet...")
    logger.info("Press Ctrl+C to abort.")
    logger.warning(
        "This process may take up to 60 seconds depending on the switch you are connected to."
    )
    progress = Progress(console=console.console())
    progress.add_task("Waiting for LLDP packet...", total=None)
    progress.start()

    res = dict(switch=None, port=None, port_desc=None, packet=None)

    def process_packet(packet: Packet):
        res["switch"] = packet.getlayer(
            lldp.LLDPDUSystemName
        ).system_name.decode()  # pyright: ignore[reportOptionalMemberAccess]
        res["port"] = packet.getlayer(
            lldp.LLDPDUPortID
        ).id.decode()  # pyright: ignore[reportOptionalMemberAccess]
        res["port_desc"] = packet.getlayer(
            lldp.LLDPDUPortDescription
        ).description.decode()  # pyright: ignore[reportOptionalMemberAccess]

        # Store the entire packet for later use
        res["packet"] = packet  # pyright: ignore[reportArgumentType]

        logger.debug(
            f"Received LLDP packet from switch {res['switch']} on port {res['port']} "
            f"through interface {packet.sniffed_on} at {datetime.now().isoformat()}"
        )

    sniff(
        filter=f"ether proto {lldp.LLDP_ETHER_TYPE}",  # BPF filter. see https://www.ibm.com/docs/en/qsip/7.4?topic=queries-berkeley-packet-filters
        prn=process_packet,
        iface=intfs,
        count=1,  # Capture only one packet
    )
    progress.stop()

    assert res["switch"]
    assert res["port"]
    assert res["port_desc"]
    logger.success(
        "Aquired the following data through LLDP: Switch: "
        f"{res['switch']}, Port: {res['port']}, Port Description: {res['port_desc']}"
    )
    return res  # pyright: ignore[reportReturnType]


def remote_debugger():
    import debugpy

    debugpy.listen(("localhost", 5678))
    print("Waiting for debugger to attach...")
    debugpy.wait_for_client()
    print("Debugger attached.")


def nautobot_api():
    token_path = Path("/var/root/.nautobot_token")
    if not token_path.exists():
        logger.warning("Nautobot token file not found at /var/root/.nautobot_token.")
        token = password(
            "Please enter your Nautobot API token: ", validate=lambda x: len(x) == 40
        ).unsafe_ask()
        token_path.write_text(token)
        token_path.chmod(0o600)
    else:
        token = token_path.read_text().strip()
        assert len(token) == 40, "Nautobot token appears to be invalid length"

    nautobot = api(url=NAUTOBOT_URL, token=token)

    return nautobot


def prompt_for_port_label() -> str:
    logger.info("Please enter the port label for this port.")
    logger.info("Should include switch closet id (ex: '2C'), room number (ex: 'SW209'), port label (ex: 'D118')")
    return text(
        "Port label: "
    ).unsafe_ask()


@app.command()
def main(
    debug: bool = typer.Option(False, help="Enable debug mode"),
    interface: str | None = typer.Option(
        None, help="Specify a single network interface to monitor for LLDP packets"
    ),
):
    # make sure we're running as root
    if os.geteuid() != 0:
        print("This tool requires root privileges to run. Restarting with sudo...")
        if scie := os.environ.get("SCIE"):
            # If we're running inside of a scie, __file__ and sys.argv[0] may not point to the correct script
            # in order to re-exec with sudo reliably, we need to point it to the path of the scie itself, and
            # that's what the SCIE env var (which is set by the SCIE bootstrapper) provides
            target = scie
        else:
            target = sys.argv[0]
        os.execvp("sudo", ["sudo", target, *sys.argv[1:]])

    if debug:
        remote_debugger()
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    logger.info("Starting port activation script...")
    intfs = get_or_update_intfs_list(interface)
    if len(intfs) == 0:
        logger.error("No ethernet interfaces found to monitor for LLDP packets")
        logger.warning("Specifically, no interfaces with 1000baseT media type were found when running `ifconfig`")
        sys.exit(1)
    logger.info("Monitoring interfaces: %s", [i.name for i in intfs])
    lldp_data = get_lldp_data(intfs)

    # Now we need the rest of the info to send to Nautobot

    existing_port_label = lldp_data["port_desc"].strip()
    
    if existing_port_label and existing_port_label != lldp_data["port"]:
        logger.info(f"Port description found from LLDP: '{existing_port_label}'")
        logger.info("Should ideally look something like '3W-AC313D-A08' or '2C-SW209-D118', etc")
        if confirm(
            f"Is '{existing_port_label}' correct?",
            instruction="Press 'Enter' to accept, or 'N' to enter a different port label",
        ).unsafe_ask():
            port_label = existing_port_label
        else:
            port_label = prompt_for_port_label()
    else:
        port_label = prompt_for_port_label()
    role = select(
        "What kind of device are you looking to activate?",
        choices=[
            "Desktop PC",
            "VOIP Phone",
            "Other",
        ],
    ).unsafe_ask()

    nautobot = nautobot_api()

    progress = Progress(console=console.console())
    task_id = progress.add_task("Activating port...", total=None)
    progress.start()
    job = nautobot.extras.jobs.run( # pyright: ignore[reportAttributeAccessIssue, reportCallIssue]
        job_name='Helpdesk Port Activation', data=dict(
            device=lldp_data["switch"].partition(".")[0], # lldp switch name is sometimes FQDN, sometimes not
            interface=lldp_data["port"],
            role=role,
            port_label=port_label,
            extra_data=dict(
                lldp_packet=lldp_data["packet"].command(),
                port_desc=lldp_data["port_desc"],
            ),
        )
    )
    jr = job.job_result  # pyright: ignore
    while jr.status.value in ["PENDING", "STARTED"]: # pyright: ignore
        jr = nautobot.extras.job_results.get(jr.id) # pyright: ignore
        progress.update(task_id, description=f"Activating port... (status: {jr.status.value})") # pyright: ignore
        time.sleep(0.5)

    progress.stop()
    if jr.status.value == "FAILURE":  # pyright: ignore
        logger.error(f"Failed to activate port due to: {jr.result.exc_type}") # pyright: ignore
        logger.warning("Please notify the networking team for assistance and share the following context with them:")
        logger.warning(f"{NAUTOBOT_URL}/extras/job-results/{jr.id}/") # pyright: ignore
    else:
        logger.success("Port activated successfully!")
        logger.info("Please disconnect and reconnect the network cable to test connectivity.")
        logger.info("If necessary, the networking team can review the port activation details at the following URL:")
        logger.info(f"{NAUTOBOT_URL}/extras/job-results/{jr.id}/") # pyright: ignore


if __name__ == "__main__":
    try:
        app()
    except KeyboardInterrupt:
        logger.warning("Script interrupted by user. Exiting...")
        sys.exit(1)
