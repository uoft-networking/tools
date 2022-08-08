# coding: utf-8

import datetime
import base64
import binascii
import sys
import types
import warnings
from collections.abc import Hashable, MutableSequence, MutableMapping
from typing import TYPE_CHECKING, Tuple, cast, Optional

# fmt: off
from .error import (MarkedYAMLError, MarkedYAMLFutureWarning,
                               MantissaNoDotYAML1_1Warning)
from .nodes import *                               # NOQA
from .nodes import (SequenceNode, MappingNode, ScalarNode)
from .compat import (_F, builtins_module, # NOQA
                                nprint, nprintf, version_tnf)
from .compat import ordereddict

from .comments import *                               # NOQA
from .comments import (CommentedMap, CommentedOrderedMap, CommentedSet,
                                  CommentedKeySeq, CommentedSeq, TaggedScalar,
                                  CommentedKeyMap,
                                  C_KEY_PRE, C_KEY_EOL, C_KEY_POST,
                                  C_VALUE_PRE, C_VALUE_EOL, C_VALUE_POST,
                                  )
from .scalarstring import (SingleQuotedScalarString, DoubleQuotedScalarString,
                                      LiteralScalarString, FoldedScalarString,
                                      PlainScalarString, ScalarString,)
from .scalarint import ScalarInt, BinaryInt, OctalInt, HexInt, HexCapsInt
from .scalarfloat import ScalarFloat
from .scalarbool import ScalarBoolean
from .timestamp import TimeStamp
from .util import timestamp_regexp, create_timestamp

if TYPE_CHECKING:  # MYPY
    from typing import Any, Dict, List, Set, Generator, Union, Optional  # NOQA
    from . import YAML


__all__ = ['BaseConstructor', 'SafeConstructor',
           'ConstructorError', 'RoundTripConstructor']
# fmt: on


class ConstructorError(MarkedYAMLError):
    pass


class DuplicateKeyFutureWarning(MarkedYAMLFutureWarning):
    pass


class DuplicateKeyError(MarkedYAMLError):
    pass


