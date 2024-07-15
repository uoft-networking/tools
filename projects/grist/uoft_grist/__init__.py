from uoft_aruba.api import ArubaRESTAPIClient
from uoft_core import BaseSettings, Field
from uoft_core.types import SecretStr, BaseModel
from importlib.metadata import version


# All of our projects are distributed as packages, so we can use the importlib.metadata 
# module to get the version of the package.
__version__ = version(__package__) # type: ignore


class Department(BaseModel):
    """This is what all Department models must look like.  Some fields are optional, some are not."""

    docid: str  # Required
    departmental_users: list[str]  # Optional
    ranges: list[str]  # Required
    watermarks: dict[str, str]  # Optional
    apgroups: dict[str, list[str]]  # Required


class Settings(BaseSettings):
    """Settings for the grist application."""

    grist_api_key: SecretStr = Field(
        title="Grist API Authentication Key",
        description="A key used to authenticate to the Grist API.",
    )

    grist_server: str = Field(
        title="Grist server IP/PORT",
        description="grist server 'http://<hostname>:8484'.",
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

    filter_ranges: dict = Field(
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

    class Config(BaseSettings.Config):
        app_name = "grist"
