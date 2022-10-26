# coding: utf-8
from __future__ import annotations

from .anchor import Anchor

from typing import Optional, Type, Union, TYPE_CHECKING
from uoft_core.yaml.anchor import Anchor

if TYPE_CHECKING:
    from typing import Text, Any, Dict, List  # NOQA

__all__ = ["ScalarInt", "BinaryInt", "OctalInt", "HexInt", "HexCapsInt", "DecimalInt"]


class ScalarInt(int):
    def __new__(cls: Union[Type[BinaryInt], Type[HexInt], Type[HexCapsInt], Type[ScalarInt], Type[OctalInt]], *args, **kw) -> Union[ScalarInt, HexCapsInt, HexInt, OctalInt, BinaryInt]:

        width = kw.pop("width", None)
        underscore = kw.pop("underscore", None)
        anchor = kw.pop("anchor", None)
        v = int.__new__(cls, *args, **kw)
        v._width = width
        v._underscore = underscore
        if anchor is not None:
            v.yaml_set_anchor(anchor, always_dump=True)
        return v

    def __iadd__(self, a):

        x = type(self)(self + a)
        x._width = self._width
        x._underscore = (
            self._underscore[:] if self._underscore is not None else None
        )  # NOQA
        return x

    def __ifloordiv__(self, a: Union[OctalInt, HexCapsInt, BinaryInt, HexInt]) -> Union[OctalInt, HexCapsInt, BinaryInt, HexInt]:

        x = type(self)(self // a)
        x._width = self._width
        x._underscore = (
            self._underscore[:] if self._underscore is not None else None
        )  # NOQA
        return x

    def __imul__(self, a: int) -> Union[OctalInt, BinaryInt, HexCapsInt, HexInt]:

        x = type(self)(self * a)
        x._width = self._width
        x._underscore = (
            self._underscore[:] if self._underscore is not None else None
        )  # NOQA
        return x

    def __ipow__(self, a: int) -> Union[OctalInt, HexCapsInt, BinaryInt, HexInt]:

        x = type(self)(self**a)
        x._width = self._width
        x._underscore = (
            self._underscore[:] if self._underscore is not None else None
        )  # NOQA
        return x

    def __isub__(self, a: int) -> Union[OctalInt, HexCapsInt, BinaryInt, HexInt]:

        x = type(self)(self - a)
        x._width = self._width
        x._underscore = (
            self._underscore[:] if self._underscore is not None else None
        )  # NOQA
        return x

    @property
    def anchor(self) -> Anchor:

        if not hasattr(self, Anchor.attrib):
            setattr(self, Anchor.attrib, Anchor())
        return getattr(self, Anchor.attrib)

    def yaml_anchor(self, any: bool=False) -> Anchor:

        if not hasattr(self, Anchor.attrib):
            return None
        if any or self.anchor.always_dump:
            return self.anchor
        return None

    def yaml_set_anchor(self, value, always_dump=False):

        self.anchor.value = value
        self.anchor.always_dump = always_dump


class BinaryInt(ScalarInt):
    def __new__(cls: Type[BinaryInt], value: int, width: None=None, underscore: None=None, anchor: None=None) -> "BinaryInt":

        return ScalarInt.__new__(
            cls, value, width=width, underscore=underscore, anchor=anchor
        )


class OctalInt(ScalarInt):
    def __new__(cls: Type[OctalInt], value: int, width: Optional[int]=None, underscore: Optional[List[Union[int, bool]]]=None, anchor: None=None) -> "OctalInt":

        return ScalarInt.__new__(
            cls, value, width=width, underscore=underscore, anchor=anchor
        )


# mixed casing of A-F is not supported, when loading the first non digit
# determines the case


class HexInt(ScalarInt):
    """uses lower case (a-f)"""

    def __new__(cls: Type[HexInt], value: int, width: None=None, underscore: Optional[List[Union[int, bool]]]=None, anchor: None=None) -> "HexInt":

        return ScalarInt.__new__(
            cls, value, width=width, underscore=underscore, anchor=anchor
        )


class HexCapsInt(ScalarInt):
    """uses upper case (A-F)"""

    def __new__(cls: Type[HexCapsInt], value: int, width: None=None, underscore: None=None, anchor: None=None) -> "HexCapsInt":

        return ScalarInt.__new__(
            cls, value, width=width, underscore=underscore, anchor=anchor
        )


class DecimalInt(ScalarInt):
    """needed if anchor"""

    def __new__(cls, value, width=None, underscore=None, anchor=None):

        return ScalarInt.__new__(
            cls, value, width=width, underscore=underscore, anchor=anchor
        )
