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
from .create_checkout import snipe_create_checkout

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


@app.command(help="Create an asset.")
def create_asset(mac_addr: str, name: str, serial: str):
    snipe_create_asset(mac_addr, name, serial)


@app.command(help="Checkout an asset.")
def checkout_asset(asset: int):
    snipe_checkout_asset(asset)


@app.command(help="Generage an asset label.")
def generate_label(asset: int):
    snipe_generate_label(asset)  # TODO MMMM


@app.command(help="Print the last generated label.")
def print_label():
    system_print_label()


@app.command(
    help="Single provision from INPUT.  Runs: create-asset, checkout-asset, generate-label, and print-label for the given asset provided."
)
def single_provision(mac_addr: str, name: str, serial: str):
    asset = snipe_create_checkout(mac_addr, name, serial)
    snipe_generate_label(asset)  # TODO MMMM
    system_print_label()


@app.command(
    help="Batch provisioning from FILE and INPUT.  Runs: create-asset, checkout-asset, generate-label, and print-label for each given asset name. Names are taken from file/interactive input, and Mac's/Serials are taken from interactive input, in pairs of two, typically scanned via barcode scanner."
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
    )
):
    if names_list.name == "-":
        print("Enter AP names, one per line. Press CTRL+D when complete.")
        names = sys.stdin.readlines()
    else:
        names = names_list.open().readlines()
    snipe_batch_provision(names)


def _debug():
    "Debugging function, only used in active debugging sessions."
    # pylint: disable=all
    app()
