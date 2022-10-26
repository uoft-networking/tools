# coding: utf-8
from __future__ import annotations

from .error import YAMLError
from .compat import nprint, DBG_NODE, dbg, nprintf  # NOQA
from .util import RegExp

from .events import (
    StreamStartEvent,
    StreamEndEvent,
    MappingStartEvent,
    MappingEndEvent,
    SequenceStartEvent,
    SequenceEndEvent,
    AliasEvent,
    ScalarEvent,
    DocumentStartEvent,
    DocumentEndEvent,
)
from .nodes import MappingNode, ScalarNode, SequenceNode

from typing import TYPE_CHECKING
from uoft_core.yaml.emitter import Emitter
from uoft_core.yaml.nodes import MappingNode, ScalarNode, SequenceNode
from uoft_core.yaml.resolver import Resolver

if TYPE_CHECKING:
    from typing import Any, Dict, Union, Text, Optional  # NOQA
    from uoft_core.yaml.main import Dumper
    from .compat import VersionType  # NOQA

__all__ = ["Serializer", "SerializerError"]


class SerializerError(YAMLError):
    pass


class Serializer:

    # 'id' and 3+ numbers, but not 000
    ANCHOR_TEMPLATE = "id%03d"
    ANCHOR_RE = RegExp("id(?!000$)\\d{3,}")

    def __init__(self, dumper: Dumper) -> None:

        self.dumper = dumper
        self.use_encoding = dumper.conf.encoding
        self.use_explicit_start = dumper.conf.explicit_start
        self.use_explicit_end = dumper.conf.explicit_end
        if isinstance(dumper.conf.version, str):
            self.use_version = tuple(map(int, dumper.conf.version.split(".")))
        else:
            self.use_version = dumper.conf.version
        self.use_tags = dumper.conf.tags
        self.serialized_nodes = {}
        self.anchors = {}
        self.last_anchor_id = 0
        self.closed = None
        self._templated_id = None

    @property
    def emitter(self) -> Emitter:
        return self.dumper.emitter

    @property
    def resolver(self) -> Resolver:
        return self.dumper.resolver

    def open(self) -> None:

        if self.closed is None:
            self.emitter.emit(StreamStartEvent(encoding=self.use_encoding))
            self.closed = False
        elif self.closed:
            raise SerializerError("serializer is closed")
        else:
            raise SerializerError("serializer is already opened")

    def close(self) -> None:

        if self.closed is None:
            raise SerializerError("serializer is not opened")
        elif not self.closed:
            self.emitter.emit(StreamEndEvent())
            self.closed = True

    # def __del__(self):
    #     self.close()

    def serialize(self, node: Union[MappingNode, ScalarNode, SequenceNode]) -> None:

        if dbg(DBG_NODE):
            nprint("Serializing nodes")
            node.dump()
        if self.closed is None:
            raise SerializerError("serializer is not opened")
        elif self.closed:
            raise SerializerError("serializer is closed")
        self.emitter.emit(
            DocumentStartEvent(
                explicit=self.use_explicit_start,
                version=self.use_version,
                tags=self.use_tags,
            )
        )
        self.anchor_node(node)
        self.serialize_node(node, None, None)
        self.emitter.emit(DocumentEndEvent(explicit=self.use_explicit_end))
        self.serialized_nodes = {}
        self.anchors = {}
        self.last_anchor_id = 0

    def anchor_node(self, node: Union[MappingNode, ScalarNode, SequenceNode]) -> None:

        if node in self.anchors:
            if self.anchors[node] is None:
                self.anchors[node] = self.generate_anchor(node)
        else:
            anchor = None
            try:
                if node.anchor.always_dump:
                    anchor = node.anchor.value
            except:  # NOQA
                pass
            self.anchors[node] = anchor
            if isinstance(node, SequenceNode):
                for item in node.value:
                    self.anchor_node(item)
            elif isinstance(node, MappingNode):
                for key, value in node.value:
                    self.anchor_node(key)
                    self.anchor_node(value)

    def generate_anchor(self, node: MappingNode) -> str:

        try:
            anchor = node.anchor.value
        except:  # NOQA
            anchor = None
        if anchor is None:
            self.last_anchor_id += 1
            return self.ANCHOR_TEMPLATE % self.last_anchor_id
        return anchor

    def serialize_node(
        self,
        node: Union[MappingNode, ScalarNode, SequenceNode],
        parent: Optional[Union[MappingNode, SequenceNode]],
        index: Optional[Union[int, ScalarNode, SequenceNode]],
    ) -> None:

        alias = self.anchors[node]
        if node in self.serialized_nodes:
            node_style = getattr(node, "style", None)
            if node_style != "?":
                node_style = None
            self.emitter.emit(AliasEvent(alias, style=node_style))
        else:
            self.serialized_nodes[node] = True
            self.resolver.descend_resolver(parent, index)
            if isinstance(node, ScalarNode):
                # here check if the node.tag equals the one that would result from parsing
                # if not equal quoting is necessary for strings
                detected_tag = self.resolver.resolve(
                    ScalarNode, node.value, (True, False)
                )
                default_tag = self.resolver.resolve(
                    ScalarNode, node.value, (False, True)
                )
                implicit = (
                    (node.tag == detected_tag),
                    (node.tag == default_tag),
                    node.tag.startswith("tag:yaml.org,2002:"),
                )
                self.emitter.emit(
                    ScalarEvent(
                        alias,
                        node.tag,
                        implicit,
                        node.value,
                        style=node.style,
                        comment=node.comment,
                    )
                )
            elif isinstance(node, SequenceNode):
                implicit = node.tag == self.resolver.resolve(
                    SequenceNode, node.value, True
                )
                comment = node.comment
                end_comment = None
                seq_comment = None
                if node.flow_style is True:
                    if comment:  # eol comment on flow style sequence
                        seq_comment = comment[0]
                        # comment[0] = None
                if comment and len(comment) > 2:
                    end_comment = comment[2]
                else:
                    end_comment = None
                self.emitter.emit(
                    SequenceStartEvent(
                        alias,
                        node.tag,
                        implicit,
                        flow_style=node.flow_style,
                        comment=node.comment,
                    )
                )
                index = 0
                for item in node.value:
                    self.serialize_node(item, node, index)
                    index += 1
                self.emitter.emit(SequenceEndEvent(comment=[seq_comment, end_comment]))
            elif isinstance(node, MappingNode):
                implicit = node.tag == self.resolver.resolve(
                    MappingNode, node.value, True
                )
                comment = node.comment
                end_comment = None
                map_comment = None
                if node.flow_style is True:
                    if comment:  # eol comment on flow style sequence
                        map_comment = comment[0]
                        # comment[0] = None
                if comment and len(comment) > 2:
                    end_comment = comment[2]
                self.emitter.emit(
                    MappingStartEvent(
                        alias,
                        node.tag,
                        implicit,
                        flow_style=node.flow_style,
                        comment=node.comment,
                        nr_items=len(node.value),
                    )
                )
                for key, value in node.value:
                    self.serialize_node(key, node, None)
                    self.serialize_node(value, node, key)
                self.emitter.emit(MappingEndEvent(comment=[map_comment, end_comment]))
            self.resolver.ascend_resolver()


def templated_id(s: str) -> None:

    return Serializer.ANCHOR_RE.match(s)
