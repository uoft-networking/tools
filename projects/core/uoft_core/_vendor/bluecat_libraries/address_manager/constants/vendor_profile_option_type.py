# Copyright 2021 BlueCat Networks (USA) Inc. and its affiliates.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
"""Values used in the Vendor Profile option API methods in BlueCat Address Manager."""
from ._enum import StrEnum


class VendorProfileOptionType(StrEnum):
    """Vendor Profile Option Types"""

    BINARY = "BINARY"
    BOOLEAN = "BOOLEAN"
    ENCAPSULATED = "ENCAPSULATED"
    IP4 = "IP4"
    IP4_MASK = "IP4_MASK"
    SIGNED_INT_8 = "SIGNED_INT_8"
    SIGNED_INT_16 = "SIGNED_INT_16"
    SIGNED_INT_32 = "SIGNED_INT_32"
    STRING = "STRING"
    TEXT = "TEXT"
    UNSIGNED_INT_8 = "UNSIGNED_INT_8"
    UNSIGNED_INT_16 = "UNSIGNED_INT_16"
    UNSIGNED_INT_32 = "UNSIGNED_INT_32"
    UNSIGNED_INT_64 = "UNSIGNED_INT_64"
