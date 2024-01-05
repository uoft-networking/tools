from uoft_aruba import Settings, ArubaRESTAPIClient
from .. import batch

import pytest


def _get_blacklist(*controllers):
    blacklist = []
    for controller in controllers:
        controller: ArubaRESTAPIClient
        blacklist += [x["STA"] for x in controller.wlan.get_ap_client_blacklist()]
    return set(blacklist)


@pytest.mark.end_to_end
class APITests:
    def test_blmgr_blacklist(self):
        s = Settings.from_cache()

        mm = s.mm_api_connection
        md1 = s.md_api_connections[0]
        md2 = s.md_api_connections[1]

        try:
            mm.login()
            md1.login()
            md2.login()
            mm.wlan.blmgr_blacklist_add("11:11:11:11:11:11")
            blacklist = _get_blacklist(md1, md2)
            assert "11:11:11:11:11:11" in blacklist
            mm.wlan.blmgr_blacklist_remove("11:11:11:11:11:11")
            blacklist = _get_blacklist(md1, md2)
            assert "11:11:11:11:11:11" not in blacklist
        finally:
            mm.logout()
            md1.logout()
            md2.logout()

    def test_cpsec_whitelist(self):
        s = Settings.from_cache()

        mm = s.mm_api_connection
        md1 = s.md_api_connections[0]
        md2 = s.md_api_connections[1]

        try:
            mm.login()
            md1.login()
            md2.login()

            group_name = mm.wlan.get_ap_groups()[0]["profile-name"]
            mm.ap_provisioning.wdb_cpsec_add_mac(
                "11:11:11:11:11:11", group_name, "testap"
            )
            whitelist = mm.ap_provisioning.get_cpsec_whitelist()
            whitelist = {x["MAC-Address"]: x for x in whitelist}
            assert "11:11:11:11:11:11" in whitelist

            mm.ap_provisioning.wdb_cpsec_delete_mac("11:11:11:11:11:11")

            whitelist = mm.ap_provisioning.get_cpsec_whitelist()
            whitelist = {x["MAC-Address"]: x for x in whitelist}
            assert "11:11:11:11:11:11" not in whitelist

        finally:
            mm.logout()
            md1.logout()
            md2.logout()


@pytest.mark.end_to_end
def test_batch_provisioner():
    p = batch.Provisioner(dry_run=True)
    groups = list(p.all_groups_by_name)
    valid_group = groups[0]
    other_group = groups[1]
    ap_invalid_group = "invalid_group"

    ap_already_provisioned = "already_provisioned", valid_group, "00:1a:1e:00:00:00"
    ap_to_provision = "to_provision", valid_group, "00:1a:1e:00:00:01"
    ap_invalid_group = (
        "invalid_group",
        ap_invalid_group,
        "00:1a:1e:00:00:02",
    )
    ap_other_group = (
        "other_group",
        other_group,
        "00:1a:1e:00:00:03",
    )
    ap_mac_in_use = (
        "mac_in_use",
        valid_group,
        "00:1a:1e:00:00:04",
    )

    input_list = [
        ap_already_provisioned,
        ap_to_provision,
        ap_invalid_group,
        ap_other_group,
        ap_mac_in_use,
    ]

    # setup

    # we want 'ap_already_provisioned' to already exist in the whitelist
    # by the time we run the batch provisioner
    p.mobility_master.ap_provisioning.wdb_cpsec_add_mac(
        ap_name=ap_already_provisioned[0],
        ap_group=ap_already_provisioned[1],
        mac_address=ap_already_provisioned[2],
    )

    # we want 'ap_other_group' to already exist in the whitelist
    # but in a different group than the one we're trying to provision it in
    p.mobility_master.ap_provisioning.wdb_cpsec_add_mac(
        ap_name=ap_other_group[0],
        ap_group=valid_group,
        mac_address=ap_other_group[2],
    )

    # we want the mac address of 'ap_mac_in_use' to already exist in the whitelist
    # but with a different ap name than the one we're trying to provision
    p.mobility_master.ap_provisioning.wdb_cpsec_add_mac(
        ap_name="already_in_use",
        ap_group=valid_group,
        mac_address=ap_mac_in_use[2],
    )

    try:
        res = p.provision_aps(input_list)
    finally:
        for *_, mac in input_list:
            try:
                p.mobility_master.ap_provisioning.wdb_cpsec_delete_mac(mac)
            except Exception as e:
                if "Entry does not exist" in e.args[0]:
                    pass
                else:
                    raise e

    assert len(res) == len(input_list)
    assert isinstance(res[0], batch.AP)
    assert isinstance(res[1], batch.AP)
    assert isinstance(res[2], batch.InvalidField)
    assert res[2].field == "ap_group"
    assert "does not exist" in res[2].args[0]
    assert isinstance(res[3], batch.AlreadyExists)
    assert "already exists on controller in group" in res[3].args[0]
    assert isinstance(res[4], batch.AlreadyExists)
    assert "already exists on controller with AP_NAME" in res[4].args[0]
