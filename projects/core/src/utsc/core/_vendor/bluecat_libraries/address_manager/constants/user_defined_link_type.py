# Copyright 2021 BlueCat Networks (USA) Inc. and its affiliates.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
"""
Values for sourceEntityTypes and destinationEntityTypes parameters.
The objects of type 'User-Defined Link field' have a type governing certain characteristics of the field and the values
that the field may hold.
"""
from ._enum import StrEnum


class UserDefinedLinkEntityType(StrEnum):
    """
    Values for sourceEntityTypes and destinationEntityTypes parameters.
    """

    DENY_MAC_POOL = "DenyMACPool"
    DEVICE = "Device"
    DHCP4_RANGE = "IP4DHCPRange"
    DHCP6_RANGE = "IP6DHCPRange"
    IP4_ADDRESS = "IP4Addr"
    IP4_BLOCK = "IP4Block"
    IP4_IP_GROUP = "IP4IPGroup"
    IP4_NETWORK = "IP4Network"
    IP4_RANGED = "IP4Ranged"
    IP6_ADDRESS = "IP6Addr"
    IP6_BLOCK = "IP6Block"
    IP6_NETWORK = "IP6Network"
    IP6_RANGED = "IP6Ranged"
    MAC_ADDRESS = "MACAddr"
    MAC_POOL = "MACPool"
    SERVER = "Server"
    SERVER_GROUP = "ServerGroup"
    VIEW = "View"
    ZONE = "Zone"
