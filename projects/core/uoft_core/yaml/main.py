# coding: utf-8
# pylint: disable=unused-import, unused-wildcard-import, wildcard-import, unused-argument, redefined-outer-name

from __future__ import annotations
from functools import cached_property
from pathlib import Path
from typing import Iterator, List, Any, Optional, TYPE_CHECKING
from io import StringIO, TextIOWrapper

from .compat import StringIO

from .resolver import Resolver
from .representer import Representer
from .constructor import Constructor
from .scanner import Scanner
from .parser import Parser
from .io import Reader
from .composer import Composer
from .emitter import Emitter
from .serializer import Serializer


from .comments import CommentedMap, CommentedSeq


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
        self.width = None
        self.line_break = None

        self.map_indent = None
        self.sequence_indent = None
        self.scalar_indent = None
        self.sequence_dash_offset = 0
        self.compact_seq_seq = None
        self.compact_seq_map = None
        self.sort_base_mapping_type_on_output = None  # default: sort

        self.top_level_colon_align = None
        self.prefix_colon = None
        self.version = None
        self.preserve_quotes = None
        self.allow_duplicate_keys = False  # duplicate keys in map, set
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

    def load(self, stream: str) -> Any:
        return Loader(self).load(stream)

    def load_all(self, stream: str) -> Iterator[CommentedMap]:  # *, skip=None):
        return Loader(self).load_all(stream)

    def dump(self, data: Any, stream: StringIO | Path | None = None) -> str | None:
        return Dumper(self).dump(data, stream)

    def dump_all(self, documents: List[Any], stream: StringIO | TextIOWrapper| Path | None) -> str | None:
        return Dumper(self).dump_all(documents, stream)

    def indent(self, mapping: Optional[int]=None, sequence: Optional[int]=None, scalar: Optional[int]=None, offset: Optional[int]=None) -> None:

        if mapping is not None:
            self.map_indent = mapping
        if sequence is not None:
            self.sequence_indent = sequence
        if scalar is not None:
            self.scalar_indent = scalar
        if offset is not None:
            self.sequence_dash_offset = offset

class Dumper:
    def __init__(self, parent: YAML) -> None:
        self.conf = parent
        self.emitter = Emitter(self)
        self.representer = Representer(self)
        self.serializer = Serializer(self)
        self.resolver = Resolver(self)

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

        if isinstance(stream, Path):
            assert isinstance(output, StringIO)
            stream.write_text(output.getvalue())
        elif stream is None:
            assert isinstance(output, StringIO)
            return output.getvalue()
        else:
            return None
    

class Loader:
    def __init__(self, parent: YAML) -> None:
        self.conf = parent
        self.reader = Reader(self)
        self.constructor = Constructor(self)
        self.resolver = Resolver(self)
        self.composer = Composer(self)
        self.parser = Parser(self)
        self.scanner = Scanner(self)

    def load(self, stream: str) -> Any:
        self.reader.stream = stream
        return self.constructor.get_single_data()

    def load_all(self, stream: str) -> Iterator[CommentedMap | CommentedSeq]:  # *, skip=None):
        self.reader.stream = stream
        while self.constructor.check_data():
            yield self.constructor.get_data()