import json
from enum import Enum
from typing import Literal, Any
from pathlib import Path
from pydantic.v1 import BaseModel, Field
from pydantic.v1.types import SecretStr as SecretStrBase, FilePath, DirectoryPath
from ._vendor.netaddr import IPNetwork as IPNetworkBase, IPAddress as IPAddressBase


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
BaseModel.__json_encode__ = BaseModel.dict   # pyright: ignore[reportAttributeAccessIssue]


class IPAddress(IPAddressBase):
    @classmethod
    def __get_validators__(cls):
        def validator(val: Any) -> "IPAddress":
            return cls(val)

        yield validator


class IPv4Address(IPAddressBase):
    @classmethod
    def __get_validators__(cls):
        def validator(val: Any) -> "IPv4Address":
            nv = cls(val)
            assert nv.version == 4, "Invalid IPv4 address"
            return nv

        yield validator


class IPv6Address(IPAddressBase):
    @classmethod
    def __get_validators__(cls):
        def validator(val: Any) -> "IPv6Address":
            nv = cls(val)
            assert nv.version == 6, "Invalid IPv6 address"
            return nv

        yield validator


class IPNetwork(IPNetworkBase):
    @classmethod
    def __get_validators__(cls):
        def validator(val: Any) -> "IPNetwork":
            return cls(val)

        yield validator


class IPv4Network(IPNetworkBase):
    @classmethod
    def __get_validators__(cls):
        def validator(val: Any) -> "IPv4Network":
            nv = cls(val)
            assert nv.version == 4, "Invalid IPv4 network"
            return nv

        yield validator


class IPv6Network(IPNetworkBase):
    @classmethod
    def __get_validators__(cls):
        def validator(val: Any) -> "IPv6Network":
            nv = cls(val)
            assert nv.version == 6, "Invalid IPv6 network"
            return nv

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
    "IPv4Network",
    "IPv6Network",
    "IPAddress",
    "IPv4Address",
    "IPv6Address",
)
