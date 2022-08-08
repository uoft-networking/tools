"container module for exposing and re-exporting common types used in switchconfig templates & filters"
# pylint: disable=unused-import

from typing import (
    Annotated,
    Any,
    Callable,
    ClassVar,
    Concatenate,
    Final,
    ForwardRef,
    Generic,
    Literal,
    Optional,
    ParamSpec,
    Protocol,
    Tuple,
    Type,
    TypeVar,
    Union,
    # ABCs (from collections.abc,
    AbstractSet,  # collections.abc.Set,
    ByteString,
    Container,
    ContextManager,
    Hashable,
    ItemsView,
    Iterable,
    Iterator,
    KeysView,
    Mapping,
    MappingView,
    MutableMapping,
    MutableSequence,
    MutableSet,
    Sequence,
    Sized,
    ValuesView,
    Awaitable,
    AsyncIterator,
    AsyncIterable,
    Coroutine,
    Collection,
    AsyncGenerator,
    AsyncContextManager,
    # Structural checks, a.k.a. protocol,
    Reversible,
    SupportsAbs,
    SupportsBytes,
    SupportsComplex,
    SupportsFloat,
    SupportsIndex,
    SupportsInt,
    SupportsRound,
    # Concrete collection type,
    ChainMap,
    Counter,
    Deque,
    Dict,
    DefaultDict,
    List,
    OrderedDict,
    Set,
    FrozenSet,
    NamedTuple,  # Not really a type,
    TypedDict,  # Not really a type,
    Generator,
    # Other concrete types,
    BinaryIO,
    IO,
    Match,
    Pattern,
    TextIO,
    # One-off things,
    AnyStr,
    NewType,
    NoReturn,
    ParamSpecArgs,
    ParamSpecKwargs,
    Text,
    TYPE_CHECKING,
    TypeAlias,
    TypeGuard,
)
from pathlib import Path

from netaddr import IPAddress, IPNetwork
from pydantic import BaseModel, Field  # pylint: disable=no-name-in-module
from pydantic.types import (
    NoneStr,
    NoneBytes,
    StrBytes,
    NoneStrBytes,
    StrictStr,
    ConstrainedBytes,
    conbytes,
    ConstrainedList,
    conlist,
    ConstrainedSet,
    conset,
    ConstrainedFrozenSet,
    confrozenset,
    ConstrainedStr,
    constr,
    PyObject,
    ConstrainedInt,
    conint,
    PositiveInt,
    NegativeInt,
    NonNegativeInt,
    NonPositiveInt,
    ConstrainedFloat,
    confloat,
    PositiveFloat,
    NegativeFloat,
    NonNegativeFloat,
    NonPositiveFloat,
    ConstrainedDecimal,
    condecimal,
    UUID1,
    UUID3,
    UUID4,
    UUID5,
    FilePath,
    DirectoryPath,
    Json,
    JsonWrapper,
    SecretStr,
    SecretBytes,
    StrictBool,
    StrictBytes,
    StrictInt,
    StrictFloat,
    PaymentCardNumber,
    ByteSize,
    PastDate,
    FutureDate,
)

from uoft_core import StrEnum


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


class Choice(BaseModel):
    # Base class used to define multiple choices in a discriminated union.
    # see the "Union" example under https://pydantic-docs.helpmanual.io/usage/types/#literal-type
    # for details
    kind: str
