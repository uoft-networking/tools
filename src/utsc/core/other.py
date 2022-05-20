"""
This module stores a random assortment of functions and utilities which require 
additinal dependencies not included in utsc.core by default.
"""

import re
import sys
from subprocess import run, PIPE
from pathlib import Path
from types import ModuleType
import inspect
from urllib.parse import quote
from typing import (
    Iterator,
    Optional,
    Sequence,
    Union,
    Any,
    TYPE_CHECKING,
)

from .yaml import dumps

if TYPE_CHECKING:
    from . import Util
    from .yaml import CommentedMap
    from pydantic import BaseModel

KeyPath = str
Val = str
Comment = Optional[str]
YamlValue = tuple[KeyPath, Val, Comment]


def re_partition(regex: re.Pattern, s: str):
    match = regex.search(s)
    if match:
        return s[: match.start()], s[slice(*match.span())], s[match.end() :]
    # else:
    return (s, "", "")


def re_rpartition(regex: re.Pattern, s: str):
    # find the last match, or None if not found
    match = None
    for match in regex.finditer(s):
        pass
    if match:
        return s[: match.start()], s[slice(*match.span())], s[match.end() :]
    # else:
    return ("", "", s)


def flatten_yaml(s: Union["CommentedMap", str], sep) -> Iterator[YamlValue]:
    """
    generator, iterates over a yaml document, yielding 3-tuples for each value.
    each tuple consists of (keypath, val, comment or None)
    keys in the key path are separated by `sep`
    if `s` is a str, it will be parsed as a yaml document
    """
    # unfinished
    raise NotImplementedError


def unflatten_yaml(data: Sequence[YamlValue]):
    """
    Takes a sequence of 3-tuples representing a yaml document,
    and constructs a new yaml document from them
    """
    # unfinished
    raise NotImplementedError


def add_comments_to_yaml_doc(doc: str, model: "BaseModel", indent=0):
    from pydantic.fields import ModelField  # noqa
    from pydantic import BaseModel  # noqa

    for field in model.fields.values():  # type: ignore
        field: ModelField
        desc = field.field_info.description
        if desc:
            # we need to split the doc into 3 parts: the line containing the
            # alias this description belongs to, all preceeding lines, and all
            # following lines. To do this, we're going to regex partition the
            # document
            pattern = re.compile(fr"^ {{{indent}}}{field.alias}:.*$", re.MULTILINE)
            pre, match, rest = re_partition(pattern, doc)
            if len(desc) > 30:
                indent_spc = indent * " "

                # comment before line, preceeded by blank line
                comment = f"\n{indent_spc}# {desc}\n"
                doc = "".join([pre, comment, match, rest])
            else:
                comment = f"  # {desc}"  # comment at end of line
                doc = "".join([pre, match, comment, rest])
        if issubclass(field.type_, BaseModel):
            submodel = model.__getattribute__(field.name)
            doc = add_comments_to_yaml_doc(doc, submodel, indent + 2)
    return doc


class Prompt:
    def __init__(self, util: "Util"):
        from prompt_toolkit import prompt, PromptSession  # noqa
        from prompt_toolkit.history import FileHistory  # noqa
        from prompt_toolkit.auto_suggest import AutoSuggestFromHistory  # noqa
        from prompt_toolkit.formatted_text import HTML  # noqa
        from prompt_toolkit.completion import WordCompleter, PathCompleter  # noqa
        from prompt_toolkit.validation import Validator, ValidationError  # noqa
        from prompt_toolkit.key_binding import KeyBindings  # noqa
        from prompt_toolkit.output.defaults import create_output  # noqa

        self.util = util
        self.prompt = prompt
        self.PromptSession = PromptSession
        self.FileHistory = FileHistory
        self.AutoSuggestFromHistory = AutoSuggestFromHistory
        self.HTML = HTML
        self.WordCompleter = WordCompleter
        self.PathCompleter = PathCompleter
        self.Validator = Validator
        self.ValidationError = ValidationError
        self.KeyBindings = KeyBindings
        self.output = create_output(stdout=sys.stderr)

    def string(
        self,
        var: str,
        description: str | None,
        default_value: str | None = None,
        **kwargs,
    ) -> str:

        message = self.HTML(f"<style fg='#ffffff' bg='#888888'>{var}</style>: ")
        history = self.FileHistory(str(self.util.history_cache / quote(var)))
        opts: dict[str, Any] = dict(
            message=message,
            auto_suggest=self.AutoSuggestFromHistory(),
            mouse_support=True,
            bottom_toolbar="",
        )
        if default_value:
            opts["default"] = default_value
        if description:

            opts["bottom_toolbar"] = self.HTML(f"<b>{description}</b>")
        opts.update(kwargs)
        return self.PromptSession(history=history, output=self.output).prompt(**opts)

    def select(
        self,
        var: str,
        choices: list[str],
        description: str | None,
        default_value: str | None = None,
        **kwargs,
    ) -> str:

        validator = self.Validator.from_callable(
            lambda x: x in choices,
            error_message=f"Choice must be one of {', '.join(choices)}",
        )

        opts = dict(
            completer=self.WordCompleter(choices),
            complete_while_typing=True,
            rprompt=self.HTML(f"Valid options are: <b>{', '.join(choices)}</b>"),
            validator=validator,
        )
        opts.update(kwargs)
        return self.string(var, description, default_value, **opts)

    def path(  # pylint: disable=too-many-arguments
        self,
        var: str,
        description: str | None,
        default_value: str | None = None,
        only_directories=False,
        completer_opts: dict | None = None,
        **kwargs,
    ) -> Path:
        completer_opts = completer_opts or {}
        opts = dict(
            completer=self.PathCompleter(
                only_directories=only_directories, **completer_opts
            ),
            complete_while_typing=True,
        )
        opts.update(kwargs)
        return Path(self.string(var, description, default_value, **opts))

    def bool_(
        self,
        var: str,
        description: str | None,
        default_value: bool | None = None,
        **kwargs,
    ) -> bool:
        if default_value is True:
            default = "yes"
        elif default_value is False:
            default = "no"
        else:
            default = None

        choices = ["yes", "no"]
        val = self.select(var, choices, description, default, **kwargs)
        return val.lower() == "yes"

    def list_(self, var: str, description: str | None, **kwargs) -> list[str]:

        kb = self.KeyBindings()

        @kb.add("c-d")
        def _(event):
            event.app.exit(result=event.app.current_buffer.text)

        opts = dict(
            multiline=True,
            rprompt=self.HTML(
                "Press <b>Enter</b> to add a new line, <b>Alt-Enter</b> or <b>Ctrl+D</b> to finish and submit list."
            ),
            key_bindings=kb,
        )
        opts.update(kwargs)
        val = self.string(var, description, **opts)
        return val.strip().split("\n")

    def dict_(self, var: str, description: str | None, **kwargs) -> dict[str, str]:

        kb = self.KeyBindings()

        Validator = self.Validator
        ValidationError = self.ValidationError

        class DictValidator(Validator):
            def validate(self, document) -> None:
                for line in document.text.splitlines():
                    if ": " not in line:
                        raise ValidationError(
                            message="Each line must have a key and a value, separated by ': '"
                        )

        @kb.add("c-d")
        def _(event):
            event.app.exit(result=event.app.current_buffer.text)

        opts = dict(
            multiline=True,
            rprompt=self.HTML(
                "Press <b>Enter</b> to add a new line, <b>Alt-Enter</b> or <b>Ctrl+D</b> to finish and submit mapping."
            ),
            key_bindings=kb,
            validator=DictValidator(),
        )
        opts.update(kwargs)
        val = self.string(var, description, **opts)
        lines = val.strip().split("\n")
        pairs = [line.partition(": ") for line in lines]
        return {k: v for k, _, v in pairs}


