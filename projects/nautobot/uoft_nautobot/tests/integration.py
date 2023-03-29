import os
from pathlib import Path

import pytest
from nautobot.core.runner.runner import configure_app
from nautobot.core.cli import _configure_settings
import django
from uoft_core import shell

pytestmark = pytest.mark.skip(reason="need to containerize nautobot dev env")

@pytest.fixture(scope="session")
def nautobot_initialized():
    for line in Path("projects/nautobot/.dev_data/.env").read_text().splitlines():
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
        default_config_path="projects/nautobot/.dev_data/nautobot_config.py",
        project="nautobot",
        default_settings="nautobot.core.settings",
        initializer=_configure_settings,
    )
    django.setup()

def _golden_config_data():
    from nautobot_golden_config.utilities.graphql import graph_ql_query
    from nautobot_golden_config.models import GoldenConfigSetting
    from nautobot.utilities.utils import NautobotFakeRequest
    from nautobot.users.models import User
    from nautobot.dcim.models import Device

    from uuid import UUID

    device = Device.objects.get(name="d1-aa")
    data = {"obj": device}
    request = NautobotFakeRequest(
        {
            "user": User.objects.get(username='trembl94'),
            "path": "/extras/jobs/plugins/nautobot_golden_config.jobs/AllGoldenConfig/",
        }
    )
    settings = GoldenConfigSetting.objects.get(slug='default')
    _, device_data = graph_ql_query(request, device, settings.sot_agg_query.query)
    data.update(device_data)
    return data

def test_golden_config(nautobot_initialized):
    from django_jinja.backend import Jinja2
    from jinja2.loaders import FileSystemLoader
    from jinja2 import Environment, StrictUndefined

    data = _golden_config_data()
    #data = debug_transposer(data)
    git_repo = Path("projects/nautobot/.gitlab_repo")
    assert git_repo.exists()
    template = "templates/Distribution Switches/WS-C3850-24XS-E.cisco.j2"

    jinja_settings = Jinja2.get_default()
    jinja_env: Environment = jinja_settings.env
    jinja_env.trim_blocks = True
    jinja_env.undefined = StrictUndefined
    jinja_env.loader = FileSystemLoader(git_repo)

    t = jinja_env.get_template(template)
    text = t.render(**data)
    Path("test.cisco").write_text(text)
    Path('test.cisco').unlink()



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
