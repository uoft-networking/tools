import os
import sys
from typing import Optional
from sys import version_info, platform, executable
from importlib.metadata import version
from pkgutil import iter_modules, resolve_name
from pathlib import Path

from . import Util

import typer
from loguru import logger

app = typer.Typer(name=__package__)

util = Util(__package__)


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
    util.logging.enable()
    util.logging.add_stderr_rich_sink(log_level)
    util.logging.add_syslog_sink()

def _add_subcommands():
    """
    Dynamically add subcommands from uoft_* packages, and add virtual subcommands for any uoft-* executables
    not already added as a subcommand.
    """
    local_subcommands = set()
    # add subcommands from uoft_* packages in same virtualenv
    for mod in iter_modules():
        if mod.ispkg and mod.name.startswith("uoft_") and mod.name != "uoft_core":
            try:
                subapp = resolve_name(f"{mod.name}.cli:app")
                local_subcommands.add(mod.name)
                app.add_typer(subapp)
            except (ImportError, AttributeError):
                # if the module doesn't have a cli.py, or if it doesn't have an app object, skip it
                pass
    
    # add virtual subcommands for any uoft-* executables available in PATH which aren't already added as a subcommand
    paths = os.environ.get("PATH", os.defpath)
    executable_file = os.X_OK | os.F_OK
    names = set()
    for path in [Path(p) for p in paths.split(os.pathsep)]:
        if not path.exists():
            continue
        for fn in path.iterdir():
            if not fn.is_file():
                continue
            if not os.access(fn, executable_file):
                continue
            if not fn.name.startswith("uoft-"):
                continue
            name = fn.name.partition('uoft-')[2].replace('-', '_')
            if name in local_subcommands:
                continue
            if name in names:
                continue
            names.add(name)
            # now we need to create a virtual command or command group for this external command
            app.command(name)(lambda: os.execv(fn, sys.argv[1:]))

            # TODO: figure out how to handle and forward shell completions for virtual subcommands


@logger.catch
def cli():
    try:
        _add_subcommands()
        print({e:v for e,v in os.environ.items() if e.startswith("COMP")}, file=sys.stderr)
        app()
    except KeyboardInterrupt:
        print("Aborted!")
        sys.exit()


if __name__ == "__main__":
    import os
    if not os.environ.get("PYDEBUG"):
        cli()
        sys.exit(0)

    from typing import Iterable

    from prompt_toolkit.completion import Completer, Completion
    import jedi


    class JediCompleter(Completer):
        """
        Autocompleter that uses the Jedi library.
        """

        def get_completions(
            self, document, _
        ) -> Iterable[Completion]:
            try:
                script = jedi.Script(f"import {document.text}")
                jedi_completions = script.complete(
                    column=document.cursor_position_col+7,
                    line=document.cursor_position_row + 1,
                )
                for jc in jedi_completions:

                    yield Completion(
                        jc.name_with_symbols,
                        len(jc.complete) - len(jc.name_with_symbols), # type: ignore
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
        #validator=v,
        completer=JediCompleter(),
        default_from_history=True
    )
    args = p.get_string("args", "Enter any arguments you'd like to pass to the module", default_from_history=True)
    sys.argv.extend(args.split())
    cd = p.get_path("cwd", "Enter the working directory you'd like to use", default_from_history=True, only_directories=True)
    os.chdir(cd)
    mod = import_module(mod_name)
    if hasattr(mod, "_debug"):
        mod._debug() # pylint: disable=protected-access
    else:
        print(f"Module {mod_name} has no _debug() function")
    sys.exit()
