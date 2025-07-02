from importlib.metadata import version
from uoft_aruba.api import ArubaRESTAPIClient
from uoft_core import BaseSettings
from sqlmodel import SQLModel, Field
from datetime import datetime
from typing_extensions import TypedDict
from typing import Optional
from sqlalchemy import Column, JSON
from uoft_core.types import BaseModel, SecretStr

# All of our projects are distributed as packages, so we can use the importlib.metadata
# module to get the version of the package.
assert __package__
__version__ = version(__package__)  # type: ignore


RawRecord = TypedDict(
    "RawRecord",
    {
        "AP name": str,  # '<AP_NAME>'
        "Age(d:h:m)": str,  # '00:00:06'
        "Auth": Optional[str],  # '802.1x'
        "Essid/Bssid/Phy": str,  # '<SSID>/0a:0a:0a:0a:0a:0a/5GHz-HE'
        "Forward mode": str,  # 'tunnel'
        "Host Name": None,  # None
        "IP": str,  # '100.112.X.X' | '100.113.X.X' | '100.114.X.X'
        "MAC": str,  # '0a:0a:0a:0a:0a:0a'
        "Name": Optional[str],  # '<UTORID>'
        "Profile": str,  # '<RADIUS_PROFILE>'
        "Roaming": str,  # 'Wireless'
        "Role": str,  # 'authenticated'
        "Type": Optional[str],  # None
        "User Type": str,  # 'WIRELESS'
        "VPN link": None,  # None
    },
)


class Department(BaseModel):
    """This is what all Department models must look like.  Some fields are optional, some are not."""

    ### TODO: Clean source data in pass
    departmental_users: list[str]  # Optional
    watermarks: dict[str, int]  # Optional
    apgroups: dict[str, list[str]]  # Required
    ranges: list[str] # Required


class Occupancy_Tracking(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    timestamp: datetime = Field(default=datetime.now())
    location: str
    unique_student: int | None = 0
    unique_staff: int | None = 0
    unique_visitors: int | None = 0
    unique_users: int | None = 0
    watermarks: dict[str, int] = Field(default=None, sa_column=Column(JSON))


class Settings(BaseSettings):
    """Settings for the occupancy application."""

    psql_database: str = Field(
        title="PSQL Database name",
        description="The username used to manage the PSQL database.",
    )

    psql_host: str = Field(
        title="PSQL hostname",
        description="The hostname of the PSQL database.",
    )

    psql_user: str = Field(
        title="PSQL username",
        description="The username used to manage the PSQL database.",
    )

    psql_password: SecretStr = Field(
        title="PSQL database password",
        description="The password used to manage the PSQL database.",
    )

    psql_port: str = Field(
        title="PSQL database port",
        description="The port for the database on the host",
    )

    aruba_svc_account: str = Field(
        title="Aruba API Authentication Account",
        description="Account used to log into the API of Aruba 'Managed Devices'.",
    )

    aruba_svc_password: SecretStr = Field(
        title="Aruba API Authentication Password",
        description="Password used to log into the API of Aruba 'Managed Devices'.",
    )

    aruba_md_hostnames: list[str] = Field(
        title="Aruba Controller (Managed Device) IP Adresses / Hostnames",
        description="A list of Aruba MD names to query.",
    )

    aruba_default_config_path: str = Field(
        title="Aruba API Default Config Path",
        description="Default config path used for API requests of Aruba 'Managed Devices'.",
    )

    global_ranges: list[str] = Field(
        title="Global column ranges",
        description="List used in conjunction with unique users.",
    )

    filter_ranges: dict[str, str] = Field(
        title="Global filter ranges",
        description="Used to count unique users.",
    )

    departments: dict[str, Department] = Field(
        title="Departmental Models",
        description="Any number of departmental models can be created as long as they follow the class format defined.",
    )  # All departments must be models like the Department class at the top.

    @property
    def md_api_connections(self):
        return [
            ArubaRESTAPIClient(
                f"{host}:4343",
                self.aruba_svc_account,
                self.aruba_svc_password.get_secret_value(),
            )
            for host in self.aruba_md_hostnames
        ]

    @property
    def get_db_connection(self):
        return f"postgresql://{self.psql_user}:{self.psql_password.get_secret_value()}@{self.psql_host}:{self.psql_port}/{self.psql_database}"

    class Config(BaseSettings.Config):
        app_name = "occupancy"
