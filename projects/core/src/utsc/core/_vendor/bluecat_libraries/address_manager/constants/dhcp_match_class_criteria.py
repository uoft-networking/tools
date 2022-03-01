# Copyright 2021 BlueCat Networks (USA) Inc. and its affiliates.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
"""Values used in the DHCP match class methods in BlueCat Address Manager."""
from ._enum import StrEnum


class DHCPMatchClass(StrEnum):
    """Values for types of DHCP match class."""

    DHCP_CLASS_AGENT_CIRCUIT_ID = "MATCH_AGENT_CIRCUIT_ID"
    DHCP_CLASS_AGENT_REMOTE_ID = "MATCH_AGENT_REMOTE_ID"
    DHCP_CLASS_CLIENT_ID = "MATCH_DHCP_CLIENT_ID"
    DHCP_CLASS_CUSTOM_MATCH = "CUSTOM_MATCH"
    DHCP_CLASS_CUSTOM_MATCH_IF = "CUSTOM_MATCH_IF"
    DHCP_CLASS_HARDWARE = "MATCH_HARDWARE"
    DHCP_CLASS_VENDOR_ID = "MATCH_DHCP_VENDOR_ID"
