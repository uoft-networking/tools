"""
Collection of tools to interact with SnipeIT, currently focused around Access Point provisiong, but will probably be expanded to support all asset types in general.
"""

from pathlib import Path
import sys
import typer
from . import Settings
from .create import snipe_create_asset
from .checkout import snipe_checkout_asset
from .generate import generate_label as snipe_generate_label
from .print import system_print_label
from .batch import snipe_batch_provision
from .serial_lookup import snipe_serial_lookup
from .location_lookup import snipe_location_lookup

app = typer.Typer(
    name="snipeit",
    context_settings={"max_content_width": 120, "help_option_names": ["-h", "--help"]},
    no_args_is_help=True,
    help=__doc__,  # Use this module's docstring as the main program help text
)


@app.callback()
@Settings.wrap_typer_command
def callback():
    pass


@app.command(help="Create an asset.", no_args_is_help=True)
def create_asset(mac_addr: str, name: str, serial: str, model_id: int = 138):
    snipe_create_asset(mac_addr, name, serial, model_id)


@app.command(help="Checkout an asset.", no_args_is_help=True)
def checkout_asset(asset: int, location_id: int = typer.Option(None), name: str = typer.Option(None)):
    snipe_checkout_asset(asset, location_id, name)


@app.command(help="Generage an asset label.", no_args_is_help=True)
def generate_label(asset: int):
    snipe_generate_label(asset)


@app.command(help="Print the last generated label.")
def print_label():
    system_print_label()


@app.command(
    help="Single provision from INPUT.  Runs: create-asset, checkout-asset, generate-label, and print-label for the given asset provided.",
    no_args_is_help=True,
)
def single_provision(
    mac_addr: str, name: str, serial: str, model_id: int = 138, location_id: int = typer.Option(None)
):
    asset = snipe_create_asset(mac_addr, name, serial, model_id)
    snipe_checkout_asset(asset, location_id, name)
    snipe_generate_label(asset)
    system_print_label()


@app.command(
    help="Batch provisioning from FILE and INPUT.  Runs: create-asset, checkout-asset, generate-label, and print-label for each given asset name. Names are taken from file/interactive input, and Mac's/Serials are taken from interactive input, in pairs of two, typically scanned via barcode scanner.\n\nIf FILE is a single dash (ex. '-'), data will be read from stdin.\n\n-Note the current default model-id is for an Aruba AP 535, supply the --model-id option as an argument along with a different model-id if required.",
    no_args_is_help=True,
)
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
    if names_list.name == "-":
        print("Enter AP names, one per line. Press CTRL+D when complete.")
        names = sys.stdin.readlines()
    else:
        names = names_list.open().readlines()
    snipe_batch_provision(names, model_id)


@app.command(
    help="Returns the asset_id of a given serial.",
    no_args_is_help=True,
)
def asset_id_lookup(serial):
    snipe_serial_lookup(serial)


@app.command(
    help="Returns the location_id of a given building code.",
    no_args_is_help=True,
)
def location_id_lookup(building_code):
    snipe_location_lookup(building_code)


def _debug():
    "Debugging function, only used in active debugging sessions."
    # pylint: disable=all
    app()
