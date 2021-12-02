import sys
import traceback
from typing import Optional
from sys import version_info, platform, executable
from importlib.metadata import version
from subprocess import run
from pathlib import Path

from utsc.core import Util

import typer
from loguru import logger

app = typer.Typer(name=__package__)

util = Util(__package__)


def version_callback(value: bool):
    if value:
        v = version_info
        print(
            f"utsc wrapper command v{version(__package__)}\nPython {v.major}.{v.minor} ({executable}) on {platform}"
        )
        raise typer.Exit()


def install_callback(value: str):
    if value:
        installation = Path(executable).parent
        pip = installation.joinpath("pip3")
        fix_shebangs = installation.joinpath('fix-shebangs.py')
        run([pip, "install", f"utsc.{value}"], check=True)
        if fix_shebangs.exists():
            run([fix_shebangs], check=True)
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
    install: Optional[str] = typer.Option(  # pylint: disable=unused-argument
        None,
        "--install",
        callback=install_callback,
        help="install a utsc tool into this python installation and exit",
    ),
):
    """
    Command-line namespace for all utsc command-line utilities. makes each utsc.* command available as a subcommand.
    """

    log_level = "INFO"
    if debug:
        log_level = "DEBUG"
    if trace:
        log_level = "TRACE"
    util.logging.enable()
    util.logging.add_stderr_rich_sink(log_level)
    util.logging.add_syslog_sink()


def cli():
    try:
        app()
    except KeyboardInterrupt:
        print("Aborted!")
        sys.exit()
    except Exception as e:
        # wrap exceptions so that only the message is printed to stderr, stacktrace printed to log
        logger.error(e)
        logger.debug(traceback.format_exc())


if __name__ == "__main__":
    import os, sys  # noqa

    if os.environ.get("PYDEBUG"):
        # Debug code goes here

        sys.exit()
    cli()
