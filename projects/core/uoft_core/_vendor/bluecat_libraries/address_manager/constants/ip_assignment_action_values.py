# Copyright 2021 BlueCat Networks (USA) Inc. and its affiliates.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
"""Values used in IP Assignment API methods in BlueCat Address Manager."""
from ._enum import StrEnum


class IPAssignmentActionValues(StrEnum):
    """Values for types of actions in BlueCat Address Manager."""

    MAKE_STATIC = "MAKE_STATIC"
    MAKE_RESERVED = "MAKE_RESERVED"
    MAKE_DHCP_RESERVED = "MAKE_DHCP_RESERVED"
