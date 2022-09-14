# coding: utf-8
from __future__ import annotations

import sys
from .anchor import Anchor

from typing import Type, TYPE_CHECKING
from uoft_core.yaml.anchor import Anchor

if TYPE_CHECKING:
    from typing import Text, Any, Dict, List  # NOQA

__all__ = ["ScalarFloat", "ExponentialFloat", "ExponentialCapsFloat"]


class ScalarFloat(float):
    def __new__(cls: Type[ScalarFloat], *args, **kw) -> "ScalarFloat":

        width = kw.pop("width", None)
        prec = kw.pop("prec", None)
        m_sign = kw.pop("m_sign", None)
        m_lead0 = kw.pop("m_lead0", 0)
        exp = kw.pop("exp", None)
        e_width = kw.pop("e_width", None)
        e_sign = kw.pop("e_sign", None)
        underscore = kw.pop("underscore", None)
        anchor = kw.pop("anchor", None)
        v = float.__new__(cls, *args, **kw)
        v._width = width
        v._prec = prec
        v._m_sign = m_sign
        v._m_lead0 = m_lead0
        v._exp = exp
        v._e_width = e_width
        v._e_sign = e_sign
        v._underscore = underscore
        if anchor is not None:
            v.yaml_set_anchor(anchor, always_dump=True)
        return v

    def __iadd__(self, a):

        return float(self) + a
        x = type(self)(self + a)
        x._width = self._width
        x._underscore = (
            self._underscore[:] if self._underscore is not None else None
        )  # NOQA
        return x

    def __ifloordiv__(self, a):

        return float(self) // a
        x = type(self)(self // a)
        x._width = self._width
        x._underscore = (
            self._underscore[:] if self._underscore is not None else None
        )  # NOQA
        return x

    def __imul__(self, a: int) -> float:

        return float(self) * a
        x = type(self)(self * a)
        x._width = self._width
        x._underscore = (
            self._underscore[:] if self._underscore is not None else None
        )  # NOQA
        x._prec = self._prec  # check for others
        return x

    def __ipow__(self, a):

        return float(self) ** a
        x = type(self)(self**a)
        x._width = self._width
        x._underscore = (
            self._underscore[:] if self._underscore is not None else None
        )  # NOQA
        return x

    def __isub__(self, a):

        return float(self) - a
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

    def dump(self, out=sys.stdout):

        out.write(
            "ScalarFloat({}| w:{}, p:{}, s:{}, lz:{}, _:{}|{}, w:{}, s:{})\n".format(
                self,
                self._width,
                self._prec,
                self._m_sign,
                self._m_lead0,
                self._underscore,
                self._exp,
                self._e_width,
                self._e_sign,
            )
        )


class ExponentialFloat(ScalarFloat):
    def __new__(cls, value, width=None, underscore=None):

        return ScalarFloat.__new__(cls, value, width=width, underscore=underscore)


class ExponentialCapsFloat(ScalarFloat):
    def __new__(cls, value, width=None, underscore=None):

        return ScalarFloat.__new__(cls, value, width=width, underscore=underscore)
