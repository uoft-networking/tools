import os
from pathlib import Path

from uoft_core import debug_cache
from django.core.management.base import BaseCommand
from jinja2 import StrictUndefined
from nautobot.dcim.models import Device


def librenms_stuff():
    from ...librenms import get_data
    import regex

    devices = get_data()
    re = regex.compile(r"^(av|[ad]\d)-.*")
    devices = list(
        filter(
            lambda d: re.match(d["hostname"]),
            devices,
        )
    )
    from nautobot.dcim.models import Device, DeviceRole, DeviceType, Manufacturer, Site
    from nautobot.ipam.models import IPAddress, VLAN, VLANGroup
    from nautobot_device_onboarding.models import OnboardingTask
    from nautobot_device_onboarding.utils.credentials import Credentials
    from nautobot_device_onboarding.worker import enqueue_onboarding_task

    def get_or_create_ip(ip):
        ip += "/32"
        try:
            return IPAddress.objects.get(address=ip)
        except IPAddress.DoesNotExist:
            return IPAddress.objects.create(address=ip)
    
    all_sites = {s.name: s for s in Site.objects.all()}
    all_sites['Student Life'] = all_sites['Student Centre']
    all_sites['Environment Sciences & Chemistry Building'] = all_sites['Environmental Science & Chemistry Building']
    for device in devices:
        hostname = device["hostname"].partition(".")[0]
        ip = device["ip"]
        #device_type = DeviceType.objects.get(name=device["hardware"])
        site = None
        role = None
        for group in device["groups"]:
            group_name = group["name"]
            if group_name == "Distribution Switches":
                role = DeviceRole.objects.get(name="Distribution Switches")
            elif group_name == "Access Switches":
                role = DeviceRole.objects.get(name="Access Switches")
            elif group_name == "Classroom Switches":
                role = DeviceRole.objects.get(name="Classroom Switches")
            elif group_name == "Campus Core Switches":
                role = DeviceRole.objects.get(name="Core Switches")
            elif group_name in all_sites:
                site = all_sites[group_name]
        assert site is not None
        assert role is not None

        ot = OnboardingTask.objects.create(
            ip_address=ip,
            site=site,
            role=role,
        )
        from ... import Settings
        s = Settings.from_cache()
        cr = Credentials(
            username=s.ssh.personal.username,
            password=s.ssh.personal.password.get_secret_value(),
            secret=s.ssh.enable_secret.get_secret_value()
        )
        enqueue_onboarding_task(ot.id, cr)
        # ip = get_or_create_ip(ip)
        # d = Device(
        #     name=hostname,
        #     site=site,
        #     #device_type=device_type,
        #     device_role=role,
        # )
        # d.validated_save()


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

def debug_transposer(data):
    # for this to work, you have to disable the transposer from running
    # inside the sotagg_query function
    # replace golden_config.transposer with a function that returns its input, 
    # delete .uoft_core.debug.cache.golden_config_data 
    # Then you can run this function to debug the transposer
    from ...golden_config import transposer_debug
    return transposer_debug(data)

def golden_config_test():
    from django_jinja.backend import Jinja2
    from jinja2.loaders import FileSystemLoader
    from jinja2 import Environment

    data = golden_config_data()
    # data = debug_transposer(data)
    git_repo = Path("gitlab_repo")
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
        librenms_stuff()
        #golden_config_test()
