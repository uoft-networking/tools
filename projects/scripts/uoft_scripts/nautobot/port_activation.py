#!/usr/bin/env -S uv run --script

# /// script
# requires-python = ">=3.10, <3.11"
# dependencies = ["scapy", "debugpy", "pynautobot", "uoft_core @ git+https://github.com/uoft-networking/tools#subdirectory=projects/core", "typer"]
# ///

import os
from scapy.all import sniff, conf, Packet
from scapy.interfaces import NetworkInterfaceDict, NetworkInterface
from scapy.contrib import lldp
import typer

from uoft_core import BaseSettings, Field
from uoft_core.types import SecretStr

app = typer.Typer(name='')


class Settings(BaseSettings):
    class Config(BaseSettings.Config):
        app_name = 'utsc_port_activation'
    
    interface_name: str = Field(default=conf.iface.name, prompt=False)
    nautobot_token: SecretStr


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


def _configure_interface():
    s = Settings.from_cache()
    interfaces: NetworkInterfaceDict = conf.ifaces
    if s.interface_name != conf.iface.name:
        target_interface = interfaces.dev_from_name(s.interface_name)
    else:
        target_interface = conf.iface
    user_did_change = _select_target_interface(target_interface)
    if user_did_change:
        s.interface_name = conf.iface.name
        s.interactive_save_config()


def get_lldp_data():
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

    sniff(
        filter=f"ether proto {lldp.LLDP_ETHER_TYPE}",  # BPF filter. see https://www.ibm.com/docs/en/qsip/7.4?topic=queries-berkeley-packet-filters
        prn=process_packet,
        count=1,  # Capture only one packet
    )

    assert res['switch']
    assert res['port']
    assert res['port_desc']
    print("Successfully aquired interface info from LLDP")
    print(f"Switch: {res['switch']}, Port: {res['port']}, Port Description: {res['port_desc']}")
    return res




if __name__ == "__main__":
    _configure_interface()
    lldp_data = get_lldp_data()
        

