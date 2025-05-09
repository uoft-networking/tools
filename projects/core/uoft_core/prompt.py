from typing import Any, Sequence, Union, get_args, get_origin
from types import UnionType
import sys
from base64 import b64encode

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.completion import WordCompleter, PathCompleter, FuzzyCompleter
from prompt_toolkit.validation import Validator, ValidationError
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.document import Document
from prompt_toolkit.output.defaults import create_output
from pydantic.error_wrappers import ErrorWrapper
from pydantic.fields import ModelField
import pydantic

from .types import Enum, Literal, BaseModel, Path, FilePath, DirectoryPath, SecretStr

SUPPORTED_TYPES = (
    str,
    int,
    float,
    bool,
    SecretStr,
    Path,
    FilePath,
    DirectoryPath,
    Enum,
    Literal,
    BaseModel,
    Union,
    list[str],
    list[int],
    list[float],
    list[bool],
    list[SecretStr],
    dict[str, str],
    dict[str, int],
    dict[str, float],
    dict[str, bool],
    dict[str, SecretStr],
)

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
    def __init__(self, history_cache: Path | None):
        if history_cache and not history_cache.exists():
            history_cache.mkdir(parents=True)
        self.history_cache = history_cache

    def get_string(
        self,
        var: str,
        description: str | None,
        default_value: str | None = None,
        is_password: bool = False,
        default_from_history: bool = False,
        **kwargs,
    ) -> str:
        if not var.endswith(": "):
            var = f"{var}: "
        message = FormattedText([("#ffffff #888888", var)])
        opts: dict[str, Any] = dict(
            message=message,
            mouse_support=True,
            bottom_toolbar="",
        )
        if default_value:
            opts["default"] = default_value
        if description:
            opts["bottom_toolbar"] = message

        history = None
        if is_password:
            opts["is_password"] = True
        else:
            if self.history_cache:
                history = FileHistory(f"{self.history_cache}/{_hash(var)}")
                opts["auto_suggest"] = AutoSuggestFromHistory()
                if default_from_history:
                    try:
                        opts["default"] = next(history.load_history_strings())  # pyright: ignore[reportArgumentType]
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
        completer_opts: dict | None = None,
        fuzzy_search: bool = False,
        generate_rprompt: bool = True,
        **kwargs,
    ) -> str:
        validator = Validator.from_callable(
            lambda x: x in choices,
            error_message=f"Choice must be one of {', '.join(choices)}",
        )

        completer_opts = completer_opts or {}
        completer = WordCompleter(list(choices), **completer_opts)
        if fuzzy_search:
            completer = FuzzyCompleter(completer)
        if generate_rprompt:
            choices_str = ", ".join(choices)
            kwargs["rprompt"] = FormattedText([("", "Valid options are: "), ("bold", choices_str)])
        opts = dict(
            completer=completer,
            complete_while_typing=True,
            validator=validator,
        )
        opts.update(kwargs)
        return self.get_string(var, description, default_value, **opts) # pyright: ignore[reportArgumentType]

    def get_path(  # pylint: disable=too-many-arguments
        self,
        var: str,
        description: str | None,
        default_value: str | None = None,
        only_directories=False,
        completer_opts: dict | None = None,
        fuzzy_search: bool = False,
        **kwargs,
    ) -> Path:
        completer_opts = completer_opts or {}
        completer = PathCompleter(only_directories=only_directories, **completer_opts)
        if fuzzy_search:
            completer = FuzzyCompleter(completer)
        opts = dict(
            completer=completer,
            complete_while_typing=True,
        )
        opts.update(kwargs)
        return Path(self.get_string(var, description, default_value, **opts)) # pyright: ignore[reportArgumentType]

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
                    raise ValidationError(message=f"{document.text} is not a valid integer") from exc

        val = self.get_string(
            var,
            description=description,
            default_value=str(default_value) if default_value else None,
            validator=IntValidator(),
            **kwargs,
        )
        return int(val.strip())

    def get_list(
        self,
        var: str,
        description: str | None,
        default_value: list[str] | None = None,
        **kwargs,
    ) -> list[str]:
        kb = KeyBindings()

        @kb.add("c-d")
        def _(event):
            event.app.exit(result=event.app.current_buffer.text)

        opts = dict(
            multiline=True,
            rprompt=FormattedText(
                [
                    ("", "Press "),
                    ("bold", "Enter"),
                    ("", " to add a new line, "),
                    ("bold", "Alt-Enter"),
                    ("", " or "),
                    ("bold", "Ctrl+D"),
                    ("", " to finish and submit list."),
                ]
            ),
            key_bindings=kb,
        )
        opts.update(kwargs)
        val = self.get_string(
            var,
            description,
            default_value="\n".join(default_value) if default_value else None,
            **opts,  # pyright: ignore[reportArgumentType]
        )
        return val.strip().split("\n")

    def get_dict(
        self,
        var: str,
        description: str | None,
        default_value: dict[str, str] | None = None,  # pyright: ignore[reportRedeclaration]
        **kwargs,
    ) -> dict[str, str]:
        kb = KeyBindings()

        class DictValidator(Validator):
            def validate(self, document) -> None:
                for line in document.text.splitlines():
                    if ": " not in line:
                        raise ValidationError(message="Each line must have a key and a value, separated by ': '")

        @kb.add("c-d")
        def _(event):
            event.app.exit(result=event.app.current_buffer.text)

        opts = dict(
            multiline=True,
            rprompt=FormattedText(
                [
                    ("", "Press "),
                    ("bold", "Enter"),
                    ("", " to add a new line, "),
                    ("bold", "Alt-Enter"),
                    ("", " or "),
                    ("bold", "Ctrl+D"),
                    ("", " to finish and submit mapping."),
                ]
            ),
            key_bindings=kb,
            validator=DictValidator(),
        )
        opts.update(kwargs)
        if default_value:
            default_value: str = "\n".join(f"{k}: {v}" for k, v in default_value.items())
        val = self.get_string(var, description, **opts)  # pyright: ignore[reportArgumentType]
        lines = val.strip().split("\n")
        pairs = [line.partition(": ") for line in lines]
        return {k: v for k, _, v in pairs}

    def get_cidr(
        self,
        var: str,
        description: str | None,
        **kwargs,
    ):
        class CIDRValidator(Validator):
            def validate(self, document) -> None:
                try:
                    ip, _, mask = document.text.partition("/")
                    if not 0 <= int(mask) <= 32:
                        raise ValueError
                except ValueError:
                    raise ValidationError(message="Value must be a valid CIDR notation, ex: 192.168.0.1/24")

        return self.get_string(var, description, validator=CIDRValidator(), **kwargs)

    def from_model(self, model: type[BaseModel], prefix: str | None = None):
        res = {}
        for name, field in model.__fields__.items():
            if prefix:
                prompt_name = f"{prefix}.{name}"
            else:
                prompt_name = name
            res[name] = self.from_model_field(prompt_name, field)
        return res

    def from_model_field(self, name: str, field: ModelField):
        type_, type_args = _unpack_type(field.outer_type_)
        desc = field.field_info.description
        default = field.get_default()

        if field.field_info.extra.get("prompt", True) is False:
            # Do not prompt for value, only return default
            return default

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

        # TODO: add title handling
        # TODO: add handling for UrlStr, EmailStr, etc
        # TODO: add handling for constr(regex=...)
        # TODO: add handling for IPAddress, IPNetwork from netaddr module

        if type_ is str:
            return self.get_string(name, desc, default_value=default)
        elif type_ is SecretStr:
            return self.get_string(name, desc, default_value=default, is_password=True)
        elif type_ is bool:
            return self.get_bool(name, desc, default_value=default)
        elif type_ is int:
            return self.get_int(name, desc, default_value=default)
        elif type_ is Literal:
            if len(type_args) == 1:
                # This is a special case, a literal with only one value, ex: Literal["podium"]
                # This case is generally used in combination with discriminated unions
                # https://docs.pydantic.dev/1.10/usage/types/#discriminated-unions-aka-tagged-unions
                # In this case, we can just return the literal value directly
                return type_args[0]
            return self.get_from_choices(name, type_args, desc, default_value=default)
        elif type_ is Path:
            return self.get_path(name, desc, default_value=default)
        elif type_ is FilePath:
            return self.get_path(name, desc, default_value=default, validator=PydanticValidator())
        elif type_ is DirectoryPath:
            return self.get_path(
                name,
                desc,
                default_value=default,
                only_directories=True,
                validator=PydanticValidator(),
            )
        elif type_ is list:
            return self.get_list(name, desc, default_value=default)
        elif type_ is dict:
            return self.get_dict(name, desc, default_value=default)
        elif type_ in [Union, UnionType]:
            assert field.sub_fields
            if not field.discriminator_key:
                # this is a naive union, ex: Union[str, int, bool]
                # not sure how to handle this correctly, so just prompt for the first type
                return self.from_model_field(name, field.sub_fields[0])

            # This is a discriminated union, ex: Union[Model1, Model2] = Field(..., discriminator=kind)
            # Prompt for the discriminator first, then prompt for the model.
            # each submodel will have a field matching the discriminator key, and those fields will each have a type of
            # Literal with one of more values. to select the righ model for prompting, we need to enumerate all the
            # literal values of the discriminator fields of all those submodels
            discriminator = field.discriminator_key
            discriminator_to_model = {}
            for subfield in field.sub_fields:
                if not issubclass(subfield.type_, pydantic.BaseModel):
                    raise ValueError(f"Discriminated union {field.name} contains a non-model type {subfield.type_}")
                if discriminator not in subfield.type_.__fields__:
                    raise ValueError(
                        f"Discriminated union {field.name} contains a model {subfield.type_} \
                            without a discriminator field {discriminator}"
                    )
                for key in get_args(subfield.type_.__fields__[discriminator].type_):
                    discriminator_to_model[key] = subfield.type_

            target_model_name = self.get_from_choices(
                "discriminator",
                list(discriminator_to_model.keys()),
                "Select a model",
                fuzzy_search=True,
            )
            target_model = discriminator_to_model[target_model_name]
            return self.from_model(target_model, prefix=name)

        else:
            if issubclass(type_, Enum):
                choices = list(type_.__members__.keys())
                val = self.get_from_choices(name, choices, desc, default_value=default)
                return type_.__members__[val]
            elif issubclass(type_, BaseModel):
                # Does it make sense to support default values for nested models?
                # How would that work?
                return self.from_model(field.type_, prefix=name)

            # At this point, we've handled every exceptional type I can think of.
            # If we get here, we're dealing with a type that we don't know how to handle.
            # Rather than throwing an exception, we'll prompt for a string with pydantic validation
            # and hope for the best.
            return self.get_string(name, desc, default_value=default, validator=PydanticValidator())
