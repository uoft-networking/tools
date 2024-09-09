from typing import Annotated, Optional
import sys

import typer

from uoft_core import logging

from .cli_commands import cpsec_allowlist, station_blocklist, list_aps
from . import Settings

logger = logging.getLogger(__name__)

DEBUG_MODE = False

app = typer.Typer(
    name="aruba",
    context_settings={"max_content_width": 120, "help_option_names": ["-h", "--help"]},
    no_args_is_help=True,
    help=__doc__,  # Use this module's docstring as the main program help text
)
app.add_typer(cpsec_allowlist.run, name="cpsec-allowlist")
app.add_typer(cpsec_allowlist.run, name="cpsec-whitelist", deprecated=True)
app.add_typer(station_blocklist.app, name="station-blocklist")
app.add_typer(list_aps.run, name="list-aps")
app.add_typer(list_aps.run, name="inventory", deprecated=True)
app.add_typer(station_blocklist.app, name="station-blacklist", deprecated=True)


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


@app.callback()
@Settings.wrap_typer_command
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


def deprecated():
    import sys
    from warnings import warn

    cmdline = " ".join(sys.argv)
    if (from_ := "uoft_aruba") in cmdline:
        to = "uoft-aruba"
        cmd = app
    elif (from_ := "Aruba_Provision_CPSEC_Whitelist") in cmdline:
        to = "uoft-aruba cpsec-allowlist"
        cmd = cpsec_allowlist.run
    else:
        raise ValueError(f"command {cmdline} is not deprecated")

    warn(
        f"The '{from_}' command has been renamed to '{to}' and will be removed in a future version.",
        DeprecationWarning,
    )
    cmd()


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
