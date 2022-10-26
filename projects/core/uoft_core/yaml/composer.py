# coding: utf-8
from __future__ import annotations

import warnings

from .error import MarkedYAMLError, ReusedAnchorWarning
from .compat import _F, nprint, nprintf  # NOQA

from .events import (
    StreamStartEvent,
    StreamEndEvent,
    MappingStartEvent,
    MappingEndEvent,
    SequenceStartEvent,
    SequenceEndEvent,
    AliasEvent,
    ScalarEvent,
)
from .nodes import MappingNode, ScalarNode, SequenceNode

from typing import Union, TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Optional  # NOQA
    from uoft_core.yaml.events import MappingEndEvent, SequenceEndEvent
    from uoft_core.yaml.main import Loader
    from uoft_core.yaml.nodes import MappingNode, ScalarNode, SequenceNode

__all__ = ["Composer", "ComposerError"]


class ComposerError(MarkedYAMLError):
    pass


class Composer:
    def __init__(self, loader: Loader) -> None:
        self.loader = loader
        self.anchors = {}

    def check_node(self) -> bool:

        # Drop the STREAM-START event.
        if self.loader.parser.check_event(StreamStartEvent):
            self.loader.parser.get_event()

        # If there are more documents available?
        return not self.loader.parser.check_event(StreamEndEvent)

    def get_node(self) -> ScalarNode | MappingNode | SequenceNode | None:

        # Get the root node of the next document.
        if not self.loader.parser.check_event(StreamEndEvent):
            return self.compose_document()

    def get_single_node(self) -> Union[MappingNode, SequenceNode, ScalarNode]:

        # Drop the STREAM-START event.
        self.loader.parser.get_event()

        # Compose a document if the stream is not empty.
        document = None
        if not self.loader.parser.check_event(StreamEndEvent):
            document = self.compose_document()

        # Ensure that the stream contains no more documents.
        if not self.loader.parser.check_event(StreamEndEvent):
            event = self.loader.parser.get_event()
            raise ComposerError(
                "expected a single document in the stream",
                document.start_mark,
                "but found another document",
                event.start_mark,
            )

        # Drop the STREAM-END event.
        self.loader.parser.get_event()

        return document

    def compose_document(self) -> Union[ScalarNode, MappingNode, SequenceNode]:

        # Drop the DOCUMENT-START event.
        self.loader.parser.get_event()

        # Compose the root node.
        node = self.compose_node(None, None)

        # Drop the DOCUMENT-END event.
        self.loader.parser.get_event()

        self.anchors = {}
        return node

    def return_alias(self, a: Union[ScalarNode, MappingNode]) -> Union[ScalarNode, MappingNode]:

        return a

    def compose_node(self, parent: Optional[Union[MappingNode, SequenceNode]], index: Optional[Union[ScalarNode, SequenceNode, int]]) -> Union[MappingNode, SequenceNode, ScalarNode]:

        if self.loader.parser.check_event(AliasEvent):
            event = self.loader.parser.get_event()
            alias = event.anchor
            if alias not in self.anchors:
                raise ComposerError(
                    None,
                    None,
                    _F("found undefined alias {alias!r}", alias=alias),
                    event.start_mark,
                )
            return self.return_alias(self.anchors[alias])
        event = self.loader.parser.peek_event()
        anchor = event.anchor
        if anchor is not None:  # have an anchor
            if anchor in self.anchors:
                # raise ComposerError(
                #     "found duplicate anchor %r; first occurrence"
                #     % (anchor), self.anchors[anchor].start_mark,
                #     "second occurrence", event.start_mark)
                ws = (
                    "\nfound duplicate anchor {!r}\nfirst occurrence {}\nsecond occurrence "
                    "{}".format(
                        (anchor), self.anchors[anchor].start_mark, event.start_mark
                    )
                )
                warnings.warn(ws, ReusedAnchorWarning)
        self.loader.resolver.descend_resolver(parent, index)
        if self.loader.parser.check_event(ScalarEvent):
            node = self.compose_scalar_node(anchor)
        elif self.loader.parser.check_event(SequenceStartEvent):
            node = self.compose_sequence_node(anchor)
        elif self.loader.parser.check_event(MappingStartEvent):
            node = self.compose_mapping_node(anchor)
        self.loader.resolver.ascend_resolver()
        return node

    def compose_scalar_node(self, anchor: Optional[str]) -> ScalarNode:

        event = self.loader.parser.get_event()
        tag = event.tag
        if tag is None or tag == "!":
            tag = self.loader.resolver.resolve(ScalarNode, event.value, event.implicit)
        node = ScalarNode(
            tag,
            event.value,
            event.start_mark,
            event.end_mark,
            style=event.style,
            comment=event.comment,
            anchor=anchor,
        )
        if anchor is not None:
            self.anchors[anchor] = node
        return node

    def compose_sequence_node(self, anchor: None) -> SequenceNode:

        start_event = self.loader.parser.get_event()
        tag = start_event.tag
        if tag is None or tag == "!":
            tag = self.loader.resolver.resolve(SequenceNode, None, start_event.implicit)
        node = SequenceNode(
            tag,
            [],
            start_event.start_mark,
            None,
            flow_style=start_event.flow_style,
            comment=start_event.comment,
            anchor=anchor,
        )
        if anchor is not None:
            self.anchors[anchor] = node
        index = 0
        while not self.loader.parser.check_event(SequenceEndEvent):
            node.value.append(self.compose_node(node, index))
            index += 1
        end_event = self.loader.parser.get_event()
        if node.flow_style is True and end_event.comment is not None:
            if node.comment is not None:
                nprint(
                    "Warning: unexpected end_event commment in sequence "
                    "node {}".format(node.flow_style)
                )
            node.comment = end_event.comment
        node.end_mark = end_event.end_mark
        self.check_end_doc_comment(end_event, node)
        return node

    def compose_mapping_node(self, anchor: Optional[str]) -> MappingNode:

        start_event = self.loader.parser.get_event()
        tag = start_event.tag
        if tag is None or tag == "!":
            tag = self.loader.resolver.resolve(MappingNode, None, start_event.implicit)
        node = MappingNode(
            tag,
            [],
            start_event.start_mark,
            None,
            flow_style=start_event.flow_style,
            comment=start_event.comment,
            anchor=anchor,
        )
        if anchor is not None:
            self.anchors[anchor] = node
        while not self.loader.parser.check_event(MappingEndEvent):
            # key_event = self.parser.peek_event()
            item_key = self.compose_node(node, None)
            # if item_key in node.value:
            #     raise ComposerError("while composing a mapping",
            #             start_event.start_mark,
            #             "found duplicate key", key_event.start_mark)
            item_value = self.compose_node(node, item_key)
            # node.value[item_key] = item_value
            node.value.append((item_key, item_value))
        end_event = self.loader.parser.get_event()
        if node.flow_style is True and end_event.comment is not None:
            node.comment = end_event.comment
        node.end_mark = end_event.end_mark
        self.check_end_doc_comment(end_event, node)
        return node

    def check_end_doc_comment(self, end_event: Union[SequenceEndEvent, MappingEndEvent], node: Union[MappingNode, SequenceNode]) -> None:

        if end_event.comment and end_event.comment[1]:
            # pre comments on an end_event, no following to move to
            if node.comment is None:
                node.comment = [None, None]
            assert not isinstance(node, ScalarEvent)
            # this is a post comment on a mapping node, add as third element
            # in the list
            node.comment.append(end_event.comment[1])
            end_event.comment[1] = None
