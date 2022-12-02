from typing import Optional

from uoft_core import shell, BaseSettings, SecretStr

import ldap3
import typer


app = typer.Typer(name="ldap")


class Settings(BaseSettings):
    bind_username: str
    bind_password: SecretStr
    server: str
    users_base_dn: str
    groups_base_dn: str

    class Config(BaseSettings.Config):
        app_name = "ldap"


@app.callback()
@Settings.wrap_typer_command
def _():
    pass


@app.command()
def user(
    name: str,
):
    s = Settings.from_cache()
    server = ldap3.Server(s.server, get_info=ldap3.ALL)
    conn = ldap3.Connection(server, s.bind_username, s.bind_password.get_secret_value(), auto_bind=True)  # type: ignore
    conn.search(s.users_base_dn, f"(name={name})", attributes=ldap3.ALL_ATTRIBUTES)
    print(conn.entries)


@app.command()
def group(name: Optional[str] = "", attributes: str = "cn,name,member,objectClass"):
    if attributes == "ALL":
        attrs = ldap3.ALL_ATTRIBUTES
    else:
        attrs = attributes.split(",")
    s = Settings.from_cache()
    server = ldap3.Server(s.server, get_info=ldap3.ALL)
    conn = ldap3.Connection(server, s.bind_username, s.bind_password.get_secret_value(), auto_bind=True)  # type: ignore
    conn.search(s.groups_base_dn, f"(name={name}*)", attributes=attrs)
    for entry in conn.entries:
        print(entry)
