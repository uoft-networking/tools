from uoft_core import BaseSettings, SecretStr

class Settings(BaseSettings):
    bind_username: str
    bind_password: SecretStr
    server: str
    users_base_dn: str
    groups_base_dn: str

    class Config(BaseSettings.Config):
        app_name = "ldap"
