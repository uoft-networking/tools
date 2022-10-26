# coding: utf-8
from __future__ import annotations

"""
stuff to deal with comments and formatting on dict/list/ordereddict/set
these are not really related, formatting could be factored out as
a separate base
"""

import sys
import copy

from .compat import ordereddict
from .compat import MutableSliceableSequence, _F, nprintf  # NOQA
from .scalarstring import ScalarString
from .anchor import Anchor

from collections.abc import MutableSet, Sized, Set, Mapping

from typing import Callable, Tuple, TYPE_CHECKING
from uoft_core.yaml.anchor import Anchor
from uoft_core.yaml.tokens import CommentToken

if TYPE_CHECKING:
    from typing import Any, Dict, Optional, List, Union, Optional, Iterator  # NOQA

# fmt: off
__all__ = ['CommentedSeq', 'CommentedKeySeq',
           'CommentedMap', 'CommentedOrderedMap',
           'CommentedSet', 'comment_attrib', 'merge_attrib',
           'C_POST', 'C_PRE', 'C_SPLIT_ON_FIRST_BLANK', 'C_BLANK_LINE_PRESERVE_SPACE',
           ]
# fmt: on

# splitting of comments by the scanner
# an EOLC (End-Of-Line Comment) is preceded by some token
# an FLC (Full Line Comment) is a comment not preceded by a token, i.e. # is
#   the first non-blank on line
# a BL is a blank line i.e. empty or spaces/tabs only
# bits 0 and 1 are combined, you can choose only one
C_POST = 0b00
C_PRE = 0b01
C_SPLIT_ON_FIRST_BLANK = (
    0b10  # as C_POST, but if blank line then C_PRE all lines before
)
# first blank goes to POST even if no following real FLC
# (first blank -> first of post)
# 0b11 -> reserved for future use
C_BLANK_LINE_PRESERVE_SPACE = 0b100
# C_EOL_PRESERVE_SPACE2 = 0b1000


class IDX:
    # temporary auto increment, so rearranging is easier
    def __init__(self):

        self._idx = 0

    def __call__(self):

        x = self._idx
        self._idx += 1
        return x

    def __str__(self):

        return str(self._idx)


cidx = IDX()

# more or less in order of subjective expected likelyhood
# the _POST and _PRE ones are lists themselves
C_VALUE_EOL = C_ELEM_EOL = cidx()
C_KEY_EOL = cidx()
C_KEY_PRE = C_ELEM_PRE = cidx()  # not this is not value
C_VALUE_POST = C_ELEM_POST = cidx()  # not this is not value
C_VALUE_PRE = cidx()
C_KEY_POST = cidx()
C_TAG_EOL = cidx()
C_TAG_POST = cidx()
C_TAG_PRE = cidx()
C_ANCHOR_EOL = cidx()
C_ANCHOR_POST = cidx()
C_ANCHOR_PRE = cidx()


comment_attrib = "_yaml_comment"
format_attrib = "_yaml_format"
line_col_attrib = "_yaml_line_col"
merge_attrib = "_yaml_merge"
tag_attrib = "_yaml_tag"


