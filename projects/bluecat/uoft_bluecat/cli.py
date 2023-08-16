"""
CLI and API to manage a Bluecat instance
"""
import sys
from pathlib import Path
from csv import DictReader, Sniffer

import typer

from . import Settings

app = typer.Typer(
    name="bluecat",
    context_settings={"max_content_width": 120, "help_option_names": ["-h", "--help"]},
    no_args_is_help=True,
    help=__doc__,  # Use this module's docstring as the main program help text
)


@app.callback()
@Settings.wrap_typer_command
def callback():
    s = Settings.from_cache()


@app.command()
def register_ips_from_file(
    filename: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        resolve_path=True,
        allow_dash=True,
    )
):
    if filename.name == "-":
        file = sys.stdin.readlines()
    else:
        file = filename.open().readlines()
    dialect = Sniffer().sniff(
        file[0]
    )  # figure out if the file is a csv, or a tsv, or whatever
    reader = DictReader(file, dialect=dialect)

    api = Settings.from_cache().get_api_connection()
    conf_id = api.get_configuration()["id"]
    for row in reader:
        mac = row['mac-address']
        ip = row['ipv4']
        res = api.get_ipv4_address(ip, configuration_id=conf_id)
        if res:
            print(f"IP {ip} already registered to Bluecat Object ID: {res['id']}")
            continue
        res = api.assign_ipv4_address(ip, mac, row['hostname'], configuration_id=conf_id)
        print(f"Successfully registered MAC {mac} with address {ip} to Bluecat Object ID: {res}")


def _debug():
    "Debugging function, only used in active debugging sessions."
    # pylint: disable=all
    app()
