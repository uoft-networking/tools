#!/usr/bin/env -S uv run --script

# /// script
# requires-python = ">=3.10, <3.11"
# dependencies = ["scapy", "debugpy", "pynautobot", "questionary", "uoft_core @ git+https://github.com/uoft-networking/tools#subdirectory=projects/core", "typer"]
# ///

import os
from typing import Literal
from datetime import datetime
from scapy.all import sniff, conf, Packet
from scapy.interfaces import NetworkInterfaceDict, NetworkInterface
from scapy.contrib import lldp
import typer
from questionary import Choice, checkbox

from uoft_core import BaseSettings, Field
from uoft_core.types import SecretStr

app = typer.Typer(name='')


class Settings(BaseSettings):
    class Config(BaseSettings.Config):
        app_name = 'utsc_port_activation'
    
    nautobot_token: SecretStr
    target_intfs: list[str] | Literal[''] = Field('', prompt=False)
    all_intfs: list[str] | Literal[''] = Field('', prompt=False)


def _select_target_interface(iface: NetworkInterface) -> bool:
    "Prompts user whether or not to change the target interface for LLDP monitoring, return value is bool indicating if user changed target interface"
    print("In order for this program to run correctly, it needs to monitor a specific interface for LLDP packets")
    print("The default selected interface is:")
    print("Name: ", iface.name)                              
    print('Network name: ', iface.network_name)
    print("Description: ", iface.description)
    print("Index: ", iface.index)

    if 'y' not in input("Would you like to change it? [y or n]: ").strip().lower():
        return False
    
    print("Index \t Name \t Network Name \t Description")
    print("-"*50)
    indexes = []
    for iface in conf.ifaces.values():
        print(f"{iface.index}\t{iface.name}\t{iface.network_name}\t{iface.description}")
        indexes.append(iface.index)
    while True:
        chosen_index = input("Enter the index of the interface you want to use: ").strip()
        try:
            chosen_index = int(chosen_index)
            assert chosen_index in indexes
            break
        except Exception:
            print("That is not a valid index number, please try again")
    chosen_iface = conf.ifaces.dev_from_index(chosen_index)
    conf.iface = chosen_iface

    return True


def get_or_update_intfs_list() -> list[NetworkInterface]:
    s = Settings.from_cache()
    choices = []
    all_intfs = []
    for i in conf.ifaces.values():
        choices.append(Choice(f"{i.name}: {i.description}", i.name))
        all_intfs.append(i.name)
    if s.target_intfs == '' or s.all_intfs == '':
        print("In order for this program to run correctly, it needs to monitor a specific interface for LLDP packets")
        s.target_intfs = checkbox("Please select all ethernet interfaces in your system", choices).unsafe_ask()
        s.all_intfs = all_intfs
        s.interactive_save_config()
    elif set(s.all_intfs) != set(all_intfs):
        print("The list of network adapters in your system appears to have changed since you last ran this program")
        s.target_intfs = checkbox("Please select all ethernet interfaces in your system", choices).unsafe_ask()
        s.all_intfs = all_intfs
        s.interactive_save_config()
    return [i for i in conf.ifaces.values() if i.name in s.target_intfs]


def get_lldp_data(intfs: list[NetworkInterface]):
    print("Listening for LLDP packet...")
    print("Please plug in network cable now.")
    print("If network cable is already plugged in, please unplug it and plug it back in")

    res = dict(
        switch=None, 
        port=None, 
        port_desc=None)

    def process_packet(packet: Packet):
        res['switch'] = packet.getlayer(lldp.LLDPDUSystemName).system_name.decode()  # pyright: ignore[reportOptionalMemberAccess]
        res['port'] = packet.getlayer(lldp.LLDPDUPortID).id.decode()  # pyright: ignore[reportOptionalMemberAccess]
        res['port_desc'] = packet.getlayer(lldp.LLDPDUPortDescription).description.decode()  # pyright: ignore[reportOptionalMemberAccess]
        print(res, datetime.now())

    sniff(
        filter=f"ether proto {lldp.LLDP_ETHER_TYPE}",  # BPF filter. see https://www.ibm.com/docs/en/qsip/7.4?topic=queries-berkeley-packet-filters
        prn=process_packet,
        iface=intfs,
        count=300,  # Capture only one packet
    )

    assert res['switch']
    assert res['port']
    assert res['port_desc']
    print("Successfully aquired interface info from LLDP")
    print(f"Switch: {res['switch']}, Port: {res['port']}, Port Description: {res['port_desc']}")
    return res




if __name__ == "__main__":
    intfs = get_or_update_intfs_list()
    lldp_data = get_lldp_data(intfs)

