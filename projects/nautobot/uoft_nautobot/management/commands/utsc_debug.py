import os
from pathlib import Path

from uoft_core import debug_cache
from django.core.management.base import BaseCommand
from jinja2 import StrictUndefined
from nautobot.dcim.models import Device
from .update_device_types import update_device_types
from .import_devices_from_librenms import create_devices


def librenms_stuff():

    
    from nautobot_device_onboarding.models import OnboardingTask
    from nautobot_device_onboarding.utils.credentials import Credentials
    from nautobot_device_onboarding.worker import enqueue_onboarding_task
    from nautobot.ipam.models import IPAddress

    def get_or_create_ip(ip):
        ip += "/32"
        try:
            return IPAddress.objects.get(address=ip)
        except IPAddress.DoesNotExist:
            return IPAddress.objects.create(address=ip)
    

        # ot = OnboardingTask.objects.create(
        #     ip_address=ip,
        #     site=site,
        #     role=role,
        # )
        # from ... import Settings
        # s = Settings.from_cache()
        # cr = Credentials(
        #     username=s.ssh.personal.username,
        #     password=s.ssh.personal.password.get_secret_value(),
        #     secret=s.ssh.enable_secret.get_secret_value()
        # )
        # enqueue_onboarding_task(ot.id, cr)
        # ip = get_or_create_ip(ip)
        # d = Device(
        #     name=hostname,
        #     site=site,
        #     #device_type=device_type,
        #     device_role=role,
        # )
        # d.validated_save()


    #print(devices)

def debug_transposer(data):
    # for this to work, you have to disable the transposer from running
    # inside the sotagg_query function
    # replace golden_config.transposer with a function that returns its input, 
    # delete .uoft_core.debug.cache.golden_config_data 
    # Then you can run this function to debug the transposer
    from ...golden_config import transposer_debug
    return transposer_debug(data)

def golden_config_test():
    pass


def prod_workbench():
    import pynautobot

    prod = pynautobot.api(
        "https://engine.server.utsc.utoronto.ca", os.environ.get("MY_API_TOKEN")
    )

    print(prod)


class Command(BaseCommand):
    help = "Run debug code from the uoft_nautobot plugin"

    def handle(self, *args, **options):
        create_devices()
        #update_device_types()
        #librenms_stuff()
        #golden_config_test()
