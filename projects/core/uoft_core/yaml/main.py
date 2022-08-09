# coding: utf-8
# pylint: disable=unused-import, unused-wildcard-import, wildcard-import, unused-argument, redefined-outer-name

import sys
import os
import glob
from importlib import import_module

from .error import UnsafeLoaderWarning, YAMLError  # NOQA

from .tokens import *  # NOQA
from .events import *  # NOQA
from .nodes import *  # NOQA

from .compat import StringIO, BytesIO, with_metaclass, nprint

from .loader import RoundTripLoader as Loader
from .dumper import RoundTripDumper as Dumper
from .resolver import VersionedResolver as Resolver
from .representer import RoundTripRepresenter as Representer
from .constructor import RoundTripConstructor as Constructor
from .scanner import RoundTripScanner as Scanner
from .parser import RoundTripParser as Parser
from .reader import Reader
from .composer import Composer
from .emitter import Emitter
from .serializer import Serializer

from .comments import CommentedMap, CommentedSeq, C_PRE

from typing import List, Set, Dict, Union, Any, Callable, Optional, Text  # NOQA
from .compat import StreamType, StreamTextType, VersionType  # NOQA
from pathlib import Path



# YAML is an acronym, i.e. spoken: rhymes with "camel". And thus a
# subset of abbreviations, which should be all caps according to PEP8