def model_to_yaml(model: "BaseModel"):

    doc = dumps(model.dict(by_alias=True))
    # Now to add in the comments.
    doc = add_comments_to_yaml_doc(doc, model)
    return doc


def bump_version():
    """
    bump a project's version number.
    bumps the __version__ var in the project's __init__.py
    bumps the version in pyproject.toml
    tags the current git commit with that version number
    """
    import argparse  # noqa
    from ._vendor import tomlkit  # noqa
    import semver  # noqa

    semver_bump_types = ["major", "minor", "patch", "prerelease", "build"]
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "bump_type", choices=semver_bump_types, default="patch", nargs="?"
    )
    parser.add_argument(
        "--no-sign", action="store_true", help="don't force signed commits"
    )
    parser.add_argument(
        "--ignore-status",
        action="store_true",
        help="ignore output of git status, proceed with unclean directory tree",
    )
    args = parser.parse_args()
    if not args.ignore_status:
        git_status = run(["git", "status"], stdout=PIPE, check=True).stdout.decode()
        if "nothing to commit, working tree clean" not in git_status:
            print(
                "git working tree not clean. aborting. run `git status` and commit"
                " or ignore all outstanding files, then try again."
            )
            sys.exit(1)
    pyproject = tomlkit.parse(Path("pyproject.toml").read_text(encoding="utf-8"))
    package_name = pyproject["tool"]["poetry"]["name"]  # type: ignore
    old_version = pyproject["tool"]["poetry"]["version"]  # type: ignore
    version = semver.VersionInfo.parse(old_version)
    # for every bump_type in the list above, there is a bump_{type} method
    # on the VersionInfo object. here we look up the method and call it
    # ex if bump_type is 'patch', this will call version.bump_patch()
    version = getattr(version, f"bump_{args.bump_type}")()
    new_version = str(version)
    pyproject["tool"]["poetry"]["version"] = new_version  # type: ignore
    init_file = Path(f"{package_name}/__init__.py")
    init_text = init_file.read_text(encoding="utf-8")
    ver_strings_in_init_text = list(
        filter(lambda l: "__version__ =" in l, init_text.splitlines())
    )
    if ver_strings_in_init_text:
        old_ver_string = ver_strings_in_init_text[0]
        init_text = init_text.replace(old_ver_string, f"__version__ = '{new_version}'")

    # no turning back now!
    Path("pyproject.toml").write_text(tomlkit.dumps(pyproject), encoding="utf-8")
    init_file.write_text(init_text, encoding="utf-8")
    run(["git", "add", "."], check=True)
    run(
        ["git", "commit", "-m", f"bump version from {old_version} to {new_version}"],
        check=True,
    )
    sign = "" if args.no_sign else "-s"
    run(
        ["git", "tag", sign, "-a", new_version, "-m", f"version {new_version}"],
        check=True,
    )
    print("done")


def clear_caches(module: ModuleType):
    """
    clear all caches in a given module

    clear the caches of all cached functions and all cached classmethods
    and staticmethods of all classes in a given module
    """

    def get_cachables():
        # functions
        for _, function_ in inspect.getmembers(module, inspect.isfunction):
            yield function_

        for _, class_ in inspect.getmembers(module, inspect.isclass):
            # static methods
            for _, static_method in inspect.getmembers(class_, inspect.isfunction):
                yield static_method

            # class methods
            for _, class_method in inspect.getmembers(class_, inspect.ismethod):
                yield class_method

    for cacheable in get_cachables():
        if hasattr(cacheable, "cache"):
            cacheable.cache = {}
