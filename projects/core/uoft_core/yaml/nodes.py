# coding: utf-8
from __future__ import annotations

import sys

from .compat import _F

from typing import List, Optional, Union, TYPE_CHECKING
from uoft_core.yaml.anchor import Anchor
from uoft_core.yaml.scalarstring import DoubleQuotedScalarString, LiteralScalarString, PlainScalarString, SingleQuotedScalarString
from uoft_core.yaml.tokens import CommentToken

if TYPE_CHECKING:
    from typing import Dict, Any, Text  # NOQA
    from uoft_core.yaml.error import StringMark


class Node:
    __slots__ = "id", "tag", "value", "start_mark", "end_mark", "comment", "anchor"

    def __init__(self, tag: str, value: Union[str, DoubleQuotedScalarString, PlainScalarString, SingleQuotedScalarString, LiteralScalarString], start_mark: Optional[StringMark], end_mark: Optional[StringMark], comment: Optional[Any]=None, anchor: Optional[Union[str, Anchor]]=None) -> None:

        try:
            self.id: str = "base"
        except AttributeError:
            # we are initializing a suclass with a read-only id attribute
            pass
        self.tag = tag
        self.value = value
        self.start_mark = start_mark
        self.end_mark = end_mark
        self.comment = comment
        self.anchor = anchor

    def __repr__(self):

        value = self.value
        # if isinstance(value, list):
        #     if len(value) == 0:
        #         value = '<empty>'
        #     elif len(value) == 1:
        #         value = '<1 item>'
        #     else:
        #         value = f'<{len(value)} items>'
        # else:
        #     if len(value) > 75:
        #         value = repr(value[:70]+' ... ')
        #     else:
        #         value = repr(value)
        value = repr(value)
        return _F(
            "{class_name!s}(tag={self_tag!r}, value={value!s})",
            class_name=self.__class__.__name__,
            self_tag=self.tag,
            value=value,
        )

    def dump(self, indent=0):

        if isinstance(self.value, str):
            sys.stdout.write(
                "{}{}(tag={!r}, value={!r})\n".format(
                    "  " * indent, self.__class__.__name__, self.tag, self.value
                )
            )
            if self.comment:
                sys.stdout.write(
                    "    {}comment: {})\n".format("  " * indent, self.comment)
                )
            return
        sys.stdout.write(
            "{}{}(tag={!r})\n".format("  " * indent, self.__class__.__name__, self.tag)
        )
        if self.comment:
            sys.stdout.write("    {}comment: {})\n".format("  " * indent, self.comment))
        for v in self.value:
            if isinstance(v, tuple):
                for v1 in v:
                    v1.dump(indent + 1)
            elif isinstance(v, Node):
                v.dump(indent + 1)
            else:
                sys.stdout.write("Node value type? {}\n".format(type(v)))


class ScalarNode(Node):
    """
    styles:
      ? -> set() ? key, no value
      " -> double quoted
      ' -> single quoted
      | -> literal style
      > -> folding style
    """

    __slots__ = ("style",)
    id = "scalar"

    def __init__(
        self,
        tag: str,
        value: Union[str, DoubleQuotedScalarString, PlainScalarString, SingleQuotedScalarString, LiteralScalarString],
        start_mark: Optional[StringMark]=None,
        end_mark: Optional[StringMark]=None,
        style: Optional[str]=None,
        comment: Optional[Any]=None,
        anchor: Optional[Union[str, Anchor]]=None,
    ) -> None:

        Node.__init__(
            self, tag, value, start_mark, end_mark, comment=comment, anchor=anchor
        )
        self.style = style


class CollectionNode(Node):
    __slots__ = ("flow_style",)

    def __init__(
        self,
        tag: str,
        value: List[Any],
        start_mark: Optional[StringMark]=None,
        end_mark: None=None,
        flow_style: Optional[bool]=None,
        comment: Optional[Union[List[Optional[List[CommentToken]]], List[CommentToken], List[Optional[CommentToken]]]]=None,
        anchor: Optional[Union[str, Anchor]]=None,
    ) -> None:

        Node.__init__(self, tag, value, start_mark, end_mark, comment=comment)
        self.flow_style = flow_style
        self.anchor = anchor


class SequenceNode(CollectionNode):
    __slots__ = ()
    id = "sequence"


class MappingNode(CollectionNode):
    __slots__ = ("merge",)
    id = "mapping"

    def __init__(
        self,
        tag: str,
        value: List[Any],
        start_mark: Optional[StringMark]=None,
        end_mark: None=None,
        flow_style: Optional[bool]=None,
        comment: Optional[Union[List[Optional[List[CommentToken]]], List[Optional[CommentToken]]]]=None,
        anchor: Optional[Union[str, Anchor]]=None,
    ) -> None:

        CollectionNode.__init__(
            self, tag, value, start_mark, end_mark, flow_style, comment, anchor
        )
        self.merge = None
