# pylint: disable=unused-argument, import-outside-toplevel, unspecified-encoding
import os
import sys
import traceback
from typing import Optional
from pathlib import Path
import json

from . import config
from .generate import render_template, model_questionnaire
from .deploy import deploy_to_console

from utsc.core import (
    DataFileFormats,
    UTSCCoreError,
    chomptxt,
    parse_config_file,
    txt,
    write_config_file,
)
from utsc.core.other import Prompt

import typer
from loguru import logger

app = typer.Typer(name="switchdeploy")

prompt = Prompt(config.util)


def version_callback(value: bool):
    if value:
        from . import __version__
        from sys import version_info as v, platform, executable

        print(
            f"Switchdeploy v{__version__} \nPython {v.major}.{v.minor} ({executable}) on {platform}"
        )
        raise typer.Exit()


def initialize_config(value: bool):
    if not value:
        return
    from . import ConfigModel

    config_files = [str(x) for x in config.util.config.writable_or_creatable_files]
    try:
        existing_config = config.util.config.merged_data
    except UTSCCoreError:
        existing_config = {}
    target_config_file = prompt.select(
        "target_config_file",
        choices=config_files,
        description="Please choose a config file to create. Hit the Tab key to view available choices",
    )
    config_data = model_questionnaire(ConfigModel, existing_config)
    config_data = ConfigModel(**config_data)
    
    # convert the model to a serializable dict
    config_data = json.loads(config_data.json())
    write_config_file(Path(target_config_file), config_data)
    logger.success(f"Configuration data written to {target_config_file}")
    raise typer.Exit()


def initialize_templates(value: bool):
    if not value:
        return
    templates = Path("templates")
    logger.debug(f"preparing to initialize {templates.resolve()}")
    if templates.exists() and templates.joinpath("__init__.py").exists():
        overwrite = prompt.bool_(
            "overwrite?",
            "Do you wish to overwrite / reset the existing __init__.py file in `./templates`?",
        )
        if not overwrite:
            logger.error("Cancelled")
            raise typer.Exit()
    templates.mkdir(exist_ok=True)
    logger.debug("created templates directory")
    example_templates = Path(__file__).parent.joinpath("example_template_dir")
    logger.debug(f"copying content from {example_templates.resolve()}")
    for file in example_templates.iterdir():
        templates.joinpath(file.name).write_text(file.read_text())
    config.util.console.print(
        chomptxt(
            """
            [green]Done![/green] you may now start adding templates to the 
            `templates` folder and adding logic to the `__init__.py` file within
            """
        )
    )
    raise typer.Exit()


@app.callback(
    context_settings={"max_content_width": 120, "help_option_names": ["-h", "--help"]}
)
def callback(
    debug: bool = typer.Option(False, help="Turn on debug logging"),
    trace: bool = typer.Option(False, help="Turn on trace logging. implies --debug"),
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        callback=version_callback,
        help="Show version information and exit",
    ),
    init_config: Optional[bool] = typer.Option(
        None,
        "--init-config",
        callback=initialize_config,
        help="Create the configuration file for this application and fill it out interactively",
    ),
    init_templates: Optional[bool] = typer.Option(
        None,
        "--init-templates",
        callback=initialize_templates,
        help="Create a template project/folder to put templates into",
    ),
):
    """
    UTSC NetMgmt Switch Deploy tool
    """

    log_level = "INFO"
    if debug:
        log_level = "DEBUG"
        config.data.debug = True
    if trace:
        log_level = "TRACE"
    config.util.logging.enable()
    config.util.logging.add_stderr_rich_sink(log_level)
    config.util.logging.add_syslog_sink()


def template_name_completion(ctx: typer.Context, partial: str):
    root = config.templates.PATH

    def template_names():
        for path in root.rglob("*.j2"):
            path = path.relative_to(root)
            path = str(path)
            if partial and partial not in path:
                continue
            yield path

    return list(template_names())

# TODO: figure out how to bridge the divide between targeting local templates and targeting cached templates
# maybe split generate into two functions, one for local templates and one for cached templates
@app.command()
def generate(
    template: Path = typer.Argument(
        ...,
        help="The name of the template file to render",
        autocompletion=template_name_completion,
    ),
    template_dir: Optional[Path] = typer.Option(
        None, file_okay=False, help="The directory from which to select templates"
    ),
    data_file: Optional[Path] = typer.Option(
        None,
        dir_okay=False,
        allow_dash=True,
        help=chomptxt(
            """
            data file to load template variables from. 
            Any variables not supplied here will be prompted for interactively
            """
        ),
    ),
    data_file_format: Optional[DataFileFormats] = typer.Option(
        None,
        help="override file format of --data-file, force it to be parsed as this format instead",
    ),
):
    "Generate a switch configuration from a questionnaire, a data file, or both"
    if data_file:
        if data_file.name == "-":
            logger.info("reading data from stdin and parsing as JSON...")
            data = json.load(sys.stdin)
        else:
            data = parse_config_file(data_file, parse_as=data_file_format)
    else:
        data = {}
    print(render_template(template, data))


def console_name_completion(partial: str):
    targets = list(config.data.deploy.targets.keys()) if config.data.deploy else []
    res = []
    if partial:
        for target in targets:
            if partial in target:
                res.append(target)
    else:
        res = targets
    return res


@app.command()
def to_console(
    console_name: str = typer.Argument(
        ..., help="Name of the console server / port to deploy to"
    )
):
    "Connect to a serial console server, authenticate, and pass in configuration from STDIN"
    if config.data.deploy and console_name in config.data.deploy.targets:
        target = config.data.deploy.targets[console_name]
    else:
        target = console_name
    deploy_to_console(target)


def cli():
    try:
        # CLI code goes here
        app()
    except KeyboardInterrupt:
        print("Aborted!")
        sys.exit()
    except Exception as e:
        # wrap exceptions so that only the message is printed to stderr, stacktrace printed to log
        if config.data.debug:
            import ipdb

            ipdb.set_trace()
        logger.error(e)
        logger.debug(traceback.format_exc())


if __name__ == "__main__":

    if os.environ.get("PYDEBUG"):
        # Debug code goes here

        from .util import get_comment_block_schema

        t = txt(
            """
            {#
            # variable_name | description | default_value
            usage | One of: (deskswitch/podium/access), Example: deskswitch | 
            building_code | (aka alpha code) Example: SW | 
            room_code | Example: 254A | 
            tr_code | (Optional, only applicable if usage is access) Telecom Room code, Example: 2r | 
            user_id | (Optional, only applicable if usage is deskswitch) UTSCID of the person this switch  | 
            network | network address of the mgmt network in CIDR notation, Example: 10.14.1.0/24 | 
            ip | IP address of this switch on the mgmt network, Example: 10.14.1.33 |
            #}
            {% macro hostname_partial() -%}
            {# in a hostname like 'av-ac254a', 'a1-ic2r', or 'a1-someuser' #}
                {% if usage == 'deskswitch' %}{{ user_id }}{% endif %}
                {% if usage == 'podium' %}{{ building_code | lower }}{{ room_code | lower }}{% endif %}
                {% if usage == 'access' %}{{ building_code | lower }}{{ tr_code }}{% endif %}
            {%- endmacro %}
            {% macro hostname() %}{{ usage | remap("usages") }}-{{ hostname_partial() }}{% endmacro %}

            """
        )
        get_comment_block_schema(t)
        sys.exit()
    cli()
