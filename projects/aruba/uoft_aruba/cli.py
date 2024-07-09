from .cli_commands import cpsec_allowlist, station_blocklist, list_aps
import typer

from . import Settings

app = typer.Typer(
    name="aruba",
    context_settings={"max_content_width": 120, "help_option_names": ["-h", "--help"]},
    no_args_is_help=True,
    help=__doc__,  # Use this module's docstring as the main program help text
)
app.add_typer(cpsec_allowlist.run, name="cpsec-allowlist")
app.add_typer(cpsec_allowlist.run, name="cpsec-whitelist", deprecated=True)
app.add_typer(station_blocklist.app, name="station-blocklist")
app.add_typer(list_aps.run, name="list-aps")
app.add_typer(list_aps.run, name="inventory")
app.add_typer(station_blocklist.app, name="station-blacklist", deprecated=True)


@app.callback()
@Settings.wrap_typer_command
def callback(debug: bool = typer.Option(False, help="Enable debug mode.")):
    # TODO: Add debug mode
    pass


def deprecated():
    import sys
    from warnings import warn

    cmdline = " ".join(sys.argv)
    if (from_ := "uoft_aruba") in cmdline:
        to = "uoft-aruba"
        cmd = app
    elif (from_ := "Aruba_Provision_CPSEC_Whitelist") in cmdline:
        to = "uoft-aruba cpsec-allowlist"
        cmd = cpsec_allowlist.run
    else:
        raise ValueError(f"command {cmdline} is not deprecated")

    warn(
        f"The '{from_}' command has been renamed to '{to}' and will be removed in a future version.",
        DeprecationWarning,
    )
    cmd()


def _debug():
    "Debugging function, only used in active debugging sessions."
    # pylint: disable=all
    app()
