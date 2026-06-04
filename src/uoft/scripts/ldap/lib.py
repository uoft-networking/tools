from . import Settings

from typing import Optional

import ldap3

def user(
    name: str,
):
    s = Settings.from_cache()
    server = ldap3.Server(s.server, get_info=ldap3.ALL)
    conn = ldap3.Connection(server, s.bind_username, s.bind_password.get_secret_value(), auto_bind=True)  # type: ignore
    conn.search(s.users_base_dn, f"(name={name})", attributes=ldap3.ALL_ATTRIBUTES)
    print(conn.entries)


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