class Comment:
    # using sys.getsize tested the Comment objects, __slots__ makes them bigger
    # and adding self.end did not matter
    __slots__ = "comment", "_items", "_post", "_pre"
    attrib = comment_attrib

    def __init__(self, old: bool=True) -> None:

        self._pre = None if old else []
        self.comment = None  # [post, [pre]]
        # map key (mapping/omap/dict) or index (sequence/list) to a  list of
        # dict: post_key, pre_key, post_value, pre_value
        # list: pre item, post item
        self._items = {}
        # self._start = [] # should not put these on first item
        self._post = []

    def __str__(self) -> str:

        if bool(self._post):
            end = ",\n  end=" + str(self._post)
        else:
            end = ""
        return "Comment(comment={0},\n  items={1}{2})".format(
            self.comment, self._items, end
        )

    def _old__repr__(self):

        if bool(self._post):
            end = ",\n  end=" + str(self._post)
        else:
            end = ""
        try:
            ln = max([len(str(k)) for k in self._items]) + 1
        except ValueError:
            ln = ""
        it = "    ".join(
            ["{:{}} {}\n".format(str(k) + ":", ln, v) for k, v in self._items.items()]
        )
        if it:
            it = "\n    " + it + "  "
        return "Comment(\n  start={},\n  items={{{}}}{})".format(self.comment, it, end)

    def __repr__(self):

        if self._pre is None:
            return self._old__repr__()
        if bool(self._post):
            end = ",\n  end=" + repr(self._post)
        else:
            end = ""
        try:
            ln = max([len(str(k)) for k in self._items]) + 1
        except ValueError:
            ln = ""
        it = "    ".join(
            ["{:{}} {}\n".format(str(k) + ":", ln, v) for k, v in self._items.items()]
        )
        if it:
            it = "\n    " + it + "  "
        return "Comment(\n  pre={},\n  items={{{}}}{})".format(self.pre, it, end)

    @property
    def items(self) -> Any:

        return self._items

    @property
    def end(self):

        return self._post

    @end.setter
    def end(self, value):

        self._post = value

    @property
    def pre(self):

        return self._pre

    @pre.setter
    def pre(self, value):

        self._pre = value

    def get(self, item, pos):

        x = self._items.get(item)
        if x is None or len(x) < pos:
            return None
        return x[pos]  # can be None

    def set(self, item, pos, value):

        x = self._items.get(item)
        if x is None:
            self._items[item] = x = [None] * (pos + 1)
        else:
            while len(x) <= pos:
                x.append(None)
        assert x[pos] is None
        x[pos] = value

    def __contains__(self, x):

        # test if a substring is in any of the attached comments
        if self.comment:
            if self.comment[0] and x in self.comment[0].value:
                return True
            if self.comment[1]:
                for c in self.comment[1]:
                    if x in c.value:
                        return True
        for value in self.items.values():
            if not value:
                continue
            for c in value:
                if c and x in c.value:
                    return True
        if self.end:
            for c in self.end:
                if x in c.value:
                    return True
        return False


# to distinguish key from None
def NoComment():

    pass


class Format:
    __slots__ = ("_flow_style",)
    attrib = format_attrib

    def __init__(self) -> None:

        self._flow_style = None

    def set_flow_style(self) -> None:

        self._flow_style = True

    def set_block_style(self) -> None:

        self._flow_style = False

    def flow_style(self, default: Optional[bool]=None) -> Optional[bool]:

        """if default (the flow_style) is None, the flow style tacked on to
        the object explicitly will be taken. If that is None as well the
        default flow style rules the format down the line, or the type
        of the constituent values (simple -> flow, map/list -> block)"""
        if self._flow_style is None:
            return default
        return self._flow_style


class LineCol:
    """
    line and column information wrt document, values start at zero (0)
    """

    attrib = line_col_attrib

    def __init__(self) -> None:

        self.line = None
        self.col = None
        self.data = None

    def add_kv_line_col(self, key: Union[CommentedKeySeq, str], data: List[int]) -> None:

        if self.data is None:
            self.data = {}
        self.data[key] = data

    def key(self, k: str) -> Tuple[int, int]:

        return self._kv(k, 0, 1)

    def value(self, k: str) -> Tuple[int, int]:

        return self._kv(k, 2, 3)

    def _kv(self, k: str, x0: int, x1: int) -> Tuple[int, int]:

        if self.data is None:
            return None
        data = self.data[k]
        return data[x0], data[x1]

    def item(self, idx: int) -> Tuple[int, int]:

        if self.data is None:
            return None
        return self.data[idx][0], self.data[idx][1]

    def add_idx_line_col(self, key: int, data: List[int]) -> None:

        if self.data is None:
            self.data = {}
        self.data[key] = data

    def __repr__(self):

        return _F("LineCol({line}, {col})", line=self.line, col=self.col)


class Tag:
    """store tag information for roundtripping"""

    __slots__ = ("value",)
    attrib = tag_attrib

    def __init__(self) -> None:

        self.value = None

    def __repr__(self):

        return "{0.__class__.__name__}({0.value!r})".format(self)


