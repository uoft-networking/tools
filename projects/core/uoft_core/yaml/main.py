# coding: utf-8
# pylint: disable=unused-import, unused-wildcard-import, wildcard-import, unused-argument, redefined-outer-name

from __future__ import annotations
from functools import cached_property
from pathlib import Path

from .tokens import *  # NOQA
from .events import *  # NOQA
from .nodes import *  # NOQA

from .compat import StringIO, BytesIO, nprint, version_tnf

from .resolver import Resolver
from .representer import Representer
from .constructor import Constructor
from .scanner import Scanner
from .parser import Parser
from .io import Reader
from .composer import Composer
from .emitter import Emitter
from .serializer import Serializer

from .comments import CommentedSeq

from typing import Iterator, TextIO, Tuple, List, Any, Optional, TYPE_CHECKING
from io import StringIO, TextIOWrapper
from uoft_core.yaml.comments import CommentedMap
from uoft_core.yaml.emitter import Emitter


# YAML is an acronym, i.e. spoken: rhymes with "camel". And thus a
# subset of abbreviations, which should be all caps according to PEP8


class YAML:
    def __init__(self) -> None:  # input=None,

        """
        """
        self._context_manager = None

        self.allow_unicode = True
        self.default_flow_style = False
        self.comment_handling = None
        self.stream = None
        self.canonical = None
        self.old_indent = None
        self.width = None
        self.line_break = None

        self.map_indent = None
        self.sequence_indent = None
        self.sequence_dash_offset = 0
        self.compact_seq_seq = None
        self.compact_seq_map = None
        self.sort_base_mapping_type_on_output = None  # default: sort

        self.top_level_colon_align = None
        self.prefix_colon = None
        self.version = None
        self.preserve_quotes = None
        self.allow_duplicate_keys = version_tnf((0, 15, 1), (0, 16))  # duplicate keys in map, set
        self.encoding = "utf-8"
        self.explicit_start = None
        self.explicit_end = None
        self.tags = None
        self.default_style = None
        self.top_level_block_style_scalar_no_indent_error_1_1 = False
        # directives end indicator with single scalar document
        self.scalar_after_indicator = None
        # [a, b: 1, c: {d: 2}]  vs. [a, {b: 1}, {c: {d: 2}}]
        self.brace_single_entry_mapping_in_flow_sequence = False

    @cached_property
    def reader(self) -> Reader:
        return Reader(self)

    @cached_property
    def emitter(self) -> Emitter:
        return Emitter(self)

    @cached_property
    def serializer(self) -> Serializer:
        return Serializer(self)

    @cached_property
    def scanner(self) -> Scanner:
        return Scanner(self)

    @cached_property
    def parser(self) -> Parser:
        return Parser(self)

    @cached_property
    def composer(self) -> Composer:
        return Composer(self)

    @cached_property
    def representer(self) -> Representer:
        return Representer(self)

    @cached_property
    def constructor(self) -> Constructor:
        return Constructor(self)

    @cached_property
    def resolver(self) -> Resolver:
        return Resolver(self)

    def scan(self, stream):

        """
        Scan a YAML stream and produce scanning tokens.
        """
        if not hasattr(stream, "read") and hasattr(stream, "open"):
            # pathlib.Path() instance
            with stream.open("rb") as fp:
                return self.scan(fp)
        self.reader.stream = stream

        try:
            while self.scanner.check_token():
                yield self.scanner.get_token()
        finally:
            self.parser.dispose()
            try:
                self.reader.reset_reader()
            except AttributeError:
                pass
            try:
                self.scanner.reset_scanner()
            except AttributeError:
                pass

    def parse(self, stream):

        """
        Parse a YAML stream and produce parsing events.
        """
        if not hasattr(stream, "read") and hasattr(stream, "open"):
            # pathlib.Path() instance
            with stream.open("rb") as fp:
                return self.parse(fp)
        self.reader.stream = stream
        try:
            while self.parser.check_event():
                yield self.parser.get_event()
        finally:
            self.parser.dispose()
            try:
                self.reader.reset_reader()
            except AttributeError:
                pass
            try:
                self.scanner.reset_scanner()
            except AttributeError:
                pass

    def compose(self, stream):

        """
        Parse the first YAML document in a stream
        and produce the corresponding representation tree.
        """
        if not hasattr(stream, "read") and hasattr(stream, "open"):
            # pathlib.Path() instance
            with stream.open("rb") as fp:
                return self.compose(fp)
        self.reader.stream = stream
        try:
            return self.constructor.composer.get_single_node()
        finally:
            self.parser.dispose()
            try:
                self.reader.reset_reader()
            except AttributeError:
                pass
            try:
                self.scanner.reset_scanner()
            except AttributeError:
                pass

    def compose_all(self, stream):

        """
        Parse all YAML documents in a stream
        and produce corresponding representation trees.
        """
        self.reader.stream = stream
        try:
            while self.constructor.composer.check_node():
                yield self.constructor.composer.get_node()
        finally:
            self.parser.dispose()
            try:
                self.reader.reset_reader()
            except AttributeError:
                pass
            try:
                self.scanner.reset_scanner()
            except AttributeError:
                pass

    # separate output resolver?

    # def load(self, stream=None):
    #     if self._context_manager:
    #        if not self._input:
    #             raise TypeError("Missing input stream while dumping from context manager")
    #         for data in self._context_manager.load():
    #             yield data
    #         return
    #     if stream is None:
    #         raise TypeError("Need a stream argument when not loading from context manager")
    #     return self.load_one(stream)

    def load(self, stream: str) -> Any:

        """
        at this point you either have the non-pure Parser (which has its own reader and
        scanner) or you have the pure Parser.
        If the pure Parser is set, then set the Reader and Scanner, if not already set.
        If either the Scanner or Reader are set, you cannot use the non-pure Parser,
            so reset it to the pure parser and set the Reader resp. Scanner if necessary
        """
        if not hasattr(stream, "read") and hasattr(stream, "open"):
            # pathlib.Path() instance
            with stream.open("rb") as fp:
                return self.load(fp)
        self.reader.stream = stream
        try:
            return self.constructor.get_single_data()
        finally:
            self.parser.dispose()
            try:
                self.reader.reset_reader()
            except AttributeError:
                pass
            try:
                self.scanner.reset_scanner()
            except AttributeError:
                pass

    def load_all(self, stream: str) -> Iterator[CommentedMap]:  # *, skip=None):

        if not hasattr(stream, "read") and hasattr(stream, "open"):
            # pathlib.Path() instance
            with stream.open("r") as fp:
                for d in self.load_all(fp):
                    yield d
                return
        # if skip is None:
        #     skip = []
        # elif isinstance(skip, int):
        #     skip = [skip]
        self.reader.stream = stream
        try:
            while self.constructor.check_data():
                yield self.constructor.get_data()
        finally:
            self.parser.dispose()
            try:
                self.reader.reset_reader()
            except AttributeError:
                pass
            try:
                self.scanner.reset_scanner()
            except AttributeError:
                pass


    def emit(self, events, stream):

        """
        Emit YAML parsing events into a stream.
        If stream is None, return the produced string instead.
        """
        self.emitter.stream = stream
        try:
            for event in events:
                self.emitter.emit(event)
        finally:
            self.emitter.dispose()

    def serialize(self, node, stream):

        """
        Serialize a representation tree into a YAML stream.
        If stream is None, return the produced string instead.
        """
        self.serialize_all([node], stream)

    def serialize_all(self, nodes, stream):

        """
        Serialize a sequence of representation trees into a YAML stream.
        If stream is None, return the produced string instead.
        """
        self.emitter.stream = stream
        try:
            self.serializer.open()
            for node in nodes:
                self.serializer.serialize(node)
            self.serializer.close()
        finally:
            self.emitter.dispose()

    def dump(self, data: Any, stream: StringIO | Path | None = None) -> str | None:

        return self.dump_all([data], stream)

    def dump_all(self, documents: List[Any], stream: StringIO | TextIOWrapper| Path | None) -> str | None:
        if not isinstance(stream, (StringIO, TextIOWrapper)):
            output = StringIO()
        else:
            output = stream

        self.emitter.stream = output
        self.serializer.open()
        for data in documents:
            self.representer.represent(data)

        self.serializer.close()
        self.emitter.dispose()

        if isinstance(stream, Path):
            assert isinstance(output, StringIO)
            stream.write_text(output.getvalue())
        elif stream is None:
            assert isinstance(output, StringIO)
            return output.getvalue()
        else:
            return None

    # basic types
    def map(self, **kw):
        return CommentedMap(**kw)

    def seq(self, *args):
        return CommentedSeq(*args)

    # ### backwards compatibility
    def _indent(self, mapping: Optional[int]=None, sequence: Optional[int]=None, offset: Optional[int]=None) -> None:

        if mapping is not None:
            self.map_indent = mapping
        if sequence is not None:
            self.sequence_indent = sequence
        if offset is not None:
            self.sequence_dash_offset = offset

    @property
    def indent(self):

        return self._indent

    @indent.setter
    def indent(self, val):

        self.old_indent = val

    @property
    def block_seq_indent(self):

        return self.sequence_dash_offset

    @block_seq_indent.setter
    def block_seq_indent(self, val):

        self.sequence_dash_offset = val

    def compact(self, seq_seq=None, seq_map=None):

        self.compact_seq_seq = seq_seq
        self.compact_seq_map = seq_map