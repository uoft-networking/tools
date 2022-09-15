# coding: utf-8
from __future__ import annotations

from .error import *  # NOQA
from .nodes import *  # NOQA
from .compat import ordereddict
from .compat import _F, nprint, nprintf  # NOQA
from .scalarstring import (
    LiteralScalarString,
    FoldedScalarString,
    SingleQuotedScalarString,
    DoubleQuotedScalarString,
    PlainScalarString,
)
from .comments import (
    CommentedMap,
    CommentedOrderedMap,
    CommentedSeq,
    CommentedKeySeq,
    CommentedKeyMap,
    CommentedSet,
    comment_attrib,
    merge_attrib,
    TaggedScalar,
)
from .scalarint import ScalarInt, BinaryInt, OctalInt, HexInt, HexCapsInt
from .scalarfloat import ScalarFloat
from .scalarbool import ScalarBoolean
from .timestamp import TimeStamp
from .anchor import Anchor

import datetime
import sys
import types

import copyreg
import base64
from collections import OrderedDict

from typing import TYPE_CHECKING
from uoft_core.yaml.anchor import Anchor
from uoft_core.yaml.comments import CommentedKeySeq, CommentedMap, CommentedOrderedMap, CommentedSeq, CommentedSet, TaggedScalar
from uoft_core.yaml.compat import ordereddict
if TYPE_CHECKING:
    from uoft_core.yaml.main import Dumper
from uoft_core.yaml.nodes import MappingNode, ScalarNode, SequenceNode
from uoft_core.yaml.scalarfloat import ScalarFloat
from uoft_core.yaml.scalarint import BinaryInt, HexInt, HexCapsInt, OctalInt, ScalarInt
from uoft_core.yaml.scalarstring import DoubleQuotedScalarString, FoldedScalarString, LiteralScalarString, PlainScalarString, SingleQuotedScalarString
from uoft_core.yaml.serializer import Serializer
from uoft_core.yaml.tokens import CommentToken

if TYPE_CHECKING:
    from typing import Dict, List, Any, Union, Text, Optional  # NOQA

# fmt: off
__all__ = ['Representer', 'SafeRepresenter', 'Representer',
           'RepresenterError']
# fmt: on


class RepresenterError(YAMLError):
    pass


