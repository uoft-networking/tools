# pylint: disable=unused-argument, unused-import, redefined-outer-name, import-outside-toplevel, unspecified-encoding
import os
import sys
import traceback
from typing import Optional
from pathlib import Path
import json

from . import config, _default_templates_dir
from .generate import render_template, model_questionnaire
from .deploy import deploy_to_console

from uoft_core import (
    DataFileFormats,
    File,
    UofTCoreError,
    chomptxt,
    parse_config_file,
    txt,
    write_config_file,
)
from uoft_core.other import Prompt

import typer
from loguru import logger

app = typer.Typer(name="switchdeploy")
generate = typer.Typer(name="generate")
app.add_typer(generate)

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
    except UofTCoreError:
        existing_config = {}
    target_config_file = prompt.select(
        "target_config_file",
        choices=config_files,
        description="Please choose a config file to create. Hit the Tab key to view available choices",
    )
    config_data = model_questionnaire(ConfigModel, existing_config)

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


def show_paths(value: bool):
    if not value:
        return
    con = config.util.console
    states = {
        File.readable: "[green]readable[/]",
        File.writable: "[bright_green]writable[/]",
        File.creatable: "[white]creatable[/]",
        File.unusable: "[bright_black]unusable[/]",
    }
    conf_files = config.util.config.files

    con.print("\n[bold]Config files:[/bold]")
    for file, state in conf_files:
        con.print(f" - {states[state]}: {file}")

    con.print("\n\n[bold]Cache files:[/bold]")
    file = config.util.cache_dir
    state = states[File.state(file)]
    con.print(f" - Data cache({state}): {file}")
    file = get_cache_dir()
    state = states[File.state(file)]
    con.print(f" - Templates cache({state}): {file}")
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
    show_paths: Optional[bool] = typer.Option(
        None,
        "--show-paths",
        callback=show_paths,
        help="Show all filesystem paths used by this application",
    ),
):
    """
    UofT NetMgmt Switch Deploy tool
    """

    log_level = "INFO"
    if debug:
        log_level = "DEBUG"
        if config.data:
            config.data.debug = True
    if trace:
        log_level = "TRACE"
    config.util.logging.enable()
    config.util.logging.add_stderr_rich_sink(log_level)
    config.util.logging.add_syslog_sink()


def get_cache_dir(cache_dir: Optional[Path] = None):
    # sourcery skip: merge-nested-ifs
    if not cache_dir:
        if config.data and config.data.generate:
            cache_dir = config.data.generate.templates_dir
        else:
            cache_dir = _default_templates_dir()
    return cache_dir


def template_name_completion(ctx: typer.Context, partial: str):
    root = get_cache_dir(ctx.params["cache_dir"])

    def template_names():
        for path in root.rglob("*.j2"):
            path = path.relative_to(root)
            path = str(path)
            if partial and partial not in path:
                continue
            yield path

    return list(template_names())


class args:
    cache_dir = typer.Option(
        None, file_okay=False, help="The directory from which to select templates"
    )
    data_file = typer.Option(
        None,
        dir_okay=False,
        allow_dash=True,
        help=chomptxt(
            """
            data file to load template variables from. 
            Any variables not supplied here will be prompted for interactively
            """
        ),
    )
    data_file_format = typer.Option(
        None,
        help="override file format of --data-file, force it to be parsed as this format instead",
    )


@generate.command("from-cache")
def generate_from_cache(
    template: Path = typer.Argument(
        ...,
        help="The name of the template file to render",
        autocompletion=template_name_completion,
    ),
    cache_dir: Optional[Path] = args.cache_dir,
    data_file: Optional[Path] = args.data_file,
    data_file_format: Optional[DataFileFormats] = args.data_file_format,
):
    "Generate a switch configuration from a template file in the template cache"
    if data_file:
        if data_file.name == "-":
            logger.info("reading data from stdin and parsing as JSON...")
            data = json.load(sys.stdin)
        else:
            data = parse_config_file(data_file, parse_as=data_file_format)
    else:
        data = {}
    cache_dir = get_cache_dir(cache_dir)
    template = cache_dir.joinpath(template)
    print(render_template(template, data))


@generate.command("from-file")
def generate_from_file(
    template: Path = typer.Argument(
        ...,
        help="The name of the template file to render",
    ),
    data_file: Optional[Path] = args.data_file,
    data_file_format: Optional[DataFileFormats] = args.data_file_format,
):
    "Generate a switch configuration from a local template file"
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
    if not (config.data and config.data.deploy and config.data.deploy.targets):
        return []
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
    if (
        config.data
        and config.data.deploy
        and console_name in config.data.deploy.targets
    ):
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
    except Exception as e:  # pylint: disable=broad-except
        if config.data and config.data.debug:
            import ipdb

            ipdb.set_trace()
        # wrap exceptions so that only the message is printed to stderr, stacktrace printed to log
        logger.error(e)
        logger.debug(traceback.format_exc())


if __name__ == "__main__":

    if os.environ.get("PYDEBUG"):
        # Debug code goes here
        # pylint: disable=C,R,W,I, undefined-variable

        from .util import construct_model_instance_interactively
        from uoft_switchconfig.types import *

        class SubModel(BaseModel):
            id: int = Field(description="The VLAN ID of this VLAN, Example: 100")
            description: str = Field(
                description="The description of this VLAN, Example: PUBLIC"
            )
            ip: IPv4Network = Field(
                description="The IP address of this VLAN, in CIDR notation, Example: 10.14.1.33/24"
            )

        class MyEnum(StrEnum):
            opt_a = object()
            opt_b = object()
            opt_c = object()

        class ChoiceA(Choice):
            kind: Literal["choicea"]

        class ChoiceB(Choice):
            kind: Literal["choiceb"]

        class Model(BaseModel):
            a: str
            aa: bool
            b: int
            bb: float
            c: Optional[str]
            cc: str | None
            d: Union[str, int, None]
            e: MyEnum
            f: Path
            g: DirectoryPath
            h: Literal["one", "two"]
            i: IPv4Address
            j: SubModel
            k: Union[ChoiceA, ChoiceB]
            l: list
            ll: List
            ids: List[int]
            names: List[str]
            ips: List[IPv4Address]
            objects: List[SubModel]
            z: dict
            za: Dict
            zb: Dict[str, str]
            zc: Dict[int, str]
            xd: Dict[str, int]

        r = construct_model_instance_interactively(Model)
        sys.exit()
    cli()