class YAML:
    def __init__(
        self, *, pure=False, output=None, plug_ins=None
    ):  # input=None,
        # type: (Any, Optional[Text], Any, Any, Any) -> None
        """
        typ: 'rt'/None -> RoundTripLoader/RoundTripDumper,  (default)
        pure: if True only use Python modules
        input/output: needed to work as context manager
        plug_ins: a list of plug-in files
        """
        self._context_manager = None
        self._reader = None
        self._serializer = None
        self._emitter = None
        self._representer = None
        self._scanner = None
        self._parser = None
        self._composer = None
        self._constructor = None
        self._resolver = None

        self._output = output
        self.pure = pure
        self.plug_ins = []
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

    @property
    def reader(self) -> Reader:
        if not self._reader:
            self._reader = Reader(None, loader=self)
        return self._reader

    @property
    def scanner(self) -> Scanner:
        if not self._scanner:
            self._scanner = Scanner(loader=self)
        return self._scanner

    @property
    def parser(self) -> Parser:
        if not self._parser:
            self._parser = Parser(loader=self)
        return self._parser

    @property
    def composer(self) -> Composer:
        if not self._composer:
            self._composer = Composer(loader=self)
        return self._composer

    @property
    def constructor(self) -> Constructor:
        if not self._constructor:
            self._constructor = Constructor(loader=self)
            self._constructor.allow_duplicate_keys = self.allow_duplicate_keys
        return self._constructor

    @property
    def resolver(self) -> Resolver:
        if not self._resolver:
            self._resolver = Resolver(loader=self)
        return self._resolver

    @property
    def emitter(self) -> Emitter:
        if not self._emitter:
            self._emitter = Emitter(
                None,
                canonical=self.canonical,
                indent=self.old_indent,
                width=self.width,
                allow_unicode=self.allow_unicode,
                line_break=self.line_break,
                prefix_colon=self.prefix_colon,
                brace_single_entry_mapping_in_flow_sequence=self.brace_single_entry_mapping_in_flow_sequence,  # NOQA
                dumper=self,
            )
            if self.map_indent is not None:
                self._emitter.best_map_indent = self.map_indent
            if self.sequence_indent is not None:
                self._emitter.best_sequence_indent = self.sequence_indent
            if self.sequence_dash_offset is not None:
                self._emitter.sequence_dash_offset = self.sequence_dash_offset
            if self.compact_seq_seq is not None:
                self._emitter.compact_seq_seq = self.compact_seq_seq
            if self.compact_seq_map is not None:
                self._emitter.compact_seq_map = self.compact_seq_map
        return self._emitter

    @property
    def serializer(self) -> Serializer:
        if not self._serializer:
            self._serializer = Serializer(
                encoding=self.encoding,
                explicit_start=self.explicit_start,
                explicit_end=self.explicit_end,
                version=self.version,
                tags=self.tags,
                dumper=self,
            )
        return self._serializer

    @property
    def representer(self) -> Representer:
        if not self._representer:
            repres = Representer(
                default_style=self.default_style,
                default_flow_style=self.default_flow_style,
                dumper=self,
            )
            if self.sort_base_mapping_type_on_output is not None:
                repres.sort_base_mapping_type_on_output = (
                    self.sort_base_mapping_type_on_output
                )
            self._representer = repres
        return self._representer

    def scan(self, stream):
        # type: (StreamTextType) -> Any
        """
        Scan a YAML stream and produce scanning tokens.
        """
        if not hasattr(stream, "read") and hasattr(stream, "open"):
            # pathlib.Path() instance
            with stream.open("rb") as fp:
                return self.scan(fp)
        _, parser = self.get_constructor_parser(stream)
        try:
            while self.scanner.check_token():
                yield self.scanner.get_token()
        finally:
            parser.dispose()
            try:
                self.reader.reset_reader()
            except AttributeError:
                pass
            try:
                self.scanner.reset_scanner()
            except AttributeError:
                pass

    def parse(self, stream):
        # type: (StreamTextType) -> Any
        """
        Parse a YAML stream and produce parsing events.
        """
        if not hasattr(stream, "read") and hasattr(stream, "open"):
            # pathlib.Path() instance
            with stream.open("rb") as fp:
                return self.parse(fp)
        _, parser = self.get_constructor_parser(stream)
        try:
            while parser.check_event():
                yield parser.get_event()
        finally:
            parser.dispose()
            try:
                self.reader.reset_reader()
            except AttributeError:
                pass
            try:
                self.scanner.reset_scanner()
            except AttributeError:
                pass

    def compose(self, stream):
        # type: (Union[Path, StreamTextType]) -> Any
        """
        Parse the first YAML document in a stream
        and produce the corresponding representation tree.
        """
        if not hasattr(stream, "read") and hasattr(stream, "open"):
            # pathlib.Path() instance
            with stream.open("rb") as fp:
                return self.compose(fp)
        constructor, parser = self.get_constructor_parser(stream)
        try:
            return constructor.composer.get_single_node()
        finally:
            parser.dispose()
            try:
                self.reader.reset_reader()
            except AttributeError:
                pass
            try:
                self.scanner.reset_scanner()
            except AttributeError:
                pass

    def compose_all(self, stream):
        # type: (Union[Path, StreamTextType]) -> Any
        """
        Parse all YAML documents in a stream
        and produce corresponding representation trees.
        """
        constructor, parser = self.get_constructor_parser(stream)
        try:
            while constructor.composer.check_node():
                yield constructor.composer.get_node()
        finally:
            parser.dispose()
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

    def load(self, stream):
        # type: (Union[Path, StreamTextType]) -> Any
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
        constructor, parser = self.get_constructor_parser(stream)
        try:
            return constructor.get_single_data()
        finally:
            parser.dispose()
            try:
                self.reader.reset_reader()
            except AttributeError:
                pass
            try:
                self.scanner.reset_scanner()
            except AttributeError:
                pass

    def load_all(self, stream):  # *, skip=None):
        # type: (Union[Path, StreamTextType]) -> Any
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
        constructor, parser = self.get_constructor_parser(stream)
        try:
            while constructor.check_data():
                yield constructor.get_data()
        finally:
            parser.dispose()
            try:
                self.reader.reset_reader()
            except AttributeError:
                pass
            try:
                self.scanner.reset_scanner()
            except AttributeError:
                pass

    def get_constructor_parser(self, stream):
        # type: (StreamTextType) -> Any
        """
        the old cyaml needs special setup, and therefore the stream
        """
        self.reader.stream = stream
        return self.constructor, self.parser

    def emit(self, events, stream):
        # type: (Any, Any) -> None
        """
        Emit YAML parsing events into a stream.
        If stream is None, return the produced string instead.
        """
        _, _, emitter = self.get_serializer_representer_emitter(stream, None)
        try:
            for event in events:
                emitter.emit(event)
        finally:
            emitter.dispose()

    def serialize(self, node, stream):
        # type: (Any, Optional[StreamType]) -> Any
        """
        Serialize a representation tree into a YAML stream.
        If stream is None, return the produced string instead.
        """
        self.serialize_all([node], stream)

    def serialize_all(self, nodes, stream):
        # type: (Any, Optional[StreamType]) -> Any
        """
        Serialize a sequence of representation trees into a YAML stream.
        If stream is None, return the produced string instead.
        """
        serializer, _, emitter = self.get_serializer_representer_emitter(stream, None)
        try:
            serializer.open()
            for node in nodes:
                serializer.serialize(node)
            serializer.close()
        finally:
            emitter.dispose()

    def dump(self, data, stream=None, *, transform=None):
        # type: (Any, Union[Path, StreamType], Any, Any) -> Any
        if self._context_manager:
            if not self._output:
                raise TypeError(
                    "Missing output stream while dumping from context manager"
                )
            if transform is not None:
                raise TypeError(
                    "{}.dump() in the context manager cannot have transform keyword "
                    "".format(self.__class__.__name__)
                )
            self._context_manager.dump(data)
        else:  # old style
            if stream is None:
                raise TypeError(
                    "Need a stream argument when not dumping from context manager"
                )
            return self.dump_all([data], stream, transform=transform)

    def dump_all(self, documents, stream: Union[Path, StreamType], *, transform=None):
        if self._context_manager:
            raise NotImplementedError
        self._output = stream
        self._context_manager = YAMLContextManager(self, transform=transform)
        for data in documents:
            self._context_manager.dump(data)
        self._context_manager.teardown_output()
        self._output = None
        self._context_manager = None

    def Xdump_all(self, documents, stream, *, transform=None):
        """
        Serialize a sequence of Python objects into a YAML stream.
        """
        fstream = None
        if not hasattr(stream, "write") and hasattr(stream, "open"):
            # pathlib.Path() instance
            with stream.open("w") as fp:
                return self.dump_all(documents, fp, transform=transform)
        # The stream should have the methods `write` and possibly `flush`.
        if transform is not None:
            fstream = stream
            if self.encoding is None:
                stream = StringIO()
            else:
                stream = BytesIO()
        try:
            self.serializer.open()
            for data in documents:
                self.representer.represent(data)
            self.serializer.close()
        finally:
            self.emitter.dispose()
            delattr(self, "_serializer")
            delattr(self, "_emitter")
        if transform:
            val = stream.getvalue()
            if self.encoding and isinstance(val, bytes):
                val = val.decode(self.encoding)
            if fstream is None:
                transform(val)
            else:
                fstream.write(transform(val))
        return None

    def get_serializer_representer_emitter(self, stream, tlca):
        # type: (StreamType, Any) -> Any
        # we have only .Serializer to deal with (vs .Reader & .Scanner), much simpler
        self.emitter.stream = stream
        self.emitter.top_level_colon_align = tlca
        if self.scalar_after_indicator is not None:
            self.emitter.scalar_after_indicator = self.scalar_after_indicator
        return self.serializer, self.representer, self.emitter

    # basic types
    def map(self, **kw):
        # type: (Any) -> Any
        if "rt" in self.typ:
            return CommentedMap(**kw)
        else:
            return dict(**kw)

    def seq(self, *args):
        # type: (Any) -> Any
        if "rt" in self.typ:
            return CommentedSeq(*args)
        else:
            return list(*args)

    # helpers
    def official_plug_ins(self):
        # type: () -> Any
        """search for list of subdirs that are plug-ins, if __file__ is not available, e.g.
        single file installers that are not properly emulating a file-system (issue 324)
        no plug-ins will be found. If any are packaged, you know which file that are
        and you can explicitly provide it during instantiation:
            yaml = ruamel.yaml.YAML(plug_ins=['ruamel/yaml/jinja2/__plug_in__'])
        """
        try:
            bd = os.path.dirname(__file__)
        except NameError:
            return []
        gpbd = os.path.dirname(os.path.dirname(bd))
        res = [x.replace(gpbd, "")[1:-3] for x in glob.glob(bd + "/*/__plug_in__.py")]
        return res

    def register_class(self, cls):
        # type:(Any) -> Any
        """
        register a class for dumping loading
        - if it has attribute yaml_tag use that to register, else use class name
        - if it has methods to_yaml/from_yaml use those to dump/load else dump attributes
          as mapping
        """
        tag = getattr(cls, "yaml_tag", "!" + cls.__name__)
        try:
            self.representer.add_representer(cls, cls.to_yaml)
        except AttributeError:

            def t_y(representer, data):
                # type: (Any, Any) -> Any
                return representer.represent_yaml_object(
                    tag, data, cls, flow_style=representer.default_flow_style
                )

            self.representer.add_representer(cls, t_y)
        try:
            self.constructor.add_constructor(tag, cls.from_yaml)
        except AttributeError:

            def f_y(constructor, node):
                # type: (Any, Any) -> Any
                return constructor.construct_yaml_object(node, cls)

            self.constructor.add_constructor(tag, f_y)
        return cls

    # ### context manager

    def __enter__(self):
        # type: () -> Any
        self._context_manager = YAMLContextManager(self)
        return self

    def __exit__(self, typ, value, traceback):
        # type: (Any, Any, Any) -> None
        if typ:
            nprint("typ", typ)
        self._context_manager.teardown_output()
        # self._context_manager.teardown_input()
        self._context_manager = None

    # ### backwards compatibility
    def _indent(self, mapping=None, sequence=None, offset=None):
        # type: (Any, Any, Any) -> None
        if mapping is not None:
            self.map_indent = mapping
        if sequence is not None:
            self.sequence_indent = sequence
        if offset is not None:
            self.sequence_dash_offset = offset

    @property
    def indent(self):
        # type: () -> Any
        return self._indent

    @indent.setter
    def indent(self, val):
        # type: (Any) -> None
        self.old_indent = val

    @property
    def block_seq_indent(self):
        # type: () -> Any
        return self.sequence_dash_offset

    @block_seq_indent.setter
    def block_seq_indent(self, val):
        # type: (Any) -> None
        self.sequence_dash_offset = val

    def compact(self, seq_seq=None, seq_map=None):
        # type: (Any, Any) -> None
        self.compact_seq_seq = seq_seq
        self.compact_seq_map = seq_map


