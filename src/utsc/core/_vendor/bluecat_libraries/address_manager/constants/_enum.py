# Copyright 2021 BlueCat Networks (USA) Inc. and its affiliates.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
"""Enumeration class to be used in constant classes in BlueCat Address Manager."""
from enum import Enum


class StrEnum(str, Enum):
    """Enum where members are also (and must be) strings"""

    def __str__(self):
        return str(self.value)
