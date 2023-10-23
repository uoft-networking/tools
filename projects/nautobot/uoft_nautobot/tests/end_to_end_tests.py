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


def _golden_config_data(device_name):
    # These modules cannot be imported until after django.setup() is called
    # as part of the _nautobot_initialized fixture.
    from nautobot_golden_config.utilities.graphql import graph_ql_query
    from nautobot_golden_config.models import GoldenConfigSetting
    from nautobot.utilities.utils import NautobotFakeRequest
    from nautobot.users.models import User
    from nautobot.dcim.models import Device

    device = Device.objects.get(name=device_name)
    request = NautobotFakeRequest(
        {
            "user": User.objects.get(username="admin"),
            "path": "/extras/jobs/plugins/nautobot_golden_config.jobs/AllGoldenConfig/",
        }
    )
    settings = GoldenConfigSetting.objects.get(slug="default")
    _, device_data = graph_ql_query(request, device, settings.sot_agg_query.query)
    return device, device_data


@pytest.mark.end_to_end
class NautobotTests:
    def test_golden_config(self, _nautobot_initialized, mocker):
        from ..golden_config import transposer
        from nautobot_golden_config.utilities.constant import PLUGIN_CFG
        from ..jinja_filters import import_repo_filters_module

        git_repo = fixtures_dir / "_private/.gitlab_repo"
        mocker.patch.dict(
            PLUGIN_CFG,
            {"sot_agg_transposer": "uoft_nautobot.golden_config.noop_transposer"},
        )

        device_name = "d1-sw"
        obj, data = _golden_config_data(device_name)
        data = transposer(data)
        data["obj"] = obj

        assert git_repo.exists()
        import_repo_filters_module(git_repo)
        template = "templates/entrypoint.j2"

        jinja_settings = Jinja2.get_default()
        jinja_env: Environment = jinja_settings.env
        jinja_env.trim_blocks = True
        jinja_env.undefined = StrictUndefined
        jinja_env.loader = FileSystemLoader(git_repo)

        t = jinja_env.get_template(template)
        text = t.render(**data)
        Path("hazmat/test.cisco").write_text(text)
        Path("hazmat/test.cisco").unlink()

    def test_runjob(self, _nautobot_initialized, mocker):
        from nautobot.extras.management.commands.runjob import Command
        from nautobot.extras.models import GitRepository
        from nautobot.utilities.utils import NautobotFakeRequest
        from nautobot.users.models import User
        from nautobot.dcim.models import Device

        # refresh templates git repo
        repo = GitRepository.objects.get(name="golden_config_templates")
        request = NautobotFakeRequest(
            {
                "user": User.objects.get(username="admin"),
                "path": "plugins/nautobot_golden_config.jobs/IntendedJob",
                "META": {},
                "POST": {},
                "GET": {},
            }
        )
        repo.request = request
        repo.save(trigger_resync=True)

        PLUGIN_CFG = django.conf.settings.PLUGINS_CONFIG.get(  # type: ignore
            "nautobot_plugin_nornir", {}
        )
        NORNIR_SETTINGS = PLUGIN_CFG.get("nornir_settings")
        NORNIR_SETTINGS["runner"] = dict(plugin="serial")

        uuid = Device.objects.get(name="a1-p50c").id

        Command().run_from_argv(
            [
                "nautobot-server",
                "runjob",
                "--local",
                "--commit",
                "--username",
                "trembl94",
                "--data",
                f'{{"device":["{uuid}"]}}',
                "plugins/nautobot_golden_config.jobs/IntendedJob",
            ]
        )

    def test_interfaces_excel(self, _nautobot_initialized):
        from ..excel import import_from_excel, export_to_excel
        from nautobot.dcim.models import Device

        device = "d1-sw"
        device_obj = Device.objects.get(name=device)
        pk = device_obj.id

        _, xlsx_content = export_to_excel(pk)
        Path("hazmat/test.xlsx").write_bytes(xlsx_content)

        import_from_excel(pk, Path("hazmat/test.xlsx").read_bytes())

        Path("hazmat/test.xlsx").unlink()
