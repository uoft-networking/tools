from enum import Enum
from typing import Literal, Any, Sequence, get_args, get_origin
from pathlib import Path
import sys
from base64 import b64encode

from . import Util

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.completion import WordCompleter, PathCompleter
from prompt_toolkit.validation import Validator, ValidationError
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.document import Document
from prompt_toolkit.output.defaults import create_output
from pydantic import BaseModel
from pydantic.types import SecretStr, FilePath, DirectoryPath
from pydantic.error_wrappers import ErrorWrapper
from pydantic.fields import ModelField

output = create_output(stdout=sys.stderr)


def _unpack_type(tp: Any):
    name = get_origin(tp)
    args = get_args(tp)

    if name is None:
        # for base types like str, bool, int, get_origin returns None
        name = tp

    return name, args


def _hash(s: str) -> str:
    return b64encode(s.encode()).decode()


class Prompt:
    def __init__(self, util: Util):

        self.history_cache = util.history_cache
        if not self.history_cache.exists():
            self.history_cache.mkdir(parents=True)

    def get_string(
        self,
        var: str,
        description: str | None,
        default_value: str | None = None,
        is_password: bool = False,
        default_from_history: bool = False,
        **kwargs,
    ) -> str:

        message = HTML(f"<style fg='#ffffff' bg='#888888'>{var}</style>: ")
        opts: dict[str, Any] = dict(
            message=message,
            mouse_support=True,
            bottom_toolbar="",
        )
        if default_value:
            opts["default"] = default_value
        if description:
            opts["bottom_toolbar"] = HTML(f"<b>{description}</b>")

        if is_password:
            history = None
            opts["is_password"] = True
        else:
            history = FileHistory(f"{self.history_cache}/{_hash(var)}")
            opts["auto_suggest"] = AutoSuggestFromHistory()
            if default_from_history:
                try:
                    opts["default"] = next(history.load_history_strings()) # type: ignore
                except StopIteration:
                    pass

        opts.update(kwargs)
        return PromptSession(history=history, output=output).prompt(**opts)

    def get_from_choices(
        self,
        var: str,
        choices: Sequence[str],
        description: str | None,
        default_value: str | None = None,
        **kwargs,
    ) -> str:

        validator = Validator.from_callable(
            lambda x: x in choices,
            error_message=f"Choice must be one of {', '.join(choices)}",
        )

        opts = dict(
            completer=WordCompleter(list(choices)),
            complete_while_typing=True,
            rprompt=HTML(f"Valid options are: <b>{', '.join(choices)}</b>"),
            validator=validator,
        )
        opts.update(kwargs)
        return self.get_string(var, description, default_value, **opts)

    def get_path(  # pylint: disable=too-many-arguments
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
            completer=PathCompleter(
                only_directories=only_directories, **completer_opts
            ),
            complete_while_typing=True,
        )
        opts.update(kwargs)
        return Path(self.get_string(var, description, default_value, **opts))

    def get_bool(
        self,
        var: str,
        description: str | None,
        default_value: bool | None = None,
        **kwargs,
    ) -> bool:

        truths = "y Y yes Yes true True".split()
        falses = "n N no No false False".split()
        all_valid = truths + falses

        if default_value is True:
            default = "yes"
        elif default_value is False:
            default = "no"
        else:
            default = None

        class BoolValidator(Validator):
            def validate(self, document) -> None:
                if document.text.strip() not in all_valid:
                    raise ValidationError(message=f"Value must be one of: {all_valid}")

        val = self.get_from_choices(
            var,
            all_valid,
            description=description,
            default_value=default,
            validator=BoolValidator(),
            **kwargs,
        )

        return val.strip() in truths

    def get_int(
        self,
        var: str,
        description: str | None,
        default_value: int | None = None,
        **kwargs,
    ) -> int:
        class IntValidator(Validator):
            def validate(self, document) -> None:
                try:
                    int(document.text.strip())
                except Exception as exc:
                    raise ValidationError(
                        message=f"{document.text} is not a valid integer"
                    ) from exc

        val = self.get_string(
            var,
            description=description,
            default_value=str(default_value) if default_value else None,
            validator=IntValidator(),
            **kwargs,
        )
        return int(val.strip())

    def get_list(self, var: str, description: str | None, **kwargs) -> list[str]:

        kb = KeyBindings()

        @kb.add("c-d")
        def _(event):
            event.app.exit(result=event.app.current_buffer.text)

        opts = dict(
            multiline=True,
            rprompt=HTML(
                "Press <b>Enter</b> to add a new line, <b>Alt-Enter</b> or <b>Ctrl+D</b> to finish and submit list."
            ),
            key_bindings=kb,
        )
        opts.update(kwargs)
        val = self.get_string(var, description, **opts)
        return val.strip().split("\n")

    def get_dict(self, var: str, description: str | None, **kwargs) -> dict[str, str]:

        kb = KeyBindings()

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
            rprompt=HTML(
                "Press <b>Enter</b> to add a new line, <b>Alt-Enter</b> or <b>Ctrl+D</b> to finish and submit mapping."
            ),
            key_bindings=kb,
            validator=DictValidator(),
        )
        opts.update(kwargs)
        val = self.get_string(var, description, **opts)
        lines = val.strip().split("\n")
        pairs = [line.partition(": ") for line in lines]
        return {k: v for k, _, v in pairs}

    def from_model(self, model: type[BaseModel], prefix: str|None = None):
        res = {}
        for name, field in model.__fields__.items():
            if prefix:
                prompt_name = f"{prefix}.{name}"
            else:
                prompt_name = name
            res[name] = self.from_model_field(prompt_name, field)
        return res

    def from_model_field(self, name: str, field: ModelField):
        type_name, type_args = _unpack_type(field.outer_type_)
        desc = field.field_info.description

        class PydanticValidator(Validator):
            def validate(self, document: Document):
                _, errors = field.validate(document.text, {}, loc="")
                if errors:
                    if isinstance(errors, ErrorWrapper):
                        msg = errors.exc
                    else:
                        # errors is a potentially recursive list of errors
                        msg = errors
                    raise ValidationError(message=str(msg))

        # reminder: add title handling

        if type_name is str:
            return self.get_string(name, desc)
        elif type_name is SecretStr:
            return self.get_string(name, desc, is_password=True)
        elif type_name is bool:
            return self.get_bool(name, desc)
        elif type_name is int:
            return self.get_int(name, desc)
        elif type_name is Literal:
            return self.get_from_choices(name, type_args, desc)
        elif type_name is Path:
            return self.get_path(name, desc)
        elif type_name is FilePath:
            return self.get_path(name, desc, validator=PydanticValidator())
        elif type_name is DirectoryPath:
            return self.get_path(
                name, desc, only_directories=True, validator=PydanticValidator()
            )
        elif type_name is list:
            return self.get_list(name, desc)
        elif type_name is dict:
            return self.get_dict(name, desc)
        else:
            if issubclass(type_name, Enum):
                choices = list(type_name.__members__.keys())
                val = self.get_from_choices(name, choices, desc)
                return type_name.__members__[val]
            elif issubclass(type_name, BaseModel):
                return self.from_model(field.type_, prefix=name)

            # this implementation only supports list[str], dict[str, str], and similar types like list[int],
            # which pydantic can coerce directly from list[str] or dict[str, str].
            # reminder: move list & dict handling down to this else block, and validate subtypes contained in them

            raise RuntimeError(
                f"{self.__class__} does not yet support prompting for values of type {field.type_}"
            )

