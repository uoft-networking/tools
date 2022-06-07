from ...librenms import get_data

from django.core.management.base import BaseCommand
from nautobot.dcim.models import Device, DeviceRole, DeviceType, Rack, Site


class Command(BaseCommand):
    help = "Run debug code from the utsc_nautobot plugin"

    def handle(self, *args, **options):
        devices = get_data()
        devices = list(filter(lambda d: 'netmgmt.utsc' in d['hostname'] and 'd1-' in d['hostname'], devices))
        for device in devices:
            Device()
        print()