class Representer:

    yaml_representers = {}
    yaml_multi_representers = {}

    def __init__(self, dumper: Dumper) -> None:

        self.dumper = dumper
        self.default_style = dumper.conf.default_style
        self.default_flow_style = dumper.conf.default_flow_style
        self.represented_objects = {}
        self.object_keeper = []
        self.alias_key = None
        if (sbmt := dumper.conf.sort_base_mapping_type_on_output) is not None:
            self.sort_base_mapping_type_on_output = sbmt
        else:
            self.sort_base_mapping_type_on_output = True
        
        self.yaml_representers = {
            str: self.represent_str,
            bytes: self.represent_binary,
            bool: self.represent_bool,
            int: self.represent_int,
            float: self.represent_float,
            list: self.represent_list,
            tuple: self.represent_list,
            dict: self.represent_dict,
            set: self.represent_set,
            OrderedDict: self.represent_ordereddict,
            datetime.date: self.represent_date,
            datetime.datetime: self.represent_datetime,
            None: self.represent_undefined,
            type(None): self.represent_none,
            LiteralScalarString: self.represent_literal_scalarstring,
            FoldedScalarString: self.represent_folded_scalarstring,
            SingleQuotedScalarString: self.represent_single_quoted_scalarstring,
            DoubleQuotedScalarString: self.represent_double_quoted_scalarstring,
            PlainScalarString: self.represent_plain_scalarstring,
            ScalarInt: self.represent_scalar_int,
            BinaryInt: self.represent_binary_int,
            OctalInt: self.represent_octal_int,
            HexInt: self.represent_hex_int,
            HexCapsInt: self.represent_hex_caps_int,
            ScalarFloat: self.represent_scalar_float,
            ScalarBoolean: self.represent_scalar_bool,
            CommentedSeq: self.represent_list,
            CommentedMap: self.represent_dict,
            CommentedOrderedMap: self.represent_ordereddict,
            OrderedDict: self.represent_ordereddict,
            CommentedSet: self.represent_set,
            TaggedScalar: self.represent_tagged_scalar,
            TimeStamp: self.represent_datetime,
        }

    @property
    def serializer(self) -> Serializer:
        return self.dumper.serializer

    def represent(self, data: Any) -> None:

        node = self.represent_data(data)
        self.serializer.serialize(node)
        self.represented_objects = {}
        self.object_keeper = []
        self.alias_key = None

    def represent_data(self, data: Any) -> MappingNode | SequenceNode | ScalarNode:

        if self.ignore_aliases(data):
            self.alias_key = None
        else:
            self.alias_key = id(data)
        if self.alias_key is not None:
            if self.alias_key in self.represented_objects:
                node = self.represented_objects[self.alias_key]
                # if node is None:
                #     raise RepresenterError(
                #          f"recursive objects are not allowed: {data!r}")
                return node
            # self.represented_objects[alias_key] = None
            self.object_keeper.append(data)
        data_types = type(data).__mro__
        if data_types[0] in self.yaml_representers:
            node = self.yaml_representers[data_types[0]](data)
        else:
            for data_type in data_types:
                if data_type in self.yaml_multi_representers:
                    node = self.yaml_multi_representers[data_type](data)
                    break
            else:
                if None in self.yaml_multi_representers:
                    node = self.yaml_multi_representers[None](data)
                elif None in self.yaml_representers:
                    node = self.yaml_representers[None](data)
                else:
                    node = ScalarNode(None, str(data))
        # if alias_key is not None:
        #     self.represented_objects[alias_key] = node
        return node

    def represent_key(self, data: Union[int, str]) -> MappingNode | SequenceNode | ScalarNode:

        """
        David Fraser: Extract a method to represent keys in mappings, so that
        a subclass can choose not to quote them (for example)
        used in represent_mapping
        https://bitbucket.org/davidfraser/pyyaml/commits/d81df6eb95f20cac4a79eed95ae553b5c6f77b8c
        """
        if isinstance(data, CommentedKeySeq):
            self.alias_key = None
            return self.represent_sequence(
                "tag:yaml.org,2002:seq", data, flow_style=True
            )
        if isinstance(data, CommentedKeyMap):
            self.alias_key = None
            return self.represent_mapping(
                "tag:yaml.org,2002:map", data, flow_style=True
            )
        return self.represent_data(data)

    @classmethod
    def add_representer(cls, data_type, representer):

        if "yaml_representers" not in cls.__dict__:
            cls.yaml_representers = cls.yaml_representers.copy()
        cls.yaml_representers[data_type] = representer

    @classmethod
    def add_multi_representer(cls, data_type, representer):

        if "yaml_multi_representers" not in cls.__dict__:
            cls.yaml_multi_representers = cls.yaml_multi_representers.copy()
        cls.yaml_multi_representers[data_type] = representer

    def represent_scalar(self, tag: str, value: Union[str, DoubleQuotedScalarString, PlainScalarString, SingleQuotedScalarString, LiteralScalarString], style: Optional[str]=None, anchor: Optional[Anchor]=None) -> ScalarNode:

        if style is None:
            style = self.default_style
        comment = None
        if style and style[0] in "|>":
            comment = getattr(value, "comment", None)
            if comment:
                comment = [None, [comment]]
        node = ScalarNode(tag, value, style=style, comment=comment, anchor=anchor)
        if self.alias_key is not None:
            self.represented_objects[self.alias_key] = node
        return node

    def represent_tagged_scalar(self, data: TaggedScalar) -> ScalarNode:

        try:
            tag = data.tag.value
        except AttributeError:
            tag = None
        try:
            anchor = data.yaml_anchor()
        except AttributeError:
            anchor = None
        return self.represent_scalar(tag, data.value, style=data.style, anchor=anchor)

    def represent_literal_scalarstring(self, data: LiteralScalarString) -> ScalarNode:

        tag = None
        style = "|"
        anchor = data.yaml_anchor(any=True)
        tag = "tag:yaml.org,2002:str"
        return self.represent_scalar(tag, data, style=style, anchor=anchor)

    represent_preserved_scalarstring = represent_literal_scalarstring

    def represent_folded_scalarstring(self, data: FoldedScalarString) -> ScalarNode:

        tag = None
        style = ">"
        anchor = data.yaml_anchor(any=True)
        for fold_pos in reversed(getattr(data, "fold_pos", [])):
            if (
                data[fold_pos] == " "
                and (fold_pos > 0 and not data[fold_pos - 1].isspace())
                and (fold_pos < len(data) and not data[fold_pos + 1].isspace())
            ):
                data = data[:fold_pos] + "\a" + data[fold_pos:]
        tag = "tag:yaml.org,2002:str"
        return self.represent_scalar(tag, data, style=style, anchor=anchor)

    def represent_single_quoted_scalarstring(self, data: SingleQuotedScalarString) -> ScalarNode:

        tag = None
        style = "'"
        anchor = data.yaml_anchor(any=True)
        tag = "tag:yaml.org,2002:str"
        return self.represent_scalar(tag, data, style=style, anchor=anchor)

    def represent_double_quoted_scalarstring(self, data: DoubleQuotedScalarString) -> ScalarNode:

        tag = None
        style = '"'
        anchor = data.yaml_anchor(any=True)
        tag = "tag:yaml.org,2002:str"
        return self.represent_scalar(tag, data, style=style, anchor=anchor)

    def represent_plain_scalarstring(self, data: PlainScalarString) -> ScalarNode:

        tag = None
        style = ""
        anchor = data.yaml_anchor(any=True)
        tag = "tag:yaml.org,2002:str"
        return self.represent_scalar(tag, data, style=style, anchor=anchor)

    def represent_sequence(self, tag: str, sequence: Union[CommentedSeq, CommentedKeySeq], flow_style: Optional[bool]=None) -> SequenceNode:

        value = []
        # if the flow_style is None, the flow style tacked on to the object
        # explicitly will be taken. If that is None as well the default flow
        # style rules
        try:
            flow_style = sequence.fa.flow_style(flow_style)
        except AttributeError:
            flow_style = flow_style
        try:
            anchor = sequence.yaml_anchor()
        except AttributeError:
            anchor = None
        node = SequenceNode(tag, value, flow_style=flow_style, anchor=anchor)
        if self.alias_key is not None:
            self.represented_objects[self.alias_key] = node
        best_style = True
        try:
            comment = getattr(sequence, comment_attrib)
            node.comment = comment.comment
            # reset any comment already printed information
            if node.comment and node.comment[1]:
                for ct in node.comment[1]:
                    ct.reset()
            item_comments = comment.items
            for v in item_comments.values():
                if v and v[1]:
                    for ct in v[1]:
                        ct.reset()
            item_comments = comment.items
            if node.comment is None:
                node.comment = comment.comment
            else:
                # as we are potentially going to extend this, make a new list
                node.comment = comment.comment[:]
            try:
                node.comment.append(comment.end)
            except AttributeError:
                pass
        except AttributeError:
            item_comments = {}
        for idx, item in enumerate(sequence):
            node_item = self.represent_data(item)
            self.merge_comments(node_item, item_comments.get(idx))
            if not (isinstance(node_item, ScalarNode) and not node_item.style):
                best_style = False
            value.append(node_item)
        if flow_style is None:
            if len(sequence) != 0 and self.default_flow_style is not None:
                node.flow_style = self.default_flow_style
            else:
                node.flow_style = best_style
        return node

    def represent_omap(self, tag: str, omap: Union[OrderedDict, CommentedOrderedMap], flow_style: None=None) -> SequenceNode:

        value = []
        try:
            flow_style = omap.fa.flow_style(flow_style)
        except AttributeError:
            flow_style = flow_style
        try:
            anchor = omap.yaml_anchor()
        except AttributeError:
            anchor = None
        node = SequenceNode(tag, value, flow_style=flow_style, anchor=anchor)
        if self.alias_key is not None:
            self.represented_objects[self.alias_key] = node
        best_style = True
        try:
            comment = getattr(omap, comment_attrib)
            if node.comment is None:
                node.comment = comment.comment
            else:
                # as we are potentially going to extend this, make a new list
                node.comment = comment.comment[:]
            if node.comment and node.comment[1]:
                for ct in node.comment[1]:
                    ct.reset()
            item_comments = comment.items
            for v in item_comments.values():
                if v and v[1]:
                    for ct in v[1]:
                        ct.reset()
            try:
                node.comment.append(comment.end)
            except AttributeError:
                pass
        except AttributeError:
            item_comments = {}
        for item_key in omap:
            item_val = omap[item_key]
            node_item = self.represent_data({item_key: item_val})
            # node_item.flow_style = False
            # node item has two scalars in value: node_key and node_value
            item_comment = item_comments.get(item_key)
            if item_comment:
                if item_comment[1]:
                    node_item.comment = [None, item_comment[1]]
                assert getattr(node_item.value[0][0], "comment", None) is None
                node_item.value[0][0].comment = [item_comment[0], None]
                nvc = getattr(node_item.value[0][1], "comment", None)
                if nvc is not None:  # end comment already there
                    nvc[0] = item_comment[2]
                    nvc[1] = item_comment[3]
                else:
                    node_item.value[0][1].comment = item_comment[2:]
            # if not (isinstance(node_item, ScalarNode) \
            #    and not node_item.style):
            #     best_style = False
            value.append(node_item)
        if flow_style is None:
            if self.default_flow_style is not None:
                node.flow_style = self.default_flow_style
            else:
                node.flow_style = best_style
        return node

    def represent_mapping(self, tag: str, mapping: Dict[str, int] | CommentedMap, flow_style: None=None) -> MappingNode:

        value = []
        try:
            flow_style = mapping.fa.flow_style(flow_style)
        except AttributeError:
            flow_style = flow_style
        try:
            anchor = mapping.yaml_anchor()
        except AttributeError:
            anchor = None
        node = MappingNode(tag, value, flow_style=flow_style, anchor=anchor)
        if self.alias_key is not None:
            self.represented_objects[self.alias_key] = node
        best_style = True
        # no sorting! !!
        try:
            comment = getattr(mapping, comment_attrib)
            if node.comment is None:
                node.comment = comment.comment
            else:
                # as we are potentially going to extend this, make a new list
                node.comment = comment.comment[:]
            if node.comment and node.comment[1]:
                for ct in node.comment[1]:
                    ct.reset()
            item_comments = comment.items
            if self.dumper.conf.comment_handling is None:
                for v in item_comments.values():
                    if v and v[1]:
                        for ct in v[1]:
                            ct.reset()
                try:
                    node.comment.append(comment.end)
                except AttributeError:
                    pass
            else:
                # NEWCMNT
                pass
        except AttributeError:
            item_comments = {}
        merge_list = [m[1] for m in getattr(mapping, merge_attrib, [])]
        try:
            merge_pos = getattr(mapping, merge_attrib, [[0]])[0][0]
        except IndexError:
            merge_pos = 0
        item_count = 0
        if bool(merge_list):
            items = mapping.non_merged_items()
        else:
            items = mapping.items()
        for item_key, item_value in items:
            item_count += 1
            node_key = self.represent_key(item_key)
            node_value = self.represent_data(item_value)
            item_comment = item_comments.get(item_key)
            if item_comment:
                # assert getattr(node_key, 'comment', None) is None
                # issue 351 did throw this because the comment from the list item was
                # moved to the dict
                node_key.comment = item_comment[:2]
                nvc = getattr(node_value, "comment", None)
                if nvc is not None:  # end comment already there
                    nvc[0] = item_comment[2]
                    nvc[1] = item_comment[3]
                else:
                    node_value.comment = item_comment[2:]
            if not (isinstance(node_key, ScalarNode) and not node_key.style):
                best_style = False
            if not (isinstance(node_value, ScalarNode) and not node_value.style):
                best_style = False
            value.append((node_key, node_value))
        if flow_style is None:
            if (
                (item_count != 0) or bool(merge_list)
            ) and self.default_flow_style is not None:
                node.flow_style = self.default_flow_style
            else:
                node.flow_style = best_style
        if bool(merge_list):
            # because of the call to represent_data here, the anchors
            # are marked as being used and thereby created
            if len(merge_list) == 1:
                arg = self.represent_data(merge_list[0])
            else:
                arg = self.represent_data(merge_list)
                arg.flow_style = True
            value.insert(merge_pos, (ScalarNode("tag:yaml.org,2002:merge", "<<"), arg))
        return node

    def represent_none(self, data: None) -> ScalarNode:

        if (
            len(self.represented_objects) == 0
            and not self.serializer.use_explicit_start
        ):
            # this will be open ended (although it is not yet)
            return self.represent_scalar("tag:yaml.org,2002:null", "null")
        return self.represent_scalar("tag:yaml.org,2002:null", "")

    def represent_str(self, data: str) -> ScalarNode:

        return self.represent_scalar("tag:yaml.org,2002:str", data)

    def represent_binary(self, data):

        if hasattr(base64, "encodebytes"):
            data = base64.encodebytes(data).decode("ascii")
        else:
            # check py2 only?
            data = base64.encodestring(data).decode("ascii")
        return self.represent_scalar("tag:yaml.org,2002:binary", data, style="|")

    def represent_bool(self, data, anchor=None):
        
        try:
            anchor = data.yaml_anchor()
        except AttributeError:
            anchor = None

        value = bool(data)
        return self.represent_scalar("tag:yaml.org,2002:bool", value, anchor=anchor)

    def represent_scalar_bool(self, data):

        try:
            anchor = data.yaml_anchor()
        except AttributeError:
            anchor = None
        return self.represent_bool(data, anchor=anchor)

    def represent_int(self, data: int) -> ScalarNode:

        return self.represent_scalar("tag:yaml.org,2002:int", str(data))

    def represent_scalar_int(self, data: ScalarInt) -> ScalarNode:

        if data._width is not None:
            s = "{:0{}d}".format(data, data._width)
        else:
            s = format(data, "d")
        anchor = data.yaml_anchor(any=True)
        return self.insert_underscore("", s, data._underscore, anchor=anchor)

    def represent_binary_int(self, data: BinaryInt) -> ScalarNode:

        if data._width is not None:
            # cannot use '{:#0{}b}', that strips the zeros
            s = "{:0{}b}".format(data, data._width)
        else:
            s = format(data, "b")
        anchor = data.yaml_anchor(any=True)
        return self.insert_underscore("0b", s, data._underscore, anchor=anchor)

    def represent_octal_int(self, data: OctalInt) -> ScalarNode:

        if data._width is not None:
            # cannot use '{:#0{}o}', that strips the zeros
            s = "{:0{}o}".format(data, data._width)
        else:
            s = format(data, "o")
        anchor = data.yaml_anchor(any=True)
        return self.insert_underscore("0o", s, data._underscore, anchor=anchor)

    def represent_hex_int(self, data: HexInt) -> ScalarNode:

        if data._width is not None:
            # cannot use '{:#0{}x}', that strips the zeros
            s = "{:0{}x}".format(data, data._width)
        else:
            s = format(data, "x")
        anchor = data.yaml_anchor(any=True)
        return self.insert_underscore("0x", s, data._underscore, anchor=anchor)

    def represent_hex_caps_int(self, data: HexCapsInt) -> ScalarNode:

        if data._width is not None:
            # cannot use '{:#0{}X}', that strips the zeros
            s = "{:0{}X}".format(data, data._width)
        else:
            s = format(data, "X")
        anchor = data.yaml_anchor(any=True)
        return self.insert_underscore("0x", s, data._underscore, anchor=anchor)

    def represent_float(self, data: float) -> ScalarNode:

        if data != data or (data == 0.0 and data == 1.0):
            value = ".nan"
        elif data == float('inf'):
            value = ".inf"
        elif data == -float('inf'):
            value = "-.inf"
        else:
            value = repr(data).lower()
            if getattr(self.serializer, "use_version", None) == (1, 1):
                if "." not in value and "e" in value:
                    # Note that in some cases `repr(data)` represents a float number
                    # without the decimal parts.  For instance:
                    #   >>> repr(1e17)
                    #   '1e17'
                    # Unfortunately, this is not a valid float representation according
                    # to the definition of the `!!float` tag in YAML 1.1.  We fix
                    # this by adding '.0' before the 'e' symbol.
                    value = value.replace("e", ".0e", 1)
        return self.represent_scalar("tag:yaml.org,2002:float", value)

    def represent_scalar_float(self, data: ScalarFloat) -> ScalarNode:

        """this is way more complicated"""
        value = None
        anchor = data.yaml_anchor(any=True)
        if data != data or (data == 0.0 and data == 1.0):
            value = ".nan"
        elif data == float('inf'):
            value = ".inf"
        elif data == -float('inf'):
            value = "-.inf"
        if value:
            return self.represent_scalar(
                "tag:yaml.org,2002:float", value, anchor=anchor
            )
        if data._exp is None and data._prec > 0 and data._prec == data._width - 1:
            # no exponent, but trailing dot
            value = "{}{:d}.".format(
                data._m_sign if data._m_sign else "", abs(int(data))
            )
        elif data._exp is None:
            # no exponent, "normal" dot
            prec = data._prec
            ms = data._m_sign if data._m_sign else ""
            # -1 for the dot
            value = "{}{:0{}.{}f}".format(
                ms, abs(data), data._width - len(ms), data._width - prec - 1
            )
            if prec == 0 or (prec == 1 and ms != ""):
                value = value.replace("0.", ".")
            while len(value) < data._width:
                value += "0"
        else:
            # exponent
            m, es = "{:{}.{}e}".format(
                # data, data._width, data._width - data._prec + (1 if data._m_sign else 0)
                data,
                data._width,
                data._width + (1 if data._m_sign else 0),
            ).split("e")
            w = data._width if data._prec > 0 else (data._width + 1)
            if data < 0:
                w += 1
            m = m[:w]
            e = int(es)
            m1, m2 = m.split(".")  # always second?
            while len(m1) + len(m2) < data._width - (1 if data._prec >= 0 else 0):
                m2 += "0"
            if data._m_sign and data > 0:
                m1 = "+" + m1
            esgn = "+" if data._e_sign else ""
            if data._prec < 0:  # mantissa without dot
                if m2 != "0":
                    e -= len(m2)
                else:
                    m2 = ""
                while (len(m1) + len(m2) - (1 if data._m_sign else 0)) < data._width:
                    m2 += "0"
                    e -= 1
                value = m1 + m2 + data._exp + "{:{}0{}d}".format(e, esgn, data._e_width)
            elif data._prec == 0:  # mantissa with trailing dot
                e -= len(m2)
                value = (
                    m1
                    + m2
                    + "."
                    + data._exp
                    + "{:{}0{}d}".format(e, esgn, data._e_width)
                )
            else:
                if data._m_lead0 > 0:
                    m2 = "0" * (data._m_lead0 - 1) + m1 + m2
                    m1 = "0"
                    m2 = m2[: -data._m_lead0]  # these should be zeros
                    e += data._m_lead0
                while len(m1) < data._prec:
                    m1 += m2[0]
                    m2 = m2[1:]
                    e -= 1
                value = (
                    m1
                    + "."
                    + m2
                    + data._exp
                    + "{:{}0{}d}".format(e, esgn, data._e_width)
                )

        if value is None:
            value = repr(data).lower()
        return self.represent_scalar("tag:yaml.org,2002:float", value, anchor=anchor)

    def represent_list(self, data: CommentedSeq) -> SequenceNode:

        try:
            t = data.tag.value
        except AttributeError:
            t = None
        if t:
            if t.startswith("!!"):
                tag = "tag:yaml.org,2002:" + t[2:]
            else:
                tag = t
        else:
            tag = "tag:yaml.org,2002:seq"
        return self.represent_sequence(tag, data)

    def represent_dict(self, data: CommentedMap) -> MappingNode:

        """write out tag if saved on loading"""
        try:
            t = data.tag.value
        except AttributeError:
            t = None
        if t:
            if t.startswith("!!"):
                tag = "tag:yaml.org,2002:" + t[2:]
            else:
                tag = t
        else:
            tag = "tag:yaml.org,2002:map"
        return self.represent_mapping(tag, data)

    def represent_ordereddict(self, data: Union[OrderedDict, CommentedOrderedMap]) -> SequenceNode:

        return self.represent_omap("tag:yaml.org,2002:omap", data)

    def represent_set(self, setting: CommentedSet) -> MappingNode:

        flow_style = False
        tag = "tag:yaml.org,2002:set"
        # return self.represent_mapping(tag, value)
        value = []
        flow_style = setting.fa.flow_style(flow_style)
        try:
            anchor = setting.yaml_anchor()
        except AttributeError:
            anchor = None
        node = MappingNode(tag, value, flow_style=flow_style, anchor=anchor)
        if self.alias_key is not None:
            self.represented_objects[self.alias_key] = node
        best_style = True
        # no sorting! !!
        try:
            comment = getattr(setting, comment_attrib)
            if node.comment is None:
                node.comment = comment.comment
            else:
                # as we are potentially going to extend this, make a new list
                node.comment = comment.comment[:]
            if node.comment and node.comment[1]:
                for ct in node.comment[1]:
                    ct.reset()
            item_comments = comment.items
            for v in item_comments.values():
                if v and v[1]:
                    for ct in v[1]:
                        ct.reset()
            try:
                node.comment.append(comment.end)
            except AttributeError:
                pass
        except AttributeError:
            item_comments = {}
        for item_key in setting.odict:
            node_key = self.represent_key(item_key)
            node_value = self.represent_data(None)
            item_comment = item_comments.get(item_key)
            if item_comment:
                assert getattr(node_key, "comment", None) is None
                node_key.comment = item_comment[:2]
            node_key.style = node_value.style = "?"
            if not (isinstance(node_key, ScalarNode) and not node_key.style):
                best_style = False
            if not (isinstance(node_value, ScalarNode) and not node_value.style):
                best_style = False
            value.append((node_key, node_value))
        best_style = best_style
        return node

    def represent_date(self, data:     datetime.date) -> ScalarNode:

        value = data.isoformat()
        return self.represent_scalar("tag:yaml.org,2002:timestamp", value)

    def represent_datetime(self, data):

        inter = "T" if data._yaml["t"] else " "
        _yaml = data._yaml
        if _yaml["delta"]:
            data += _yaml["delta"]
            value = data.isoformat(inter)
        else:
            value = data.isoformat(inter)
        if _yaml["tz"]:
            value += _yaml["tz"]
        return self.represent_scalar("tag:yaml.org,2002:timestamp", value)

    def represent_yaml_object(self, tag, data, cls, flow_style=None):

        if hasattr(data, "__getstate__"):
            state = data.__getstate__()
        else:
            state = data.__dict__.copy()
        anchor = state.pop(Anchor.attrib, None)
        res = self.represent_mapping(tag, state, flow_style=flow_style)
        if anchor is not None:
            res.anchor = anchor
        return res

    def represent_undefined(self, data):

        raise RepresenterError(_F("cannot represent an object: {data!s}", data=data))

    def ignore_aliases(self, data: Any) -> bool:

        try:
            if data.anchor is not None and data.anchor.value is not None:
                return False
        except AttributeError:
            pass
        # https://docs.python.org/3/reference/expressions.html#parenthesized-forms :
        # "i.e. two occurrences of the empty tuple may or may not yield the same object"
        # so "data is ()" should not be used
        if data is None or (isinstance(data, tuple) and data == ()):
            return True
        if isinstance(data, (bytes, str, bool, int, float)):
            return True
        return False

    def insert_underscore(self, prefix: str, s: str, underscore: Optional[List[Union[int, bool]]], anchor: Optional[Anchor]=None) -> ScalarNode:

        if underscore is None:
            return self.represent_scalar(
                "tag:yaml.org,2002:int", prefix + s, anchor=anchor
            )
        if underscore[0]:
            sl = list(s)
            pos = len(s) - underscore[0]
            while pos > 0:
                sl.insert(pos, "_")
                pos -= underscore[0]
            s = "".join(sl)
        if underscore[1]:
            s = "_" + s
        if underscore[2]:
            s += "_"
        return self.represent_scalar("tag:yaml.org,2002:int", prefix + s, anchor=anchor)

    def merge_comments(self, node: Union[MappingNode, SequenceNode, ScalarNode], comments: None | List[None] | List[CommentToken | List[CommentToken]]) -> Union[MappingNode, SequenceNode, ScalarNode]:

        if comments is None:
            assert hasattr(node, "comment")
            return node
        if getattr(node, "comment", None) is not None:
            for idx, val in enumerate(comments):
                if idx >= len(node.comment):
                    continue
                nc = node.comment[idx]
                if nc is not None:
                    assert val is None or val == nc
                    comments[idx] = nc
        node.comment = comments
        return node