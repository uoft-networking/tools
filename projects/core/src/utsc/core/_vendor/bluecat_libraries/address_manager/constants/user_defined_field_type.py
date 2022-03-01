# Copyright 2020 BlueCat Networks (USA) Inc. and its affiliates.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
"""Values for type of user-defined field.

The objects of type 'User-defined field' have a type governing certain characteristics of the field and the values
that the field may hold.
"""
from ._enum import StrEnum


class UserDefinedFieldType(StrEnum):
    """Values for user-defined field parameters."""

    BOOLEAN = "BOOLEAN"
    DATE = "DATE"
    EMAIL = "EMAIL"
    INTEGER = "INTEGER"
    LONG = "LONG"
    TEXT = "TEXT"
    URL = "URL"
    WORKFLOW = "WORKFLOW"