class CommentedBase:
    @property
    def ca(self) -> Comment:

        if not hasattr(self, Comment.attrib):
            setattr(self, Comment.attrib, Comment())
        return getattr(self, Comment.attrib)

    def yaml_end_comment_extend(self, comment: None, clear: bool=False) -> None:

        if comment is None:
            return
        if clear or self.ca.end is None:
            self.ca.end = []
        self.ca.end.extend(comment)

    def yaml_key_comment_extend(self, key: Union[int, str], comment: List[Optional[Union[CommentToken, List[CommentToken]]]], clear: bool=False) -> None:

        r = self.ca._items.setdefault(key, [None, None, None, None])
        if clear or r[1] is None:
            if comment[1] is not None:
                assert isinstance(comment[1], list)
            r[1] = comment[1]
        else:
            r[1].extend(comment[0])
        r[0] = comment[0]

    def yaml_value_comment_extend(self, key: str, comment: List[Optional[Union[CommentToken, List[CommentToken], List[str]]]], clear: bool=False) -> None:

        r = self.ca._items.setdefault(key, [None, None, None, None])
        if clear or r[3] is None:
            if comment[1] is not None:
                assert isinstance(comment[1], list)
            r[3] = comment[1]
        else:
            r[3].extend(comment[0])
        r[2] = comment[0]

    def yaml_set_start_comment(self, comment: str, indent: int=0) -> None:

        """overwrites any preceding comment lines on an object
        expects comment to be without `#` and possible have multiple lines
        """
        from .error import CommentMark
        from .tokens import CommentToken

        pre_comments = self._yaml_clear_pre_comment()
        if comment[-1] == "\n":
            comment = comment[:-1]  # strip final newline if there
        start_mark = CommentMark(indent)
        for com in comment.split("\n"):
            c = com.strip()
            if len(c) > 0 and c[0] != "#":
                com = "# " + com
            pre_comments.append(CommentToken(com + "\n", start_mark))

    def yaml_set_comment_before_after_key(
        self, key: str, before: Optional[str]=None, indent: int=0, after: Optional[str]=None, after_indent: Optional[int]=None
    ) -> None:

        """
        expects comment (before/after) to be without `#` and possible have multiple lines
        """
        from .error import CommentMark
        from .tokens import CommentToken

        def comment_token(s, mark):

            # handle empty lines as having no comment
            return CommentToken(("# " if s else "") + s + "\n", mark)

        if after_indent is None:
            after_indent = indent + 2
        if before and (len(before) > 1) and before[-1] == "\n":
            before = before[:-1]  # strip final newline if there
        if after and after[-1] == "\n":
            after = after[:-1]  # strip final newline if there
        start_mark = CommentMark(indent)
        c = self.ca.items.setdefault(key, [None, [], None, None])
        if before is not None:
            if c[1] is None:
                c[1] = []
            if before == "\n":
                c[1].append(comment_token("", start_mark))
            else:
                for com in before.split("\n"):
                    c[1].append(comment_token(com, start_mark))
        if after:
            start_mark = CommentMark(after_indent)
            if c[3] is None:
                c[3] = []
            for com in after.split("\n"):
                c[3].append(comment_token(com, start_mark))

    @property
    def fa(self) -> Format:

        """format attribute

        set_flow_style()/set_block_style()"""
        if not hasattr(self, Format.attrib):
            setattr(self, Format.attrib, Format())
        return getattr(self, Format.attrib)

    def yaml_add_eol_comment(self, comment: str, key: Union[int, str]=NoComment, column: Optional[int]=None) -> None:

        """
        there is a problem as eol comments should start with ' #'
        (but at the beginning of the line the space doesn't have to be before
        the #. The column index is for the # mark
        """
        from .tokens import CommentToken
        from .error import CommentMark

        if column is None:
            try:
                column = self._yaml_get_column(key)
            except AttributeError:
                column = 0
        if comment[0] != "#":
            comment = "# " + comment
        if column is None:
            if comment[0] == "#":
                comment = " " + comment
                column = 0
        start_mark = CommentMark(column)
        ct = [CommentToken(comment, start_mark), None]
        self._yaml_add_eol_comment(ct, key=key)

    @property
    def lc(self) -> LineCol:

        if not hasattr(self, LineCol.attrib):
            setattr(self, LineCol.attrib, LineCol())
        return getattr(self, LineCol.attrib)

    def _yaml_set_line_col(self, line: int, col: int) -> None:

        self.lc.line = line
        self.lc.col = col

    def _yaml_set_kv_line_col(self, key: Union[CommentedKeySeq, str], data: List[int]) -> None:

        self.lc.add_kv_line_col(key, data)

    def _yaml_set_idx_line_col(self, key: int, data: List[int]) -> None:

        self.lc.add_idx_line_col(key, data)

    @property
    def anchor(self) -> Anchor:

        if not hasattr(self, Anchor.attrib):
            setattr(self, Anchor.attrib, Anchor())
        return getattr(self, Anchor.attrib)

    def yaml_anchor(self) -> Optional[Anchor]:

        if not hasattr(self, Anchor.attrib):
            return None
        return self.anchor

    def yaml_set_anchor(self, value: str, always_dump: bool=False) -> None:

        self.anchor.value = value
        self.anchor.always_dump = always_dump

    @property
    def tag(self) -> Tag:

        if not hasattr(self, Tag.attrib):
            setattr(self, Tag.attrib, Tag())
        return getattr(self, Tag.attrib)

    def yaml_set_tag(self, value: str) -> None:

        self.tag.value = value

    def copy_attributes(self, t, memo=None):

        # fmt: off
        for a in [Comment.attrib, Format.attrib, LineCol.attrib, Anchor.attrib,
                  Tag.attrib, merge_attrib]:
            if hasattr(self, a):
                if memo is not None:
                    setattr(t, a, copy.deepcopy(getattr(self, a, memo)))
                else:
                    setattr(t, a, getattr(self, a))
        # fmt: on

    def _yaml_add_eol_comment(self, comment, key):

        raise NotImplementedError

    def _yaml_get_pre_comment(self):

        raise NotImplementedError

    def _yaml_get_column(self, key):

        raise NotImplementedError


