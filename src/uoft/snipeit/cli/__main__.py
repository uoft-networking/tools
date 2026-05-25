"""
Collection of tools to interact with SnipeIT, currently focused around Access Point provisiong, but will probably be expanded to support all asset types in general.
"""

from pathlib import Path
import sys
import typer
from typing import Annotated, Optional

from uoft_core import logging
from . import Settings
from .create import snipe_create_asset
from .checkout import snipe_checkout_asset
from .generate import generate_label as snipe_generate_label
from .print import system_print_label
from .batch import snipe_batch_provision
from .serial_lookup import snipe_serial_lookup
from .location_lookup import snipe_location_lookup

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
    name="snipeit",
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
def create_asset(mac_addr: str, name: str, serial: str, model_id: int = 138):
    "Create an asset."
    snipe_create_asset(mac_addr, name, serial, model_id)


@app.command()
def checkout_asset(
    asset: int,
    location_id: int = typer.Option(None),
    name: str = typer.Option(None),
):
    "Checkout an asset."
    snipe_checkout_asset(asset, location_id, name)


@app.command()
def generate_label(asset: int):
    "Generage an asset label."
    snipe_generate_label(asset)


@app.command()
def print_label():
    "Print the last generated label."
    system_print_label()


@app.command()
def single_provision(
    mac_addr: str,
    name: str,
    serial: str,
    model_id: int = 138,
    location_id: int = typer.Option(None),
):
    """Single provision from INPUT.

    Runs: create-asset, checkout-asset, generate-label, and print-label for the
    given asset provided.
    """
    asset = snipe_create_asset(mac_addr, name, serial, model_id)
    snipe_checkout_asset(asset, location_id, name)
    snipe_generate_label(asset)
    system_print_label()


@app.command()
def batch_provision(
    names_list: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        resolve_path=True,
        allow_dash=True,
    ),
    model_id: int = 138,
):
    """Batch provisioning from FILE and INPUT.

    Runs: create-asset, checkout-asset, generate-label, and print-label for each
    given asset name. Names are taken from file/interactive input, and Mac's/Serials
    are taken from interactive input, in pairs of two, typically scanned via
    barcode scanner.

    If FILE is a single dash (ex. '-'), data will be read from stdin.

    -Note the current default model-id is for an Aruba AP 535, supply the
    --model-id option as an argument along with a different model-id if required.
    """
    if names_list.name == "-":
        print("Enter AP names, one per line. Press CTRL+D when complete.")
        names = sys.stdin.readlines()
    else:
        names = names_list.open().readlines()
    snipe_batch_provision(names, model_id)


@app.command()
def asset_id_lookup(serial):
    "Returns the asset_id of a given serial."
    snipe_serial_lookup(serial)


@app.command()
def location_id_lookup(building_code):
    "Returns the location_id of a given building code."
    snipe_location_lookup(building_code)


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