class YAMLContextManager:
    def __init__(self, yaml, transform=None):
        # type: (Any, Any) -> None  # used to be: (Any, Optional[Callable]) -> None
        self._yaml = yaml
        self._output_inited = False
        self._output_path = None
        self._output = self._yaml._output
        self._transform = transform

        # self._input_inited = False
        # self._input = input
        # self._input_path = None
        # self._transform = yaml.transform
        # self._fstream = None

        if not hasattr(self._output, "write") and hasattr(self._output, "open"):
            # pathlib.Path() instance, open with the same mode
            self._output_path = self._output
            self._output = self._output_path.open("w")

        # if not hasattr(self._stream, 'write') and hasattr(stream, 'open'):
        # if not hasattr(self._input, 'read') and hasattr(self._input, 'open'):
        #    # pathlib.Path() instance, open with the same mode
        #    self._input_path = self._input
        #    self._input = self._input_path.open('r')

        if self._transform is not None:
            self._fstream = self._output
            if self._yaml.encoding is None:
                self._output = StringIO()
            else:
                self._output = BytesIO()

    def teardown_output(self):
        # type: () -> None
        if self._output_inited:
            self._yaml.serializer.close()
        else:
            return
        self._yaml.emitter.dispose()
        delattr(self._yaml, "_serializer")
        delattr(self._yaml, "_emitter")
        if self._transform:
            val = self._output.getvalue()
            if self._yaml.encoding and isinstance(val, bytes):
                val = val.decode(self._yaml.encoding)
            if self._fstream is None:
                self._transform(val)
            else:
                self._fstream.write(self._transform(val))
                self._fstream.flush()
                self._output = self._fstream  # maybe not necessary
        if self._output_path is not None:
            self._output.close()

    def init_output(self, first_data):
        # type: (Any) -> None
        if self._yaml.top_level_colon_align is True:
            tlca = max([len(str(x)) for x in first_data])  # type: Any
        else:
            tlca = self._yaml.top_level_colon_align
        self._yaml.get_serializer_representer_emitter(self._output, tlca)
        self._yaml.serializer.open()
        self._output_inited = True

    def dump(self, data):
        # type: (Any) -> None
        if not self._output_inited:
            self.init_output(data)
        self._yaml.representer.represent(data)

    # def teardown_input(self):
    #     pass
    #
    # def init_input(self):
    #     # set the constructor and parser on YAML() instance
    #     self._yaml.get_constructor_parser(stream)
    #
    # def load(self):
    #     if not self._input_inited:
    #         self.init_input()
    #     try:
    #         while self._yaml.constructor.check_data():
    #             yield self._yaml.constructor.get_data()
    #     finally:
    #         parser.dispose()
    #         try:
    #             self._reader.reset_reader()  # type: ignore
    #         except AttributeError:
    #             pass
    #         try:
    #             self._scanner.reset_scanner()  # type: ignore
    #         except AttributeError:
    #             pass


