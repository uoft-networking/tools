from typing import Optional

from . import Settings

import typer


app = typer.Typer(name="ldap")


@app.callback()
@Settings.wrap_typer_command
def _():
    pass


@app.command()
def user(
    name: str,
):
    from . import lib

    lib.user(name)

@app.command()
def group(name: Optional[str] = "", attributes: str = "cn,name,member,objectClass"):
    from . import lib

    lib.group(name, attributes)
