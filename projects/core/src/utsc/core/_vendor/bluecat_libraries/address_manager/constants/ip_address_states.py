# Copyright 2021 BlueCat Networks (USA) Inc. and its affiliates.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
"""Values used in IP Address related API methods in BlueCat Address Manager."""
from ._enum import StrEnum


class IPAddressState(StrEnum):
    """Values for types of IP address' states in BlueCat Address Manager."""

    UNALLOCATED = "UNALLOCATED"
    STATIC = "STATIC"
    DHCP_ALLOCATED = "DHCP_ALLOCATED"
    DHCP_FREE = "DHCP_FREE"
    DHCP_RESERVED = "DHCP_RESERVED"
    DHCP_LEASED = "DHCP_LEASED"
    RESERVED = "RESERVED"
    GATEWAY = "GATEWAY"