class BaseConstructor:

    yaml_constructors = {}
    yaml_multi_constructors = {}

    def __init__(self, loader: "YAML"):
        self.loader = loader
        self.yaml_base_dict_type = dict
        self.yaml_base_list_type = list
        self.constructed_objects = {}
        self.recursive_objects = {}
        self.state_generators = []
        self.deep_construct = False
        self._preserve_quotes = self.loader.preserve_quotes
        self.allow_duplicate_keys = version_tnf((0, 15, 1), (0, 16))

    @property
    def composer(self):
        return self.loader.composer

    @property
    def resolver(self):
        return self.loader.resolver

    @property
    def scanner(self):
        return self.loader.scanner

    def check_data(self):
        # If there are more documents available?
        return self.composer.check_node()

    def get_data(self):
        # Construct and return the next document.
        if self.composer.check_node():
            return self.construct_document(self.composer.get_node())

    def get_single_data(self):
        # Ensure that the stream contains a single document and construct it.
        node = self.composer.get_single_node()
        if node is not None:
            return self.construct_document(node)
        return None

    def construct_document(self, node: Node):
        # type: (Any) -> Any
        data = self.construct_object(node)
        while bool(self.state_generators):
            state_generators = self.state_generators
            self.state_generators = []
            for generator in state_generators:
                for _dummy in generator:
                    pass
        self.constructed_objects = {}
        self.recursive_objects = {}
        self.deep_construct = False
        return data

    def construct_object(self, node: Node, deep=False):
        # type: (Any, bool) -> Any
        """deep is True when creating an object/mapping recursively,
        in that case want the underlying elements available during construction
        """
        original_deep_construct = None
        if node in self.constructed_objects:
            return self.constructed_objects[node]
        if deep:
            original_deep_construct = self.deep_construct
            self.deep_construct = True
        if node in self.recursive_objects:
            return self.recursive_objects[node]
            # raise ConstructorError(
            #     None, None, 'found unconstructable recursive node', node.start_mark
            # )
        self.recursive_objects[node] = None
        data = self.construct_non_recursive_object(node)

        self.constructed_objects[node] = data
        del self.recursive_objects[node]
        if original_deep_construct is not None:
            # restore the original value for deep_construct
            self.deep_construct = original_deep_construct
        return data

    def construct_non_recursive_object(self, node: Node, tag: Optional[str] = None):
        constructor = None
        tag_suffix = None
        if tag is None:
            tag = node.tag
        if tag in self.yaml_constructors:
            constructor = self.yaml_constructors[tag]
        else:
            for tag_prefix in self.yaml_multi_constructors:
                if tag and tag.startswith(tag_prefix):
                    tag_suffix = tag[len(tag_prefix) :]
                    constructor = self.yaml_multi_constructors[tag_prefix]
                    break
            else:
                if None in self.yaml_multi_constructors:
                    tag_suffix = tag
                    constructor = self.yaml_multi_constructors[None]
                elif None in self.yaml_constructors:
                    constructor = self.yaml_constructors[None]
                elif isinstance(node, ScalarNode):
                    constructor = self.__class__.construct_scalar
                elif isinstance(node, SequenceNode):
                    constructor = self.__class__.construct_sequence
                elif isinstance(node, MappingNode):
                    constructor = self.__class__.construct_mapping
                else:
                    raise ConstructorError(
                        problem=f"Could not find a constructor for node of type {type(node)}",
                        problem_mark=node.start_mark,
                    )
        if tag_suffix is None:
            data = constructor(self, node) # type: ignore
        else:
            data = constructor(self, tag_suffix, node) # type: ignore
        if isinstance(data, types.GeneratorType):
            generator = data
            data = next(generator)
            if self.deep_construct:
                for _dummy in generator:
                    pass
            else:
                self.state_generators.append(generator)
        return data

    def construct_scalar(self, node):
        if not isinstance(node, ScalarNode):
            raise ConstructorError(
                None,
                None,
                _F("expected a scalar node, but found {node_id!s}", node_id=node.id),
                node.start_mark,
            )
        return node.value

    def construct_sequence(self, node, deep=False):
        """deep is True when creating an object/mapping recursively,
        in that case want the underlying elements available during construction
        """
        if not isinstance(node, SequenceNode):
            raise ConstructorError(
                problem=f"expected a sequence node, but found {node.id!s}",
                problem_mark=node.start_mark,
            )
        return [self.construct_object(child, deep=deep) for child in node.value]

    def construct_mapping(self, node: MappingNode, deep=False):
        # type: (Any, bool) -> Any
        """deep is True when creating an object/mapping recursively,
        in that case want the underlying elements available during construction
        """
        if not isinstance(node, MappingNode):
            raise ConstructorError(
                problem=f"expected a mapping node, but found {node.id!s}",
                problem_mark=node.start_mark,
            )
        total_mapping = self.yaml_base_dict_type()
        if getattr(node, "merge", None) is not None:
            todo = [(node.merge, False), (node.value, False)]
        else:
            todo = [(node.value, True)]
        todo = cast(list[Tuple[list[Tuple[Node, Node]], bool]], todo)
        for values, check in todo:
            mapping = self.yaml_base_dict_type()
            for key_node, value_node in values:
                # keys can be list -> deep
                key = self.construct_object(key_node, deep=True)
                # lists are not hashable, but tuples are
                if not isinstance(key, Hashable):
                    if isinstance(key, list):
                        key = tuple(key)
                if not isinstance(key, Hashable):
                    raise ConstructorError(
                        context="while constructing a mapping",
                        context_mark=node.start_mark,
                        problem="found unhashable key",
                        problem_mark=key_node.start_mark,
                    )

                value = self.construct_object(value_node, deep=deep)
                if check:
                    if self.check_mapping_key(node, key_node, mapping, key, value):
                        mapping[key] = value
                else:
                    mapping[key] = value
            total_mapping.update(mapping)
        return total_mapping

    def check_mapping_key(self, node: Node, key_node: Node, mapping, key, value) -> bool:
        """return True if key is unique"""
        if key in mapping:
            if not self.allow_duplicate_keys:
                mk = mapping.get(key)
                args = [
                    "while constructing a mapping",
                    node.start_mark,
                    'found duplicate key "{}" with value "{}" '
                    '(original value: "{}")'.format(key, value, mk),
                    key_node.start_mark,
                    """
                    To suppress this check see:
                        http://yaml.readthedocs.io/en/latest/api.html#duplicate-keys
                    """,
                    """\
                    Duplicate keys will become an error in future releases, and are errors
                    by default when using the new API.
                    """,
                ]
                if self.allow_duplicate_keys is None:
                    warnings.warn(DuplicateKeyFutureWarning(*args))
                else:
                    raise DuplicateKeyError(*args)
            return False
        return True

    def check_set_key(self, node: Node, key_node, setting, key):
        if key in setting:
            if not self.allow_duplicate_keys:
                args = [
                    "while constructing a set",
                    node.start_mark,
                    'found duplicate key "{}"'.format(key),
                    key_node.start_mark,
                    """
                    To suppress this check see:
                        http://yaml.readthedocs.io/en/latest/api.html#duplicate-keys
                    """,
                    """\
                    Duplicate keys will become an error in future releases, and are errors
                    by default when using the new API.
                    """,
                ]
                if self.allow_duplicate_keys is None:
                    warnings.warn(DuplicateKeyFutureWarning(*args))
                else:
                    raise DuplicateKeyError(*args)

    def construct_pairs(self, node: Node, deep=False):
        if not isinstance(node, MappingNode):
            raise ConstructorError(
                problem=f"expected a mapping node, but found {node.id!s}",
                problem_mark=node.start_mark,
            )
        pairs = []
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            value = self.construct_object(value_node, deep=deep)
            pairs.append((key, value))
        return pairs

    @classmethod
    def add_constructor(cls, tag, constructor):
        if "yaml_constructors" not in cls.__dict__:
            cls.yaml_constructors = cls.yaml_constructors.copy()
        cls.yaml_constructors[tag] = constructor

    @classmethod
    def add_multi_constructor(cls, tag_prefix, multi_constructor):
        if "yaml_multi_constructors" not in cls.__dict__:
            cls.yaml_multi_constructors = cls.yaml_multi_constructors.copy()
        cls.yaml_multi_constructors[tag_prefix] = multi_constructor


