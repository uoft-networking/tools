from typing import Any, Literal, Type, TYPE_CHECKING, Union, get_origin, get_args
import os
import string
import secrets
from pathlib import Path

from . import config

from utsc.core import StrEnum
from utsc.core.other import Prompt
from pydantic import BaseModel
from loguru import logger  # noqa
from jinja2 import Environment, StrictUndefined, FileSystemLoader
from arrow import now

if TYPE_CHECKING:
    from pydantic.fields import ModelField

prompt = Prompt(config.util)

class SwitchConfigException(Exception):
    pass


class EnvVars:
    # a change to Jinja broke the ability to embed
    # os.environ as a simple dict into jinja environment's
    # globals. Here we wrap it in a simple getter
    def __getattr__(self, name):
        return os.environ.get(name, "")


# any object placed into this dictionary will be made available as a global variable in all templates
DEFAULT_GLOBALS = {
    "env_vars": EnvVars(),
    "now": now(),
    "password_gen": lambda: "".join(
        [secrets.choice(string.ascii_letters + string.digits) for i in range(24)]
    ),
}


def extract_questions(template: str) -> list[tuple[str, str, str]]:
    # extract questionnaire from template
    questions_missing_msg = "Missing question block. All switch \
        templates must start with a comment block starting with \
        '{#\\n' and ending with '#}\\n'."

    if not template.startswith("{#"):
        raise SwitchConfigException(questions_missing_msg)
    questions_str, _, _ = template.partition("#}")
    if not questions_str:
        raise SwitchConfigException(questions_missing_msg)
    questions_lst = questions_str.splitlines()
    if len(questions_lst) < 3:
        raise SwitchConfigException(
            "Question block has an invalid format. \
            See the README for what a valid quesiton block format looks like"
        )

    questions_lst = questions_lst[2:]
    questions = []
    for question in questions_lst:
        var, desc, default_val = tuple(
            map(lambda s: s.strip(), question.split("|", maxsplit=3))
        )
        questions.append((var, desc, default_val))
    return questions


def get_answers_interactively(questions: list[tuple[str, str, str]]) -> dict:
    ans = {}
    for question in questions:
        var = question[0]
        val = prompt.string(*question)
        ans[var] = val
    return ans


def validate_data_from_comment_block_schema(template_file: Path, input_data: dict[str, Any]):
    template = template_file.read_text()
    try:
        questions = extract_questions(template)
    except SwitchConfigException as e:
        raise SwitchConfigException(f"Error in {template_file}: {e.args[0]}") from e
    if not input_data:
        return get_answers_interactively(questions)
    # else:
    output = input_data.copy()
    for question in questions:
        field_name = question[0]
        if field_name not in input_data:
            output[field_name] = prompt.string(*question)
    return output


class Choice(BaseModel):
    # Base class used to define multiple choices in a discriminated union.
    # see the "Union" example under https://pydantic-docs.helpmanual.io/usage/types/#literal-type
    # for details
    kind: str


def discriminated_union_choices(field: "ModelField") -> dict[str, Type] | None:
    """
    Return the set of kind literals for a discriminated union, 
    or None if this field is not a discriminated union.

    Given a pydantic model field whose annotation is something like `Union[Choice1,Choice2,Choice3], 
    and given that each of these sub types of the union is an instance of Choice,
    and given that each of these Choice subclasses has a `kind` attribute annotated with a Literal string,
    return the set of strings of all choices"""
    if get_origin(field.type_) is not Union: # type: ignore
        return None
    assert isinstance(field.sub_fields, list)
    choices = {}
    for sub in field.sub_fields:
        if not issubclass(sub.type_, Choice):
            return None
        kind_type = sub.type_.__fields__['kind'].type_
        assert get_origin(kind_type) is Literal
        choice = get_args(kind_type)[0]
        choices[choice] = sub.type_
    return choices


ValidatorBase = prompt.Validator

class ValidatorWrapper(ValidatorBase):
    def __init__(self, field: 'ModelField', values: dict[str, Any]) -> None:
        self.field = field
        self.values = values

    def validate(self, document) -> None:
        _, errors = self.field.validate(document.text, self.values, loc=self.field.name)
        if errors:
            from pydantic.error_wrappers import ErrorWrapper # noqa
            if isinstance(errors, ErrorWrapper):
                raise prompt.ValidationError(message=str(errors.exc))
            # else:
            raise prompt.ValidationError(message=str(errors))

def model_questionnaire(model: Type["BaseModel"], input_data: dict[str, Any] | None = None):
    """
    Given a pydantic data model, 
    prompt user for inputs matching fields on that model, 
    and return an instance of that model 
    """

    input_data = input_data or {}
    for name, field in model.__fields__.items():
        if name in input_data:
            continue

        desc = field.field_info.description
        default = field.default
        
        if (choices := discriminated_union_choices(field)):
            choice = prompt.select(name, list(choices.keys()), desc)
            input_data[name] = model_questionnaire(choices[choice], {'kind': choice})
            continue
        elif issubclass(field.type_, StrEnum):
            choices = list(field.type_.__members__.keys())
            input_data[name] = prompt.select(name, choices, desc)
            continue
        # TODO: add handlers for fields of type list[str], Literal['string1','string2'], etc.
        else:
            # prompt for str, and let pydantic's validators sort it out
            validator = ValidatorWrapper(field, input_data)

            input_data[name] = prompt.string(name, desc, default, validator=validator)
    return input_data


def render_template(template_name: str, input_data: dict[str, Any] | None = None):
    input_data = input_data or {}
    templates = config.templates
    template_data = templates.get_template_data(template_name, input_data)

    jinja = Environment(
        trim_blocks=True,
        lstrip_blocks=True,
        loader=FileSystemLoader(templates.PATH),
        undefined=StrictUndefined,
        line_statement_prefix="//",
        line_comment_prefix="##",
    )
    # Add filter functions from the Filters class to the environment for use inside the templates
    for funcname in dir(templates.Filters):
        func = getattr(templates.Filters, funcname)
        if callable(func) and not funcname.startswith("__"):
            jinja.filters[funcname] = func

    # make the answers dict available to the template
    jinja.globals.update(DEFAULT_GLOBALS)
    jinja.globals.update(template_data)

    # Fetch and render the template
    rendered = jinja.get_template(template_name).render()

    return rendered
