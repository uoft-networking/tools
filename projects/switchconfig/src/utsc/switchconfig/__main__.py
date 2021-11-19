import sys
import traceback
from typing import Optional

from . import config
from .generate import render_template, model_questionnaire
from .deploy import deploy_to_console

from utsc.core import UTSCCoreError, parse_config_file, write_config_file

import typer
from loguru import logger

app = typer.Typer(name="switchdeploy")


def version_callback(value: bool):
    if value:
def init_config_callback(value: bool):
    if value:
        from . import ConfigModel
        from utsc.core.other import Prompt

        prompt = Prompt(config.util)
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
        try:
            # TODO: clean this up
            config_data['generate']['templates_dir'] = str(config_data['generate']['templates_dir'])
        except (KeyError, ValueError):
            pass
        write_config_file(Path(target_config_file), config_data)
        logger.success(f"Configuration data written to {target_config_file}")
        raise typer.Exit()


@app.callback(
    context_settings={"max_content_width": 120, "help_option_names": ["-h", "--help"]}
)
def callback(
    debug: bool = typer.Option(False, help="Turn on debug logging"),
    trace: bool = typer.Option(False, help="Turn on trace logging. implies --debug"),
    init_config: Optional[bool] = typer.Option(
        None,
        "--init-config",
        callback=init_config_callback,
        help="Create the configuration file for this application and fill it out interactively",
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


def template_name_completion(partial: str):
    root = config.templates.PATH

    def template_names():
        for path in root.rglob("*.j2"):
            path = path.relative_to(root)
            path = str(path)
            if partial and partial not in path:
                continue
            yield path

    return list(template_names())
    

@app.command()
def generate(
    template_name: str = typer.Argument(
        ...,
        help="The name of the template file to render",
        autocompletion=template_name_completion,
    )
):
    "Generate a switch configuration from a questionnaire"
    print(render_template(template_name))


def console_name_completion(partial: str):
    if config.data.deploy:
        targets = list(config.data.deploy.targets.keys())
    else:
        targets = []
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
            import ipdb # noqa
            ipdb.set_trace()
        logger.error(e)
        logger.debug(traceback.format_exc())


if __name__ == "__main__":
    import os, sys  # noqa

    if os.environ.get("PYDEBUG"):
        # Debug code goes here

        res = render_template("2960CX.cisco.j2")
        res
        sys.exit()
    cli()
