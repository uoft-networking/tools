# Copyright 2021 BlueCat Networks (USA) Inc. and its affiliates.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
"""Values used in the DNS Deployment Role API methods in BlueCat Address Manager."""
from ._enum import StrEnum


class DNSDeploymentRoleType(StrEnum):
    """DNS Deployment Role Type"""

    AD_MASTER = "AD_MASTER"
    FORWARDER = "FORWARDER"
    MASTER = "MASTER"
    MASTER_HIDDEN = "MASTER_HIDDEN"
    NONE = "NONE"
    RECURSION = "RECURSION"
    SLAVE = "SLAVE"
    SLAVE_STEALTH = "SLAVE_STEALTH"
    STUB = "STUB"
