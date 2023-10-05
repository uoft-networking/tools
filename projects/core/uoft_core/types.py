import json
from enum import Enum
from typing import Literal, Any
from pathlib import Path
from pydantic import BaseModel, Field
from pydantic.types import SecretStr as SecretStrBase, FilePath, DirectoryPath
from ._vendor.netaddr import IPNetwork, IPAddress


_json_default = json.JSONEncoder.default

def _custom_json_default_encoder(self: json.JSONEncoder, o: Any) -> Any:
    # this function works exactly like the default json.JSONEncoder.default
    # except that it also handles objects which have a __json_encode__ method
    if hasattr(o, "__json_encode__"):
        return o.__json_encode__()
    if isinstance(o, set):
        return list(o)
    return _json_default(self, o)


# monkey-patch the default json encoder to handle objects with a __json_encode__ method
# # We absolutely should not be doing this, but the stdlib json module does not
# provide a way to override the default encoder.
json.JSONEncoder.default = _custom_json_default_encoder

# monkey-patch BaseModel to be JSON serializable
BaseModel.__json_encode__ = BaseModel.dict # type: ignore


class IPv4Address(IPAddress):
    @classmethod
    def __get_validators__(cls):
        def validator(val: Any) -> "IPv4Address":
            return cls(val).ipv4()  # type: ignore

        yield validator


class IPv6Address(IPAddress):
    @classmethod
    def __get_validators__(cls):
        def validator(val: Any) -> "IPv6Address":
            return cls(val).ipv6()  # type: ignore

        yield validator


class IPv4Network(IPNetwork):
    @classmethod
    def __get_validators__(cls):
        def validator(val: Any) -> "IPv4Network":
            return cls(val).ipv4()  # type: ignore

        yield validator


class IPv6Network(IPNetwork):
    @classmethod
    def __get_validators__(cls):
        def validator(val: Any) -> "IPv6Network":
            return cls(val).ipv6()  # type: ignore

        yield validator

# All data types that we endeavor to support in uoft_core
# TODO: merge types from switchconfig.types into here

class SecretStr(SecretStrBase):
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}('**********')"

    def __json_encode__(self):
        return self.get_secret_value()



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

    def __json_encode__(self):
        return self.name


__all__ = (
    "Enum",
    "Literal",
    "Any",
    "Path",
    "BaseModel",
    "Field",
    "SecretStr",
    "FilePath",
    "DirectoryPath",
    "StrEnum",
    "IPNetwork",
    "IPAddress",
)
