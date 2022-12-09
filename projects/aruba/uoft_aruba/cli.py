import typer

from . import Settings, cpsec_whitelist, stm_blacklist


app = typer.Typer(
    name="aruba",
    context_settings={"max_content_width": 120, "help_option_names": ["-h", "--help"]},
    no_args_is_help=True,
    help=__doc__,  # Use this module's docstring as the main program help text
)
app.add_typer(cpsec_whitelist.run, name="cpsec-whitelist")
app.add_typer(stm_blacklist.app, name="stm-blacklist")


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
        to = "uoft-aruba cpsec-whitelist"
        cmd = cpsec_whitelist.run
    else:
        raise ValueError(f"command {cmdline} is not deprecated")

    warn(
        FutureWarning(
            f"The '{from_}' command has been renamed to '{to}' and will be removed in a future version."
        )
    )
    cmd()


def _debug():
    "Debugging function, only used in active debugging sessions."
    # pylint: disable=all
    app()