class SafeConstructor(BaseConstructor):
    def construct_scalar(self, node):
        if isinstance(node, MappingNode):
            for key_node, value_node in node.value:
                if key_node.tag == "tag:yaml.org,2002:value":
                    return self.construct_scalar(value_node)
        return BaseConstructor.construct_scalar(self, node)

    def flatten_mapping(self, node: Node):
        """
        This implements the merge key feature http://yaml.org/type/merge.html
        by inserting keys from the merge dict/list of dicts if not yet
        available in this node
        """
        merge = []
        index = 0
        while index < len(node.value):
            key_node, value_node = node.value[index]
            if key_node.tag == "tag:yaml.org,2002:merge":
                if merge:  # double << key
                    if self.allow_duplicate_keys:
                        del node.value[index]
                        index += 1
                        continue
                    args = [
                        "while constructing a mapping",
                        node.start_mark,
                        'found duplicate key "{}"'.format(key_node.value),
                        key_node.start_mark,
                        """
                        To suppress this check see:
                           http://yaml.readthedocs.io/en/latest/api.html#duplicate-keys
                        """,
                        """\
                        Duplicate keys will become an error in future releases, and are errors
                        by default when using the new API.
                        """,
                    ]
                    if self.allow_duplicate_keys is None:
                        warnings.warn(DuplicateKeyFutureWarning(*args))
                    else:
                        raise DuplicateKeyError(*args)
                del node.value[index]
                if isinstance(value_node, MappingNode):
                    self.flatten_mapping(value_node)
                    merge.extend(value_node.value)
                elif isinstance(value_node, SequenceNode):
                    submerge = []
                    for subnode in value_node.value:
                        if not isinstance(subnode, MappingNode):
                            raise ConstructorError(
                                context="while constructing a mapping",
                                context_mark=node.start_mark,
                                problem=f"expected a mapping for merging, but found {subnode.id!s}",
                                problem_mark=subnode.start_mark,
                            )
                        self.flatten_mapping(subnode)
                        submerge.append(subnode.value)
                    submerge.reverse()
                    for value in submerge:
                        merge.extend(value)
                else:
                    raise ConstructorError(
                        context="while constructing a mapping",
                        context_mark=node.start_mark,
                        problem=f"expected a mapping or list of mappings for merging, but found {value_node.id!s}",
                        problem_mark=value_node.start_mark,
                    )
            elif key_node.tag == "tag:yaml.org,2002:value":
                key_node.tag = "tag:yaml.org,2002:str"
                index += 1
            else:
                index += 1
        if bool(merge):
            node.merge = (
                merge  # separate merge keys to be able to update without duplicate
            )
            node.value = merge + node.value

    def construct_mapping(self, node, deep=False):
        # type: (Any, bool) -> Any
        """deep is True when creating an object/mapping recursively,
        in that case want the underlying elements available during construction
        """
        if isinstance(node, MappingNode):
            self.flatten_mapping(node)
        return BaseConstructor.construct_mapping(self, node, deep=deep)

    def construct_yaml_null(self, node):
        # type: (Any) -> Any
        self.construct_scalar(node)
        return None

    # YAML 1.2 spec doesn't mention yes/no etc any more, 1.1 does
    bool_values = {
        "yes": True,
        "no": False,
        "y": True,
        "n": False,
        "true": True,
        "false": False,
        "on": True,
        "off": False,
    }

    def construct_yaml_bool(self, node):
        # type: (Any) -> bool
        value = self.construct_scalar(node)
        return self.bool_values[value.lower()]

    def construct_yaml_int(self, node):
        # type: (Any) -> int
        value_s = self.construct_scalar(node)
        value_s = value_s.replace("_", "")
        sign = +1
        if value_s[0] == "-":
            sign = -1
        if value_s[0] in "+-":
            value_s = value_s[1:]
        if value_s == "0":
            return 0
        elif value_s.startswith("0b"):
            return sign * int(value_s[2:], 2)
        elif value_s.startswith("0x"):
            return sign * int(value_s[2:], 16)
        elif value_s.startswith("0o"):
            return sign * int(value_s[2:], 8)
        elif self.resolver.processing_version == (1, 1) and value_s[0] == "0":
            return sign * int(value_s, 8)
        elif self.resolver.processing_version == (1, 1) and ":" in value_s:
            digits = [int(part) for part in value_s.split(":")]
            digits.reverse()
            base = 1
            value = 0
            for digit in digits:
                value += digit * base
                base *= 60
            return sign * value
        else:
            return sign * int(value_s)

    inf_value = 1e300
    while inf_value != inf_value * inf_value:
        inf_value *= inf_value
    nan_value = -inf_value / inf_value  # Trying to make a quiet NaN (like C99).

    def construct_yaml_float(self, node):
        # type: (Any) -> float
        value_so = self.construct_scalar(node)
        value_s = value_so.replace("_", "").lower()
        sign = +1
        if value_s[0] == "-":
            sign = -1
        if value_s[0] in "+-":
            value_s = value_s[1:]
        if value_s == ".inf":
            return sign * self.inf_value
        elif value_s == ".nan":
            return self.nan_value
        elif self.resolver.processing_version != (1, 2) and ":" in value_s:
            digits = [float(part) for part in value_s.split(":")]
            digits.reverse()
            base = 1
            value = 0.0
            for digit in digits:
                value += digit * base
                base *= 60
            return sign * value
        else:
            if self.resolver.processing_version != (1, 2) and "e" in value_s:
                # value_s is lower case independent of input
                mantissa, exponent = value_s.split("e")
                if "." not in mantissa:
                    warnings.warn(MantissaNoDotYAML1_1Warning(node, value_so))
            return sign * float(value_s)

    def construct_yaml_binary(self, node):
        # type: (Any) -> Any
        try:
            value = self.construct_scalar(node).encode("ascii")
        except UnicodeEncodeError as exc:
            raise ConstructorError(
                None,
                None,
                _F("failed to convert base64 data into ascii: {exc!s}", exc=exc),
                node.start_mark,
            )
        try:
            return base64.decodebytes(value)
        except binascii.Error as exc:
            raise ConstructorError(
                None,
                None,
                _F("failed to decode base64 data: {exc!s}", exc=exc),
                node.start_mark,
            )

    timestamp_regexp = timestamp_regexp  # moved to util 0.17.17

    def construct_yaml_timestamp(self, node, values=None):
        # type: (Any, Any) -> Any
        if values is None:
            try:
                match = self.timestamp_regexp.match(node.value)
            except TypeError:
                match = None
            if match is None:
                raise ConstructorError(
                    None,
                    None,
                    'failed to construct timestamp from "{}"'.format(node.value),
                    node.start_mark,
                )
            values = match.groupdict()
        return create_timestamp(**values)

    def construct_yaml_pairs(self, node):
        # type: (Any) -> Any
        # Note: the same code as `construct_yaml_omap`.
        pairs = []  # type: List[Any]
        yield pairs
        if not isinstance(node, SequenceNode):
            raise ConstructorError(
                "while constructing pairs",
                node.start_mark,
                _F("expected a sequence, but found {node_id!s}", node_id=node.id),
                node.start_mark,
            )
        for subnode in node.value:
            if not isinstance(subnode, MappingNode):
                raise ConstructorError(
                    "while constructing pairs",
                    node.start_mark,
                    _F(
                        "expected a mapping of length 1, but found {subnode_id!s}",
                        subnode_id=subnode.id,
                    ),
                    subnode.start_mark,
                )
            if len(subnode.value) != 1:
                raise ConstructorError(
                    "while constructing pairs",
                    node.start_mark,
                    _F(
                        "expected a single mapping item, but found {len_subnode_val:d} items",
                        len_subnode_val=len(subnode.value),
                    ),
                    subnode.start_mark,
                )
            key_node, value_node = subnode.value[0]
            key = self.construct_object(key_node)
            value = self.construct_object(value_node)
            pairs.append((key, value))



