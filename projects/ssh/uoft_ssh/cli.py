"""
A toolkit for working with SSH. Wrappers, Ansible convenience features, Nornir integration, etc
"""

from typing import Annotated, Optional
import sys
import socket

import typer

from uoft_core import logging
from uoft_core.console import console
from . import Settings

logger = logging.getLogger(__name__)

DEBUG_MODE = False


def _version_callback(value: bool):
    if not value:
        return
    from . import __version__
    import sys

    print(
        f"uoft-{Settings.Config.app_name} v{__version__} \nPython {sys.version_info.major}."
        f"{sys.version_info.minor} ({sys.executable}) on {sys.platform}"
    )
    raise typer.Exit()


app = typer.Typer(
    name="ssh",
    context_settings={"max_content_width": 120, "help_option_names": ["-h", "--help"]},
    no_args_is_help=True,
    help=__doc__,  # Use this module's docstring as the main program help text
)


@app.callback()
# @Settings.wrap_typer_command
# TODO: implement support for exploding submodels in Settings.wrap_typer_command
def ssh(
    ctx: typer.Context,
    host: Annotated[str, typer.Argument(help="The hostname or IP address of the remote server")],
    command: Annotated[
        str | None,
        typer.Argument(
            help="The command to run on the remote server. "
            "Interactive shell will be launched if no command specified",
        ),
    ] = None,
    login_as_admin: Annotated[
        bool, typer.Option("--login-as-admin", help="Login as admin user (instead of using your utorid)")
    ] = False,
    version: Annotated[
        Optional[bool],
        typer.Option("--version", callback=_version_callback, is_eager=True, help="Show version information and exit"),
    ] = None,
    debug: bool = typer.Option(False, help="Turn on debug logging", envvar="DEBUG"),
    trace: bool = typer.Option(False, help="Turn on trace logging. implies --debug", envvar="TRACE"),
):
    global DEBUG_MODE
    log_level = "INFO"
    if debug:
        log_level = "DEBUG"
        DEBUG_MODE = True
    if trace:
        log_level = "TRACE"
        DEBUG_MODE = True
    logging.basicConfig(level=log_level)


@app.command(context_settings={"ignore_unknown_options": True, "allow_extra_args": True})
def wrapper(
    ctx: typer.Context,
    host: Annotated[str, typer.Argument(help="The hostname or IP address of the remote server")],
    command: Annotated[
        str | None,
        typer.Option(
            help="The command to run on the remote server. "
            "Interactive shell will be launched if no command specified"
        ),
    ] = None,
    login_as_admin: Annotated[bool, typer.Option(help="Login as admin user")] = False,
):
    import pexpect
    s = Settings.from_cache()
    creds = s.admin if login_as_admin else s.personal
    extra_args = ctx.args

    # sanity check the host
    try:
        ip_addr = socket.gethostbyname(host)
    except socket.gaierror as e:
        logger.error(f"Could not resolve {host}: \n{e}")
        sys.exit(1)

    if '-l' in extra_args:
        l_index = extra_args.index('-l')
        username = extra_args[l_index + 1]
        extra_args.pop(l_index+1)
        extra_args.pop(l_index)
    else:
        username = creds.username

    ssh_command = f"ssh {' '.join(extra_args)} {username}@{ip_addr}"
    if command:
        ssh_command += f" {command}"

    logger.debug(f"Running command: {ssh_command}")


    child = pexpect.spawn(ssh_command)
    logger.info("Waiting for password prompt")

    # TODO: on timeout, check for host key errors and handle them
    match = child.expect(["[pP]assword:", 'has changed and you have requested strict checking'])
    if match == 1:
        logger.error(f"Host key for {host} has changed")
        logger.warning("If this is expected, run the following command to remove the old key:")
        logger.warning(f"[bold]ssh-keygen -R {host}[/]")
        logger.warning(f"[bold]ssh-keygen -R {ip_addr}[/]")
        sys.exit(1)


    console().set_window_title(f"uoft-ssh {host}")
    child.sendline(creds.password.get_secret_value())
    while True:
        child.interact()
        if child.isalive():
            # the only way to get to this point in control flow is to have hit the escape character (default is ^])
            # The only reason for a user to do so is to inject the enable password into the session
            child.sendline(s.enable_secret.get_secret_value())
            continue
        else:
            # `child.interact()` returned because the child process exited
            break
    child.close()
    sys.exit(child.exitstatus)


@app.command()
def nornir():
    # TODO: nornir! with napalm!
    pass


def cli():
    try:
        # CLI code goes here
        app()
    except KeyboardInterrupt:
        print("Aborted!")
        sys.exit()
    except Exception as e:
        if DEBUG_MODE:
            raise
        logger.error(e)
        sys.exit(1)


def _debug():
    "Debugging function, only used in active debugging sessions."
    # pylint: disable=all
    app()
