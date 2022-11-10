from enum import Enum
from typing import Literal
from pathlib import Path
from pydantic import BaseModel
from pydantic.types import SecretStr, FilePath, DirectoryPath

# All data types that we endeavor to support in uoft_core
# TODO: merge types from switchconfig.types into here
# TODO: subclass SecretStr to add a "__rich_repr__" method. Should fix issue of SecretStr value showing up in stack traces

class StrEnum(str, Enum):
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}.{self.name}"

    def __str__(self) -> str:
        return self.name

    @classmethod
    def from_str(cls, name: str):
        return cls.__members__[name]

    @classmethod
    def __get_validators__(cls):
        def validator(val: str) -> "StrEnum":
            return cls.from_str(val)  # type: ignore
        yield validator

__all__ = (
    "Enum",
    "Literal",
    "Path",
    "BaseModel",
    "SecretStr",
    "FilePath",
    "DirectoryPath",
    "StrEnum",
)