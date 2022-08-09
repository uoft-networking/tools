import os
from pathlib import Path

from uoft_core import debug_cache
from django.core.management.base import BaseCommand
from jinja2 import StrictUndefined
from nautobot.dcim.models import Device, DeviceRole, DeviceType, Rack, Site


def librenms_stuff():
    from ...librenms import get_data

    devices = get_data()
    devices = list(
        filter(
            lambda d: "netmgmt.utsc" in d["hostname"] and "d1-" in d["hostname"],
            devices,
        )
    )
    for device in devices:
        Device()
    print()


@debug_cache
def golden_config_data():
    from nautobot_golden_config.utilities.graphql import graph_ql_query
    from nautobot_golden_config.models import GoldenConfigSetting
    from nautobot.utilities.utils import NautobotFakeRequest
    from nautobot.users.models import User

    from uuid import UUID

    device = Device.objects.get(id=UUID("d1726e48-e4f0-4c76-9af9-da3cfa676161"))
    data = {"obj": device}
    request = NautobotFakeRequest(
        {
            "user": User.objects.get(id=UUID("b728e599-09ae-41de-8734-f17045c42c50")),
            "path": "/extras/jobs/plugins/nautobot_golden_config.jobs/AllGoldenConfig/",
        }
    )
    settings = GoldenConfigSetting.objects.get(
        id=UUID("92368e69-14db-4471-8b66-f71ccbfe4d76")
    )
    status, device_data = graph_ql_query(request, device, settings.sot_agg_query.query)
    data.update(device_data)
    return data


def golden_config_test():
    from django_jinja.backend import Jinja2
    from jinja2.loaders import FileSystemLoader
    from jinja2 import Environment

    data = golden_config_data()
    git_repo = Path("./gitlab_repo")
    template = "templates/Distribution Switches/WS-C3850-24XS-E.j2"

    jinja_settings = Jinja2.get_default()
    jinja_env: Environment = jinja_settings.env
    jinja_env.trim_blocks = True
    jinja_env.undefined = StrictUndefined
    jinja_env.loader = FileSystemLoader(git_repo)

    t = jinja_env.get_template(template)
    text = t.render(**data)  # need to add nornir host object to jinja context
    print(text)
    pass


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


class Command(BaseCommand):
    help = "Run debug code from the uoft_nautobot plugin"

    def handle(self, *args, **options):
        golden_config_test()        
