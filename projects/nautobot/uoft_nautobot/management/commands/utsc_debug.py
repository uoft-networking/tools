import os
from pathlib import Path

from uoft_core import debug_cache
from django.core.management.base import BaseCommand
from jinja2 import StrictUndefined
from nautobot.dcim.models import Device


def librenms_stuff():
    from ...librenms import get_data

    devices = get_data()
    devices = list(
        filter(
            lambda d: "netmgmt.utsc" in d["hostname"] and "d1-" in d["hostname"],
            devices,
        )
    )
    print(devices)


@debug_cache
def golden_config_data():
    from nautobot_golden_config.utilities.graphql import graph_ql_query
    from nautobot_golden_config.models import GoldenConfigSetting
    from nautobot.utilities.utils import NautobotFakeRequest
    from nautobot.users.models import User

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


def golden_config_test():
    from django_jinja.backend import Jinja2
    from jinja2.loaders import FileSystemLoader
    from jinja2 import Environment

    data = golden_config_data()
    git_repo = Path("projects/nautobot/gitlab_repo")
    template = "templates/Distribution Switches/WS-C3850-24XS-E.cisco.j2"

    jinja_settings = Jinja2.get_default()
    jinja_env: Environment = jinja_settings.env
    jinja_env.trim_blocks = True
    jinja_env.undefined = StrictUndefined
    jinja_env.loader = FileSystemLoader(git_repo)

    t = jinja_env.get_template(template)
    text = t.render(**data)
    print(text)


def refresh_device_types():
    from ...datasources import refresh_single_device_type

    model_file = Path(
        "dev_data/git/netbox-community-devicetype-library/device-types/Cisco/WS-C3850-24XS-E.yaml"
    )

    refresh_single_device_type(model_file)


def prod_workbench():
    import pynautobot

    prod = pynautobot.api(
        "https://engine.server.utsc.utoronto.ca", os.environ.get("MY_API_TOKEN")
    )

    print(prod)


class Command(BaseCommand):
    help = "Run debug code from the uoft_nautobot plugin"

    def handle(self, *args, **options):
        golden_config_test()
