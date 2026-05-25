
from ipaddress import IPv4Network, IPv6Network

from uoft_core import BaseSettings, SecretStr, Field

class Settings(BaseSettings):
    user: str
    password: SecretStr
    host: str = "ipam-dev.its.utoronto.ca"
    port: int = 5432
    database: str = "ipam"
    tags_by_network: dict[IPv4Network | IPv6Network, str] = Field(
        default_factory=dict,
        title="Tags by Network",
        description="A mapping of network prefixes to tags. "
        "The key is the network prefix, and the value is the tag "
        "to apply to networks that fall within that prefix.",
    )
    tags_by_network_exact: dict[IPv4Network | IPv6Network, str] = Field(
        default_factory=dict,
        title="Tags by Network",
        description="A mapping of network prefixes to tags. "
        "The key is the network prefix, and the value is the tag "
        "to apply to the network that exactly matches that prefix.",
    )

    class Config(BaseSettings.Config):
        app_name = "stg-ipam-dev"

    def get_dsn(self) -> str:
        auth = f"{self.user}:{self.password.get_secret_value()}"
        return f"postgresql+psycopg://{auth}@{self.host}:{self.port}/{self.database}"
