# Copyright 2021 BlueCat Networks (USA) Inc. and its affiliates.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
"""Values used in methods related to zone template in BlueCat Address Manager."""
from ._enum import StrEnum


class ZoneTemplateReapplyMode(StrEnum):
    """Constants used in methods with zone template."""

    UPDATE = "templateReapplyModeUpdate"
    IGNORE = "templateReapplyModeIgnore"
    OVERWRITE = "templateReapplyModeOverwrite"
