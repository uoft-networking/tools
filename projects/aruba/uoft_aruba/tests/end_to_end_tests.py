from uoft_aruba import Settings, ArubaRESTAPIClient

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
            mm.ap_provisioning.wdb_cpsec_add_mac("11:11:11:11:11:11", group_name, "testap")
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
