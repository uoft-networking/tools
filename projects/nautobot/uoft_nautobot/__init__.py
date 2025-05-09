from importlib.metadata import version
import typing

from nautobot.apps import NautobotAppConfig
from uoft_core import BaseSettings, Field, SecretStr
from uoft_core.types import BaseModel
from uoft_aruba import Settings as ArubaSettings
from uoft_ssh import Settings as SSHSettingsBase, Credentials
from uoft_bluecat import Settings as BluecatSettings

# All of our projects are distributed as packages, so we can use the importlib.metadata 
# module to get the version of the package.
assert __package__
__version__ = version(__package__) # type: ignore

class SSHSettings(SSHSettingsBase):
    nautobot: Credentials = Field(
        description="Credentials for the Nautobot user, typically has read-only access."
    )


class LDAPSettings(BaseModel):
    server: str
    is_active_directory: bool = False
    cert_is_self_signed: bool = False
    bind_dn: str
    bind_password: SecretStr
    user_search_base: str = (
        "OU=UTORIDStaff,OU=Staff Users,DC=utscad,DC=utsc,DC=utoronto,DC=ca"
    )
    user_attribute_map: dict[str, str] = Field(
        default_factory=lambda: {
            "first_name": "givenName",
            "last_name": "sn",
            "email": "mail",
        }
    )
    group_search_base: str = "OU=Security Groups,DC=utscad,DC=utsc,DC=utoronto,DC=ca"


class KeycloakSettings(BaseModel):
    endpoint: str
    client_id: str
    client_secret: SecretStr
    public_key: str

    @property
    def authorization_url(self):
        return f"{self.endpoint}/protocol/openid-connect/auth"

    @property
    def access_token_url(self):
        return f"{self.endpoint}/protocol/openid-connect/token"


class Settings(BaseSettings):
    debug: bool = False
    allowed_hosts: list[str] = Field(default_factory=lambda: ["*"])
    secret_key: SecretStr
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "nautobot"
    db_user: str = "nautobot"
    db_password: SecretStr = SecretStr("")
    db_timeout: int = 300
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_username: str = ""
    redis_password: SecretStr = SecretStr("")
    redis_ssl: bool = False
    bluecat: BluecatSettings = Field(prompt=False)
    aruba: ArubaSettings = Field(prompt=False)
    ssh: SSHSettings = Field(prompt=False)
    nornir_timeout: int = 30
    gitlab_templates_username: str
    gitlab_templates_password: SecretStr
    gitlab_data_username: str
    gitlab_data_password: SecretStr
    groups_active: str = "GL_IITS_Users"
    groups_staff: str = "GL_SysNetAdmins"
    groups_superuser: str = "GL_SysNetAdmins"
    additional_groups: list[str] = Field(
        default_factory=lambda: [
            "GL_IITS_Helpdesk",
            "GL_IITS_Networking",
            "GL_IITS_Security",
            "GL_IITS_Systems",
        ]
    )
    ldap: LDAPSettings | None = Field(prompt=False)
    keycloak: KeycloakSettings | None = Field(prompt=False)

    class Config(BaseSettings.Config):
        app_name = "nautobot"
        prompt_on_missing_values = True

        @classmethod
        def parse_env_var(cls, field_name: str, raw_val: str):
            if field_name in {"allowed_hosts", "aruba_controllers"}:
                return raw_val.split(",")
            return cls.json_loads(raw_val)

    def get_db_connection(self):
        return f"postgresql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

    def get_redis_connection(self, database_number=0):
        scheme = "rediss" if self.redis_ssl else "redis"
        username = self.redis_username
        password = self.redis_password.get_secret_value()

        # Default Redis credentials to being empty unless a username or password is
        # provided. Then map it to "username:password@". We're not URL-encoding the
        # password because the Redis Python client already does this.
        creds = ""
        if username or password:
            creds = f"{username}:{password}@"

        return (
            f"{scheme}://{creds}{self.redis_host}:{self.redis_port}/{database_number}"
        )

    def all_groups(self):
        return {
            self.groups_active,
            self.groups_staff,
            self.groups_superuser,
            *self.additional_groups,
        }


class UofTPluginConfig(NautobotAppConfig):
    name = "uoft_nautobot"
    verbose_name = "UofT Nautobot Plugin"
    author = "Alex Tremblay"
    author_email = "alex.tremblay@utoronto.ca"
    version = __version__
    description = (
        "A Plugin containing all the extensions and customizations to Nautobot that the "
        "UofT networking teams need"
    )
    base_url = "uoft"
    min_version = "0.9"
    max_version = "9.0"
    middleware: typing.ClassVar = []
    installed_apps: typing.ClassVar = []
    default_settings: typing.ClassVar = {}


def print_config_path():
    from pathlib import Path

    print(Path(__file__).parent.joinpath("nautobot_config.py"))


config = UofTPluginConfig
