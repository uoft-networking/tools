from . import settings
from .api import phpIPAMRESTAPIClient
from collections import defaultdict
import ipaddress
import sys


def phpipam_ansible_lookup(serial):
    s = settings()
    with (phpIPAMRESTAPIClient(s.phpipam_hostname, s.username, s.password.get_secret_value(), s.app_id) as host):
        configuration_dict = defaultdict(str)
        devices = host.get_all_addresses_raw().json()["data"]
        device_info = next((device for device in devices if device["custom_Serial"] == f"{serial}"), None)
        if device_info is None:
            print(f"No match found.\n")
            sys.exit()
        subnet_info = host.subnet_search_raw(device_info["subnetId"]).json()["data"]
        vlan_info = host.vlan_search_raw(subnet_info["vlanId"]).json()["data"]
        location_info = host.get_location_raw(subnet_info["location"]).json()["data"]

        configuration_dict["gateway_address"] = set_gateway(subnet_info["subnet"]).exploded
        configuration_dict["mgmt_vlan_id"] = device_info["id"]
        configuration_dict["ip_address"] = device_info["ip"]
        configuration_dict["hostname"] = device_info["hostname"]
        configuration_dict["uplink_device"] = device_info["port"]
        configuration_dict["serial"] = device_info["custom_Serial"]
        configuration_dict["subnet_mask"] = subnet_info["mask"]
        configuration_dict["network_address"] = subnet_info["subnet"]
        configuration_dict["mgmt_vlan_name"] = vlan_info["name"]
        configuration_dict["building_code"] = location_info["name"]

        return dict(configuration_dict)


def set_gateway(network_address):
    return ipaddress.ip_address(network_address) + 1
