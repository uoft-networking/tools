"""
Manage entries in the Station Manager (STM) / Blacklist Manager (BLMGR) blacklist database.
"""

import json

import typer

from .. import settings

app = typer.Typer(  # If run as main create a 'typer.Typer' app instance to run the program within.
    context_settings={"max_content_width": 120, "help_option_names": ["-h", "--help"]},
    no_args_is_help=True,
    help=__doc__,  # Use this module's docstring as the main program help text
    short_help="Aruba STM Blacklist Management Tools",
    add_completion=False,
)


@app.command()
def get(
    as_json: bool = typer.Option(
        False, help="Return the list of blacklisted MACs as JSON."
    )
):
    "Print out a list of all entries in the STM/BLMGR Blacklist"
    res = {}
    for c in settings().md_api_connections:
        with c:
            for entry in c.wlan.get_ap_client_blacklist():
                res[entry["STA"]] = entry

    if as_json:
        print(json.dumps(list(res.values()), indent=4))
    else:
        print(*res.values(), sep="\n")


@app.command()
def remove(ctx: typer.Context, mac_address: str):
    "Remove a MAC address from the STM/BLMGR Blacklist"
    with settings().mm_api_connection as c:
        c.wlan.blmgr_blacklist_remove(mac_address)
        c.controller.write_memory()

    print(f"Removed {mac_address} from the STM/BLMGR Blacklist")
    
@app.command()
def purge(ctx: typer.Context, mac_address: str):
    "Purge all entries from the STM/BLMGR Blacklist"
    with settings().mm_api_connection as c:
        c.wlan.blmgr_blacklist_purge()
        c.controller.write_memory()

    print(f"the STM/BLMGR Blacklist has been purged")


@app.command()
def add(
    ctx: typer.Context,
    mac_address: str,
):
    "Add a MAC address to the AP Client Blacklist"
    # stm endpoint on individual controllers does not support post operations
    # when those controllers are slaved to a mobility master. we need to use the blmgr endpoint
    # on the mobility master instead
    with settings().mm_api_connection as c:
        c.login()
        c.wlan.blmgr_blacklist_add(mac_address)
        c.controller.write_memory()
        c.logout()

    print("Added {mac_address} to the STM/BLMGR Blacklist")