class RoundTripConstructor(SafeConstructor):
    """need to store the comments on the node itself,
    as well as on the items
    """

    def comment(self, idx):
        # type: (Any) -> Any
        assert self.loader.comment_handling is not None
        x = self.scanner.comments[idx]
        x.set_assigned()
        return x

    def comments(self, list_of_comments, idx=None):
        # type: (Any, Optional[Any]) -> Any
        # hand in the comment and optional pre, eol, post segment
        if list_of_comments is None:
            return []
        if idx is not None:
            if list_of_comments[idx] is None:
                return []
            list_of_comments = list_of_comments[idx]
        for x in list_of_comments:
            yield self.comment(x)

    def construct_scalar(self, node):
        # type: (Any) -> Any
        if not isinstance(node, ScalarNode):
            raise ConstructorError(
                None,
                None,
                _F("expected a scalar node, but found {node_id!s}", node_id=node.id),
                node.start_mark,
            )

        if node.style == "|" and isinstance(node.value, str):
            lss = LiteralScalarString(node.value, anchor=node.anchor)
            if self.loader and self.loader.comment_handling is None:
                if node.comment and node.comment[1]:
                    lss.comment = node.comment[1][0]  # type: ignore
            else:
                # NEWCMNT
                if node.comment is not None and node.comment[1]:
                    # nprintf('>>>>nc1', node.comment)
                    # EOL comment after |
                    lss.comment = self.comment(node.comment[1][0])  # type: ignore
            return lss
        if node.style == ">" and isinstance(node.value, str):
            fold_positions = []  # type: List[int]
            idx = -1
            while True:
                idx = node.value.find("\a", idx + 1)
                if idx < 0:
                    break
                fold_positions.append(idx - len(fold_positions))
            fss = FoldedScalarString(node.value.replace("\a", ""), anchor=node.anchor)
            if self.loader and self.loader.comment_handling is None:
                if node.comment and node.comment[1]:
                    fss.comment = node.comment[1][0]  # type: ignore
            else:
                # NEWCMNT
                if node.comment is not None and node.comment[1]:
                    # nprintf('>>>>nc2', node.comment)
                    # EOL comment after >
                    fss.comment = self.comment(node.comment[1][0])  # type: ignore
            if fold_positions:
                fss.fold_pos = fold_positions  # type: ignore
            return fss
        elif bool(self._preserve_quotes) and isinstance(node.value, str):
            if node.style == "'":
                return SingleQuotedScalarString(node.value, anchor=node.anchor)
            if node.style == '"':
                return DoubleQuotedScalarString(node.value, anchor=node.anchor)
        if node.anchor:
            return PlainScalarString(node.value, anchor=node.anchor)
        return node.value

    def construct_yaml_int(self, node):
        # type: (Any) -> Any
        width = None  # type: Any
        value_su = self.construct_scalar(node)
        try:
            sx = value_su.rstrip("_")
            underscore = [len(sx) - sx.rindex("_") - 1, False, False]  # type: Any
        except ValueError:
            underscore = None
        except IndexError:
            underscore = None
        value_s = value_su.replace("_", "")
        sign = +1
        if value_s[0] == "-":
            sign = -1
        if value_s[0] in "+-":
            value_s = value_s[1:]
        if value_s == "0":
            return 0
        elif value_s.startswith("0b"):
            if self.resolver.processing_version > (1, 1) and value_s[2] == "0":
                width = len(value_s[2:])
            if underscore is not None:
                underscore[1] = value_su[2] == "_"
                underscore[2] = len(value_su[2:]) > 1 and value_su[-1] == "_"
            return BinaryInt(
                sign * int(value_s[2:], 2),
                width=width,
                underscore=underscore,
                anchor=node.anchor,
            )
        elif value_s.startswith("0x"):
            # default to lower-case if no a-fA-F in string
            if self.resolver.processing_version > (1, 1) and value_s[2] == "0":
                width = len(value_s[2:])
            hex_fun = HexInt  # type: Any
            for ch in value_s[2:]:
                if ch in "ABCDEF":  # first non-digit is capital
                    hex_fun = HexCapsInt
                    break
                if ch in "abcdef":
                    break
            if underscore is not None:
                underscore[1] = value_su[2] == "_"
                underscore[2] = len(value_su[2:]) > 1 and value_su[-1] == "_"
            return hex_fun(
                sign * int(value_s[2:], 16),
                width=width,
                underscore=underscore,
                anchor=node.anchor,
            )
        elif value_s.startswith("0o"):
            if self.resolver.processing_version > (1, 1) and value_s[2] == "0":
                width = len(value_s[2:])
            if underscore is not None:
                underscore[1] = value_su[2] == "_"
                underscore[2] = len(value_su[2:]) > 1 and value_su[-1] == "_"
            return OctalInt(
                sign * int(value_s[2:], 8),
                width=width,
                underscore=underscore,
                anchor=node.anchor,
            )
        elif self.resolver.processing_version != (1, 2) and value_s[0] == "0":
            return sign * int(value_s, 8)
        elif self.resolver.processing_version != (1, 2) and ":" in value_s:
            digits = [int(part) for part in value_s.split(":")]
            digits.reverse()
            base = 1
            value = 0
            for digit in digits:
                value += digit * base
                base *= 60
            return sign * value
        elif self.resolver.processing_version > (1, 1) and value_s[0] == "0":
            # not an octal, an integer with leading zero(s)
            if underscore is not None:
                # cannot have a leading underscore
                underscore[2] = len(value_su) > 1 and value_su[-1] == "_"
            return ScalarInt(
                sign * int(value_s), width=len(value_s), underscore=underscore
            )
        elif underscore:
            # cannot have a leading underscore
            underscore[2] = len(value_su) > 1 and value_su[-1] == "_"
            return ScalarInt(
                sign * int(value_s),
                width=None,
                underscore=underscore,
                anchor=node.anchor,
            )
        elif node.anchor:
            return ScalarInt(sign * int(value_s), width=None, anchor=node.anchor)
        else:
            return sign * int(value_s)

    def construct_yaml_float(self, node):
        # type: (Any) -> Any
        def leading_zeros(v):
            # type: (Any) -> int
            lead0 = 0
            idx = 0
            while idx < len(v) and v[idx] in "0.":
                if v[idx] == "0":
                    lead0 += 1
                idx += 1
            return lead0

        # underscore = None
        m_sign = False  # type: Any
        value_so = self.construct_scalar(node)
        value_s = value_so.replace("_", "").lower()
        sign = +1
        if value_s[0] == "-":
            sign = -1
        if value_s[0] in "+-":
            m_sign = value_s[0]
            value_s = value_s[1:]
        if value_s == ".inf":
            return sign * self.inf_value
        if value_s == ".nan":
            return self.nan_value
        if self.resolver.processing_version != (1, 2) and ":" in value_s:
            digits = [float(part) for part in value_s.split(":")]
            digits.reverse()
            base = 1
            value = 0.0
            for digit in digits:
                value += digit * base
                base *= 60
            return sign * value
        if "e" in value_s:
            try:
                mantissa, exponent = value_so.split("e")
                exp = "e"
            except ValueError:
                mantissa, exponent = value_so.split("E")
                exp = "E"
            if self.resolver.processing_version != (1, 2):
                # value_s is lower case independent of input
                if "." not in mantissa:
                    warnings.warn(MantissaNoDotYAML1_1Warning(node, value_so))
            lead0 = leading_zeros(mantissa)
            width = len(mantissa)
            prec = mantissa.find(".")
            if m_sign:
                width -= 1
            e_width = len(exponent)
            e_sign = exponent[0] in "+-"
            # nprint('sf', width, prec, m_sign, exp, e_width, e_sign)
            return ScalarFloat(
                sign * float(value_s),
                width=width,
                prec=prec,
                m_sign=m_sign,
                m_lead0=lead0,
                exp=exp,
                e_width=e_width,
                e_sign=e_sign,
                anchor=node.anchor,
            )
        width = len(value_so)
        prec = value_so.index(
            "."
        )  # you can use index, this would not be float without dot
        lead0 = leading_zeros(value_so)
        return ScalarFloat(
            sign * float(value_s),
            width=width,
            prec=prec,
            m_sign=m_sign,
            m_lead0=lead0,
            anchor=node.anchor,
        )

    def construct_yaml_str(self, node):
        # type: (Any) -> Any
        value = self.construct_scalar(node)
        if isinstance(value, ScalarString):
            return value
        return value

    def construct_rt_sequence(self, node, seqtyp, deep=False):
        # type: (Any, Any, bool) -> Any
        if not isinstance(node, SequenceNode):
            raise ConstructorError(
                None,
                None,
                _F("expected a sequence node, but found {node_id!s}", node_id=node.id),
                node.start_mark,
            )
        ret_val = []
        if self.loader and self.loader.comment_handling is None:
            if node.comment:
                seqtyp._yaml_add_comment(node.comment[:2])
                if len(node.comment) > 2:
                    # this happens e.g. if you have a sequence element that is a flow-style
                    # mapping and that has no EOL comment but a following commentline or
                    # empty line
                    seqtyp.yaml_end_comment_extend(node.comment[2], clear=True)
        else:
            # NEWCMNT
            if node.comment:
                nprintf("nc3", node.comment)
        if node.anchor:
            from .serializer import templated_id

            if not templated_id(node.anchor):
                seqtyp.yaml_set_anchor(node.anchor)
        for idx, child in enumerate(node.value):
            if child.comment:
                seqtyp._yaml_add_comment(child.comment, key=idx)
                child.comment = None  # if moved to sequence remove from child
            ret_val.append(self.construct_object(child, deep=deep))
            seqtyp._yaml_set_idx_line_col(
                idx, [child.start_mark.line, child.start_mark.column]
            )
        return ret_val

    def flatten_mapping(self, node):
        # type: (Any) -> Any
        """
        This implements the merge key feature http://yaml.org/type/merge.html
        by inserting keys from the merge dict/list of dicts if not yet
        available in this node
        """

        def constructed(value_node):
            # type: (Any) -> Any
            # If the contents of a merge are defined within the
            # merge marker, then they won't have been constructed
            # yet. But if they were already constructed, we need to use
            # the existing object.
            if value_node in self.constructed_objects:
                value = self.constructed_objects[value_node]
            else:
                value = self.construct_object(value_node, deep=False)
            return value

        # merge = []
        merge_map_list = []  # type: List[Any]
        index = 0
        while index < len(node.value):
            key_node, value_node = node.value[index]
            if key_node.tag == "tag:yaml.org,2002:merge":
                if merge_map_list:  # double << key
                    if self.allow_duplicate_keys:
                        del node.value[index]
                        index += 1
                        continue
                    args = [
                        "while constructing a mapping",
                        node.start_mark,
                        'found duplicate key "{}"'.format(key_node.value),
                        key_node.start_mark,
                        """
                        To suppress this check see:
                           http://yaml.readthedocs.io/en/latest/api.html#duplicate-keys
                        """,
                        """\
                        Duplicate keys will become an error in future releases, and are errors
                        by default when using the new API.
                        """,
                    ]
                    if self.allow_duplicate_keys is None:
                        warnings.warn(DuplicateKeyFutureWarning(*args))
                    else:
                        raise DuplicateKeyError(*args)
                del node.value[index]
                if isinstance(value_node, MappingNode):
                    merge_map_list.append((index, constructed(value_node)))
                    # self.flatten_mapping(value_node)
                    # merge.extend(value_node.value)
                elif isinstance(value_node, SequenceNode):
                    # submerge = []
                    for subnode in value_node.value:
                        if not isinstance(subnode, MappingNode):
                            raise ConstructorError(
                                "while constructing a mapping",
                                node.start_mark,
                                _F(
                                    "expected a mapping for merging, but found {subnode_id!s}",
                                    subnode_id=subnode.id,
                                ),
                                subnode.start_mark,
                            )
                        merge_map_list.append((index, constructed(subnode)))
                    #     self.flatten_mapping(subnode)
                    #     submerge.append(subnode.value)
                    # submerge.reverse()
                    # for value in submerge:
                    #     merge.extend(value)
                else:
                    raise ConstructorError(
                        "while constructing a mapping",
                        node.start_mark,
                        _F(
                            "expected a mapping or list of mappings for merging, "
                            "but found {value_node_id!s}",
                            value_node_id=value_node.id,
                        ),
                        value_node.start_mark,
                    )
            elif key_node.tag == "tag:yaml.org,2002:value":
                key_node.tag = "tag:yaml.org,2002:str"
                index += 1
            else:
                index += 1
        return merge_map_list
        # if merge:
        #     node.value = merge + node.value

    def _sentinel(self):
        # type: () -> None
        pass

    def construct_mapping(self, node, maptyp, deep=False):  # type: ignore
        # type: (Any, Any, bool) -> Any
        if not isinstance(node, MappingNode):
            raise ConstructorError(
                None,
                None,
                _F("expected a mapping node, but found {node_id!s}", node_id=node.id),
                node.start_mark,
            )
        merge_map = self.flatten_mapping(node)
        # mapping = {}
        if self.loader and self.loader.comment_handling is None:
            if node.comment:
                maptyp._yaml_add_comment(node.comment[:2])
                if len(node.comment) > 2:
                    maptyp.yaml_end_comment_extend(node.comment[2], clear=True)
        else:
            # NEWCMNT
            if node.comment:
                # nprintf('nc4', node.comment, node.start_mark)
                if maptyp.ca.pre is None:
                    maptyp.ca.pre = []
                for cmnt in self.comments(node.comment, 0):
                    maptyp.ca.pre.append(cmnt)
        if node.anchor:
            from .serializer import templated_id

            if not templated_id(node.anchor):
                maptyp.yaml_set_anchor(node.anchor)
        last_key, last_value = None, self._sentinel
        for key_node, value_node in node.value:
            # keys can be list -> deep
            key = self.construct_object(key_node, deep=True)
            # lists are not hashable, but tuples are
            if not isinstance(key, Hashable):
                if isinstance(key, MutableSequence):
                    key_s = CommentedKeySeq(key)
                    if key_node.flow_style is True:
                        key_s.fa.set_flow_style()
                    elif key_node.flow_style is False:
                        key_s.fa.set_block_style()
                    key = key_s
                elif isinstance(key, MutableMapping):
                    key_m = CommentedKeyMap(key)
                    if key_node.flow_style is True:
                        key_m.fa.set_flow_style()
                    elif key_node.flow_style is False:
                        key_m.fa.set_block_style()
                    key = key_m
            if not isinstance(key, Hashable):
                raise ConstructorError(
                    "while constructing a mapping",
                    node.start_mark,
                    "found unhashable key",
                    key_node.start_mark,
                )
            value = self.construct_object(value_node, deep=deep)
            if self.check_mapping_key(node, key_node, maptyp, key, value):
                if self.loader and self.loader.comment_handling is None:
                    if (
                        key_node.comment
                        and len(key_node.comment) > 4
                        and key_node.comment[4]
                    ):
                        if last_value is None:
                            key_node.comment[0] = key_node.comment.pop(4)
                            maptyp._yaml_add_comment(key_node.comment, value=last_key)
                        else:
                            key_node.comment[2] = key_node.comment.pop(4)
                            maptyp._yaml_add_comment(key_node.comment, key=key)
                        key_node.comment = None
                    if key_node.comment:
                        maptyp._yaml_add_comment(key_node.comment, key=key)
                    if value_node.comment:
                        maptyp._yaml_add_comment(value_node.comment, value=key)
                else:
                    # NEWCMNT
                    if key_node.comment:
                        nprintf("nc5a", key, key_node.comment)
                        if key_node.comment[0]:
                            maptyp.ca.set(key, C_KEY_PRE, key_node.comment[0])
                        if key_node.comment[1]:
                            maptyp.ca.set(key, C_KEY_EOL, key_node.comment[1])
                        if key_node.comment[2]:
                            maptyp.ca.set(key, C_KEY_POST, key_node.comment[2])
                    if value_node.comment:
                        nprintf("nc5b", key, value_node.comment)
                        if value_node.comment[0]:
                            maptyp.ca.set(key, C_VALUE_PRE, value_node.comment[0])
                        if value_node.comment[1]:
                            maptyp.ca.set(key, C_VALUE_EOL, value_node.comment[1])
                        if value_node.comment[2]:
                            maptyp.ca.set(key, C_VALUE_POST, value_node.comment[2])
                maptyp._yaml_set_kv_line_col(
                    key,
                    [
                        key_node.start_mark.line,
                        key_node.start_mark.column,
                        value_node.start_mark.line,
                        value_node.start_mark.column,
                    ],
                )
                maptyp[key] = value
                last_key, last_value = key, value  # could use indexing
        # do this last, or <<: before a key will prevent insertion in instances
        # of collections.OrderedDict (as they have no __contains__
        if merge_map:
            maptyp.add_yaml_merge(merge_map)

    def construct_setting(self, node, typ, deep=False):
        # type: (Any, Any, bool) -> Any
        if not isinstance(node, MappingNode):
            raise ConstructorError(
                None,
                None,
                _F("expected a mapping node, but found {node_id!s}", node_id=node.id),
                node.start_mark,
            )
        if self.loader and self.loader.comment_handling is None:
            if node.comment:
                typ._yaml_add_comment(node.comment[:2])
                if len(node.comment) > 2:
                    typ.yaml_end_comment_extend(node.comment[2], clear=True)
        else:
            # NEWCMNT
            if node.comment:
                nprintf("nc6", node.comment)
        if node.anchor:
            from .serializer import templated_id

            if not templated_id(node.anchor):
                typ.yaml_set_anchor(node.anchor)
        for key_node, value_node in node.value:
            # keys can be list -> deep
            key = self.construct_object(key_node, deep=True)
            # lists are not hashable, but tuples are
            if not isinstance(key, Hashable):
                if isinstance(key, list):
                    key = tuple(key)
            if not isinstance(key, Hashable):
                raise ConstructorError(
                    "while constructing a mapping",
                    node.start_mark,
                    "found unhashable key",
                    key_node.start_mark,
                )
            # construct but should be null
            value = self.construct_object(value_node, deep=deep)  # NOQA
            self.check_set_key(node, key_node, typ, key)
            if self.loader and self.loader.comment_handling is None:
                if key_node.comment:
                    typ._yaml_add_comment(key_node.comment, key=key)
                if value_node.comment:
                    typ._yaml_add_comment(value_node.comment, value=key)
            else:
                # NEWCMNT
                if key_node.comment:
                    nprintf("nc7a", key_node.comment)
                if value_node.comment:
                    nprintf("nc7b", value_node.comment)
            typ.add(key)

    def construct_yaml_seq(self, node):
        # type: (Any) -> Any
        data = CommentedSeq()
        data._yaml_set_line_col(node.start_mark.line, node.start_mark.column)
        # if node.comment:
        #    data._yaml_add_comment(node.comment)
        yield data
        data.extend(self.construct_rt_sequence(node, data))
        self.set_collection_style(data, node)

    def construct_yaml_map(self, node):
        # type: (Any) -> Any
        data = CommentedMap()
        data._yaml_set_line_col(node.start_mark.line, node.start_mark.column)
        yield data
        self.construct_mapping(node, data, deep=True)
        self.set_collection_style(data, node)

    def set_collection_style(self, data, node):
        # type: (Any, Any) -> None
        if len(data) == 0:
            return
        if node.flow_style is True:
            data.fa.set_flow_style()
        elif node.flow_style is False:
            data.fa.set_block_style()

    def construct_yaml_object(self, node, cls):
        # type: (Any, Any) -> Any
        data = cls.__new__(cls)
        yield data
        if hasattr(data, "__setstate__"):
            state = SafeConstructor.construct_mapping(self, node, deep=True)
            data.__setstate__(state)
        else:
            state = SafeConstructor.construct_mapping(self, node)
            if hasattr(data, "__attrs_attrs__"):  # issue 394
                data.__init__(**state)
            else:
                data.__dict__.update(state)
        if node.anchor:
            from .serializer import templated_id
            from .anchor import Anchor

            if not templated_id(node.anchor):
                if not hasattr(data, Anchor.attrib):
                    a = Anchor()
                    setattr(data, Anchor.attrib, a)
                else:
                    a = getattr(data, Anchor.attrib)
                a.value = node.anchor

    def construct_yaml_omap(self, node):
        # type: (Any) -> Any
        # Note: we do now check for duplicate keys
        omap = CommentedOrderedMap()
        omap._yaml_set_line_col(node.start_mark.line, node.start_mark.column)
        if node.flow_style is True:
            omap.fa.set_flow_style()
        elif node.flow_style is False:
            omap.fa.set_block_style()
        yield omap
        if self.loader and self.loader.comment_handling is None:
            if node.comment:
                omap._yaml_add_comment(node.comment[:2])
                if len(node.comment) > 2:
                    omap.yaml_end_comment_extend(node.comment[2], clear=True)
        else:
            # NEWCMNT
            if node.comment:
                nprintf("nc8", node.comment)
        if not isinstance(node, SequenceNode):
            raise ConstructorError(
                "while constructing an ordered map",
                node.start_mark,
                _F("expected a sequence, but found {node_id!s}", node_id=node.id),
                node.start_mark,
            )
        for subnode in node.value:
            if not isinstance(subnode, MappingNode):
                raise ConstructorError(
                    "while constructing an ordered map",
                    node.start_mark,
                    _F(
                        "expected a mapping of length 1, but found {subnode_id!s}",
                        subnode_id=subnode.id,
                    ),
                    subnode.start_mark,
                )
            if len(subnode.value) != 1:
                raise ConstructorError(
                    "while constructing an ordered map",
                    node.start_mark,
                    _F(
                        "expected a single mapping item, but found {len_subnode_val:d} items",
                        len_subnode_val=len(subnode.value),
                    ),
                    subnode.start_mark,
                )
            key_node, value_node = subnode.value[0]
            key = self.construct_object(key_node)
            assert key not in omap
            value = self.construct_object(value_node)
            if self.loader and self.loader.comment_handling is None:
                if key_node.comment:
                    omap._yaml_add_comment(key_node.comment, key=key)
                if subnode.comment:
                    omap._yaml_add_comment(subnode.comment, key=key)
                if value_node.comment:
                    omap._yaml_add_comment(value_node.comment, value=key)
            else:
                # NEWCMNT
                if key_node.comment:
                    nprintf("nc9a", key_node.comment)
                if subnode.comment:
                    nprintf("nc9b", subnode.comment)
                if value_node.comment:
                    nprintf("nc9c", value_node.comment)
            omap[key] = value

    def construct_yaml_set(self, node):
        # type: (Any) -> Any
        data = CommentedSet()
        data._yaml_set_line_col(node.start_mark.line, node.start_mark.column)
        yield data
        self.construct_setting(node, data)

    def construct_undefined(self, node):
        # type: (Any) -> Any
        try:
            if isinstance(node, MappingNode):
                data = CommentedMap()
                data._yaml_set_line_col(node.start_mark.line, node.start_mark.column)
                if node.flow_style is True:
                    data.fa.set_flow_style()
                elif node.flow_style is False:
                    data.fa.set_block_style()
                data.yaml_set_tag(node.tag)
                yield data
                if node.anchor:
                    from .serializer import templated_id

                    if not templated_id(node.anchor):
                        data.yaml_set_anchor(node.anchor)
                self.construct_mapping(node, data)
                return
            elif isinstance(node, ScalarNode):
                data2 = TaggedScalar()
                data2.value = self.construct_scalar(node)
                data2.style = node.style
                data2.yaml_set_tag(node.tag)
                yield data2
                if node.anchor:
                    from .serializer import templated_id

                    if not templated_id(node.anchor):
                        data2.yaml_set_anchor(node.anchor, always_dump=True)
                return
            elif isinstance(node, SequenceNode):
                data3 = CommentedSeq()
                data3._yaml_set_line_col(node.start_mark.line, node.start_mark.column)
                if node.flow_style is True:
                    data3.fa.set_flow_style()
                elif node.flow_style is False:
                    data3.fa.set_block_style()
                data3.yaml_set_tag(node.tag)
                yield data3
                if node.anchor:
                    from .serializer import templated_id

                    if not templated_id(node.anchor):
                        data3.yaml_set_anchor(node.anchor)
                data3.extend(self.construct_sequence(node))
                return
        except:  # NOQA
            pass
        raise ConstructorError(
            None,
            None,
            _F(
                "could not determine a constructor for the tag {node_tag!r}",
                node_tag=node.tag,
            ),
            node.start_mark,
        )

    def construct_yaml_timestamp(self, node, values=None):
        # type: (Any, Any) -> Any
        try:
            match = self.timestamp_regexp.match(node.value)
        except TypeError:
            match = None
        if match is None:
            raise ConstructorError(
                None,
                None,
                'failed to construct timestamp from "{}"'.format(node.value),
                node.start_mark,
            )
        values = match.groupdict()
        if not values["hour"]:
            return create_timestamp(**values)
            # return SafeConstructor.construct_yaml_timestamp(self, node, values)
        for part in ["t", "tz_sign", "tz_hour", "tz_minute"]:
            if values[part]:
                break
        else:
            return create_timestamp(**values)
            # return SafeConstructor.construct_yaml_timestamp(self, node, values)
        dd = create_timestamp(**values)  # this has delta applied
        delta = None
        if values["tz_sign"]:
            tz_hour = int(values["tz_hour"])
            minutes = values["tz_minute"]
            tz_minute = int(minutes) if minutes else 0
            delta = datetime.timedelta(hours=tz_hour, minutes=tz_minute)
            if values["tz_sign"] == "-":
                delta = -delta
        # should check for None and solve issue 366 should be tzinfo=delta)
        data = TimeStamp(
            dd.year, dd.month, dd.day, dd.hour, dd.minute, dd.second, dd.microsecond
        )
        if delta:
            data._yaml["delta"] = delta
            tz = values["tz_sign"] + values["tz_hour"]
            if values["tz_minute"]:
                tz += ":" + values["tz_minute"]
            data._yaml["tz"] = tz
        else:
            if values["tz"]:  # no delta
                data._yaml["tz"] = values["tz"]

        if values["t"]:
            data._yaml["t"] = True
        return data

    def construct_yaml_bool(self, node):
        # type: (Any) -> Any
        b = SafeConstructor.construct_yaml_bool(self, node)
        if node.anchor:
            return ScalarBoolean(b, anchor=node.anchor)
        return b


