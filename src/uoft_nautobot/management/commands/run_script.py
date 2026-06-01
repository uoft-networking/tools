from typing import Any
import runpy

from django.core.management.base import BaseCommand
from nautobot.core.management.commands.nbshell import Command as NBShellCommand


class Command(BaseCommand):
    """
    Run a script in the Nautobot shell environment with all Nautobot ORM models and utility functions pre-loaded.
    This is intended for one-off scripts that need to be run in the Nautobot environment but
    don't warrant a full Nautobot Job implementation uoft-nautobot code extension."""

    help = __doc__  # pyright: ignore[reportAssignmentType]

    def add_arguments(self, parser):
        parser.add_argument(
            "SCRIPT",
            help="The script to run. this should be a relative or absolute path to a python file to be executed",
        )

    def handle(self, *args: Any, **options: Any) -> str | None:
        script_path = options["SCRIPT"]
        nbshell_cmd = NBShellCommand()
        init_globals = nbshell_cmd.get_imported_objects({})
        runpy.run_path(script_path, init_globals=init_globals, run_name="__main__")
        return f"Script {script_path} executed successfully."
