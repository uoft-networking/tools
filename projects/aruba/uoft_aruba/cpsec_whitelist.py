#!/usr/bin/env python3.10
# Author: Kyle Fozo, June 2022.  Big shoutout and Kudos to Alex Tremblay for all his help and mentorship along this journey!
#
# ***External to the required imports below, this script also requires the system to have PASS (https://www.passwordstore.org/),
# ***The service account password must be encrypted in it without an access password.
# ***Ensure that you set your own CONFIG PARAMETERS in the supplied .env file.
#

# Used for settings import from .env
from pydantic import BaseSettings

# Used for help and argument control
import typer

# used for sys.exit() and to obfuscate tracebacks.  use --debug if required.
import sys

# Used for mac address pattern patching
import re

# Used to simplify dealing with the Aruba API.
from uoft_core.aruba import ArubaRESTAPIClient

# used for shell interaction
from uoft_core import shell

# useful data types
from pathlib import Path

# a type alias to clean up code below
InputTable = list[tuple[str, str, str]]

# Supress traces, debug flag provided.
sys.tracebacklimit = 0


class Settings(BaseSettings):
    organizational_division: str = ""
    svc_account: str = ""
    mm_vrrp_hostname: str = ""
    md_vrrp_hostname: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
if not all(
    [
        settings.md_vrrp_hostname,
        settings.mm_vrrp_hostname,
        settings.svc_account,
        settings.organizational_division,
    ]
):
    raise Exception(f"Empty field(s) in .env! Configure your supplied .env file prior to the use of this tool!")


run = typer.Typer(  # If run as main create a 'typer.Typer' app instance to run the program within.
    no_args_is_help=True,
    help=f"Welcome to the Aruba CPSEC Whitelist Provisioning Tool for {settings.organizational_division}.\n\n \n\nThe Aruba wireless system at {settings.organizational_division} utilizes the 'Control Plane Security' (CPSEC) 'Whitelist Database' (WDB) to authorize and provision WAPs onto the Aruba Wireless Platform.  This is done by generating certificates for each WAP we will bring online within the CPSEC WDB.\n\n \n\nThis tool has been designed to automate single or batch provisioning of WAPs into the CPSEC WDB, as well as modifying their certs to 'factory-approved' so the registrations do not expire.\n\n \n\nYou will require a valid, configured, AP_GROUP along with a MAC_ADDRESS and AP_NAME to be provisioned.\n\n \n\nRun commands without arguemnts for HELP information, or add the --help option after any command for more information and format requirements.",
    add_completion=False,
)


provision = typer.Typer()
run.add_typer(  # Create the 'provision' subcommand within typer.
    provision,
    name="provision",
    help="This command is used to single or batch provision new Aruba WAPs into the CPSEC WDB and modify theirs certs to 'factory-approved' so that they do not expire.  Read the specific HELP entries first as input must be escaped in certain situations.",
    no_args_is_help=True,
)


@run.command()
def Get_AP_Groups(  # Create the 'get-ap-groups' command within typer.
    debug: bool = typer.Option(False, help="Turn on debug logging"),
):
    "Returns a list of valid AP_GROUPs and exits."
    try:
        passwd = shell(f"pass show {settings.svc_account}")
        with (ArubaRESTAPIClient(f"{settings.md_vrrp_hostname}:4343", f"{settings.svc_account}", passwd) as host1):
            raw_controller_ap_groups = host1.wlan.get_ap_groups()["_data"]["ap_group"]
            controller_ap_groups = []
            for raw_controller_ap_group in raw_controller_ap_groups:
                controller_ap_groups.append(raw_controller_ap_group["profile-name"].rpartition("'")[2])
            print(f"Below you will find a list of valid AP_GROUPs to use in your input:\n")
            print(*controller_ap_groups, sep="\n")
            sys.exit()
    except Exception as error:
        if debug:
            raise error
        else:
            print(f"Error!: {error}")


