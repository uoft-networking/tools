# Copyright 2021 BlueCat Networks (USA) Inc. and its affiliates.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
"""Values used in the access right API methods in BlueCat Address Manager."""
from ._enum import StrEnum


class AccessRightValues(StrEnum):
    """Values for types of access right in BlueCat Address Manager."""

    AddAccess = "ADD"
    ChangeAccess = "CHANGE"
    FullAccess = "FULL"
    HideAccess = "HIDE"
    ViewAccess = "VIEW"