def yaml_object(yml):
    # type: (Any) -> Any
    """decorator for classes that needs to dump/load objects
    The tag for such objects is taken from the class attribute yaml_tag (or the
    class name in lowercase in case unavailable)
    If methods to_yaml and/or from_yaml are available, these are called for dumping resp.
    loading, default routines (dumping a mapping of the attributes) used otherwise.
    """

    def yo_deco(cls):
        # type: (Any) -> Any
        tag = getattr(cls, "yaml_tag", "!" + cls.__name__)
        try:
            yml.representer.add_representer(cls, cls.to_yaml)
        except AttributeError:

            def t_y(representer, data):
                # type: (Any, Any) -> Any
                return representer.represent_yaml_object(
                    tag, data, cls, flow_style=representer.default_flow_style
                )

            yml.representer.add_representer(cls, t_y)
        try:
            yml.constructor.add_constructor(tag, cls.from_yaml)
        except AttributeError:

            def f_y(constructor, node):
                # type: (Any, Any) -> Any
                return constructor.construct_yaml_object(node, cls)

            yml.constructor.add_constructor(tag, f_y)
        return cls

    return yo_deco

# Loader/Dumper are no longer composites, to get to the associated
# Resolver()/Representer(), etc., you need to instantiate the class


def add_implicit_resolver(
    tag, regexp, first=None, Loader=Loader, Dumper=Dumper, resolver=Resolver
):
    """
    Add an implicit scalar detector.
    If an implicit scalar value matches the given regexp,
    the corresponding tag is assigned to the scalar.
    first is a sequence of possible initial characters or None.
    """
    if Loader is None and Dumper is None:
        resolver.add_implicit_resolver(tag, regexp, first)
        return
    if Loader:
        if hasattr(Loader, "add_implicit_resolver"):
            Loader.add_implicit_resolver(tag, regexp, first)
        else:
            Resolver.add_implicit_resolver(tag, regexp, first)
    if Dumper:
        if hasattr(Dumper, "add_implicit_resolver"):
            Dumper.add_implicit_resolver(tag, regexp, first)
        else:
            Resolver.add_implicit_resolver(tag, regexp, first)