RoundTripConstructor.add_constructor(
    "tag:yaml.org,2002:null", RoundTripConstructor.construct_yaml_null
)

RoundTripConstructor.add_constructor(
    "tag:yaml.org,2002:bool", RoundTripConstructor.construct_yaml_bool
)

RoundTripConstructor.add_constructor(
    "tag:yaml.org,2002:int", RoundTripConstructor.construct_yaml_int
)

RoundTripConstructor.add_constructor(
    "tag:yaml.org,2002:float", RoundTripConstructor.construct_yaml_float
)

RoundTripConstructor.add_constructor(
    "tag:yaml.org,2002:binary", RoundTripConstructor.construct_yaml_binary
)

RoundTripConstructor.add_constructor(
    "tag:yaml.org,2002:timestamp", RoundTripConstructor.construct_yaml_timestamp
)

RoundTripConstructor.add_constructor(
    "tag:yaml.org,2002:omap", RoundTripConstructor.construct_yaml_omap
)

RoundTripConstructor.add_constructor(
    "tag:yaml.org,2002:pairs", RoundTripConstructor.construct_yaml_pairs
)

RoundTripConstructor.add_constructor(
    "tag:yaml.org,2002:set", RoundTripConstructor.construct_yaml_set
)

RoundTripConstructor.add_constructor(
    "tag:yaml.org,2002:str", RoundTripConstructor.construct_yaml_str
)

RoundTripConstructor.add_constructor(
    "tag:yaml.org,2002:seq", RoundTripConstructor.construct_yaml_seq
)

RoundTripConstructor.add_constructor(
    "tag:yaml.org,2002:map", RoundTripConstructor.construct_yaml_map
)

RoundTripConstructor.add_constructor(None, RoundTripConstructor.construct_undefined)
