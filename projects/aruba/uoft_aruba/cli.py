from typer import Typer
from . import cpsec_whitelist

app = Typer()
app.add_typer(cpsec_whitelist.run, name="cpsec_whitelist")
