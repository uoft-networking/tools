import sys
import traceback
from typing import Optional

from . import config

import typer
from loguru import logger

app = typer.Typer(name="at.scripts")
collect = typer.Typer()
app.add_typer(collect, name="collect")


def version_callback(value: bool):
    if value:
        from . import __version__  # noqa
        from sys import version_info as v, platform, executable  # noqa

        print(
            f"at.scripts v{__version__} \nPython {v.major}.{v.minor} ({executable}) on {platform}"
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
    Alex Tremblay's assorted scripts
    """

    log_level = "INFO"
    if debug:
        log_level = "DEBUG"
    if trace:
        log_level = "TRACE"
    config.util.logging.enable()
    config.util.logging.add_stderr_rich_sink(log_level)
    config.util.logging.add_syslog_sink()


@collect.command()
def bluecat():
    """
    Collect bluecat data
    """
    from . import bluecat  # noqa

    bluecat.collect()


def cli():
    try:
        # CLI code goes here
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
        from . import bluecat  # noqa

        bluecat.collect()

        sys.exit()
    cli()
