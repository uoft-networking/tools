import os, sys
import traceback
from typing import Optional

from . import config
from . import bluecat
from . import ldap

import typer
from loguru import logger

app = typer.Typer(
    name="uoft_scripts",
    context_settings={"max_content_width": 120, "help_option_names": ["-h", "--help"]},
    no_args_is_help=True,
    help=__doc__,  # Use this module's docstring as the main program help text
)
app.add_typer(bluecat.app)
app.add_typer(ldap.app)


def version_callback(value: bool):
    if value:
        from . import __version__  # noqa
        from sys import version_info as v, platform, executable  # noqa

        print(
            f"uoft_scripts v{__version__} \nPython {v.major}.{v.minor} ({executable}) on {platform}"
        )
        raise typer.Exit()


@app.callback()
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


def cli():
    try:
        # CLI code goes here
        app()
    except KeyboardInterrupt:
        print("Aborted!")
        sys.exit()
    except Exception as e:  # pylint: disable=broad-except
        # wrap exceptions so that only the message is printed to stderr, stacktrace printed to log
        logger.error(e)
        logger.debug(traceback.format_exc())


def deprecated():
    import sys
    from warnings import warn

    cmdline = " ".join(sys.argv)
    if (from_ := "uoft_scripts") in cmdline:
        to = "uoft-scripts"
        cmd = app
    elif (from_ := "utsc.scripts") in cmdline:
        to = "uoft-scripts"
        cmd = app
    elif (from_ := "utsc.scripts aruba") in cmdline:
        to = "uoft-aruba"
        from uoft_aruba.cli import app as aruba_app
        cmd = aruba_app
    else:
        raise ValueError(f"command {cmdline} is not deprecated")

    #TODO: convert this into a log.warn msg once we've sorted out logging
    warn(
        FutureWarning(
            f"The '{from_}' command has been renamed to '{to}' and will be removed in a future version."
        )
    )
    cmd()



def _debug():
    "Debugging function, only used in active debugging sessions."
    # pylint: disable=all
    print()

if __name__ == "__main__":
    cli()