@provision.command(  # Create the 'from-file' subcommand within 'provision'.
    no_args_is_help=True,
    short_help=f"READ THE FROM-CLI HELP BEFORE USE! ... from-cli --help\n\nProvisions a CSV list of MAC_ADDRESS,AP_GROUP,AP_NAME's, one per line.",
)
def From_File(
    filename: Path,
    debug: bool = typer.Option(False, help="Turn on debug logging"),
) -> InputTable:
    """FILENAME must be a CSV file of WAP instances, one per line, formatted as such:\n
    MAC_ADDRESS,AP_GROUP,AP_NAME\n
    MAC_ADDRESS,AP_GROUP,AP_NAME\n\n\n
    Note that my example AP_GROUP is "-CC Lab" with a space.  This does -not- need to be escaped when you are importing from CSV.\n\n\n
    Example:\n
    00:01:10:12:02:21,-CC Lab,test_ap_name_18\n
    00:01:02:12:02:21,-CC Lab,test_ap_name_19\n
    """
    try:
        input_WAPs = Read_From_File(filename)
        Verify_And_Create(input_WAPs)
    except Exception as error:
        if debug:
            raise error
        else:
            print(f"Error!: {error}")


@provision.command(  # Create the 'from-cli' subcommand within 'provision'.
    no_args_is_help=True,
    short_help="READ THE FROM-CLI HELP BEFORE USE! ... from-cli --help\n\nProvisions a single WAP comprised of a single \escaped\ MAC_ADDRESS,AP_GROUP,AP_NAME entry, from cli.",
)
def From_CLI(
    input: list[str],
    debug: bool = typer.Option(False, help="Turn on debug logging"),
):
    """INPUT must be a single WAP instance formattted as such:\n
    MAC_ADDRESS,AP_GROUP,AP_NAME\n\n\n
    Note that my example AP_GROUP is "-CC Lab" with a space.  This -does- need to be escaped when you are inputting from CLI.\n\n\n
    Example:\n
    00:01:00:12:02:21,-CC\ Lab,test_ap_name_16\n
    """
    try:
        input_WAPs = Read_From_CLI(input)
        Verify_And_Create(input_WAPs)
    except Exception as error:
        if debug:
            raise error
        else:
            print(f"Error!: {error}")


def Read_From_CLI(input_table: list[str]) -> InputTable:
    "Reads a single 'MAC_ADDRESS,AP_GROUP,AP_NAME' entry from cli."
    response = []
    for line in input_table:
        items = line.split(",")
        # confirm we only have 3 fields in CSV and split into list 'items'
        assert len(items) == 3, f"Error in input {line} has more than three fields."
        response.append(tuple(items))
    return response


def Read_From_File(filename: Path) -> InputTable:
    "Reads a CSV list of 'MAC_ADDRESS,AP_GROUP,AP_NAME's, one per line."
    response = []
    for line in filename.read_text().splitlines():
        items = line.split(",")
        # confirm we only have 3 fields in CSV and split into list 'items'
        assert len(items) == 3, f"Error in input {line} has more than three fields."
        response.append(tuple(items))
    return response


def Verify_And_Create(input_table: InputTable):
    "Verifies input data for script, and then creates entries in CPSEC Whitelist."
    outer_lambda = lambda row: tuple(map(lambda item: item[:75], row))
    input_table = list(map(outer_lambda, input_table))
    # Lambda prevent input overflow.
    passwd = shell(f"pass show {settings.svc_account}")
    # All passwords are stored in a gpg encrypted file and accessed through pass.  No passwords are EVER in scripts.
    with (ArubaRESTAPIClient(f"{settings.md_vrrp_hostname}:4343", f"{settings.svc_account}", passwd) as host1):
        Check_Input_Groups(host1, input_table)  # Confirm input AP_GROUPs exist on MM
    with (ArubaRESTAPIClient(f"{settings.mm_vrrp_hostname}:4343", f"{settings.svc_account}", passwd) as host2):
        Check_Input_Names_Macs(host2, input_table)  # Confirm mac format / names or macs not already in use on MM.
        Create_Whitelist_Entry_CPSEC_And_Approve(host2, input_table)


