# Copyright 2021 BlueCat Networks (USA) Inc. and its affiliates.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
"""
Values defined for SNMP Versions for SNMP Services in BlueCat Address Manager.
"""
from ._enum import StrEnum


class SNMPVersion(StrEnum):
    """Constants defined for SNMP versions."""

    V1 = "v1"
    V2C = "v2c"
    V3 = "v3"
