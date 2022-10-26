import sys
from typing import Optional
from sys import version_info, platform, executable
from importlib.metadata import version

from . import Util

import typer
from loguru import logger

app = typer.Typer(name=__package__)

util = Util(__package__)


def version_callback(value: bool):
    if value:
        v = version_info
        print(
            f"uoft wrapper command v{version(__package__)}\nPython {v.major}.{v.minor} ({executable}) on {platform})"
        )
        raise typer.Exit()


@app.callback(
    context_settings={"max_content_width": 120, "help_option_names": ["-h", "--help"]}
)
def callback(
    debug: bool = typer.Option(False, help="Turn on debug logging"),
    trace: bool = typer.Option(False, help="Turn on trace logging. implies --debug"),
    version: Optional[bool] = typer.Option(  # pylint: disable=unused-argument
        None,
        "--version",
        callback=version_callback,
        help="Show version information and exit",
    ),
):
    """
    Command-line namespace for all uoft command-line utilities. makes each uoft_* command available as a subcommand.
    """

    log_level = "INFO"
    if debug:
        log_level = "DEBUG"
    if trace:
        log_level = "TRACE"
    util.logging.enable()
    util.logging.add_stderr_rich_sink(log_level)
    util.logging.add_syslog_sink()

@logger.catch
def cli():
    try:
        app()
    except KeyboardInterrupt:
        print("Aborted!")
        sys.exit()


if __name__ == "__main__":
    import os

    if os.environ.get("PYDEBUG"):
        # let's interactively prompt for a module to debug and execute that

        from importlib import import_module
        from importlib.util import find_spec
        from .prompt import Prompt, Validator

        p = Prompt(util)
        v = Validator.from_callable(
            lambda n: bool(find_spec(n)),
            "no such module exists in the current python installation",
        )
        mod_name = p.get_string(
            "module name",
            'Enter the full dotted name of the module you\'d like to debug. Ex: "uoft_core.nested_data"',
            validator=v,
            default_from_history=True
        )
        args = p.get_string("args", "Enter any arguments you'd like to pass to the module", default_from_history=True)
        sys.argv.extend(args.split())
        mod = import_module(mod_name)
        if hasattr(mod, "_debug"):
            mod._debug() # pylint: disable=protected-access
        else:
            print(f"Module {mod_name} has no _debug() function")
        sys.exit()
    cli()
