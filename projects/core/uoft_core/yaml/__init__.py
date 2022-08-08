# coding: utf-8

from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from typing import Dict, Any  # NOQA

_package_data = dict(
    full_package_name="ruamel.yaml",
    version_info=(0, 17, 21),
    __version__="0.17.21",
    version_timestamp="2022-02-12 09:49:22",
    author="Anthon van der Neut",
    author_email="a.van.der.neut@ruamel.eu",
    description="ruamel.yaml is a YAML parser/emitter that supports roundtrip preservation of comments, seq/map flow style, and map key order",  # NOQA
    entry_points=None,
    since=2014,
    extras_require={
        ':platform_python_implementation=="CPython" and python_version<"3.11"': [
            "ruamel.yaml.clib>=0.2.6"
        ],  # NOQA
        "jinja2": ["ruamel.yaml.jinja2>=0.2"],
        "docs": ["ryd"],
    },
    classifiers=[
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: Implementation :: CPython",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Text Processing :: Markup",
        "Typing :: Typed",
    ],
    keywords="yaml 1.2 parser round-trip preserve quotes order config",
    read_the_docs="yaml",
    supported=[(3, 5)],  # minimum
    tox=dict(
        env="*f",  # f for 3.5
        fl8excl="_test/lib",
    ),
    # universal=True,
    python_requires=">=3",
    rtfd="yaml",
)  # type: Dict[Any, Any]


version_info = _package_data["version_info"]
__version__ = _package_data["__version__"]

try:
    from .cyaml import *  # NOQA

    __with_libyaml__ = True
except (ImportError, ValueError):  # for Jython
    __with_libyaml__ = False

from .main import *  # NOQA


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