"""
Manage entries in the Station Manager (STM) / Blocklist Manager (BLMGR) blocklist database.
"""

import json

import typer

from .. import settings

app = typer.Typer(  # If run as main create a 'typer.Typer' app instance to run the program within.
    context_settings={"max_content_width": 120, "help_option_names": ["-h", "--help"]},
    no_args_is_help=True,
    help=__doc__,  # Use this module's docstring as the main program help text
    short_help="Aruba STM Blocklist Management Tools",
    add_completion=False,
)


@app.command()
def get(
    as_json: bool = typer.Option(
        False, help="Return the list of blocklisted MACs as JSON."
    )
):
    "Print out a list of all entries in the STM/BLMGR Blocklist"
    res = {}
    for c in settings().md_api_connections:
        with c:
            for entry in c.wlan.get_ap_client_blocklist():
                res[entry["STA"]] = entry

    if as_json:
        print(json.dumps(list(res.values()), indent=4))
    else:
        print(*res.values(), sep="\n")


@app.command()
def remove(ctx: typer.Context, mac_address: str):
    "Remove a MAC address from the STM/BLMGR Blocklist"
    with settings().mm_api_connection as c:
        c.wlan.blmgr_blocklist_remove(mac_address)
        c.controller.write_memory()

    print(f"Removed {mac_address} from the STM/BLMGR Blocklist")


@app.command()
def purge(ctx: typer.Context):
    "Purge all entries from the STM/BLMGR Blocklist"
    with settings().mm_api_connection as c:
        c.wlan.blmgr_blocklist_purge()
        c.controller.write_memory()

    print("the STM/BLMGR Blocklist has been purged")


@app.command()
def add(
    ctx: typer.Context,
    mac_address: str,
):
    "Add a MAC address to the AP Client Blocklist"
    # stm endpoint on individual controllers does not support post operations
    # when those controllers are slaved to a mobility master. we need to use the blmgr endpoint
    # on the mobility master instead
    with settings().mm_api_connection as c:
        c.login()
        c.wlan.blmgr_blocklist_add(mac_address)
        c.controller.write_memory()
        c.logout()

    print(f"Added {mac_address} to the STM/BLMGR Blocklist")
