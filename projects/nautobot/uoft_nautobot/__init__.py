from importlib import metadata
from uoft_core import BaseSettings, Field, SecretStr
from uoft_aruba import Settings as ArubaSettings
from uoft_ssh import Settings as SSHSettingsBase, Credentials
from uoft_bluecat import Settings as BluecatSettings

__version__ = metadata.version(__name__)


from nautobot.apps import NautobotAppConfig


class SSHSettings(SSHSettingsBase):
    nautobot: Credentials = Field(description="Credentials for the Nautobot user, typically has read-only access.")


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
    ldap_server: str
    ldap_is_active_directory: bool = False
    ldap_cert_is_self_signed: bool = False
    ldap_bind_dn: str
    ldap_bind_password: SecretStr
    ldap_user_search_base: str = (
        "OU=UTORIDStaff,OU=Staff Users,DC=utscad,DC=utsc,DC=utoronto,DC=ca"
    )
    ldap_user_attribute_map: dict[str, str] = Field(
        default_factory=lambda: {
            "first_name": "givenName",
            "last_name": "sn",
            "email": "mail",
        }
    )
    ldap_group_search_base: str = (
        "OU=Security Groups,DC=utscad,DC=utsc,DC=utoronto,DC=ca"
    )
    ldap_groups_active: str = "GL_IITS_Users"
    ldap_groups_staff: str = "GL_SysNetAdmins"
    ldap_groups_superuser: str = "GL_SysNet_SuperUsers"
    ldap_additional_groups: list[str] = Field(default_factory = lambda: ["GL_Helpdesk"])

    class Config(BaseSettings.Config):
        app_name = "nautobot"
        prompt_on_missing_values = True

        @classmethod
        def parse_env_var(cls, field_name: str, raw_val: str):
            if field_name in {"allowed_hosts", "aruba_controllers"}:
                return raw_val.split(',')
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


class UofTPluginConfig(NautobotAppConfig):
    name = "uoft_nautobot"
    verbose_name = "UofT Nautobot Plugin"
    author = "Alex Tremblay"
    author_email = "alex.tremblay@utoronto.ca"
    version = __version__
    description = "A Plugin containing all the extensions and customizations to Nautobot that the UofT networking teams need"
    base_url = "uoft"
    min_version = "0.9"
    max_version = "9.0"
    middleware = []
    installed_apps = []
    default_settings = {}


def print_config_path():
    from pathlib import Path

    print(Path(__file__).parent.joinpath("nautobot_config.py"))


config = UofTPluginConfig
