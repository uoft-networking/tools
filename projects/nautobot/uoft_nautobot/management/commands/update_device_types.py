from pathlib import Path
from argparse import ArgumentParser
from shutil import which
from subprocess import PIPE, run
from typing import Optional

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from ...datasources import refresh_single_device_type


class Command(BaseCommand):
    help = "Create or update a DeviceType entry in the database, from a 'netbox-community/devicetype-library' compatible git repo"

    def add_arguments(self, parser: ArgumentParser):
        def_git_path = f"{settings.GIT_ROOT}/netbox-community-devicetype-library"
        parser.add_argument(
            "--git-repo-path",
            metavar='PATH',
            default=def_git_path,
            help="filesystem path of a git repository containing DeviceType definition yaml files",
        )
        parser.add_argument(
            "type_definitions",
            metavar='YAML_FILE',
            nargs="*",
            help="name of a yaml file to process, relative to the git repo. If none are specified and `fzf` is intalled on this system, an interactive prompt will be opened to select one",
        )

    def handle(self, *args, git_repo_path: str | Path = '', type_definitions: Optional[list[str]] = None, **options):
        type_definitions = type_definitions or []
        git_repo_path = Path(git_repo_path)
        if not type_definitions:
            if which('fzf') is None:
                raise CommandError('no DEVICE_TYPE specified. fzf utility is not installed, so DEVICE_TYPE cannot be specified interactively. please run this command again with --help')

            res = run('fzf -m'.split(), check=True, stdout=PIPE, cwd=git_repo_path)
            type_definitions.extend(res.stdout.decode().splitlines())
        
        for filename in type_definitions:
            dt = refresh_single_device_type(git_repo_path / filename)
            self.stderr.write(f'Created device "{dt}" from file `{filename}`')