class CommentedSeq(MutableSliceableSequence, list, CommentedBase):
    __slots__ = (Comment.attrib, "_lst")

    def __init__(self, *args, **kw) -> None:

        list.__init__(self, *args, **kw)

    def __getsingleitem__(self, idx: int) -> Any:

        return list.__getitem__(self, idx)

    def __setsingleitem__(self, idx: int, value: Any) -> None:

        # try to preserve the scalarstring type if setting an existing key to a new value
        if idx < len(self):
            if (
                isinstance(value, str)
                and not isinstance(value, ScalarString)
                and isinstance(self[idx], ScalarString)
            ):
                value = type(self[idx])(value)
        list.__setitem__(self, idx, value)

    def __delsingleitem__(self, idx: Optional[int]=None) -> None:

        list.__delitem__(self, idx)
        self.ca.items.pop(idx, None)  # might not be there -> default value
        for list_index in sorted(self.ca.items):
            if list_index < idx:
                continue
            self.ca.items[list_index - 1] = self.ca.items.pop(list_index)

    def __len__(self) -> int:

        return list.__len__(self)

    def insert(self, idx: int, val: str) -> None:

        """the comments after the insertion have to move forward"""
        list.insert(self, idx, val)
        for list_index in sorted(self.ca.items, reverse=True):
            if list_index < idx:
                break
            self.ca.items[list_index + 1] = self.ca.items.pop(list_index)

    def extend(self, val: List[Any]) -> None:

        list.extend(self, val)

    def __eq__(self, other):

        return list.__eq__(self, other)

    def _yaml_add_comment(self, comment: List[Optional[Union[CommentToken, List[CommentToken]]]], key: Union[Callable, int]=NoComment) -> None:

        if key is not NoComment:
            self.yaml_key_comment_extend(key, comment)
        else:
            self.ca.comment = comment

    def _yaml_add_eol_comment(self, comment: List[Optional[CommentToken]], key: int) -> None:

        self._yaml_add_comment(comment, key=key)

    def _yaml_get_columnX(self, key: int) -> int:

        return self.ca.items[key][0].start_mark.column

    def _yaml_get_column(self, key: int) -> int:

        column = None
        sel_idx = None
        pre, post = key - 1, key + 1
        if pre in self.ca.items:
            sel_idx = pre
        elif post in self.ca.items:
            sel_idx = post
        else:
            # self.ca.items is not ordered
            for row_idx, _k1 in enumerate(self):
                if row_idx >= key:
                    break
                if row_idx not in self.ca.items:
                    continue
                sel_idx = row_idx
        if sel_idx is not None:
            column = self._yaml_get_columnX(sel_idx)
        return column

    def _yaml_get_pre_comment(self):

        pre_comments = []
        if self.ca.comment is None:
            self.ca.comment = [None, pre_comments]
        else:
            pre_comments = self.ca.comment[1]
        return pre_comments

    def _yaml_clear_pre_comment(self) -> List[Any]:

        pre_comments = []
        if self.ca.comment is None:
            self.ca.comment = [None, pre_comments]
        else:
            self.ca.comment[1] = pre_comments
        return pre_comments

    def __deepcopy__(self, memo):

        res = self.__class__()
        memo[id(self)] = res
        for k in self:
            res.append(copy.deepcopy(k, memo))
            self.copy_attributes(res, memo=memo)
        return res

    def __add__(self, other):

        return list.__add__(self, other)

    def sort(self, key=None, reverse=False):

        if key is None:
            tmp_lst = sorted(zip(self, range(len(self))), reverse=reverse)
            list.__init__(self, [x[0] for x in tmp_lst])
        else:
            tmp_lst = sorted(
                zip(map(key, list.__iter__(self)), range(len(self))), reverse=reverse
            )
            list.__init__(self, [list.__getitem__(self, x[1]) for x in tmp_lst])
        itm = self.ca.items
        self.ca._items = {}
        for idx, x in enumerate(tmp_lst):
            old_index = x[1]
            if old_index in itm:
                self.ca.items[idx] = itm[old_index]

    def __repr__(self) -> str:

        return list.__repr__(self)


