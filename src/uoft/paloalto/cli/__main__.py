"""
CLI and API to work with Paloalto products (NSM, etc)
"""

import typing as t
import sys

import typer

from uoft.core import logging
from uoft.core.types import SecretStr
from ..conf import Settings

logger = logging.getLogger(__name__)

DEBUG_MODE = False
TARGET_HOST = None


def get_settings() -> Settings:
    """Get the settings for the current host."""
    global TARGET_HOST
    s = Settings.from_cache()
    if TARGET_HOST:
        s = s.get_host_config(TARGET_HOST)
    return s


def _version_callback(value: bool):
    if not value:
        return
    from ..version import __version__
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
    version: t.Annotated[
        t.Optional[bool],
        typer.Option("--version", callback=_version_callback, is_eager=True, help="Show version information and exit"),
    ] = None,
    debug: bool = typer.Option(False, help="Turn on debug logging", envvar="DEBUG"),
    trace: bool = typer.Option(False, help="Turn on trace logging. implies --debug", envvar="TRACE"),
    host: t.Annotated[
        t.Optional[str],
        typer.Option(
            "--host",
            "-H",
            help="The host to connect to. This should match a key in the 'hosts' section of the config file.",
            envvar="PALOALTO_HOST",
        ),
    ] = None,
):
    global DEBUG_MODE, TARGET_HOST
    TARGET_HOST = host
    log_level = "INFO"
    if debug:
        log_level = "DEBUG"
        DEBUG_MODE = True
    if trace:
        log_level = "TRACE"
        DEBUG_MODE = True
    logging.basicConfig(level=log_level)

    logger.debug(f"Using config: {Settings.from_cache()}")


@app.command()
def generate_api_key():
    """Generate an API key for the Palo Alto API"""
    with get_settings().get_api_connection() as api:
        print(api.api_key)


@app.command()
def network_list():
    """Get all addresses from the Palo Alto API"""
    with get_settings().get_api_connection() as api:
        networks = api.network_list()
    for n in networks:
        print(f"{n['@name']:30} => {n['ip-netmask']}")


@app.command()
def network_create(name: str, netmask: str, description: t.Optional[str] = None, tags: t.Optional[list[str]] = None):
    """Create a network object in the Palo Alto API"""
    tags_set = set(tags) if tags else None
    with get_settings().get_api_connection() as api:
        api.network_create(name, netmask, description, tags=tags_set)
    logger.success(f"Created network '{name}' with netmask '{netmask}'")


@app.command()
def network_delete(name: str):
    """Delete a network object in the Palo Alto API"""
    with get_settings().get_api_connection() as api:
        api.network_delete(name)
    logger.success(f"Deleted network '{name}'")


@app.command()
def commit():
    """Commit changes to the Palo Alto API"""
    with get_settings().get_api_connection() as api:
        api.commit()
    logger.success("Changes committed")


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
