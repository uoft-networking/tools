# coding: utf-8
from __future__ import annotations

import re

from typing import Tuple, Type, TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any, Dict, List, Union, Text, Optional  # NOQA
    from . import YAML
    from .compat import VersionType  # NOQA
    from .main import Loader, Dumper

from .compat import _DEFAULT_YAML_VERSION, _F  # NOQA
from .error import *  # NOQA
from .nodes import MappingNode, ScalarNode, SequenceNode  # NOQA
from .util import RegExp  # NOQA
from uoft_core.yaml.nodes import MappingNode, ScalarNode, SequenceNode
from uoft_core.yaml.util import LazyEval

__all__ = ["Resolver", "ResolverError"]


# fmt: off
# resolvers consist of
# - a list of applicable version
# - a tag
# - a regexp
# - a list of first characters to match
implicit_resolvers = [
    ([(1, 2)],
        'tag:yaml.org,2002:bool',
        RegExp('''^(?:true|True|TRUE|false|False|FALSE)$''', re.X),
        list('tTfF')),
    ([(1, 1)],
        'tag:yaml.org,2002:bool',
        RegExp('''^(?:y|Y|yes|Yes|YES|n|N|no|No|NO
        |true|True|TRUE|false|False|FALSE
        |on|On|ON|off|Off|OFF)$''', re.X),
        list('yYnNtTfFoO')),
    ([(1, 2)],
        'tag:yaml.org,2002:float',
        RegExp('''^(?:
         [-+]?(?:[0-9][0-9_]*)\\.[0-9_]*(?:[eE][-+]?[0-9]+)?
        |[-+]?(?:[0-9][0-9_]*)(?:[eE][-+]?[0-9]+)
        |[-+]?\\.[0-9_]+(?:[eE][-+][0-9]+)?
        |[-+]?\\.(?:inf|Inf|INF)
        |\\.(?:nan|NaN|NAN))$''', re.X),
        list('-+0123456789.')),
    ([(1, 1)],
        'tag:yaml.org,2002:float',
        RegExp('''^(?:
         [-+]?(?:[0-9][0-9_]*)\\.[0-9_]*(?:[eE][-+]?[0-9]+)?
        |[-+]?(?:[0-9][0-9_]*)(?:[eE][-+]?[0-9]+)
        |\\.[0-9_]+(?:[eE][-+][0-9]+)?
        |[-+]?[0-9][0-9_]*(?::[0-5]?[0-9])+\\.[0-9_]*  # sexagesimal float
        |[-+]?\\.(?:inf|Inf|INF)
        |\\.(?:nan|NaN|NAN))$''', re.X),
        list('-+0123456789.')),
    ([(1, 2)],
        'tag:yaml.org,2002:int',
        RegExp('''^(?:[-+]?0b[0-1_]+
        |[-+]?0o?[0-7_]+
        |[-+]?[0-9_]+
        |[-+]?0x[0-9a-fA-F_]+)$''', re.X),
        list('-+0123456789')),
    ([(1, 1)],
        'tag:yaml.org,2002:int',
        RegExp('''^(?:[-+]?0b[0-1_]+
        |[-+]?0?[0-7_]+
        |[-+]?(?:0|[1-9][0-9_]*)
        |[-+]?0x[0-9a-fA-F_]+
        |[-+]?[1-9][0-9_]*(?::[0-5]?[0-9])+)$''', re.X),  # sexagesimal int
        list('-+0123456789')),
    ([(1, 2), (1, 1)],
        'tag:yaml.org,2002:merge',
        RegExp('^(?:<<)$'),
        ['<']),
    ([(1, 2), (1, 1)],
        'tag:yaml.org,2002:null',
        RegExp('''^(?: ~
        |null|Null|NULL
        | )$''', re.X),
        ['~', 'n', 'N', '']),
    ([(1, 2), (1, 1)],
        'tag:yaml.org,2002:timestamp',
        RegExp('''^(?:[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]
        |[0-9][0-9][0-9][0-9] -[0-9][0-9]? -[0-9][0-9]?
        (?:[Tt]|[ \\t]+)[0-9][0-9]?
        :[0-9][0-9] :[0-9][0-9] (?:\\.[0-9]*)?
        (?:[ \\t]*(?:Z|[-+][0-9][0-9]?(?::[0-9][0-9])?))?)$''', re.X),
        list('0123456789')),
    ([(1, 2), (1, 1)],
        'tag:yaml.org,2002:value',
        RegExp('^(?:=)$'),
        ['=']),
    # The following resolver is only for documentation purposes. It cannot work
    # because plain scalars cannot start with '!', '&', or '*'.
    ([(1, 2), (1, 1)],
        'tag:yaml.org,2002:yaml',
        RegExp('^(?:!|&|\\*)$'),
        list('!&*')),
]
# fmt: on