class CommentedKeySeq(tuple, CommentedBase):
    """This primarily exists to be able to roundtrip keys that are sequences"""

    def _yaml_add_comment(self, comment, key=NoComment):

        if key is not NoComment:
            self.yaml_key_comment_extend(key, comment)
        else:
            self.ca.comment = comment

    def _yaml_add_eol_comment(self, comment, key):

        self._yaml_add_comment(comment, key=key)

    def _yaml_get_columnX(self, key):

        return self.ca.items[key][0].start_mark.column

    def _yaml_get_column(self, key):

        column = None
        sel_idx = None
        pre, post = key - 1, key + 1
        if pre in self.ca.items:
            sel_idx = pre
        elif post in self.ca.items:
            sel_idx = post
        else:
            # self.ca.items is not ordered
            for row_idx, _k1 in enumerate(self):
                if row_idx >= key:
                    break
                if row_idx not in self.ca.items:
                    continue
                sel_idx = row_idx
        if sel_idx is not None:
            column = self._yaml_get_columnX(sel_idx)
        return column

    def _yaml_get_pre_comment(self):

        pre_comments = []
        if self.ca.comment is None:
            self.ca.comment = [None, pre_comments]
        else:
            pre_comments = self.ca.comment[1]
        return pre_comments

    def _yaml_clear_pre_comment(self):

        pre_comments = []
        if self.ca.comment is None:
            self.ca.comment = [None, pre_comments]
        else:
            self.ca.comment[1] = pre_comments
        return pre_comments


class CommentedMapView(Sized):
    __slots__ = ("_mapping",)

    def __init__(self, mapping: "CommentedMap") -> None:

        self._mapping = mapping

    def __len__(self) -> int:

        count = len(self._mapping)
        return count


class CommentedMapKeysView(CommentedMapView, Set):
    __slots__ = ()

    @classmethod
    def _from_iterable(self, it):

        return set(it)

    def __contains__(self, key):

        return key in self._mapping

    def __iter__(self) -> Iterator[str]:

        # for x in self._mapping._keys():
        for x in self._mapping:
            yield x


class CommentedMapItemsView(CommentedMapView, Set):
    __slots__ = ()

    @classmethod
    def _from_iterable(self, it):

        return set(it)

    def __contains__(self, item):

        key, value = item
        try:
            v = self._mapping[key]
        except KeyError:
            return False
        else:
            return v == value

    def __iter__(self) -> Iterator[Any]:

        for key in self._mapping._keys():
            yield (key, self._mapping[key])


class CommentedMapValuesView(CommentedMapView):
    __slots__ = ()

    def __contains__(self, value):

        for key in self._mapping:
            if value == self._mapping[key]:
                return True
        return False

    def __iter__(self):

        for key in self._mapping._keys():
            yield self._mapping[key]


