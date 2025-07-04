from pathlib import Path
import uuid

import pytest
from nautobot.core.cli import load_settings
import django
from django.test.client import RequestFactory

from django_jinja.backend import Jinja2
from jinja2.loaders import FileSystemLoader
from jinja2 import Environment, StrictUndefined


fixtures_dir = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def _nautobot_initialized():
    load_settings("projects/nautobot/.dev_data/nautobot_config.py")
    django.setup()
    from django.conf import settings  # noqa: F401


def _golden_config_data(device_name):
    # These modules cannot be imported until after django.setup() is called
    # as part of the _nautobot_initialized fixture.
    from nautobot_golden_config.utilities.graphql import graph_ql_query
    from nautobot_golden_config.models import GoldenConfigSetting
    from nautobot.users.models import User
    from nautobot.dcim.models import Device

    device = Device.objects.get(name=device_name)
    request = RequestFactory().get("/extras/jobs/plugins/nautobot_golden_config.jobs/AllGoldenConfig/")
    request.user = User.objects.get(username="admin") # pyright: ignore[reportAttributeAccessIssue]
    request.id = uuid.uuid4()  # pyright: ignore[reportAttributeAccessIssue]

    settings = GoldenConfigSetting.objects.get(name="Default Settings")
    q = settings.sot_agg_query.query  # pyright: ignore[reportAttributeAccessIssue]
    _, device_data = graph_ql_query(request, device, q)
    return device, device_data


@pytest.mark.end_to_end
class NautobotTests:
    def test_golden_config(self, _nautobot_initialized, mocker):
        from ..golden_config import transposer
        from ..datasources import refresh_graphql_queries
        from nautobot_golden_config.utilities.constant import PLUGIN_CFG
        from ..jinja_filters import import_repo_filters_module
        from nautobot.extras.datasources.git import (
            update_git_config_contexts,
            GitRepository,
        )

        git_repo = fixtures_dir / "_private/.gitlab_repo"
        assert git_repo.exists()
        mocker.patch.dict(
            PLUGIN_CFG,
            {"sot_agg_transposer": "uoft_nautobot.golden_config.noop_transposer"},
        )

        mocker.patch.object(GitRepository, "filesystem_path", property(lambda _: str(git_repo)))
        _repo_record = GitRepository.objects.get(name="golden_config_templates")
        _job_result = mocker.Mock()
        update_git_config_contexts(_repo_record, _job_result)
        refresh_graphql_queries(_repo_record, _job_result)

        import_repo_filters_module(git_repo)
        template = "templates/entrypoint.j2"

        def _render(device_name):
            obj, data = _golden_config_data(device_name)
            data = transposer(data)
            data["obj"] = obj

            jinja_settings = Jinja2.get_default()
            jinja_env: Environment = jinja_settings.env
            jinja_env.trim_blocks = True
            jinja_env.undefined = StrictUndefined
            jinja_env.loader = FileSystemLoader(git_repo)

            t = jinja_env.get_template(template)
            text = t.render(**data)
            return text

        Path("hazmat/test.cisco").write_text(_render("d1-sw"))
        Path("hazmat/test-aruba.cisco").write_text(_render("a1-p50c"))
        Path("hazmat/test.cisco").unlink()
        Path("hazmat/test-aruba.cisco").unlink()

    def test_runjob(self, _nautobot_initialized, mocker):
        from nautobot.extras.management.commands.runjob import Command
        from nautobot.extras.models import GitRepository
        from nautobot.users.models import User
        from nautobot.dcim.models import Device

        # refresh templates git repo
        repo = GitRepository.objects.get(name="golden_config_templates")
        repo.sync(user=User.objects.get(username="admin"))

        PLUGIN_CFG = django.conf.settings.PLUGINS_CONFIG.get(  # pyright: ignore[reportAttributeAccessIssue]
            "nautobot_plugin_nornir", {}
        )
        NORNIR_SETTINGS = PLUGIN_CFG.get("nornir_settings")
        NORNIR_SETTINGS["runner"] = dict(plugin="serial")

        uuid = Device.objects.get(name="a1-p50c").id

        Command().run_from_argv([
            "nautobot-server",
            "runjob",
            "--local",
            "--commit",
            "--username",
            "trembl94",
            "--data",
            f'{{"device":["{uuid}"]}}',
            "plugins/nautobot_golden_config.jobs/IntendedJob",
        ])

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
