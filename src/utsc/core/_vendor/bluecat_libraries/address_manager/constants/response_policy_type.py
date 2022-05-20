# Copyright 2021 BlueCat Networks (USA) Inc. and its affiliates.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
"""Values used in methods related to DNS response policies in BlueCat Address Manager."""
from ._enum import StrEnum


class ResponsePolicy(StrEnum):
    """Constants used in to define the response policy type."""

    BLACKHOLE = "BLACKHOLE"
    BLACKLIST = "BLACKLIST"
    REDIRECT = "REDIRECT"
    WHITELIST = "WHITELIST"
