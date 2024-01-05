"""
Welcome to the Aruba CPSEC Whitelist Provisioning Tool.

The Aruba wireless system utilizes the 'Control Plane Security' (CPSEC) 'Whitelist Database' (WDB) 
to authorize and provision WAPs onto the Aruba Wireless Platform. 
This is done by generating certificates for each WAP we will bring online within the CPSEC WDB.

This tool has been designed to automate single or batch provisioning of WAPs into the CPSEC WDB, 
as well as modifying their certs to 'factory-approved' so the registrations do not expire.

"""

import typer
import sys
import csv
import io
from pathlib import Path
from .. import Settings, batch

run = typer.Typer(  # If run as main create a 'typer.Typer' app instance to run the program within.
    context_settings={"max_content_width": 120, "help_option_names": ["-h", "--help"]},
    no_args_is_help=True,
    help=__doc__,  # Use this module's docstring as the main program help text
    short_help="Aruba CPSEC Whitelist Provisioning Tool",
)


@run.command()
def get_ap_groups():  # Create the 'get-ap-groups' command within typer.
    "Returns a list of valid AP_GROUPs and exits."
    s = Settings.from_cache()
    with s.mm_api_connection as host:
        raw_controller_ap_groups = host.wlan.get_ap_groups()
        controller_ap_groups = []
        for raw_controller_ap_group in raw_controller_ap_groups:
            controller_ap_groups.append(
                raw_controller_ap_group["profile-name"].rpartition("'")[2]
            )
        s.util.console.print(
            "Below you will find a list of valid AP_GROUPs to use in your input:"
        )
        print(*controller_ap_groups, sep="\n")


@run.command(  # Create the 'from-file' subcommand within 'provision'.
    short_help="Provisions a CSV list of MAC_ADDRESS,AP_GROUP,AP_NAME's, one per line.",
)
def provision(
    filename: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        resolve_path=True,
        allow_dash=True,
    ),
):
    """
    Provision a list of APs using information from a provided CSV file.
    Each row in the CSV file represents an AP to be provisioned.
    The CSV file must consist of 3 columns: MAC_ADDRESS, AP_GROUP, and AP_NAME.
    The CSV file must not contain a header row.\n

    If FILENAME is a single dash (ex. "-"), data will be read from stdin.\n\n

    Note that my example AP_GROUP is "-CC Lab" with a space.
    This does -not- need to be escaped when you are importing from CSV.
    Example:
    Given a file names `my_aps.csv` with the following contents:\n
    00:01:10:12:02:21,-CC Lab,test_ap_name_18\n
    00:01:02:12:02:21,-CC Lab,test_ap_name_19
    """
    s = Settings.from_cache()
    if filename.name == "-":
        if sys.stdin.isatty():
            s.util.console.print(
                """Please enter AP details to be provisioned, one per line. Press CTRL+D when complete.\nMAC_ADDRESS,AP_GROUP,AP_NAME"""
            )
        file = io.StringIO(sys.stdin.read())

    else:
        file = filename.open()

    csv_format = csv.Sniffer().sniff(file.read(1024)) or csv.excel
    file.seek(0)

    reader = csv.reader(file, csv_format)
    aps_list = [
        (ap_name, ap_group, mac_address)
        for mac_address, ap_group, ap_name, *_ in reader
    ]
    results = batch.Provisioner(dry_run=True).provision_aps(aps_list)
    failed_aps = [ap for ap in results if isinstance(ap, Exception)]

    if failed_aps:
        s.util.console.print("The following APs failed to provision:\nMAC_ADDRESS,AP_GROUP,AP_NAME,REASON")
        for ap_error in failed_aps:
            s.util.console.print(
                f"{ap_error.ap.mac_address},{ap_error.ap.group},{ap_error.ap.name},{ap_error.args[0]}"
            )


def _debug():
    "Debugging function, only used in active debugging sessions."
    # pylint: disable=all
    run()
