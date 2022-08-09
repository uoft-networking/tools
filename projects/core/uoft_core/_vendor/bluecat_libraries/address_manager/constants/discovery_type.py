# Copyright 2021 BlueCat Networks (USA) Inc. and its affiliates.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
"""
Types of discovery methods to use for the network discovery operation in BlueCat Address Manager.
"""
from ._enum import StrEnum


class DiscoveryType(StrEnum):
    """Constants used for network discovery types."""

    NO_DISCOVERY = "NO_DISCOVERY"
    PINGSWEEP = "PINGSWEEP"
    SNMP = "SNMP"
    SNMP_PINGSWEEP = "SNMP_PINGSWEEP"
