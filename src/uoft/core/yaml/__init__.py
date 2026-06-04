# coding: utf-8
from __future__ import annotations

from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from typing import Dict, Any  # NOQA

# This module tree  originally forked from ruamel.yaml (https://sourceforge.net/p/ruamel-yaml/code/ci/0.17.21/tree/) by Anton van der Neut

from .main import *  # NOQA
from .comments import CommentedMap, CommentedSeq, CommentToken


def loads(doc: str) -> dict:
    y = YAML()
    y.indent(mapping=2, sequence=4, offset=2)
    return y.load(doc)


def dumps(data) -> str:
    y = YAML()
    y.indent(mapping=2, sequence=4, offset=2)
    stream = StringIO()
    y.dump(data, stream)
    return stream.getvalue()


def from_yaml(doc: str) -> dict:
    return loads(doc)


def to_yaml(data) -> str:
    return dumps(data)


def get_comment(
    obj: CommentedSeq | CommentedMap, key: str | int | None = None
) -> str | None:  # noqa
    """
    Take a yaml object, and fetch comments from it. if a key is provided,
    fetch the comment associated with that key
    (str for mappings, int for sequences).
    if no key is provided, fetch the comment associated with the object itself
    if no comment can be found, return None
    """

    if not isinstance(obj, (CommentedMap, CommentedSeq)):
        return None
    if key is None:
        comment_list = obj.ca.comment
        # here comment_list can either be None or a list
        comment_list = comment_list if comment_list else []
    else:
        comment_list = obj.ca.items.get(key, [None])
        # the values of the ca.items dict are always lists of 4 elements,
        # one of which is the comment token, the rest are None.
        # which of the 4 elements is the
        # CommentToken changes depending on... something?
        # so we'll jsut filter the list looking for the first comment token
    comment_list = [token for token in comment_list if token]
    comment_list = cast(list[CommentToken] | None, comment_list)
    if comment_list:
        return comment_list[0].value.partition("#")[2].strip()
    # else:
    return None
