import typer
import pprint
from .. import settings

run = typer.Typer(  # If run as main create a 'typer.Typer' app instance to run the program within.
    context_settings={"max_content_width": 120, "help_option_names": ["-h", "--help"]},
    no_args_is_help=True,
    help=__doc__,  # Use this module's docstring as the main program help text
    short_help="Aruba AP List Tool",
    add_completion=False,
)


@run.command()
def List_APs():
    s = settings()
    with s.mm_api_connection as host:
        output = host.showcommand("show whitelist-db cpsec")[
        "Control-Plane Security Allowlist-entry Details"
    ]
        pprint.pprint(output)
