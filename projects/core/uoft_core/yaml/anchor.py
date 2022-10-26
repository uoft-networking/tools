# coding: utf-8
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any, Dict, Optional, List, Union, Optional, Iterator  # NOQA

anchor_attrib = "_yaml_anchor"


class Anchor:
    __slots__ = "value", "always_dump"
    attrib = anchor_attrib

    def __init__(self) -> None:

        self.value = None
        self.always_dump = False

    def __repr__(self):

        ad = ", (always dump)" if self.always_dump else ""
        return "Anchor({!r}{})".format(self.value, ad)
