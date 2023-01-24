from uoft_core import BaseSettings, Field, root_validator
from uoft_aruba.api import ArubaRESTAPIClient
from pydantic.types import SecretStr


class Settings(BaseSettings):
    svc_account: str = Field(title="Aruba API Authentication Account")
    mm_vrrp_hostname: str = Field(
        title="Aruba Mobility Master Primary IP Adress / Hostname"
    )
    md_hostnames: list[str] = Field(
        title="Aruba Controller (Managed Device) IP Adresses / Hostnames"
    )

    password: SecretStr = Field(
        title="Aruba API Authentication Password",
        description="Password used to authenticate to the Aruba API.",
    )

    default_config_path: str = Field(
        "/md",
        title="Aruba API Default Config Path",
        description="Default config path used for API requests. Ex /md or /md/UTSC"
    )

    @root_validator(pre=True)
    def _catch_deprecated_configs(cls, values):  # pylint: disable=no-self-argument
        if "md_vrrp_hostname" in values:
            raise DeprecationWarning(
                "md_vrrp_hostname is deprecated. "
                "Please update your config files to use a list called 'mm_hostnames' instead. "
                "Please check one of the following config files for the deprecated config and update it: {}".format(
                    cls._util().config.readable_files
                )
            )
        return values

    @property
    def md_api_connections(self):
        return [
            ArubaRESTAPIClient(
                f"{host}:4343", self.svc_account, self.password.get_secret_value()
            )
            for host in self.md_hostnames
        ]

    @property
    def mm_api_connection(self):
        return ArubaRESTAPIClient(
            f"{self.mm_vrrp_hostname}:4343",
            self.svc_account,
            self.password.get_secret_value(),
            self.default_config_path
        )

    class Config(BaseSettings.Config):
        app_name = "aruba"


def settings() -> Settings:
    return Settings.from_cache()  # pylint: disable=protected-access
