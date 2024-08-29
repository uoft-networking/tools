import sys
from typing import Annotated, Optional

from . import ldap
from . import nautobot
from . import librenms

from uoft_core import logging

import typer

def _version_callback(value: bool):
    if not value:
        return
    from . import __version__
    import sys

    print(
        f"uoft-scripts v{__version__} \nPython {sys.version_info.major}."
        f"{sys.version_info.minor} ({sys.executable}) on {sys.platform}"
    )
    raise typer.Exit()


app = typer.Typer(
    name="scripts",
    context_settings={"max_content_width": 120, "help_option_names": ["-h", "--help"]},
    no_args_is_help=True,
    help=__doc__,  # Use this module's docstring as the main program help text
)
app.add_typer(ldap.app)
app.add_typer(nautobot.app)
app.add_typer(librenms.app)


@app.callback()
def callback(
    version: Annotated[
        Optional[bool],
        typer.Option("--version", callback=_version_callback, is_eager=True, help="Show version information and exit"),
    ] = None,
    debug: bool = typer.Option(False, help="Turn on debug logging", envvar="DEBUG"),
    trace: bool = typer.Option(False, help="Turn on trace logging. implies --debug", envvar="TRACE"),
):
    log_level = "INFO"
    if debug:
        log_level = "DEBUG"
    logging.basicConfig(level=log_level)


def cli():
    try:
        # CLI code goes here
        app()
    except KeyboardInterrupt:
        print("Aborted!")
        sys.exit()


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
