import os
from pathlib import Path

import pytest
from nautobot.core.runner.runner import configure_app
from nautobot.core.cli import _configure_settings
import django
from uoft_core import shell


@pytest.fixture(scope="session")
def nautobot_initialized():
    for line in Path("projects/nautobot/dev_data/.env").read_text().splitlines():
        if line is not "" and not line.startswith(("#", " ")):
            key, val = line.split("=", 1)
            os.environ[key] = val
    for line in shell("pass show nautobot-secrets").splitlines():
        if line.startswith("export"):
            line = line.split(" ", 1)[1]
            key, val = line.split("=", 1)
            if val.startswith("'") and val.endswith("'"):
                val = val[1:-1]
            os.environ[key] = val
    configure_app(
        default_config_path="projects/nautobot/dev_data/nautobot_config.py",
        project="nautobot",
        default_settings="nautobot.core.settings",
        initializer=_configure_settings,
    )
    django.setup()


def test_golden_config(nautobot_initialized):
    from uoft_nautobot.management.commands.utsc_debug import golden_config_test

    golden_config_test()


@pytest.mark.skip(reason="need to containerizer nautobot dev env")
def test_runjob(nautobot_initialized):
    from nautobot.extras.management.commands.runjob import Command

    Command().run_from_argv(
        [
            "nautobot-server",
            "runjob",
            "--local",
            "--commit",
            "--username",
            "trembl94",
            "--data",
            '{"device":["d1726e48-e4f0-4c76-9af9-da3cfa676161"]}',
            "plugins/nautobot_golden_config.jobs/IntendedJob",
        ]
    )
