import sys
import traceback
from typing import Optional

from . import config
from .generate import render_template
from .deploy import deploy_to_console

import typer
from loguru import logger

app = typer.Typer(name="switchdeploy")


def version_callback(value: bool):
    if value:
        from . import __version__ # noqa
        from sys import (version_info as v, platform, executable) # noqa
        print(f"Switchdeploy v{__version__} \nPython {v.major}.{v.minor} ({executable}) on {platform}")
        raise typer.Exit()


@app.callback(
    context_settings={"max_content_width": 120, "help_option_names": ["-h", "--help"]}
)
def callback(
    debug: bool = typer.Option(False, help="Turn on debug logging"),
    trace: bool = typer.Option(False, help="Turn on trace logging. implies --debug"),
    version: Optional[bool] = typer.Option(  # pylint: disable=unused-argument
        None, "--version", callback=version_callback,
        help="Show version information and exit"
    )
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
    targets = list(config.data.deploy_targets.keys())
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
    target = config.data.deploy_targets[console_name]
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
