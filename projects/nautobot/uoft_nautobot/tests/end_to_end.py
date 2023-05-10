from pathlib import Path

import pytest
from nautobot.core.runner.runner import configure_app
from nautobot.core.cli import _configure_settings
import django

from django_jinja.backend import Jinja2
from jinja2.loaders import FileSystemLoader
from jinja2 import Environment, StrictUndefined

fixtures_dir = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def _nautobot_initialized():
    configure_app(
        default_config_path="projects/nautobot/.dev_data/nautobot_config.py",
        project="nautobot",
        default_settings="nautobot.core.settings",
        initializer=_configure_settings,
    )
    django.setup()


def _golden_config_data():
    # These modules cannot be imported until after django.setup() is called
    # as part of the _nautobot_initialized fixture.
    from nautobot_golden_config.utilities.graphql import graph_ql_query
    from nautobot_golden_config.models import GoldenConfigSetting
    from nautobot.utilities.utils import NautobotFakeRequest
    from nautobot.users.models import User
    from nautobot.dcim.models import Device
    device = Device.objects.get(name="d1-aa")
    data = {"obj": device}
    request = NautobotFakeRequest(
        {
            "user": User.objects.get(username="admin"),
            "path": "/extras/jobs/plugins/nautobot_golden_config.jobs/AllGoldenConfig/",
        }
    )
    settings = GoldenConfigSetting.objects.get(slug="default")
    _, device_data = graph_ql_query(request, device, settings.sot_agg_query.query)
    return device_data


@pytest.mark.end_to_end
class Nautobot:
    def golden_config(self, _nautobot_initialized, mocker):
        from ..golden_config import transposer
        from nautobot_golden_config.utilities.constant import PLUGIN_CFG
        git_repo = fixtures_dir / "_private/.gitlab_repo"
        mocked_repo_path = mocker.patch('uoft_nautobot.golden_config._get_golden_config_repo_path')
        mocked_repo_path.return_value = git_repo
        mocked_plugin_config = mocker.patch.dict(PLUGIN_CFG, {"sot_agg_transposer": "uoft_nautobot.golden_config.noop_transposer"})

        # device = Device.objects.get(name="d1-ac")
        # data = {"obj": device}

        data = _golden_config_data()
        data = transposer(data)
        
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
        Path("test.cisco").unlink()

    def runjob(self, _nautobot_initialized, mocker):
        from nautobot.extras.management.commands.runjob import Command
        from nautobot.extras.models import GitRepository

        PLUGIN_CFG = django.conf.settings.PLUGINS_CONFIG.get( # type: ignore
            "nautobot_plugin_nornir", {}
        )
        NORNIR_SETTINGS = PLUGIN_CFG.get("nornir_settings")
        NORNIR_SETTINGS["runner"] = dict(plugin="serial")

        Command().run_from_argv(
            [
                "nautobot-server",
                "runjob",
                "--local",
                "--commit",
                "--username",
                "trembl94",
                "--data",
                '{"device":["80fae153-d00c-492f-ba0d-cdc3d4022c79"]}',
                "plugins/nautobot_golden_config.jobs/IntendedJob",
            ]
        )
