import os
import sys
from typing import Optional
from sys import version_info, platform, executable
from importlib.metadata import version
from pkgutil import resolve_name
from shutil import which

from . import Util

import typer

app = typer.Typer(name=__package__) # type: ignore

util = Util(__package__) # type: ignore


def version_callback(value: bool):
    if value:
        v = version_info
        print(
            f"uoft wrapper command v{version(__package__)}\nPython {v.major}.{v.minor} ({executable}) on {platform})"
        )
        raise typer.Exit()


@app.callback(
    context_settings={"max_content_width": 120, "help_option_names": ["-h", "--help"]}
)
def callback(
    debug: bool = typer.Option(False, help="Turn on debug logging"),
    trace: bool = typer.Option(False, help="Turn on trace logging. implies --debug"),
    version: Optional[bool] = typer.Option(  # pylint: disable=unused-argument
        None,
        "--version",
        callback=version_callback,
        help="Show version information and exit",
    ),
):
    """
    Command-line namespace for all uoft command-line utilities. makes each uoft_* command available as a subcommand.
    """

    log_level = "INFO"
    if debug:
        log_level = "DEBUG"
    if trace:
        log_level = "TRACE"
    import logging
    logging.basicConfig(level=log_level, format="%(levelname)s: %(message)s", stream=sys.stderr)


# [[[cog
# import _cog as c; c.all_projects_as_python_list()
# ]]]
ALL_PROJECTS = [
    "grist",
    "snipeit",
    "phpipam",
    "librenms",
    "aruba",
    "nautobot",
    "paloalto",
    "bluecat",
    "ssh",
    "scripts",
    "switchconfig",
    "core",
]
# [[[end]]]


def _add_subcommands() -> tuple[set[str], set[str]]:
    """
    Dynamically add subcommands from uoft_* packages, and add virtual subcommands for any uoft-* executables
    not already added as a subcommand.
    """
    internal_subcommands = set()
    external_subcommands = set()

    for p in ALL_PROJECTS:
        try:
            # look for a python package named uoft_<p> in the local virtualenv and a cli module in it
            # try to add a subcommand for it
            subapp = __import__(f"uoft_{p}.cli").cli.app
            internal_subcommands.add(p)
            app.add_typer(subapp)
        except (ImportError, AttributeError):
            # if the module isn't installed locally, doesn't have a cli.py,
            # or if it doesn't have an app object,
            # look for it on PATH and add a virtual subcommand for it
            ext = which(f"uoft-{p}")
            if ext:
                name = ext
                external_subcommands.add(p)

                # I think a typer update broke my lambda...
                # seems to require an actual function now
                @app.command(p)
                def _():
                    os.execv(name, [f"uoft-{p}"] + sys.argv[2:])

    return internal_subcommands, external_subcommands


def _get_subcommand_name():
    shell = os.environ.get("_UOFT_COMPLETE", "").partition("_")[2]
    if shell == "bash":
        # completion arguments are stored in the COMP_WORDS environment variable as a newline-delimited list
        var = "COMP_WORDS"
        sep = "\n"

    elif shell == "zsh":
        # completion arguments are stored in the _TYPER_COMPLETE_ARGS environment variable as a space-delimited list
        var = "_TYPER_COMPLETE_ARGS"
        sep = " "

    elif shell == "fish":
        # completion arguments are stored in the _TYPER_COMPLETE_ARGS environment variable as a space-delimited list
        var = "_TYPER_COMPLETE_ARGS"
        sep = " "
    else:
        # we don't know how to get the subcommand name for this shell
        return None

    words = os.environ.get(var, "")
    if words.count(sep) > 1:
        words = words.split(sep)
        # the first argument is the command name, the second is the subcommand name
        return words[1], var, sep
    return None


def handle_external_subcommand_completion(external: set[str]):
    if not os.environ.get("_UOFT_COMPLETE"):
        return

    if res := _get_subcommand_name():
        subcommand, var, sep = res
        if subcommand in external:
            # prepare completeion env args for the external subcommand
            os.environ[f"_UOFT_{subcommand.upper()}_COMPLETE"] = os.environ[
                "_UOFT_COMPLETE"
            ]
            os.environ[var] = os.environ[var].replace(
                f"uoft{sep}{subcommand}", f"uoft-{subcommand}", 1
            )
            if bash_comp_word_count := os.environ.get("COMP_CWORD"):
                os.environ["COMP_CWORD"] = str(int(bash_comp_word_count) - 1)
            os.execvpe(
                "uoft-" + subcommand, [f"uoft-{subcommand}"] + sys.argv[1:], os.environ
            )


def cli():
    try:
        internal, external = _add_subcommands()
        handle_external_subcommand_completion(external)
        app()
    except KeyboardInterrupt:
        print("Aborted!")
        sys.exit()
    except Exception as e:
        if os.environ.get("PYDEBUG"):
            raise
        print(f"Error: {e}")
        sys.exit(1)
        


if __name__ == "__main__":
    import os

    if not os.environ.get("PYDEBUG"):
        cli()
        sys.exit(0)

    from typing import Iterable

    from prompt_toolkit.completion import Completer, Completion
    import jedi

    from . import logging

    class JediCompleter(Completer):
        """
        Autocompleter that uses the Jedi library.
        """

        def get_completions(self, document, _) -> Iterable[Completion]:
            try:
                script = jedi.Script(f"import {document.text}")
                jedi_completions = script.complete(
                    column=document.cursor_position_col + 7,
                    line=document.cursor_position_row + 1,
                )
                for jc in jedi_completions:
                    yield Completion(
                        jc.name_with_symbols,
                        len(jc.complete) - len(jc.name_with_symbols),  # type: ignore
                        display=jc.name_with_symbols,
                        display_meta=jc.type,
                    )

            except Exception:  # pylint: disable=broad-except
                # There are many ways in which jedi completions can fail.
                # We don't want to crash the application because of this.
                # See: ptpython.completer.JediCompleter.get_completions
                # or ptpython.utils.get_jedi_script_from_document for examples
                pass

    # let's interactively prompt for a module to debug and execute that

    from importlib import import_module
    from .prompt import Prompt

    history_cache = util.history_cache
    p = Prompt(history_cache)
    mod_name = p.get_string(
        "module name",
        'Enter the full dotted name of the module you\'d like to debug. Ex: "uoft_core.nested_data"',
        # validator=v,
        completer=JediCompleter(),
        default_from_history=True,
    )
    args = p.get_string(
        "args",
        "Enter any arguments you'd like to pass to the module",
        default_from_history=True,
    )
    sys.argv.extend(args.split())
    cd = p.get_path(
        "cwd",
        "Enter the working directory you'd like to use",
        default_from_history=True,
        only_directories=True,
    )
    os.chdir(cd)

    if '--debug' in sys.argv:
        level = logging.DEBUG
    elif '--trace' in sys.argv:
        level = logging.TRACE
    else:
        level = logging.INFO
    
    logging.basicConfig(level=level)
    
    mod = import_module(mod_name)
    if hasattr(mod, "_debug"):
        mod._debug()  # pylint: disable=protected-access
    else:
        print(f"Module {mod_name} has no _debug() function")
    sys.exit()
