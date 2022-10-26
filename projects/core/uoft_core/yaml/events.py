# coding: utf-8
from __future__ import annotations

from .compat import _F

# Abstract classes.

from typing import Tuple, Union, TYPE_CHECKING
from uoft_core.yaml.error import StringMark
from uoft_core.yaml.scalarstring import DoubleQuotedScalarString, LiteralScalarString, PlainScalarString, SingleQuotedScalarString
from uoft_core.yaml.tokens import CommentToken

if TYPE_CHECKING:
    from typing import Any, Dict, Optional, List  # NOQA

SHOW_LINES = False


def CommentCheck():

    pass


class Event:
    __slots__ = "start_mark", "end_mark", "comment"

    def __init__(self, start_mark: Optional[StringMark]=None, end_mark: Optional[StringMark]=None, comment: Any=CommentCheck) -> None:

        self.start_mark = start_mark
        self.end_mark = end_mark
        # assert comment is not CommentCheck
        if comment is CommentCheck:
            comment = None
        self.comment = comment

    def __repr__(self) -> str:

        if True:
            arguments = []
            if hasattr(self, "value"):
                # if you use repr(getattr(self, 'value')) then flake8 complains about
                # abuse of getattr with a constant. When you change to self.value
                # then mypy throws an error
                arguments.append(repr(self.value))
            for key in ["anchor", "tag", "implicit", "flow_style", "style"]:
                v = getattr(self, key, None)
                if v is not None:
                    arguments.append(_F("{key!s}={v!r}", key=key, v=v))
            if self.comment not in [None, CommentCheck]:
                arguments.append("comment={!r}".format(self.comment))
            if SHOW_LINES:
                arguments.append(
                    "({}:{}/{}:{})".format(
                        self.start_mark.line,
                        self.start_mark.column,
                        self.end_mark.line,
                        self.end_mark.column,
                    )
                )
            arguments = ", ".join(arguments)
        else:
            attributes = [
                key
                for key in ["anchor", "tag", "implicit", "value", "flow_style", "style"]
                if hasattr(self, key)
            ]
            arguments = ", ".join(
                [
                    _F("{k!s}={attr!r}", k=key, attr=getattr(self, key))
                    for key in attributes
                ]
            )
            if self.comment not in [None, CommentCheck]:
                arguments += ", comment={!r}".format(self.comment)
        return _F(
            "{self_class_name!s}({arguments!s})",
            self_class_name=self.__class__.__name__,
            arguments=arguments,
        )


class NodeEvent(Event):
    __slots__ = ("anchor",)

    def __init__(self, anchor: Optional[str], start_mark: Optional[StringMark]=None, end_mark: Optional[StringMark]=None, comment: Optional[Any]=None) -> None:

        Event.__init__(self, start_mark, end_mark, comment)
        self.anchor = anchor


class CollectionStartEvent(NodeEvent):
    __slots__ = "tag", "implicit", "flow_style", "nr_items"

    def __init__(
        self,
        anchor: Optional[str],
        tag: Optional[str],
        implicit: bool,
        start_mark: Optional[StringMark]=None,
        end_mark: Optional[StringMark]=None,
        flow_style: Optional[bool]=None,
        comment: Optional[Union[List[Optional[List[CommentToken]]], List[CommentToken], List[None], List[Optional[CommentToken]]]]=None,
        nr_items: Optional[int]=None,
    ) -> None:

        NodeEvent.__init__(self, anchor, start_mark, end_mark, comment)
        self.tag = tag
        self.implicit = implicit
        self.flow_style = flow_style
        self.nr_items = nr_items


class CollectionEndEvent(Event):
    __slots__ = ()


# Implementations.


class StreamStartEvent(Event):
    __slots__ = ("encoding",)

    def __init__(self, start_mark: Optional[StringMark]=None, end_mark: Optional[StringMark]=None, encoding: Optional[str]=None, comment: None=None) -> None:

        Event.__init__(self, start_mark, end_mark, comment)
        self.encoding = encoding


class StreamEndEvent(Event):
    __slots__ = ()


class DocumentStartEvent(Event):
    __slots__ = "explicit", "version", "tags"

    def __init__(
        self,
        start_mark: Optional[StringMark]=None,
        end_mark: Optional[StringMark]=None,
        explicit: Optional[bool]=None,
        version: Optional[Tuple[int, int]]=None,
        tags: None=None,
        comment: Optional[List[Optional[List[CommentToken]]]]=None,
    ) -> None:

        Event.__init__(self, start_mark, end_mark, comment)
        self.explicit = explicit
        self.version = version
        self.tags = tags


class DocumentEndEvent(Event):
    __slots__ = ("explicit",)

    def __init__(self, start_mark: Optional[StringMark]=None, end_mark: Optional[StringMark]=None, explicit: Optional[bool]=None, comment: None=None) -> None:

        Event.__init__(self, start_mark, end_mark, comment)
        self.explicit = explicit


class AliasEvent(NodeEvent):
    __slots__ = "style"

    def __init__(
        self, anchor: str, start_mark: Optional[StringMark]=None, end_mark: Optional[StringMark]=None, style: None=None, comment: None=None
    ) -> None:

        NodeEvent.__init__(self, anchor, start_mark, end_mark, comment)
        self.style = style


class ScalarEvent(NodeEvent):
    __slots__ = "tag", "implicit", "value", "style"

    def __init__(
        self,
        anchor: Optional[str],
        tag: Optional[str],
        implicit: Union[Tuple[bool, bool, bool], Tuple[bool, bool]],
        value: Union[LiteralScalarString, str, DoubleQuotedScalarString, PlainScalarString, SingleQuotedScalarString],
        start_mark: Optional[StringMark]=None,
        end_mark: Optional[StringMark]=None,
        style: Optional[str]=None,
        comment: Optional[Union[List[Union[CommentToken, List[str]]], List[Optional[List[CommentToken]]], List[None], List[Optional[CommentToken]]]]=None,
    ) -> None:

        NodeEvent.__init__(self, anchor, start_mark, end_mark, comment)
        self.tag = tag
        self.implicit = implicit
        self.value = value
        self.style = style


class SequenceStartEvent(CollectionStartEvent):
    __slots__ = ()


class SequenceEndEvent(CollectionEndEvent):
    __slots__ = ()


class MappingStartEvent(CollectionStartEvent):
    __slots__ = ()


class MappingEndEvent(CollectionEndEvent):
    __slots__ = ()
