# Copyright 2021 BlueCat Networks (USA) Inc. and its affiliates.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
"""Values used in the DHCP custom option API methods in BlueCat Address Manager."""
from ._enum import StrEnum


class DHCPCustomOptionType(StrEnum):
    """DHCP Custom Option Type"""

    BINARY = "BINARY"
    BOOLEAN = "BOOLEAN"
    ENCAPSULATED = "ENCAPSULATED"
    IP4 = "IP4"
    IP4_BLOCK = "IP4_BLOCK"
    IP4_MASK = "IP4_MASK"
    IP4_RANGE = "IP4_RANGE"
    SIGNED_INT_8 = "SIGNED_INT_8"
    SIGNED_INT_16 = "SIGNED_INT_16"
    SIGNED_INT_32 = "SIGNED_INT_32"
    STRING = "STRING"
    TEXT = "TEXT"
    UNSIGNED_INT_8 = "UNSIGNED_INT_8"
    UNSIGNED_INT_16 = "UNSIGNED_INT_16"
    UNSIGNED_INT_32 = "UNSIGNED_INT_32"
    UNSIGNED_INT_64 = "UNSIGNED_INT_64"