# this code currently not tested
def add_path_resolver(
    tag, path, kind=None, Loader=Loader, Dumper=Dumper, resolver=Resolver
):
    """
    Add a path based resolver for the given tag.
    A path is a list of keys that forms a path
    to a node in the representation tree.
    Keys can be string values, integers, or None.
    """
    if Loader:
        if hasattr(Loader, "add_path_resolver"):
            Loader.add_path_resolver(tag, path, kind)
        else:
            Resolver.add_path_resolver(tag, path, kind)
    if Dumper:
        if hasattr(Dumper, "add_path_resolver"):
            Dumper.add_path_resolver(tag, path, kind)
        else:
            Resolver.add_path_resolver(tag, path, kind)


def add_constructor(tag, object_constructor, Loader=None, constructor=Constructor):
    # type: (Any, Any, Any, Any) -> None
    """
    Add an object constructor for the given tag.
    object_onstructor is a function that accepts a Loader instance
    and a node object and produces the corresponding Python object.
    """
    if Loader is None:
        constructor.add_constructor(tag, object_constructor)
    else:
        if hasattr(Loader, "add_constructor"):
            Loader.add_constructor(tag, object_constructor)
            return
        Constructor.add_constructor(tag, object_constructor)


def add_multi_constructor(
    tag_prefix, multi_constructor, Loader=Loader, constructor=Constructor
):
    """
    Add a multi-constructor for the given tag prefix.
    Multi-constructor is called for a node if its tag starts with tag_prefix.
    Multi-constructor accepts a Loader instance, a tag suffix,
    and a node object and produces the corresponding Python object.
    """
    Constructor.add_multi_constructor(tag_prefix, multi_constructor)


