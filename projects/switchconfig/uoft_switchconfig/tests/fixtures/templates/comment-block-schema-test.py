"""
TODO: document this file
"""

from ipaddress import IPv4Network

class Filters:
    """
    Container class for a bunch of filter functions.
    Every function defined in this class is made available as a jinja filter
    """

    @staticmethod
    def gateway_ip(subnet: str) -> str:
        """
        for a given subnet in CIDR notation, return the IP address of the default gateway.
        Example: {{subnet|gateway_ip}} where example subnet 10.0.0.0/24 produces 10.0.0.1
        """
        return str(next(IPv4Network(subnet).hosts()))

    @staticmethod
    def network_address(subnet: str) -> str:
        """
        for a given subnet in CIDR notation, return the network address of that network
        """
        return str(IPv4Network(subnet).network_address)

    @staticmethod
    def network_mask(subnet: str) -> str:
        """
        for a given subnet in CIDR notation, return the network address of that network
        """
        return str(IPv4Network(subnet).netmask)

    @staticmethod
    def remap(key: str, map_name: str) -> str:
        """look up a key in a specific map/dict, and return its value"""
        m = {
            "usages": {
                "podium": "av",
                "deskswitch": "a1",
                "access": "a1",
            }
        }
        d = m[map_name]
        return d[key]