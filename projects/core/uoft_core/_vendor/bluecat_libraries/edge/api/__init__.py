# Copyright 2020 BlueCat Networks (USA) Inc. and its affiliates.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
"""Module for exposing the API for working with BlueCat Edge."""

from .client import EdgeClient
from .exceptions import EdgeErrorResponse

__all__ = [
    "EdgeClient",
    "EdgeErrorResponse",
]