def add_representer(
    data_type, object_representer, Dumper=Dumper, representer=Representer
):
    # type: (Any, Any, Any, Any) -> None
    """
    Add a representer for the given type.
    object_representer is a function accepting a Dumper instance
    and an instance of the given data type
    and producing the corresponding representation node.
    """
    if hasattr(Dumper, "add_representer"):
        Dumper.add_representer(data_type, object_representer)
        return
    Representer.add_representer(data_type, object_representer)


# this code currently not tested
def add_multi_representer(
    data_type, multi_representer, Dumper=Dumper, representer=Representer
):
    # type: (Any, Any, Any, Any) -> None
    """
    Add a representer for the given type.
    multi_representer is a function accepting a Dumper instance
    and an instance of the given data type or subtype
    and producing the corresponding representation node.
    """
    if hasattr(Dumper, "add_multi_representer"):
        Dumper.add_multi_representer(data_type, multi_representer)
        return
    Representer.add_multi_representer(data_type, multi_representer)


class YAMLObjectMetaclass(type):
    """
    The metaclass for YAMLObject.
    """

    def __init__(cls, name, bases, kwds):
        # type: (Any, Any, Any) -> None
        super().__init__(name, bases, kwds)
        if "yaml_tag" in kwds and kwds["yaml_tag"] is not None:
            cls.yaml_constructor.add_constructor(cls.yaml_tag, cls.from_yaml)  # type: ignore
            cls.yaml_representer.add_representer(cls, cls.to_yaml)  # type: ignore


class YAMLObject(with_metaclass(YAMLObjectMetaclass)):  # type: ignore
    """
    An object that can dump itself to a YAML stream
    and load itself from a YAML stream.
    """

    __slots__ = ()  # no direct instantiation, so allow immutable subclasses

    yaml_constructor = Constructor
    yaml_representer = Representer

    yaml_tag = None  # type: Any
    yaml_flow_style = None  # type: Any

    @classmethod
    def from_yaml(cls, constructor, node):
        # type: (Any, Any) -> Any
        """
        Convert a representation node to a Python object.
        """
        return constructor.construct_yaml_object(node, cls)

    @classmethod
    def to_yaml(cls, representer, data):
        # type: (Any, Any) -> Any
        """
        Convert a Python object to a representation node.
        """
        return representer.represent_yaml_object(
            cls.yaml_tag, data, cls, flow_style=cls.yaml_flow_style
        )