def Check_Input_Groups(host: ArubaRESTAPIClient, input_table: InputTable):
    "Verifies input AP_GROUPs data for script, returns an error if an input AP_GROUP does not exist on Managed Device."
    raw_controller_ap_groups = host.wlan.get_ap_groups()["_data"]["ap_group"]
    controller_ap_groups = []
    group_assertion_list = []
    for raw_controller_ap_group in raw_controller_ap_groups:
        controller_ap_groups.append(raw_controller_ap_group["profile-name"].rpartition("'")[2])
    input_ap_groups = [line[1] for line in input_table]
    for input_ap_group in input_ap_groups:
        if input_ap_group not in controller_ap_groups:
            group_assertion_list.append(input_ap_group)
        else:
            print(f"Verifying Input AP_GROUP '{input_ap_group}' is valid...GOOD")
    assert (
        len(group_assertion_list) == 0
    ), f"The following AP_GROUP(s) are -not- configured on the controller!\n '{group_assertion_list}'\nConfirm input!  Run --help for help."


def Check_Input_Names_Macs(host: ArubaRESTAPIClient, input_table: InputTable):
    "Verifies input AP_NAMEs and MAC_ADDRESSes data for script, returns an error if an input AP_NAME or MAC_ADDRESS already exists in CPSEC Whitelist."
    raw_controller_ap_names_macs = host.showcommand("show whitelist-db cpsec")[
        "Control-Plane Security Whitelist-entry Details"
    ]
    controller_ap_names = []
    controller_ap_macs = []
    name_assertion_list = []
    mac_assertion_list = []
    for raw_ap_name in raw_controller_ap_names_macs:
        controller_ap_names.append(raw_ap_name["AP-Name"])
    input_ap_names = [line[2] for line in input_table]
    for input_ap_name in input_ap_names:
        if input_ap_name in controller_ap_names:
            name_assertion_list.append(input_ap_name)
        else:
            print(f"Verifying Input AP_NAME {input_ap_name} is not in use...GOOD")
    assert (
        len(name_assertion_list) == 0
    ), f"The following AP_NAME(s) are already in use on the controller!\n '{name_assertion_list}'\nConfirm input!  Run --help for help."
    for raw_ap_mac in raw_controller_ap_names_macs:
        controller_ap_macs.append(raw_ap_mac["MAC-Address"])
    input_mac_addresses = [line[0] for line in input_table]
    for input_ap_mac in input_mac_addresses:
        mac_address_validate_pattern = "^(?:[0-9A-Fa-f]{2}[:-]){5}(?:[0-9A-Fa-f]{2})$"
        match = re.match(mac_address_validate_pattern, input_ap_mac)
        if match:
            print(f"Verifying fotmat of input MAC_ADDRESS {input_ap_mac} ...GOOD")
        else:
            raise Exception(f"Mac address format incorrect for {input_ap_mac}")
        if input_ap_mac in controller_ap_macs:
            mac_assertion_list.append(input_ap_mac)
    assert (
        len(mac_assertion_list) == 0
    ), f"The following MAC_ADDRESS(es) are already in use on the controller!\n '{mac_assertion_list}'\nConfirm input!  Run --help for help."


def Create_Whitelist_Entry_CPSEC_And_Approve(host: ArubaRESTAPIClient, input_table: InputTable):
    "Creates the CPSEC Whitelist entries, and then modifies this certificate types to 'factory-approved'."
    for line in input_table:
        input_mac_address, input_ap_group, input_ap_name = line
        host.ap_provisioning.wdb_cpsec_add_mac(input_mac_address, input_ap_group, input_ap_name)
        print(
            f"Added new CPSEC whitelist entry for {input_ap_name} / {input_mac_address}"
        )  # Create a CPSEC whitelist entry, for each WAP in the supplied file.
        host.ap_provisioning.wdb_cpsec_modify_mac_factory_approved(input_mac_address)
        print(
            f"Modified CPSEC entry for {input_ap_name} / {input_mac_address} to factory_approved"
        )  # Modify a CPSEC whitelist entry to have a permanent factory-approved certifiacte, for each WAP in the supplied file.


# Is only run if script run directly, otherwise allows for import.
if __name__ == "__main__":
    run()
