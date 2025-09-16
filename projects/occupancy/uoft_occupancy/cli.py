"""
Occupancy tracking
"""

from typing import Annotated, Optional
import sys
import typer
from uoft_core import logging
from collections import defaultdict
from sqlmodel import SQLModel, Session, create_engine
from . import Settings, Occupancy_Tracking, RawRecord
import json
import concurrent.futures

logger = logging.getLogger(__name__)

DEBUG_MODE = False


def _version_callback(value: bool):
    if not value:
        return
    from . import __version__
    import sys

    print(
        f"uoft-{Settings.Config.app_name} v{__version__} \nPython {sys.version_info.major}."
        f"{sys.version_info.minor} ({sys.executable}) on {sys.platform}"
    )
    raise typer.Exit()


app = typer.Typer(
    name="occupancy",
    context_settings={"max_content_width": 120, "help_option_names": ["-h", "--help"]},
    no_args_is_help=True,
    help=__doc__,  # Use this module's docstring as the main program help text
)


@app.callback()
@Settings.wrap_typer_command
def callback(
    version: Annotated[
        Optional[bool],
        typer.Option(
            "--version",
            callback=_version_callback,
            is_eager=True,
            help="Show version information and exit",
        ),
    ] = None,
    debug: bool = typer.Option(False, help="Turn on debug logging", envvar="DEBUG"),
    trace: bool = typer.Option(False, help="Turn on trace logging. implies --debug", envvar="TRACE"),
):
    global DEBUG_MODE
    log_level = "INFO"
    if debug:
        log_level = "DEBUG"
        DEBUG_MODE = True
    if trace:
        log_level = "TRACE"
        DEBUG_MODE = True
    logging.basicConfig(level=log_level)


def cli():
    try:
        # CLI code goes here
        app()
    except KeyboardInterrupt:
        print("Aborted!")
        sys.exit()
    except Exception as e:
        if DEBUG_MODE:
            raise
        logger.error(e)
        sys.exit(1)


@app.command()
def run_polls():
    data = get_data_raw_threaded()
    data = filter_data(data)
    data = count_data(data)
    write_to_db(data)


@app.command()
def show_groups():
    s = Settings().from_cache()
    for department in s.departments.values():
        for apgroup in department.apgroups:
            print(apgroup)


def get_data_raw(host):
    # region example data
    # {'AP name': '<AP_NAME>',
    #  'Age(d:h:m)': '00:00:06',
    #  'Auth': '802.1x',
    #  'Essid/Bssid/Phy': '<SSID>/0a:0a:0a:0a:0a:0a/5GHz-HE',
    #  'Forward mode': 'tunnel',
    #  'Host Name': None,
    #  'IP': '100.112.X.X' | '100.113.X.X' | '100.114.X.X'
    #  'MAC': '0a:0a:0a:0a:0a:0a',
    #  'Name': '<USERNAME>',
    #  'Profile': '<RADIUS_PROFILE',
    #  'Roaming': 'Wireless',
    #  'Role': 'authenticated',
    #  'Type': None,
    #  'User Type': 'WIRELESS',
    #  'VPN link': None}
    # endregion
    with host:
        res = host.showcommand("show user-table unique ip")["Users"]
    return res


def get_data_raw_threaded():
    s = Settings().from_cache()
    data = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(get_data_raw, host) for host in s.md_api_connections]
        for future in concurrent.futures.as_completed(futures):
            host_data = future.result()
            data.extend(host_data)
    return data


def filter_data(raw_data: list[RawRecord]):
    s = Settings().from_cache()
    unique_data = dict()
    for line in raw_data:
        for department in s.departments.values():
            for apgroup in department.apgroups.values():
                if line["AP name"] in apgroup:
                    name = line["Name"]
                    if not name:
                        continue
                    unique_data[name] = line
    return list(unique_data.values())


def count_data(unique_data: list[RawRecord]):
    s = Settings().from_cache()
    inverted_ap2g = defaultdict(list)
    tally = defaultdict(lambda: defaultdict(int))
    watermarks = defaultdict(lambda: defaultdict(str))
    for department in s.departments.values():
        watermarksd = defaultdict(int)
        for group, aps in department.apgroups.items():
            watermarks[group]["location"] = group
            for range in department.ranges:
                tally[group][range] = 0
            for watermark, value in department.watermarks.items():
                watermarksd[watermark] = value
            # create an inverted dictionary to compare against, ap : group
            for ap in aps:
                inverted_ap2g[ap].append(group)
            for client in unique_data:
                assert client["Name"]
                client_ap_name = client["AP name"]
                client_ip: str = client["IP"]
                client_name: str = client["Name"]
                client_role = client["Role"]
                # handle the @eduroam etc type usernames and strip down to username only / logon state
                if "@" in client_name and client_role != "logon":
                    client_name = client_name.partition("@")[0]
                # tally each of the range types for each user as well as a total unique user count
                for range_name, ip_prefix in s.filter_ranges.items():
                    # This range_name will look like "unique_student", ip_prefix looks like "100.112"
                    if client_ip.startswith(ip_prefix) and group in inverted_ap2g[client_ap_name]:
                        tally[group][range_name] += 1
                        tally[group]["unique_users"] += 1
                        # if the department has departmental users count and create a watermark for that
                        if client_name in department.departmental_users:
                            if watermarksd["Departmental_Users"] is None:
                                watermarksd["Departmental_Users"] = 0
                            watermarksd["Departmental_Users"] += 1
            watermarks[group]["watermarks"] = json.dumps(watermarksd)
            tally[group].update(watermarks[group])
    return tally


def write_to_db(tally: dict):
    s = Settings().from_cache()
    engine = create_engine(s.get_db_connection)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        for line in tally.values():
            session.add(Occupancy_Tracking(**line))
        session.commit()


def _debug():
    "Debugging function, only used in active debugging sessions."
    # pylint: disable=all
    run_polls()
