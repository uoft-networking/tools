import os
from pathlib import Path

import pytest
from nautobot.core.runner.runner import configure_app
from nautobot.core.cli import _configure_settings
import django
from uoft_core import shell


@pytest.fixture(scope="session")
def nautobot_initialized():
    for line in Path('projects/nautobot/dev_data/.env').read_text().splitlines():
        if line is not '' and not line.startswith(('#', ' ')):
            key, val = line.split('=', 1)
            os.environ[key] = val
    for line in shell('pass show nautobot-secrets').splitlines():
        if line.startswith('export'):
            line = line.split(' ', 1)[1]
            key, val = line.split('=', 1)
            if val.startswith("'") and val.endswith("'"):
                val = val[1:-1]
            os.environ[key] = val
    configure_app(
        default_config_path='projects/nautobot/dev_data/nautobot_config.py',
        project='nautobot',
        default_settings='nautobot.core.settings',
        initializer=_configure_settings,
        )
    django.setup()

def test_debug(nautobot_initialized):
    os.environ["PYDEBUG"] = "1"
    from uoft_nautobot.management.commands.utsc_debug import golden_config_test
    golden_config_test()