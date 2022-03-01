# Copyright 2021 BlueCat Networks (USA) Inc. and its affiliates.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
"""Values for types of the option in BlueCat Address Manager."""
from ._enum import StrEnum


class OptionType(StrEnum):
    """Constants used in the option types."""

    DHCP_CLIENT = "DHCPClient"
    DHCP_SERVICE = "DHCPService"
    DHCP_VENDOR_CLIENT = "DHCPVendorClient"
    DHCP6_CLIENT = "DHCP6Client"
    DHCP6_SERVICE = "DHCP6Service"
    DHCP6_VENDOR_CLIENT = "DHCP6VendorClient"
    DHCP_RAW = "DHCP_RAW"
    DHCPV6_RAW = "DHCPV6_RAW"
    DNS = "DNS"
    DNS_RAW = "DNS_RAW"
