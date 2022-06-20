from pathlib import Path

from django.core.management.base import BaseCommand
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


def golden_config_test():
    from nautobot_golden_config.utilities.graphql import graph_ql_query
    from nautobot_golden_config.models import GoldenConfigSetting
    from nautobot.utilities.utils import NautobotFakeRequest
    from nautobot.users.models import User
    from django_jinja.backend import Jinja2
    from jinja2.loaders import FileSystemLoader
    from jinja2 import Environment

    from uuid import UUID

    git_repo = Path("./dev_data/git/github-utsc-utoronto-ca/")
    template = "templates/Distribution Switches/WS-C3850-24XS-E.j2"

    jinja_settings = Jinja2.get_default()
    jinja_env: Environment = jinja_settings.env
    jinja_env.loader = FileSystemLoader(git_repo)
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

    t = jinja_env.get_template(template)
    text = t.render(**data) # need to add nornir host object to jinja context
    print()


class Command(BaseCommand):
    help = "Run debug code from the utsc_nautobot plugin"

    def handle(self, *args, **options):
        # librenms_stuff()
        golden_config_test()
