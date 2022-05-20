# Copyright 2020 BlueCat Networks (USA) Inc. and its affiliates.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# pylint: disable=C0112,C0115,C0116,W0511,W0613;
"""Functions related to the conversion of data to and from BlueCat Address Manager's API."""
import re
from typing import Union

from ...http_client.exceptions import GeneralError


def deserialize_joined_key_value_pairs(value: str, item_sep="|", keyvalue_sep="=") -> dict:
    """Convert a single-string representation into a dictionary."""

    # if not value.endswith('|'):
    #     raise GeneralError('Serialized properties (key-value pairs) should end with a pipe character.')
    if value.endswith(item_sep):
        value = value[:-1]

    # NOTE: A straightforward "split by pipes and then split by equal signs" would cause erroneous interpretations,
    # because of the presence of escaped pipes in both names and values.
    # NOTE: Currently, equal signs are not escaped, although they may be present in both the name and the value of a
    # property. We can have "=====" as a key-value pair and no way of knowing is it "=" : "===", "==": "==", or
    # "===": "=". Thus, the first occurring equal sign is treated as a separator.
    pairs = []
    escaped = False
    token = []
    for char in value:
        if char == "\\":
            if escaped:
                token.append("\\")
                escaped = False
            else:
                escaped = True
            continue
        if char == "0" and escaped:
            token.append("\\")
            escaped = False
        if char == item_sep:
            if escaped:
                token.append(item_sep)
                escaped = False
            else:
                if not token:
                    raise GeneralError("Empty key-value pair in serialized properties.")
                pairs.append("".join(token))
                token = []
            continue
        token.append(char)
    if escaped:
        raise GeneralError("Incomplete escape sequence in serialized properties (key-value pairs).")
    if token:
        pairs.append("".join(token))
    pairs = map(lambda item: item.split(keyvalue_sep, maxsplit=1), pairs)
    return dict(pairs)


def serialize_joined_key_value_pairs(values: dict, item_sep="|", keyvalue_sep="=") -> str:
    if not values:
        return ""

    result = item_sep.join(
        "{key}{keyvalue_sep}{value}".format(
            key=escape(key), keyvalue_sep=keyvalue_sep, value=escape(str(value))
        )
        for key, value in values.items()
    )
    return result + item_sep if result else ""


def serialize_joined_values(values: list, item_sep=",") -> str:
    if not values:
        return ""
    result = item_sep.join(str(x) for x in values)
    return result


def serialize_possible_list(value: Union[str, "list[str]", "list[list[str]]"]) -> str:
    """
    If ``value`` is a list, then either all inner elements must be lists, or no element can be a
    list. Otherwise, no behavior is guaranteed.
    """
    # Simple value case
    if not isinstance(value, list):
        return str(value)

    # Empty list case
    if not value:
        return ""

    # 1D case
    if not isinstance(value[0], list):
        return ",".join(str(x) for x in value)

    # 2D case
    out = []
    for inner in value:
        x = ",".join(str(x) for x in inner)
        out.append("{" + x + "}")
    return ",".join(out)


def deserialize_possible_list(value: str) -> Union[str, "list[str]", "list[list[str]]"]:
    # We rely on the fact that individual values do not contain `{`, `}`, or `,`

    # 2D case
    if value.startswith("{"):
        return [item.group(1).split(",") for item in re.finditer(r"{([^}]*)}", value)]

    # Empty string becomes [""]
    out = value.split(",")
    return out if len(out) > 1 else out[0]


def escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("|", "\\|")


def unescape(value: str) -> str:
    return value.replace("\\|", "|").replace("\\\\", "\\")
