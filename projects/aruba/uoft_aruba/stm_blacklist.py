import json

import typer

from . import settings

app = typer.Typer(  # If run as main create a 'typer.Typer' app instance to run the program within.
    context_settings={"max_content_width": 120, "help_option_names": ["-h", "--help"]},
    no_args_is_help=True,
    help=__doc__,  # Use this module's docstring as the main program help text
    short_help="Aruba STM Blacklist Management Tools",
    add_completion=False,
)


@app.command()
def get():
    "Print out a list of all entries in the STM Blacklist across both controllers as JSON."
    res = []
    for c in settings().md_api_connections:
        with c:
            res.extend(c.stm_blacklist_get())
                
    print(json.dumps(res, indent=4))


@app.command()
def remove(ctx: typer.Context, mac_address: str):

    for c in settings().md_api_connections:
        with c:
            c.stm_blacklist_remove(mac_address)
            c.controller.write_memory()

    print("Done!")