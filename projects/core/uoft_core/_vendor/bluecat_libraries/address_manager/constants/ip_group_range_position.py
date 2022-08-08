# Copyright 2021 BlueCat Networks (USA) Inc. and its affiliates.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
"""Values used in the IPv4 IP group method."""
from ._enum import StrEnum


class IPGroupRangePosition(StrEnum):
    """Constants used to specify the position of the IP group range in the parent network."""

    END_OFFSET = "END_OFFSET"
    START_ADDRESS = "START_ADDRESS"
    START_OFFSET = "START_OFFSET"
