import json
from pathlib import Path
import uuid

import pytest
from nautobot.core.cli import load_settings
import django
from django.test.client import RequestFactory

from django_jinja.backend import Jinja2
from jinja2.loaders import FileSystemLoader
from jinja2 import Environment, StrictUndefined
from uoft_core import logging


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


#@pytest.mark.end_to_end
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

    def test_port_activation(self, _nautobot_initialized, mocker):
        from nautobot.extras.management.commands.runjob import Command
        d = {
            "device": "a2-testlab",
            "extra_data": {
                "lldp_packet": "Ether(dst='01:80:c2:00:00:0e', src='54:8a:ba:c0:2b:97', type=35020)/LLDPDU()/LLDPDUChassisID(_type=1, _length=7, subtype=4, id='54:8a:ba:c0:2b:80')/LLDPDUPortID(_type=2, _length=9, subtype=5, id=b'Gi1/0/23')/LLDPDUTimeToLive(_type=3, _length=2, ttl=120)/LLDPDUSystemName(_type=5, _length=35, system_name=b'a1-testlab.netmgmt.utsc.utoronto.ca')/LLDPDUSystemDescription(_type=6, _length=255, description=b'Cisco IOS Software [Gibraltar], Catalyst L3 Switch Software (CAT3K_CAA-UNIVERSALK9-M), Version 16.12.14, RELEASE SOFTWARE (fc1)\\nTechnical Support: http://www.cisco.com/techsupport\\nCopyright (c) 1986-2025 by Cisco Systems, Inc.\\nCompiled Mon 08-Sep-25 08:50')/LLDPDUPortDescription(_type=4, _length=25, description=b'[--alext-test-mac-lldp--]')/LLDPDUSystemCapabilities(_type=7, _length=4, reserved_5_available=0, reserved_4_available=0, reserved_3_available=0, reserved_2_available=0, reserved_1_available=0, two_port_mac_relay_available=0, s_vlan_component_available=0, c_vlan_component_available=0, station_only_available=0, docsis_cable_device_available=0, telephone_available=0, router_available=1, wlan_access_point_available=0, mac_bridge_available=1, repeater_available=0, other_available=0, reserved_5_enabled=0, reserved_4_enabled=0, reserved_3_enabled=0, reserved_2_enabled=0, reserved_1_enabled=0, two_port_mac_relay_enabled=0, s_vlan_component_enabled=0, c_vlan_component_enabled=0, station_only_enabled=0, docsis_cable_device_enabled=0, telephone_enabled=0, router_enabled=0, wlan_access_point_enabled=0, mac_bridge_enabled=1, repeater_enabled=0, other_enabled=0)/LLDPDUManagementAddress(_type=8, _length=12, _management_address_string_length=5, management_address_subtype=1, management_address=b'\\n\\x0e\\x1e\\xfa', interface_numbering_subtype=3, interface_number=0, _oid_string_length=0, object_id=b'')/LLDPDUGenericOrganisationSpecific(_type=127, _length=6, org_code=32962, subtype=1, data=b'\\x02\\x9a')/LLDPDUGenericOrganisationSpecific(_type=127, _length=9, org_code=4623, subtype=1, data=b'\\x03l\\x01\\x00\\x1e')/LLDPDUEndOfLLDPDU(_type=0, _length=0)",
            },
            "interface": "GigabitEthernet0/5",
            "port_label": "hw103c-testing",
            "role": "Desktop PC",
            "room": ""
        }
        Command().handle(local=False, username='helpdesk_service_account', job='uoft_nautobot.jobs.HelpdeskPortActivation', profile=False, data=json.dumps(d))