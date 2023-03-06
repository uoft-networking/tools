from pathlib import Path
from argparse import ArgumentParser
from shutil import which
from subprocess import PIPE, run
from typing import Optional


from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from nautobot.extras.models import GitRepository
from nautobot.utilities.utils import NautobotFakeRequest
from nautobot.users.models import User
from ...datasources import refresh_single_device_type


class Command(BaseCommand):
    help = "Create or update DeviceType entries in the database, from a 'netbox-community/devicetype-library' compatible git repo"

    def handle(self, *args, **options):
        repo_name = "devicetype-library"
        url = "https://github.com/netbox-community/devicetype-library"
        repo = GitRepository.objects.filter(name=repo_name).first()
    


        request = NautobotFakeRequest(
            {
                "user": User.objects.get(username='trembl94'),
                "path": "/extras/git-repositories/",
                "META": {"REMOTE_ADDR": ""},
                "GET": {},
                "POST": {},
            }
        )

        if repo:
            repo.request = request
            
            from ...datasources import refresh_device_types
            from unittest.mock import MagicMock
            refresh_device_types(repo, MagicMock(), interactive=True)
            #repo.save()  # Force a refresh, including the processing of datasource callbacks
        else:
            repo = GitRepository.objects.create(
                name=repo_name, branch="master", remote_url=url, provided_contents=["nautobot.device_types"], request = request
            )
