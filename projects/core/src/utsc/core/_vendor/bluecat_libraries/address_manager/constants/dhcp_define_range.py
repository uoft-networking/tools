# Copyright 2021 BlueCat Networks (USA) Inc. and its affiliates.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
"""Values used in the DHCP Define Range API methods in BlueCat Address Manager."""
from ._enum import StrEnum


class DHCPDefineRange(StrEnum):
    """DHCP Define Range"""

    AUTOCREATE_BY_SIZE = "AUTOCREATE_BY_SIZE"
    OFFSET_AND_SIZE = "OFFSET_AND_SIZE"
    START_ADDRESS_AND_SIZE = "START_ADDRESS_AND_SIZE"
    OFFSET_AND_PERCENTAGE = "OFFSET_AND_PERCENTAGE"
