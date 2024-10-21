"""
CLI and API to work with Paloalto products (NSM, etc)
"""

from typing import Annotated, Optional
import sys

import typer

from uoft_core import logging
from uoft_core.types import SecretStr
from . import Settings

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
    name="paloalto",
    context_settings={"max_content_width": 120, "help_option_names": ["-h", "--help"]},
    no_args_is_help=True,
    help=__doc__,  # Use this module's docstring as the main program help text
)


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


@app.command()
def generate_api_key():
    """Generate an API key for the Palo Alto API"""
    s = Settings.from_cache()
    api = s.get_api_connection()
    api.login()
    key = api.generate_api_key()
    s.api_key = SecretStr(key)
    s.interactive_save_config()


@app.command()
def network_list():
    """Get all addresses from the Palo Alto API"""
    s = Settings.from_cache()
    api = s.get_api_connection()
    api.login()
    networks = api.network_list()
    for n in networks:
        print(f"{n['@name']:30} => {n['ip-netmask']}")

@app.command()
def network_create(name: str, netmask: str, description: str | None = None, tags: list[str] | None = None):
    """Create a network object in the Palo Alto API"""
    tags_set = set(tags) or None
    s = Settings.from_cache()
    api = s.get_api_connection()
    api.login()
    api.network_create(name, netmask, description, tags=tags_set)


@app.command()
def network_delete(name: str):
    """Delete a network object in the Palo Alto API"""
    s = Settings.from_cache()
    api = s.get_api_connection()
    api.login()
    api.network_delete(name)
    

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