class CommentedMap(ordereddict, CommentedBase):
    __slots__ = (Comment.attrib, "_ok", "_ref")

    def __init__(self, *args, **kw) -> None:

        self._ok = set()
        self._ref = []
        ordereddict.__init__(self, *args, **kw)

    def _yaml_add_comment(self, comment: List[Optional[Union[CommentToken, List[CommentToken], List[str]]]], key: Union[Callable, str]=NoComment, value: Union[Callable, str]=NoComment) -> None:

        """values is set to key to indicate a value attachment of comment"""
        if key is not NoComment:
            self.yaml_key_comment_extend(key, comment)
            return
        if value is not NoComment:
            self.yaml_value_comment_extend(value, comment)
        else:
            self.ca.comment = comment

    def _yaml_add_eol_comment(self, comment: List[Optional[CommentToken]], key: str) -> None:

        """add on the value line, with value specified by the key"""
        self._yaml_add_comment(comment, value=key)

    def _yaml_get_columnX(self, key: str) -> int:

        return self.ca.items[key][2].start_mark.column

    def _yaml_get_column(self, key: str) -> Optional[int]:

        column = None
        sel_idx = None
        pre, post, last = None, None, None
        for x in self:
            if pre is not None and x != key:
                post = x
                break
            if x == key:
                pre = last
            last = x
        if pre in self.ca.items:
            sel_idx = pre
        elif post in self.ca.items:
            sel_idx = post
        else:
            # self.ca.items is not ordered
            for k1 in self:
                if k1 >= key:
                    break
                if k1 not in self.ca.items:
                    continue
                sel_idx = k1
        if sel_idx is not None:
            column = self._yaml_get_columnX(sel_idx)
        return column

    def _yaml_get_pre_comment(self):

        pre_comments = []
        if self.ca.comment is None:
            self.ca.comment = [None, pre_comments]
        else:
            pre_comments = self.ca.comment[1]
        return pre_comments

    def _yaml_clear_pre_comment(self) -> List[Any]:

        pre_comments = []
        if self.ca.comment is None:
            self.ca.comment = [None, pre_comments]
        else:
            self.ca.comment[1] = pre_comments
        return pre_comments

    def update(self, *vals, **kw):

        try:
            ordereddict.update(self, *vals, **kw)
        except TypeError:
            # probably a dict that is used
            for x in vals[0]:
                self[x] = vals[0][x]
        if vals:
            try:
                self._ok.update(vals[0].keys())
            except AttributeError:
                # assume one argument that is a list/tuple of two element lists/tuples
                for x in vals[0]:
                    self._ok.add(x[0])
        if kw:
            self._ok.add(*kw.keys())

    def insert(self, pos: int, key: str, value: str, comment: Optional[str]=None) -> None:

        """insert key value into given position
        attach comment if provided
        """
        keys = list(self.keys()) + [key]
        ordereddict.insert(self, pos, key, value)
        for keytmp in keys:
            self._ok.add(keytmp)
        for referer in self._ref:
            for keytmp in keys:
                referer.update_key_value(keytmp)
        if comment is not None:
            self.yaml_add_eol_comment(comment, key=key)

    def mlget(self, key: List[Union[str, int]], default: None=None, list_ok: bool=False) -> int:

        """multi-level get that expects dicts within dicts"""
        if not isinstance(key, list):
            return self.get(key, default)
        # assume that the key is a list of recursively accessible dicts

        def get_one_level(key_list, level, d):

            if not list_ok:
                assert isinstance(d, dict)
            if level >= len(key_list):
                if level > len(key_list):
                    raise IndexError
                return d[key_list[level - 1]]
            return get_one_level(key_list, level + 1, d[key_list[level - 1]])

        try:
            return get_one_level(key, 1, self)
        except KeyError:
            return default
        except (TypeError, IndexError):
            if not list_ok:
                raise
            return default

    def __getitem__(self, key: Union[CommentedKeySeq, int, str]) -> Any:

        try:
            return ordereddict.__getitem__(self, key)
        except KeyError:
            for merged in getattr(self, merge_attrib, []):
                if key in merged[1]:
                    return merged[1][key]
            raise

    def __setitem__(self, key: Union[CommentedKeySeq, int, str], value: Any) -> None:

        # try to preserve the scalarstring type if setting an existing key to a new value
        if key in self:
            if (
                isinstance(value, str)
                and not isinstance(value, ScalarString)
                and isinstance(self[key], ScalarString)
            ):
                value = type(self[key])(value)
        ordereddict.__setitem__(self, key, value)
        self._ok.add(key)

    def _unmerged_contains(self, key):

        if key in self._ok:
            return True
        return None

    def __contains__(self, key: Union[CommentedKeySeq, int, str]) -> bool:

        return bool(ordereddict.__contains__(self, key))

    def get(self, key, default=None):

        try:
            return self.__getitem__(key)
        except:  # NOQA
            return default

    def __repr__(self) -> str:

        return ordereddict.__repr__(self).replace("CommentedMap", "ordereddict")

    def non_merged_items(self) -> Iterator[Tuple[str, str]]:

        for x in ordereddict.__iter__(self):
            if x in self._ok:
                yield x, ordereddict.__getitem__(self, x)

    def __delitem__(self, key: str) -> None:

        # for merged in getattr(self, merge_attrib, []):
        #     if key in merged[1]:
        #         value = merged[1][key]
        #         break
        # else:
        #     # not found in merged in stuff
        #     ordereddict.__delitem__(self, key)
        #    for referer in self._ref:
        #        referer.update=_key_value(key)
        #    return
        #
        # ordereddict.__setitem__(self, key, value)  # merge might have different value
        # self._ok.discard(key)
        self._ok.discard(key)
        ordereddict.__delitem__(self, key)
        for referer in self._ref:
            referer.update_key_value(key)

    def __iter__(self) -> Iterator[Union[int, str]]:

        for x in ordereddict.__iter__(self):
            yield x

    def _keys(self) -> Iterator[Union[CommentedKeySeq, int, str]]:

        for x in ordereddict.__iter__(self):
            yield x

    def __len__(self) -> int:

        return int(ordereddict.__len__(self))

    def __eq__(self, other: Union[Dict[str, str], CommentedMap]) -> bool:

        return bool(dict(self) == other)

    def keys(self) -> CommentedMapKeysView:

        return CommentedMapKeysView(self)

    def values(self):

        return CommentedMapValuesView(self)

    def _items(self):

        for x in ordereddict.__iter__(self):
            yield x, ordereddict.__getitem__(self, x)

    def items(self) -> CommentedMapItemsView:

        return CommentedMapItemsView(self)

    @property
    def merge(self) -> List[Any]:

        if not hasattr(self, merge_attrib):
            setattr(self, merge_attrib, [])
        return getattr(self, merge_attrib)

    def copy(self):

        x = type(self)()  # update doesn't work
        for k, v in self._items():
            x[k] = v
        self.copy_attributes(x)
        return x

    def add_referent(self, cm: "CommentedMap") -> None:

        if cm not in self._ref:
            self._ref.append(cm)

    def add_yaml_merge(self, value: List[Tuple[int, CommentedMap]]) -> None:

        for v in value:
            v[1].add_referent(self)
            for k, v in v[1].items():
                if ordereddict.__contains__(self, k):
                    continue
                ordereddict.__setitem__(self, k, v)
        self.merge.extend(value)

    def update_key_value(self, key):

        if key in self._ok:
            return
        for v in self.merge:
            if key in v[1]:
                ordereddict.__setitem__(self, key, v[1][key])
                return
        ordereddict.__delitem__(self, key)

    def __deepcopy__(self, memo):

        res = self.__class__()
        memo[id(self)] = res
        for k in self:
            res[k] = copy.deepcopy(self[k], memo)
        self.copy_attributes(res, memo=memo)
        return res


