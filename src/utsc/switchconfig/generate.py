from pathlib import Path
import sys
from typing import Callable, Optional, Any, Type
from inspect import getmembers, isfunction

from .util import (
    DEFAULT_GLOBALS,
    model_questionnaire, 
    get_comment_block_schema, 
    construct_model_from_comment_block_schema,
    create_python_module,
    normalize_extension_name
)

from loguru import logger
from pydantic import BaseModel
from jinja2 import Environment, StrictUndefined, FileSystemLoader

JINJA_OPTS = {
    "block_start_string",
    "block_end_string",
    "variable_start_string",
    "variable_end_string",
    "comment_start_string",
    "comment_end_string",
    "line_statement_prefix",
    "line_comment_prefix",
    "trim_blocks",
    "lstrip_blocks",
    "newline_sequence", 
    "keep_trailing_newline",}

class ExtensionModule():
    filters: Optional[dict[str, Callable]] = None
    tests: Optional[dict[str, Callable[[Any], bool]]] = None
    globals: Optional[dict[str, Any]] = None
    jinja_opts: Optional[dict[str, Any]] = None
    model: Optional[Type[BaseModel]] = None
    preprocess_data: Optional[Callable[[dict[str, Any]], dict[str, Any]]] = None

    def __init__(self, module) -> None:
        if hasattr(module, "Filters"):
            filters = module.Filters
            self.filters = dict(getmembers(filters, isfunction))
        if hasattr(module, "Tests"):
            tests = module.Tests
            self.tests = dict(getmembers(tests, isfunction))
        if hasattr(module, "GLOBALS"):
            assert isinstance(module.GLOBALS, dict), "GLOBALS must be a python dictionary"
            self.globals = module.GLOBALS
        if hasattr(module, "JINJA_OPTS"):
            assert isinstance(module.JINJA_OPTS, dict), "JINJA_OPTS must be a python dictionary"
            self.jinja_opts = {}
            for key in JINJA_OPTS:
                if key in module.JINJA_OPTS:
                    self.jinja_opts[key] = module.JINJA_OPTS[key]
        if hasattr(module, "Model"):
            self.model = module.Model
        if hasattr(module, "preprocess_data"):
            assert isinstance(module.preprocess_data, Callable), "preprocess_data must be a python function"
            self.preprocess_data = module.preprocess_data


def get_template_extension(template: Path) -> Optional[ExtensionModule]:
    extension_file = template.with_suffix(".py")
    if not extension_file.exists():
        return None

    logger.trace(f"Found extension file {extension_file}")
    extension_name = normalize_extension_name(extension_file.stem)

    if extension_name in sys.modules:
        template_module = sys.modules[extension_name]
    else:
        template_module =  create_python_module(extension_name, extension_file)
    
    return ExtensionModule(template_module)


def validate_data_for_template(template: Path, extension: Optional[ExtensionModule], data: dict[str, Any]):
    # if template contains a model, validate the data using that model
    # if template does not contain a model, but does contain a comment block schema, 
    # construct a model from the comment block schema and validate the data using that model
    # otherwise, pass the data through without validation
    if extension is not None and extension.model is not None:
        logger.trace(f"Validating data using model {extension.model}")
        return model_questionnaire(extension.model, data)
    if (comment_block_schema := get_comment_block_schema(template.read_text())):
        logger.trace("Validating data using comment block schema")
        model = construct_model_from_comment_block_schema(comment_block_schema)
        return model_questionnaire(model, data)
    # else:
    return data



def render_template(template: Path, input_data: dict[str, Any] | None = None):
    input_data = input_data or {}
    extension = get_template_extension(template)
    logger.trace(f'input data: {input_data}')
    if extension and extension.preprocess_data:
        logger.trace("Found `preprocess_data` function in template extension module, passing input data through that")
        template_data = extension.preprocess_data(input_data)
    else:
        logger.trace("No `preprocess_data` function defined in template extension module")
        template_data = input_data
    template_data = validate_data_for_template(template, extension, template_data)

    jinja = Environment(
        trim_blocks=True,
        lstrip_blocks=True,
        loader=FileSystemLoader(template.parent),
        undefined=StrictUndefined,
        line_statement_prefix="//",
        line_comment_prefix="##",
    )
    # Add filter functions from the Filters class to the environment for use inside the templates
    if extension and extension.filters:
        logger.trace("Loading filters from `Filters` class in template extension module")
        jinja.filters.update(extension.filters)

    # Add test functions from the Tests class to the environment for use inside the templates
    if extension and extension.tests:
        logger.trace("Loading tests from `Tests` class in template extension module")
        jinja.tests.update(extension.tests)

    # make all useable data available to the template
    jinja.globals.update(DEFAULT_GLOBALS)
    if extension and extension.globals:
        logger.trace("loading `GLOBALS` from templates module")
        jinja.globals.update(extension.globals)
    jinja.globals.update(template_data)
    logger.trace(f"jinja environment globals: {jinja.globals}")

    # Fetch and render the template
    rendered = jinja.get_template(template.name).render()

    logger.success(f"template {template.name} has been successfully rendered")

    return rendered
