"""
A toolkit for working with SSH. Wrappers, Ansible convenience features, Nornir integration, etc
"""

import typing as t
import sys
import socket

import typer

from uoft.core import logging
from uoft.core.console import console
from ..conf import Settings
from ..util import (
    get_ssh_session,
    HostKeyChanged,
    HostKeyAlgorithmMismatch,
    KeyExchangeMethodMismatch,
    UnknownHostKey,
    SSHSessionError,
)


logger = logging.getLogger(__name__)

DEBUG_MODE = False


def _version_callback(value: bool):
    if not value:
        return
    from ..version import __version__
    import sys

    print(
        f"uoft-{Settings.Config.app_name} v{__version__} \nPython {sys.version_info.major}."
        f"{sys.version_info.minor} ({sys.executable}) on {sys.platform}"
    )
    raise typer.Exit()


app = typer.Typer(
    name="ssh",
    no_args_is_help=True,
    help=__doc__,  # Use this module's docstring as the main program help text
)


@app.command(
    context_settings={
        "max_content_width": 120,
        "help_option_names": ["-h", "--help"],
        "ignore_unknown_options": True,
        "allow_extra_args": True,
    },
)
# @Settings.wrap_typer_command
# TODO: implement support for exploding submodels in Settings.wrap_typer_command
def ssh(
    ctx: typer.Context,
    host: t.Annotated[str, typer.Argument(help="The hostname or IP address of the remote server")],
    command: t.Annotated[
        str | None,
        typer.Option(
            help="The command to run on the remote server. Interactive shell will be launched if no command specified",
        ),
    ] = None,
    login_as_admin: t.Annotated[
        bool, typer.Option("--login-as-admin", help="Login as admin user (instead of using your utorid)")
    ] = False,
    terminal_server: t.Annotated[
        bool,
        typer.Option("--terminal-server", help="Use the terminal server credentials to login (instead of your utorid)"),
    ] = False,
    debug: t.Annotated[bool, typer.Option("--debug", help="Turn on debug logging", envvar="DEBUG")] = False,
    trace: t.Annotated[
        bool, typer.Option("--trace", help="Turn on trace logging. implies --debug", envvar="TRACE")
    ] = False,
    _: t.Annotated[
        t.Optional[bool],
        typer.Option("--version", callback=_version_callback, is_eager=True, help="Show version information and exit"),
    ] = None,
):
    """
    SSH into a remote host, automatically authenticating you using encrypted credentials.

    If no command is specified, an interactive shell will be launched.

    This command wraps the `ssh` command, and accepts all the same arguments.

    by default, this command will use the username and password defined in the "personal" section of the settings file.

    If you want to use a different username, you can specify it with the `-l` flag.

    If you want to use the admin credentials instead of the personal credentials, you can specify the
    `--login-as-admin` flag.

    Additionally, you can at any point in time hit the escape character (default is ^]) to inject the enable password
    into the running SSH session.

    Note:
        This command accepts all the same arguments as the `ssh` command, with one exception:
        due to the complexities of combining CLI parsers, to run a command on the target machine instead of a shell,
        the command must be supplied as an option instead of an argument. ie, instead of `ssh host 'cat /some/file'`,
        you would run `ssh --command 'cat /some/file' host`
    """

    global DEBUG_MODE
    log_level = "INFO"
    if debug:
        log_level = "DEBUG"
        DEBUG_MODE = True
    if trace:
        log_level = "TRACE"
        DEBUG_MODE = True
    logging.basicConfig(level=log_level)
    s = Settings.from_cache()
    if login_as_admin:
        creds = s.admin
    elif terminal_server:
        creds = s.terminal_server
    else:
        creds = s.personal
    extra_args = ctx.args

    # sanity check the host
    try:
        ip_addr = socket.gethostbyname(host)
    except socket.gaierror as e:
        logger.error(f"Could not resolve {host}: \n{e}")
        sys.exit(1)

    if "-l" in extra_args:
        l_index = extra_args.index("-l")
        username = extra_args[l_index + 1]
        extra_args.pop(l_index + 1)
        extra_args.pop(l_index)
    else:
        username = creds.username

    try:
        child = get_ssh_session(host, username, password=creds.password.get_secret_value(), extra_args=extra_args)
    except HostKeyChanged:
        logger.error(f"Host key for {host} has changed")
        logger.warning("If this is expected, run the following command to remove the old key:")
        logger.warning(f"[bold]ssh-keygen -R {host}[/]", extra={"markup": True})
        logger.warning(f"[bold]ssh-keygen -R {ip_addr}[/]", extra={"markup": True})
        sys.exit(1)
    except KeyExchangeMethodMismatch as e:
        logger.error(f"Key exchange method mismatch: {e.theirs}")
        logger.warning("If this is expected, run this command again with the following flag:")
        logger.warning(f"-o KexAlgorithms=+{e.theirs}")
        sys.exit(1)
    except HostKeyAlgorithmMismatch as e:
        logger.error(f"Host key algorithm mismatch: {e.theirs}")
        logger.warning("If this is expected, run this command again with the following flag:")
        logger.warning(f"-o HostKeyAlgorithms=+{e.theirs}")
        sys.exit(1)
    except UnknownHostKey:
        logger.error(f"Host key for {host} is unknown")
        logger.warning("If this is not your first time connecting to this host, this may be a security risk.")
        logger.warning(" hit Ctrl-C to abort, or hit Enter to continue connecting")
        input()
        child = get_ssh_session(host, username, password=creds.password.get_secret_value(), accept_unknown_host=True)
    except SSHSessionError as e:
        logger.error(e)
        sys.exit(1)

    console().set_window_title(f"uoft-ssh {host}")
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