# based on brownie mappings
@classmethod
def raise_immutable(cls, *args, **kwargs):

    raise TypeError("{} objects are immutable".format(cls.__name__))


class CommentedKeyMap(CommentedBase, Mapping):
    __slots__ = Comment.attrib, "_od"
    """This primarily exists to be able to roundtrip keys that are mappings"""

    def __init__(self, *args, **kw):

        if hasattr(self, "_od"):
            raise_immutable(self)
        try:
            self._od = ordereddict(*args, **kw)
        except TypeError:
            raise

    __delitem__ = (
        __setitem__
    ) = clear = pop = popitem = setdefault = update = raise_immutable

    # need to implement __getitem__, __iter__ and __len__
    def __getitem__(self, index):

        return self._od[index]

    def __iter__(self):

        for x in self._od.__iter__():
            yield x

    def __len__(self):

        return len(self._od)

    def __hash__(self):

        return hash(tuple(self.items()))

    def __repr__(self):

        if not hasattr(self, merge_attrib):
            return self._od.__repr__()
        return "ordereddict(" + repr(list(self._od.items())) + ")"

    @classmethod
    def fromkeys(keys, v=None):

        return CommentedKeyMap(dict.fromkeys(keys, v))

    def _yaml_add_comment(self, comment, key=NoComment):

        if key is not NoComment:
            self.yaml_key_comment_extend(key, comment)
        else:
            self.ca.comment = comment

    def _yaml_add_eol_comment(self, comment, key):

        self._yaml_add_comment(comment, key=key)

    def _yaml_get_columnX(self, key):

        return self.ca.items[key][0].start_mark.column

    def _yaml_get_column(self, key):

        column = None
        sel_idx = None
        pre, post = key - 1, key + 1
        if pre in self.ca.items:
            sel_idx = pre
        elif post in self.ca.items:
            sel_idx = post
        else:
            # self.ca.items is not ordered
            for row_idx, _k1 in enumerate(self):
                if row_idx >= key:
                    break
                if row_idx not in self.ca.items:
                    continue
                sel_idx = row_idx
        if sel_idx is not None:
            column = self._yaml_get_columnX(sel_idx)
        return column

    def _yaml_get_pre_comment(self):

        pre_comments = []
        if self.ca.comment is None:
            self.ca.comment = [None, pre_comments]
        else:
            self.ca.comment[1] = pre_comments
        return pre_comments