class ResolverError(YAMLError):
    pass


class Resolver:
    """
    this resolver delays loading
    the pattern matching rules. That way it can decide to load 1.1 rules
    or the (default) 1.2 rules, that no longer support octal without 0o, sexagesimals
    and Yes/No/On/Off booleans.
    """
    DEFAULT_SCALAR_TAG = "tag:yaml.org,2002:str"
    DEFAULT_SEQUENCE_TAG = "tag:yaml.org,2002:seq"
    DEFAULT_MAPPING_TAG = "tag:yaml.org,2002:map"

    yaml_implicit_resolvers = {}
    yaml_path_resolvers = {}

    def __init__(self, parent: Loader | Dumper) -> None:
        from .main import Loader, Dumper # imported here to avoid circular import
        if isinstance(parent, Loader):
            self.loader = parent
            self.dumper = None
        elif isinstance(parent, Dumper):
            self.loader = None
            self.dumper = parent
        self.resolver_exact_paths = []
        self.resolver_prefix_paths = []
        self._version_implicit_resolver = {}

    @property
    def loader_version(self):
        if not self.loader:
            return None
        return self.get_loader_version(self.loader.conf.version)

    def get_loader_version(self, version: Optional[Union[str, Tuple[int, int]]]) -> Optional[Tuple[int, int]]:

        if version is None or isinstance(version, tuple):
            return version
        if isinstance(version, list) and not isinstance(version, str):
            return tuple(version)
        # assume string
        return tuple(map(int, version.split(".")))

    def add_version_implicit_resolver(self, version: Tuple[int, int], tag: str, regexp: LazyEval, first: List[str | None]) -> None:

        if first is None:
            first = [None]
        impl_resolver = self._version_implicit_resolver.setdefault(version, {})
        for ch in first:
            impl_resolver.setdefault(ch, []).append((tag, regexp))

    @property
    def versioned_resolver(self) -> Dict[str | None, List[Tuple[str, LazyEval]]]:

        """
        select the resolver based on the version we are parsing
        """
        version = self.processing_version
        if isinstance(version, str):
            version = tuple(map(int, version.split(".")))
        if version not in self._version_implicit_resolver:
            for x in implicit_resolvers:
                if version in x[0]:
                    self.add_version_implicit_resolver(version, x[1], x[2], x[3])
        return self._version_implicit_resolver[version]

    @classmethod
    def add_implicit_resolver_base(cls, tag, regexp, first):

        if "yaml_implicit_resolvers" not in cls.__dict__:
            # deepcopy doesn't work here
            cls.yaml_implicit_resolvers = dict(
                (k, cls.yaml_implicit_resolvers[k][:])
                for k in cls.yaml_implicit_resolvers
            )
        if first is None:
            first = [None]
        for ch in first:
            cls.yaml_implicit_resolvers.setdefault(ch, []).append((tag, regexp))

    @classmethod
    def add_implicit_resolver(cls, tag, regexp, first):

        if "yaml_implicit_resolvers" not in cls.__dict__:
            # deepcopy doesn't work here
            cls.yaml_implicit_resolvers = dict(
                (k, cls.yaml_implicit_resolvers[k][:])
                for k in cls.yaml_implicit_resolvers
            )
        if first is None:
            first = [None]
        for ch in first:
            cls.yaml_implicit_resolvers.setdefault(ch, []).append((tag, regexp))
        implicit_resolvers.append(([(1, 2), (1, 1)], tag, regexp, first))

    @classmethod
    def add_path_resolver(cls, tag, path, kind=None):

        # Note: `add_path_resolver` is experimental.  The API could be changed.
        # `new_path` is a pattern that is matched against the path from the
        # root to the node that is being considered.  `node_path` elements are
        # tuples `(node_check, index_check)`.  `node_check` is a node class:
        # `ScalarNode`, `SequenceNode`, `MappingNode` or `None`.  `None`
        # matches any kind of a node.  `index_check` could be `None`, a boolean
        # value, a string value, or a number.  `None` and `False` match against
        # any _value_ of sequence and mapping nodes.  `True` matches against
        # any _key_ of a mapping node.  A string `index_check` matches against
        # a mapping value that corresponds to a scalar key which content is
        # equal to the `index_check` value.  An integer `index_check` matches
        # against a sequence value with the index equal to `index_check`.
        if "yaml_path_resolvers" not in cls.__dict__:
            cls.yaml_path_resolvers = cls.yaml_path_resolvers.copy()
        new_path = []
        for element in path:
            if isinstance(element, (list, tuple)):
                if len(element) == 2:
                    node_check, index_check = element
                elif len(element) == 1:
                    node_check = element[0]
                    index_check = True
                else:
                    raise ResolverError(
                        _F("Invalid path element: {element!s}", element=element)
                    )
            else:
                node_check = None
                index_check = element
            if node_check is str:
                node_check = ScalarNode
            elif node_check is list:
                node_check = SequenceNode
            elif node_check is dict:
                node_check = MappingNode
            elif (
                node_check not in [ScalarNode, SequenceNode, MappingNode]
                and not isinstance(node_check, str)
                and node_check is not None
            ):
                raise ResolverError(
                    _F("Invalid node checker: {node_check!s}", node_check=node_check)
                )
            if not isinstance(index_check, (str, int)) and index_check is not None:
                raise ResolverError(
                    _F(
                        "Invalid index checker: {index_check!s}",
                        index_check=index_check,
                    )
                )
            new_path.append((node_check, index_check))
        if kind is str:
            kind = ScalarNode
        elif kind is list:
            kind = SequenceNode
        elif kind is dict:
            kind = MappingNode
        elif kind not in [ScalarNode, SequenceNode, MappingNode] and kind is not None:
            raise ResolverError(_F("Invalid node kind: {kind!s}", kind=kind))
        cls.yaml_path_resolvers[tuple(new_path), kind] = tag

    def descend_resolver(self, current_node: Optional[Union[MappingNode, SequenceNode]], current_index: Optional[Union[ScalarNode, SequenceNode, int]]) -> None:

        if not self.yaml_path_resolvers:
            return
        exact_paths = {}
        prefix_paths = []
        if current_node:
            depth = len(self.resolver_prefix_paths)
            for path, kind in self.resolver_prefix_paths[-1]:
                if self.check_resolver_prefix(
                    depth, path, kind, current_node, current_index
                ):
                    if len(path) > depth:
                        prefix_paths.append((path, kind))
                    else:
                        exact_paths[kind] = self.yaml_path_resolvers[path, kind]
        else:
            for path, kind in self.yaml_path_resolvers:
                if not path:
                    exact_paths[kind] = self.yaml_path_resolvers[path, kind]
                else:
                    prefix_paths.append((path, kind))
        self.resolver_exact_paths.append(exact_paths)
        self.resolver_prefix_paths.append(prefix_paths)

    def ascend_resolver(self) -> None:

        if not self.yaml_path_resolvers:
            return
        self.resolver_exact_paths.pop()
        self.resolver_prefix_paths.pop()

    def check_resolver_prefix(self, depth, path, kind, current_node, current_index):

        node_check, index_check = path[depth - 1]
        if isinstance(node_check, str):
            if current_node.tag != node_check:
                return False
        elif node_check is not None:
            if not isinstance(current_node, node_check):
                return False
        if index_check is True and current_index is not None:
            return False
        if (index_check is False or index_check is None) and current_index is None:
            return False
        if isinstance(index_check, str):
            if not (
                isinstance(current_index, ScalarNode)
                and index_check == current_index.value
            ):
                return False
        elif isinstance(index_check, int) and not isinstance(index_check, bool):
            if index_check != current_index:
                return False
        return True

    def resolve(self, kind: Union[Type[MappingNode], Type[ScalarNode], Type[SequenceNode]], value: Any, implicit: Union[bool, Tuple[bool, bool]]) -> str:

        if kind is ScalarNode and implicit[0]:
            if value == "":
                resolvers = self.versioned_resolver.get("", [])
            else:
                resolvers = self.versioned_resolver.get(value[0], [])
            resolvers += self.versioned_resolver.get(None, [])
            for tag, regexp in resolvers:
                if regexp.match(value):
                    return tag
            implicit = implicit[1]
        if bool(self.yaml_path_resolvers):
            exact_paths = self.resolver_exact_paths[-1]
            if kind in exact_paths:
                return exact_paths[kind]
            if None in exact_paths:
                return exact_paths[None]
        if kind is ScalarNode:
            return self.DEFAULT_SCALAR_TAG
        elif kind is SequenceNode:
            return self.DEFAULT_SEQUENCE_TAG
        elif kind is MappingNode:
            return self.DEFAULT_MAPPING_TAG

    @property
    def processing_version(self) -> Tuple[int, int]:

        version = None
        if self.loader:
            version = self.loader.scanner.yaml_version
        if version is None:
            version = self.loader_version
        if version is None:
            version = _DEFAULT_YAML_VERSION
        return version

