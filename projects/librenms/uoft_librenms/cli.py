"""
API Wrapper and (hopefully soon) CLI interface for the LibreNMS REST API
"""
from typing import Annotated, Optional
import sys

import typer

from . import Settings
from uoft_core import logging

logger = logging.getLogger(__name__)

DEBUG_MODE = False


def _version_callback(value: bool):
    if not value:
        return
    from . import __version__
    import sys

    print(
        f"uoft-{Settings.Config.app_name} v{__version__} \nPython {sys.version_info.major}."
        f"{sys.version_info.minor} ({sys.executable}) on {sys.platform}"
    )
    raise typer.Exit()

app = typer.Typer(
    name="librenms",
    context_settings={"max_content_width": 120, "help_option_names": ["-h", "--help"]},
    no_args_is_help=True,
    help=__doc__,  # Use this module's docstring as the main program help text
)

@app.callback()
#@Settings.wrap_typer_command
#TODO: implement click paramtype support for Settings AnyHttpUrl
def callback(
    version: Annotated[
        Optional[bool],
        typer.Option("--version", callback=_version_callback, is_eager=True, help="Show version information and exit"),
    ] = None,
    debug: bool = typer.Option(False, help="Turn on debug logging", envvar="DEBUG"),
    trace: bool = typer.Option(False, help="Turn on trace logging. implies --debug", envvar="TRACE"),
):
    global DEBUG_MODE
    log_level = "INFO"
    if debug:
        log_level = "DEBUG"
        DEBUG_MODE = True
    if trace:
        log_level = "TRACE"
        DEBUG_MODE = True
    logging.basicConfig(level=log_level)


@app.command()
def re_discover(device_name: str):
    """
    Triggers discovery on an existing device in LibreNMS
    """

    api = Settings.from_cache().api_connection()
    res = api.devices.discover_device(device_name)
    logger.info(res)


def cli():
    try:
        # CLI code goes here
        app()
    except KeyboardInterrupt:
        print("Aborted!")
        sys.exit()
    except Exception as e:
        if DEBUG_MODE:
            raise
        logger.error(e)
        sys.exit(1)

def _debug():
    "Debugging function, only used in active debugging sessions."
    # pylint: disable=all
    app()
