from collections.abc import Iterator
import json
from enum import Enum
from typing import Literal, Any
from pathlib import Path
from pydantic import BaseModel, Field
from pydantic.types import SecretStr as SecretStrBase, FilePath, DirectoryPath


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

try:
    from netaddr import IPNetwork as IPNetworkBase, IPAddress as IPAddressBase

    class IPAddress(IPAddressBase):
        @classmethod
        def __get_validators__(cls):
            def validator(val: str) -> "IPAddress":
                return cls(val)

            yield validator

        def __json_encode__(self):
            return str(self)

    class IPNetwork(IPNetworkBase):
        @classmethod
        def __get_validators__(cls):
            def validator(val: str) -> "IPNetwork":
                return cls(val)

            yield validator

        def __json_encode__(self):
            return str(self)

        @property
        def ip(self) -> IPAddress:
            return IPAddress(super().ip)

        @property
        def network(self) -> IPAddress:
            return IPAddress(super().network)

        @property
        def broadcast(self) -> IPAddress | None:
            res = super().broadcast
            if res is None:
                return None
            return IPAddress(res)

        @property
        def netmask(self) -> IPAddress:
            return IPAddress(super().netmask)

        @property
        def hostmask(self) -> IPAddress:
            return IPAddress(super().hostmask)

        @property
        def cidr(self):
            return self.__class__(super().cidr)

        def iter_hosts(self) -> Iterator[IPAddress]:
            for host in super().iter_hosts():
                yield IPAddress(host)

        def __iter__(self) -> Iterator[IPAddress]:
            for addr in super().__iter__():
                yield IPAddress(addr)

        def __getitem__(self, index: int):
            # super().__getitem__ will return either an IPAddress or an iterator of IPAddresses,
            # depending on the type of index passed in
            res = super().__getitem__(index)
            if isinstance(res, IPAddressBase):
                return IPAddress(res)
            else:
                for addr in res:  # type: ignore
                    yield IPAddress(addr)

except ImportError:
    pass

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
