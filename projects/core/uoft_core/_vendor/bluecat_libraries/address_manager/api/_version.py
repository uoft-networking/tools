# Copyright 2020 BlueCat Networks (USA) Inc. and its affiliates.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# pylint: disable=protected-access; Access private field of non-self Version arguments.
"""Definition of a class for comparing versions."""
from typing import Union


class Version:
    """Version class."""

    def __new__(cls, ver: Union["Version", str]) -> "Version":
        """String input must be a dot-separated list of integers (e.g. '1.2.3')."""
        if isinstance(ver, Version):
            return ver
        if isinstance(ver, str):
            o = object.__new__(cls)
            o.__v = tuple(int(x) for x in ver.split("."))
            return o
        raise TypeError(
            f"Invalid argument type for {Version.__name__}(): {repr(type(ver).__name__)}"
        )

    def __str__(self) -> str:
        return ".".join(str(x) for x in self.__v)

    def __repr__(self) -> str:
        return f"{Version.__name__}({repr(str(self))})"

    def __cmp_helper(self, op: str, other: Union["Version", str]) -> bool:
        try:
            other = Version(other)
        except TypeError:
            return NotImplemented
        self, other = self.__v, other.__v
        if len(self) < len(other):
            self += (0,) * (len(other) - len(self))
        else:
            other += (0,) * (len(self) - len(other))
        return getattr(self, op)(other)

    def __eq__(self, other: Union["Version", str]) -> bool:
        return self.__cmp_helper("__eq__", other)

    def __ne__(self, other: Union["Version", str]) -> bool:
        return self.__cmp_helper("__ne__", other)

    def __lt__(self, other: Union["Version", str]) -> bool:
        return self.__cmp_helper("__lt__", other)

    def __le__(self, other: Union["Version", str]) -> bool:
        return self.__cmp_helper("__le__", other)

    def __gt__(self, other: Union["Version", str]) -> bool:
        return self.__cmp_helper("__gt__", other)

    def __ge__(self, other: Union["Version", str]) -> bool:
        return self.__cmp_helper("__ge__", other)
