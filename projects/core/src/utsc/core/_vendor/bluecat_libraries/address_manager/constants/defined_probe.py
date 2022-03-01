# Copyright 2021 BlueCat Networks (USA) Inc. and its affiliates.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
"""Values used by data collection probes in BlueCat Address Manager."""
from enum import IntEnum

from ._enum import StrEnum


class DefinedProbe(StrEnum):
    """Values of pre-defined SQL queries that have been triggered to collect data."""

    LEASE_COUNT_PER_DATE = "LEASE_COUNT_PER_DATE"
    NETWORK_BLOOM = "NETWORK_BLOOM"


class DefinedProbeStatus(IntEnum):
    """Values of status codes for the data collection probe"""

    INIT = 0
    INQUEUE = 1
    PROCESSING = 2
    COMPLETED = 3
