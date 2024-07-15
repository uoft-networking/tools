"""
UofT Grist - Utilization Reporting
"""
from typing import Annotated, Optional
from collections import defaultdict
import datetime
import sys
from grist_api import GristDocAPI
import typer
from . import Settings, Department
from uoft_core import logging

logger = logging.getLogger(__name__)

app = typer.Typer(
    name="grist",
    context_settings={"max_content_width": 120, "help_option_names": ["-h", "--help"]},
    no_args_is_help=True,
    help=__doc__,  # Use this module's docstring as the main program help text
)


def version_callback(value: bool):
    if value:
        from . import __version__
        from sys import version_info as v, platform, executable

        print(
            f"uoft-grist v{__version__} \nPython {v.major}.{v.minor} ({executable}) on {platform}"
        )
        raise typer.Exit()


@app.callback()
def callback(
    debug: bool = typer.Option(False, help="Turn on debug logging", envvar="DEBUG"),
    trace: bool = typer.Option(False, help="Turn on trace logging. implies --debug", envvar="TRACE"),
):
    log_level = "INFO"
    if debug:
        log_level = "DEBUG"
    logging.basicConfig(level=log_level)


def cli():
    try:
        app()
    except KeyboardInterrupt:
        print("Aborted!")
        sys.exit()


@app.command()
def run_polls():
    upload_to_grist(count_data(filter_data(get_data_raw())))


@app.command()
def show_groups():
    s = Settings().from_cache()
    for departments in s.departments:
            print(departments, s.departments[departments], end="\n\n")


@app.command()
def clean_databases():
    clean()


def get_data_raw():
    s = Settings().from_cache()
    raw_data = []
    try:
        for host in s.md_api_connections:
            with host:
                raw_data.extend(host.showcommand("show user-table unique ip")["Users"])
    except Exception:
        logger.exception("Cannot source data.")
        sys.exit()
    return raw_data


def filter_data(raw_data):  ### Make this per AP in the future.
    unique_data = defaultdict()
    for line in raw_data:
        name = line["Name"]
        unique_data[name] = line
    unique_data = list(unique_data.values())
    return unique_data


def count_data(unique_data):
    s = Settings().from_cache()
    tally = defaultdict(lambda: defaultdict(int))
    inverteds = defaultdict(list)
    for department in s.departments.values():
        for group_name in department.apgroups:
            if department.departmental_users is not None:
                tally[group_name]["Departmental_Users"] += 0
        ap_groups = department.apgroups
        for group, aps in ap_groups.items():
            tally[group]["Unique_Users"] += 0
            for ap in aps:
                inverteds[ap].append(group)
            for client in unique_data:
                client_ap_name = client["AP name"]
                client_ip: str = client["IP"]
                client_name: str = client["Name"]
                if client_name is None:
                    continue
                client_role = client["Role"]
                if "@" in client_name and client_role != "logon":
                    client_name = client_name.partition("@")[0]
                for range_name, ip_prefix in s.filter_ranges.items():
                    # This range_name will look like "unique_student", ip_prefix looks like "100.112"
                    if (
                        client_ip.startswith(ip_prefix)
                        and group in inverteds[client_ap_name]
                    ):
                        tally[group][range_name] += 1
                        tally[group]["Unique_Users"] += 1
                        if client_name in department.departmental_users:
                            tally[group]["Departmental_Users"] += 1
    return tally


def upload_to_grist(tally: dict):
    s = Settings.from_cache()
    for department in s.departments.values():
        add_records_to_table(
            tally,
            department,
        )


def add_records_to_table(
    tally,
    department: Department,
):
    s = Settings.from_cache()
    grist = GristDocAPI(
        department.docid,
        server=s.grist_server,
        api_key=s.grist_api_key.get_secret_value(),
    )
    for group_name in department.apgroups:
        table_name = group_name.capitalize()
        tables = None
        try:
            tables = grist.call("tables")
        except Exception:
            print("Cannot call Grist table for dept")
            continue
        assert tables is not None
        tables = tables["tables"]
        table_ids = [t["id"] for t in tables]
        watermark_columns = []
        record: dict[str, str | int] = {
            "Date": datetime.datetime.now().strftime("%Y/%m/%d %H:%M")
        }
        watermark_columns.append(dict(id="Date", fields=[]))
        for range in s.global_ranges:
            if range in department.ranges:
                count = tally[group_name][range]
                record[range] = str(count)
                watermark_columns.append(dict(id=range, fields={"type": "Int"}))
        record["Unique_Users"] = str(tally[group_name]["Unique_Users"])
        watermark_columns.append(dict(id="Unique_Users", fields={"type": "Int"}))
        if (
            "Departmental_Users" in tally[group_name]
            and len(department.departmental_users) != 0
        ):
            record["Departmental_Users"] = str(tally[group_name]["Departmental_Users"])
            watermark_columns.append(
                dict(id="Departmental_Users", fields={"type": "Int"})
            )
        for watermark in department.watermarks.items():
            key, field = watermark
            watermark_columns.append(dict(id=key, fields={"type": "Int"}))
            record[key] = field
        if table_name not in table_ids:
            try:
                grist.call(
                    "tables",
                    dict(
                        tables=[
                            dict(
                                id=table_name,
                                columns=watermark_columns,
                            )
                        ]
                    ),
                )
            except Exception:
                print("Cannot call tables")
                continue
        try:
            grist.add_records(
                table_name,
                [record],
            )
        except Exception:
            print("Cannot add records")
            continue


def clean():
    s = Settings().from_cache()
    today = datetime.datetime.today()
    days_30_ago = today - datetime.timedelta(days=30)
    for department in s.departments.values():
        grist = GristDocAPI(
            department.docid,
            server=s.grist_server,
            api_key=s.grist_api_key.get_secret_value(),
        )
        for group_name in department.apgroups:
            table_name = group_name.capitalize()
            tables = grist.call("tables")
            tables = tables["tables"]  # type:ignore
            for table in tables:
                table_name = table["id"]
                if table_name == "Landing_Page":
                    continue
                values = grist.fetch_table(table_name)
                for value in values:
                    date = datetime.datetime.strptime(value[2], "%Y/%m/%d %H:%M")
                    if date < days_30_ago:
                        value_int = []
                        value_int.append(value.id)
                        try:
                            grist.delete_records(table_name, value_int)
                        except Exception:
                            continue


def _debug():
    "Debugging function, only used in active debugging sessions."
    # pylint: disable=all
    s = Settings.from_cache()
    cli()
    # clean_databases()