class CommentedOrderedMap(CommentedMap):
    __slots__ = (Comment.attrib,)


class CommentedSet(MutableSet, CommentedBase):
    __slots__ = Comment.attrib, "odict"

    def __init__(self, values: Optional[List[str]]=None) -> None:

        self.odict = ordereddict()
        MutableSet.__init__(self)
        if values is not None:
            self |= values

    def _yaml_add_comment(self, comment: List[Optional[Union[CommentToken, List[CommentToken]]]], key: Union[Callable, str]=NoComment, value: Callable=NoComment) -> None:

        """values is set to key to indicate a value attachment of comment"""
        if key is not NoComment:
            self.yaml_key_comment_extend(key, comment)
            return
        if value is not NoComment:
            self.yaml_value_comment_extend(value, comment)
        else:
            self.ca.comment = comment

    def _yaml_add_eol_comment(self, comment, key):

        """add on the value line, with value specified by the key"""
        self._yaml_add_comment(comment, value=key)

    def add(self, value: str) -> None:

        """Add an element."""
        self.odict[value] = None

    def discard(self, value: str) -> None:

        """Remove an element.  Do not raise an exception if absent."""
        del self.odict[value]

    def __contains__(self, x: str) -> bool:

        return x in self.odict

    def __iter__(self) -> Iterator[str]:

        for x in self.odict:
            yield x

    def __len__(self) -> int:

        return len(self.odict)

    def __repr__(self):

        return "set({0!r})".format(self.odict.keys())


class TaggedScalar(CommentedBase):
    # the value and style attributes are set during roundtrip construction
    def __init__(self, value: None=None, style: None=None, tag: None=None) -> None:

        self.value = value
        self.style = style
        if tag is not None:
            self.yaml_set_tag(tag)

    def __str__(self):

        return self.value


def dump_comments(d, name="", sep=".", out=sys.stdout):

    """
    recursively dump comments, all but the toplevel preceded by the path
    in dotted form x.0.a
    """
    if isinstance(d, dict) and hasattr(d, "ca"):
        if name:
            out.write("{} {}\n".format(name, type(d)))
        out.write("{!r}\n".format(d.ca))
        for k in d:
            dump_comments(
                d[k], name=(name + sep + str(k)) if name else k, sep=sep, out=out
            )
    elif isinstance(d, list) and hasattr(d, "ca"):
        if name:
            out.write("{} {}\n".format(name, type(d)))
        out.write("{!r}\n".format(d.ca))
        for idx, k in enumerate(d):
            dump_comments(
                k, name=(name + sep + str(idx)) if name else str(idx), sep=sep, out=out
            )
